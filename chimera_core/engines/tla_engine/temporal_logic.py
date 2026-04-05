"""
Temporal Logic - LTL/CTL Operators

Implements temporal logic operators for formal verification:
- LTL (Linear Temporal Logic): □, ◇, ○, U, W
- CTL (Computation Tree Logic): AG, AF, EG, EF, AX, EX, AU, EU
- Safety/Liveness properties
- Trace checking

Based on:
- Lamport, L. (2002). Specifying Systems (TLA+ book)
- Clarke, E. M., Grumberg, O., & Peled, D. (1999). Model Checking
"""

from typing import Callable, List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod


# ============================================================================
# ENUMS
# ============================================================================

class TemporalOperatorType(Enum):
    """Types of temporal operators"""
    # LTL
    ALWAYS = "[]"           # □ (box) - always, globally
    EVENTUALLY = "<>"       # ◇ (diamond) - eventually, finally
    NEXT = "X"              # ○ - next state
    UNTIL = "U"             # - until
    WEAK_UNTIL = "W"        # - weak until
    RELEASE = "R"           # - release
    
    # CTL
    AG = "AG"               # All paths, Globally
    AF = "AF"               # All paths, Finally
    EG = "EG"               # Exists path, Globally
    EF = "EF"               # Exists path, Finally
    AX = "AX"               # All paths, neXt
    EX = "EX"               # Exists path, neXt
    AU = "AU"               # All paths, Until
    EU = "EU"               # Exists path, Until


class PropertyType(Enum):
    """Types of temporal properties"""
    SAFETY = "safety"           # "Bad things never happen"
    LIVENESS = "liveness"       # "Good things eventually happen"
    FAIRNESS = "fairness"       # "Fair scheduling"
    INVARIANT = "invariant"     # "Always true"


# ============================================================================
# TRACE REPRESENTATION
# ============================================================================

