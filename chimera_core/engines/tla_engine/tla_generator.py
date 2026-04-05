"""
TLA+ Specification Generator

Generates TLA+ specifications from CSL constraints.
TLA+ is Lamport's Temporal Logic of Actions specification language.

Features:
- CSL → TLA+ translation
- Temporal property generation
- State space specification
- Invariant/safety property encoding

Based on:
- Lamport, L. (2002). Specifying Systems: The TLA+ Language and Tools
- Lamport, L. (1994). The Temporal Logic of Actions

Note: V0.1 generates basic TLA+. V0.5 will add full TLC integration.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# TLA+ ELEMENTS
# ============================================================================

class TLAOperator(Enum):
    """TLA+ temporal operators"""
    ALWAYS = "[]"           # □ - Always/Globally
    EVENTUALLY = "<>"       # ◇ - Eventually/Finally
    NEXT = "'"             # Prime - Next state
    ENABLED = "ENABLED"     # Action enablement
    UNCHANGED = "UNCHANGED" # Variables unchanged
    
    # Actions
    INIT = "Init"
    NEXT_ACTION = "Next"
    SPEC = "Spec"
    
    # Logic
    AND = "/\\"
    OR = "\\/"
    NOT = "~"
    IMPLIES = "=>"
    EQUIV = "<=>"
    
    # Quantifiers
    FORALL = "\\A"
    EXISTS = "\\E"


@dataclass
class TLAVariable:
    """TLA+ variable"""
    name: str
    type_annotation: Optional[str] = None
    initial_value: Optional[Any] = None
    
    def declare(self) -> str:
        """Generate variable declaration"""
        return f"VARIABLE {self.name}"
    
    def __repr__(self):
        return self.name


@dataclass
class TLAConstant:
    """TLA+ constant"""
    name: str
    type_annotation: Optional[str] = None
    
    def declare(self) -> str:
        """Generate constant declaration"""
        return f"CONSTANT {self.name}"


# ============================================================================
# TLA+ SPECIFICATION BUILDER
# ============================================================================

class TLASpec:
    """
    TLA+ Specification.
    
    Structure:
    - MODULE name
    - EXTENDS (standard modules)
    - CONSTANTS
    - VARIABLES
    - Init (initial state predicate)
    - Next (next-state relation)
    - Spec (temporal formula)
    - Properties (invariants, liveness)
    """
    
    def __init__(self, module_name: str):
        """
        Initialize TLA+ spec.
        
        Args:
            module_name: Module name
        """
        self.module_name = module_name
        self.extends: List[str] = ["Naturals", "Integers", "Sequences"]
        self.constants: List[TLAConstant] = []
        self.variables: List[TLAVariable] = []
        self.init_predicates: List[str] = []
        self.next_actions: List[str] = []
        self.invariants: List[str] = []
        self.properties: List[str] = []
        
        # Additional definitions
        self.definitions: List[str] = []
    
    def add_constant(self, name: str, type_annotation: Optional[str] = None):
        """Add constant"""
        self.constants.append(TLAConstant(name, type_annotation))
    
    def add_variable(self, name: str, type_annotation: Optional[str] = None, initial: Any = None):
        """Add variable"""
        self.variables.append(TLAVariable(name, type_annotation, initial))
    
    def add_init_predicate(self, predicate: str):
        """Add initial state predicate"""
        self.init_predicates.append(predicate)
    
    def add_next_action(self, action: str):
        """Add next-state action"""
        self.next_actions.append(action)
    
    def add_invariant(self, name: str, formula: str):
        """Add invariant (safety property)"""
        self.invariants.append(f"{name} == {formula}")
    
    def add_property(self, name: str, formula: str):
        """Add temporal property"""
        self.properties.append(f"{name} == {formula}")
    
    def add_definition(self, definition: str):
        """Add custom definition"""
        self.definitions.append(definition)
    
    def generate(self) -> str:
        """
        Generate complete TLA+ specification.
        
        Returns:
            TLA+ spec as string
        """
        lines = []
        
        # Module declaration
        lines.append(f"---- MODULE {self.module_name} ----")
        lines.append("")
        
        # EXTENDS
        if self.extends:
            lines.append(f"EXTENDS {', '.join(self.extends)}")
            lines.append("")
        
        # CONSTANTS
        if self.constants:
            for const in self.constants:
                lines.append(const.declare())
            lines.append("")
        
        # VARIABLES
        if self.variables:
            vars_str = ", ".join(v.name for v in self.variables)
            lines.append(f"VARIABLES {vars_str}")
            lines.append("")
        
        # Custom definitions
        if self.definitions:
            for defn in self.definitions:
                lines.append(defn)
            lines.append("")
        
        # Init
        lines.append("Init ==")
        if self.init_predicates:
            for i, pred in enumerate(self.init_predicates):
                prefix = "  /\\ " if i > 0 else "  "
                lines.append(f"{prefix}{pred}")
        else:
            lines.append("  TRUE")
        lines.append("")
        
        # Next
        lines.append("Next ==")
        if self.next_actions:
            for i, action in enumerate(self.next_actions):
                prefix = "  \\/ " if i > 0 else "  "
                lines.append(f"{prefix}{action}")
        else:
            lines.append("  TRUE")
        lines.append("")
        
        # Spec (temporal formula)
        lines.append("Spec == Init /\\ [][Next]_<<" + ", ".join(v.name for v in self.variables) + ">>")
        lines.append("")
        
        # Invariants
        if self.invariants:
            lines.append("\\* Invariants")
            for inv in self.invariants:
                lines.append(inv)
            lines.append("")
        
        # Properties
        if self.properties:
            lines.append("\\* Temporal Properties")
            for prop in self.properties:
                lines.append(prop)
            lines.append("")
        
        # Module end
        lines.append("====")
        
        return "\n".join(lines)


# ============================================================================
# CSL → TLA+ TRANSLATOR
# ============================================================================

class CSLToTLATranslator:
    """
    Translate CSL constraints to TLA+ specifications.
    
    Maps:
    - CSL variables → TLA+ VARIABLES
    - CSL constraints → TLA+ invariants/properties
    - Causal graph → State transitions
    """
    
    def __init__(self):
        """Initialize translator"""
        self.spec: Optional[TLASpec] = None
        self.variable_domains: Dict[str, str] = {}
    
    def translate_constraint(
        self,
        constraint_name: str,
        condition: str,
        action: str,
        variables: Set[str]
    ) -> TLASpec:
        """
        Translate CSL constraint to TLA+ spec.
        
        Args:
            constraint_name: Name of constraint
            condition: WHEN condition
            action: THEN action
            variables: Variables involved
            
        Returns:
            TLA+ specification
        """
        spec = TLASpec(constraint_name)
        
        # Add variables
        for var in variables:
            spec.add_variable(var)
        
        # Convert condition to TLA+ invariant
        # Simplified: CSL "WHEN X THEN Y" → TLA+ "[] (X => Y)"
        
        # Initial state (unconstrained)
        spec.add_init_predicate("TRUE")
        
        # Next state (action can occur)
        spec.add_next_action("TRUE")
        
        # Safety property: WHEN condition holds, action constraint must hold
        tla_condition = self._csl_to_tla_expr(condition)
        tla_action = self._csl_to_tla_expr(action)
        
        invariant_formula = f"[](({tla_condition}) => ({tla_action}))"
        spec.add_invariant(f"{constraint_name}Safety", invariant_formula)
        
        self.spec = spec
        return spec
    
    def translate_constitution(
        self,
        domain_name: str,
        constraints: List[Dict[str, Any]],
        causal_graph: Optional[Dict[str, List[str]]] = None
    ) -> TLASpec:
        """
        Translate full constitution to TLA+ spec.
        
        Args:
            domain_name: Domain name
            constraints: List of constraints
            causal_graph: Optional causal graph
            
        Returns:
            TLA+ specification
        """
        spec = TLASpec(domain_name)
        
        # Extract all variables
        all_vars = set()
        for constraint in constraints:
            all_vars.update(constraint.get("variables", []))
        
        # Add variables
        for var in all_vars:
            spec.add_variable(var)
        
        # Initial state
        spec.add_init_predicate("TRUE")  # Simplified
        
        # Next state actions
        if causal_graph:
            # Generate actions based on causal structure
            for child, parents in causal_graph.items():
                if parents:
                    parent_str = " /\\ ".join(f"{p}' = {p}" for p in parents)
                    action = f"({parent_str}) /\\ {child}' \\in Domain_{child}"
                else:
                    action = f"{child}' \\in Domain_{child}"
                spec.add_next_action(action)
        else:
            spec.add_next_action("TRUE")
        
        # Add constraints as invariants
        for i, constraint in enumerate(constraints):
            name = constraint.get("name", f"Constraint{i}")
            condition = constraint.get("condition", "TRUE")
            action = constraint.get("action", "TRUE")
            
            tla_cond = self._csl_to_tla_expr(condition)
            tla_act = self._csl_to_tla_expr(action)
            
            formula = f"[](({tla_cond}) => ({tla_act}))"
            spec.add_invariant(name, formula)
        
        self.spec = spec
        return spec
    
    def _csl_to_tla_expr(self, csl_expr: str) -> str:
        """
        Convert CSL expression to TLA+ expression.
        
        Simplified for V0.1. V0.5 will use proper parser.
        
        Args:
            csl_expr: CSL expression
            
        Returns:
            TLA+ expression
        """
        # Basic conversions
        tla_expr = csl_expr
        
        # Operators
        tla_expr = tla_expr.replace(" AND ", " /\\ ")
        tla_expr = tla_expr.replace(" OR ", " \\/ ")
        tla_expr = tla_expr.replace(" NOT ", " ~ ")
        
        # Comparisons (keep as is)
        # <, >, <=, >=, =, != are same in TLA+
        tla_expr = tla_expr.replace("!=", "#")
        
        # String equality
        tla_expr = tla_expr.replace(' == ', ' = ')
        
        # Modal operators
        tla_expr = tla_expr.replace("MUST BE", "=")
        tla_expr = tla_expr.replace("MUST NOT BE", "#")
        
        return tla_expr


# ============================================================================
# TLA+ PROPERTY BUILDERS
# ============================================================================

def create_safety_property(variable: str, condition: str) -> str:
    """
    Create TLA+ safety property.
    
    Safety: []P (always P)
    
    Args:
        variable: Variable name
        condition: Condition
        
    Returns:
        TLA+ formula
    """
    return f"[]({variable} {condition})"


def create_liveness_property(variable: str, goal: str) -> str:
    """
    Create TLA+ liveness property.
    
    Liveness: <>P (eventually P)
    
    Args:
        variable: Variable name
        goal: Goal condition
        
    Returns:
        TLA+ formula
    """
    return f"<>({variable} {goal})"


def create_response_property(trigger: str, response: str) -> str:
    """
    Create TLA+ response property.
    
    Response: [](P => <>Q)
    
    Args:
        trigger: Trigger condition
        response: Response condition
        
    Returns:
        TLA+ formula
    """
    return f"[](({trigger}) => <>({response}))"


# ============================================================================
# EXAMPLES
# ============================================================================

def example_simple_constraint():
    """Example: Simple CSL constraint"""
    print("=== Simple Constraint Translation ===")
    
    translator = CSLToTLATranslator()
    
    # CSL: WHEN price < 50000 THEN action MUST NOT BE "SELL"
    spec = translator.translate_constraint(
        constraint_name="NoPanicSell",
        condition="price < 50000",
        action="action # \"SELL\"",
        variables={"price", "action"}
    )
    
    tla_code = spec.generate()
    print(tla_code)
    
    return spec


def example_trading_constitution():
    """Example: Trading constitution"""
    print("\n=== Trading Constitution ===")
    
    translator = CSLToTLATranslator()
    
    constraints = [
        {
            "name": "NoSellOnDrop",
            "variables": ["price_change", "action"],
            "condition": "price_change < -0.05",
            "action": "action # \"SELL\""
        },
        {
            "name": "MaxPositionSize",
            "variables": ["position", "max_position"],
            "condition": "TRUE",
            "action": "position <= max_position"
        }
    ]
    
    causal_graph = {
        "price_change": [],
        "action": ["price_change"],
        "position": ["action"]
    }
    
    spec = translator.translate_constitution(
        domain_name="TradingBot",
        constraints=constraints,
        causal_graph=causal_graph
    )
    
    tla_code = spec.generate()
    print(tla_code)
    
    return spec


def example_custom_spec():
    """Example: Custom TLA+ spec"""
    print("\n=== Custom TLA+ Specification ===")
    
    spec = TLASpec("Counter")
    
    # Variables
    spec.add_variable("counter", "Nat", 0)
    spec.add_constant("MAX", "Nat")
    
    # Initial state
    spec.add_init_predicate("counter = 0")
    
    # Next state actions
    spec.add_next_action("counter' = counter + 1 /\\ counter < MAX")
    spec.add_next_action("counter' = 0 /\\ counter >= MAX")
    
    # Invariants
    spec.add_invariant("TypeInvariant", "counter \\in Nat")
    spec.add_invariant("BoundedCounter", "[](counter <= MAX)")
    
    # Liveness
    spec.add_property("EventuallyMax", "<>(counter = MAX)")
    
    tla_code = spec.generate()
    print(tla_code)
    
    return spec


if __name__ == "__main__":
    spec1 = example_simple_constraint()
    spec2 = example_trading_constitution()
    spec3 = example_custom_spec()
    
    print("\n=== Property Builders ===")
    
    safety = create_safety_property("balance", ">= 0")
    print(f"Safety: {safety}")
    
    liveness = create_liveness_property("status", "= \"completed\"")
    print(f"Liveness: {liveness}")
    
    response = create_response_property("alarm = TRUE", "handled = TRUE")
    print(f"Response: {response}")
