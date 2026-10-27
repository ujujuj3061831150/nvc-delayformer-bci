"""Build a self-contained LaTeX source ZIP for manuscript submission."""

from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript"
OUTPUT = ROOT / "reports" / "manuscript_latex_source.zip"

files = {
    "main.tex": MANUSCRIPT / "main.tex",
    "main.bbl": MANUSCRIPT / "main.bbl",
    "supplementary.tex": MANUSCRIPT / "supplementary.tex",
    "supplementary.bbl": MANUSCRIPT / "supplementary.bbl",
    "references.bib": MANUSCRIPT / "references.bib",
}

for tex_name in ("main.tex", "supplementary.tex"):
    tex = files[tex_name].read_text(encoding="utf-8")
    for figure in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", tex):
        files[figure] = MANUSCRIPT / figure

missing = [name for name, path in files.items() if not path.is_file()]
if missing:
    raise FileNotFoundError(f"Missing submission source files: {missing}")

readme = (
    "NVC-DelayFormer manuscript source\n"
    "Compile main.tex and supplementary.tex separately with pdflatex.\n"
    "The bibliography .bbl files are included; references.bib is supplied for BibTeX regeneration.\n"
)
with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name, path in sorted(files.items()):
        archive.write(path, name)
    archive.writestr("README.txt", readme)

print(f"Built {OUTPUT} with {len(files) + 1} files")
