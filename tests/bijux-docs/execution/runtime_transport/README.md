# Installed browser package transport

The fixture producer packages its already installed npm tree into the same
source-bound artifact as the rendered fixtures. No browser executable or Node
executable is supplied by this archive. Consumers observe their current Node
binary, npm package tree, platform, source package manifest and lock again.
Every package file, executable mode, directory and declared `.bin` link must
match the producer's immutable transport. Required installed versions come
from the exact source lock; unsupported optional packages may be absent only
when the lock excludes the current operating system.

Canonical preparation renders fixtures on the host, then observes and compresses
the installed packages inside the exact immutable browser container. Docker
receives the actual setup-node executable and installed npm package through
read-only mounts. The child observes its own OS, libc and kernel; runner image
attributes are forwarded unchanged. The source and installed packages are
read-only, and only the owned archive output and operation journal are writable.
No supplied platform declaration replaces physical observation. Consumers still
refuse any platform, toolchain, source, file or topology difference, including
kernel or runner-image drift between jobs.

The archive and receipt are byte inventories, not source or execution
authority. Ordinary jobs first verify the same-run producer envelope. Retained
inputs still require the existing API-created artifact capability. A missing
or inapplicable runtime archive uses a fresh `npm ci`; browser execution and
the native case reports remain mandatory. A pre-existing dependency tree is
preserved and uses the ordinary install route.

The bounded transport candidate changes neither cases nor engine assignments.
Local compression and reconstruction clocks measure only those operations.
Hosted transfer, setup, upload and cleanup costs remain part of the complete
job budget. A strict cost improvement requires the same tested source inputs
and coverage on both sides of the comparison.
