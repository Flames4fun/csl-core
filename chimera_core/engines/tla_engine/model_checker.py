"""
Model Checker - TLC Integration

Mock TLC (TLA+ model checker) interface for V0.1.
V0.5 will integrate real TLC via subprocess.

Provides:
- Model checking simulation
- State space exploration
- Property verification
- Counterexample generation

Based on:
- Lamport's TLC model checker
- Yu, Y., et al. (1999). Model checking TLA+ specifications
"""

from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass
from enum import Enum
import random


# ============================================================================
# ENUMS
# ============================================================================

class CheckResult(Enum):
    """Model checking results"""
    VALID = "valid"                 # Property holds
    VIOLATED = "violated"           # Property violated
    UNKNOWN = "unknown"             # Cannot determine
    TIMEOUT = "timeout"             # Exceeded time limit
    ERROR = "error"                 # Checking error


class ExplorationStrategy(Enum):
    """State space exploration strategies"""
    BFS = "bfs"                     # Breadth-first
    DFS = "dfs"                     # Depth-first
    RANDOM = "random"               # Random
    BOUNDED = "bounded"             # Bounded (depth limit)


# ============================================================================
# MODEL CHECKING RESULTS
# ============================================================================

@dataclass
class CounterExample:
    """
    Counterexample trace.
    
    Shows sequence of states leading to property violation.
    """
    states: List[Dict[str, Any]]
    violation_index: int
    property_name: str
    
    def __repr__(self):
        return f"CounterExample({len(self.states)} states, violation at {self.violation_index})"
    
    def format(self) -> str:
        """Format counterexample for display"""
        lines = [f"Counterexample for {self.property_name}:"]
        
        for i, state in enumerate(self.states):
            marker = " <--- VIOLATION" if i == self.violation_index else ""
            lines.append(f"  State {i}: {state}{marker}")
        
        return "\n".join(lines)


@dataclass
class ModelCheckingResult:
    """Result of model checking"""
    result: CheckResult
    property_name: str
    states_explored: int
    time_ms: int
    
    # If violated
    counterexample: Optional[CounterExample] = None
    
    # Statistics
    deadlocks_found: int = 0
    max_depth_reached: int = 0
    
    def __repr__(self):
        status = "✓ VALID" if self.result == CheckResult.VALID else "✗ VIOLATED"
        return (
            f"ModelCheckingResult({status}, "
            f"{self.states_explored} states, "
            f"{self.time_ms}ms)"
        )


# ============================================================================
# STATE SPACE REPRESENTATION
# ============================================================================

class State:
    """Single state in state space"""
    
    def __init__(self, variables: Dict[str, Any], state_id: int = 0):
        """
        Initialize state.
        
        Args:
            variables: State variables
            state_id: Unique state ID
        """
        self.variables = variables
        self.state_id = state_id
    
    def __getitem__(self, key: str) -> Any:
        return self.variables.get(key)
    
    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return self.variables == other.variables
    
    def __hash__(self):
        # Hash based on sorted variable items
        items = tuple(sorted(self.variables.items()))
        return hash(items)
    
    def copy(self) -> 'State':
        """Create copy of state"""
        return State(self.variables.copy(), self.state_id)


class StateSpace:
    """
    State space for model checking.
    
    Manages states and transitions.
    """
    
    def __init__(self, initial_state: State):
        """
        Initialize state space.
        
        Args:
            initial_state: Initial state
        """
        self.initial = initial_state
        self.states: Set[State] = {initial_state}
        self.transitions: Dict[int, List[int]] = {}
        self.next_id = 1
    
    def add_state(self, state: State) -> int:
        """
        Add state to space.
        
        Returns:
            State ID
        """
        if state not in self.states:
            state.state_id = self.next_id
            self.next_id += 1
            self.states.add(state)
            return state.state_id
        else:
            # Find existing state
            for s in self.states:
                if s == state:
                    return s.state_id
            return -1
    
    def add_transition(self, from_id: int, to_id: int):
        """Add transition between states"""
        if from_id not in self.transitions:
            self.transitions[from_id] = []
        self.transitions[from_id].append(to_id)
    
    def get_successors(self, state_id: int) -> List[int]:
        """Get successor state IDs"""
        return self.transitions.get(state_id, [])


# ============================================================================
# MOCK MODEL CHECKER
# ============================================================================

