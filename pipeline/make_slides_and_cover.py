"""Build the 16:9 slide deck (slides_submission.pdf) and its dark figure.

All numbers are taken verbatim from results_paper_numbers.txt and results_score_test_main.txt.

    python pipeline/make_slides_and_cover.py
"""
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cover_layout import render_cover

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG1_DARK_PNG = os.path.join(ROOT, "docs", "figures", "fig1_dark_slide.png")
SLIDES_HTML = os.path.join(ROOT, "docs", "slides.html")
SLIDES_PDF = os.path.join(ROOT, "slides_submission.pdf")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"),
                       "opencode", "edge-slides-profile")


def build_cover_png():
    """Render the project cover PNG via cover_layout.render_cover()."""
    render_cover()


SLIDES_CSS = """
@page { size: 297mm 167mm; margin: 0; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; }
html, body { margin: 0; padding: 0; background: #0f172a; color: #f8fafc;
             font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; }
.slide { width: 297mm; height: 167mm; padding: 12mm 15mm; position: relative;
         page-break-after: always; overflow: hidden; background: #0f172a;
         display: flex; flex-direction: column; justify-content: space-between; }
.slide:last-child { page-break-after: auto; }
.top-tag { color: #38bdf8; font-size: 9.5pt; font-weight: 700; letter-spacing: 0.6px;
           text-transform: uppercase; margin-bottom: 2mm; }
h1 { font-size: 24pt; line-height: 1.18; margin: 0 0 3mm 0; color: #f8fafc; }
h2 { font-size: 18pt; line-height: 1.2; margin: 0 0 3mm 0; color: #f8fafc; }
h3 { font-size: 11.5pt; margin: 0 0 2mm 0; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.4px; }
p, li { font-size: 10.5pt; line-height: 1.4; color: #cbd5e1; margin: 0 0 2mm 0; }
ul { margin: 0; padding-left: 5mm; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; flex: 1; align-items: stretch; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5mm; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 3mm; padding: 4.5mm 5.5mm; }
.card-accent { border-left: 4px solid #38bdf8; }
.card-warn { border-left: 4px solid #f87171; }
.big-num { font-size: 26pt; font-weight: 800; color: #38bdf8; line-height: 1.05; margin-bottom: 1.5mm; }
.big-num.red { color: #f87171; }
.big-num.green { color: #34d399; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 1.5mm; }
th, td { border: 1px solid #334155; padding: 1.8mm 2.2mm; text-align: left; color: #e2e8f0; }
th { background: #0f172a; color: #38bdf8; font-weight: 700; }
.footer { display: flex; justify-content: space-between; align-items: center;
          border-top: 1px solid #334155; padding-top: 2.5mm; font-size: 8.5pt; color: #94a3b8; }
.badge { display: inline-block; padding: 0.8mm 2.2mm; border-radius: 1.5mm; font-size: 8.5pt;
         font-weight: 700; background: #0284c7; color: #fff; margin-right: 2mm; }
.badge.pre { background: #475569; }
code { font-family: Consolas, monospace; font-size: 9pt; color: #38bdf8; }
"""


