"""Compatibility entry point; implementation is in age_runtime.examples.library_service."""
import sys
from age_runtime.examples import library_service as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
