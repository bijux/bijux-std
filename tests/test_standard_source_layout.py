"""Keep canonical source and consumer paths independent of checkout names."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'shared/bijux-checks/scripts/standard-source-layout.sh'

class StandardSourceLayoutTests(unittest.TestCase):
    def test_checkout_identity_and_authored_layout_both_select_canonical_source(self):
        owner=ROOT/'artifacts/tests/source-layout';owner.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as directory:
            for name,remote,source,expected in [
                ('owned-checkout','git@github.com:bijux/bijux-std.git',True,0),
                ('bijux-std','https://github.com/bijux/bijux-ro-crate-node.git',True,1),
                ('consumer','https://github.com/bijux/bijux-std.git',False,1),
            ]:
                root=Path(directory)/name;root.mkdir()
                subprocess.run(['git','init','-q',str(root)],check=True)
                subprocess.run(['git','-C',str(root),'remote','add','origin',remote],check=True)
                if source:
                    (root/'shared/bijux-checks').mkdir(parents=True)
                    (root/'shared/shared-dir-sha256.txt').write_text('source-owned manifest')
                result=subprocess.run(['bash','-c','source "$1"; is_standard_source_checkout "$2"','fixture',str(HELPER),str(root)])
                self.assertEqual(result.returncode,expected,name)
