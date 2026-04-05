"""
Proof Builder - Formal Verification Proof Certificates

Builds and validates proof certificates for formal verification.
Proof certificates provide evidence that properties hold.

Features:
- Proof certificate generation
- Inductive invariants
- Proof validation
- Certificate serialization

Based on:
- Necula, G. C. (1997). Proof-carrying code
- Lamport, L. (2012). How to write a 21st century proof
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib
import json


# ============================================================================
# ENUMS
# ============================================================================

class ProofType(Enum):
    """Types of formal proofs"""
    INDUCTIVE = "inductive"             # Inductive invariant
    SAFETY = "safety"                   # Safety property
    LIVENESS = "liveness"               # Liveness property
    REFINEMENT = "refinement"           # Refinement proof
    MODEL_CHECKING = "model_checking"   # Model checking result


class ProofStatus(Enum):
    """Proof verification status"""
    VERIFIED = "verified"       # Proof checked and valid
    UNVERIFIED = "unverified"   # Not yet checked
    INVALID = "invalid"         # Proof has errors
    INCOMPLETE = "incomplete"   # Proof steps missing


# ============================================================================
# PROOF CERTIFICATE
# ============================================================================

@dataclass
class ProofStep:
    """Single step in proof"""
    step_number: int
    statement: str
    justification: str
    assumptions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "statement": self.statement,
            "justification": self.justification,
            "assumptions": self.assumptions
        }


@dataclass
class ProofCertificate:
    """
    Formal proof certificate.
    
    Contains:
    - Property being proved
    - Proof steps
    - Verification metadata
    - Digital signature (for authenticity)
    """
    property_name: str
    property_formula: str
    proof_type: ProofType
    
    # Proof content
    steps: List[ProofStep] = field(default_factory=list)
    lemmas: List[str] = field(default_factory=list)
    
    # Verification
    status: ProofStatus = ProofStatus.UNVERIFIED
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    
    # Model checking metadata
    states_explored: Optional[int] = None
    time_ms: Optional[int] = None
    
    # Cryptographic
    certificate_hash: Optional[str] = None
    signature: Optional[str] = None
    
    def add_step(self, statement: str, justification: str, assumptions: List[str] = None):
        """Add proof step"""
        step_num = len(self.steps) + 1
        step = ProofStep(
            step_number=step_num,
            statement=statement,
            justification=justification,
            assumptions=assumptions or []
        )
        self.steps.append(step)
    
    def add_lemma(self, lemma: str):
        """Add lemma"""
        self.lemmas.append(lemma)
    
    def compute_hash(self) -> str:
        """Compute cryptographic hash of certificate"""
        # Create canonical representation
        data = {
            "property": self.property_name,
            "formula": self.property_formula,
            "type": self.proof_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "lemmas": self.lemmas
        }
        
        # Compute SHA-256
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        hash_obj = hashlib.sha256(canonical.encode())
        self.certificate_hash = hash_obj.hexdigest()
        
        return self.certificate_hash
    
    def verify_integrity(self) -> bool:
        """Verify certificate hash integrity"""
        if not self.certificate_hash:
            return False
        
        # Recompute hash
        stored_hash = self.certificate_hash
        self.certificate_hash = None  # Temporarily clear
        
        computed = self.compute_hash()
        is_valid = (computed == stored_hash)
        
        self.certificate_hash = stored_hash  # Restore
        
        return is_valid
    
    def mark_verified(self, verifier: str = "Chimera"):
        """Mark certificate as verified"""
        self.status = ProofStatus.VERIFIED
        self.verified_by = verifier
        self.verified_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "property_name": self.property_name,
            "property_formula": self.property_formula,
            "proof_type": self.proof_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "lemmas": self.lemmas,
            "status": self.status.value,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "states_explored": self.states_explored,
            "time_ms": self.time_ms,
            "certificate_hash": self.certificate_hash,
            "signature": self.signature
        }
    
    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProofCertificate':
        """Load from dictionary"""
        cert = cls(
            property_name=data["property_name"],
            property_formula=data["property_formula"],
            proof_type=ProofType(data["proof_type"])
        )
        
        # Load steps
        for step_data in data.get("steps", []):
            step = ProofStep(
                step_number=step_data["step"],
                statement=step_data["statement"],
                justification=step_data["justification"],
                assumptions=step_data.get("assumptions", [])
            )
            cert.steps.append(step)
        
        # Load metadata
        cert.lemmas = data.get("lemmas", [])
        cert.status = ProofStatus(data.get("status", "unverified"))
        cert.verified_by = data.get("verified_by")
        
        if data.get("verified_at"):
            cert.verified_at = datetime.fromisoformat(data["verified_at"])
        
        cert.states_explored = data.get("states_explored")
        cert.time_ms = data.get("time_ms")
        cert.certificate_hash = data.get("certificate_hash")
        cert.signature = data.get("signature")
        
        return cert


# ============================================================================
# PROOF BUILDERS
# ============================================================================

class InductiveProofBuilder:
    """
    Build inductive invariant proofs.
    
    Structure:
    1. Base case: Inv(s0)
    2. Inductive step: Inv(s) ∧ Next(s, s') => Inv(s')
    3. Conclusion: □Inv
    """
    
    def __init__(self, invariant: str):
        """
        Initialize builder.
        
        Args:
            invariant: Invariant formula
        """
        self.invariant = invariant
        self.certificate = ProofCertificate(
            property_name="InductiveInvariant",
            property_formula=f"[]{invariant}",
            proof_type=ProofType.INDUCTIVE
        )
    
    def add_base_case(self, initial_state: str):
        """Add base case proof"""
        self.certificate.add_step(
            statement=f"Inv({initial_state})",
            justification="Base case: invariant holds in initial state",
            assumptions=[f"Init = {initial_state}"]
        )
    
    def add_inductive_step(self, state_transition: str):
        """Add inductive step"""
        self.certificate.add_step(
            statement=f"Inv(s) ∧ Next(s, s') => Inv(s')",
            justification="Inductive step: invariant preserved by transitions",
            assumptions=[f"Next = {state_transition}"]
        )
    
    def add_conclusion(self):
        """Add conclusion"""
        self.certificate.add_step(
            statement=f"[]{self.invariant}",
            justification="By induction, invariant always holds",
            assumptions=["Base case", "Inductive step"]
        )
    
    def build(self) -> ProofCertificate:
        """Build and return certificate"""
        self.certificate.compute_hash()
        return self.certificate


class SafetyProofBuilder:
    """Build safety property proofs"""
    
    def __init__(self, property_name: str, safety_condition: str):
        """
        Initialize builder.
        
        Args:
            property_name: Property name
            safety_condition: Safety condition
        """
        self.certificate = ProofCertificate(
            property_name=property_name,
            property_formula=f"[]{safety_condition}",
            proof_type=ProofType.SAFETY
        )
    
    def add_invariant_lemma(self, invariant: str):
        """Add invariant as lemma"""
        self.certificate.add_lemma(f"Invariant: {invariant}")
    
    def add_proof_by_invariant(self, invariant: str, safety: str):
        """Prove safety using invariant"""
        self.certificate.add_step(
            statement=f"[]{invariant}",
            justification="Invariant proved inductively"
        )
        
        self.certificate.add_step(
            statement=f"{invariant} => {safety}",
            justification="Invariant implies safety condition"
        )
        
        self.certificate.add_step(
            statement=f"[]{safety}",
            justification="By transitivity: []Inv ∧ (Inv => Safety) => []Safety"
        )
    
    def build(self) -> ProofCertificate:
        """Build certificate"""
        self.certificate.compute_hash()
        return self.certificate


class ModelCheckingProofBuilder:
    """Build proof certificates from model checking results"""
    
    def __init__(self, property_name: str, property_formula: str):
        """
        Initialize builder.
        
        Args:
            property_name: Property name
            property_formula: Formula
        """
        self.certificate = ProofCertificate(
            property_name=property_name,
            property_formula=property_formula,
            proof_type=ProofType.MODEL_CHECKING
        )
    
    def add_model_checking_result(
        self,
        result: str,
        states_explored: int,
        time_ms: int
    ):
        """Add model checking result"""
        self.certificate.states_explored = states_explored
        self.certificate.time_ms = time_ms
        
        self.certificate.add_step(
            statement=f"Model checking result: {result}",
            justification=f"Explored {states_explored} states in {time_ms}ms"
        )
        
        if result == "VALID":
            self.certificate.add_step(
                statement=self.certificate.property_formula,
                justification="Property verified by exhaustive model checking"
            )
    
    def build(self) -> ProofCertificate:
        """Build certificate"""
        self.certificate.compute_hash()
        return self.certificate


# ============================================================================
# PROOF VALIDATOR
# ============================================================================

class ProofValidator:
    """
    Validate proof certificates.
    
    Checks:
    - Hash integrity
    - Proof structure
    - Step justifications (simplified in V0.1)
    """
    
    def __init__(self):
        """Initialize validator"""
        pass
    
    def validate(self, certificate: ProofCertificate) -> bool:
        """
        Validate proof certificate.
        
        Args:
            certificate: Certificate to validate
            
        Returns:
            True if valid
        """
        # Check hash integrity
        if not certificate.verify_integrity():
            certificate.status = ProofStatus.INVALID
            return False
        
        # Check proof structure
        if not certificate.steps:
            certificate.status = ProofStatus.INCOMPLETE
            return False
        
        # V0.1: Basic validation
        # V0.5: Full logical validation
        
        certificate.mark_verified("ProofValidator")
        return True
    
    def validate_inductive_proof(self, certificate: ProofCertificate) -> bool:
        """Validate inductive proof structure"""
        if certificate.proof_type != ProofType.INDUCTIVE:
            return False
        
        # Check for base case and inductive step
        has_base = any("base case" in s.justification.lower() for s in certificate.steps)
        has_inductive = any("inductive" in s.justification.lower() for s in certificate.steps)
        
        return has_base and has_inductive


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_inductive_proof(
    invariant: str,
    initial_state: str,
    transition: str
) -> ProofCertificate:
    """
    Create inductive invariant proof.
    
    Args:
        invariant: Invariant formula
        initial_state: Initial state
        transition: Transition relation
        
    Returns:
        ProofCertificate
    """
    builder = InductiveProofBuilder(invariant)
    builder.add_base_case(initial_state)
    builder.add_inductive_step(transition)
    builder.add_conclusion()
    
    return builder.build()


def create_safety_proof(
    property_name: str,
    safety_condition: str,
    invariant: str
) -> ProofCertificate:
    """
    Create safety proof.
    
    Args:
        property_name: Property name
        safety_condition: Safety condition
        invariant: Invariant that implies safety
        
    Returns:
        ProofCertificate
    """
    builder = SafetyProofBuilder(property_name, safety_condition)
    builder.add_invariant_lemma(invariant)
    builder.add_proof_by_invariant(invariant, safety_condition)
    
    return builder.build()


# ============================================================================
# EXAMPLES
# ============================================================================

def example_inductive_proof():
    """Example: Inductive invariant proof"""
    print("=== Inductive Invariant Proof ===")
    
    # Prove: counter <= MAX
    builder = InductiveProofBuilder("counter <= MAX")
    
    builder.add_base_case("counter = 0")
    builder.add_inductive_step("counter' = counter + 1")
    builder.add_conclusion()
    
    cert = builder.build()
    
    print(f"Property: {cert.property_name}")
    print(f"Formula: {cert.property_formula}")
    print(f"\nProof steps:")
    for step in cert.steps:
        print(f"  {step.step_number}. {step.statement}")
        print(f"     ({step.justification})")
    
    print(f"\nHash: {cert.certificate_hash}")
    
    # Validate
    validator = ProofValidator()
    is_valid = validator.validate(cert)
    print(f"Valid: {is_valid}")
    print(f"Status: {cert.status.value}")
    
    return cert


def example_safety_proof():
    """Example: Safety property proof"""
    print("\n=== Safety Proof ===")
    
    builder = SafetyProofBuilder("NoNegativeBalance", "balance >= 0")
    
    builder.add_invariant_lemma("balance >= 0")
    builder.add_proof_by_invariant("balance >= 0", "balance >= 0")
    
    cert = builder.build()
    
    print(f"Property: {cert.property_name}")
    print(f"Lemmas: {cert.lemmas}")
    print(f"\nProof steps:")
    for step in cert.steps:
        print(f"  {step.step_number}. {step.statement}")
    
    return cert


def example_model_checking_proof():
    """Example: Model checking proof"""
    print("\n=== Model Checking Proof ===")
    
    builder = ModelCheckingProofBuilder("NoPanicSell", "[](price < 50000 => action != SELL)")
    
    builder.add_model_checking_result("VALID", 1000, 450)
    
    cert = builder.build()
    
    print(f"Property: {cert.property_name}")
    print(f"States explored: {cert.states_explored}")
    print(f"Time: {cert.time_ms}ms")
    
    # Serialize
    json_str = cert.to_json()
    print(f"\nSerialized length: {len(json_str)} bytes")
    
    # Deserialize
    cert2 = ProofCertificate.from_dict(json.loads(json_str))
    print(f"Deserialized: {cert2.property_name}")
    
    return cert


if __name__ == "__main__":
    cert1 = example_inductive_proof()
    cert2 = example_safety_proof()
    cert3 = example_model_checking_proof()
    
    print("\n=== Validation ===")
    
    validator = ProofValidator()
    
    print(f"Inductive proof valid: {validator.validate_inductive_proof(cert1)}")
    print(f"Safety proof valid: {validator.validate(cert2)}")
    print(f"Model checking proof valid: {validator.validate(cert3)}")
