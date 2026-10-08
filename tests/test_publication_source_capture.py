from pathlib import Path
import importlib.util,tempfile,unittest
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

if __name__=='__main__':unittest.main(verbosity=2)
