"""Compatibility entry point; implementation is in age_runtime.examples.demo."""
import sys
from age_runtime.examples import demo as _implementation

if __name__ == "__main__":
    import runpy
    runpy.run_module("age_runtime.examples.demo", run_name="__main__")
else:
    sys.modules[__name__] = _implementation
