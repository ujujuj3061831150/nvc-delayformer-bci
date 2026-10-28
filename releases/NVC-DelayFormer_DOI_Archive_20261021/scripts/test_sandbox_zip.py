import tempfile
import zipfile
import subprocess
import re
from pathlib import Path

zip_path = Path("reports/manuscript_latex_source.zip").resolve()

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp)
    print(f"Extracted {len(list(tmp.iterdir()))} items to {tmp}")

    # Compile main.tex
    cmd_main = ["pdflatex", "-interaction=nonstopmode", "main.tex"]
    subprocess.run(cmd_main, cwd=tmp, capture_output=True, text=True)
    subprocess.run(cmd_main, cwd=tmp, capture_output=True, text=True)

    main_pdf = tmp / "main.pdf"
    print(f"Sandbox main.pdf exists: {main_pdf.exists()}")

    # Compile supplementary.tex
    cmd_supp = ["pdflatex", "-interaction=nonstopmode", "supplementary.tex"]
    subprocess.run(cmd_supp, cwd=tmp, capture_output=True, text=True)
    subprocess.run(cmd_supp, cwd=tmp, capture_output=True, text=True)

    supp_pdf = tmp / "supplementary.pdf"
    print(f"Sandbox supplementary.pdf exists: {supp_pdf.exists()}")

    main_log = (tmp / "main.log").read_text(encoding="utf-8", errors="ignore")
    supp_log = (tmp / "supplementary.log").read_text(encoding="utf-8", errors="ignore")

    m_main = re.search(r"Output written on main\.pdf \((\d+) pages", main_log)
    m_supp = re.search(r"Output written on supplementary\.pdf \((\d+) pages", supp_log)

    p_main = m_main.group(1) if m_main else "UNKNOWN"
    p_supp = m_supp.group(1) if m_supp else "UNKNOWN"

    print(f"Sandbox main.pdf pages: {p_main}")
    print(f"Sandbox supplementary.pdf pages: {p_supp}")

    overfull_main = re.findall(r"Overfull \\hbox.*", main_log)
    overfull_supp = re.findall(r"Overfull \\hbox.*", supp_log)
    print(f"Sandbox main.pdf overfull hbox count: {len(overfull_main)}")
    print(f"Sandbox supplementary.pdf overfull hbox count: {len(overfull_supp)}")
