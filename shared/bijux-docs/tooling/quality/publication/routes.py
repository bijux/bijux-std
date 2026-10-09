"""Build a deterministic route inventory and resolve links against its artifact."""
from __future__ import annotations
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET
from validate_production_url import development_host


class Document(HTMLParser):
    def __init__(self, path: Path, url: str):
        super().__init__(convert_charrefs=True)
        self.path, self.url = path, url
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.canonicals: list[str] = []
        self.noindex = False
        self.redirect = False
        self.refreshes: list[str | None] = []
        self.base_hrefs: list[str | None] = []
        self.config = ''
        self._config = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'base':
            self.base_hrefs.extend(value for key,value in attrs if key == 'href')
        if values.get('id'):
            self.ids.append(values['id'])
        if tag == 'a' and values.get('name') and values.get('name') != values.get('id'):
            self.ids.append(values['name'])
        if tag == 'link' and 'canonical' in (values.get('rel') or '').split():
            self.canonicals.append(values.get('href') or '')
        elif tag in {'a', 'area', 'link'} and values.get('href'):
            self.references.append(('link' if tag in {'a','area'} else 'asset', values['href']))
        for key in ('src', 'poster', 'action', 'formaction'):
            if values.get(key):
                self.references.append(('asset', values[key]))
        if tag == 'meta':
            self.noindex |= values.get('name','').lower() == 'robots' and 'noindex' in values.get('content','').lower()
            if any(key == 'http-equiv' and (value or '').strip().lower() == 'refresh' for key,value in attrs):
                self.redirect = True
                # Ambiguous duplicate attributes cannot select browser authority.
                counts = Counter(key for key,_ in attrs)
                self.refreshes.append(values.get('content') if counts['http-equiv'] == counts['content'] == 1 else None)
        if tag == 'script' and values.get('id') == '__config':
            self._config = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self._config = False

    def handle_data(self, data):
        if self._config:
            self.config += data


def route_url(site_url: str, relative: str) -> str:
    if relative == 'index.html':
        relative = ''
    elif relative.endswith('/index.html'):
        relative = relative[:-len('index.html')]
    return urljoin(site_url, quote(relative,safe="/"))


def inventory(site: Path, site_url: str) -> dict[Path, Document]:
    result = {}
    for path in sorted(site.rglob('*.html')):
        if path.is_symlink():
            raise ValueError(f'Symlink route is not admitted: {path.relative_to(site)}')
        doc = Document(path, route_url(site_url, path.relative_to(site).as_posix()))
        doc.feed(path.read_text(encoding='utf-8'))
        result[path.resolve()] = doc
    if not result or (site/'index.html').resolve() not in result:
        raise ValueError('Selected artifact must contain at least its root index.html')
    return result


def resolve(site: Path, site_url: str, current: str, value: str) -> tuple[Path | None, str]:
    url = urlsplit(urljoin(current, value))
    base = urlsplit(site_url)
    if url.scheme not in {'http','https'} or url.netloc != base.netloc:
        return None, ''
    if not url.path.startswith(base.path):
        return None, ''
    relative = unquote(url.path[len(base.path):])
    target = (site/relative).resolve()
    if not target.is_relative_to(site.resolve()):
        raise ValueError('Local reference escapes the selected artifact')
    if target.is_dir() or url.path.endswith('/'):
        target /= 'index.html'
    return target, unquote(url.fragment)


def is_network_boundary(site_url: str, target: str, network_urls: list[str]) -> bool:
    absolute = urljoin(site_url, target)
    # Another product's publication is outside this artifact, even on the same origin.
    return any(root != site_url and absolute.startswith(root) and len(urlsplit(root).path) > len(urlsplit(site_url).path)
               for root in network_urls)


