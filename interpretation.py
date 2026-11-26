"""Compatibility entry point; implementation is in age_runtime.interfaces.interpretation."""
import sys
from age_runtime.interfaces import interpretation as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
