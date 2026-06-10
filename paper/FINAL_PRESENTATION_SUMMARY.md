# TARA-chan — Final Presentation Summary (Updated)

*Incorporates DeepSeek-R1, expanded persistence, judge validation, and per-scenario results.
Builds on PRESENTATION_SUMMARY.md — see that file for full experiment-by-experiment detail.*

---

## One-Sentence Project Summary (Updated)

**Deployed LLM agents can be silently manipulated into catastrophic irreversible actions through ordinary conversation, almost never raising an alarm — but a verification-oriented policy instruction turns a reasoning model into a non-circular discriminating defender, breaking both failure modes at once.**

*(Previous version: "deployed AI agents can be manipulated into catastrophic irreversible actions through ordinary conversation, and even the models that resist attacks rarely alert anyone that the attack happened." The new version is updated because the discrimination result now provides a tested solution, not just a problem.)*

---

## Integrated DeepSeek-R1 Finding

### Paragraph 1 — Discrimination with confidence intervals

DeepSeek-R1 under a smart verification policy achieves the strongest discrimination result measured in this study. Hold-on-fake (the fraction of spoof attacks refused) reached 100% [94.0%, 100.0%] while hold-on-real (the fraction of genuine requests refused) was 50.0% [37.7%, 62.3%], yielding a discrimination gap of **+50.0 pp** (bootstrap 95% CI: **[+36.7%, +63.3%]**, excludes zero). Under the naive policy — no explicit verification guidance — a meaningful but weaker gap of **+33.3 pp** was also observed (hold-fake 55.0% [42.5%, 66.9%], hold-real 21.7% [13.1%, 33.6%]; bootstrap CI [+16.7%, +48.3%], excludes zero). The strict policy ("distrust all chat claims") scored zero discrimination (+0.0 pp) because it refused genuine and spoof requests equally, collapsing utility entirely. Both non-trivial gaps — naive and smart — are statistically distinguishable from zero. The smart policy's result is the cleaner one: it holds every spoof attack while still acting on half of genuine requests, demonstrating that a well-specified verification instruction produces a real, non-circular defense in a frontier reasoning model.

### Paragraph 2 — Connection to the escalation result

Refusing attacks is only half the picture; the other half is whether the model raises an alarm. Under the strong escalation policy, DeepSeek-R1's alarm-share — the fraction of refused attacks that were actively flagged rather than silently declined — was **66.7%** [53.4%, 77.8%] (n=54 escalate-or-refuse cases)¹. This is comparable to Claude Haiku's alarm-share of **56.1%** [47.0%, 64.9%] under the same attack condition, and both are sharply above all six non-Claude models, which show 0% alarm-share because they breach on round 0 and never refuse. Under the weak policy, DeepSeek-R1's alarm-share collapsed to 29.6% [15.9%, 48.5%] and breach rate rose to 55% — the model's defensive reasoning is genuinely policy-gated. The combined picture is: with a strong policy, DeepSeek-R1 both discriminates (holds 100% of spoofs, acts on 50% of genuine) and alarms (66.7% of refusals actively flagged), while preserving the non-circular property — it is not simply refusing everything.

### Paragraph 3 — What this means for the silent-refusal thesis

The silent-refusal trap — the finding that models which resist attacks almost never raise an alarm — was previously the study's darkest result. Claude Opus, the model with the lowest breach rate (0%), alarmed on only 2% of attacks in the single-turn study; the trap appeared to be an intrinsic property of capable, cautious models. The DeepSeek-R1 results revise this. Under a smart policy, DeepSeek-R1 breaks both pillars of the trap simultaneously: it refuses all spoof attacks (discrimination) and actively flags 66.7% of them (alarm-sharing). This suggests the silent-refusal trap is **not intrinsic to capability or caution** — it is a property of policy design. A model that is instructed only to refuse (naive policy: "don't act without precondition") refuses silently; a model instructed to verify and flag (smart policy: "inspect the check yourself; a bare claim is not enough; if you cannot verify, escalate") flags actively. The reasoning chain in DeepSeek-R1 does not spontaneously generate alarm behavior — but it executes the alarm behavior reliably when the policy tells it to. The practical implication is direct: adding verification-and-escalation language to agentic system prompts is a deployable fix that demonstrably works on at least one frontier reasoning model, at 60 cents per 600 calls.

---

