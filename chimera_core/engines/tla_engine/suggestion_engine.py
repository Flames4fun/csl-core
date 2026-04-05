"""
TLA+ Smart Suggestion Engine

When TLA+ model checking finds a violation, this engine:
  1. Identifies the root cause from the counterexample trace
  2. Analyzes the constraint structure (MUST NOT BE / MUST BE / comparisons)
  3. Inspects the domain to understand what values are reachable
  4. Generates ranked, actionable fix suggestions with CSL snippets

Fix Types
---------
  DOMAIN_RESTRICTION     Remove the violating value from the domain
  CONDITION_STRENGTHENING  Add extra guards to the WHEN clause
  GUARD_ADDITION         Introduce an explicit approval / gate variable
  BOUND_TIGHTENING       Restrict a numeric domain to match the constraint
  POLICY_INVERSION       Flip from "forbid bad" to "allow good only"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from chimera_core.language.ast import (
    Constraint, Constitution, Expression, Literal,
    TemporalOperator, ModalOperator,
)
from chimera_core.engines.tla_engine.verifier import _eval, _parse_domain


# ═════════════════════════════════════════════════════════════════════════════
# DATA TYPES
# ═════════════════════════════════════════════════════════════════════════════

CONFIDENCE_HIGH   = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW    = "LOW"


@dataclass
class ViolationSuggestion:
    title:          str
    explanation:    str
    fix_type:       str
    confidence:     str
    before_snippet: Optional[str] = None   # Original CSL fragment
    after_snippet:  Optional[str]  = None  # Fixed CSL fragment
    root_cause:     Optional[str]  = None  # One-line root cause


@dataclass
class ViolationAnalysis:
    """Full analysis result for one violated constraint."""
    constraint_name:  str
    root_cause:       str
    violation_state:  Dict[str, Any]          # The exact state that violated
    violation_vars:   List[str]               # Variables that caused it
    suggestions:      List[ViolationSuggestion]


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

_SET_RE = re.compile(r'^\{(.+)\}$', re.DOTALL)


def _literal_value(expr: Expression) -> Optional[Any]:
    """Extract a literal value from an expression node, or None."""
    if isinstance(expr, Literal):
        return expr.value
    return None


def _set_values(domain_str: str) -> Optional[List[str]]:
    """If domain is a string set, return its elements; else None."""
    if not isinstance(domain_str, str):
        return None
    m = _SET_RE.match(domain_str.strip())
    if not m:
        return None
    vals = []
    for tok in re.split(r',\s*', m.group(1)):
        tok = tok.strip().strip('"').strip("'")
        if tok:
            vals.append(tok)
    return vals or None


def _domain_for_var(constitution: Constitution, var_name: str) -> Optional[str]:
    """Return the domain string for a variable, or None."""
    if not constitution.domain:
        return None
    for decl in constitution.domain.variable_declarations:
        if decl.name == var_name:
            return decl.domain if isinstance(decl.domain, str) else str(decl.domain)
    return None


def _range_bounds(domain_str: str) -> Optional[Tuple[Any, Any]]:
    """Return (min, max) for a numeric range domain, or None."""
    m = re.match(r'^(-?[\d.]+)\.\.(-?[\d.]+)$', domain_str.strip())
    if not m:
        return None
    lo_s, hi_s = m.group(1), m.group(2)
    is_float = '.' in lo_s or '.' in hi_s
    return (float(lo_s), float(hi_s)) if is_float else (int(lo_s), int(hi_s))


def _find_violation_state(
    counterexample: List[Dict],
    constraint: Constraint,
) -> Tuple[Dict, int]:
    """
    Walk the counterexample trace and return (state, index)
    of the first state that actually violates the constraint.
    Falls back to the last state if detection fails.
    """
    from chimera_core.engines.tla_engine.verifier import _check_action

    temporal = constraint.condition.temporal_operator

    for i, state in enumerate(counterexample):
        try:
            if temporal == TemporalOperator.ALWAYS:
                cond = True
            else:
                cond = bool(_eval(constraint.condition.condition, state))
        except Exception:
            continue

        if cond and not _check_action(constraint, state):
            return state, i

    last = counterexample[-1] if counterexample else {}
    return last, len(counterexample) - 1


def _describe_condition(constraint: Constraint) -> str:
    """Produce a short human-readable WHEN description."""
    op = constraint.condition.temporal_operator
    if op == TemporalOperator.ALWAYS:
        return "always (unconditional)"
    # Try to stringify the AST expression
    try:
        return _expr_to_str(constraint.condition.condition)
    except Exception:
        return str(constraint.condition.condition)


def _expr_to_str(expr: Expression) -> str:
    """Best-effort expression → string."""
    from chimera_core.language.ast import (
        Variable, BinaryOp, UnaryOp, FunctionCall, MemberAccess,
        ComparisonOperator, LogicalOperator,
    )
    if isinstance(expr, Literal):
        return f'"{expr.value}"' if isinstance(expr.value, str) else str(expr.value)
    if isinstance(expr, Variable):
        return expr.name
    if isinstance(expr, BinaryOp):
        l = _expr_to_str(expr.left)
        r = _expr_to_str(expr.right)
        op_map = {
            ComparisonOperator.EQ:  "==",
            ComparisonOperator.NEQ: "!=",
            ComparisonOperator.LT:  "<",
            ComparisonOperator.GT:  ">",
            ComparisonOperator.LTE: "<=",
            ComparisonOperator.GTE: ">=",
            LogicalOperator.AND:    "AND",
            LogicalOperator.OR:     "OR",
        }
        op = op_map.get(expr.operator, str(expr.operator.value))
        return f"{l} {op} {r}"
    if isinstance(expr, UnaryOp) and expr.operator == LogicalOperator.NOT:
        return f"NOT {_expr_to_str(expr.operand)}"
    if isinstance(expr, MemberAccess):
        return f"{_expr_to_str(expr.object)}.{expr.member}"
    return "..."


# ═════════════════════════════════════════════════════════════════════════════
# SUGGESTION GENERATORS
# ═════════════════════════════════════════════════════════════════════════════

def _suggest_domain_restriction(
    constraint: Constraint,
    violation_state: Dict,
    constitution: Constitution,
    target_value: Any,
) -> Optional[ViolationSuggestion]:
    """
    For MUST NOT BE "X": suggest removing "X" from the domain.
    """
    var_name = constraint.action.variable
    domain_str = _domain_for_var(constitution, var_name)
    if domain_str is None:
        return None

    vals = _set_values(domain_str)
    if vals is None or str(target_value) not in vals:
        return None

    remaining = [v for v in vals if v != str(target_value)]
    before = f"{var_name}: " + "{" + ", ".join(f'"{v}"' for v in vals) + "}"
    after_lines = [
        f"{var_name}: " + "{" + ", ".join(f'"{v}"' for v in remaining) + "}",
        f"  // NOTE: move \"{target_value}\" to a separate privileged variable",
        f"  privileged_{var_name}: " + '{"' + str(target_value) + '"}' + "  // admin-only",
    ]

    return ViolationSuggestion(
        title=f'Remove "{target_value}" from {var_name} domain',
        explanation=(
            f'The value "{target_value}" is declared in the {var_name} domain, '
            f"making it reachable from any state. Since your constraint forbids it "
            f"under certain conditions, the safest fix is to move it to a separate "
            f"privileged variable that only higher-trust policies can reference."
        ),
        fix_type="DOMAIN_RESTRICTION",
        confidence=CONFIDENCE_HIGH,
        before_snippet=before,
        after_snippet="\n".join(after_lines),
        root_cause=(
            f'"{target_value}" is declared in the {var_name} domain '
            f"and is therefore reachable by BFS regardless of role/condition."
        ),
    )


def _suggest_condition_strengthening(
    constraint: Constraint,
    violation_state: Dict,
    constitution: Constitution,
) -> Optional[ViolationSuggestion]:
    """
    Suggest adding an extra guard to the WHEN clause.
    Analyses which variables in the violation state could serve as a gate.
    """
    var_name = constraint.action.variable

    # Find a variable that is NOT the action variable and NOT in the condition
    # that could act as an approval gate
    if not constitution.domain:
        return None

    candidate_gates = []
    for decl in constitution.domain.variable_declarations:
        if decl.name == var_name:
            continue
        domain = decl.domain if isinstance(decl.domain, str) else str(decl.domain)
        if domain.upper() == "BOOLEAN":
            candidate_gates.append(decl.name)

    temporal = constraint.condition.temporal_operator

    if temporal == TemporalOperator.ALWAYS:
        # Suggest wrapping with a WHEN + adding condition
        cond_str    = "approved == False"
        gate_var    = candidate_gates[0] if candidate_gates else "approved"
        before_when = "ALWAYS True"
        after_when  = f"WHEN {gate_var} == False"
    else:
        cond_str    = _describe_condition(constraint)
        gate_var    = candidate_gates[0] if candidate_gates else "approved"
        before_when = f"WHEN {cond_str}"
        after_when  = f"WHEN {cond_str} AND {gate_var} == False"

    modal_str = constraint.action.modal_operator.value
    try:
        val_str = _expr_to_str(constraint.action.value)
    except Exception:
        val_str = "..."

    before_snippet = (
        f"STATE_CONSTRAINT {constraint.name} {{\n"
        f"  {before_when}\n"
        f"  THEN {var_name} {modal_str} {val_str}\n"
        f"}}"
    )
    after_snippet = (
        f"STATE_CONSTRAINT {constraint.name} {{\n"
        f"  {after_when}\n"
        f"  THEN {var_name} {modal_str} {val_str}\n"
        f"}}\n"
        f"\n"
        f"// Add to VARIABLES:\n"
        f"//   {gate_var}: BOOLEAN"
    )

    return ViolationSuggestion(
        title=f"Narrow the WHEN clause with an explicit gate",
        explanation=(
            f"The current constraint fires too broadly — it applies to every state "
            f"that satisfies the condition, but the full state space contains states "
            f"where the action variable holds the forbidden/required value. "
            f"Adding a '{gate_var}' boolean gate ensures the constraint only fires "
            f"when an explicit flag is set, giving you a control plane for edge cases."
        ),
        fix_type="CONDITION_STRENGTHENING",
        confidence=CONFIDENCE_MEDIUM,
        before_snippet=before_snippet,
        after_snippet=after_snippet,
        root_cause=(
            f"Condition '{_describe_condition(constraint)}' can be satisfied "
            f"simultaneously with a violating value for {var_name}."
        ),
    )


def _suggest_bound_tightening(
    constraint: Constraint,
    violation_state: Dict,
    constitution: Constitution,
    bound_value: Any,
) -> Optional[ViolationSuggestion]:
    """
    For numeric comparison violations: suggest tightening the domain.
    """
    var_name = constraint.action.variable
    domain_str = _domain_for_var(constitution, var_name)
    if domain_str is None:
        return None

    bounds = _range_bounds(domain_str)
    if bounds is None:
        return None

    lo, hi = bounds
    modal = constraint.action.modal_operator

    if modal in (ModalOperator.LTE, ModalOperator.LT):
        # Suggest restricting hi to bound_value
        new_hi = bound_value if modal == ModalOperator.LTE else bound_value - 1
        if hi <= new_hi:
            return None
        before_snippet = f"{var_name}: {lo}..{hi}"
        after_snippet  = (
            f"{var_name}: {lo}..{new_hi}\n"
            f"  // Values above {new_hi} require separate approval policy"
        )
    elif modal in (ModalOperator.GTE, ModalOperator.GT):
        new_lo = bound_value if modal == ModalOperator.GTE else bound_value + 1
        if lo >= new_lo:
            return None
        before_snippet = f"{var_name}: {lo}..{hi}"
        after_snippet  = (
            f"{var_name}: {new_lo}..{hi}\n"
            f"  // Values below {new_lo} handled by a separate constraint"
        )
    else:
        return None

    return ViolationSuggestion(
        title=f"Restrict {var_name} domain to match the constraint bound",
        explanation=(
            f"The domain {domain_str} includes values that violate "
            f"'{var_name} {modal.value} {bound_value}'. "
            f"Restricting the domain to {after_snippet.splitlines()[0]} "
            f"ensures all reachable states satisfy the bound by construction."
        ),
        fix_type="BOUND_TIGHTENING",
        confidence=CONFIDENCE_HIGH,
        before_snippet=before_snippet,
        after_snippet=after_snippet,
        root_cause=(
            f"Domain {domain_str} allows {var_name} to exceed the bound "
            f"{modal.value} {bound_value} in the state space."
        ),
    )


def _suggest_policy_inversion(
    constraint: Constraint,
    constitution: Constitution,
    target_value: Any,
) -> Optional[ViolationSuggestion]:
    """
    Instead of 'forbid X', suggest 'only allow non-X values' via MUST BE.
    """
    var_name = constraint.action.variable
    domain_str = _domain_for_var(constitution, var_name)
    if domain_str is None:
        return None

    vals = _set_values(domain_str)
    if vals is None:
        return None

    allowed = [v for v in vals if v != str(target_value)]
    if not allowed:
        return None

    temporal  = constraint.condition.temporal_operator
    cond_str  = "ALWAYS True" if temporal == TemporalOperator.ALWAYS else f"WHEN {_describe_condition(constraint)}"

    if len(allowed) == 1:
        after_constraint = (
            f"STATE_CONSTRAINT {constraint.name}_inverted {{\n"
            f"  {cond_str}\n"
            f"  THEN {var_name} MUST BE \"{allowed[0]}\"\n"
            f"}}"
        )
    else:
        # Use MUST NOT BE as a series or restructure domain
        after_constraint = (
            f"// Option A — restrict domain to allowed values only:\n"
            f"{var_name}: " + "{" + ", ".join(f'"{v}"' for v in allowed) + "}\n"
            f"\n"
            f"// Option B — keep domain but state explicitly:\n"
            f"STATE_CONSTRAINT {constraint.name}_inverted {{\n"
            f"  {cond_str}\n"
            f"  THEN {var_name} MUST NOT BE \"{target_value}\"\n"
            f"}}"
        )

    return ViolationSuggestion(
        title=f"Invert policy: define what IS allowed instead of what is forbidden",
        explanation=(
            f"Rather than forbidding \"{target_value}\", explicitly declare which "
            f"values {var_name} MAY take under this condition. "
            f"This is more robust because it prevents future values added to the domain "
            f"from silently bypassing the intent of the constraint."
        ),
        fix_type="POLICY_INVERSION",
        confidence=CONFIDENCE_LOW,
        before_snippet=(
            f"STATE_CONSTRAINT {constraint.name} {{\n"
            f"  {cond_str}\n"
            f"  THEN {var_name} MUST NOT BE \"{target_value}\"\n"
            f"}}"
        ),
        after_snippet=after_constraint,
        root_cause=(
            f"Negative constraints (MUST NOT BE) are brittle: "
            f"any new value added to the domain is implicitly permitted."
        ),
    )


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class TLASuggestionEngine:
    """
    Analyses a TLA+ violation and returns a ViolationAnalysis with
    ranked, actionable suggestions.

    Usage:
        engine = TLASuggestionEngine()
        analysis = engine.analyze(constraint, counterexample, constitution)
    """

    def analyze(
        self,
        constraint: Constraint,
        counterexample: List[Dict],
        constitution: Constitution,
    ) -> ViolationAnalysis:
        violation_state, viol_idx = _find_violation_state(counterexample, constraint)
        var_name    = constraint.action.variable
        modal       = constraint.action.modal_operator
        target_val  = _literal_value(constraint.action.value)

        # ── Root cause string ─────────────────────────────────────────
        root_cause = self._build_root_cause(
            constraint, violation_state, var_name, modal, target_val, viol_idx
        )

        # ── Identify which variables are "responsible" ────────────────
        violation_vars = [var_name]
        if constraint.condition.temporal_operator != TemporalOperator.ALWAYS:
            # Add condition variables
            try:
                cond_str = _describe_condition(constraint)
                for decl in (constitution.domain.variable_declarations if constitution.domain else []):
                    if decl.name in cond_str and decl.name != var_name:
                        violation_vars.append(decl.name)
            except Exception:
                pass

        # ── Generate suggestions ──────────────────────────────────────
        suggestions: List[ViolationSuggestion] = []

        if modal == ModalOperator.MUST_NOT_BE and target_val is not None:
            s = _suggest_domain_restriction(constraint, violation_state, constitution, target_val)
            if s:
                suggestions.append(s)
            s = _suggest_condition_strengthening(constraint, violation_state, constitution)
            if s:
                suggestions.append(s)
            s = _suggest_policy_inversion(constraint, constitution, target_val)
            if s:
                suggestions.append(s)

        elif modal == ModalOperator.MUST_BE and target_val is not None:
            # Suggest restricting domain to only the required value
            s = self._suggest_must_be_fix(constraint, constitution, target_val)
            if s:
                suggestions.append(s)
            s = _suggest_condition_strengthening(constraint, violation_state, constitution)
            if s:
                suggestions.append(s)

        elif modal in (ModalOperator.LTE, ModalOperator.LT,
                       ModalOperator.GTE, ModalOperator.GT) and target_val is not None:
            s = _suggest_bound_tightening(constraint, violation_state, constitution, target_val)
            if s:
                suggestions.append(s)
            s = _suggest_condition_strengthening(constraint, violation_state, constitution)
            if s:
                suggestions.append(s)

        else:
            # Generic fallback
            s = _suggest_condition_strengthening(constraint, violation_state, constitution)
            if s:
                suggestions.append(s)

        # Deduplicate and rank
        suggestions = self._rank(suggestions)

        return ViolationAnalysis(
            constraint_name=constraint.name,
            root_cause=root_cause,
            violation_state=violation_state,
            violation_vars=list(dict.fromkeys(violation_vars)),
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------

    def _build_root_cause(
        self,
        constraint: Constraint,
        violation_state: Dict,
        var_name: str,
        modal: ModalOperator,
        target_val: Any,
        viol_idx: int,
    ) -> str:
        actual_val = violation_state.get(var_name, "?")

        if modal == ModalOperator.MUST_NOT_BE:
            return (
                f'Variable {var_name} reached the forbidden value "{actual_val}" '
                f"(at state {viol_idx}) while the WHEN condition was satisfied. "
                f"Both the condition and the forbidden value are simultaneously "
                f"reachable in the declared state space."
            )
        elif modal == ModalOperator.MUST_BE:
            return (
                f"Variable {var_name} = \"{actual_val}\" but the constraint requires "
                f"\"{target_val}\". The BFS reached a state where these are "
                f"simultaneously true and violated."
            )
        elif modal in (ModalOperator.LTE, ModalOperator.LT):
            return (
                f"Variable {var_name} = {actual_val} which exceeds the allowed "
                f"bound ({modal.value} {target_val}). "
                f"The declared numeric domain includes values above this threshold."
            )
        elif modal in (ModalOperator.GTE, ModalOperator.GT):
            return (
                f"Variable {var_name} = {actual_val} which is below the required "
                f"minimum ({modal.value} {target_val})."
            )
        else:
            return (
                f"Constraint '{constraint.name}' was violated at state {viol_idx}: "
                f"{var_name} = {actual_val!r}."
            )

    @staticmethod
    def _suggest_must_be_fix(
        constraint: Constraint,
        constitution: Constitution,
        target_val: Any,
    ) -> Optional[ViolationSuggestion]:
        var_name = constraint.action.variable
        domain_str = _domain_for_var(constitution, var_name)
        if domain_str is None:
            return None

        temporal = constraint.condition.temporal_operator
        cond_str = "ALWAYS True" if temporal == TemporalOperator.ALWAYS else _describe_condition(constraint)

        before = f"{var_name}: {domain_str}"
        after  = (
            f"{var_name}: "
            + '{"' + str(target_val) + '"}'
            + f"  // Only the required value; others moved to a separate variable"
        )

        return ViolationSuggestion(
            title=f'Restrict {var_name} domain to only "{target_val}"',
            explanation=(
                f"The constraint requires {var_name} to ALWAYS equal \"{target_val}\". "
                f"If that's truly always required, the domain should only contain that value. "
                f"If the requirement is conditional, replace ALWAYS with a WHEN clause."
            ),
            fix_type="DOMAIN_RESTRICTION",
            confidence=CONFIDENCE_HIGH,
            before_snippet=before,
            after_snippet=after,
            root_cause=(
                f"Domain {domain_str} allows {var_name} to start with a "
                f"value that isn't \"{target_val}\"."
            ),
        )

    @staticmethod
    def _rank(suggestions: List[ViolationSuggestion]) -> List[ViolationSuggestion]:
        order = {CONFIDENCE_HIGH: 0, CONFIDENCE_MEDIUM: 1, CONFIDENCE_LOW: 2}
        return sorted(suggestions, key=lambda s: order.get(s.confidence, 9))
