"""Compatibility entry point; implementation is in age_runtime.core.play."""
import sys
from age_runtime.core import play as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
