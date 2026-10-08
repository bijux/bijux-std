"""Validate complete source projection without touching downstream repositories."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MASTERCLASS_EXTRAHEAD = '''{% extends "base.html" %}

{% block extrahead %}
  {{ super() }}
  <link rel="icon" href="{{ 'favicon.ico' | url }}">
  <link rel="apple-touch-icon" href="{{ 'apple-touch-icon.png' | url }}">
  <link rel="apple-touch-icon-precomposed" href="{{ 'apple-touch-icon-precomposed.png' | url }}">
{% endblock %}
'''

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(os.environ.get('BIJUX_TEST_DOCS_SCRIPTS', ROOT/'shared/bijux-docs/tooling/scripts'))
SCRIPT = SCRIPTS/'project_bijux_docs.py'
spec = importlib.util.spec_from_file_location('bijux_docs_projection', SCRIPT)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


class DocsSourceProjectionTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/website-delivery'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix='docs-projection-', dir=artifacts)
        self.addCleanup(self.sandbox.cleanup)
        self.repo = Path(self.sandbox.name) / 'consumer'
        self.shared = self.repo / '.bijux/shared/bijux-docs'
        for name in ('header.html','footer.html','footer-profile-links.html','nav.html','nav-item.html','bijux-nav.html','logo.html','javascripts/base.html','javascripts/palette.html'):
            path = self.shared / 'partials' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('canonical ' + name)
        for name in ('styles/extra.css','scripts/bootstrap.js','scripts/nav-sync.js','scripts/mermaid-init.js','assets/javascripts/vendor/mermaid-11.6.0.min.js'):
            path = self.shared / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('canonical ' + name)
        (self.shared / 'config').mkdir()
        vendor = self.shared / 'assets/javascripts/vendor/mermaid-11.6.0.min.js'
        (self.shared / 'config/mkdocs-baseline.json').write_text(json.dumps(dict(required_exclude_docs=['/overrides/','/hooks/'],diagram=dict(
            vendor='assets/javascripts/vendor/mermaid-11.6.0.min.js',sha256=hashlib.sha256(vendor.read_bytes()).hexdigest()))))
        for name in ('root/docs.mk','ci/docs.mk'):
            source = self.shared.parent / 'bijux-makes-py' / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('canonical ' + name)
            target = self.repo / 'makes/bijux-py' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('old ' + name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'bijux@example.invalid')
        self.git('config', 'user.name', 'Bijux projection tests')
        self.commit()

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.repo), *arguments],
                              capture_output=True, text=True, check=True)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'test(docs): retain projected source')

    def snapshot(self):
        return {path.relative_to(self.repo).as_posix(): path.read_bytes()
                for path in self.repo.rglob('*')
                if path.is_file() and '.git' not in path.relative_to(self.repo).parts
                and 'artifacts' not in path.relative_to(self.repo).parts}

    def prepare_sync(self):
        scripts = ROOT/'shared/bijux-docs/tooling/scripts'
        shutil.copytree(scripts, self.shared/'tooling/scripts', dirs_exist_ok=True)
        shutil.copytree(ROOT/'shared/bijux-docs/tooling/configuration', self.shared/'tooling/configuration', dirs_exist_ok=True)
        baseline_path = self.shared/'config/mkdocs-baseline.json'
        baseline = json.loads(baseline_path.read_text())
        canonical = json.loads((ROOT/'shared/bijux-docs/config/mkdocs-baseline.json').read_text())
        for field in ('extra_css', 'extra_javascript', 'required_plugins', 'retired_extra_javascript', 'theme', 'retired_theme_logos'):
            baseline[field] = canonical[field]
        baseline_path.write_text(json.dumps(baseline))
        if SCRIPTS != scripts:
            shutil.copytree(SCRIPTS, self.shared/'tooling/scripts', dirs_exist_ok=True)
        (self.shared/'config/hub-links.json').write_text(json.dumps([
            dict(key='fixture',label='Fixture',url='https://bijux.io/')]))
        config = 'extra:\n  bijux:\n    repository: fixture\n'
        (self.repo/'mkdocs.shared.yml').write_text(config)
        (self.repo/'mkdocs.yml').write_text('INHERIT: mkdocs.shared.yml\n' + config)
        self.commit()

    def run_sync(self, **environment):
        return subprocess.run(['bash', str(self.shared/'tooling/scripts/sync_bijux_docs.sh')],
                              cwd=self.repo, text=True, capture_output=True,
                              env={**os.environ, 'BIJUX_STD_LOCAL_VERIFY':'1', **environment})

    def test_nested_palette_base_and_logo_are_projected_and_checked(self):
        projection.apply(self.repo,self.shared)
        for name in ('javascripts/base.html','javascripts/palette.html','logo.html'):
            self.assertEqual((self.repo/'docs/overrides/partials'/name).read_bytes(),(self.shared/'partials'/name).read_bytes())
        self.assertEqual(projection.apply(self.repo,self.shared,check=True),[])

    def test_material_main_override_projects_at_template_root(self):
        (self.shared/'partials/main.html').write_text('Canonical Material scripts block')
        projection.apply(self.repo,self.shared)
        self.assertEqual((self.repo/'docs/overrides/main.html').read_text(),'Canonical Material scripts block')
        self.assertFalse((self.repo/'docs/overrides/partials/main.html').exists())
        self.assertEqual(projection.apply(self.repo,self.shared,check=True),[])

    def test_python_docs_profiles_refresh_with_the_same_projection(self):
        projection.apply(self.repo,self.shared)
        self.assertEqual((self.repo/'makes/bijux-py/root/docs.mk').read_text(),'canonical root/docs.mk')
        self.assertEqual((self.repo/'makes/bijux-py/ci/docs.mk').read_text(),'canonical ci/docs.mk')

    def test_nested_generated_drift_is_rejected(self):
        projection.apply(self.repo,self.shared)
        (self.repo/'docs/overrides/partials/javascripts/palette.html').write_text('wrong generated state')
        with self.assertRaisesRegex(RuntimeError,'javascripts/palette.html'):
            projection.apply(self.repo,self.shared,check=True)

    def test_altered_pinned_vendor_fails_before_any_projection_mutation(self):
        before = (self.repo/'makes/bijux-py/root/docs.mk').read_bytes()
        (self.shared/'assets/javascripts/vendor/mermaid-11.6.0.min.js').write_text('changed bytes')
        with self.assertRaisesRegex(RuntimeError,'altered pinned diagram vendor'):
            projection.apply(self.repo,self.shared)
        self.assertEqual((self.repo/'makes/bijux-py/root/docs.mk').read_bytes(),before)
        self.assertFalse((self.repo/'docs').exists())

    def test_missing_python_source_fails_before_generated_docs_write(self):
        (self.shared.parent/'bijux-makes-py/ci/docs.mk').unlink()
        with self.assertRaisesRegex(RuntimeError,'Missing canonical projection inputs'):
            projection.apply(self.repo,self.shared)
        self.assertFalse((self.repo/'docs').exists())

    def test_author_readmes_are_not_projected_as_public_pages(self):
        (self.shared/'styles/README.md').write_text('Style author guide')
        (self.shared/'scripts/README.md').write_text('Runtime author guide')
        projection.apply(self.repo,self.shared)
        self.assertFalse((self.repo/'docs/assets/styles/README.md').exists())
        self.assertFalse((self.repo/'docs/assets/javascripts/shell/README.md').exists())

    def test_legacy_generated_author_readme_is_retired_without_overwriting_user_work(self):
        source = self.shared/'styles/README.md'
        source.write_text('Style author guide')
        target = self.repo/'docs/assets/styles/README.md'
        target.parent.mkdir(parents=True)
        target.write_text(source.read_text())
        self.commit()
        projection.apply(self.repo,self.shared)
        self.assertFalse(target.exists())
        target.write_text('User-edited guide')
        with self.assertRaisesRegex(RuntimeError,'Preserve modified author documentation'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(target.read_text(),'User-edited guide')

    def test_pending_tracked_projected_work_preserves_all_files(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        for relative in ('docs/overrides/partials/javascripts/palette.html',
                         'docs/assets/javascripts/vendor/mermaid-11.6.0.min.js',
                         'makes/bijux-py/ci/docs.mk'):
            with self.subTest(destination=relative):
                destination = self.repo/relative
                original = destination.read_bytes()
                destination.write_text('Pending user work')
                before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError,'Preserve local generated destination changes'):
                    projection.apply(self.repo,self.shared)
                self.assertEqual(self.snapshot(),before)
                destination.write_bytes(original)

    def test_staged_projected_work_preserves_all_files(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        target = self.repo/'docs/overrides/partials/logo.html'
        target.write_text('Staged user work')
        self.git('add',str(target.relative_to(self.repo)))
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Preserve local generated destination changes'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_untracked_projected_work_preserves_all_files(self):
        target = self.repo/'docs/assets/javascripts/shell/bootstrap.js'
        target.parent.mkdir(parents=True)
        target.write_text('Untracked user work')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Preserve untracked generated destination input'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_destination_collision_fails_before_config_and_any_generated_mutation(self):
        self.prepare_sync()
        collision = self.repo/'docs/overrides/partials/nav-item.html'
        collision.mkdir(parents=True)
        (collision/'user.txt').write_text('Preserved user directory')
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('not a regular file',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_complete_local_candidate_sync_is_explicit_and_idempotent(self):
        self.prepare_sync()
        first = self.run_sync()
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertIn('Local candidate verification only',first.stdout)
        self.assertIn('hub_links:',(self.repo/'mkdocs.shared.yml').read_text())
        self.assertEqual((self.repo/'makes/bijux-py/ci/docs.mk').read_text(),'canonical ci/docs.mk')
        self.commit()
        before = self.snapshot()
        second = self.run_sync()
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_readme_conflict_fails_before_config_and_any_generated_mutation(self):
        self.prepare_sync()
        (self.shared/'styles/README.md').write_text('Canonical author guide')
        target = self.repo/'docs/assets/styles/README.md'
        target.parent.mkdir(parents=True)
        target.write_text('Edited author guide')
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Preserve modified author documentation',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_dirty_config_fails_before_any_projection_mutation(self):
        self.prepare_sync()
        (self.repo/'mkdocs.yml').write_text('extra:\n  bijux:\n    repository: user-work\n')
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Preserve local generated destination changes',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_applicable_make_source_must_match_independently_fetched_authority(self):
        self.prepare_sync()
        checks = self.shared.parent/'bijux-checks/scripts'
        checks.mkdir(parents=True)
        for name in ('verify-accepted-source.sh','directory-tree-sha256.sh'):
            shutil.copy2(ROOT/'shared/bijux-checks/scripts'/name,checks/name)
        upstream = self.repo.parent/'upstream'
        shutil.copytree(self.shared.parent,upstream/'shared')
        def upstream_git(*args):
            return subprocess.run(['git','-C',str(upstream),*args],capture_output=True,text=True,check=True)
        upstream_git('init','-q')
        upstream_git('config','user.email','bijux@example.invalid')
        upstream_git('config','user.name','Bijux authority tests')
        upstream_git('add','shared')
        upstream_git('commit','-qm','test(std): publish fixture authority')
        sha = upstream_git('rev-parse','HEAD').stdout.strip()
        authority = self.repo.parent/'authority'
        subprocess.run(['git','clone','-q',str(upstream),str(authority)],check=True,capture_output=True)
        (self.shared.parent/'bijux-makes-py/ci/docs.mk').write_text('Unauthorized local profile')
        before = self.snapshot()
        result = self.run_sync(BIJUX_STD_LOCAL_VERIFY='0',BIJUX_STD_ALLOW_LOCAL_SOURCE='1',
                               BIJUX_STD_ROOT=str(authority),BIJUX_STD_REF=sha,
                               BIJUX_STD_GIT_URL=str(upstream))
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn('local shared Python Make profiles differ',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_production_url_guard_rejects_loopback_and_keeps_public_subpath(self):
        import subprocess, sys
        validator = ROOT/'shared/bijux-docs/tooling/quality/validate_production_url.py'
        for value in ('http://127.0.0.1:8000/', 'https://localhost/', 'https://[::1]/', 'https://192.168.1.1/', 'https://bijux.io/bijux-core/?preview=1'):
            with self.subTest(url=value):
                result = subprocess.run([sys.executable,str(validator),value],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
        result = subprocess.run([sys.executable,str(validator),'https://bijux.io/bijux-core/'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_non_python_consumer_does_not_gain_unrequested_make_profiles(self):
        import shutil
        shutil.rmtree(self.repo/'makes')
        projection.apply(self.repo,self.shared)
        self.assertFalse((self.repo/'makes').exists())

    def ownership(self):
        return self.repo / projection.OWNERSHIP

    def authority(self):
        root = self.repo.parent / 'authority'
        shutil.copytree(self.shared.parent, root/'shared')
        self.authority_root = root
        self.authority_git('init', '-q')
        self.authority_git('config', 'user.email', 'bijux@example.invalid')
        self.authority_git('config', 'user.name', 'Bijux source object tests')
        self.authority_git('remote', 'add', 'origin', 'https://github.com/bijux/bijux-std.git')
        return self.publish_authority()

    def authority_git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.authority_root), *arguments], check=True, text=True, capture_output=True)

    def publish_authority(self):
        self.authority_git('add', 'shared')
        self.authority_git('commit', '-qm', 'test(docs): retain source object')
        return {'mode': 'accepted-github', 'origin': 'https://github.com/bijux/bijux-std.git',
                'sha': self.authority_git('rev-parse', 'HEAD').stdout.strip(), 'authority': str(self.authority_root)}

    def test_clean_committed_masterclass_extrahead_is_never_automatically_adopted(self):
        self.prepare_sync()
        target = self.repo/'docs/overrides/main.html'
        target.parent.mkdir(parents=True)
        target.write_text(MASTERCLASS_EXTRAHEAD)
        self.commit()
        first = self.run_sync()
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertEqual(target.read_text(),MASTERCLASS_EXTRAHEAD)
        self.assertNotIn('docs/overrides/main.html',json.loads(self.ownership().read_text())['files'])
        self.commit()
        (self.shared/'partials/main.html').write_text('Canonical scripts ownership')
        self.commit()
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('explicit authored extension migration', result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('docs/overrides/main.html',json.loads(self.ownership().read_text())['files'])

    def test_even_matching_clean_new_template_requires_explicit_ownership(self):
        target = self.repo/'docs/overrides/main.html'
        target.parent.mkdir(parents=True)
        target.write_text(MASTERCLASS_EXTRAHEAD)
        (self.shared/'partials/main.html').write_text(MASTERCLASS_EXTRAHEAD)
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'consumer-owned extension'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_new_nested_partial_does_not_claim_clean_authored_file(self):
        target = self.repo/'docs/overrides/partials/javascripts/base.html'
        target.parent.mkdir(parents=True)
        target.write_text('Consumer script extension')
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'consumer-owned extension'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_ignored_untracked_matching_legacy_file_is_preserved(self):
        self.prepare_sync()
        target = self.repo/'docs/assets/javascripts/shell/bootstrap.js'
        target.parent.mkdir(parents=True)
        target.write_bytes((self.shared/'scripts/bootstrap.js').read_bytes())
        (self.repo/'.gitignore').write_text('docs/assets/javascripts/shell/bootstrap.js\n')
        self.git('add','.gitignore')
        self.git('commit','-qm','test(docs): retain ignored authored input')
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Preserve untracked generated destination input',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_reviewed_legacy_destination_updates_and_records_generated_hash(self):
        target = self.repo/'docs/overrides/partials/header.html'
        target.parent.mkdir(parents=True)
        target.write_text('Former generated header')
        self.commit()
        projection.apply(self.repo,self.shared)
        record = json.loads(self.ownership().read_text())
        self.assertEqual(target.read_bytes(),(self.shared/'partials/header.html').read_bytes())
        self.assertEqual(record['files']['docs/overrides/partials/header.html']['sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual(record['source'],{'mode':'local-verification','origin':None,'sha':None})

    def test_clean_committed_authored_edits_to_owned_file_cannot_be_overwritten(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        (self.repo/'docs/overrides/partials/header.html').write_text('Authored local header')
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Preserve authored changes'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_symlinked_ownership_parent_is_preserved_before_any_write(self):
        outside = self.repo.parent/'consumer-authored-shared'
        shutil.move(self.repo/'.bijux',outside)
        (self.repo/'.bijux').symlink_to(outside,target_is_directory=True)
        before = self.snapshot()
        outside_before = {str(p.relative_to(outside)):p.read_bytes() for p in outside.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(RuntimeError,'symlinked projection destination'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual({str(p.relative_to(outside)):p.read_bytes() for p in outside.rglob('*') if p.is_file()},outside_before)

    def test_malformed_ownership_record_blocks_config_and_assets_before_mutation(self):
        self.prepare_sync()
        self.ownership().write_text('{"schema":1,"files":')
        self.commit()
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Invalid projection ownership record',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_staged_ownership_metadata_blocks_refresh_without_losing_edits(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        self.ownership().write_text(self.ownership().read_text()+'\n')
        self.git('add',projection.OWNERSHIP)
        (self.shared/'partials/header.html').write_text('Changed canonical header')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Preserve local generated destination changes'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_record_cannot_rename_source_mapping_or_escape_repository(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        record = json.loads(self.ownership().read_text())
        record['files']['../authored.txt']={'source':'../authored.txt','sha256':'a'*64}
        self.ownership().write_text(json.dumps(record))
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Unsafe projection ownership source'):
            projection.apply(self.repo,self.shared)
        self.assertEqual(self.snapshot(),before)

    def test_accepted_previous_source_allows_pristine_generated_refresh(self):
        original = self.authority()
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        source = self.authority_root/'shared/bijux-docs/partials/header.html'
        source.write_text('Updated published header')
        current = self.publish_authority()
        (self.shared/'partials/header.html').write_bytes(source.read_bytes())
        projection.apply(self.repo,self.shared,context=current)
        self.assertEqual((self.repo/'docs/overrides/partials/header.html').read_bytes(),source.read_bytes())
        self.assertEqual(json.loads(self.ownership().read_text())['source']['sha'],current['sha'])
        self.assertEqual(projection.apply(self.repo,self.shared,check=True,context=current),[])

    def test_clean_tampered_record_cannot_forge_root_template_ownership(self):
        (self.shared/'partials/main.html').write_text('Published shared scripts block')
        original = self.authority()
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        target = self.repo/'docs/overrides/main.html'
        target.write_text(MASTERCLASS_EXTRAHEAD)
        record = json.loads(self.ownership().read_text())
        record['files']['docs/overrides/main.html']['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        self.ownership().write_text(json.dumps(record))
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'differs from actual prior accepted source'):
            projection.apply(self.repo,self.shared,context=original)
        self.assertEqual(self.snapshot(),before)

    def test_changed_current_source_is_rejected_before_projection(self):
        original = self.authority()
        (self.shared/'partials/header.html').write_text('Unpublished source mutation')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'differs from verified accepted source'):
            projection.apply(self.repo,self.shared,context=original)
        self.assertEqual(self.snapshot(),before)

    def test_missing_previous_source_object_refuses_unverified_ownership(self):
        original = self.authority()
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        record = json.loads(self.ownership().read_text())
        record['source']['sha']='0'*40
        self.ownership().write_text(json.dumps(record))
        self.commit()
        before = self.snapshot()
        native = subprocess.run
        def unavailable(arguments, **kwargs):
            if 'fetch' in arguments:
                return subprocess.CompletedProcess(arguments,1,b'',b'Controlled unavailable source')
            return native(arguments,**kwargs)
        with mock.patch.object(projection.subprocess,'run',side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError,'fetch exact SHA'):
                projection.apply(self.repo,self.shared,context=original)
        self.assertEqual(self.snapshot(),before)

    def test_local_ownership_never_silently_upgrades_to_accepted_provenance(self):
        projection.apply(self.repo,self.shared)
        self.commit()
        original = self.authority()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'cannot silently become accepted rollout'):
            projection.apply(self.repo,self.shared,context=original)
        self.assertEqual(self.snapshot(),before)

    def test_owned_retirement_requires_exact_previous_generated_bytes(self):
        original = self.authority()
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        (self.authority_root/'shared/bijux-docs/partials/logo.html').unlink()
        current = self.publish_authority()
        (self.shared/'partials/logo.html').unlink()
        target = self.repo/'docs/overrides/partials/logo.html'
        target.write_text('Committed consumer logo extension')
        self.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'before generated retirement'):
            projection.apply(self.repo,self.shared,context=current)
        self.assertEqual(self.snapshot(),before)

    def test_ignored_untracked_ownership_record_is_never_overwritten(self):
        self.prepare_sync()
        (self.repo/'.gitignore').write_text(projection.OWNERSHIP+'\n')
        self.git('add','.gitignore')
        self.git('commit','-qm','test(docs): protect ignored consumer metadata')
        self.ownership().write_text(json.dumps({'schema':1,'source':{'mode':'local-verification','sha':None,'origin':None},'files':{}}))
        before = self.snapshot()
        result = self.run_sync()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Preserve untracked generated destination input',result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_prior_source_auto_fetch_uses_exact_object_and_preserves_shallow_checkout(self):
        original = self.authority()
        upstream = self.authority_root
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        source = upstream/'shared/bijux-docs/partials/header.html'
        source.write_text('Published shallow update')
        current = self.publish_authority()
        shallow = self.repo.parent/'shallow-authority'
        subprocess.run(['git','clone','-q','--depth','1',upstream.as_uri(),str(shallow)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(shallow),'remote','set-url','origin',current['origin']],check=True)
        self.assertNotEqual(subprocess.run(['git','-C',str(shallow),'cat-file','-e',original['sha']+'^{commit}'],capture_output=True).returncode,0)
        (self.shared/'partials/header.html').write_bytes(source.read_bytes())
        current['authority']=str(shallow)
        working_before = {str(p.relative_to(shallow)):p.read_bytes() for p in shallow.rglob('*') if p.is_file() and '.git' not in p.relative_to(shallow).parts}
        native = subprocess.run
        fetches = []
        def fixture_fetch(arguments, **kwargs):
            if 'fetch' in arguments:
                self.assertEqual(arguments,['git','-C',str(shallow),'fetch','--quiet','--depth','1','origin',original['sha']])
                fetches.append(arguments)
                # Keep real Git shallow/object behavior, with only the network
                # transport replaced by the local exact-object fixture source.
                return native([*arguments[:-2],upstream.as_uri(),arguments[-1]],**kwargs)
            return native(arguments,**kwargs)
        with mock.patch.object(projection.subprocess,'run',side_effect=fixture_fetch):
            projection.apply(self.repo,self.shared,context=current)
        self.assertEqual(len(fetches),1)
        self.assertEqual(subprocess.check_output(['git','-C',str(shallow),'rev-parse','HEAD'],text=True).strip(),current['sha'])
        self.assertEqual(subprocess.check_output(['git','-C',str(shallow),'status','--porcelain','--untracked-files=all'],text=True),'')
        self.assertEqual({str(p.relative_to(shallow)):p.read_bytes() for p in shallow.rglob('*') if p.is_file() and '.git' not in p.relative_to(shallow).parts},working_before)
        self.assertEqual((self.repo/'docs/overrides/partials/header.html').read_text(),'Published shallow update')

    def test_origin_mismatch_refuses_before_network_and_all_consumer_mutation(self):
        original = self.authority()
        projection.apply(self.repo,self.shared,context=original)
        self.commit()
        self.authority_git('remote','set-url','origin','https://example.invalid/not-bijux.git')
        before = self.snapshot()
        native = subprocess.run
        def refuse_network(arguments, **kwargs):
            self.assertNotIn('fetch',arguments,'Origin mismatch must fail before any network operation')
            return native(arguments,**kwargs)
        with mock.patch.object(projection.subprocess,'run',side_effect=refuse_network):
            with self.assertRaisesRegex(RuntimeError,'origin differs'):
                projection.apply(self.repo,self.shared,context=original)
        self.assertEqual(self.snapshot(),before)

    def test_independently_fetched_local_fixture_retains_truthful_local_provenance(self):
        self.prepare_sync()
        checks = self.shared.parent/'bijux-checks/scripts'
        checks.mkdir(parents=True)
        for name in ('verify-accepted-source.sh','directory-tree-sha256.sh'):
            shutil.copy2(ROOT/'shared/bijux-checks/scripts'/name,checks/name)
        self.authority()
        sha = self.authority_git('rev-parse','HEAD').stdout.strip()
        authority = self.repo.parent/'fetched-local-authority'
        subprocess.run(['git','clone','-q',str(self.authority_root),str(authority)],check=True,capture_output=True)
        result = self.run_sync(BIJUX_STD_LOCAL_VERIFY='0',BIJUX_STD_ALLOW_LOCAL_SOURCE='1',BIJUX_STD_ROOT=str(authority),BIJUX_STD_REF=sha,BIJUX_STD_GIT_URL=str(self.authority_root))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(self.ownership().read_text())['source'],{'mode':'local-verification','origin':None,'sha':None})


if __name__ == '__main__':
    unittest.main()
