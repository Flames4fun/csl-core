# Contributing to CSL-Core 🛡️

First off, thank you for considering contributing to CSL-Core! 

CSL-Core is building the deterministic safety layer for AI agents. Whether you are writing a simple safety policy, fixing a bug, or building a new framework integration, your contribution helps make AI systems safer, verifiable, and mathematically sound.

We welcome contributions of all kinds. This document will help you get started quickly and smoothly.

> **Note:** By submitting a pull request, you agree that your contribution will be licensed under the [Apache 2.0 License](LICENSE).

> **Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.**

## 🧭 Table of Contents
1. [Where Can I Contribute?](#-where-can-i-contribute)
2. [Local Development Setup](#-local-development-setup)
3. [How to Contribute a New Policy](#-how-to-contribute-a-new-policy)
4. [Pull Request Process](#-pull-request-process)
5. [Community & Getting Help](#-community--getting-help)

---

## 🎯 Where Can I Contribute?

Not sure where to start? Check out our issue tracker and look for the `good first issue` or `help wanted` labels. Here are our highest impact areas right now:

### 1. Writing Policies (Great for Beginners!)
We are building a robust library of real-world safety policies (`.csl` files). You don't need to know Python to contribute here—just logic! We have open issues for various domains and use cases.

### 2. Tooling and Developer Experience
Any contribution that makes writing and testing CSL easier—like IDE support, syntax highlighting extensions, or CLI improvements—is a huge priority for us.

### 3. Framework Integrations
We currently support LangChain. Contributions integrating CSL-Core with other agentic frameworks (like LlamaIndex, AutoGen, or CrewAI) are highly welcomed.

---

## 💻 Local Development Setup

We want your onboarding to be as frictionless as possible. 

**Option A: Just writing policies?**
You can simply install the package via pip:

```bash
pip install csl-core
```

**Option B: Core development**
If you want to contribute to the core codebase, set it up locally:

1. **Fork and Clone the repository:**
First, click the **Fork** button at the top right of this page to create a copy in your own GitHub account. Then, clone your fork to your local machine:

```bash
git clone https://github.com/YOUR-USERNAME/csl-core.git
cd csl-core
```

2. **Create a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. **Install the package in editable mode with development dependencies:**

```bash
pip install -e .
```

- (If you are working on the MCP server features, use `pip install -e ".[mcp]"`)

4. **Run the test suite to verify everything works:**

```bash
pytest
```

---

## 🛡️ How to Contribute a New Policy

Writing a policy is the fastest way to get your first PR merged. Here is the exact workflow:

**Step 1: Write your policy**
Pick an open policy issue (or invent your own) and create a new `.csl` file in the `examples/community/` directory.

Follow this naming convention: `domain_usecase_guard.csl`

Examples:
- `healthcare_dosage_guard.csl`
- `defi_slippage_guard.csl`
- `devops_friday_deploy_guard.csl`
- `ecommerce_margin_guard.csl`

**Step 2: Verify the mathematics**
CSL-Core uses the Z3 Theorem Prover. Before testing, ensure your logic has no contradictions by running the compiler:

```bash    
cslcore verify your_policy.csl
```

If you see `✅`, you're good to go!

**Step 3: Simulate scenarios**
Prove that your policy works by simulating both an ALLOWED and a BLOCKED scenario using the CLI:
  
```bash  
# This should be ALLOWED
cslcore simulate your_policy.csl --input '{"action": "VALID_ACTION", "amount": 50}'

# This should be BLOCKED
cslcore simulate your_policy.csl --input '{"action": "INVALID_ACTION", "amount": 99999}'
```

- (Tip: You can also use the interactive REPL by typing `cslcore repl your_policy.csl`)

**Step 4: Submit!**
Your PR must include:
- The `.csl` policy file in `examples/community/`
- At least one ALLOWED input example
- At least one BLOCKED input example
- A brief description of what the policy protects against
- Reference to the issue it closes (e.g., `Closes #12`)

---

## 🚀 Pull Request Process

1. **Branch Naming:** Use clear branch names like `feature/new-integration`, `policy/industry-guard`, or `fix/cli-typo`.
2. **Drafting the PR:** Keep your PRs focused. If you are solving a specific issue, mention it in the description (e.g., `Closes #12`).
3. **Tests:** If you are modifying the Python core or CLI, please ensure existing tests pass (`pytest`) and add new ones if applicable.
4. **Review:** Maintainers will review your PR. We might request changes, but we will always be constructive and helpful!

---

## 💬 Community & Getting Help

Stuck on a Z3 verification error? Unsure about the syntax? Don't hesitate to reach out!
* **Discussions:** Open a thread in our [GitHub Discussions](https://github.com/Chimera-Protocol/csl-core/discussions).
* **Issues:** For bug reports and feature requests.

Thank you for helping us build a safer AI ecosystem!
