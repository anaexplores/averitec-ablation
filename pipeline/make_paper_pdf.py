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
@page { size: A4; margin: 20mm 18mm 22mm 18mm; }
html { -webkit-print-color-adjust: exact; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.5pt;
       line-height: 1.42; color: #111; margin: 0; }
.titleblock { text-align: center; margin-bottom: 9mm; }
.titleblock h1 { font-size: 15.5pt; line-height: 1.3; margin: 0 0 4mm 0; }
.titleblock p { margin: 1.2mm 0; font-size: 11pt; }
blockquote { border-left: 2.5pt solid #999; margin: 3mm 6mm; padding: 1mm 0 1mm 4mm;
             color: #333; font-size: 9.5pt; text-align: left; }
h2 { font-size: 12pt; margin: 6mm 0 2mm 0; page-break-after: avoid; }
h3 { font-size: 10.5pt; margin: 4.5mm 0 1.5mm 0; page-break-after: avoid; }
p { margin: 0 0 2.2mm 0; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 2.5mm 0; padding-left: 6mm; }
li { margin-bottom: 1.2mm; text-align: justify; hyphens: auto; }
table { border-collapse: collapse; width: 100%; font-size: 8.7pt; margin: 2mm 0 3mm 0; }
th, td { border: 0.5pt solid #888; padding: 1.1mm 1.6mm; text-align: left; vertical-align: top; }
th { background: #ececec; }
img { max-width: 100%; }
a { color: #1a4e8a; text-decoration: none; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 9pt;
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
    i = frag.find("<h2")
    if i < 0:
        raise SystemExit("no <h2> in pandoc output; layout assumptions broken")
    head, body = frag[:i], frag[i:]
    html = ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<title>Submission</title><style>" + CSS + "</style></head><body>"
            "<div class='titleblock'>" + head + "</div>" + body + "</body></html>")
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