class MockModelChecker:
    """
    Mock TLC model checker.
    
    Simulates model checking for V0.1.
    V0.5 will use real TLC.
    
    Capabilities:
    - Safety property checking (invariants)
    - Liveness property checking (basic)
    - Counterexample generation
    - State space exploration
    """
    
    def __init__(
        self,
        max_states: int = 10000,
        max_depth: int = 100,
        strategy: ExplorationStrategy = ExplorationStrategy.BFS
    ):
        """
        Initialize model checker.
        
        Args:
            max_states: Maximum states to explore
            max_depth: Maximum search depth
            strategy: Exploration strategy
        """
        self.max_states = max_states
        self.max_depth = max_depth
        self.strategy = strategy
        
        self.states_explored = 0
        self.time_ms = 0
    
    def check_safety(
        self,
        initial_state: State,
        next_state_func: Callable[[State], List[State]],
        invariant: Callable[[State], bool],
        property_name: str = "Safety"
    ) -> ModelCheckingResult:
        """
        Check safety property (invariant).
        
        Explores state space and checks if invariant holds in all states.
        
        Args:
            initial_state: Initial state
            next_state_func: Function that generates next states
            invariant: Invariant predicate
            property_name: Property name
            
        Returns:
            ModelCheckingResult
        """
        import time
        start_time = time.time()
        
        # Initialize
        state_space = StateSpace(initial_state)
        visited: Set[State] = set()
        queue = [initial_state]
        
        self.states_explored = 0
        trace = []
        
        # BFS exploration
        while queue and self.states_explored < self.max_states:
            current = queue.pop(0)
            
            if current in visited:
                continue
            
            visited.add(current)
            self.states_explored += 1
            trace.append(current.variables.copy())
            
            # Check invariant
            if not invariant(current):
                # Violation found!
                counterexample = CounterExample(
                    states=trace,
                    violation_index=len(trace) - 1,
                    property_name=property_name
                )
                
                self.time_ms = int((time.time() - start_time) * 1000)
                
                return ModelCheckingResult(
                    result=CheckResult.VIOLATED,
                    property_name=property_name,
                    states_explored=self.states_explored,
                    time_ms=self.time_ms,
                    counterexample=counterexample
                )
            
            # Generate successors
            if len(trace) < self.max_depth:
                successors = next_state_func(current)
                for succ in successors:
                    if succ not in visited:
                        queue.append(succ)
                        state_space.add_state(succ)
        
        # No violation found
        self.time_ms = int((time.time() - start_time) * 1000)
        
        return ModelCheckingResult(
            result=CheckResult.VALID,
            property_name=property_name,
            states_explored=self.states_explored,
            time_ms=self.time_ms,
            max_depth_reached=len(trace)
        )
    
    def check_liveness(
        self,
        initial_state: State,
        next_state_func: Callable[[State], List[State]],
        goal: Callable[[State], bool],
        property_name: str = "Liveness"
    ) -> ModelCheckingResult:
        """
        Check liveness property (eventually goal).
        
        Simplified: checks if goal is reachable.
        
        Args:
            initial_state: Initial state
            next_state_func: Next state function
            goal: Goal predicate
            property_name: Property name
            
        Returns:
            ModelCheckingResult
        """
        import time
        start_time = time.time()
        
        visited: Set[State] = set()
        queue = [initial_state]
        
        self.states_explored = 0
        goal_reached = False
        
        while queue and self.states_explored < self.max_states:
            current = queue.pop(0)
            
            if current in visited:
                continue
            
            visited.add(current)
            self.states_explored += 1
            
            # Check if goal reached
            if goal(current):
                goal_reached = True
                break
            
            # Generate successors
            successors = next_state_func(current)
            for succ in successors:
                if succ not in visited:
                    queue.append(succ)
        
        self.time_ms = int((time.time() - start_time) * 1000)
        
        if goal_reached:
            return ModelCheckingResult(
                result=CheckResult.VALID,
                property_name=property_name,
                states_explored=self.states_explored,
                time_ms=self.time_ms
            )
        else:
            return ModelCheckingResult(
                result=CheckResult.VIOLATED,
                property_name=property_name,
                states_explored=self.states_explored,
                time_ms=self.time_ms
            )
    
    def check_deadlock_freedom(
        self,
        initial_state: State,
        next_state_func: Callable[[State], List[State]]
    ) -> ModelCheckingResult:
        """
        Check for deadlocks.
        
        Deadlock: state with no successors.
        
        Args:
            initial_state: Initial state
            next_state_func: Next state function
            
        Returns:
            ModelCheckingResult
        """
        import time
        start_time = time.time()
        
        visited: Set[State] = set()
        queue = [initial_state]
        
        self.states_explored = 0
        deadlocks = 0
        
        while queue and self.states_explored < self.max_states:
            current = queue.pop(0)
            
            if current in visited:
                continue
            
            visited.add(current)
            self.states_explored += 1
            
            # Check for deadlock
            successors = next_state_func(current)
            if not successors:
                deadlocks += 1
            
            for succ in successors:
                if succ not in visited:
                    queue.append(succ)
        
        self.time_ms = int((time.time() - start_time) * 1000)
        
        if deadlocks == 0:
            return ModelCheckingResult(
                result=CheckResult.VALID,
                property_name="DeadlockFreedom",
                states_explored=self.states_explored,
                time_ms=self.time_ms,
                deadlocks_found=0
            )
        else:
            return ModelCheckingResult(
                result=CheckResult.VIOLATED,
                property_name="DeadlockFreedom",
                states_explored=self.states_explored,
                time_ms=self.time_ms,
                deadlocks_found=deadlocks
            )


# ============================================================================
# TLC SUBPROCESS INTERFACE (V0.5)
# ============================================================================

