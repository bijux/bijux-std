from pathlib import Path
import importlib.util,tempfile,unittest
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bijux_source_capture',ROOT/'shared/bijux-docs/security/producer_authority.py');authority=importlib.util.module_from_spec(spec);spec.loader.exec_module(authority)

class SourceCapture(unittest.TestCase):
 def setUp(self):
  runtime=ROOT/'artifacts/qualification/publication-source-capture';runtime.mkdir(parents=True,exist_ok=True)
  self.scratch=tempfile.TemporaryDirectory(dir=runtime);self.addCleanup(self.scratch.cleanup);self.root=Path(self.scratch.name)
 def test_generated_trees_are_pruned_before_access(self):
  (self.root/'mkdocs.yml').write_text('site_name: Bijux')
  for name in ('artifacts','.git','__pycache__'):
   path=self.root/name;path.mkdir();(path/'must-not-read').write_text('generated')
  real=Path.read_bytes;observed=[]
  def read(path):observed.append(path.relative_to(self.root).as_posix());return real(path)
  with patch.object(Path,'read_bytes',read):result=authority.files(self.root,source=True)
  self.assertEqual(observed,['mkdocs.yml']);self.assertEqual(set(result),{'mkdocs.yml'})
 def test_public_output_scan_keeps_artifact_named_subtree(self):
  (self.root/'artifacts').mkdir();(self.root/'artifacts/report.js').write_text('owned report')
  self.assertEqual(set(authority.files(self.root)),{'artifacts/report.js'})
 def test_owned_nested_artifact_named_content_is_retained(self):
  (self.root/'docs/artifacts').mkdir(parents=True);(self.root/'docs/artifacts/guide.md').write_text('authored')
  self.assertEqual(set(authority.files(self.root,source=True)),{'docs/artifacts/guide.md'})
 def test_symlinked_owned_source_is_rejected(self):
  (self.root/'docs').mkdir();(self.root/'docs/link').symlink_to(self.root/'missing')
  with self.assertRaisesRegex(ValueError,'symlink'):authority.files(self.root,source=True)

class PublicationSourceCapture(unittest.TestCase):
 def setUp(self):
  SourceCapture.setUp(self)
  self.git('init','-q')
  (self.root/'.gitignore').write_text('artifacts/\n.hypothesis\n*.ignored.md\n')
  (self.root/'docs').mkdir()
  (self.root/'docs/guide.md').write_text('# Reader guide\n')
  (self.root/'mkdocs.yml').write_text('site_name: Bijux\n')
  self.git('add','.gitignore','docs/guide.md','mkdocs.yml')
  self.commit()
 def git(self,*args):
  return subprocess.check_output(['git','-C',str(self.root),*args],text=True)
 def commit(self):
  self.git('-c','user.name=Bijux','-c','user.email=tests@bijux.invalid','commit','-qm','test: capture owned publication source')
 def test_ignored_run_aliases_do_not_become_renderer_source(self):
  (self.root/'artifacts/cache').mkdir(parents=True)
  (self.root/'.hypothesis').symlink_to('artifacts/cache',target_is_directory=True)
  (self.root/'packages/runtime').mkdir(parents=True)
  (self.root/'packages/runtime/.hypothesis').symlink_to('../../artifacts/cache',target_is_directory=True)
  result=authority.files(self.root,source=True,publication_source=True)
  self.assertEqual(set(result),{'.gitignore','docs/guide.md','mkdocs.yml'})
 def test_untracked_publication_source_is_rejected(self):
  (self.root/'docs/new.md').write_text('# Unreviewed\n')
  with self.assertRaisesRegex(ValueError,'publication source is dirty'):
   authority.files(self.root,source=True,publication_source=True)
 def test_changed_tracked_publication_source_is_rejected(self):
  (self.root/'docs/guide.md').write_text('# Changed\n')
  with self.assertRaisesRegex(ValueError,'publication source is dirty'):
   authority.files(self.root,source=True,publication_source=True)
 def test_committed_source_symlink_is_rejected(self):
  guide=self.root/'docs/guide.md';guide.unlink();guide.symlink_to('../mkdocs.yml')
  self.git('add','docs/guide.md');self.commit()
  with self.assertRaisesRegex(ValueError,'symlink tracked source'):
   authority.files(self.root,source=True,publication_source=True)
 def test_ignored_actual_renderer_input_is_still_rejected(self):
  (self.root/'docs/private.ignored.md').write_text('# Not accepted source\n')
  authority.files(self.root,source=True,publication_source=True)
  spec=importlib.util.spec_from_file_location('bijux_actual_source_inputs',ROOT/'shared/bijux-docs/security/build_identity.py')
  identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)
  config=SimpleNamespace(docs_dir=self.root/'docs',theme={},hooks={})
  with self.assertRaisesRegex(ValueError,'ignored renderer source'):
   identity.source_inputs(config,self.root,publication_scope=True)

if __name__=='__main__':unittest.main(verbosity=2)
