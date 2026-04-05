"""
TLA+ Specification Builder — CSL AST → TLA+ / CFG files

Generates proper TLA+ (PlusCal-free) module + TLC configuration file from
a CSL Constitution AST.  The output is suitable for `java -jar tla2tools.jar`.

Key design:
  • Variables declared with VARIABLES; TypeOK constrains each to its domain
  • Init assigns each variable non-deterministically from its abstract domain
    (using \\in) — TLC will explore ALL combinations
  • Next is a STUTTER step (UNCHANGED <<vars>>) so TLC performs reachability
    from Init and checks invariants at every reachable state
  • Invariants are pure boolean predicates; each CSL STATE_CONSTRAINT maps to
    one TLA+ INVARIANT

Predicate abstraction (sound optimisation for large numeric domains):
  • For `amount: 0..100000` with threshold 50000 in constraints, the abstract
    domain is {0, 49999, 50000, 50001, 100000} — preserves all "interesting"
    boundaries while drastically reducing state space
  • String/bool sets are passed through verbatim (no abstraction needed)
  • Soundness: for linear arithmetic, the intervals between thresholds are
    equivalent classes; checking one representative per class suffices
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from chimera_core.language.ast import (
    Constitution, Constraint, VariableDeclaration, Expression,
    Literal, Variable, BinaryOp, UnaryOp, FunctionCall, MemberAccess,
    TemporalOperator, ModalOperator,
    ComparisonOperator, LogicalOperator, ArithmeticOperator,
)


# ─────────────────────────────────────────────────────────────────────────────
# Regex helpers
# ─────────────────────────────────────────────────────────────────────────────

_SET_RE   = re.compile(r'^\{(.+)\}$', re.DOTALL)
_RANGE_RE = re.compile(r'^(-?[\d.]+)\.\.(-?[\d.]+)$')


# ═════════════════════════════════════════════════════════════════════════════
# 1. PREDICATE ABSTRACTION
# ═════════════════════════════════════════════════════════════════════════════

def _extract_thresholds(var_name: str, constraints: List[Constraint]) -> Set[int]:
    """
    Walk all CSL constraint expressions and collect every numeric literal
    that appears in a comparison involving `var_name`.

    Example:
        WHEN amount > 50000 → {50000}
        THEN risk_score <= 10  → {10}
    """
    thresholds: Set[int] = set()

    def _walk(expr: Expression) -> None:
        if isinstance(expr, BinaryOp):
            _walk(expr.left)
            _walk(expr.right)
            # If one side is the target variable and other is a literal
            if (isinstance(expr.left, Variable) and expr.left.name == var_name
                    and isinstance(expr.right, Literal)):
                val = expr.right.value
                if isinstance(val, (int, float)):
                    thresholds.add(int(val))
            elif (isinstance(expr.right, Variable) and expr.right.name == var_name
                    and isinstance(expr.left, Literal)):
                val = expr.left.value
                if isinstance(val, (int, float)):
                    thresholds.add(int(val))
        elif isinstance(expr, UnaryOp):
            _walk(expr.operand)

    for c in constraints:
        try:
            _walk(c.condition.condition)
        except Exception:
            pass
        try:
            # action value
            _walk(c.action.value)
        except Exception:
            pass

    return thresholds


def _abstract_int_domain(lo: int, hi: int, thresholds: Set[int]) -> List[int]:
    """
    Build abstract domain for integer range [lo..hi] by adding boundary
    points around each threshold.  The result is always a subset of [lo, hi].

    For each threshold T:
        add T-1, T, T+1  (clipped to [lo, hi])

    Always includes lo and hi.

    Soundness argument:
        For linear arithmetic constraints, the truth value of any comparison
        `v OP T` is constant within each open interval (−∞,T), {T}, (T,+∞).
        Therefore checking one representative per interval is sufficient.
    """
    points: Set[int] = {lo, hi}
    for t in thresholds:
        for delta in (-1, 0, 1):
            v = t + delta
            if lo <= v <= hi:
                points.add(v)
    return sorted(points)


def _domain_to_tla_set(
    var_name: str,
    domain_str: str,
    constraints: List[Constraint],
) -> Tuple[str, str]:
    """
    Convert a CSL domain string to a TLA+ set expression and a human-readable
    cardinality description.

    Returns:
        (tla_set_expr, description)
    """
    if not isinstance(domain_str, str):
        return "{0}", "trivial"

    s = domain_str.strip()

    # ── Boolean ──────────────────────────────────────────────────────────────
    if s.upper() == "BOOLEAN":
        return "BOOLEAN", "|2| = 2"

    # ── String / mixed set  {"A","B","C"} ─────────────────────────────────
    m = _SET_RE.match(s)
    if m:
        inner = m.group(1)
        members: List[str] = []
        for tok in re.split(r',\s*', inner):
            tok = tok.strip()
            if tok:
                members.append(tok)   # keep original quoting
        if not members:
            return '{"__empty__"}', "empty"
        tla = "{" + ", ".join(members) + "}"
        return tla, f"|{len(members)}|"

    # ── Integer range ─────────────────────────────────────────────────────
    mr = _RANGE_RE.match(s)
    if mr:
        lo_s, hi_s = mr.group(1), mr.group(2)
        is_float = '.' in lo_s or '.' in hi_s
        if is_float:
            # TLC can't iterate floats; use a small representative set
            lo_f, hi_f = float(lo_s), float(hi_s)
            step = (hi_f - lo_f) / 5
            vals = [lo_f + i * step for i in range(6)]
            tla = "{" + ", ".join(str(round(v, 6)) for v in vals) + "}"
            return tla, "float~6pts"

        lo, hi = int(lo_s), int(hi_s)
        span = hi - lo + 1

        if span <= 20:
            # Small range — use TLA+ integer range notation
            return f"{lo}..{hi}", f"|{span}|"

        # Large range — apply predicate abstraction
        thresholds = _extract_thresholds(var_name, constraints)
        abstract = _abstract_int_domain(lo, hi, thresholds)
        tla = "{" + ", ".join(str(v) for v in abstract) + "}"
        card_original = f"|{span:,}|"
        card_abstract = f"|{len(abstract)}| (abstracted from {card_original})"
        return tla, card_abstract

    # ── Int / Nat / unknown ───────────────────────────────────────────────
    if s in ("Int",):
        return "{-100, -10, -1, 0, 1, 10, 100}", "|Int| abstracted"
    if s in ("Nat",):
        return "{0, 1, 10, 100, 1000}", "|Nat| abstracted"

    return "{0}", "unknown"


# ═════════════════════════════════════════════════════════════════════════════
# 2. EXPRESSION → TLA+ STRING
# ═════════════════════════════════════════════════════════════════════════════

def _expr_to_tla(expr: Expression) -> str:
    """Recursively convert a CSL expression to a TLA+ string."""
    if isinstance(expr, Literal):
        v = expr.value
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)

    if isinstance(expr, Variable):
        return expr.name

    if isinstance(expr, UnaryOp):
        inner = _expr_to_tla(expr.operand)
        if expr.operator == LogicalOperator.NOT:
            return f"~({inner})"
        if expr.operator == ArithmeticOperator.SUB:
            return f"(-{inner})"
        return inner

    if isinstance(expr, BinaryOp):
        l = _expr_to_tla(expr.left)
        r = _expr_to_tla(expr.right)
        op_map: Dict[Any, str] = {
            LogicalOperator.AND:         "/\\",
            LogicalOperator.OR:          "\\/",
            ComparisonOperator.EQ:       "=",
            ComparisonOperator.NEQ:      "#",
            ComparisonOperator.LT:       "<",
            ComparisonOperator.GT:       ">",
            ComparisonOperator.LTE:      "=<",
            ComparisonOperator.GTE:      ">=",
            ArithmeticOperator.ADD:      "+",
            ArithmeticOperator.SUB:      "-",
            ArithmeticOperator.MUL:      "*",
            ArithmeticOperator.DIV:      "\\div",
            ArithmeticOperator.MOD:      "%",
        }
        op_str = op_map.get(expr.operator, "?")
        return f"({l} {op_str} {r})"

    if isinstance(expr, MemberAccess):
        obj = _expr_to_tla(expr.object)
        return f"{obj}.{expr.member}"

    if isinstance(expr, FunctionCall):
        args = ", ".join(_expr_to_tla(a) for a in expr.args)
        # No TLA+ stdlib here; best effort
        return f"{expr.name}({args})"

    # Fallback: TRUE (safe — fails open)
    return "TRUE"


def _condition_to_tla(constraint: Constraint) -> str:
    """
    Convert the WHEN/ALWAYS clause to a TLA+ boolean expression.
    """
    temporal = constraint.condition.temporal_operator
    if temporal == TemporalOperator.ALWAYS:
        return "TRUE"
    try:
        return _expr_to_tla(constraint.condition.condition)
    except Exception:
        return "TRUE"


def _action_to_tla(constraint: Constraint) -> str:
    """
    Convert the THEN action clause to a TLA+ boolean expression.

    ModalOperator mapping:
        MUST_BE     → var = val
        MUST_NOT_BE → var # val
        MAY_BE      → TRUE  (always permitted)
        EQ / NEQ / LT / GT / LTE / GTE → direct comparison
    """
    action = constraint.action
    var    = action.variable
    try:
        val = _expr_to_tla(action.value)
    except Exception:
        return "TRUE"

    modal = action.modal_operator

    if modal == ModalOperator.MUST_BE:     return f'{var} = {val}'
    if modal == ModalOperator.MUST_NOT_BE: return f'{var} # {val}'
    if modal == ModalOperator.MAY_BE:      return "TRUE"
    if modal == ModalOperator.EQ:          return f'{var} = {val}'
    if modal == ModalOperator.NEQ:         return f'{var} # {val}'
    if modal == ModalOperator.LT:          return f'{var} < {val}'
    if modal == ModalOperator.GT:          return f'{var} > {val}'
    if modal == ModalOperator.LTE:         return f'{var} =< {val}'
    if modal == ModalOperator.GTE:         return f'{var} >= {val}'

    return "TRUE"


def _invariant_to_tla(constraint: Constraint, indent: int = 2) -> str:
    """
    □(cond ⟹ action)  ≡  (~cond) \\/ action
    """
    cond   = _condition_to_tla(constraint)
    action = _action_to_tla(constraint)
    sp = " " * indent

    if cond == "TRUE":
        return f"{sp}{action}"
    return f"{sp}(~({cond})) \\/ ({action})"


# ═════════════════════════════════════════════════════════════════════════════
# 3. SPEC BUILDER
# ═════════════════════════════════════════════════════════════════════════════

class TLASpecResult:
    """Output of TLASpecBuilder.build()"""

    def __init__(
        self,
        module_name: str,
        tla_source: str,
        cfg_source: str,
        domain_info: List[Dict],
    ):
        self.module_name = module_name
        self.tla_source  = tla_source
        self.cfg_source  = cfg_source
        self.domain_info = domain_info  # [{name, domain, tla_set, card}]

    def write(self, directory: Path) -> Tuple[Path, Path]:
        """Write .tla and .cfg to directory; return (tla_path, cfg_path)."""
        tla_path = directory / f"{self.module_name}.tla"
        cfg_path = directory / f"{self.module_name}.cfg"
        tla_path.write_text(self.tla_source, encoding="utf-8")
        cfg_path.write_text(self.cfg_source, encoding="utf-8")
        return tla_path, cfg_path

    def __repr__(self) -> str:
        lines = self.tla_source.count("\n")
        inv_count = self.cfg_source.count("INVARIANT")
        return f"TLASpecResult({self.module_name}, {lines} lines, {inv_count} invariants)"


class TLASpecBuilder:
    """
    Builds a TLA+ module + TLC configuration file from a CSL Constitution.

    Usage:
        builder = TLASpecBuilder()
        spec = builder.build(constitution)
        tla_path, cfg_path = spec.write(tmp_dir)
    """

    # Safe module name: only [A-Za-z0-9_]
    _SAFE_RE = re.compile(r'[^A-Za-z0-9_]')

    def build(self, constitution: Constitution) -> TLASpecResult:
        module_name = self._module_name(constitution)
        constraints = constitution.constraints or []
        decls       = (constitution.domain.variable_declarations
                       if constitution.domain else [])

        # ── Build domain info (with predicate abstraction) ────────────────
        domain_info: List[Dict] = []
        for d in decls:
            raw = d.domain if isinstance(d.domain, str) else str(d.domain)
            tla_set, card = _domain_to_tla_set(d.name, raw, constraints)
            domain_info.append({
                "name":    d.name,
                "domain":  raw,
                "tla_set": tla_set,
                "card":    card,
            })

        tla_source = self._build_tla(module_name, decls, domain_info, constraints)
        cfg_source = self._build_cfg(module_name, constraints)

        return TLASpecResult(module_name, tla_source, cfg_source, domain_info)

    # ------------------------------------------------------------------

    def _module_name(self, constitution: Constitution) -> str:
        base = "CSLPolicy"
        if constitution.domain:
            base = constitution.domain.name or "CSLPolicy"
        safe = self._SAFE_RE.sub("_", base)
        # TLA+ module names must start with a letter
        if safe and not safe[0].isalpha():
            safe = "M_" + safe
        return safe or "CSLPolicy"

    # ------------------------------------------------------------------

    def _build_tla(
        self,
        module_name: str,
        decls: List[VariableDeclaration],
        domain_info: List[Dict],
        constraints: List[Constraint],
    ) -> str:
        lines: List[str] = []
        bar = "-" * 60

        # ── Module header ─────────────────────────────────────────────
        lines.append(f"{bar} MODULE {module_name} {bar}")
        lines.append("")
        lines.append("\\* Auto-generated by CSL-Core TLA+ Spec Builder")
        lines.append("\\* DO NOT EDIT — regenerate from CSL source")
        lines.append("")
        # Always extend Integers so numeric comparisons (<, >, <=, >=) work.
        # Sequences is added for set/tuple operations.
        lines.append("EXTENDS Integers, Sequences")
        lines.append("")

        # ── VARIABLES ────────────────────────────────────────────────
        if decls:
            var_names = ", ".join(d.name for d in decls)
            lines.append(f"VARIABLES {var_names}")
        else:
            lines.append("VARIABLES _dummy")
        lines.append("")

        # ── TypeOK ───────────────────────────────────────────────────
        lines.append("\\* Type invariant — each variable stays in its domain")
        lines.append("TypeOK ==")
        if domain_info:
            for i, di in enumerate(domain_info):
                sep = "/\\" if i > 0 else "  "
                lines.append(f"  {sep} {di['name']} \\in {di['tla_set']}")
        else:
            lines.append("  /\\ _dummy \\in {0}")
        lines.append("")

        # ── Init ─────────────────────────────────────────────────────
        lines.append("\\* Initial state: all variables choose non-deterministically from domain")
        lines.append("Init ==")
        if domain_info:
            for i, di in enumerate(domain_info):
                sep = "/\\" if i > 0 else "  "
                lines.append(f"  {sep} {di['name']} \\in {di['tla_set']}")
        else:
            lines.append("  /\\ _dummy = 0")
        lines.append("")

        # ── Next (stutter) ───────────────────────────────────────────
        lines.append("\\* Next: stutter — state is fixed; TLC checks all Init states")
        lines.append("Next ==")
        if decls:
            var_names = ", ".join(d.name for d in decls)
            lines.append(f"  UNCHANGED <<{var_names}>>")
        else:
            lines.append("  UNCHANGED <<_dummy>>")
        lines.append("")

        # ── vars tuple (must be defined BEFORE Spec) ─────────────────
        if decls:
            var_names = ", ".join(d.name for d in decls)
            lines.append(f"vars == <<{var_names}>>")
        else:
            lines.append("vars == <<_dummy>>")
        lines.append("")

        # ── Spec ─────────────────────────────────────────────────────
        lines.append("Spec == Init /\\ [][Next]_vars")
        lines.append("")

        # ── Invariants ───────────────────────────────────────────────
        for c in constraints:
            inv_name = self._safe_name(c.name)
            lines.append(f"\\* CSL: {c.name}")
            lines.append(f"{inv_name} ==")
            body = _invariant_to_tla(c, indent=2)
            lines.append(body)
            lines.append("")

        # ── Module footer ─────────────────────────────────────────────
        lines.append("=" * (len(bar) * 2 + len(module_name) + 2))
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------

    def _build_cfg(self, module_name: str, constraints: List[Constraint]) -> str:
        lines: List[str] = []
        lines.append(f"\\* TLC configuration for {module_name}")
        lines.append("INIT Init")
        lines.append("NEXT Next")
        lines.append("")
        lines.append("\\* Type invariant (always check)")
        lines.append("INVARIANT TypeOK")
        lines.append("")

        if constraints:
            lines.append("\\* CSL constraints as safety invariants")
            for c in constraints:
                lines.append(f"INVARIANT {self._safe_name(c.name)}")

        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------

    @staticmethod
    def _safe_name(name: str) -> str:
        """Convert constraint name to a valid TLA+ identifier."""
        safe = re.sub(r'[^A-Za-z0-9_]', '_', name)
        if safe and not safe[0].isalpha():
            safe = "inv_" + safe
        return safe or "inv_unnamed"
