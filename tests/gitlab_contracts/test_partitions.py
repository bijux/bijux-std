"""Exercise real discovered cases and reject incomplete or counterfeit coverage."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'shared/bijux-gitlab/contracts.py'


def module():
    if not RUNNER.is_file(): raise AssertionError('Source-owned contract partitions are missing')
    spec=importlib.util.spec_from_file_location('bijux_contract_partition_controls',RUNNER)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


class ContractPartitionTests(unittest.TestCase):
    def setUp(self):
        owner=ROOT/'artifacts/qualification/contract-partitions';owner.mkdir(parents=True,exist_ok=True)
        scratch=tempfile.TemporaryDirectory(dir=owner);self.addCleanup(scratch.cleanup)
        self.root=Path(scratch.name)
        (self.root/'tests').mkdir()
        (self.root/'.gitignore').write_text('artifacts/\n__pycache__/\n')
        self.source=self.root/'tests/test_cases.py'
        body=['import unittest\nfrom pathlib import Path\n',
              'def record(value):\n p=Path("artifacts/order.log");p.parent.mkdir(parents=True,exist_ok=True)\n with p.open("a") as stream:stream.write(value+"\\n")\n',
              'def setUpModule():record("module:setup")\ndef tearDownModule():record("module:teardown")\n']
        for name in ('Alpha','Beta'):
            body.append('class '+name+'(unittest.TestCase):\n @classmethod\n def setUpClass(cls):record(cls.__name__+":setup")\n @classmethod\n def tearDownClass(cls):record(cls.__name__+":teardown")\n')
            for index in range(12):body.append(f' def test_{index:02d}(self):record(self.id())\n')
        self.source.write_text(''.join(body))
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        self.commit()

    def commit(self):
        subprocess.run(['git','-C',str(self.root),'add','.gitignore','tests'],check=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Bijux tests','-c','user.email=tests@example.invalid',
                        'commit','-qm','test(contracts): define owned suite'],check=True)
        self.head=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()

    def run_partition(self,index,count=6):
        self.assertTrue(RUNNER.is_file(),'Source-owned contract partitions are missing')
        artifacts=self.root/'artifacts';artifacts.mkdir(exist_ok=True)
        output=Path(tempfile.mkdtemp(dir=artifacts))/'unit-results.json'
        result=subprocess.run([sys.executable,'-B',str(RUNNER),'run','--root',str(self.root),
            '--partition-index',str(index),'--partition-count',str(count),'--output',str(output)],
            cwd=self.root,text=True,capture_output=True)
        self.assertTrue(output.is_file(),result.stderr)
        return result,json.loads(output.read_text())

    def successful(self):
        receipts=[]
        for index in range(6):
            result,receipt=self.run_partition(index)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(receipt['status'],'passed')
            receipts.append(receipt)
        return receipts

    def test_six_real_partitions_cover_complete_discovery_in_fixture_order(self):
        receipts=self.successful()
        coverage=module().verify_coverage(receipts,self.head)
        self.assertEqual(coverage['executed_cases'],24)
        self.assertEqual(coverage['partition_count'],6)
        expected=[f'test_cases.{owner}.test_{index:02d}' for owner in ('Alpha','Beta') for index in range(12)]
        for index,receipt in enumerate(receipts):
            self.assertEqual(receipt['universe_ids'],expected)
            self.assertEqual(receipt['expected_ids'],[name for name in expected if module().assigned_partition(name)==index])
            self.assertEqual(receipt['executed_ids'],receipt['expected_ids'])
            self.assertEqual([row['id'] for row in receipt['case_results']],receipt['expected_ids'])
        log=(self.root/'artifacts/order.log').read_text().splitlines()
        expected_log=[]
        for receipt in receipts:
            if not receipt['expected_ids']:continue
            expected_log.append('module:setup')
            for owner in ('Alpha','Beta'):
                cases=[name for name in receipt['expected_ids'] if '.'+owner+'.' in name]
                if cases:expected_log.extend([owner+':setup',*cases,owner+':teardown'])
            expected_log.append('module:teardown')
        self.assertEqual(log,expected_log)

    def test_assignment_uses_stable_complete_case_identifier_hash(self):
        expected={'test_cases.Alpha.test_00':3,'test_cases.Alpha.test_01':0,
                  'test_cases.Beta.test_00':3,'test_cases.Beta.test_11':5}
        for name,index in expected.items():self.assertEqual(module().assigned_partition(name),index)

    def test_failed_or_skipped_case_cannot_qualify(self):
        for statement in ('self.fail("actual failure")','self.skipTest("actual skip")'):
            self.source.write_text('import unittest\nclass Broken(unittest.TestCase):\n def test_broken(self):'+statement+'\n')
            self.commit()
            index=module().assigned_partition('test_cases.Broken.test_broken')
            result,receipt=self.run_partition(index)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(receipt['status'],'failed')
            self.assertEqual(receipt['source_head'],self.head)
            self.assertEqual(receipt['executed_ids'],['test_cases.Broken.test_broken'])
            if 'skipTest' in statement:
                self.assertEqual(len(receipt['skips']),1);self.assertEqual(receipt['failures'],[])
            else:
                self.assertEqual(len(receipt['failures']),1);self.assertEqual(receipt['skips'],[])
            with self.assertRaises(ValueError):module().verify_coverage([receipt],self.head)

    def test_actual_error_stops_before_remaining_assigned_case(self):
        self.source.write_text('import unittest\nclass Broken(unittest.TestCase):\n def test_a(self):raise RuntimeError("actual error")\n def test_b(self):pass\n')
        self.commit()
        result,receipt=self.run_partition(0,1)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(receipt['expected_ids'],['test_cases.Broken.test_a','test_cases.Broken.test_b'])
        self.assertEqual(receipt['executed_ids'],['test_cases.Broken.test_a'])
        self.assertEqual(receipt['case_results'],[{'id':'test_cases.Broken.test_a','status':'error'}])
        self.assertEqual(len(receipt['errors']),1)

    def test_discovery_errors_and_duplicate_ids_execute_nothing(self):
        for source in ('raise RuntimeError("discovery failure")\n',
                       'import unittest\nclass Duplicate(unittest.TestCase):\n def test_case(self):pass\ndef load_tests(loader,tests,pattern):\n return unittest.TestSuite([Duplicate("test_case"),Duplicate("test_case")])\n'):
            self.source.write_text(source);self.commit()
            result,receipt=self.run_partition(0)
            self.assertNotEqual(result.returncode,0)
            self.assertTrue(receipt['discovery_errors'])
            self.assertEqual(receipt['executed_ids'],[])

    def test_missing_duplicate_foreign_or_altered_receipts_are_rejected(self):
        receipts=self.successful();validator=module().verify_coverage
        invalid=[receipts[:-1],receipts+[copy.deepcopy(receipts[0])]]
        for change in ('source','universe','missing-case','duplicate-case','wrong-owner','failure','skip','missing-result'):
            altered=copy.deepcopy(receipts);selected=next(row for row in altered if row['expected_ids'])
            if change=='source':selected['source_head']='b'*40
            elif change=='universe':selected['universe_ids'].pop()
            elif change=='missing-case':selected['executed_ids'].pop()
            elif change=='duplicate-case':selected['executed_ids'].append(selected['executed_ids'][0])
            elif change=='wrong-owner':selected['partition_index']=(selected['partition_index']+1)%6
            elif change=='failure':selected['failures']=[{'id':selected['expected_ids'][0],'detail':'failed'}]
            elif change=='skip':selected['skips']=[{'id':selected['expected_ids'][0],'reason':'skipped'}]
            else:selected['case_results'].pop()
            invalid.append(altered)
        for altered in invalid:
            with self.subTest(kind=len(altered)),self.assertRaises(ValueError):validator(altered,self.head)

    def test_invalid_partition_numbers_and_foreign_source_are_rejected(self):
        for index,count in ((-1,6),(6,6),(0,0),(True,6),(0,True),(0,1000)):
            with self.subTest(index=index,count=count),self.assertRaises(ValueError):
                module().run_partition(self.root,partition_index=index,partition_count=count)
        with self.assertRaises(ValueError):module().verify_coverage([], 'not-a-commit')

    def test_cli_rejects_outside_and_symlink_parent_outputs_without_writing(self):
        artifacts=self.root/'artifacts';artifacts.mkdir()
        outside=self.root/'outside';outside.mkdir()
        (artifacts/'linked').symlink_to(outside,target_is_directory=True)
        for output in (outside/'unit-results.json',artifacts/'linked/unit-results.json'):
            with self.subTest(output=output):
                result=subprocess.run([sys.executable,'-B',str(RUNNER),'run','--root',str(self.root),
                    '--partition-index','0','--output',str(output)],cwd=self.root,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0,result.stderr)
                self.assertFalse(output.exists())

    def test_cli_preserves_existing_output_bytes(self):
        output=self.root/'artifacts/unit-results.json';output.parent.mkdir()
        original=b'original owned evidence\n';output.write_bytes(original)
        result=subprocess.run([sys.executable,'-B',str(RUNNER),'run','--root',str(self.root),
            '--partition-index','0','--output',str(output)],cwd=self.root,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(output.read_bytes(),original)
