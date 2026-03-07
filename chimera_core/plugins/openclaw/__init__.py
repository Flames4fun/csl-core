"""
CSL-Core OpenClaw Plugin — Deterministic Gatekeeper

Formally verified policy enforcement for OpenClaw AI agents.
Hooks into before_tool_call to evaluate every tool execution
against a Z3-verified CSL policy in microseconds.

Quick start:
    from chimera_core.plugins.openclaw import OpenClawGuard

    guard = OpenClawGuard("openclaw_guard.csl")
    result = guard.evaluate("bash", {"command": "rm -rf /"}, {"sender_role": "UNKNOWN"})
    # result.allowed = False
    # result.violations = ["untrusted_no_bash"]
"""

from .guard import OpenClawGuard, EvalResult
from .config import OpenClawConfig
from .context_mapper import map_context
from . import pii_detector

__all__ = [
    "OpenClawGuard",
    "EvalResult",
    "OpenClawConfig",
    "map_context",
    "pii_detector",
]
