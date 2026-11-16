"""Build the submission PDF from docs/PAPER_DRAFT.md (official template structure).

NEW sprint work. No LaTeX toolchain on this machine, so the route is:
pandoc renders the markdown to an HTML fragment, a print stylesheet formats it
(template-like title block, numbered sections, A4), and Edge headless prints
it to PDF. The build is verified afterwards: total pages, the page where
References starts (the 8-page limit applies to main text before references),
required sections present, key numbers present, link annotations alive.

    python pipeline/make_paper_pdf.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "docs", "PAPER_DRAFT.md")
HTML = os.path.join(ROOT, "docs", "paper.html")
PDF = os.path.join(ROOT, "paper_submission.pdf")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"),
                       "opencode", "edge-pdf-profile")

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
html { -webkit-print-color-adjust: exact; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.3pt;
       line-height: 1.38; color: #111; margin: 0; }
.titlebox { border-top: 2.5pt solid #111; border-bottom: 0.8pt solid #111;
            padding: 5mm 4mm; margin: 0 0 5mm 0; text-align: center; }
.titlebox h1 { font-size: 16pt; line-height: 1.28; margin: 0; font-weight: bold; }
.titlebox h1 sup { font-size: 10pt; font-weight: normal; }
.authorblock { text-align: center; margin: 4mm 0 5mm 0; font-size: 10.5pt; line-height: 1.35; }
.authorblock .with { margin-top: 3mm; }
.abstractblock { margin: 0 14mm 4mm 14mm; }
.abstractblock h2 { text-align: center; font-size: 11.5pt; margin: 0 0 2.5mm 0; }
.abstractblock p { font-style: italic; font-size: 10pt; line-height: 1.36;
                   text-align: justify; margin: 0 0 2mm 0; }
.sprint-footnote { border-top: 0.6pt solid #555; padding-top: 1.5mm; margin: 3mm 0 5mm 0;
                   font-size: 8.8pt; color: #222; }
h2 { font-size: 12pt; margin: 5mm 0 2mm 0; page-break-after: avoid; }
h3 { font-size: 10.5pt; margin: 3.8mm 0 1.2mm 0; page-break-after: avoid; }
p { margin: 0 0 2mm 0; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 2.2mm 0; padding-left: 6mm; }
li { margin-bottom: 1mm; text-align: justify; hyphens: auto; }
table { border-collapse: collapse; width: 100%; font-size: 8.7pt; margin: 2mm 0 2.5mm 0; }
th, td { border: 0.5pt solid #888; padding: 1.1mm 1.6mm; text-align: left; vertical-align: top; }
th { background: #ececec; }
figure { margin: 2mm 0; text-align: center; }
figcaption { display: none; }
img { max-width: 95%; }
a { color: #1a4e8a; text-decoration: none; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.8pt;
       background: #f4f4f4; padding: 0 0.6mm; }
"""

REQUIRED = (
    "Caveats In, Verdicts Unchanged", "Abstract", "1. Introduction",
    "2. Related Work", "3. Methods", "4. Results", "5. Discussion and Limitations",
    "6. Conclusion", "Code and Data", "References", "LLM Usage Statement",
    "Limitations and Dual-Use", "73.0% to 76.5%", "0.06", "22.1%",
)


def build_html():
    frag = subprocess.run(
        ["pandoc", DRAFT, "-f", "markdown", "-t", "html5", "--wrap=none"],
        capture_output=True, text=True, check=True,
    ).stdout
    m_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", frag, re.S)
    m_abs = re.search(r"(<h2[^>]*>Abstract</h2>.*?)<h2", frag, re.S)
    i_intro = frag.find("<h2 id=\"introduction\"")
    if not (m_h1 and m_abs and i_intro > 0):
        raise SystemExit("could not locate title/abstract/intro in pandoc output")
    title_html = m_h1.group(1)
    abs_html = m_abs.group(1)
    rest_html = frag[i_intro:]
    header_html = (
        f"<div class='titlebox'><h1>{title_html}<sup>1</sup></h1></div>"
        "<div class='authorblock'>"
        "<div><strong>Ana</strong> (GitHub <code>anaexplores</code>)</div>"
        "<div>Independent researcher</div>"
        "<div class='with'><strong>With</strong><br>Apart Research</div>"
        "</div>"
        f"<div class='abstractblock'>{abs_html}</div>"
        "<div class='sprint-footnote'><sup>1</sup> Research conducted at the "
        "<a href='https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15'>"
        "AI x Epistemics Research Sprint</a>, November 2026.</div>"
    )
    html = ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<title>Submission</title><style>" + CSS + "</style></head><body>"
            + header_html + rest_html + "</body></html>")
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", os.path.relpath(HTML, ROOT))


def build_pdf():
    if os.path.exists(PDF):
        os.remove(PDF)
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--user-data-dir={PROFILE}",
           f"--print-to-pdf={PDF}",
           "file:///" + HTML.replace("\\", "/")]
    subprocess.run(cmd, check=True, timeout=120)
    if not (os.path.exists(PDF) and os.path.getsize(PDF) > 10000):
        raise SystemExit("Edge did not produce a usable PDF")
    print("wrote", os.path.relpath(PDF, ROOT), f"({os.path.getsize(PDF)} bytes)")


def inject_links():
    """Edge headless exports only the first link as an annotation; add the rest.

    Every URL that appears as printed text (the reference list, Code and Data)
    gets a Link annotation over its exact bounding box, so the submission
    checklist requirement "links work" holds inside the PDF itself.
    """
    import io
    import re as _re
    import pdfplumber
    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import Link

    url_re = _re.compile(r"https?://")
    boxes = []
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages):
            for w in page.extract_words():
                if not url_re.match(w["text"]):
                    continue
                url = w["text"].rstrip(".,;:)]")
                rect = (w["x0"], page.height - w["bottom"] - 1,
                        w["x1"], page.height - w["top"] + 1)
                boxes.append((pno, rect, url))
    data = open(PDF, "rb").read()
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    writer.append(reader)
    for pno, rect, url in boxes:
        writer.add_annotation(pno, Link(rect=rect, url=url))
    tmp = PDF + ".tmp"
    with open(tmp, "wb") as f:
        writer.write(f)
    os.replace(tmp, PDF)
    print(f"link annotations added over printed URLs: {len(boxes)}")


def verify():
    import pdfplumber
    from pypdf import PdfReader
    with pdfplumber.open(PDF) as pdf:
        pages = len(pdf.pages)
        texts = [(p.extract_text() or "") for p in pdf.pages]
    flat = re.sub(r"\s+", " ", "\n".join(texts))
    refs_page = next((n + 1 for n, t in enumerate(texts) if "References" in t), None)
    links = 0
    for pg in PdfReader(PDF).pages:
        for a in (pg.get("/Annots") or []):
            if a.get_object().get("/Subtype") == "/Link":
                links += 1
    print(f"pages total: {pages}")
    print(f"References heading first appears on page: {refs_page}")
    if refs_page:
        print(f"main text before references: at most {refs_page - 1} pages (hard limit 8, recommended ~4)")
    print(f"link annotations in PDF: {links}")
    if links < 17:
        print("FAIL: expected at least 17 link annotations (1 title link + 16 printed URLs)")
        return 1
    missing = [k for k in REQUIRED if k not in flat]
    if missing:
        print("MISSING STRINGS:", missing)
        return 1
    if texts and "file:///" in texts[0]:
        print("FAIL: Edge printed a header/footer with the file URL; adjust flags")
        return 1
    print("all required sections and key numbers present")
    return 0


def main():
    build_html()
    build_pdf()
    inject_links()
    return verify()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