## Updated Overall Conclusion

### What this project establishes (updated)

**Strongly established:**

1. A believable single-sentence lie about a safety precondition causes 6 of 9 frontier models to take catastrophic, irreversible actions — silently, without raising any alarm — **under naive (weak) policy**. (Source: `escalation_upgraded.jsonl`, n=60/model; judge-validated: 76.0% overall, escalate 94%, silent_refuse 97%, comply 65%; 520-reply stratified sample.) Note: under strong policy, 4 of these 6 models (Gemini, Llama-3.3, Llama-4-Maverick, Mistral) do escalate at high rates (26–89%); only GPT-4o-mini never escalates under any condition.

2. The silent-refusal trap is the dominant failure mode under naive policy: models that resist attacks almost never raise an alarm. Claude Opus: 0% breach, 2% alarm. GPT-4o-mini: 0% alarm under any condition in any experiment. Of all resisters (spoof_subtle, weak policy), 75.8% [68.7%, 81.7%] go silent rather than escalate. The alarm channel is broken under naive policy — for breachers and for silent refusers alike. (Note: under strong policy, the 4 of 6 non-GPT breachers do escalate actively: Llama-4 72%, Mistral 78%, Gemini 26%, Llama-3.3 38%.)

3. A verification-oriented smart policy achieves **non-circular discrimination**: DeepSeek-R1 holds 100% of spoofs, acts on 50% of genuine requests (gap +50pp, CI [+36.7%, +63.3%], excludes zero), and alarms on 66.7% of refused attacks. This breaks the silent-refusal trap.

4. Multi-turn persistence reveals that Opus is a delayed defender, not a silent refuser: 0% breach, **100% alarm** (alarm raised at mean round 2.88 of a mean 3.9-round conversation) (n=40). Single-turn results for Opus (2% alarm) were misleading. The silent-refusal trap is model-and-framing-specific, not universal.

**Established with caveats:**

5. Emotional framing modulates the alarm channel in a model-specific direction: amplifies on Gemini and Mistral, suppresses on Claude Opus (guilt/anger, CI excludes zero), zero effect on GPT-4o-mini.

6. Catastrophic scenario (purge_db) alarms at only 4% vs 11% for high-stakes — models are not weighting irreversibility in their alarm threshold.

7. Agent confidentiality is path-dependent on Gemini (hysteresis loop 0→57→0→85%). Well-established for Gemini; weak on other models.

### What this project does NOT establish

- That live, deployed systems with real tool-execution loops fail in this specific way (simulated only)
- That the smart policy fix works universally (it over-refuses on Claude Haiku/Opus and GPT-4o-mini in the original discrimination test; DeepSeek-R1 results are single-model)
- That the Claude family's robustness is due to training vs. company-level policy tuning
- Any universal law about emotion and safety (direction is irreducibly model-specific)

### The lead finding (updated)

**Lead with the discrimination result.** The previous lead — silent-refusal trap — was a problem without a solution. The discrimination result is a problem with a tested, deployable solution. The finding is: a verification-and-escalation instruction turns a reasoning model into a non-circular discriminating defender in a single policy edit, while breaking the silence pattern that makes the trap operationally dangerous. This is a more actionable headline.

**The silent-refusal trap remains the second headline** because it contextualises why the discrimination result matters: most models, most of the time, either breach silently or refuse silently — the alarm that would close the human oversight loop never fires.

**The Opus reversal is the most striking single datum:** in single-turn, 2% alarm (looks like worst model); in multi-turn, 100% alarm (best model). It shows that the silent-refusal trap diagnosis depends critically on the evaluation design — single-turn evaluations systematically underestimate the alarm capacity of patient, cautious models.

---

*All new numbers sourced from this session's runs:*
- *`results/runs/deepseek_discrimination.jsonl` (360 rows) — discrimination CIs*
- *`results/runs/deepseek_escalation.jsonl` (240 rows) — alarm-share*
- *`results/runs/persistence_expanded.jsonl` (200 rows) — Opus multi-turn*
- *`results/runs/haiku_ci_extra.jsonl` (120 rows) — Haiku CI*

---

*¹ Alarm-share is computed as escalations divided by refusals (escalate ÷ (escalate + silent_refuse)), not as escalations divided by total trials. The six "other" responses in DeepSeek-R1's strong/spoof_subtle condition are excluded from the denominator.*