def validate_reference(value: str, current: str, kind: str, label: str,
                       exceptions: list[dict], observations: list[dict]) -> str | None:
    if any(c in value for c in ('{', '}', '\\')) or any(ord(c) < 32 for c in value):
        return 'malformed/unrendered public URL ' + value
    try:
        parsed = urlsplit(urljoin(current, value))
        hostname = parsed.hostname or ''
        if parsed.scheme not in {'http', 'https'}:
            return None
        if not hostname or parsed.username is not None or parsed.password is not None:
            return 'public URL cannot contain credentials or a missing hostname'
        if '%' in hostname:
            return 'malformed public URL hostname ' + value
        _ = parsed.port
        if development_host(hostname):
            allowed = kind == 'link' and next((item for item in exceptions
                       if item['route'] == label and item['url'] == value), None)
            observations.append(dict(route=label,url=value,kind=kind,
                                     classification='development-origin',exempted=bool(allowed),
                                     purpose=allowed['purpose'] if allowed else None))
            if not allowed:
                return 'development/private host in public ' + kind + ' URL ' + value
        elif kind == 'asset' and parsed.scheme == 'http':
            return 'insecure active resource URL ' + value
    except ValueError:
        return 'malformed public URL ' + value
    return None


def refresh_destination(doc: Document) -> str:
    """Read one explicit refresh target without substituting its canonical URL."""
    failure = 'redirect refresh requires one unambiguous destination'
    if len(doc.refreshes) != 1 or not isinstance(doc.refreshes[0],str):
        raise ValueError(failure)
    match = re.fullmatch(r'\s*[0-9]+(?:\.[0-9]+)?\s*;\s*(?:url\s*=\s*)?(.*?)\s*',
                         doc.refreshes[0], re.IGNORECASE)
    if not match:
        raise ValueError(failure)
    destination = match[1]
    if destination.startswith(('"',"'")):
        if len(destination) < 2 or destination[-1] != destination[0]:
            raise ValueError(failure)
        destination = destination[1:-1].strip()
    if not destination:
        raise ValueError(failure)
    return destination


def redirect_destination(site: Path, site_url: str, doc: Document,
                         docs: dict[Path, Document], label: str,
                         observations: list[dict]) -> tuple[Path | None, str | None]:
    try:
        if any(doc.base_hrefs):
            return None, 'unsupported redirect base href for a public URL'
        value = refresh_destination(doc)
        # Automatic navigation cannot inherit an authored development-link exception.
        failure = validate_reference(value,doc.url,'asset',label,[],observations)
        if failure:
            return None, 'redirect refresh: ' + failure
        target, fragment = resolve(site,site_url,doc.url,value)
        if target not in docs:
            return None, 'redirect refresh must reach a built production route'
        if fragment and fragment not in docs[target].ids:
            return target, 'redirect refresh anchor is missing'
        if len(doc.canonicals) == 1:
            canonical, _ = resolve(site,site_url,doc.url,doc.canonicals[0])
            if target != canonical:
                return target, 'redirect refresh destination differs from canonical'
        return target, None
    except ValueError as exc:
        return None, str(exc)


def redirect_cycles(site: Path, edges: dict[Path, Path]) -> list[str]:
    """Traverse each built refresh edge once, including self and joined cycles."""
    errors = []
    finished = set()
    for source in edges:
        pending = {}
        current = source
        while current in edges and current not in finished:
            if current in pending:
                cycle = list(pending)[pending[current]:]
                errors.append('redirect refresh cycle: '+', '.join(sorted(p.relative_to(site).as_posix() for p in cycle)))
                break
            pending[current] = len(pending)
            current = edges[current]
        finished.update(pending)
    return errors


