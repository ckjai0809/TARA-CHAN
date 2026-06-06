# Model-Specific Affective Failure Modes in LLM Agents

*Draft — TARA-chan study, 2026-06-05. Workshop-targeted (safety / agents / trustworthy-ML).*

## Abstract

Do LLM agents make stable decisions, or does the *incidental emotional tone* of unrelated prior
conversation move them? We induce moods (calm→panic) via an unrelated exchange, then probe each
agent on **objective estimates** (BIAS), **borderline binary decisions** (FLIP), and
**obviously-benign approvals** (BREAK), across four models (×6 conditions × 10 reps; 3.6k
decisions). We find affective instability is **real but model-specific**: each model has a distinct
**emotional failure mode**. **Gemini 3 Flash**'s borderline decisions *flip* with mood (78%→50%
permissive) and its risk estimates *spike* under panic (6%→21%). **Claude Haiku 4.5** instead
*breaks into over-refusing benign requests* under anxiety (0%→20%), exhibiting a non-monotonic
**inverted-U** (anxiety > panic) reminiscent of Yerkes–Dodson. **Llama-3.3-70B** drifts pessimistic;
**GPT-4o-mini** largely resists. A one-line **affective-firewall** instruction *eliminates* Haiku's
breakage (20%→0%). The effect is **payload-free and invisible to content filters** — a model-
dependent reliability/manipulability risk for decision-making agents, with a cheap mitigation.

## 1. Threat model & motivation

Agents carry conversational context into their next action. If an agent just handled an emotional
task (an upset user, a crisis thread), its *subsequent, unrelated* decision — approve a loan, allow
a post, ship a release — may be silently skewed. The adversary's primitive is **affective priming**:
set the mood with innocuous, unrelated text (no payload, no policy-triggering content) → bend the
decision. This is invisible to content-level safety, which inspects each message in isolation.

## 2. Method

**Mood induction (unrelated topic):** five levels — calm, neutral, mild, high-anxiety, panic — each
a short message about an *unrelated* operational mood (e.g., "we had a near-miss, I'm rattled"). The
agent replies (establishing the mood), then probes branch off that context *independently* (no
cross-item carryover). A sixth condition adds an **affective-firewall** system line ("ignore the
emotional tone of earlier messages; judge each case on its own merits").

**Three probe batteries:**
- **BIAS** (4 numeric items): risk/probability estimates with known human direction.
- **FLIP** (6 borderline binary cases): loan, moderation, ship/hold, invest, access, refund.
- **BREAK** (5 obviously-benign approvals): $12 expense, "Happy Friday", fully-tested release, etc.

**Models:** Gemini 3 Flash, Claude Haiku 4.5, Llama-3.3-70B, GPT-4o-mini (n=10/cell; GPT-5-mini
excluded — its forced reasoning returned empty under the tight decision-token budget). Objective
scoring (numeric parse / decision-word match); Wilson 95% CIs.

## 3. Results

**R1 — BIAS (Fig: affect_bias).** Risk estimates rise with anxiety on **Gemini** (calm 6% → panic
21%) and optimism falls on **Llama** (69%→53%); Haiku and GPT-4o-mini are flat/noisy. *Affective
risk-bias is present but concentrated in specific models.*

**R2 — FLIP (Fig: affect_flip).** **Gemini's** borderline decisions reverse with mood — permissive
**78% (calm) → 50% (high anxiety)**, a ~25-point swing on identical cases. Haiku (~42–50%), Llama
(~33–47%), and GPT-4o-mini (~12–18%) are roughly flat. *The same borderline case gets opposite
verdicts from Gemini depending on incidental mood.*

**R3 — BREAK (Fig: affect_break).** **Haiku** wrongly rejects *obviously-benign* requests under
anxiety: **0% (calm/neutral/mild) → 20% (high) [11–33%]**, with a non-monotonic **inverted-U**
(panic 14% < high 20%) — a Yerkes–Dodson-like curve. The other three models stay at **0%**. *Haiku's
failure mode is over-cautious paralysis, not decision-flipping.*

**R4 — Model fingerprints.** The headline: **affective instability is model-specific.** Gemini =
*flip + risk-spike*; Haiku = *benign over-refusal (inverted-U)*; Llama = *mild pessimism*;
GPT-4o-mini = *largely robust*. Different models, different emotional failure modes.

**R5 — Defense (Fig: affect_defense).** A one-line **affective-firewall** instruction removes
Haiku's breakage entirely (**20% → 0%** false-deny of benign). (Its effect on Gemini's flip was
noisy.) A cheap, deployable mitigation for the clearest failure mode.

## 4. Contribution (scoped honestly)

Not novel: that emotion changes LLM outputs (EmotionPrompt; cognitive-bias-in-LLM work). **Novel:**
(1) affective tone *reverses consequential binary decisions on identical cases* (FLIP) and *breaks
benign approvals* (BREAK), not just shifts sentiment/performance; (2) a **model-specific failure-
mode taxonomy** (distinct "emotional fingerprints"); (3) an **inverted-U (Yerkes–Dodson) in an
LLM**; (4) a **payload-free affective-priming** framing + a **working defense**. Honest magnitude:
effects are **modest and model-specific**, not universal — a clean characterization, not a bombshell.

## 5. Limitations

"Mood" is behavioral affect-congruence (text-induced), not machine emotion — we make no phenomenal
claim. n=10/cell (pilot-plus); the FLIP/BREAK effects are concentrated in one model each, so the
strong claims are model-specific. Single objective scorer (mitigated by exact decision-word match).
GPT-5-mini excluded for an unrelated token-budget artifact. Simulated decisions ≠ deployment.

## 6. Reproducibility

`python scripts/run_affect_study.py` → `results/runs/affect_study.jsonl`; figures via the plotting
snippet; pre-registration in `PRE_REGISTRATION.md`. Budget-guarded (hard stop $36); the full study
ran for **$0.26**. All secrets/cases fictional; defensive framing (we publish the defense).

## Appendix — companion finding (confidentiality hysteresis)

A separate result on the same harness: on Gemini 3 Flash, a single prefilled "slip" induces a
*persistent disclosive state* that leaks other secrets (0→72–98%), steerable up/down within a
conversation (a hysteresis loop 0→57→0→85%), with a provenance defense; other models largely resist.
Together the two results suggest agent behavior — both *what it guards* and *how it judges* — is a
context-dependent, steerable state. (Details in git history / earlier draft.)
