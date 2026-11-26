"""Compatibility entry point; implementation is in age_runtime.interfaces.browser_play."""
import sys
from age_runtime.interfaces import browser_play as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
