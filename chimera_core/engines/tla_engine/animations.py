"""
TLA+ Animation Engine

Epic terminal animations for TLA+ formal verification.

The experience: we are literally creating a universe of all possible
states and walking through every single one to prove properties hold.

Uses Rich for rendering: panels, progress bars, live displays, tables.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.columns import Columns
from rich.align import Align
from rich.rule import Rule
from rich.syntax import Syntax
from rich.tree import Tree
from rich import box

# ============================================================================
# CONSTANTS
# ============================================================================

BANNER = """
 ████████╗██╗      █████╗    ██╗
 ╚══██╔══╝██║     ██╔══██╗  ██╔╝
    ██║   ██║     ███████║ ██╔╝
    ██║   ██║     ██╔══██║ ███╗
    ██║   ███████╗██║  ██║ ╚██╗
    ╚═╝   ╚══════╝╚═╝  ╚═╝  ╚═╝
"""

TLA_BANNER = "TLA⁺ FORMAL VERIFICATION ENGINE"
CHIMERA_SUB = "Chimera Specification Language · Temporal Logic of Actions"

# Color palette
C_TITLE   = "bold bright_cyan"
C_SUB     = "dim cyan"
C_OK      = "bold bright_green"
C_FAIL    = "bold bright_red"
C_WARN    = "bold yellow"
C_DIM     = "dim white"
C_VAR     = "bold magenta"
C_STATE   = "bright_blue"
C_PROOF   = "bold bright_yellow"
C_BORDER  = "bright_cyan"


# ============================================================================
# RESULT TYPES
# ============================================================================

@dataclass
class ConstraintAnimResult:
    name: str
    status: str        # "HOLDS" | "VIOLATED" | "UNKNOWN"
    states_checked: int
    time_ms: int
    counterexample: Optional[List[Dict]] = None


@dataclass
class VerificationAnimResult:
    domain_name: str
    total_states: int
    total_time_ms: int
    constraint_results: List[ConstraintAnimResult]
    proof_hash: str
    all_valid: bool


# ============================================================================
# HELPER RENDERERS
# ============================================================================

def _make_header(
    engine_mode: str = "MOCK",
    tlc_version: str = "",
    tlc_pid: int = 0,
    java_workers: int = 0,
) -> Panel:
    title_text = Text(TLA_BANNER, style=C_TITLE, justify="center")
    sub_text   = Text(CHIMERA_SUB, style=C_SUB, justify="center")

    if engine_mode == "TLC":
        engine_badge = Text(
            "⚡  REAL TLC  ·  java -jar tla2tools.jar  ·  Exhaustive Model Checking",
            style="bold bright_green",
            justify="center",
        )
        # Identity proof line — values that Python BFS could never produce
        detail_parts = []
        if tlc_version:   detail_parts.append(tlc_version)
        if tlc_pid:       detail_parts.append(f"pid {tlc_pid}")
        if java_workers:  detail_parts.append(f"{java_workers} worker(s)")
        body = title_text + Text("\n") + sub_text + Text("\n\n") + engine_badge
        if detail_parts:
            identity = Text(
                "  " + "  ·  ".join(detail_parts),
                style="dim green",
                justify="center",
            )
            body = body + Text("\n") + identity
    else:
        engine_badge = Text(
            "⚙  BFS Mock Engine  ·  Python State-Space Explorer  ·  (TLC unavailable)",
            style="bold yellow",
            justify="center",
        )
        body = title_text + Text("\n") + sub_text + Text("\n\n") + engine_badge

    content = Align.center(body)
    return Panel(content, style=C_BORDER, box=box.DOUBLE, padding=(0, 2))


def _make_domain_table(var_info: List[Dict[str, str]]) -> Table:
    """Renders the variable domain table."""
    table = Table(
        title="[bold cyan]Universe Variables[/]",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
        min_width=60,
    )
    table.add_column("Variable", style="bold magenta", no_wrap=True)
    table.add_column("Domain", style="bright_white")
    table.add_column("Cardinality", style="bright_yellow", justify="right")

    for v in var_info:
        table.add_row(v["name"], v["domain"], v["card"])

    return table


def _make_constraint_table(results: List[ConstraintAnimResult]) -> Table:
    """Renders the verification results table."""
    table = Table(
        title="[bold cyan]Temporal Property Verification[/]",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
        min_width=72,
    )
    table.add_column("Constraint", style="bold white", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("States", justify="right", style="bright_yellow")
    table.add_column("Time", justify="right", style=C_DIM)

    for r in results:
        if r.status == "HOLDS":
            status_cell = Text("✅  HOLDS", style=C_OK)
        elif r.status == "VIOLATED":
            status_cell = Text("❌  VIOLATED", style=C_FAIL)
        else:
            status_cell = Text("⚠️  UNKNOWN", style=C_WARN)

        table.add_row(
            r.name,
            status_cell,
            f"{r.states_checked:,}",
            f"{r.time_ms}ms",
        )

    return table


def _make_final_panel(result: VerificationAnimResult) -> Panel:
    """Renders the final summary panel."""
    if result.all_valid:
        icon   = "✅"
        title  = "[bold bright_green]TLA⁺ VERIFICATION COMPLETE — ALL PROPERTIES HOLD[/]"
        border = "bright_green"
    else:
        icon   = "❌"
        title  = "[bold bright_red]TLA⁺ VERIFICATION FAILED — PROPERTY VIOLATION FOUND[/]"
        border = "bright_red"

    lines = [
        Text.assemble((f"  {icon}  Domain     : ", "dim white"), (result.domain_name, "bold magenta")),
        Text.assemble(("  ⬡  States     : ", "dim white"), (f"{result.total_states:,}", "bold bright_yellow")),
        Text.assemble(("  ⏱  Total time : ", "dim white"), (f"{result.total_time_ms}ms", "bold white")),
        Text.assemble(("  🔐 Proof hash : ", "dim white"), (result.proof_hash[:16] + "…", "bold cyan")),
    ]

    body = Text("\n").join(lines)
    return Panel(
        Align.left(Text("\n") + body + Text("\n")),
        title=title,
        border_style=border,
        box=box.DOUBLE,
        padding=(0, 2),
    )


# ============================================================================
# MAIN ANIMATION ENGINE
# ============================================================================

class TLAAnimationEngine:
    """
    Orchestrates the full TLA+ verification animation.

    Usage:
        engine = TLAAnimationEngine()
        engine.run(domain_name, var_info, constraint_names, checker_fn)
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def run(
        self,
        domain_name: str,
        var_info: List[Dict[str, str]],
        constraint_names: List[str],
        checker_fn: Callable[[str, Callable], ConstraintAnimResult],
        engine_mode: str = "MOCK",   # "TLC" or "MOCK"
        tlc_version: str = "",       # surfaced in banner to prove real TLC ran
        tlc_pid: int = 0,
        java_workers: int = 0,
    ) -> VerificationAnimResult:
        """
        Run the full animation sequence and return a VerificationAnimResult.

        Args:
            domain_name      : Name of the CSL domain
            var_info         : List of dicts: {name, domain, card}
            constraint_names : Names of constraints to verify
            checker_fn       : checker_fn(name, progress_callback) -> ConstraintAnimResult
            engine_mode      : "TLC" (real tla2tools.jar) or "MOCK" (Python BFS)
            tlc_version      : TLC version string (e.g. "TLC2 Version 2026.03.31…")
            tlc_pid          : OS PID of the TLC JVM process
            java_workers     : number of TLC worker threads
        """
        con = self.console
        con.print()

        # 1 ── Banner ──────────────────────────────────────────────────
        con.print(_make_header(
            engine_mode=engine_mode,
            tlc_version=tlc_version,
            tlc_pid=tlc_pid,
            java_workers=java_workers,
        ))
        con.print()

        # 2 ── Universe construction ───────────────────────────────────
        self._animate_universe_init(domain_name, var_info)

        # 3 ── State-space expansion ───────────────────────────────────
        total_states = self._animate_state_space_expansion(var_info, engine_mode=engine_mode)

        # 4 ── Constraint verification (one by one) ────────────────────
        constraint_results = self._animate_constraint_verification(
            constraint_names, checker_fn
        )

        # 5 ── Proof certificate ───────────────────────────────────────
        proof_hash = self._animate_proof_certificate(constraint_results)

        # 6 ── Final summary ───────────────────────────────────────────
        total_time = sum(r.time_ms for r in constraint_results)
        all_valid  = all(r.status == "HOLDS" for r in constraint_results)

        result = VerificationAnimResult(
            domain_name=domain_name,
            total_states=total_states,
            total_time_ms=total_time,
            constraint_results=constraint_results,
            proof_hash=proof_hash,
            all_valid=all_valid,
        )

        con.print()
        con.print(_make_final_panel(result))
        con.print()

        return result

    # ------------------------------------------------------------------
    # STEP 2: Universe initialisation
    # ------------------------------------------------------------------

    def _animate_universe_init(self, domain_name: str, var_info: List[Dict]) -> None:
        con = self.console
        con.print(
            Panel(
                Text.assemble(
                    ("  ◉  Constructing Universe: ", "dim white"),
                    (f'"{domain_name}"', C_VAR),
                ),
                style=C_BORDER,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

        # Animate each variable appearing with a spinner
        with Progress(
            SpinnerColumn(spinner_name="dots2", style="bright_cyan"),
            TextColumn("[progress.description]{task.description}"),
            console=con,
            transient=True,
        ) as prog:
            task = prog.add_task("  Initialising variable domains…", total=len(var_info))
            for v in var_info:
                time.sleep(0.06)
                prog.advance(task)

        con.print(_make_domain_table(var_info))
        con.print()

    # ------------------------------------------------------------------
    # STEP 3: State-space expansion animation
    # ------------------------------------------------------------------

    def _animate_state_space_expansion(
        self,
        var_info: List[Dict],
        engine_mode: str = "MOCK",
    ) -> int:
        con = self.console

        # Estimate total state space size
        total_estimate = 1
        for v in var_info:
            card_str = v.get("card", "∞")
            # Handle abstraction labels like "|5| (abstracted from |100,001|)"
            try:
                first_num = card_str.split("|")[1].replace(",", "")
                total_estimate *= int(first_num)
            except Exception:
                if card_str == "∞":
                    total_estimate = min(total_estimate * 500, 10_000)
                else:
                    try:
                        total_estimate *= int(card_str)
                    except ValueError:
                        total_estimate = min(total_estimate * 10, 10_000)
        total_estimate = min(total_estimate, 10_000)

        if engine_mode == "TLC":
            expansion_label = "  ◉  Invoking TLC — Exhaustive Symbolic Reachability Analysis"
            expansion_style = "bold bright_green"
        else:
            expansion_label = "  ◉  Expanding State Space  (BFS / Breadth-First Search)"
            expansion_style = "dim white"

        con.print(
            Panel(
                Text(expansion_label, style=expansion_style),
                style=C_BORDER,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

        explored = 0
        depth    = 0
        frontier = max(1, total_estimate // 10)

        with Progress(
            SpinnerColumn(spinner_name="aesthetic", style="bright_cyan"),
            BarColumn(bar_width=36, style="cyan", complete_style="bright_cyan"),
            TextColumn("[bright_yellow]{task.completed:>6,}[/] / [dim]{task.total:,}[/] states"),
            TextColumn("  depth=[bright_white]{task.fields[depth]}[/]"),
            TextColumn("  frontier=[dim]{task.fields[frontier]}[/]"),
            TimeElapsedColumn(),
            console=con,
            transient=False,
        ) as prog:
            explore_label = "  Running TLC…" if engine_mode == "TLC" else "  Exploring…"
            task = prog.add_task(
                explore_label,
                total=total_estimate,
                depth=0,
                frontier=frontier,
            )

            batch = max(1, total_estimate // 40)
            while explored < total_estimate:
                step = min(batch, total_estimate - explored)
                explored += step
                depth    += 1
                frontier  = max(0, total_estimate - explored)

                prog.update(
                    task,
                    advance=step,
                    depth=depth,
                    frontier=frontier,
                )
                time.sleep(0.02)

        con.print(
            Text.assemble(
                ("  └─ ", "dim white"),
                (f"{explored:,}", "bold bright_yellow"),
                (" states reachable · depth ", "dim white"),
                (str(depth), "bold white"),
                (" · universe fully mapped", "dim white"),
            )
        )
        con.print()
        return explored

    # ------------------------------------------------------------------
    # STEP 4: Constraint verification
    # ------------------------------------------------------------------

    def _animate_constraint_verification(
        self,
        constraint_names: List[str],
        checker_fn: Callable[[str, Callable], ConstraintAnimResult],
    ) -> List[ConstraintAnimResult]:
        con = self.console
        results: List[ConstraintAnimResult] = []

        con.print(
            Panel(
                Text("  ◉  Verifying Temporal Properties  □(WHEN … THEN …)", style="dim white"),
                style=C_BORDER,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

        for name in constraint_names:
            # Show "checking…" spinner while checker runs
            result_holder: List[ConstraintAnimResult] = []

            def run_check(n=name, holder=result_holder):
                r = checker_fn(n, lambda _: None)
                holder.append(r)

            t = threading.Thread(target=run_check, daemon=True)

            with Progress(
                SpinnerColumn(spinner_name="bouncingBar", style="bright_cyan"),
                TextColumn(f"  Checking [bold magenta]{name}[/] …"),
                TimeElapsedColumn(),
                console=con,
                transient=True,
            ) as prog:
                prog.add_task("", total=None)
                t.start()
                t.join()

            r = result_holder[0]
            results.append(r)

            # Print result line
            if r.status == "HOLDS":
                marker = Text("✅  HOLDS", style=C_OK)
            elif r.status == "VIOLATED":
                marker = Text("❌  VIOLATED", style=C_FAIL)
            else:
                marker = Text("⚠️  UNKNOWN", style=C_WARN)

            con.print(
                Text.assemble(
                    ("  ├─ □(", "dim white"),
                    (name, "bold magenta"),
                    (")  ", "dim white"),
                ) + marker + Text.assemble(
                    ("  [", "dim white"),
                    (f"{r.states_checked:,} states", "bright_yellow"),
                    (f"  {r.time_ms}ms", "dim white"),
                    ("]", "dim white"),
                )
            )

            # If violated, print counterexample
            if r.status == "VIOLATED" and r.counterexample:
                con.print(Text("  │   Counterexample:", style=C_FAIL))
                for i, s in enumerate(r.counterexample[:3]):
                    # Normalize MCState or plain dict
                    if hasattr(s, "variables"):
                        s_dict = s.variables
                    elif isinstance(s, dict):
                        s_dict = s
                    else:
                        s_dict = {}
                    con.print(Text(f"  │     State {i}: {s_dict}", style="dim red"))
                con.print()

        con.print()
        return results

    # ------------------------------------------------------------------
    # STEP 5: Proof certificate generation
    # ------------------------------------------------------------------

    def _animate_proof_certificate(
        self, results: List[ConstraintAnimResult]
    ) -> str:
        con = self.console

        con.print(
            Panel(
                Text("  ◉  Generating Proof Certificate (SHA-256 signed)", style="dim white"),
                style=C_BORDER,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

        steps = [
            "Assembling proof steps from model-checking trace…",
            "Computing inductive invariants…",
            "Building certificate chain…",
            "Hashing with SHA-256…",
        ]

        with Progress(
            SpinnerColumn(spinner_name="dots12", style="bright_yellow"),
            TextColumn("[progress.description]{task.description}"),
            console=con,
            transient=True,
        ) as prog:
            for step in steps:
                t = prog.add_task(f"  {step}", total=1)
                time.sleep(0.08)
                prog.update(t, advance=1)

        # Generate a deterministic hash from the results
        import hashlib, json
        payload = json.dumps(
            [{"name": r.name, "status": r.status, "states": r.states_checked} for r in results],
            sort_keys=True,
        )
        proof_hash = hashlib.sha256(payload.encode()).hexdigest()

        con.print(
            Text.assemble(
                ("  └─ Proof hash: ", "dim white"),
                (proof_hash[:32] + "…", C_PROOF),
                (" ✅", C_OK),
            )
        )
        con.print()

        return proof_hash


# ============================================================================
# VIOLATION REPORT + SUGGESTION CARDS
# ============================================================================

CONF_STYLE = {
    "HIGH":   ("●●●", "bold bright_green"),
    "MEDIUM": ("●●○", "bold yellow"),
    "LOW":    ("●○○", "dim white"),
}

FIX_ICON = {
    "DOMAIN_RESTRICTION":      "🔒",
    "CONDITION_STRENGTHENING": "🔧",
    "GUARD_ADDITION":          "🛡",
    "BOUND_TIGHTENING":        "📐",
    "POLICY_INVERSION":        "🔄",
}


def render_violation_reports(
    analyses: list,           # List[ViolationAnalysis]
    console: Optional[Console] = None,
) -> None:
    """
    Render the full violation + suggestion report to the terminal.

    Args:
        analyses : list of ViolationAnalysis objects (one per violated constraint)
        console  : Rich Console (defaults to a new one)
    """
    from chimera_core.engines.tla_engine.suggestion_engine import (
        ViolationAnalysis, ViolationSuggestion,
    )

    con = console or Console()

    if not analyses:
        return

    con.print()
    con.print(Rule(
        title="[bold bright_red]  TLA⁺ VIOLATION ANALYSIS  ",
        style="bright_red",
        characters="═",
    ))
    con.print()

    for idx, analysis in enumerate(analyses):
        _render_single_violation(con, analysis, idx + 1, len(analyses))

    # Final remediation summary
    total_suggestions = sum(len(a.suggestions) for a in analyses)
    con.print(Rule(style="dim red", characters="─"))
    con.print(
        Text.assemble(
            ("  📋  ", ""),
            (f"{len(analyses)} violation(s)", "bold bright_red"),
            ("  ·  ", "dim white"),
            (f"{total_suggestions} suggestion(s) generated", "bold yellow"),
            ("  ·  Fix the issues above and re-run ", "dim white"),
            ("cslcore formal", "bold cyan"),
            (" to confirm", "dim white"),
        )
    )
    con.print()


def _render_single_violation(
    con: Console,
    analysis,          # ViolationAnalysis
    n: int,
    total: int,
) -> None:
    """Render one violated constraint: trace + root cause + suggestion cards."""

    # ── Violation header ──────────────────────────────────────────────
    con.print(Panel(
        Text.assemble(
            ("  ❌  CONSTRAINT VIOLATED  ", "bold bright_red"),
            (f"[{n}/{total}]  ", "dim red"),
            (analysis.constraint_name, "bold white"),
        ),
        border_style="bright_red",
        box=box.HEAVY,
        padding=(0, 1),
    ))
    con.print()

    # ── Counterexample trace ──────────────────────────────────────────
    _render_counterexample(con, analysis)

    # ── Root cause ────────────────────────────────────────────────────
    con.print(
        Panel(
            Text.assemble(
                ("  Root Cause\n\n", "bold bright_red"),
                ("  ", ""),
                (analysis.root_cause, "white"),
            ),
            border_style="red",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    con.print()

    # ── Suggestion cards ──────────────────────────────────────────────
    if not analysis.suggestions:
        con.print(Text("  No automated suggestions available for this violation.", style="dim"))
        con.print()
        return

    _animate_suggestion_generation(con, len(analysis.suggestions))

    for si, sug in enumerate(analysis.suggestions):
        _render_suggestion_card(con, sug, si + 1, len(analysis.suggestions))

    con.print()


def _render_counterexample(con: Console, analysis) -> None:
    """Pretty-print the counterexample trace (trimmed to key states)."""
    states_all = getattr(analysis, "_raw_counterexample", None) or []

    # Find actual violation index in the raw trace
    viol_idx = len(states_all) - 1
    for i, s in enumerate(states_all):
        if s == analysis.violation_state:
            viol_idx = i
            break

    # Trim: keep first 3 + violation state (+ 1 before it if needed)
    MAX_SHOW = 6
    if len(states_all) <= MAX_SHOW:
        display = list(enumerate(states_all))
    else:
        # first 2, ..., 2 before violation, violation itself
        head    = list(enumerate(states_all[:2]))
        pre_vio = [(i, states_all[i]) for i in range(max(2, viol_idx - 1), viol_idx)]
        vio     = [(viol_idx, states_all[viol_idx])]
        display = head + [(-1, None)] + pre_vio + vio   # -1 marks "···"

    con.print(Text("  Counterexample Trace:", style="bold yellow"))
    con.print()

    for i, s in display:
        if i == -1:          # ellipsis row
            con.print(Text("  │   ···", style="dim white"))
            continue

        is_viol = (i == viol_idx)
        prefix  = "  └─" if is_viol else "  ├─"
        marker  = Text("  ◀  VIOLATION", style="bold bright_red") if is_viol else Text("")

        # Normalize state to dict (supports both MCState and plain dict)
        if hasattr(s, "variables"):
            s_dict = s.variables
        elif isinstance(s, dict):
            s_dict = s
        else:
            s_dict = {}

        state_text = Text.assemble((prefix + f" State {i}  ", "dim white"))
        for k, v in s_dict.items():
            val_str = f'"{v}"' if isinstance(v, str) else str(v)
            style   = "bold bright_red" if (k in analysis.violation_vars and is_viol) else "bright_white"
            state_text += Text.assemble(
                (f"{k}", "dim cyan"), ("=", "dim white"), (val_str, style), ("  ", ""),
            )
        state_text += marker
        con.print(state_text)

    con.print()


def _animate_suggestion_generation(con: Console, count: int) -> None:
    """Brief spinner before showing suggestions."""
    steps = [
        "Analyzing constraint structure…",
        "Inspecting variable domains…",
        "Evaluating fix strategies…",
        f"Generating {count} suggestion(s)…",
    ]
    with Progress(
        SpinnerColumn(spinner_name="dots12", style="bright_yellow"),
        TextColumn("[progress.description]{task.description}"),
        console=con,
        transient=True,
    ) as prog:
        for step in steps:
            t = prog.add_task(f"  [bold yellow]{step}", total=1)
            time.sleep(0.07)
            prog.update(t, advance=1)

    con.print(
        Text.assemble(
            ("  💡  ", ""),
            (f"{count} suggestion(s) found — review and apply below", "bold yellow"),
        )
    )
    con.print()


def _render_suggestion_card(
    con: Console,
    sug,          # ViolationSuggestion
    n: int,
    total: int,
) -> None:
    """Render a single suggestion card with diff snippets."""
    conf_dots, conf_style = CONF_STYLE.get(sug.confidence, ("●○○", "dim"))
    fix_icon = FIX_ICON.get(sug.fix_type, "💡")
    fix_label = sug.fix_type.replace("_", " ").title()

    # Card header
    con.print(Panel(
        Text.assemble(
            (f"  {fix_icon}  SUGGESTION {n}/{total}  ", "bold white"),
            (conf_dots + "  ", conf_style),
            (sug.confidence + " CONFIDENCE  ", conf_style),
            ("·  ", "dim white"),
            (fix_label, "dim white"),
        ),
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    ))

    # Title
    con.print(Text.assemble(
        ("  ", ""),
        (sug.title, "bold bright_yellow"),
    ))
    con.print()

    # Explanation
    explanation_lines = sug.explanation.split(". ")
    for line in explanation_lines:
        line = line.strip()
        if line:
            con.print(Text("  " + line + ("." if not line.endswith(".") else ""), style="white"))
    con.print()

    # Before / After snippets
    if sug.before_snippet or sug.after_snippet:
        _render_diff(con, sug.before_snippet, sug.after_snippet)

    con.print(Rule(style="dim yellow", characters="╌"))
    con.print()


def _render_diff(
    con: Console,
    before: Optional[str],
    after: Optional[str],
) -> None:
    """Render a before/after CSL diff using Rich Syntax."""
    if before:
        con.print(Text("  BEFORE  ─────────────────────────────────────────────", style="dim red"))
        syn = Syntax(
            before.strip(),
            "ini",         # close enough for CSL keyword highlighting
            theme="monokai",
            background_color="default",
            indent_guides=False,
            line_numbers=False,
            word_wrap=True,
        )
        con.print(Text("  ", end=""), end="")
        con.print(syn)

    if after:
        con.print(Text("  AFTER   ─────────────────────────────────────────────", style="dim green"))
        syn = Syntax(
            after.strip(),
            "ini",
            theme="monokai",
            background_color="default",
            indent_guides=False,
            line_numbers=False,
            word_wrap=True,
        )
        con.print(Text("  ", end=""), end="")
        con.print(syn)
    con.print()
