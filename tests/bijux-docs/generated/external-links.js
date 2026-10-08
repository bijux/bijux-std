// Product-owned external link behavior; the shared shell is loaded unchanged.
function bijuxMarkOffsiteLinks() {
  for (const link of document.querySelectorAll("a[href]")) {
    let url;
    try {
      url = new URL(link.getAttribute("href"), window.location.href);
    } catch {
      continue;
    }
    if (url.origin !== window.location.origin && ["https:", "http:"].includes(url.protocol)) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  }
}
document$.subscribe(bijuxMarkOffsiteLinks);
