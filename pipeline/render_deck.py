"""Render an editorial, light-theme project cover and a 5-slide presentation deck.

No fabricated data: all numbers come from results_paper_numbers.txt and results_score_test_main.txt.

Usage: python pipeline/render_deck.py
"""
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVER_PNG = os.path.join(ROOT, "docs", "figures", "project_cover.png")
NEE_PNG = os.path.join(ROOT, "docs", "figures", "nee_abstention.png")
ACC_PNG = os.path.join(ROOT, "docs", "figures", "ablation_accuracy.png")
SLIDES_HTML = os.path.join(ROOT, "docs", "slides.html")
SLIDES_PDF = os.path.join(ROOT, "slides_submission.pdf")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "opencode", "edge-deck-profile")

PAPER, INK, SLATE = "#FAFAF7", "#14213D", "#526072"
BLUE, TEAL, RED, AMBER = "#2563EB", "#0F766E", "#C2410C", "#B45309"
BORDER = "#E2E4E8"
JUDGE_NAMES = ["Claude\nHaiku 5.5", "DeepSeek\nV4 Pro", "Gemini\n4 Argon", "GPT-6\nLuna"]


def _style_axis(ax, accent=INK):
    ax.set_facecolor("#FFFFFF")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BORDER)
    ax.tick_params(axis="y", colors=SLATE, labelsize=8)
    ax.tick_params(axis="x", colors=INK, labelsize=8.5)
    ax.set_ylabel(ax.get_ylabel(), color=SLATE, fontsize=9)


def make_nee_chart():
    """Two horizontal bars: all NEE issued (55 of 2352) vs true NEE cases (18 * 4)."""
    fig, ax = plt.subplots(figsize=(6.8, 2.5), dpi=170, facecolor="white")
    ax.set_facecolor("white")
    y = [1, 0]
    ax.barh(y, [18, 1], color=BLUE, height=0.34, label="True NEE (18 unique claims in every judge condition)")
    ax.barh(y[1], 55, color=RED, height=0.34, label="Issued by judges (55 of 2,352)")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["True cases (unique claims)", "Issued by judges"], color=INK,
                       fontsize=9.5, fontweight="bold")
    ax.set_xlim(0, 62)
    ax.set_xlabel("Count of 'Not Enough Evidence' labels / occurrences", color=SLATE, fontsize=8.7)
    _style_axis(ax)
    ax.set_title("Gold NEE (9.2% of claims) is almost never issued (2.3% of verdicts)",
                 color=INK, fontsize=10.5, fontweight="bold", loc="left", pad=9)
    ax.text(55 + 1, 1, "18 cases in each condition", color=INK, va="center", fontsize=8.3)
    ax.text(55 + 1, 0, "55 issued (4 judges × 3 conditions)", color=INK, va="center", fontsize=8.3)
    ax.legend(loc="lower right", fontsize=7.3, frameon=False)
    fig.tight_layout()
    fig.savefig(NEE_PNG, dpi=170)
    plt.close(fig)
    return NEE_PNG


