"""Policy module - Capability evaluation and enforcement."""

from .policy_engine import evaluate_capability, PolicyViolation

# Re-export nudge policy function from legacy module
# Note: There's a naming conflict - policy.py file and policy/ directory both exist
# We import by manipulating sys.path temporarily to get the .py file
import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)

# Temporarily remove policy/ from sys.modules if present
_policy_pkg = sys.modules.pop('ReDNACoreDemo.core.policy', None)

try:
    # Import the policy.py file directly
    import importlib.util
    _policy_py_path = os.path.join(_parent_dir, 'policy.py')
    _spec = importlib.util.spec_from_file_location("_nudge_policy", _policy_py_path)
    _nudge_module = importlib.util.module_from_spec(_spec)
    sys.modules['_nudge_policy'] = _nudge_module
    _spec.loader.exec_module(_nudge_module)
    evaluate_nudge_policy = _nudge_module.evaluate_nudge_policy
finally:
    # Restore policy package in sys.modules
    if _policy_pkg:
        sys.modules['ReDNACoreDemo.core.policy'] = _policy_pkg

__all__ = ["evaluate_capability", "PolicyViolation", "evaluate_nudge_policy"]
