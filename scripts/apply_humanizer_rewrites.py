import re
from pathlib import Path

def main():
    report_path = Path("reports/academic_humanizer_audit_report.md")
    main_tex_path = Path("manuscript/main.tex")
    supp_tex_path = Path("reports/Supplementary_Material.tex")
    supp2_tex_path = Path("manuscript/supplementary.tex")

    report_text = report_path.read_text(encoding="utf-8")
    main_tex = main_tex_path.read_text(encoding="utf-8")
    supp_tex = supp_tex_path.read_text(encoding="utf-8")

    blocks = re.split(r'\n(?=### P\d+)', report_text)[1:]
    rewrites = []

    for b in blocks:
        p_id = re.search(r'### (P\d+)', b).group(1)
        doc_match = re.search(r'\*\*Document & Location:\*\*\s*`([^`]+)`', b)
        doc_loc = doc_match.group(1) if doc_match else ""
        verdict_match = re.search(r'\*\*Audit Verdict:\*\*\s*(.*)', b)
        verdict = verdict_match.group(1).strip() if verdict_match else ""

        if "Rewrite" not in verdict:
            continue

        orig_match = re.search(r'\*\*Original Verbatim Text:\*\*.*?\n\s*```latex\s*\n(.*?)\n\s*```', b, re.DOTALL)
        rec_match = re.search(r'\*\*Recommended Text:\*\*.*?\n\s*```latex\s*\n(.*?)\n\s*```', b, re.DOTALL)

        if not orig_match or not rec_match:
            print(f"Failed parsing {p_id}")
            continue

        orig = orig_match.group(1)
        rec = rec_match.group(1)

        orig_lines = orig.split("\n")
        if all(line.startswith("  ") or line == "" for line in orig_lines):
            orig = "\n".join(line[2:] if line.startswith("  ") else line for line in orig_lines)

        rec_lines = rec.split("\n")
        if all(line.startswith("  ") or line == "" for line in rec_lines):
            rec = "\n".join(line[2:] if line.startswith("  ") else line for line in rec_lines)

        rewrites.append({
            "p_id": p_id,
            "doc_loc": doc_loc,
            "orig": orig.strip(),
            "rec": rec.strip()
        })

    print(f"Total rewrites to apply: {len(rewrites)}")

    main_replaced = 0
    supp_replaced = 0

    for r in rewrites:
        p_id = r["p_id"]
        doc = r["doc_loc"]
        orig = r["orig"]
        rec = r["rec"]

        if "main.tex" in doc:
            if orig not in main_tex:
                raise ValueError(f"Orig for {p_id} not found in main.tex")
            if main_tex.count(orig) > 1:
                raise ValueError(f"Orig for {p_id} appears multiple times in main.tex")
            main_tex = main_tex.replace(orig, rec, 1)
            main_replaced += 1
        else:
            if orig not in supp_tex:
                raise ValueError(f"Orig for {p_id} not found in supp.tex")
            if supp_tex.count(orig) > 1:
                raise ValueError(f"Orig for {p_id} appears multiple times in supp.tex")
            supp_tex = supp_tex.replace(orig, rec, 1)
            supp_replaced += 1

    print(f"Applied {main_replaced} rewrites to main.tex")
    print(f"Applied {supp_replaced} rewrites to Supplementary_Material.tex")
    print(f"Total applied: {main_replaced + supp_replaced}")

    # Write files
    main_tex_path.write_text(main_tex, encoding="utf-8")
    supp_tex_path.write_text(supp_tex, encoding="utf-8")
    supp2_tex_path.write_text(supp_tex, encoding="utf-8")
    print("Files successfully updated and synchronized.")

if __name__ == "__main__":
    main()
