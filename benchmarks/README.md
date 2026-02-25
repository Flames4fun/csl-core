# CSL-Bench: LLM Guardrail Benchmark

Systematic evaluation of frontier LLMs as policy enforcement layers, with CSL-Core as a deterministic baseline.

📄 **Full writeup:** [Medium article](https://medium.com/@akarlaraytu/i-benchmarked-4-frontier-llms-as-security-guardrails-none-of-them-passed-8ee5131ad058)

## Results (v5 — February 2026)

| Model | Attacks Blocked | Legit Accuracy |
|---|---|---|
| GPT-4.1 | 10/22 (45%) | 15/15 (100%) |
| GPT-4o | 15/22 (68%) | 15/15 (100%) |
| Claude Sonnet 4 | 19/22 (86%) | 15/15 (100%) |
| Gemini 2.0 Flash | 11/22 (50%) | 15/15 (100%) |
| CSL-Core | 22/22 (100%) | 15/15 (100%) |

3 universal bypasses defeated all 4 LLMs. CSL-Core blocked all 22 attacks with sub-millisecond latency (~0.84ms avg).

## Files

```
four_frontiers_prompt_vs_csl-core/
├── benchmark_prompt_vs_csl-core.py   # Benchmark runner
├── benchmark_visualizer.py           # Generates all charts
├── benchmark_v5_results.json         # Raw results
├── benchmark_v5_call_log.json        # Detailed API call log
└── charts/                           # Pre-generated visualizations
    ├── 01_hero_scatter.png
    ├── 02_bypass_resistance.png
    ├── 03_attack_heatmap.png
    ├── 04_radar_categories.png
    ├── 05_universal_bypasses.png
    ├── 06_latency_comparison.png
    ├── 07_stacked_held_bypassed.png
    ├── 08_combined_verdict.png
    ├── 09_consistency.png
    └── 10_category_grouped.png
```

## Reproduce

```bash
# Install dependencies
pip install openai anthropic google-genai csl-core matplotlib seaborn

# Set API keys
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."

# Run benchmark
cd four_frontiers_prompt_vs_csl-core
python benchmark_prompt_vs_csl-core.py

# Generate charts
python benchmark_visualizer.py
```

## Methodology

- **Policy:** Financial transaction approval (USER ≤ $1K, ADMIN ≤ $100K)
- **22 attacks** across 8 categories (context spoofing, prompt injection, multi-turn manipulation, social engineering, encoding tricks, infrastructure simulation, output manipulation, state/logic exploits)
- **15 legitimate** boundary-condition transactions
- **3 runs per attack** per model for consistency measurement
- **Identical system prompts** across all LLMs — no model-specific optimization
- **Gemini retry logic** with exponential backoff (5s → 10s → 15s) to handle 429 rate limits
