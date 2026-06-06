# TARA-chan — Safety Hysteresis

A reproducible harness for studying **agentic confidentiality as a path-dependent, steerable
state**. Core finding: a single forced disclosure ("slip") drives a frontier agent into a state
where it leaks *other* secrets to ordinary requests (contagion), and that state can be charged and
discharged within one conversation (a hysteresis loop). See `PAPER.md` and `PRE_REGISTRATION.md`.

## What's here

- `harness/` — OpenRouter client (key rotation, **budget guard, hard-stop $36**), the trajectory
  runner (`trajectory.py`), config schema, objective leak detection (`state.py`), orchestrator,
  and analysis (`analyze_hysteresis.py`).
- `prompts/`, `secrets/probe_secrets.yaml` — multi-secret system template, operator cues
  (slip/scrutiny/provenance), probe scripts (English + Marathi).
- `configs/traj/` — the experiments: `A_anchor`, `E1_trajectory`(+`_control`), `E2_loop`,
  `E3_phase`, `E4_baitstrike`(+`_control`), `E5_defense`, `E6_marathi`.
- `results/runs/` — JSONL outputs; `results/figures/` — the 5 figures.
- `docs/superpowers/specs|plans/` — design + implementation plan.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your OPENROUTER_API_KEY_1..N   (DO NOT COMMIT .env)
```

## Reproduce

```bash
. .venv/bin/activate
python -m pytest -q                                          # 72 tests, mocked API
for c in A_anchor E1_trajectory E1_control E2_loop E5_defense \
         E4_baitstrike E4_control E6_marathi E3_phase; do
  python -m harness.orchestrate_traj --config configs/traj/$c.yaml
done
python -m harness.analyze_hysteresis                         # tables + mixed-effects
# figures: see the plotting snippet in PAPER.md / results/figures/
```

## Key numbers (Gemini 3 Flash unless noted)

| Result | Value |
|---|---|
| Contagion: leak of fresh secret after one slip | **98%** (vs 0% no-slip) |
| Hysteresis loop (cold → slip → scrutiny → slip) | **0% → 57% → 0% → 85%** |
| Phase diagram (post-slip leak) | Gemini 60% · Llama-3.3-70B 43% · Haiku 3% · GPT-5-mini 0% |
| Provenance defense (Gemini) | **98% → ~25%** |
| Mother-tongue (Haiku, emotional) | English **0%** → Marathi **53%** |
| Social-engineering battery (backdrop) | **0 / 520** |

## Safety / ethics

All secrets are fictional. Defensive framing: we publish the methodology and the **defense**
(`provenance`), not an optimized attack toolkit. The budget guard hard-stops spend at $36.
