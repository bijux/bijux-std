# Native GitLab standards execution

`pipeline.py` composes physical job contracts from the existing catalogue,
renderer and browser ownership registries. `execute.py --job '<exact name>'`
executes only a declared physical owner. It uses argument arrays and the
repository's existing Make targets and Python controllers. A failed command
fails its job and retains the actual exit code; no optional-success replacement
or shell command assembled from pipeline variables is supported.

Execution requires GitLab.com's canonical `bijux-oss/bijux-std` project ID
88948041, the actual positive pipeline/job identifiers, exact physical job name,
checkout SHA, checkout directory, event and ref/protection identity. The native
context comes from `tests/bijux-docs/execution/ci_context.py`. GitHub execution
variables are never fabricated. Only after this admission does the ephemeral CI
checkout's `origin` become the public canonical URL. Its previous URL, which may
contain runner credentials, is never read or logged by the harness. Ordinary
local execution without native context fails before changing a remote.

## Runtime and command identity

The standard and contract jobs use the exact Ruby 3.3.12 image declared by the
pipeline. The standard gate independently admits Ruby/Psych before its checksum,
action-reference, shared-standard and generated-pipeline checks. Frontend jobs,
including fixture production, run in the same pinned Playwright image.

Jobs requiring Node download exactly 24.21.0 from its fixed `nodejs.org` release
URL, verify the archive against that release's official HTTPS `SHASUMS256.txt`,
extract into `artifacts/gitlab/tools/node` and verify the executable's version.
Catalogue and contract jobs install exactly uv 0.11.17 into their artifact-owned
virtual environment, using an artifact-owned pip cache. No global pip
installation or unverified installer script is used. A shared bootstrap helper
runs the existing catalogue Make target and independently reopens the standalone
CPython 3.14.4 recipe observation. Catalogue behavior and dependency targets are
unchanged.

Contract tests use a separate environment under
`artifacts/gitlab/contracts/python`, installed through the existing hash-locked
catalogue dependency target. Its `bin` directory leads the contract child's
`PATH`. The child must report exact CPython 3.14.4, the safe tar data filter and
PyYAML imported from that owned environment. The runtime receipt records its
actual path, resolved executable hash and lock hash separately from the system
Python that launches the harness and from the standalone recipe. Safe archive
extraction filters remain enabled. Only the source contract job has its distinct
longer budget; frontend jobs retain the strict 180-second whole-job limit.

The tracked-entrypoint owner also installs the unchanged default renderer lock
through its existing catalogue target.

The pipeline images must provide Python with venv support, Git, Make, curl,
CA certificates, tar, `xz-utils`, Perl, jq and ShellCheck. Runtime tools, caches,
Python bytecode, temporary files and receipts remain under `artifacts/`.
Scratch directories are created before exporting `TMPDIR`. Browser binaries
are the preinstalled `/ms-playwright` image runtime.

Native Python children use unbuffered output so diagnostics emitted before a
timeout remain available in the provider trace.

Every argv execution emits paired source-owned GitLab trace sections and records
its command, real exit code and duration in
`artifacts/gitlab/jobs/$CI_JOB_ID/runtime.json`. Runtime versions, official Node
archive digest/URLs and installed tool executable digests are retained there.
These declarations supplement native job/trace evidence; they do not replace
provider admission or confer publication permission.

The contract-test subprocess receives its artifact paths and runtime tools, but
does not inherit `GITLAB_CI`, `CI_*`, `GITHUB_*` or provider read tokens. Contract
fixtures establish their own explicit provider identities. The containing job's
admission and runtime receipt retain its actual GitLab context. Frontend
qualification, source planning, policy, navigation and reporting retain their
native provider environment.

The complete contract target uses fail-fast unit discovery so hosted failures
retain their traceback promptly. Successful runs execute the complete unit
inventory and theme checks. The source contract job has a 30-minute limit;
frontend jobs retain their separate strict 180-second whole-job limit.

## Fresh qualification and acceptance

All executions select full fresh verification. Retained proof, affected-input
omissions, observation modes, package release and publication operations are
unsupported and fail explicitly. Fixture production invokes native
`browser_gate.py prepare` directly inside the pinned image. It retains the
existing physical runtime, source and archive proof without Docker-in-Docker.

Navigation and report first call the source-owned native evidence collector.
Navigation excludes the still-unfinished navigation/report owners; report
excludes only itself. The collector requires completed successful prerequisite
jobs at the exact project/pipeline/commit, native lifecycle traces and complete
owned artifact bodies before materializing them. Job identity comes from complete
public pipeline-job API snapshots with retried jobs included. Immutable job-ID
lookups use the latest completed snapshot; the final inventory refresh rejects
newer or changed executions. Restricted single-job and API trace endpoints are
not required.

Public project metadata must bind the numeric project ID to its expected namespace
path before the collector reads `/<namespace>/<project>/-/jobs/<job-id>/raw`.
These public raw traces require no token. Plaintext bodies are bounded; HTML,
sign-in pages and unowned job/project identities fail closed. Approved GitLab
storage redirects carry no credentials and signed query URLs are never retained.
Both classic ANSI section markers and timestamped native log records retain their
original byte hashes and offsets. A complete native `step_script` section remains
mandatory for every frontend job. Missing public evidence blocks qualification;
ambient interactive/session tokens are never a fallback.

Only admitted actual jobs derive result flags. The existing fresh fault/browser
aggregates, renderer-control verification and input planner's plain `verify`
operation then recheck materialized evidence. Report also runs the existing
required check registry through `run-bijux-check-suite.sh`, preserving the
consumer declaration and `artifacts/bijux-checks` reports before acceptance. A collector failure prevents those
controller commands from running. The publisher never waits on its own containing
pipeline; this package does not implement a publisher.

Report emits `artifacts/gitlab/acceptance/acceptance.json` only after successful
native prerequisite admission and fresh verification. Schema version 1 records
server URL, integer project/pipeline IDs, project path, source commit, pipeline
event, ref and boolean protection state, actual prerequisite job records and
separate `validation.status: passed` and `publication.status: pending`. The
running report job is never represented as an already successful prerequisite.
No infrastructure apply, release, GitHub mutation or mirror write occurs.

## Canonical review

`policy.py` reads bounded public native GitLab metadata without session or job
tokens. Feature-branch pushes establish branch validation only, with no review
or publication authorization claim. Merge-request jobs must match the actual
native MR head, target the canonical main branch and be non-draft. Owner `bijux`
requires `owner-self-signoff`; another author requires an actual current native
approval by `bijux`. The MR is read again to reject a racing head/state change.

Protected main must bind exactly one actual merged native MR whose merge commit
is the validated checkout. Imported historical GitHub review records, an
unrelated MR, missing approval, direct main push, squash/rebase substitution or
mismatched head cannot establish this admission. Tag/release authorization and
unsupported manual/scheduled review contexts fail explicitly. Every successful
policy receipt still records `publication_authorization: false`.