@dataclass
class State:
    """Single state in execution trace"""
    variables: Dict[str, Any]
    timestamp: Optional[int] = None
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like access"""
        return self.variables.get(key)
    
    def satisfies(self, predicate: Callable[[Dict], bool]) -> bool:
        """Check if state satisfies predicate"""
        return predicate(self.variables)


class Trace:
    """
    Execution trace (sequence of states).
    
    Used for LTL checking.
    """
    
    def __init__(self, states: List[State]):
        """
        Initialize trace.
        
        Args:
            states: List of states in temporal order
        """
        self.states = states
    
    def __len__(self) -> int:
        return len(self.states)
    
    def __getitem__(self, index: int) -> State:
        return self.states[index]
    
    def get_suffix(self, start: int) -> 'Trace':
        """Get suffix of trace starting at index"""
        return Trace(self.states[start:])
    
    def is_finite(self) -> bool:
        """Check if trace is finite"""
        return True  # In V0.1, all traces are finite
    
    def variables_at(self, index: int) -> Dict[str, Any]:
        """Get state variables at index"""
        return self.states[index].variables


# ============================================================================
# TEMPORAL FORMULAS (Abstract)
# ============================================================================

class TemporalFormula(ABC):
    """Base class for temporal formulas"""
    
    @abstractmethod
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """
        Evaluate formula on trace starting at index.
        
        Args:
            trace: Execution trace
            index: Starting position
            
        Returns:
            True if formula holds
        """
        pass
    
    @abstractmethod
    def to_string(self) -> str:
        """Convert to string representation"""
        pass
    
    def __repr__(self):
        return self.to_string()


# ============================================================================
# ATOMIC PROPOSITIONS
# ============================================================================

class AtomicProp(TemporalFormula):
    """
    Atomic proposition.
    
    Example: price > 50000
    """
    
    def __init__(self, predicate: Callable[[Dict], bool], description: str = ""):
        """
        Initialize atomic proposition.
        
        Args:
            predicate: Function that checks if state satisfies property
            description: Human-readable description
        """
        self.predicate = predicate
        self.description = description
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """Check if current state satisfies predicate"""
        if index >= len(trace):
            return False
        return self.predicate(trace.variables_at(index))
    
    def to_string(self) -> str:
        return self.description or "AtomicProp"


# ============================================================================
# BOOLEAN OPERATORS
# ============================================================================

class Not(TemporalFormula):
    """Negation: ¬φ"""
    
    def __init__(self, formula: TemporalFormula):
        self.formula = formula
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        return not self.formula.evaluate(trace, index)
    
    def to_string(self) -> str:
        return f"¬({self.formula.to_string()})"


class And(TemporalFormula):
    """Conjunction: φ ∧ ψ"""
    
    def __init__(self, left: TemporalFormula, right: TemporalFormula):
        self.left = left
        self.right = right
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        return self.left.evaluate(trace, index) and self.right.evaluate(trace, index)
    
    def to_string(self) -> str:
        return f"({self.left.to_string()} ∧ {self.right.to_string()})"


class Or(TemporalFormula):
    """Disjunction: φ ∨ ψ"""
    
    def __init__(self, left: TemporalFormula, right: TemporalFormula):
        self.left = left
        self.right = right
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        return self.left.evaluate(trace, index) or self.right.evaluate(trace, index)
    
    def to_string(self) -> str:
        return f"({self.left.to_string()} ∨ {self.right.to_string()})"


class Implies(TemporalFormula):
    """Implication: φ → ψ"""
    
    def __init__(self, antecedent: TemporalFormula, consequent: TemporalFormula):
        self.antecedent = antecedent
        self.consequent = consequent
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        return not self.antecedent.evaluate(trace, index) or self.consequent.evaluate(trace, index)
    
    def to_string(self) -> str:
        return f"({self.antecedent.to_string()} → {self.consequent.to_string()})"


# ============================================================================
# LTL OPERATORS
# ============================================================================

class Next(TemporalFormula):
    """
    Next: ○φ (or Xφ)
    
    True if φ holds in next state.
    """
    
    def __init__(self, formula: TemporalFormula):
        self.formula = formula
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        if index + 1 >= len(trace):
            return False
        return self.formula.evaluate(trace, index + 1)
    
    def to_string(self) -> str:
        return f"○({self.formula.to_string()})"


class Always(TemporalFormula):
    """
    Always: □φ (or Gφ)
    
    True if φ holds in all future states.
    
    □φ ≡ φ ∧ ○□φ
    """
    
    def __init__(self, formula: TemporalFormula):
        self.formula = formula
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """Check if formula holds at all future positions"""
        for i in range(index, len(trace)):
            if not self.formula.evaluate(trace, i):
                return False
        return True
    
    def to_string(self) -> str:
        return f"□({self.formula.to_string()})"


class Eventually(TemporalFormula):
    """
    Eventually: ◇φ (or Fφ)
    
    True if φ holds in some future state.
    
    ◇φ ≡ ¬□¬φ
    """
    
    def __init__(self, formula: TemporalFormula):
        self.formula = formula
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """Check if formula holds at some future position"""
        for i in range(index, len(trace)):
            if self.formula.evaluate(trace, i):
                return True
        return False
    
    def to_string(self) -> str:
        return f"◇({self.formula.to_string()})"


class Until(TemporalFormula):
    """
    Until: φ U ψ
    
    φ holds until ψ becomes true.
    ψ must eventually become true.
    """
    
    def __init__(self, left: TemporalFormula, right: TemporalFormula):
        self.left = left
        self.right = right
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """Check if left holds until right becomes true"""
        for i in range(index, len(trace)):
            # Check if right holds
            if self.right.evaluate(trace, i):
                return True
            
            # Check if left still holds
            if not self.left.evaluate(trace, i):
                return False
        
        # Reached end without right becoming true
        return False
    
    def to_string(self) -> str:
        return f"({self.left.to_string()} U {self.right.to_string()})"


class WeakUntil(TemporalFormula):
    """
    Weak Until: φ W ψ
    
    φ holds until ψ becomes true.
    ψ may never become true (then φ must always hold).
    
    φ W ψ ≡ (φ U ψ) ∨ □φ
    """
    
    def __init__(self, left: TemporalFormula, right: TemporalFormula):
        self.left = left
        self.right = right
    
    def evaluate(self, trace: Trace, index: int = 0) -> bool:
        """Check if left holds weakly until right"""
        for i in range(index, len(trace)):
            # If right holds, we're done
            if self.right.evaluate(trace, i):
                return True
            
            # If left doesn't hold, fail
            if not self.left.evaluate(trace, i):
                return False
        
        # Reached end with left always holding - success
        return True
    
    def to_string(self) -> str:
        return f"({self.left.to_string()} W {self.right.to_string()})"


# ============================================================================
# PROPERTY BUILDERS
# ============================================================================

def safety_property(invariant: Callable[[Dict], bool], description: str = "") -> TemporalFormula:
    """
    Create safety property: □φ
    
    "Bad thing never happens"
    
    Args:
        invariant: Predicate that should always hold
        description: Description
        
    Returns:
        Always formula
    """
    prop = AtomicProp(invariant, description)
    return Always(prop)


def liveness_property(goal: Callable[[Dict], bool], description: str = "") -> TemporalFormula:
    """
    Create liveness property: ◇φ
    
    "Good thing eventually happens"
    
    Args:
        goal: Predicate that should eventually hold
        description: Description
        
    Returns:
        Eventually formula
    """
    prop = AtomicProp(goal, description)
    return Eventually(prop)


def response_property(
    trigger: Callable[[Dict], bool],
    response: Callable[[Dict], bool],
    trigger_desc: str = "",
    response_desc: str = ""
) -> TemporalFormula:
    """
    Create response property: □(φ → ◇ψ)
    
    "Whenever trigger happens, response eventually follows"
    
    Args:
        trigger: Trigger condition
        response: Response condition
        trigger_desc: Trigger description
        response_desc: Response description
        
    Returns:
        Response formula
    """
    trigger_prop = AtomicProp(trigger, trigger_desc)
    response_prop = AtomicProp(response, response_desc)
    
    # φ → ◇ψ
    implication = Implies(trigger_prop, Eventually(response_prop))
    
    # □(φ → ◇ψ)
    return Always(implication)


def stability_property(
    condition: Callable[[Dict], bool],
    description: str = ""
) -> TemporalFormula:
    """
    Create stability property: ◇□φ
    
    "Eventually, condition becomes and stays true"
    
    Args:
        condition: Condition that should stabilize
        description: Description
        
    Returns:
        Stability formula
    """
    prop = AtomicProp(condition, description)
    return Eventually(Always(prop))


# ============================================================================
# TRACE CHECKER
# ============================================================================

class TemporalChecker:
    """
    Temporal logic trace checker.
    
    Checks if traces satisfy temporal formulas.
    """
    
    def __init__(self):
        """Initialize checker"""
        pass
    
    def check(self, trace: Trace, formula: TemporalFormula) -> bool:
        """
        Check if trace satisfies formula.
        
        Args:
            trace: Execution trace
            formula: Temporal formula
            
        Returns:
            True if trace satisfies formula
        """
        return formula.evaluate(trace, 0)
    
    def find_counterexample(
        self,
        trace: Trace,
        formula: TemporalFormula
    ) -> Optional[int]:
        """
        Find first position where formula fails.
        
        Args:
            trace: Execution trace
            formula: Temporal formula
            
        Returns:
            Index of counterexample, or None if formula holds
        """
        # For safety properties (□φ), find first violation
        if isinstance(formula, Always):
            inner = formula.formula
            for i in range(len(trace)):
                if not inner.evaluate(trace, i):
                    return i
            return None
        
        # For general formulas, check at start
        if not formula.evaluate(trace, 0):
            return 0
        
        return None
    
    def check_all(
        self,
        trace: Trace,
        formulas: List[TemporalFormula]
    ) -> Dict[str, bool]:
        """
        Check multiple formulas on trace.
        
        Args:
            trace: Execution trace
            formulas: List of formulas
            
        Returns:
            Dictionary of {formula_str: result}
        """
        results = {}
        for formula in formulas:
            results[formula.to_string()] = self.check(trace, formula)
        return results


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_trace_from_states(state_dicts: List[Dict[str, Any]]) -> Trace:
    """
    Create trace from list of state dictionaries.
    
    Args:
        state_dicts: List of state variable dictionaries
        
    Returns:
        Trace
    """
    states = [State(variables=s, timestamp=i) for i, s in enumerate(state_dicts)]
    return Trace(states)


# ============================================================================
# EXAMPLES
# ============================================================================

def example_safety():
    """Example: Safety property"""
    print("=== Safety Property Example ===")
    
    # Property: balance should never be negative
    prop = safety_property(
        lambda s: s.get("balance", 0) >= 0,
        "balance >= 0"
    )
    
    # Trace 1: Valid
    trace1 = create_trace_from_states([
        {"balance": 100},
        {"balance": 80},
        {"balance": 60},
        {"balance": 40}
    ])
    
    # Trace 2: Invalid (goes negative)
    trace2 = create_trace_from_states([
        {"balance": 100},
        {"balance": 50},
        {"balance": -10},  # Violation!
        {"balance": 20}
    ])
    
    checker = TemporalChecker()
    
    print(f"Property: {prop}")
    print(f"\nTrace 1 (valid): {checker.check(trace1, prop)}")
    print(f"Trace 2 (invalid): {checker.check(trace2, prop)}")
    
    violation = checker.find_counterexample(trace2, prop)
    if violation is not None:
        print(f"Violation at index {violation}: {trace2[violation].variables}")
    
    return checker


def example_liveness():
    """Example: Liveness property"""
    print("\n=== Liveness Property Example ===")
    
    # Property: Eventually reach goal state
    prop = liveness_property(
        lambda s: s.get("status") == "completed",
        "status = completed"
    )
    
    # Trace 1: Eventually reaches goal
    trace1 = create_trace_from_states([
        {"status": "pending"},
        {"status": "processing"},
        {"status": "completed"}
    ])
    
    # Trace 2: Never reaches goal
    trace2 = create_trace_from_states([
        {"status": "pending"},
        {"status": "processing"},
        {"status": "failed"}
    ])
    
    checker = TemporalChecker()
    
    print(f"Property: {prop}")
    print(f"\nTrace 1 (reaches goal): {checker.check(trace1, prop)}")
    print(f"Trace 2 (fails): {checker.check(trace2, prop)}")
    
    return checker


def example_response():
    """Example: Response property"""
    print("\n=== Response Property Example ===")
    
    # Property: If alarm triggered, response follows
    prop = response_property(
        lambda s: s.get("alarm") == True,
        lambda s: s.get("handled") == True,
        "alarm triggered",
        "handled"
    )
    
    # Trace 1: Response follows
    trace1 = create_trace_from_states([
        {"alarm": False, "handled": False},
        {"alarm": True, "handled": False},
        {"alarm": True, "handled": True}
    ])
    
    # Trace 2: No response
    trace2 = create_trace_from_states([
        {"alarm": False, "handled": False},
        {"alarm": True, "handled": False},
        {"alarm": True, "handled": False}
    ])
    
    checker = TemporalChecker()
    
    print(f"Property: {prop}")
    print(f"\nTrace 1 (responds): {checker.check(trace1, prop)}")
    print(f"Trace 2 (no response): {checker.check(trace2, prop)}")
    
    return checker


if __name__ == "__main__":
    c1 = example_safety()
    c2 = example_liveness()
    c3 = example_response()
    
    print("\n=== Complex Formula Example ===")
    
    # □(price < 50000 → ◇(action = HOLD))
    # "If price drops below 50000, eventually action is HOLD"
    
    price_low = AtomicProp(lambda s: s.get("price", 100000) < 50000, "price < 50000")
    action_hold = AtomicProp(lambda s: s.get("action") == "HOLD", "action = HOLD")
    
    formula = Always(Implies(price_low, Eventually(action_hold)))
    
    trace = create_trace_from_states([
        {"price": 55000, "action": "BUY"},
        {"price": 48000, "action": "BUY"},   # Trigger
        {"price": 47000, "action": "SELL"},
        {"price": 46000, "action": "HOLD"}   # Response
    ])
    
    checker = TemporalChecker()
    result = checker.check(trace, formula)
    
    print(f"Formula: {formula}")
    print(f"Result: {result}")
