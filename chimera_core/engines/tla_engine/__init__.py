"""
TLA+ Engine for CSL-Core

Provides formal model checking (Temporal Logic of Actions) for CSL policies.

Key entry point:
    from chimera_core.engines.tla_engine import TLAVerifier
    ok, issues = TLAVerifier().verify(constitution)
"""

from .verifier import TLAVerifier, TLAIssue

from .model_checker import (
    MockModelChecker,
    CheckResult,
    ModelCheckingResult,
    CounterExample,
    ExplorationStrategy,
    State as MCState,
    StateSpace,
)

from .temporal_logic import (
    TemporalChecker,
    TemporalFormula,
    AtomicProp,
    Always,
    Eventually,
    Until,
    WeakUntil,
    Next,
    Not,
    And,
    Or,
    Implies,
    Trace,
    State,
    safety_property,
    liveness_property,
    response_property,
    stability_property,
    create_trace_from_states,
)

from .tla_generator import (
    TLASpec,
    TLAVariable,
    TLAConstant,
    TLAOperator,
    CSLToTLATranslator,
    create_safety_property,
    create_liveness_property,
    create_response_property,
)

from .proof_builder import (
    ProofCertificate,
    ProofStep,
    ProofType,
    ProofStatus,
    ProofValidator,
    InductiveProofBuilder,
    SafetyProofBuilder,
    ModelCheckingProofBuilder,
    create_inductive_proof,
    create_safety_proof,
)

from .animations import TLAAnimationEngine, ConstraintAnimResult, VerificationAnimResult

from .tla_spec_builder import TLASpecBuilder, TLASpecResult

from .tlc_runner import (
    TLCRunner,
    TLCResult,
    TLCViolation,
    java_available,
    find_jar,
    ensure_jar,
    run_tlc_on_spec,
    parse_tlc_output,
)

__all__ = [
    # Main verifier
    "TLAVerifier",
    "TLAIssue",
    # Model checking
    "MockModelChecker",
    "CheckResult",
    "ModelCheckingResult",
    "CounterExample",
    "ExplorationStrategy",
    "MCState",
    "StateSpace",
    # Temporal logic
    "TemporalChecker",
    "TemporalFormula",
    "AtomicProp",
    "Always",
    "Eventually",
    "Until",
    "WeakUntil",
    "Next",
    "Not",
    "And",
    "Or",
    "Implies",
    "Trace",
    "State",
    "safety_property",
    "liveness_property",
    "response_property",
    "stability_property",
    "create_trace_from_states",
    # TLA+ generator
    "TLASpec",
    "TLAVariable",
    "TLAConstant",
    "TLAOperator",
    "CSLToTLATranslator",
    "create_safety_property",
    "create_liveness_property",
    "create_response_property",
    # Proof builder
    "ProofCertificate",
    "ProofStep",
    "ProofType",
    "ProofStatus",
    "ProofValidator",
    "InductiveProofBuilder",
    "SafetyProofBuilder",
    "ModelCheckingProofBuilder",
    "create_inductive_proof",
    "create_safety_proof",
    # Animations
    "TLAAnimationEngine",
    "ConstraintAnimResult",
    "VerificationAnimResult",
    # Real TLC integration
    "TLASpecBuilder",
    "TLASpecResult",
    "TLCRunner",
    "TLCResult",
    "TLCViolation",
    "java_available",
    "find_jar",
    "ensure_jar",
    "run_tlc_on_spec",
    "parse_tlc_output",
]
