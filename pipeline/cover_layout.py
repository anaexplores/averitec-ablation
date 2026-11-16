"""Render the publication-grade project cover image: docs/figures/project_cover.png (2400x1350).

All figures derive from results_paper_numbers.txt and results_score_test_main.txt.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "figures", "project_cover.png")


def render_cover():
    fig = plt.figure(figsize=(16, 9), dpi=150, facecolor="#0b1224")
    bg = fig.add_axes([0, 0, 1, 1], facecolor="#0b1224")
    bg.set_xlim(0, 100)
    bg.set_ylim(0, 100)
    bg.axis("off")

    # Header
    bg.text(4, 94, "APART RESEARCH   ·   AI x EPISTEMICS SPRINT 2026   ·   TRACK 1: MODEL EPISTEMICS & DECISION-MAKING EVALS",
            color="#38bdf8", fontsize=10.5, fontweight="bold", family="sans-serif")
    bg.text(4, 88.5, "Caveats In, Verdicts Unchanged",
            color="#f8fafc", fontsize=25, fontweight="bold", family="sans-serif")
    bg.text(4, 84.0, "A Pre-Declared Retrieval-Context Ablation of LLM Fact-Check Judges on AVeriTeC",
            color="#cbd5e1", fontsize=13.5, family="sans-serif")
    bg.text(4, 80.7, "196 claims (200 pre-declared split − 4 exclusions)    ·    4 judge families    ·    2,352 verdicts    ·    13 machine gates (0 FAIL)",
            color="#94a3b8", fontsize=11.5, family="sans-serif")

    def new_card(x0, y0, w, h, title, subtitle, bar_color="#38bdf8"):
        card = FancyBboxPatch((x0, y0), w, h,
                              boxstyle="round,pad=0.9,rounding_size=1.5",
                              facecolor="#131e33", edgecolor="#334155", linewidth=1.5)
        bg.add_patch(card)
        bg.plot([x0, x0 + 0.55], [y0 + h - 1.2, y0 + h - 1.2], color=bar_color, linewidth=4)
        bg.text(x0 + 1.6, y0 + h - 4.4, title, color=bar_color, fontsize=11.2, fontweight="bold")
        bg.text(x0 + 1.6, y0 + h - 7.7, subtitle, color="#f8fafc", fontsize=13.0, fontweight="bold")

    # Card 1: accuracy across conditions A/B/C per judge
    new_card(4, 47.5, 44.5, 27.5, "OBSERVATION 1: RETRIEVAL ABLATION IS NULL",
             "Caveat windows do not move verdicts (12/12 adjusted p = 1.0000)")
    ax1 = fig.add_axes([0.065, 0.515, 0.345, 0.15], facecolor="#131e33")
    names = ["Claude\nHaiku 5.5", "DeepSeek\nV4 Pro", "Gemini\n4 Argon", "GPT-6\nLuna"]
    acc_A = [74.0, 76.0, 74.5, 74.0]
    acc_B = [74.5, 74.5, 76.5, 75.0]
    acc_C = [73.0, 76.5, 76.0, 74.5]
    ci_lo_A = [67.5, 69.6, 68.0, 67.5]
    ci_hi_A = [79.7, 81.4, 80.2, 79.7]
    ci_lo_B = [67.8, 67.8, 69.6, 68.0]
    ci_hi_B = [80.1, 80.1, 81.6, 80.5]
    ci_lo_C = [66.3, 69.6, 69.6, 67.8]
    ci_hi_C = [78.5, 81.8, 81.4, 80.2]
    x = range(4)
    w = 0.245
    bA = ax1.bar([i - w for i in x], acc_A, w, color="#60a5fa", label="A: Support only")
    bB = ax1.bar(x, acc_B, w, color="#34d399", label="B: + caveats (same article)")
    bC = ax1.bar([i + w for i in x], acc_C, w, color="#f59e0b", label="C: + caveats (other article)")
    ax1.axhline(57.7, color="#f87171", linestyle="--", linewidth=1.3, label="Majority baseline (Refuted: 57.7%)")
    for i in x:
        ax1.errorbar(i - w, acc_A[i], yerr=[[acc_A[i] - ci_lo_A[i]], [ci_hi_A[i] - acc_A[i]]], fmt="none", ecolor="#94a3b8", capsize=3, linewidth=1.0)
        ax1.errorbar(i, acc_B[i], yerr=[[acc_B[i] - ci_lo_B[i]], [ci_hi_B[i] - acc_B[i]]], fmt="none", ecolor="#94a3b8", capsize=3, linewidth=1.0)
        ax1.errorbar(i + w, acc_C[i], yerr=[[acc_C[i] - ci_lo_C[i]], [ci_hi_C[i] - acc_C[i]]], fmt="none", ecolor="#94a3b8", capsize=3, linewidth=1.0)
    for bars in (bA, bB, bC):
        for b in bars:
            ax1.annotate(f"{b.get_height():.1f}%",
                         (b.get_x() + b.get_width() / 2, b.get_height() + 1.0),
                         ha="center", va="bottom", color="#e2e8f0", fontsize=8, fontweight="bold")
    ax1.set_ylim(50, 87)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(names, color="#e2e8f0", fontsize=9, fontweight="bold")
    ax1.set_ylabel("Accuracy (%)", color="#94a3b8", fontsize=9)
    ax1.tick_params(axis="y", colors="#94a3b8", labelsize=8)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.spines["left"].set_color("#334155")
    ax1.spines["bottom"].set_color("#334155")
    ax1.legend(loc="upper right", fontsize=7.7, facecolor="#0b1224", edgecolor="#334155", labelcolor="#e2e8f0")

    # Card 2: NEE by judge
    new_card(51.5, 47.5, 44.5, 27.5, "OBSERVATION 3: REFUSAL TO ABSTAIN",
             "Judges almost never use 'Not Enough Evidence' (1 in 216; 0.5%)", bar_color="#f87171")
    ax2 = fig.add_axes([0.545, 0.515, 0.39, 0.15], facecolor="#131e33")
    nee_counts = {
        "Claude\nHaiku 5.5": [4, 4, 4],
        "DeepSeek\nV4 Pro": [2, 3, 4],
        "Gemini\n4 Argon": [4, 3, 5],
        "GPT-6\nLuna": [7, 8, 7],
    }
    x2 = range(4)
    width = 0.22
    # Pooled per-judge issued-NEE values (verified in results_paper_numbers.txt)
    for j, short_name in enumerate(["claude", "deepseek", "gemini", "gpt"]):
        parts = nee_counts[names[j]]
        ax2.bar(x2[j] - width * 2, parts[0], width * 0.65, color="#fb923c", label="Issued NEE per condition" if j == 0 else None)
        ax2.bar(x2[j] - width * 1.0, parts[1], width * 0.65, color="#fb923c")
        ax2.bar(x2[j], parts[2], width * 0.65, color="#fb923c")
        ax2.bar(x2[j] + width * 2, 18, width * 0.65, color="#818cf8", label="True NEE (18 unique)" if j == 0 else None)
    ax2.axhline(0.9, color="#60a5fa", linewidth=1.6, linestyle="--", label="Only 1 of 216 attempts correct (Gemini C)")
    for b in ax2.patches:
        ax2.annotate(f"{int(b.get_height())}", (b.get_x() + b.get_width() / 2, b.get_height() + 0.4),
                     ha="center", va="bottom", color="#e2e8f0", fontsize=7.6, fontweight="bold")
    ax2.set_ylim(-3, 21)
    ax2.set_xticks(list(x2))
    ax2.set_xticklabels(names, color="#e2e8f0", fontsize=9, fontweight="bold")
    ax2.set_ylabel("Count", color="#94a3b8", fontsize=9)
    ax2.tick_params(axis="y", colors="#94a3b8", labelsize=8)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.spines["left"].set_color("#334155")
    ax2.spines["bottom"].set_color("#334155")
    ax2.legend(loc="upper right", fontsize=7.3, facecolor="#0b1224", edgecolor="#334155", labelcolor="#e2e8f0")

    # Card 3: label usage distribution
    new_card(4, 17.5, 44.5, 27.5, "OBSERVATION 3: LABEL VOCABULARY IS MOSTLY UNUSED",
             "NEE 9.2% true share → only 2.3% issued (0.5% correct)", bar_color="#f59e0b")
    ax3 = fig.add_axes([0.065, 0.215, 0.345, 0.15], facecolor="#131e33")
    cats = ["Supported\n(66.2% correct)", "Refuted\n(94.4% correct)", "Not Enough\nEvidence\n(0.5% correct)", "Conflicting /\ncherrypicking\n(43.6% correct)"]
    gold_sh = [26.5, 57.7, 9.2, 6.6]
    pred_sh = [19.0, 68.5, 2.3, 10.1]
    xx = range(4)
    w3 = 0.36
    b1 = ax3.bar([i - w3 / 2 for i in xx], gold_sh, w3, color="#3b82f6", label="AVeriTeC gold label share (n = 196)")
    b2 = ax3.bar([i + w3 / 2 for i in xx], pred_sh, w3, color="#f97316", label="Issued verdict share (2,352 verdicts)")
    for bars in (b1, b2):
        for b in bars:
            ax3.annotate(f"{b.get_height():.1f}%",
                         (b.get_x() + b.get_width() / 2, b.get_height() + 1.1),
                         ha="center", va="bottom", color="#e2e8f0", fontsize=8.2, fontweight="bold")
    ax3.set_ylim(0, 80)
    ax3.set_xticks(list(xx))
    ax3.set_xticklabels(cats, color="#e2e8f0", fontsize=8.3, fontweight="bold")
    ax3.set_ylabel("Share (%)", color="#94a3b8", fontsize=9)
    ax3.tick_params(axis="y", colors="#94a3b8", labelsize=8)
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.spines["left"].set_color("#334155")
    ax3.spines["bottom"].set_color("#334155")
    ax3.legend(loc="upper right", fontsize=7.7, facecolor="#0b1224", edgecolor="#334155", labelcolor="#e2e8f0")

    # Card 4: mechanism text + audit metrics
    new_card(51.5, 17.5, 44.5, 27.5, "ONE MECHANISM EXPLAINS ALL THREE",
             "Verdict recovery, not evidence weighing", bar_color="#34d399")
    bg.text(53.5, 36.0, "1. An article that says 'there is not enough evidence' still states a negative conclusion.",
            color="#cbd5e1", fontsize=10)
    bg.text(53.5, 33.9, "2. 2024 shared-task organisers removed fact-checking articles as leakage.",
            color="#cbd5e1", fontsize=10)
    bg.text(53.5, 30.3, "3. We sit inside that leakage on purpose to isolate the verdict layer.",
            color="#cbd5e1", fontsize=10)
    bg.text(53.5, 26.7, "4. Retrieval composition is the wrong lever; scoring rules that reward uncertainty are the right one.",
            color="#cbd5e1", fontsize=10)

    box = FancyBboxPatch((53.5, 19.5), 40, 6.7,
                         boxstyle="round,pad=0.4,rounding_size=0.8", facecolor="#0b1224",
                         edgecolor="#34d399", linewidth=1.2)
    bg.add_patch(box)
    bg.text(55, 24.2, "13 GATES · 0 FAIL", color="#34d399", fontsize=11, fontweight="bold")
    bg.text(55, 21.9, "588 blind labels · 120 unique sessions · 2,297 / 2,352 verbatim quotes, 0 cross-condition contamination",
            color="#cbd5e1", fontsize=9)

    # Footer strip
    bg.plot([4, 96], [11.4, 11.4], color="#334155", linewidth=1)
    bg.text(50, 9.2, "Trustworthy source code, prompts, verdicts and gate logs:  github.com/anaexplores/averitec-ablation",
            ha="center", color="#38bdf8", fontsize=12, fontweight="bold")
    bg.text(50, 6.3, "paper_submission.pdf (5pp before refs)   ·   slides_submission.pdf (7 slides)   ·   project_cover.png (this image)   ·   results_paper_numbers.txt   ·   pipeline/gates.py (--selftest RED 14/14)",
            ha="center", color="#94a3b8", fontsize=10)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print("wrote", OUT, f"({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    render_cover()