def validate(site: Path, site_url: str, docs: dict[Path, Document], network_urls: list[str],
             exceptions: list[dict] | None = None,
             observations: list[dict] | None = None) -> list[str]:
    errors = []
    exceptions = exceptions or []
    observations = observations if observations is not None else []
    canonical_routes = set()
    redirect_edges = {}
    for path, doc in docs.items():
        label = path.relative_to(site).as_posix()
        duplicate = [key for key, count in Counter(doc.ids).items() if count > 1]
        if duplicate:
            errors.append(f'{label}: duplicate document IDs: {", ".join(sorted(duplicate))}')
        if path.name != '404.html':
            # Redirect producers may identify their destination relative to this route.
            canonical = urljoin(doc.url, doc.canonicals[0]) if len(doc.canonicals) == 1 else None
            if len(doc.canonicals) != 1 or (not doc.redirect and doc.canonicals[0] != doc.url):
                errors.append(f'{label}: canonical must identify this production route ({doc.url})')
            elif not doc.noindex:
                canonical_routes.add(canonical)
            if doc.redirect and doc.canonicals:
                target, _ = resolve(site,site_url,doc.url,doc.canonicals[0])
                if target not in docs or canonical != docs[target].url:
                    errors.append(f'{label}: redirect canonical does not reach a built route')
        if doc.redirect:
            target, failure = redirect_destination(site,site_url,doc,docs,label,observations)
            if target is not None:
                redirect_edges[path] = target
            if failure:
                errors.append(f'{label}: {failure}')
        for kind, value in doc.references:
            failure = validate_reference(value,doc.url,kind,label,exceptions,observations)
            if failure:
                errors.append(f'{label}: {failure}')
                continue
            if is_network_boundary(site_url,urljoin(doc.url,value),network_urls):
                continue
            try:
                target, fragment = resolve(site,site_url,doc.url,value)
            except ValueError as exc:
                errors.append(f'{label}: {exc}')
                continue
            if target is None:
                continue
            if not target.is_file():
                errors.append(f'{label}: missing {kind} destination {value}')
            elif kind == 'link' and fragment and target in docs and fragment not in docs[target].ids:
                errors.append(f'{label}: missing anchor {value}')
    errors.extend(redirect_cycles(site,redirect_edges))
    for path in sorted(site.rglob('*.css')):
        css = path.read_text(encoding='utf-8')
        values = re.findall(r'url\(\s*[\'"]?([^\'"\)\s]+)',css)
        values += re.findall(r'@import\s+[\'"]([^\'"]+)',css)
        for value in values:
            failure = validate_reference(value,urljoin(site_url,path.relative_to(site).as_posix()),'asset',path.relative_to(site).as_posix(),exceptions,observations)
            if failure:
                errors.append(f'{path.relative_to(site)}: {failure}')
                continue
            target, _ = resolve(site,site_url,urljoin(site_url,path.relative_to(site).as_posix()),value)
            if target is not None and not target.is_file():
                errors.append(f'{path.relative_to(site)}: missing CSS asset {value}')
    sitemap = site/'sitemap.xml'
    if not sitemap.is_file():
        errors.append('Selected artifact is missing sitemap.xml')
    else:
        try:
            urls = [node.text or '' for node in ET.parse(sitemap).iter() if node.tag.rsplit('}',1)[-1] == 'loc']
            if len(urls) != len(set(urls)):
                errors.append('sitemap.xml: duplicate route entries')
            unknown = set(urls)-canonical_routes
            missing = canonical_routes-set(urls)
            if unknown:
                errors.append('sitemap.xml: noncanonical/nonproduction/excluded routes: '+', '.join(sorted(unknown)))
            if missing:
                errors.append('sitemap.xml: missing eligible canonical routes: '+', '.join(sorted(missing)))
        except ET.ParseError:
            errors.append('sitemap.xml: invalid XML')
    compressed = site/'sitemap.xml.gz'
    if compressed.exists():
        import gzip
        from io import BytesIO
        try:
            plain = sitemap.read_bytes()
            if compressed.is_symlink() or gzip.GzipFile(fileobj=BytesIO(compressed.read_bytes())).read(len(plain)+1) != plain:
                errors.append('sitemap.xml.gz: content differs from the plain sitemap')
        except (OSError,EOFError):
            errors.append('sitemap.xml.gz: invalid compressed sitemap')
    return errors


def records(site: Path, docs: dict[Path, Document]) -> list[dict]:
    return [dict(path=path.relative_to(site).as_posix(), url=doc.url,
                 canonical=doc.canonicals, noindex=doc.noindex, redirect=doc.redirect,
                 anchors=len(set(doc.ids)), references=len(doc.references))
            for path,doc in docs.items()]
