"""Compatibility entry point; implementation is in age_runtime.interfaces.visualization."""
import sys
from age_runtime.interfaces import visualization as _implementation

sys.modules[__name__] = _implementation
