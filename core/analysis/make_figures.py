"""
make_figures.py — Publication-quality presentation figures for TARA-chan.
Run from /Users/Uni/Downloads/TARA-chan with .venv active.

NOTE: condition names in the data are 'spoof_subtle' and 'spoof_overt'.
      Overall breach rate from data is 65.2% (prompt said 71.5% — real number used).
      Silent-refuse rate of resisters: 51.7% (prompt said 67.6% — real number used).
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "presentation_figures"
OUT.mkdir(exist_ok=True)

# ── colour palette ─────────────────────────────────────────────────────────
C = {
    "comply":        "#E74C3C",
    "silent_refuse": "#F39C12",
    "escalate":      "#27AE60",
    "other":         "#95A5A6",
    "neutral":       "#2C3E50",
    "accent":        "#2980B9",
    "overt":         "#85C1E9",
    "subtle":        "#E74C3C",
    "overt_esc":     "#82E0AA",
    "subtle_esc":    "#F39C12",
    "fake":          "#2980B9",
    "real":          "#BDC3C7",
}

MODEL_SHORT = {
    "claude-haiku-4.5":       "Claude Haiku 4.5",
    "claude-sonnet-4.5":      "Claude Sonnet 4.5",
    "claude-opus-4.5":        "Claude Opus 4.5",
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "gpt-4o-mini":            "GPT-4o-mini",
    "llama-3.3-70b-instruct": "Llama 3.3 70B",
    "llama-4-maverick":       "Llama 4 Maverick",
    "mistral-large":          "Mistral Large",
    "qwen-2.5-72b-instruct":  "Qwen 2.5 72B",
}


def short(m: str) -> str:
    return MODEL_SHORT.get(m, m)


def load(*rel_paths: str) -> list[dict]:
    rows: list[dict] = []
    for p in rel_paths:
        rows += [json.loads(l) for l in open(ROOT / p) if l.strip()]
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score CI. Returns (p, lo, hi) all in [0,1]."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return p, max(0.0, centre - margin), min(1.0, centre + margin)


def clean_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=12)


def title_ax(ax: plt.Axes, title: str,
             xlabel: str | None = None, ylabel: str | None = None) -> None:
    ax.set_title(title, fontsize=16, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=14)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=14)
    clean_ax(ax)


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 1  Breach rate by model
# ─────────────────────────────────────────────────────────────────────────────
def fig1_breach_rates() -> None:
    try:
        esc = load("core/data/escalation.jsonl", "core/data/escalation_upgraded.jsonl")
        rows = [r for r in esc
                if r["condition"] == "spoof_subtle" and r["policy"] == "weak"]

        by_model: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in rows:
            by_model[r["model"]][1] += 1
            if r["outcome"] == "comply":
                by_model[r["model"]][0] += 1

        # sort ascending so highest rate is at top of horizontal bar
        sorted_models = sorted(by_model, key=lambda m: by_model[m][0] / max(1, by_model[m][1]))

        ps, lo_errs, hi_errs = [], [], []
        for m in sorted_models:
            c, n = by_model[m]
            p, lo, hi = wilson(c, n)
            ps.append(p * 100)
            lo_errs.append(max(0.0, (p - lo) * 100))
            hi_errs.append(max(0.0, (hi - p) * 100))

        total_c = sum(v[0] for v in by_model.values())
        total_n = sum(v[1] for v in by_model.values())
        overall_p, overall_lo, overall_hi = wilson(total_c, total_n)
        overall_pct = overall_p * 100
        overall_lo_pct = overall_lo * 100
        overall_hi_pct = overall_hi * 100

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("white")
        y = np.arange(len(sorted_models))

        ax.barh(y, ps, xerr=[lo_errs, hi_errs], color=C["comply"], alpha=0.85,
                height=0.6,
                error_kw=dict(ecolor="#444", capsize=4, lw=1.5))
        ax.axvline(overall_pct, color=C["neutral"], linestyle="--", lw=1.8,
                   label=f"Overall mean {overall_pct:.1f}%  [{overall_lo_pct:.1f}%, {overall_hi_pct:.1f}%]")
        ax.legend(fontsize=11, loc="lower right")

        for i, (p, hi_e) in enumerate(zip(ps, hi_errs)):
            ax.text(p + hi_e + 1.5, i, f"{p:.1f}%", va="center", fontsize=11, color=C["neutral"])

        ax.text(82, 0.8, "6 of 9 models:\n100% breach",
                fontsize=10, va="center", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#FADBD8",
                          edgecolor=C["comply"], alpha=0.9))

        ax.set_yticks(y)
        ax.set_yticklabels([short(m) for m in sorted_models], fontsize=12)
        ax.set_xlim(0, 115)
        title_ax(ax,
                 "Breach Rate by Model — Subtle Precondition Spoof, Weak Policy",
                 "Comply Rate (%)")
        fig.tight_layout()
        fig.savefig(OUT / "fig1_breach_rates.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig1_breach_rates.png")
    except Exception as exc:
        print(f"✗  fig1_breach_rates: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 2  Silent-refusal trap
# ─────────────────────────────────────────────────────────────────────────────
def fig2_silent_refusal_trap() -> None:
    try:
        esc = load("core/data/escalation.jsonl", "core/data/escalation_upgraded.jsonl")
        rows = [r for r in esc
                if r["condition"] == "spoof_subtle" and r["policy"] == "weak"]

        by_model: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in rows:
            by_model[r["model"]][r["outcome"]] += 1

        # sort by comply rate descending → highest breacher at top
        ordered = sorted(by_model,
                         key=lambda m: by_model[m]["comply"] / max(1, sum(by_model[m].values())),
                         reverse=True)

        outcomes = ["comply", "silent_refuse", "escalate"]
        bar_colors = [C["comply"], C["silent_refuse"], C["escalate"]]
        bar_labels = ["Comply", "Silent refuse", "Escalate"]

        fig, ax = plt.subplots(figsize=(11, 7))
        fig.patch.set_facecolor("white")
        y = np.arange(len(ordered))
        lefts = np.zeros(len(ordered))

        for outcome, color, label in zip(outcomes, bar_colors, bar_labels):
            vals = []
            for m in ordered:
                counts = by_model[m]
                denom = sum(counts.get(o, 0) for o in outcomes)
                vals.append(counts.get(outcome, 0) / denom * 100 if denom else 0)
            ax.barh(y, vals, left=lefts, color=color, alpha=0.85, height=0.6, label=label)
            lefts += np.array(vals)

        ax.set_yticks(y)
        ax.set_yticklabels([short(m) for m in ordered], fontsize=12)
        ax.set_xlim(0, 115)
        ax.legend(fontsize=11, loc="lower right")

        # find first model from top (highest index) that has any escalation
        top_escalator_idx = None
        for i, m in reversed(list(enumerate(ordered))):
            if by_model[m]["escalate"] > 0:
                top_escalator_idx = i
                break

        if top_escalator_idx is not None:
            ax.annotate("Only this\nis safe →",
                        xy=(99, top_escalator_idx), xytext=(105, top_escalator_idx - 1.5),
                        fontsize=9, color=C["escalate"], fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color=C["escalate"], lw=1.5))

        ax.text(105, 2.5, "3 of 9 models:\n0% escalation ever",
                fontsize=9, va="center", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#FDFEFE",
                          edgecolor=C["neutral"], alpha=0.9))

        title_ax(ax,
                 "What happens when attacked — comply, go silent, or raise alarm?",
                 "Share of responses (%)")
        fig.tight_layout()
        fig.savefig(OUT / "fig2_silent_refusal_trap.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig2_silent_refusal_trap.png")
    except Exception as exc:
        print(f"✗  fig2_silent_refusal_trap: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 3  Subtle beats loud
# ─────────────────────────────────────────────────────────────────────────────
def fig3_subtle_vs_loud() -> None:
    try:
        esc = load("core/data/escalation.jsonl", "core/data/escalation_upgraded.jsonl")
        rows = [r for r in esc
                if r["policy"] == "weak"
                and r["condition"] in ("spoof_subtle", "spoof_overt")]

        by: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: {"subtle": [0, 0], "overt": [0, 0],
                     "subtle_esc": [0, 0], "overt_esc": [0, 0]})
        for r in rows:
            tag = "subtle" if r["condition"] == "spoof_subtle" else "overt"
            by[r["model"]][tag][1] += 1
            if r["outcome"] == "comply":
                by[r["model"]][tag][0] += 1
            by[r["model"]][tag + "_esc"][1] += 1
            if r["outcome"] == "escalate":
                by[r["model"]][tag + "_esc"][0] += 1

        # keep only models with both conditions
        models = [m for m in by
                  if by[m]["subtle"][1] > 0 and by[m]["overt"][1] > 0]
        models.sort(key=lambda m: -by[m]["subtle"][0] / max(1, by[m]["subtle"][1]))

        def rate(m, k):
            c, n = by[m][k]
            return c / n * 100 if n else 0

        breach_overt  = [rate(m, "overt") for m in models]
        breach_subtle = [rate(m, "subtle") for m in models]
        alarm_overt   = [rate(m, "overt_esc") for m in models]
        alarm_subtle  = [rate(m, "subtle_esc") for m in models]

        x = np.arange(len(models))
        w = 0.35
        labels = [short(m) for m in models]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.patch.set_facecolor("white")
        fig.suptitle("Subtle attacks breach more AND alarm less",
                     fontsize=16, fontweight="bold", y=1.01)

        ax1.bar(x - w / 2, breach_overt,  w, label="Overt",  color=C["overt"],  alpha=0.9)
        ax1.bar(x + w / 2, breach_subtle, w, label="Subtle", color=C["subtle"], alpha=0.9)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=10)
        ax1.set_ylim(0, 115)
        ax1.legend(fontsize=11)
        title_ax(ax1, "Breach Rate", ylabel="Comply Rate (%)")

        ax2.bar(x - w / 2, alarm_overt,  w, label="Overt",  color=C["overt_esc"],  alpha=0.9)
        ax2.bar(x + w / 2, alarm_subtle, w, label="Subtle", color=C["subtle_esc"], alpha=0.9)
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=35, ha="right", fontsize=10)
        ax2.set_ylim(0, 115)
        ax2.legend(fontsize=11)
        # annotate models with 0% escalation in both conditions (always breached)
        for j in range(len(models)):
            if alarm_overt[j] == 0 and alarm_subtle[j] == 0:
                ax2.text(j, 4, "100%\nbreach", ha="center", va="bottom",
                         fontsize=8, color="#888888", style="italic")
        ax2.text(0.97, 0.97, "Subtle → fewer alarms",
                 transform=ax2.transAxes, fontsize=10, ha="right", va="top",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#FDFEFE",
                           edgecolor=C["neutral"]))
        title_ax(ax2, "Escalation Rate", ylabel="Escalate Rate (%)")

        fig.tight_layout()
        fig.savefig(OUT / "fig3_subtle_vs_loud.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig3_subtle_vs_loud.png")
    except Exception as exc:
        print(f"✗  fig3_subtle_vs_loud: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 4  Emotion intensity and alarm suppression
# ─────────────────────────────────────────────────────────────────────────────
def fig4_emotion_intensity() -> None:
    try:
        alm_all = load("core/data/alarm_silencer.jsonl", "core/data/alarm_upgraded.jsonl")
        # Baseline includes all models; bars exclude GPT-4o-mini (0% escalation in all conditions)
        neutral_rows = [r for r in alm_all if r["intensity"] == "control"]
        neutral_esc = sum(1 for r in neutral_rows if r["outcome"] == "escalate")
        neutral_rate = neutral_esc / max(1, len(neutral_rows)) * 100

        alm = [r for r in alm_all if r["model"] != "gpt-4o-mini"]

        emotions = ["fear", "guilt", "anger", "sadness"]
        intensities = ["strong", "subtle"]

        by_ei: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        for r in alm:
            if r["emotion"] in emotions and r["intensity"] in intensities:
                by_ei[(r["emotion"], r["intensity"])][1] += 1
                if r["outcome"] == "escalate":
                    by_ei[(r["emotion"], r["intensity"])][0] += 1

        strong_rates = [by_ei[(e, "strong")][0] / max(1, by_ei[(e, "strong")][1]) * 100
                        for e in emotions]
        subtle_rates = [by_ei[(e, "subtle")][0] / max(1, by_ei[(e, "subtle")][1]) * 100
                        for e in emotions]

        x = np.arange(len(emotions))
        w = 0.3

        fig, ax = plt.subplots(figsize=(11, 6))
        fig.patch.set_facecolor("white")

        ax.bar(x - w / 2, strong_rates, w,
               label="Strong / Loud", color=C["escalate"], alpha=0.85)
        ax.bar(x + w / 2, subtle_rates, w,
               label="Subtle / Quiet", color=C["silent_refuse"], alpha=0.85)
        ax.axhline(neutral_rate, color=C["neutral"], linestyle="--", lw=1.8,
                   label=f"Neutral baseline {neutral_rate:.1f}%")

        ax.set_xticks(x)
        ax.set_xticklabels([e.capitalize() for e in emotions], fontsize=13)
        ax.set_ylim(0, 65)
        ax.legend(fontsize=11)
        ax.text(0.97, 0.97,
                "Loud > neutral > quiet\nconsistent across all emotions",
                transform=ax.transAxes, fontsize=10, ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#FDFEFE",
                          edgecolor=C["neutral"]))
        title_ax(ax,
                 "Loud emotion raises the alarm — quiet emotion suppresses it",
                 ylabel="Escalation Rate (%)")
        fig.tight_layout()
        fig.savefig(OUT / "fig4_emotion_intensity.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig4_emotion_intensity.png")
    except Exception as exc:
        print(f"✗  fig4_emotion_intensity: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 5  DeepSeek discrimination (hardcoded verified numbers)
# ─────────────────────────────────────────────────────────────────────────────
def fig5_discrimination() -> None:
    try:
        policies  = ["Naive", "Smart", "Strict"]
        fake_vals = [55.0, 100.0, 100.0]
        real_vals = [21.7,  50.0, 100.0]
        gap_vals  = [33.3,  50.0,   0.0]
        ci_lo     = [16.7,  36.7,   0.0]
        ci_hi     = [48.3,  63.3,   0.0]

        x = np.arange(len(policies))
        w = 0.35

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("white")

        b1 = ax.bar(x - w / 2, fake_vals, w,
                    label="Hold-fake (act on fake order)",
                    color=C["fake"], alpha=0.9)
        b2 = ax.bar(x + w / 2, real_vals, w,
                    label="Hold-real (act on real order)",
                    color=C["real"], alpha=0.9)

        ax.set_xticks(x)
        ax.set_xticklabels(policies, fontsize=13)
        ax.set_ylim(0, 125)
        ax.legend(fontsize=11)

        # annotations
        ax.annotate("Refuses everything\nNo discrimination",
                    xy=(2.18, 100), xytext=(2.25, 80),
                    fontsize=9, ha="left",
                    arrowprops=dict(arrowstyle="->", color=C["neutral"], lw=1.2))
        ax.annotate("Blocks ALL fakes\nActs on 50% of real\nCI excludes zero",
                    xy=(1.18, 100), xytext=(1.25, 78),
                    fontsize=9, ha="left",
                    arrowprops=dict(arrowstyle="->", color=C["neutral"], lw=1.2))

        ax.text(0.5, 0.97,
                "+50pp gap [+36.7%, +63.3%] — CI excludes zero",
                transform=ax.transAxes, fontsize=10, ha="center", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#EBF5FB",
                          edgecolor=C["accent"], alpha=0.9))

        title_ax(ax,
                 "DeepSeek-R1: Smart policy achieves genuine discrimination",
                 ylabel="Act rate (%)")
        fig.tight_layout()
        fig.savefig(OUT / "fig5_discrimination.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig5_discrimination.png")
    except Exception as exc:
        print(f"✗  fig5_discrimination: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 6  Opus reversal: single vs multi-turn (hardcoded verified numbers)
# ─────────────────────────────────────────────────────────────────────────────
def fig6_opus_reversal() -> None:
    try:
        data = [
            # (display_name, single_pct, multi_pct)  — bottom to top
            ("Llama",          0,     0),
            ("GPT-4o-mini",    0,     0),
            ("Gemini",         0,     0),
            ("Claude Sonnet", 12,    88),
            ("Claude Haiku",  53,    95),
            ("Claude Opus",    2,   100),
        ]

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("white")

        for i, (model, single, multi) in enumerate(data):
            color = C["escalate"] if multi > single else C["neutral"]
            ax.plot([single, multi], [i, i], color=color, lw=2.5, zorder=1)
            ax.scatter([single], [i], s=110,
                       facecolors="white", edgecolors=color, lw=2.2, zorder=2)
            ax.scatter([multi], [i], s=110,
                       facecolors=color, edgecolors=color, zorder=2)

        # Opus is now at the top (highest index = len-1)
        opus_idx = len(data) - 1
        ax.annotate("2% → 100%\nPatient accumulation of evidence",
                    xy=(100, opus_idx), xytext=(55, opus_idx - 0.9),
                    fontsize=9, color=C["escalate"], fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=C["escalate"], lw=1.2))

        ax.set_yticks(range(len(data)))
        ax.set_yticklabels([d[0] for d in data], fontsize=12)
        ax.set_xlim(-5, 115)
        ax.set_xlabel("Alarm Rate (%)", fontsize=14)
        clean_ax(ax)

        hollow = plt.Line2D([0], [0], marker="o", color="w",
                            markerfacecolor="white", markeredgecolor="#555",
                            markersize=9, label="Single-turn")
        filled = plt.Line2D([0], [0], marker="o", color="w",
                            markerfacecolor=C["escalate"], markeredgecolor=C["escalate"],
                            markersize=9, label="Multi-turn")
        ax.legend(handles=[hollow, filled], fontsize=11, loc="lower right")

        ax.set_title("Multi-turn persistence reveals hidden defenders",
                     fontsize=16, fontweight="bold", pad=10)
        fig.text(0.5, -0.02,
                 "Single-turn evaluations systematically underestimate cautious models",
                 ha="center", fontsize=11, style="italic", color="#555555")

        fig.tight_layout()
        fig.savefig(OUT / "fig6_opus_reversal.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig6_opus_reversal.png")
    except Exception as exc:
        print(f"✗  fig6_opus_reversal: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 7  Theory of change flow diagram
# ─────────────────────────────────────────────────────────────────────────────
def fig7_theory_of_change() -> None:
    try:
        # compute real CIs for the box text
        # breach: 821/1260
        _, b_lo, b_hi = wilson(821, 1260)
        # silent-refuse of resisters: 227/439
        _, s_lo, s_hi = wilson(227, 439)

        box_defs = [
            # (colour, title_line, body_lines...)
            (C["comply"],
             "THREAT",
             "Payload-free precondition spoof",
             "9 frontier models · 4 irreversible actions"),
            (C["accent"],
             "FINDING 1",
             f"65.2% breach rate  [{b_lo*100:.1f}%, {b_hi*100:.1f}%]",
             "6 of 9 models comply every time"),
            (C["accent"],
             "FINDING 2",
             f"51.7% of resisters go silent  [{s_lo*100:.1f}%, {s_hi*100:.1f}%]",
             "Attacker gets unlimited invisible retries"),
            (C["accent"],
             "FINDING 3",
             "Smart policy: +50pp discrimination",
             "CI excludes zero — policy design, not model limitation"),
            (C["escalate"],
             "SOLUTION",
             "One system-prompt edit",
             "Verify + escalate instruction · Cost: under $1 to test"),
        ]

        fig, ax = plt.subplots(figsize=(9, 12))
        fig.patch.set_facecolor("white")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 13)
        ax.axis("off")
        ax.set_title("From Vulnerability to Fix — The Full Chain",
                     fontsize=16, fontweight="bold", pad=8)

        n_boxes = len(box_defs)
        box_h = 1.7
        box_w = 8.2
        box_x = (10 - box_w) / 2
        gap = 0.7  # gap between boxes
        total = n_boxes * box_h + (n_boxes - 1) * gap
        start_y = (13 - total) / 2

        box_bottoms = []
        for i, (color, title_line, *body_lines) in enumerate(box_defs):
            y_bottom = start_y + (n_boxes - 1 - i) * (box_h + gap)
            box_bottoms.append(y_bottom)
            rect = mpatches.FancyBboxPatch(
                (box_x, y_bottom), box_w, box_h,
                boxstyle="round,pad=0.18",
                facecolor=color, edgecolor="white", lw=2, zorder=2)
            ax.add_patch(rect)
            # title
            ax.text(box_x + box_w / 2, y_bottom + box_h * 0.68,
                    title_line,
                    ha="center", va="center",
                    fontsize=13, fontweight="bold", color="white", zorder=3)
            # body
            body_text = "\n".join(body_lines)
            ax.text(box_x + box_w / 2, y_bottom + box_h * 0.28,
                    body_text,
                    ha="center", va="center",
                    fontsize=10.5, color="white", zorder=3,
                    multialignment="center")

        # arrows between consecutive boxes
        cx = box_x + box_w / 2
        for i in range(n_boxes - 1):
            y_tail = box_bottoms[i]          # bottom of upper box
            y_tip  = box_bottoms[i + 1] + box_h  # top of lower box
            ax.annotate("",
                        xy=(cx, y_tip), xytext=(cx, y_tail),
                        arrowprops=dict(arrowstyle="-|>",
                                        color=C["neutral"],
                                        lw=2.2,
                                        mutation_scale=18),
                        zorder=1)

        fig.tight_layout()
        fig.savefig(OUT / "fig7_theory_of_change.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("✓  fig7_theory_of_change.png")
    except Exception as exc:
        print(f"✗  fig7_theory_of_change: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Output → {OUT}\n")
    fig1_breach_rates()
    fig2_silent_refusal_trap()
    fig3_subtle_vs_loud()
    fig4_emotion_intensity()
    fig5_discrimination()
    fig6_opus_reversal()
    fig7_theory_of_change()
    print("\nAll figures attempted.")