class TLCInterface:
    """
    Interface to real TLC model checker.
    
    V0.1: Placeholder
    V0.5: Subprocess execution of TLC
    """
    
    def __init__(self, tlc_path: str = "tlc"):
        """
        Initialize TLC interface.
        
        Args:
            tlc_path: Path to TLC executable
        """
        self.tlc_path = tlc_path
    
    def check_spec(
        self,
        tla_file: str,
        config_file: Optional[str] = None
    ) -> ModelCheckingResult:
        """
        Check TLA+ specification using TLC.
        
        V0.5 implementation.
        
        Args:
            tla_file: Path to .tla file
            config_file: Optional .cfg file
            
        Returns:
            ModelCheckingResult
        """
        raise NotImplementedError("TLC integration in V0.5")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_simple_checker(max_states: int = 1000) -> MockModelChecker:
    """Create simple model checker"""
    return MockModelChecker(max_states=max_states, max_depth=50)


# ============================================================================
# EXAMPLES
# ============================================================================

def example_counter_safety():
    """Example: Counter safety property"""
    print("=== Counter Safety Example ===")
    
    # Model: counter starts at 0, increments, max is 10
    initial = State({"counter": 0}, 0)
    
    def next_states(state: State) -> List[State]:
        """Generate next states"""
        counter = state["counter"]
        if counter < 10:
            return [State({"counter": counter + 1})]
        return []
    
    def invariant(state: State) -> bool:
        """Safety: counter <= 10"""
        return state["counter"] <= 10
    
    checker = MockModelChecker(max_states=100)
    result = checker.check_safety(initial, next_states, invariant, "CounterBounded")
    
    print(f"Result: {result}")
    print(f"States explored: {result.states_explored}")
    print(f"Time: {result.time_ms}ms")
    
    return result


def example_counter_liveness():
    """Example: Counter liveness property"""
    print("\n=== Counter Liveness Example ===")
    
    initial = State({"counter": 0}, 0)
    
    def next_states(state: State) -> List[State]:
        counter = state["counter"]
        if counter < 10:
            return [State({"counter": counter + 1})]
        return []
    
    def goal(state: State) -> bool:
        """Goal: eventually reach 10"""
        return state["counter"] == 10
    
    checker = MockModelChecker(max_states=100)
    result = checker.check_liveness(initial, next_states, goal, "EventuallyTen")
    
    print(f"Result: {result}")
    print(f"Goal reached: {result.result == CheckResult.VALID}")
    
    return result


def example_violation():
    """Example: Property violation"""
    print("\n=== Violation Example ===")
    
    # Balance that can go negative
    initial = State({"balance": 100}, 0)
    
    def next_states(state: State) -> List[State]:
        balance = state["balance"]
        # Withdraw 30 each time
        return [State({"balance": balance - 30})]
    
    def invariant(state: State) -> bool:
        """Safety: balance >= 0"""
        return state["balance"] >= 0
    
    checker = MockModelChecker(max_states=10)
    result = checker.check_safety(initial, next_states, invariant, "NonNegativeBalance")
    
    print(f"Result: {result}")
    
    if result.counterexample:
        print("\n" + result.counterexample.format())
    
    return result


def example_trading_safety():
    """Example: Trading bot safety"""
    print("\n=== Trading Safety Example ===")
    
    initial = State({
        "price": 50000,
        "position": 0,
        "balance": 100000,
        "action": "HOLD"
    }, 0)
    
    def next_states(state: State) -> List[State]:
        """Trading actions"""
        price = state["price"]
        position = state["position"]
        balance = state["balance"]
        
        states = []
        
        # Price can change
        states.append(State({
            "price": price * 0.95,  # Drop
            "position": position,
            "balance": balance,
            "action": "HOLD"
        }))
        
        # Can buy
        if balance >= price:
            states.append(State({
                "price": price,
                "position": position + 1,
                "balance": balance - price,
                "action": "BUY"
            }))
        
        # Can sell
        if position > 0:
            states.append(State({
                "price": price,
                "position": position - 1,
                "balance": balance + price,
                "action": "SELL"
            }))
        
        return states[:2]  # Limit branching
    
    def invariant(state: State) -> bool:
        """Safety: no panic selling on drop"""
        # If price dropped significantly, should not SELL
        price = state["price"]
        action = state["action"]
        
        if price < 47500:  # 5% drop
            return action != "SELL"
        
        return True
    
    checker = MockModelChecker(max_states=100)
    result = checker.check_safety(initial, next_states, invariant, "NoPanicSell")
    
    print(f"Result: {result}")
    
    if result.counterexample:
        print("\n" + result.counterexample.format())
    
    return result


if __name__ == "__main__":
    r1 = example_counter_safety()
    r2 = example_counter_liveness()
    r3 = example_violation()
    r4 = example_trading_safety()
    
    print("\n=== Summary ===")
    print(f"Counter safety: {r1.result.value}")
    print(f"Counter liveness: {r2.result.value}")
    print(f"Violation detection: {r3.result.value}")
    print(f"Trading safety: {r4.result.value}")
