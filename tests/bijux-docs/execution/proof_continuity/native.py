"""Requalify unchanged original fixture, case, JUnit and native control bodies."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import subprocess


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate accepted receipt JSON key')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=unique)
    require(isinstance(value, dict), 'Accepted receipt must be an object')
    return value


def materialize(inputs, output):
    """Copy API-admitted bytes only; matching copies keep their original bodies."""
    require(not output.exists() and not any(path.is_symlink() for path in output.parents),
            'Accepted-proof evidence requires a fresh owned directory')
    pending = {}
    for role, item in inputs.items():
        require(type(item).__name__ == 'ArtifactInput'
                and Path(inspect.getfile(type(item).__init__)).resolve() == Path(__file__).parent.parent / 'workflow_lineage.py',
                'Original evidence requires live API-admitted artifact bytes')
        prefix = ''
        if role.startswith('fault-'):
            owner = role.removeprefix('fault-')
            prefix = 'frontend-faults/' if owner != 'public' else 'frontend-faults/public/'
        elif role.startswith('catalogue-'):
            prefix = 'catalogue-inputs/' + role.removeprefix('catalogue-') + '/'
        for name in item.files:
            relative = PurePosixPath(name)
            require(name and not relative.is_absolute() and str(relative) == name
                    and not any(part in ('.', '..') for part in relative.parts)
                    and '\\' not in name and ':' not in name, 'Original member path is unsafe')
            if role.startswith('fault-') and role != 'fault-public':
                require(PurePosixPath(name).parts[0] == role.removeprefix('fault-'),
                        'Original fault archive crosses its engine namespace')
            path = prefix + name
            body = item.read(name)
            require(digest(body) == item.files[name], 'Original API-admitted body changed')
            require(path not in pending or pending[path] == body, 'Original producer copies disagree')
            pending[path] = body
    require(not any(str(parent) in pending for path in pending for parent in PurePosixPath(path).parents),
            'Original evidence has a file/directory collision')
    output.mkdir(parents=True)
    for name, body in sorted(pending.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(body)


def workflow(job):
    require(job.get('status') == 'completed' and job.get('conclusion') == 'success',
            'Original native owner must have actually succeeded')
    return {'workflow_run_id': str(job['run_id']), 'workflow_attempt': str(job['run_attempt'])}


def execution(folder, role, job, original_head, producer):
    record = decode((folder / 'execution.json').read_bytes())
    require(record.get('schema') == 1 and record.get('executor') == {
        'role': role, 'source_head': original_head, **workflow(job)}
        and record.get('producer') == producer, 'Original execution declaration differs from its API owner')
    files = {str(path.relative_to(folder)): digest(path.read_bytes()) for path in sorted(folder.rglob('*'))
             if path.is_file() and path != folder / 'execution.json'}
    # Browser uploads may contain extra failure diagnostics. The executor binds
    # their complete native output before the aggregate's smaller retained subset.
    require(isinstance(record.get('files_sha256'), dict)
            and all(record['files_sha256'].get(name) == value for name, value in files.items()),
            'Original execution body differs from its declared native output')
    return record


def qualify(root, output, context, inputs, jobs, load):
    original = context.identity
    gate = load('browser_gate.py')
    parts = gate.PARTITIONS
    complete = decode(inputs['complete'].read('navigation-qualification.json'))
    require(complete.get('status') == 'passed' and complete.get('qualification_kind') == 'complete_engine_matrix'
            and complete.get('source_identity') == original, 'Original complete native matrix is required')
    producer = inputs['producer']
    envelope_data = producer.read('producer-envelope.json')
    envelope = producer.verify_receipt('producer-envelope.json', envelope_data)
    declaration = load('workflow_collection.py').producer_declaration(producer)
    require(envelope.get('partition_registry_sha256') == digest(parts.REGISTRY_PATH.read_bytes())
            and envelope.get('batch_registry_sha256') == digest(gate.OWNERSHIP.REGISTRY_PATH.read_bytes())
            and complete.get('producer_envelope') == envelope, 'Original producer registry or aggregate binding changed')
    for name, expected in envelope['artifact_digests'].items():
        require(digest((output / name).read_bytes()) == expected, 'Original producer member changed')
    observation = decode((output / 'renderer-source-observation.json').read_bytes())
    require(observation['source']['sha'] == original['head'] and observation['verification_only'] is True
            and observation['admission_created'] is False, 'Original fixture source observation differs')
    fixture_digest = envelope['artifact_digests']['browser-fixtures.tar.gz']
    require((output / 'browser-fixtures.sha256').read_text().strip() == fixture_digest, 'Original fixture sidecar differs')
    gate.fixture_transport().unpack(output / 'browser-fixtures.tar.gz', output, ['generated', 'contrast-generated'], fixture_digest)
    runtime = gate.runtime_transport()
    runtime.unpack(output / 'browser-packages.tar.gz', decode((output / 'browser-packages.json').read_bytes()),
                   root / 'tests/bijux-docs', output / 'node-runtime')
    inventories = {suite: decode((output / 'inventories' / (suite + '.json')).read_bytes())
                   for suite in (*parts.SUITES, gate.PERSISTED_SUITE)}
    # Reopen current canonical project counts and original rendered fixture bytes
    # using the exact freshly reconstructed, locked Node packages.
    program = """const path = require('node:path');
