"""Compatibility entry point; implementation is in age_runtime.mythos.game."""
import sys
from age_runtime.mythos import game as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
