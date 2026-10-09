# Canon documentation renderer recipe

`requirements.lock` preserves the exact 36-package documentation closure recorded
in `generated/canon-docs-renderer.json`. Its bytes, package map and Canon source
provenance are one observation input. It is a historical recipe, not the standard
renderer dependency manifest or a supported production installation.

The renderer observation workflow installs this file explicitly. The maintained
standard fixture uses `generated/requirements.lock.txt`; dependency automation
must continue reviewing that current manifest. The recipe uses a `.lock` suffix
and execution ownership so it is not mistaken for mutable fixture requirements.

A security revision for a real Canon renderer requires the corresponding Canon
source/lock change and a newly attributed physical observation. Do not relabel an
old source by editing this recipe's digest or package map. An observation creates
no consumer acceptance or publication profile admission.
