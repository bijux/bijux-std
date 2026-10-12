"""Load the physical source owners used at the accepted-proof boundary."""
import hashlib
from pathlib import Path
import sys
from types import ModuleType

EXECUTION = Path(__file__).resolve().parent.parent


def load(relative):
    path = EXECUTION / relative
    data = path.read_bytes()
    key = 'bijux_accepted_proof_' + hashlib.sha256(str(path).encode() + data).hexdigest()
    if key not in sys.modules:
        module = ModuleType(key)
        module.__file__ = str(path)
        sys.modules[key] = module
        try:
            exec(compile(data, str(path), 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(key, None)
            raise
    return sys.modules[key]