def build_dark_slide_chart():
    fig, ax = plt.subplots(figsize=(6.8, 4.2), dpi=200, facecolor="#1e293b")
    ax.set_facecolor("#1e293b")
    cats = ["Supported\n(acc: 66.2%)", "Refuted\n(acc: 94.4%)",
            "Not Enough\nEvidence\n(acc: 0.5%)", "Conflicting /\nCherrypicking\n(acc: 43.6%)"]
    gold_sh = [26.5, 57.7, 9.2, 6.6]
    pred_sh = [19.0, 68.5, 2.3, 10.1]
    xr = range(len(cats))
    w2 = 0.36
    b1 = ax.bar([i - w2 / 2 for i in xr], gold_sh, w2, label="AVeriTeC gold label share (n = 196)", color="#3b82f6")
    b2 = ax.bar([i + w2 / 2 for i in xr], pred_sh, w2, label="Issued verdict share (2,352 verdicts)", color="#f97316")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.1f}%",
                        (b.get_x() + b.get_width() / 2, b.get_height() + 1.0),
                        ha="center", va="bottom", color="#f8fafc", fontsize=8.5, fontweight="bold")
    ax.set_ylim(0, 78)
    ax.set_xticks(list(xr))
    ax.set_xticklabels(cats, color="#e2e8f0", fontsize=8.5, fontweight="bold")
    ax.set_ylabel("Share (%)", color="#cbd5e1", fontsize=9.5)
    ax.set_title("Gold label share vs. issued verdicts (4 judges × 3 conditions)",
                 color="#f8fafc", fontsize=10.5, fontweight="bold", pad=10)
    ax.tick_params(axis="y", colors="#94a3b8", labelsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color("#475569")
    ax.spines["bottom"].set_color("#475569")
    ax.legend(loc="upper right", fontsize=8, facecolor="#0f172a", edgecolor="#334155", labelcolor="#e2e8f0")
    fig.tight_layout()
    fig.savefig(FIG1_DARK_PNG, dpi=200)
    plt.close(fig)


def build_slides_html():
    build_dark_slide_chart()
    fig_uri = "file:///" + FIG1_DARK_PNG.replace("\\", "/")
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><style>{SLIDES_CSS}</style></head><body>

<!-- SLIDE 1 -->
<div class="slide">
  <div>
    <div class="top-tag">Apart Research · AI x Epistemics Research Sprint · November 2026 · Track 1</div>
    <h1 style="font-size:26pt; margin-top:2mm;">Caveats In, Verdicts Unchanged</h1>
    <p style="font-size:13.5pt; color:#94a3b8; margin-bottom:6mm;">
      A Pre-Declared Retrieval-Context Ablation of LLM Fact-Check Judges on AVeriTeC<br>
      <strong style="color:#f8fafc;">Ana</strong> (<code>github.com/anaexplores</code>) · Independent Researcher · With Apart Research
    </p>
    <div class="grid-3" style="margin-top:4mm;">
      <div class="card card-accent">
        <div class="big-num">0 / 12</div>
        <h3>Caveat Ablation Effect</h3>
        <p>All 12 paired McNemar comparisons across 4 judge families &amp; 3 retrieval conditions are non-significant (Holm adj. p = 1.0000; MDE = 3.6 pp).</p>
      </div>
      <div class="card card-warn">
        <div class="big-num red">1 / 216 (0.5%)</div>
        <h3>Refusal to Abstain</h3>
        <p>On claims whose gold label is <em>Not Enough Evidence</em> (18 unique claims × 12 runs), judges were right once, issuing the label in 2.3% of verdicts vs. 9.2% true share.</p>
      </div>
      <div class="card card-accent">
        <div class="big-num green">13 / 13 PASS</div>
        <h3>Machine-Enforced Hygiene</h3>
        <p>120 isolated single-batch judge sessions, 588 blind labels verified, 2,297 / 2,352 verbatim quotes, and <strong>0</strong> cross-condition contamination.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Repository: https://github.com/anaexplores/averitec-ablation</span>
    <span>Slide 1 / 7</span>
  </div>
</div>

<!-- SLIDE 2 -->
<div class="slide">
  <div>
    <div class="top-tag">1 · Research Question &amp; Experimental Design</div>
    <h2>Does Adding Hedging ("Caveat") Windows Make LLM Judges Less Credulous?</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Three Retrieval Conditions (n = 196 Claims)</h3>
        <ul>
          <li><strong>Dataset:</strong> Official AVeriTeC benchmark (Schlichtkrull et al., 2023; CC BY-NC 4.0). Grouped by article, stratified by 4-way label, seed <code>20261115</code> (200 test claims → 196 effective after 4 pre-declared JS-only Wayback exclusions).</li>
          <li><strong>Condition A (Support only):</strong> Top 5 BM25 windows (120 words each) from the claim's fact-checking article.</li>
          <li><strong>Condition B (Relevant caveats):</strong> Condition A + 5 caveat windows (40 words each, selected by limiting markers: <em>however, but, partially, misleading</em>) from the <strong>same</strong> article.</li>
          <li><strong>Condition C (Irrelevant control):</strong> Condition A + 5 caveat windows of identical length &amp; marker density from a <strong>random other</strong> article.</li>
        </ul>
      </div>
      <div class="card">
        <h3>Judge Panel, Isolation &amp; Sprint Provenance</h3>
        <ul>
          <li><strong>4 Judge Families (never pooled):</strong> <code>claude-haiku-5-5</code>, <code>gemini-4-argon</code>, <code>gpt-6-luna</code>, <code>deepseek-v4-pro</code>.</li>
          <li><strong>Strict Cell Isolation:</strong> 120 test cells (4 judges × 3 conditions × 10 batches). Each cell runs in one fresh subagent session (125 sessions verified in store; 0 reused). Prompts never see <code>labels_secret</code>.</li>
          <li><strong>Pre-Scoring Statistical Plan:</strong> 95% Wilson CIs, exact McNemar on paired claims, Holm correction over mandatory {{A vs B, B vs C}} and optional {{A vs C}}.</li>
          <li><span class="badge pre">PREEXISTING</span> BM25 windowing &amp; marker list from <code>anaexplores/lost-caveats</code> v0.1.1.</li>
          <li><span class="badge">NEW SPRINT WORK</span> AVeriTeC split, 3-condition runner, blind-label manifests, 120 judge sessions, statistics, 13 gates &amp; report.</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Methods &amp; Isolation</span>
    <span>Slide 2 / 7</span>
  </div>
</div>

<!-- SLIDE 3 -->
<div class="slide">
  <div>
    <div class="top-tag">2 · Observation 1 &amp; Observation 2</div>
    <h2>Caveat Windows Do Not Change Verdicts, and Foreign Caveats Do Not Degrade Them</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Exact-Match Accuracy [95% Wilson CI] (n = 196)</h3>
        <table>
          <tr><th>Judge Model</th><th>A (Support)</th><th>B (+ Same Caveats)</th><th>C (+ Foreign Caveats)</th></tr>
          <tr><td><code>claude-haiku-5-5</code></td><td>145/196 = 74.0% [0.67,0.80]</td><td>146/196 = 74.5% [0.68,0.80]</td><td>143/196 = 73.0% [0.66,0.79]</td></tr>
          <tr><td><code>deepseek-v4-pro</code></td><td>149/196 = 76.0% [0.70,0.81]</td><td>146/196 = 74.5% [0.68,0.80]</td><td>150/196 = 76.5% [0.70,0.82]</td></tr>
          <tr><td><code>gemini-4-argon</code></td><td>146/196 = 74.5% [0.68,0.80]</td><td>150/196 = 76.5% [0.70,0.82]</td><td>149/196 = 76.0% [0.70,0.81]</td></tr>
          <tr><td><code>gpt-6-luna</code></td><td>145/196 = 74.0% [0.67,0.80]</td><td>147/196 = 75.0% [0.68,0.81]</td><td>146/196 = 74.5% [0.68,0.80]</td></tr>
        </table>
        <p style="margin-top:2.5mm; font-size:9pt;">
          <strong>Majority baseline (always "Refuted"):</strong> 113/196 = 57.7%.<br>
          <em>Note:</em> Verdict-only accuracy on gold-article windows is an easier task than the official AVeriTeC leaderboard (where 2024 shared-task winner TUDA_MAI reached 63% on verdict + retrieved evidence).
        </p>
      </div>
      <div class="card">
        <h3>Exact McNemar Discordant Pairs (b, c) &amp; Two-Sided p</h3>
        <table>
          <tr><th>Comparison</th><th>claude</th><th>deepseek</th><th>gemini</th><th>gpt</th></tr>
          <tr><td><strong>A vs B</strong> (mandatory)</td><td>b=2 c=3, p=1.0000</td><td>b=5 c=2, p=0.4531</td><td>b=3 c=7, p=0.3438</td><td>b=3 c=5, p=0.7266</td></tr>
          <tr><td><strong>B vs C</strong> (mandatory)</td><td>b=5 c=2, p=0.4531</td><td>b=2 c=6, p=0.2891</td><td>b=3 c=2, p=1.0000</td><td>b=4 c=3, p=1.0000</td></tr>
          <tr><td><strong>A vs C</strong> (optional)</td><td>b=4 c=2, p=0.6875</td><td>b=3 c=4, p=1.0000</td><td>b=3 c=6, p=0.5078</td><td>b=4 c=5, p=1.0000</td></tr>
        </table>
        <ul style="margin-top:2.5mm;">
          <li><strong>All 12 Holm-adjusted p = 1.0000.</strong> Floor of detectability (MDE): 7 net discordant pairs = <strong>3.6 pp</strong>.</li>
          <li><strong>Small in raw terms:</strong> A judge flips on 4.1%–8.2% of claims per pair (7.7%–10.2% across all three), whereas two judges in the same condition disagree on 9.9%–12.7% (agreement: 88.2% A, 90.1% B, 87.3% C).</li>
          <li><strong>Sensitivity run (n = 176):</strong> Excluding DeepSeek A/batch00 fallback cell gives A vs B b=3 c=1 (p=0.6250), A vs C b=3 c=3 (p=1.0000).</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Ablation Results</span>
    <span>Slide 3 / 7</span>
  </div>
</div>

<!-- SLIDE 4 -->
<div class="slide">
  <div>
    <div class="top-tag">3 · Observation 3 (Main Diagnostic Finding)</div>
    <h2>Judges Almost Never Abstain (1 / 216 Correct on "Not Enough Evidence")</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Per-Label Breakdown (4 Judges × 3 Conditions = 2,352 Verdicts)</h3>
        <table>
          <tr><th>AVeriTeC Label</th><th>Gold Share</th><th>Judges Issue It</th><th>Accuracy on Label</th></tr>
          <tr><td><strong>Supported</strong></td><td>52/196 = 26.5%</td><td>448/2352 = 19.0%</td><td>413/624 = 66.2%</td></tr>
          <tr><td><strong>Refuted</strong></td><td>113/196 = 57.7%</td><td>1611/2352 = 68.5%</td><td>1280/1356 = 94.4%</td></tr>
          <tr><td><strong>Not Enough Evidence</strong></td><td>18/196 = 9.2%</td><td>55/2352 = 2.3%</td><td><strong style="color:#f87171;">1/216 = 0.5%</strong></td></tr>
          <tr><td><strong>Conflicting / Cherrypicking</strong></td><td>13/196 = 6.6%</td><td>238/2352 = 10.1%</td><td>68/156 = 43.6%</td></tr>
        </table>
        <div class="card card-warn" style="margin-top:3mm;">
          <h3>NEE Issued by Judge &amp; Condition (verified in results_paper_numbers.txt: 55/2352 = 2.3%)</h3>
          <table>
            <tr><th>Judge</th><th>Issued NEE in A</th><th>Issued NEE in B</th><th>Issued NEE in C</th><th>Correct NEE</th></tr>
            <tr><td><code>claude-haiku-5-5</code></td><td>4</td><td>4</td><td>4</td><td><strong style="color:#f87171;">0</strong></td></tr>
            <tr><td><code>deepseek-v4-pro</code></td><td>2</td><td>3</td><td>4</td><td><strong style="color:#f87171;">0</strong></td></tr>
            <tr><td><code>gemini-4-argon</code></td><td>4</td><td>3</td><td>5</td><td><strong style="color:#34d399;">1</strong></td></tr>
            <tr><td><code>gpt-6-luna</code></td><td>7</td><td>8</td><td>7</td><td><strong style="color:#f87171;">0</strong></td></tr>
          </table>
          <p style="font-size:9pt; margin-top:1.8mm;">Each row is 18 unique true NEE claims out of 196 test-side claims. All four judges under-issue abstention even though the excerpts literally state 'there is not enough evidence'. Only Gemini (condition C) produced exactly 1 correct NEE out of 216 pooled attempts.</p>
        </div>
        <ul style="margin-top:2.2mm;">
          <li><strong>Two rare labels move in opposite directions:</strong> Judges under-issue <em>Not Enough Evidence</em> (2.3% vs. 9.2%) but over-issue <em>Conflicting</em> (10.1% vs. 6.6%), qualifying the 2024 shared-task observation that prompted LLMs overpredict rare classes.</li>
          <li><strong>Headline accuracy (73.0%–76.5%)</strong> sits 15–19 points above the 57.7% baseline almost entirely through <em>Refuted</em> (94.4%).</li>
        </ul>
      </div>
      <div class="card" style="display:flex; flex-direction:column; justify-content:center; align-items:center;">
        <img src="{fig_uri}" style="max-width:100%; max-height:102mm; object-fit:contain;">
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Abstention Failure</span>
    <span>Slide 4 / 7</span>
  </div>
</div>

<!-- SLIDE 5 -->
<div class="slide">
  <div>
    <div class="top-tag">4 · Mechanism &amp; Cleanliness Gates</div>
    <h2>Why Both Findings Happen, and How 13 Machine Gates Prove the Run Is Clean</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Unified Mechanism: Verdict Recovery</h3>
        <ul>
          <li><strong>Why caveats are inert:</strong> In AVeriTeC, the fact-checking article states its conclusion outright, and top-5 BM25 support windows contain that sentence. The judge's task reduces to <em>locating a stated conclusion</em> rather than weighing competing evidence.</li>
          <li><strong>Why abstention fails:</strong> An article concluding "there is not enough evidence" still states a negative conclusion; judges report that conclusion as <em>Refuted</em> or <em>Conflicting</em> rather than abstaining.</li>
          <li><strong>Deliberate regime isolation:</strong> 2024 shared-task organisers removed fact-check articles from their knowledge store as leakage (Schlichtkrull et al., 2024); we sit inside that regime on purpose to test verdict-layer sensitivity when the conclusion is present.</li>
        </ul>
      </div>
      <div class="card">
        <h3>13 Fail-Closed Gates (<code>pipeline/gates.py</code> · 14/14 Selftest Red)</h3>
        <ul>
          <li><strong>G1–G4 Protocol &amp; Prompt Identity:</strong> Pre-run amendments verified; 588 <code>labels_secret</code> entries recomputed from source data (0 mismatches); all 30 batch headers byte-identical (sha256 <code>f948718f22f07be4</code>).</li>
          <li><strong>G5–G9 Panel, Schema &amp; Statistics:</strong> 120 cells schema-checked; 4 pre-declared exclusions (3 Supported, 1 Refuted) identical in A/B/C; Wilson, exact McNemar &amp; Holm enforced.</li>
          <li><strong>G10 Report Traceability:</strong> All 40 numeric claims in the report trace to results files or <code>data/references_provenance.json</code>; all 21 links resolve.</li>
          <li><strong>G11–G13 Isolation &amp; Quote Provenance:</strong> 120 unique session IDs recovered from OpenCode session store; 2,297 / 2,352 quotes verbatim in own condition (claude 0.9949, gemini 0.9983, gpt 0.9915, deepseek 0.9218) with <strong>0 cross-condition contamination</strong>.</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Mechanism &amp; Gates</span>
    <span>Slide 5 / 7</span>
  </div>
</div>

<!-- SLIDE 6 -->
<div class="slide">
  <div>
    <div class="top-tag">5 · AI Safety Implications, Limitations &amp; Future Work</div>
    <h2>Retrieval Is the Wrong Lever: Scoring Rules That Reward Honest Uncertainty Are the Right One</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Implications &amp; Honest Limitations</h3>
        <ul>
          <li><strong>AI Safety Takeaway:</strong> Under exact-match scoring on a 4-way label set, a wrong guess and an honest abstention both score 0, making guessing dominant (Kalai et al., 2025). A benchmark reporting 74.0% accuracy alongside 0.5% on abstention is not measuring calibrated judgement.</li>
          <li><strong>Limitations:</strong>
            <ul>
              <li>Verdict-recovery regime (windows from the label-producing article).</li>
              <li>Single window configuration (5×120w support + 5×40w caveats); optional caveats-only Condition D not run.</li>
              <li>20 claims batched per session (intra-batch anchoring not measured); categorical verdicts without confidence elicitation.</li>
              <li>Non-neutral fetch exclusions (3 Supported, 1 Refuted); single split (n = 196).</li>
            </ul>
          </li>
        </ul>
      </div>
      <div class="card">
        <h3>Dual-Use &amp; Concrete Next Steps</h3>
        <ul>
          <li><strong>Dual-Use Guardrails:</strong>
            <ul>
              <li>Null result on verdict accuracy does <em>not</em> justify stripping caveats shown to human readers.</li>
              <li>Condition C resilience does <em>not</em> imply robustness against adversarial removal of the decisive sentence.</li>
            </ul>
          </li>
          <li><strong>Next Steps (Follow-Up Experiment):</strong>
            <ol>
              <li>Re-score and prompt judges under a rule that awards partial credit for abstention and penalises confident wrong verdicts.</li>
              <li>Evaluate on evidence sets where the conclusion sentence is removed.</li>
              <li>Elicit calibrated confidence P(True) / P(IK) one claim per session.</li>
            </ol>
          </li>
          <li style="margin-top:2mm;"><strong>Code, Prompts, Verdicts &amp; Gates:</strong><br>
            <code>https://github.com/anaexplores/averitec-ablation</code></li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Conclusion &amp; Next Steps</span>
    <span>Slide 6 / 7</span>
  </div>
</div>

<!-- SLIDE 7 -->
<div class="slide">
  <div>
    <div class="top-tag">6 · Reproducibility Artefacts</div>
    <h2>Reproducibility Artefacts: Every Claim in This Deck Regenerates from Data</h2>
    <div class="grid-2">
      <div class="card">
        <h3>Public Code and Prompts</h3>
        <table>
          <tr><th>Path in Repository</th><th>What It Contains</th></tr>
          <tr><td><code>pipeline/</code></td><td>Fetcher, 3-condition ablation runner, collector, Wilson / McNemar / Holm scorer, 13-machine-gate harness</td></tr>
          <tr><td><code>data/judge_prompts/</code></td><td>37 files · A, B, C and 3 manifest batches in every condition</td></tr>
          <tr><td><code>data/judge_outputs_ablation/</code></td><td>133 files · all 120 judge-cell JSON outputs plus 12 collected JSONL files</td></tr>
          <tr><td><code>data/session_ledger.jsonl</code></td><td>120 rows · each (judge, condition, batch) mapped to a unique session ID recovered from the OpenCode session store</td></tr>
          <tr><td><code>docs/05_METHODS_AND_DATA_PROTOCOL.md</code></td><td>Written protocol and pre-registered statistical plan</td></tr>
          <tr><td><code>docs/GATES.md</code></td><td>13-gate register, audit totals (13 PASS, 0 FAIL), and an explicit non-coverage list</td></tr>
        </table>
      </div>
      <div class="card">
        <h3>Results, Report and Links</h3>
        <ul>
          <li><strong>Repository root:</strong> <code>https://github.com/anaexplores/averitec-ablation</code></li>
          <li><strong>Official-format report (7 pages):</strong> <code>paper_submission.pdf</code></li>
          <li><strong>6-slide presentation deck (this deck):</strong> <code>slides_submission.pdf</code></li>
          <li><strong>Cover artwork:</strong> <code>docs/figures/project_cover.png</code></li>
          <li><strong>Derived numeric summary:</strong> <code>results_paper_numbers.txt</code></li>
          <li><strong>Statistical outputs:</strong> <code>results_score_test_main.txt</code> and <code>results_score_test_deepseek_excl.txt</code> (sensitivity run, n = 176)</li>
          <li><strong>Gate audit output:</strong> <code>results_gates_audit.txt</code></li>
          <li><strong>Reference verification log:</strong> <code>data/references_provenance.json</code></li>
          <li><strong>Preexisting retrieval:</strong> <code>https://github.com/anaexplores/lost-caveats</code> (v0.1.1, released before the sprint)</li>
        </ul>
        <p style="margin-top:2.5mm; font-size:9pt; color:#94a3b8;">Verify locally with <code>python pipeline/gates.py --check-links</code> and <code>python pipeline/make_paper_numbers.py</code>, which regenerates every figure and table from data and blocks fabrication.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <span>Caveats In, Verdicts Unchanged · Reproducibility Artefacts</span>
    <span>Slide 7 / 7</span>
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
    build_cover_png()
    build_slides_html()
    build_slides_pdf()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