def make_acc_chart():
    """Group bar chart A/B/C accuracy per judge for slide 3."""
    fig, ax = plt.subplots(figsize=(7.1, 3.5), dpi=170, facecolor="white")
    acc = {
        "A: Support only": [74.0, 76.0, 74.5, 74.0],
        "B: + same-article caveats": [74.5, 74.5, 76.5, 75.0],
        "C: + foreign caveats": [73.0, 76.5, 76.0, 74.5],
    }
    colors = ["#2563EB", "#0F766E", "#B45309"]
    x = range(4)
    for idx, (label, values) in enumerate(acc.items()):
        offset = (idx - 1) * 0.26
        ax.bar([i + offset for i in x], values, 0.25, label=label, color=colors[idx])
    ax.set_ylim(50, 85)
    ax.axhline(57.7, color=RED, linestyle="--", linewidth=1.3, label="Baseline (Refuted): 57.7%")
    for bars in ax.patches:
        ax.annotate(f"{bars.get_height():.1f}%",
                    (bars.get_x() + bars.get_width() / 2, bars.get_height() + 0.8),
                    ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(list(x))
    ax.set_xticklabels(JUDGE_NAMES, color=INK, fontsize=8.6, fontweight="bold")
    ax.set_ylabel("Exact-match accuracy (%)", color=SLATE, fontsize=9)
    ax.legend(loc="upper right", fontsize=7.7, frameon=False)
    _style_axis(ax)
    ax.set_title("4 judge models: same accuracy band within 3.5 pp (73.0%–76.5%)", color=INK,
                 fontsize=11, fontweight="bold", loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(ACC_PNG, dpi=170)
    plt.close(fig)
    return ACC_PNG


def _card(ax, x, y, w, h, label, label_color):
    card = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=0.8",
                          facecolor="#FFFFFF", edgecolor=BORDER, linewidth=1.0)
    ax.add_patch(card)
    ax.plot([x + 1.4, x + 1.4], [y + h - 1.5, y + h - 1.5], color=label_color, linewidth=3)
    ax.text(x + 1.4, y + h - 3.7, label, color=label_color, fontsize=11.0, fontweight="bold")


def render_cover():
    fig = plt.figure(figsize=(16, 9), dpi=150, facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=PAPER)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.plot([4, 96], [96.5, 96.5], color=INK, lw=1.5)
    ax.text(4, 93.0, "APART RESEARCH   ·   AI x EPISTEMICS SPRINT 2026   ·   TRACK 1: MODEL EPISTEMICS & DECISION-MAKING EVALS",
            color=BLUE, fontsize=10.2, fontweight="bold", family="sans-serif")
    ax.text(4, 87.4, "Caveats In, Verdicts Unchanged", color=INK, fontsize=25, fontweight="bold", family="Georgia")
    ax.text(4, 83.3, "A pre-declared retrieval-context ablation of LLM fact-check judges on AVeriTeC",
            color=SLATE, fontsize=13.2, family="sans-serif")
    ax.text(4, 79.8, "196 claims (200 initial − 4 pre-declared exclusions)    ·    4 judge families    ·    2,352 verdicts    ·    13 machine gates: 0 FAIL",
            color=SLATE, fontsize=10.5, family="sans-serif")

    # Dominant finding
    _card(ax, 4, 47.5, 44.5, 27.5, "OBSERVATION 3: REFUSAL TO ABSTAIN", RED)
    ax.text(7, 68.5, "1 / 216", color=RED, fontsize=31, fontweight="bold", family="Georgia")
    ax.text(7, 65.0, "correct on 'Not Enough Evidence' (0.5%)", color=INK, fontsize=11.2, fontweight="bold")
    ax.text(7, 61.6, "18 unique true NEE claims × 12 runs each.", color=SLATE, fontsize=9.2)

    ax_n = fig.add_axes([0.075, 0.465, 0.32, 0.085], facecolor="white")
    ax_n.barh([0.0], [9.2], color=BLUE, height=0.50, label="True NEE label share: 9.2% (18 of 196)")
    ax_n.barh([0.65], [2.3], color=RED, height=0.50, label="Issued by judges: 2.3% (55 of 2,352)")
    ax_n.set_ylim(-0.35, 1.15)
    ax_n.set_yticks([])
    ax_n.set_xticks([])
    ax_n.set_xlim(0, 10.5)
    _style_axis(ax_n)
    ax.text(7, 44.5, "NEE issued by judge in conditions A / B / C",
            color=INK, fontsize=8.5, fontweight="bold")
    ax.text(7, 41.3, "Claude 4 / 4 / 4 · DeepSeek 2 / 3 / 4 · Gemini 4 / 3 / 5 (1 correct, C) · GPT 7 / 8 / 7 = 55",
            color=SLATE, fontsize=8.0)

    # Ablation chart in right card
    _card(ax, 51.5, 47.5, 44.5, 27.5, "OBSERVATION 1 & 2: NO VERDICT EFFECT", BLUE)
    ax.text(53.5, 66.8, "12 / 12", color=BLUE, fontsize=25, fontweight="bold", family="Georgia")
    ax.text(53.5, 62.4, "paired McNemar tests: adj. p = 1.0000 (MDE = 3.6 pp)",
            color=INK, fontsize=10.4, fontweight="bold")

    ax_a = fig.add_axes([0.56, 0.465, 0.365, 0.085], facecolor="white")
    acc_A = [74.0, 76.0, 74.5, 74.0]
    acc_B = [74.5, 74.5, 76.5, 75.0]
    acc_C = [73.0, 76.5, 76.0, 74.5]
    short_names = ["Claude", "DeepSeek", "Gemini", "GPT"]
    x = range(4)
    for idx, (vals, color) in enumerate([(acc_A, BLUE), (acc_B, TEAL), (acc_C, AMBER)]):
        ax_a.bar([i + (idx - 1) * 0.27 for i in x], vals, 0.26, color=color, label=["A: support", "B: same caveats", "C: foreign caveats"][idx])
    ax_a.axhline(57.7, linestyle="--", color=RED, linewidth=1.1, label="baseline 57.7%")
    ax_a.set_ylim(50, 85)
    ax_a.set_xticks(list(x))
    ax_a.set_xticklabels(short_names, color=INK, fontsize=6.7, fontweight="bold")
    ax_a.set_ylabel("Accuracy (%)", color=SLATE, fontsize=8.0)
    # A / B / C labels are written below the chart rather than in a crowded legend.
    ax.text(53.5, 39.0, "A = support only  ·  B = same-article caveats  ·  C = foreign caveats",
            color=BLUE, fontsize=8.2, fontweight="bold")
    _style_axis(ax_a)
    ax.text(53.5, 43.2, "Verdicts flip on 7.7%–10.2%; judges in one condition disagree on 9.9%–12.7%.",
            color=SLATE, fontsize=8.0)

    # Bottom three signal cards.
    chips = [
        (4, "MECHANISM", "Verdict recovery, not evidence weighing", "Stated verdict already in support windows.", INK),
        (35.4, "EXECUTION PROVEN", "13 machine gates · 0 FAIL", "588 labels verified · 120 isolated sessions ·", TEAL),
        (66.8, "NEXT LEVER", "Reward honest abstention", "Credit abstention over a confident guess.", BLUE),
    ]
    for x0, label, main, sub, accent in chips:
        ax.plot([x0, x0 + 28.8], [36.0, 36.0], color=BORDER, linewidth=1.0)
        ax.text(x0, 31.8, label, color=accent, fontsize=8.7, fontweight="bold")
        ax.text(x0, 27.5, main, color=INK, fontsize=11.0, fontweight="bold")
        ax.text(x0, 23.0, sub, color=SLATE, fontsize=8.4)
        if x0 == 4:
            ax.text(x0, 19.6, "hedging windows do not matter here.", color=SLATE, fontsize=8.4)
        elif x0 == 35.4:
            ax.text(x0, 19.6, "2,297 / 2,352 verbatim quotes · 0 cross-contamination.", color=SLATE, fontsize=8.4)
        else:
            ax.text(x0, 19.6, "partial credit for honest abstention.", color=SLATE, fontsize=8.4)

    ax.plot([4, 96], [16.0, 16.0], color=BORDER, linewidth=1)
    ax.text(50, 12.0, os.path.basename(COVER_PNG), color=SLATE, fontsize=9, ha="center")
    ax.text(50, 8.2, "github.com/anaexplores/averitec-ablation",
            color=INK, fontsize=12.5, fontweight="bold", ha="center")
    ax.text(50, 4.4, "paper_submission.pdf   ·   slides_submission.pdf   ·   project_cover.png   ·   results_paper_numbers.txt   ·   pipeline/gates.py (--selftest RED 14/14)",
            color=SLATE, fontsize=9.0, ha="center")

    os.makedirs(os.path.dirname(COVER_PNG), exist_ok=True)
    fig.savefig(COVER_PNG, dpi=150)
    plt.close(fig)
    print("wrote", os.path.relpath(COVER_PNG, ROOT), f"({os.path.getsize(COVER_PNG)} bytes)")


SLIDES_CSS = """
@page { size: 297mm 167mm; margin: 0; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; }
html, body { margin: 0; padding: 0; background: #FAFAF7; color: #14213D;
             font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; }
.slide { width: 297mm; height: 167mm; padding: 12mm 15mm; position: relative;
         page-break-after: always; overflow: hidden; background: #FAFAF7;
         border-top: 2px solid #14213D; display: flex; flex-direction: column;
         justify-content: space-between; }
.slide:last-child { page-break-after: auto; }
.kicker { color: #2563EB; font-size: 9.5pt; font-weight: 700; letter-spacing: 0.8px;
          text-transform: uppercase; margin-bottom: 3mm; }
h1 { font-family: Georgia, serif; font-size: 24pt; line-height: 1.22; margin: 0 0 4mm 0; color: #14213D; }
h2 { font-family: Georgia, serif; font-size: 18pt; line-height: 1.25; margin: 0 0 3mm 0; color: #14213D; }
h3 { font-size: 10.5pt; margin: 0 0 2mm 0; color: #2563EB; text-transform: uppercase; letter-spacing: 0.6px; }
p, li { font-size: 10.5pt; line-height: 1.42; color: #526072; margin: 0 0 2.0mm 0; }
ul { margin: 0; padding-left: 5mm; }
.grid-2 { display: grid; grid-template-columns: 44% 54%; gap: 2%; flex: 1; align-items: stretch; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; }
.card { background: #FFFFFF; border: 1px solid #E2E4E8; border-radius: 2mm; padding: 4.5mm 5mm; }
.big-num { font-family: Georgia, serif; font-size: 43pt; font-weight: 700; color: #C2410C; line-height: 1.0; margin-bottom: 3mm; }
.big-num.red { color: #C2410C; }
.big-num.blue { color: #2563EB; }
.big-num.teal { color: #0F766E; }
table { width: 100%; border-collapse: collapse; font-size: 8.4pt; margin-top: 1.5mm; }
th, td { border: 1px solid #E2E4E8; padding: 1.4mm 1.8mm; text-align: left; color: #14213D; }
th { background: #F0EFEC; color: #2563EB; font-weight: 700; }
.footer { display: flex; justify-content: space-between; align-items: center;
          border-top: 1px solid #E2E4E8; padding-top: 2.5mm; margin-top: 3mm;
          font-size: 8.5pt; color: #526072; }
code { font-family: Consolas, monospace; font-size: 8.8pt; color: #2563EB; }
.callout { border-top: 1px solid #E2E4E8; padding-top: 2.5mm; margin-top: 2.5mm; font-size: 9.2pt; }
"""


def build_slides_html():
    nee_uri = "file:///" + make_nee_chart().replace("\\", "/")
    acc_uri = "file:///" + make_acc_chart().replace("\\", "/")
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><style>{SLIDES_CSS}</style></head><body>

<!-- SLIDE 1: title -->
<div class="slide">
  <div>
    <div class="kicker">Apart Research · AI x Epistemics Research Sprint · November 2026 · Track 1</div>
    <h1 style="font-size:29pt; margin-top:1mm;">Caveats In, Verdicts Unchanged</h1>
    <p style="font-size:13pt; color:#526072; margin-bottom:8mm;">
      A pre-declared retrieval-context ablation of LLM fact-check judges on AVeriTeC.<br>
      <strong style="color:#14213D;">Ana</strong> (<code>github.com/anaexplores</code>) · Independent Researcher · With Apart Research
    </p>
    <div class="grid-3" style="margin-top:6mm;">
      <div class="card">
        <h3>Central finding (seconds)</h3>
        <div class="big-num">1 / 216</div>
        <p><strong>correct</strong> on 'Not Enough Evidence' (0.5%). The abstention label is true on 9.2% of claims, but issued in just 2.3% of 2,352 verdicts.</p>
      </div>
      <div class="card">
        <h3>Ablation control</h3>
        <div class="big-num blue">12 / 12</div>
        <p>Paired exact McNemar comparisons across 4 families and 3 contexts: <strong>Holm-adjusted p = 1.0000</strong>. Caveat windows do <strong>not</strong> move verdicts, and foreign caveats do <strong>not</strong> degrade them.</p>
      </div>
      <div class="card">
        <h3>Audit stability</h3>
        <div class="big-num teal">13 / 13</div>
        <p>Machine gates PASS (14/14 red-on-violation self-tests): 588 blind labels, 120 isolated judge sessions, 2,297 / 2,352 verbatim quotes, <strong>0</strong> cross-condition contamination.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>github.com/anaexplores/averitec-ablation</span><span>Slide 1 / 5</span>
  </div>
</div>

<!-- SLIDE 2: the principal finding -->
<div class="slide">
  <div>
    <div class="kicker">Observation 3 · Key diagnostic result</div>
    <h1>Judges almost never abstain: 1 correct verdict in 216 attempts on "Not Enough Evidence"</h1>
    <div class="grid-2">
      <div class="card">
        <div class="big-num">1 / 216 (0.5%)</div>
        <p><strong>18 unique NEE claims × 12 runs</strong> (4 judges × 3 conditions = 216 attempts). The judge gives a determinate Refuted or Conflicting verdict instead of abstaining.</p>
        <h3>Per-label accuracy on label (gold → issued → correct)</h3>
        <table>
          <tr><th>Label</th><th>Gold share</th><th>Issued share</th><th>Accuracy on that label</th></tr>
          <tr><td>Supported</td><td>26.5%</td><td>448/2352 = 19.0%</td><td>413/624 = 66.2%</td></tr>
          <tr><td>Refuted</td><td>57.7%</td><td>1611/2352 = 68.5%</td><td>1280/1356 = 94.4%</td></tr>
          <tr><td><strong>Not Enough Evidence</strong></td><td>9.2%</td><td>55/2352 = 2.3%</td><td><strong>1/216 = 0.5%</strong></td></tr>
          <tr><td>Conflicting / Cherrypicking</td><td>6.6%</td><td>238/2352 = 10.1%</td><td>68/156 = 43.6%</td></tr>
        </table>
        <p class="callout">Of 215 misses, 176 land on Refuted and 31 on Conflicting. Exact-match accuracy of 73.0%–76.5% sits 15–19 points above the 57.7% majority baseline almost entirely through <strong>Refuted (94.4%)</strong>.</p>
      </div>
      <div class="card" style="display:flex; flex-direction:column; justify-content:flex-start;">
        <h3>Issued by judge, conditions A / B / C (sum = 55/2352)</h3>
        <table>
          <tr><th>Judge</th><th>A</th><th>B</th><th>C</th><th>True NEE correct</th></tr>
          <tr><td><code>claude-haiku-5-5</code></td><td>4</td><td>4</td><td>4</td><td>0</td></tr>
          <tr><td><code>deepseek-v4-pro</code></td><td>2</td><td>3</td><td>4</td><td>0</td></tr>
          <tr><td><code>gemini-4-argon</code></td><td>4</td><td>3</td><td>5</td><td><strong>1</strong></td></tr>
          <tr><td><code>gpt-6-luna</code></td><td>7</td><td>8</td><td>7</td><td>0</td></tr>
        </table>
        <img src="{nee_uri}" alt="True versus issued NEE share" style="max-width:100%; margin-top:2mm; object-fit:contain;">
        <p style="font-size:9.2pt; color:#526072;">Every judge under-issues the endangered "Not Enough Evidence" label even though the support excerpt states it outright.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Observation 3 · Refusal to abstain (source: results_paper_numbers.txt)</span>
    <span>Slide 2 / 5</span>
  </div>
</div>

<!-- SLIDE 3: null effect -->
<div class="slide">
  <div>
    <div class="kicker">Observation 1 &amp; 2 · Ablation controls</div>
    <h1>Caveat windows do not move verdicts, and foreign caveats do not degrade them</h1>
    <div class="grid-2">
      <div class="card" style="padding-top:2mm; padding-bottom:2mm;">
        <img src="{acc_uri}" alt="Exact-match accuracy by judge and condition" style="width:100%; object-fit:contain;">
      </div>
      <div class="card">
        <h3>Exact McNemar pairs (b, c) and two-sided p</h3>
        <table>
          <tr><th>Comparison</th><th>Claude</th><th>DeepSeek</th><th>Gemini</th><th>GPT</th></tr>
          <tr><td><strong>A vs B</strong> (mandatory)</td><td>2, 3 (1.0000)</td><td>5, 2 (0.4531)</td><td>3, 7 (0.3438)</td><td>3, 5 (0.7266)</td></tr>
          <tr><td><strong>B vs C</strong> (mandatory)</td><td>5, 2 (0.4531)</td><td>2, 6 (0.2891)</td><td>3, 2 (1.0000)</td><td>4, 3 (1.0000)</td></tr>
          <tr><td><strong>A vs C</strong> (optional)</td><td>4, 2 (0.6875)</td><td>3, 4 (1.0000)</td><td>3, 6 (0.5078)</td><td>4, 5 (1.0000)</td></tr>
        </table>
        <ul style="margin-top:3mm;">
          <li><strong>All 12 Holm-adjusted p = 1.0000.</strong> Minimum detectable effect = 7 net discordant pairs = 3.6 pp.</li>
          <li><strong>Little churn:</strong> a judge changes its verdict on 4.1%–8.2% per pair and 7.7%–10.2% across all three, while two judges disagree on 9.9%–12.7% (meaning agreement of 88.2% A, 90.1% B, 87.3% C).</li>
          <li><strong>Sensitivity (n = 176):
            </strong> removing the DeepSeek A/batch00 fallback cell yields A vs B b=3 c=1 (p=0.6250) and A vs C b=3 c=3 (p=1.0000).</li>
        </ul>
        <p class="callout">Accuracy is verdict-only on windows from the gold fact-checking article. This is a much easier task than the official AVeriTeC leaderboard, whose 2024 winner TUDA_MAI scored 63% on verdict <em>plus</em> retrieved evidence quality.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Observation 1 &amp; 2 · Ablation does not move verdicts</span>
    <span>Slide 3 / 5</span>
  </div>
</div>

<!-- SLIDE 4: mechanism and proof of isolation -->
<div class="slide">
  <div>
    <div class="kicker">Mechanism &amp; empirical hygiene</div>
    <h2>The model recovers the stated conclusion rather than weigh evidence, while 13 gates prove the experiment stayed isolated</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Why caveat changes do nothing</h3>
        <p><strong>1.</strong> The fact-checking article writes the verdict outright. The BM25 support windows contain that decisive sentence, so extra hedging windows have no additional work to do.</p>
        <p><strong>2.</strong> An article concluding "there is not enough evidence" still states a conclusion. Judges report that conclusion as Refuted or Conflicting rather than abstaining.</p>
        <p><strong>3.</strong> The 2024 shared-task organisers removed fact-checking articles from their knowledge store as leakage. We sit inside that leakage purposely to isolate the verdict layer from retrieval.</p>
      </div>
      <div class="card">
        <h3>13 machine-enforced gates (14/14 red on violation)</h3>
        <ul>
          <li><strong>Labels:</strong> all 588 <code>labels_secret</code> entries recomputed from source data: 0 mismatches; no gold label appears in any prompt.</li>
          <li><strong>Treatment identity:</strong> all 30 batch headers share one sha256 (<code>f948718f22f07be4</code>); every condition shows exactly the same 196-claim batch order.</li>
          <li><strong>Sessions:</strong> 120 unique identifiers recovered from OpenCode session store, zero sessions reused and zero verdicts by the orchestrator.</li>
          <li><strong>Quotes:</strong> 2,297 / 2,352 verbatim within own condition, <strong>0 cross-condition contamination</strong> (claude 0.9949 · DeepSeek 0.9218 · gemini 0.9983 · gpt 0.9915).</li>
          <li><strong>Traceability:</strong> all 40 report figures trace to <code>results_paper_numbers.txt</code> or <code>data/references_provenance.json</code>, and all 21 report links resolve.</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Mechanism &amp; execution: 13 PASS, 0 FAIL</span>
    <span>Slide 4 / 5</span>
  </div>
</div>

<!-- SLIDE 5: implications and future steps -->
<div class="slide">
  <div>
    <div class="kicker">Implications, Limits &amp; Reproducibility</div>
    <h2>Retrieval composition is the wrong lever; scoring rules should reward honest uncertainty</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Implications and honest limits</h3>
        <ul>
          <li><strong>AI safety reading:</strong> Exact-match grading on a four-way vocabulary gives 0 to both a wrong guess and an honest abstention, so confident guessing dominates (Kalai et al., 2025).</li>
          <li><strong>Calibrated judgement measurement:</strong> a benchmark reporting 74.0% accuracy while its abstention class scores 0.5% measures something other than calibrated judgement.</li>
          <li><strong>Not established:</strong> caveats are not universally useless. Windows share the label-producing article, so this is verdict recovery, not independent verification.</li>
          <li><strong>Limitations:</strong> single window configuration, 20-claim sessions, categorical labels only, 3 Supported + 1 Refuted fetch exclusions, one seed (n = 196), no caveats-only Condition D.</li>
        </ul>
      </div>
      <div class="card">
        <h3>Three concrete next steps</h3>
        <ol style="padding-left:5mm;">
          <li>Re-run with partial credit for abstention and a penalty for a confident wrong verdict, to test the incentive mechanism instead of assuming it.</li>
          <li>Evaluate on evidence that no longer states the verdict sentence, so the judge must weigh competing evidence.</li>
          <li>Elicit calibrated confidence P(True) / P(IK) with one claim per session instead of batching twenty.</li>
        </ol>
        <div class="callout">
          <strong>Repository:</strong> <code>github.com/anaexplores/averitec-ablation</code><br>
          <strong>Report:</strong> <code>paper_submission.pdf</code> (5 pages before refs) · <strong>Deck:</strong> <code>slides_submission.pdf</code> (5 slides) · <strong>Cover:</strong> <code>docs/figures/project_cover.png</code><br>
          <strong>Repro commands:</strong> <code>python pipeline/gates.py --check-links</code> and <code>python pipeline/make_paper_numbers.py</code>
        </div>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Conclusion &amp; Reproducibility</span>
    <span>Slide 5 / 5</span>
  </div>
</div>

</body></html>"""
    with open(SLIDES_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", os.path.relpath(SLIDES_HTML, ROOT))


def build_slides_pdf():
    if os.path.exists(SLIDES_PDF):
        os.remove(SLIDES_PDF)
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--user-data-dir={PROFILE}",
           f"--print-to-pdf={SLIDES_PDF}",
           "file:///" + SLIDES_HTML.replace("\\", "/")]
    subprocess.run(cmd, check=True, timeout=120)
    print("wrote", os.path.relpath(SLIDES_PDF, ROOT), f"({os.path.getsize(SLIDES_PDF)} bytes)")


def main():
    render_cover()
    build_slides_html()
    build_slides_pdf()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
