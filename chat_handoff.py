"""Compatibility entry point; implementation is in age_runtime.core.chat_handoff."""
import sys
from age_runtime.core import chat_handoff as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