const identity = require(process.argv[1] + '/tests/bijux-docs/reporting/identity.js');
const inputs = JSON.parse(process.argv[2]), root = process.argv[1], out = process.argv[3], result = {};
for (const suite of inputs) {
 process.env.BIJUX_GENERATED_ROOT = path.join(out, suite === 'contrast' ? 'contrast-generated' : 'generated');
 delete require.cache[require.resolve(path.join(root, 'tests/bijux-docs/playwright.config.js'))];
 const config = require(path.join(root, 'tests/bijux-docs/playwright.' + suite + '.config.js'));
 const contract = config.reporter.find(entry => Array.isArray(entry) && String(entry[0]).endsWith('strict-reporter.js'))[1];
 result[suite] = {scope: contract.scope || 'generated_frontend', projects: contract.canonicalProjects, fixture: identity.fixtureIdentity(contract)};
} process.stdout.write(JSON.stringify(result));"""
    env = {key: value for key, value in os.environ.items() if key not in
           ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE', 'NODE_OPTIONS')}
    env['NODE_PATH'] = str(output / 'node-runtime/node_modules')
    contracts = decode(subprocess.check_output(['node', '-e', program, str(root), json.dumps(list(inventories)), str(output)],
                                               cwd=root, env=env, timeout=30))
    for suite, inventory in inventories.items():
        expected = contracts[suite]
        require(inventory['source_identity'] == original and inventory['canonical_projects'] == expected['projects']
                and inventory['qualification_scope'] == expected['scope'] and inventory['fixture_identity'] == expected['fixture'],
                'Original source-owned case contract or physical fixture differs')
    assignments = parts.plan({suite: inventories[suite] for suite in parts.SUITES})
    reports, partition_reports = [], []
    expected_paths = set()
    roles = load('workflow_collection.py').registry()
    for group, suites in parts.GROUPS.items():
        for engine in parts.ENGINES:
            owners = [row for row in roles.values() if group in row.get('groups', ()) and row.get('engine') == engine]
            require(len(owners) == 1, 'Original group has no unique physical batch owner')
            folder = output / 'shards' / (group + '-' + engine)
            execution(folder, 'browser-' + group + '-' + engine, jobs[owners[0]['job_name']], original['head'], declaration)
            for suite in suites:
                path = folder / suite / 'qualification.json'
                expected_paths.add(path)
                report = decode(path.read_bytes())
                junit = PurePosixPath(report['junit']['path'])
                require(not junit.is_absolute() and '..' not in junit.parts and str(junit) == report['junit']['path'],
                        'Original JUnit crosses its group owner')
                report['junit']['path'] = str(path.parent / junit)
                reports.append(report)
                partition_reports.append((group + '-' + engine, suite, report))
    require(set((output / 'shards').rglob('qualification.json')) == expected_paths,
            'Original browser matrix has missing or unexpected group receipts')
    parts.verify_reports(assignments, partition_reports)
    partition_identity = {f'{group}/{suite}': names for (group, suite), names in assignments.items()}
    paths = [output / 'inventories' / (suite + '.json') for suite in parts.SUITES] + sorted(expected_paths)
    retained_inputs = [{'path': str(path.relative_to(output)), 'sha256': digest(path.read_bytes())} for path in paths]
    require(complete.get('browser_partitions') == partition_identity and complete.get('inputs') == retained_inputs,
            'Original aggregate partition or physical input index differs')
    aggregate = load('../reporting/aggregate.py').aggregate([inventories[suite] for suite in parts.SUITES], reports)
    require(all(complete.get(key) == value for key, value in aggregate.items()), 'Original aggregate differs from requalified native matrix')
    commands = load('publication_gate.py').verify(output / 'publication-commands', original,
                                                workflow(jobs['std / publication commands']))
    require(complete.get('publication_commands') == commands, 'Original publication command aggregate differs')
    controls = load('renderer_controls.py')
    renderer = controls.verify_groups(output / 'renderer-controls', original,
        workflow(jobs['std / navigation']),
        workflows={group: workflow(jobs['std / renderer controls / ' + group]) for group in controls.GROUPS},
        original_source=context)
    require(complete['renderer_controls']['groups'] == renderer['groups']
            and complete['renderer_controls']['python_executed'] == renderer['python_executed']
            and complete['renderer_controls']['node_executed'] == renderer['node_executed'],
            'Original renderer case or runtime accounting differs')
    persisted = load('persisted_reader.py')
    cached = persisted.verify(output / 'persisted-reader', original_source=original,
                              inventory_path=output / 'inventories' / (persisted.SUITE + '.json'))
    execution(output / 'persisted-reader', 'persisted', jobs[persisted.JOB], original['head'], declaration)
    require(complete.get('persisted_native_reader') == cached, 'Original persisted journey aggregate differs')
    faults = load('frontend_faults.py')
    qualified_faults = faults.qualify(original_source=original, output=output / 'frontend-faults',
        workflows={owner: workflow(jobs[roles['fault-' + owner]['job_name']]) for owner in (*parts.ENGINES, 'public')})
    require(decode((output / 'frontend-faults/qualification.json').read_bytes()) == qualified_faults,
            'Original negative-control aggregate differs')
    for engine in parts.ENGINES:
        execution(output / 'frontend-faults' / engine, 'fault-' + engine,
                  jobs[roles['fault-' + engine]['job_name']], original['head'], declaration)
    catalogue = qualify_catalogue(output, original, inputs, jobs, load)
    public = qualify_public(output / 'frontend-faults/public', original)
    return {'browser_cases': aggregate['executed_cases'], 'engine_versions': aggregate['engine_versions'],
            'browser_scopes': aggregate['scopes'], 'renderer_python_cases': renderer['python_executed'],
            'renderer_node_cases': renderer['node_executed'], 'publication_cases': commands['executed'],
            'persisted_reader_cases': cached['executed_cases'], 'persisted_native_cycles': cached['cached_native_cycles'],
            'fault_controls': qualified_faults, 'public_controls': public, 'catalogue_cases': catalogue}


def qualify_catalogue(output, original, inputs, jobs, load):
    module = load('../catalogue/execution.py')
    total = 0
    for group in module.GROUPS:
        item = inputs['catalogue-' + group]
        suffix = 'catalogue/reports/' + group + '/receipt.json'
        names = [name for name in item.files if name.endswith(suffix)]
        require(len(names) == 1, 'Original catalogue receipt owner is missing or ambiguous')
        name = names[0]
        receipt = decode(item.read(name))
        runtime = receipt['runtime_before']
        require(runtime.get('version') == '3.14.4' and runtime.get('distributions') == module.pins()
                and runtime.get('lock_sha256') == module.helpers.digest(module.LOCK)
                and runtime.get('verification_only') is True and runtime.get('publication_approval') is False
                and isinstance(runtime.get('physical'), dict) and runtime['physical'].get('packages')
                and re_digest(runtime['physical'].get('executable_sha256')),
                'Original catalogue runtime is missing or differs from the owned lock')
        module.verify(receipt, group, original, runtime, workflow(jobs['std / catalogue ' + group]))
        require(item.files.get(name.removesuffix('receipt.json') + 'unittest.log') == receipt['unittest_log_sha256'],
                'Original catalogue native execution log changed')
        for path, expected in receipt['artifacts'].items():
            if isinstance(expected, dict):
                actual = {name[len(path) + 1:]: sha for name, sha in item.files.items() if name.startswith(path + '/')}
            else:
                actual = item.files.get(path)
            require(actual == expected, 'Original catalogue native artifact inventory changed')
        total += len(receipt['executed_ids'])
    return total


def re_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


def qualify_public(folder, original):
    receipt = decode((folder / 'receipt.json').read_bytes())
    require(receipt.get('verification_only') is True and receipt.get('publication_admission') is False
            and len(receipt.get('commands', [])) == 6 and receipt['commands'][0]['exit'] == 0,
            'Original public fault native command accounting is incomplete')
    manifest = decode((folder / 'generated/manifest.json').read_bytes())
    require(manifest.get('source_sha') == original['head'] and all(
        original['files'].get('shared/bijux-docs/' + name) == sha for name, sha in manifest['source_files'].items()),
        'Original public fixture source differs')
    modes = ('clean', 'missing-index', 'missing-worker', 'loopback-canonical', 'loopback-sitemap')
    errors = {'missing-index': 'search index is absent', 'missing-worker': 'configured search worker is absent',
              'loopback-canonical': 'canonical', 'loopback-sitemap': 'sitemap'}
    baseline = {str(path.relative_to(folder / 'generated/inputs/hub/site')): digest(path.read_bytes())
                for path in (folder / 'generated/inputs/hub/site').rglob('*') if path.is_file()}
    for index, mode in enumerate(modes):
        mutation = decode((folder / mode / 'mutation.json').read_bytes())
        actual = {str(path.relative_to(folder / mode / 'site')): digest(path.read_bytes())
                  for path in (folder / mode / 'site').rglob('*') if path.is_file()}
        changed = sorted(name for name in set(baseline) | set(actual) if baseline.get(name) != actual.get(name))
        validation = decode((folder / mode / 'validation.json').read_bytes())
        require(mutation == {'baseline': baseline, 'actual': actual, 'changed_paths': changed}
                and len(changed) == (0 if mode == 'clean' else 1)
                and receipt['commands'][index + 1]['exit'] == (0 if mode == 'clean' else 1)
                and validation['result'] == ('pass' if mode == 'clean' else 'fail')
                and (mode == 'clean' or any(errors[mode] in error.lower() for error in validation['errors'])),
                'Original public fault mutation or actual rejection differs')
    return len(modes)
