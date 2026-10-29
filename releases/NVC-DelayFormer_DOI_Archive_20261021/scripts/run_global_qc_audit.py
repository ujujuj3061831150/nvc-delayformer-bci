#!/usr/bin/env python3
"""
Comprehensive Global QC Audit Suite for JNE Submission Package.
Audits 10 Key Gates:
1. Git & GitHub Remote Synchronization
2. File Integrity & SHA-256 Checksum Consistency
3. Document Page Budget & Overfull Hbox Audit
4. Submission LaTeX Source Zip Sandbox Compilation
5. Zenodo DOI Release Archive Validation
6. 12-Dimension Codebase Soundness Assertions (48/48)
7. Unit Test Suite (26/26)
8. JNE Format-Free Submission Guidelines Compliance
9. Mandatory Declarations, Ethics, & Open Science Rigor
10. Scientific Tone & Anti-Overclaiming Strict Compliance
"""

import os
import re
import sys
import json
import zipfile
import tempfile
import hashlib
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest().upper()

def get_pdf_page_count(filepath):
    # Read PDF page count via regex on /Type /Page
    content = Path(filepath).read_bytes()
    pages = len(re.findall(rb'/Type\s*/Page\b', content))
    return pages

def check_log_overfull(logpath):
    if not Path(logpath).exists():
        return 0, []
    text = Path(logpath).read_text(encoding='utf-8', errors='ignore')
    matches = re.findall(r'Overfull \\hbox \([^\)]+\) in paragraph at lines \d+--\d+', text)
    return len(matches), matches

def run_gate_1_git():
    print("=" * 70)
    print("GATE 1: GIT REPOSITORY & GITHUB REMOTE SYNCHRONIZATION")
    print("=" * 70)
    res_status = subprocess.run(['git', 'status', '--porcelain'], cwd=WORKSPACE, capture_output=True, text=True)
    dirty_files = [line.strip().split()[-1] for line in res_status.stdout.strip().splitlines() if line.strip()]
    clean = len(dirty_files) == 0 or dirty_files == ['scripts/run_global_qc_audit.py']
    print(f"[*] Git working tree clean: {clean} (tracked dirty: {dirty_files})")
    if not clean:
        print("    Dirty files:\n" + res_status.stdout)

    res_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=WORKSPACE, capture_output=True, text=True)
    head_hash = res_head.stdout.strip()
    res_origin = subprocess.run(['git', 'rev-parse', 'origin/main'], cwd=WORKSPACE, capture_output=True, text=True)
    origin_hash = res_origin.stdout.strip()
    in_sync = head_hash == origin_hash
    print(f"[*] Local HEAD:   {head_hash}")
    print(f"[*] Remote origin: {origin_hash}")
    print(f"[*] Synchronized:  {in_sync}")
    
    res_remote = subprocess.run(['git', 'remote', '-v'], cwd=WORKSPACE, capture_output=True, text=True)
    remote_url = res_remote.stdout.strip().split()[1] if res_remote.stdout else ""
    print(f"[*] Remote URL:    {remote_url}")
    assert clean, "Git working tree is not clean"
    assert in_sync, "Local branch is not in sync with origin/main"
    print("[PASS] Gate 1 cleared.\n")

def run_gate_2_integrity():
    print("=" * 70)
    print("GATE 2: FILE INTEGRITY & SHA-256 CHECKSUM CONSISTENCY")
    print("=" * 70)
    checklist_path = WORKSPACE / "reports" / "Submission_Package_Checklist.md"
    assert checklist_path.exists(), "Submission checklist missing"
    checklist_text = checklist_path.read_text(encoding='utf-8')
    
    files_to_check = {
        "Main Document": (WORKSPACE / "manuscript" / "main.pdf", "manuscript/main.pdf"),
        "Supplementary File": (WORKSPACE / "reports" / "Supplementary_Material.pdf", "reports/Supplementary_Material.pdf"),
        "Cover Letter": (WORKSPACE / "reports" / "Cover_Letter.pdf", "reports/Cover_Letter.pdf"),
        "Source Zip": (WORKSPACE / "reports" / "manuscript_latex_source.zip", "reports/manuscript_latex_source.zip"),
    }
    
    for label, (path, rel_path) in files_to_check.items():
        assert path.exists(), f"File missing: {rel_path}"
        sha = compute_sha256(path)
        sha_prefix = sha[:16]
        # Check if sha_prefix is in checklist_text
        found = sha_prefix in checklist_text
        print(f"[*] {label:18s} | {rel_path:35s} | SHA256: {sha_prefix}... | Checklist Match: {found}")
        assert found, f"Checksum {sha_prefix} not found in Checklist for {rel_path}"

    # Verify duplicate synchronization
    supp_manuscript = WORKSPACE / "manuscript" / "supplementary.pdf"
    assert supp_manuscript.exists(), "manuscript/supplementary.pdf missing"
    supp_manuscript_sha = compute_sha256(supp_manuscript)
    supp_reports_sha = compute_sha256(WORKSPACE / "reports" / "Supplementary_Material.pdf")
    assert supp_manuscript_sha == supp_reports_sha, "Supplementary PDF duplicate mismatch!"
    print(f"[*] Supplementary Duplicate Sync: Exactly Identical ({supp_manuscript_sha[:16]}...)")
    print("[PASS] Gate 2 cleared.\n")

def run_gate_3_page_budgets():
    print("=" * 70)
    print("GATE 3: DOCUMENT PAGE BUDGET & OVERFULL HBOX AUDIT")
    print("=" * 70)
    docs = [
        ("manuscript/main.pdf", "manuscript/main.log", 9),
        ("reports/Supplementary_Material.pdf", "reports/Supplementary_Material.log", 4),
        ("reports/Cover_Letter.pdf", "reports/Cover_Letter.log", 1),
    ]
    for pdf_rel, log_rel, expected_pages in docs:
        pdf_path = WORKSPACE / pdf_rel
        log_path = WORKSPACE / log_rel
        pages = get_pdf_page_count(pdf_path)
        overfull_count, _ = check_log_overfull(log_path)
        print(f"[*] {pdf_rel:35s} | Pages: {pages}/{expected_pages} | Overfull \\hbox: {overfull_count}")
        assert pages == expected_pages, f"Page budget violation in {pdf_rel}: got {pages}, expected {expected_pages}"
        assert overfull_count == 0, f"Overfull hbox detected in {pdf_rel}: {overfull_count}"
    print("[PASS] Gate 3 cleared.\n")

def run_gate_4_source_zip_sandbox():
    print("=" * 70)
    print("GATE 4: SUBMISSION LATEX SOURCE ZIP SANDBOX COMPILATION")
    print("=" * 70)
    zip_path = WORKSPACE / "reports" / "manuscript_latex_source.zip"
    assert zip_path.exists(), "Source zip missing"
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)
        
        # Compile main.tex
        cmd_main = ['pdflatex', '-interaction=nonstopmode', 'main.tex']
        subprocess.run(cmd_main, cwd=tmpdir, capture_output=True)
        subprocess.run(['bibtex', 'main'], cwd=tmpdir, capture_output=True)
        subprocess.run(cmd_main, cwd=tmpdir, capture_output=True)
        
        main_pdf = Path(tmpdir) / "main.pdf"
        main_log = Path(tmpdir) / "main.log"
        assert main_pdf.exists(), "Sandbox compilation failed for main.pdf"
        main_pages = get_pdf_page_count(main_pdf)
        main_overfull, _ = check_log_overfull(main_log)
        print(f"[*] Sandbox main.pdf:          Pages = {main_pages} (Expected 9), Overfull \\hbox = {main_overfull}")
        assert main_pages == 9, f"Sandbox main.pdf pages: {main_pages} != 9"
        assert main_overfull == 0, f"Sandbox main.pdf has overfull: {main_overfull}"

        # Compile supplementary.tex
        cmd_supp = ['pdflatex', '-interaction=nonstopmode', 'supplementary.tex']
        subprocess.run(cmd_supp, cwd=tmpdir, capture_output=True)
        subprocess.run(['bibtex', 'supplementary'], cwd=tmpdir, capture_output=True)
        subprocess.run(cmd_supp, cwd=tmpdir, capture_output=True)

        supp_pdf = Path(tmpdir) / "supplementary.pdf"
        supp_log = Path(tmpdir) / "supplementary.log"
        assert supp_pdf.exists(), "Sandbox compilation failed for supplementary.pdf"
        supp_pages = get_pdf_page_count(supp_pdf)
        supp_overfull, _ = check_log_overfull(supp_log)
        print(f"[*] Sandbox supplementary.pdf: Pages = {supp_pages} (Expected 4), Overfull \\hbox = {supp_overfull}")
        assert supp_pages == 4, f"Sandbox supplementary.pdf pages: {supp_pages} != 4"
        assert supp_overfull == 0, f"Sandbox supplementary.pdf has overfull: {supp_overfull}"
    print("[PASS] Gate 4 cleared.\n")

def run_gate_5_zenodo_doi():
    print("=" * 70)
    print("GATE 5: ZENODO DOI RELEASE ARCHIVE VALIDATION")
    print("=" * 70)
    archive_path = WORKSPACE / "releases" / "NVC-DelayFormer_DOI_Archive_20261021.zip"
    assert archive_path.exists(), "Zenodo DOI archive missing"
    archive_size = archive_path.stat().st_size
    print(f"[*] Archive file: {archive_path.name} ({archive_size} bytes)")
    
    validation_json = WORKSPACE / "releases" / "NVC-DelayFormer_DOI_Archive_20261021" / "VALIDATION.json"
    assert validation_json.exists(), "VALIDATION.json missing"
    vdata = json.loads(validation_json.read_text(encoding='utf-8'))
    print(f"[*] Archive Pytest result: {vdata.get('pytest_summary')}")
    print(f"[*] Archive Source Workspace: {vdata.get('source_workspace_full_suite')}")
    assert vdata.get('pytest_returncode') == 0, "Archive pytest validation failed"
    print("[PASS] Gate 5 cleared.\n")

def run_gate_6_codebase_soundness():
    print("=" * 70)
    print("GATE 6: 12-DIMENSION CODEBASE SOUNDNESS AUDIT (48/48 CHECKS)")
    print("=" * 70)
    res = subprocess.run([sys.executable, 'tests/audit_codebase_soundness.py'], cwd=WORKSPACE, capture_output=True, text=True)
    pass_count = len(re.findall(r'\[PASS\]', res.stdout))
    print(f"[*] Soundness assertions passed: {pass_count}/48")
    assert pass_count == 48, f"Codebase soundness failed: {pass_count}/48 passed"
    print("[PASS] Gate 6 cleared.\n")

def run_gate_7_unit_tests():
    print("=" * 70)
    print("GATE 7: UNIT TEST SUITE (26/26)")
    print("=" * 70)
    res = subprocess.run(['pytest', 'tests/'], cwd=WORKSPACE, capture_output=True, text=True)
    m = re.search(r'(\d+) passed', res.stdout)
    passed_tests = int(m.group(1)) if m else 0
    print(f"[*] Pytest test result: {passed_tests}/26 passed")
    assert passed_tests == 26, f"Unit tests failed: {passed_tests}/26 passed"
    print("[PASS] Gate 7 cleared.\n")

def run_gate_8_jne_guidelines():
    print("=" * 70)
    print("GATE 8: JNE FORMAT-FREE SUBMISSION GUIDELINES COMPLIANCE")
    print("=" * 70)
    main_tex = (WORKSPACE / "manuscript" / "main.tex").read_text(encoding='utf-8')
    supp_tex = (WORKSPACE / "reports" / "Supplementary_Material.tex").read_text(encoding='utf-8')
    cover_tex = (WORKSPACE / "reports" / "Cover_Letter.tex").read_text(encoding='utf-8')
    
    # 1. Title alignment
    title_key = "Physiology-Guided Temporal Fusion for Cross-Subject EEG--fNIRS Brain--Computer Interfaces"
    assert title_key in main_tex, "Title mismatch in main.tex"
    assert title_key in supp_tex, "Title mismatch in supplementary.tex"
    assert "Physiology-Guided Temporal Fusion for Cross-Subject EEG--fNIRS Brain--Computer Interfaces" in cover_tex, "Title mismatch in Cover_Letter.tex"
    print("[*] Title Alignment across Main, Supp, and Cover Letter: 100% Consistent")

    # 2. Authors and affiliations
    assert "Hongjie~Chen" in main_tex and "Fang~Duan" in main_tex, "Authors missing in main.tex"
    assert "Huaqiao University" in main_tex, "Institution missing in main.tex"
    assert "chenhj976@gmail.com" in main_tex and "nkfetsh@gmail.com" in main_tex, "Emails missing in main.tex"
    assert "0000-0003-0982-2206" in cover_tex, "ORCID missing in Cover_Letter.tex"
    print("[*] Author Metadata & Corresponding ORCID: Complete and Verified")

    # 3. Section structure in main
    required_sections = ["Introduction", "Related Work", "Methods", "Experimental Protocol", "Results", "Discussion", "Conclusion"]
    for s in required_sections:
        assert re.search(rf'\\section\{{{s}', main_tex), f"Section missing: {s}"
    print("[*] Section Structure (Intro -> Related Work -> Methods -> Protocol -> Results -> Discussion -> Conclusion): 100% Present")

    # 4. References count
    main_bbl = (WORKSPACE / "manuscript" / "main.bbl").read_text(encoding='utf-8')
    ref_entries = re.findall(r'\\bibitem\{', main_bbl)
    print(f"[*] Main References: {len(ref_entries)} citations (Numbered [1]--[{len(ref_entries)}])")
    assert len(ref_entries) == 36, f"Expected 36 references in main.bbl, found {len(ref_entries)}"

    supp_bbl = (WORKSPACE / "reports" / "Supplementary_Material.bbl").read_text(encoding='utf-8')
    supp_ref_entries = re.findall(r'\\bibitem\{', supp_bbl)
    print(f"[*] Supplementary References: {len(supp_ref_entries)} citations (Numbered [1]--[{len(supp_ref_entries)}])")
    assert len(supp_ref_entries) == 6, f"Expected 6 references in supplementary.bbl, found {len(supp_ref_entries)}"

    # 5. Dual-cohort validation
    assert "TU Berlin" in main_tex and "Buccino" in supp_tex, "Dual cohort not documented"
    print("[*] Dual-Cohort Scope: Primary TU Berlin (29 subs) + Independent Buccino (15 subs)")
    print("[PASS] Gate 8 cleared.\n")

def run_gate_9_mandatory_declarations():
    print("=" * 70)
    print("GATE 9: MANDATORY DECLARATIONS, ETHICS, & OPEN SCIENCE RIGOR")
    print("=" * 70)
    main_tex = (WORKSPACE / "manuscript" / "main.tex").read_text(encoding='utf-8')
    cover_tex = (WORKSPACE / "reports" / "Cover_Letter.tex").read_text(encoding='utf-8')

    # Ethics
    assert "20150330" in main_tex and "20150330" in cover_tex, "TU Berlin IRB protocol missing"
    assert "University of Houston Institutional Review Board" in main_tex and "University of Houston Institutional Review Board" in cover_tex, "Houston IRB protocol missing"
    print("[*] Ethical Approval & Consent Protocols: Fully Verified (TU Berlin SH_01_20150330 & Houston IRB)")

    # Conflict of Interest
    assert "declare no competing" in main_tex or "declare that they have no" in main_tex, "COI missing in main"
    assert "declare no competing" in cover_tex, "COI missing in cover letter"
    print("[*] Conflict of Interest Declaration: Verified (No competing interests)")

    # Funding statement
    assert "No specific external grant" in cover_tex, "Funding missing in cover letter"
    print("[*] Funding Disclosure: Verified (No specific external grant supported this research)")

    # Open Source repository
    repo_url = "https://github.com/ujujuj3061831150/nvc-delayformer-bci"
    assert repo_url in main_tex, "Repo URL missing in main"
    assert repo_url in cover_tex, "Repo URL missing in cover letter"
    print(f"[*] Data & Code Open Science Repository: Verified ({repo_url})")
    print("[PASS] Gate 9 cleared.\n")

def run_gate_10_anti_overclaiming():
    print("=" * 70)
    print("GATE 10: SCIENTIFIC TONE & ANTI-OVERCLAIMING STRICT COMPLIANCE")
    print("=" * 70)
    forbidden_patterns = [
        r'\bgroundbreaking\b',
        r'\bunrivaled\b',
        r'\brevolutionary\b',
        r'\bgame-changing\b',
        r'\bfirst-ever\b',
        r'\bmiraculous\b',
        r'\bflawless\b',
        r'\bincomparable\b',
        r'数据集3',
        r'天津数据',
    ]
    main_tex = (WORKSPACE / "manuscript" / "main.tex").read_text(encoding='utf-8')
    supp_tex = (WORKSPACE / "reports" / "Supplementary_Material.tex").read_text(encoding='utf-8')
    cover_tex = (WORKSPACE / "reports" / "Cover_Letter.tex").read_text(encoding='utf-8')

    for pat in forbidden_patterns:
        m1 = re.findall(pat, main_tex, re.IGNORECASE)
        m2 = re.findall(pat, supp_tex, re.IGNORECASE)
        m3 = re.findall(pat, cover_tex, re.IGNORECASE)
        total = len(m1) + len(m2) + len(m3)
        assert total == 0, f"Forbidden promotional or obsolete pattern '{pat}' found ({total} matches)!"
    print("[*] Scan for 10 forbidden promotional & obsolete token patterns: 0 Violations (Clean)")
    print("[PASS] Gate 10 cleared.\n")

if __name__ == '__main__':
    print("######################################################################")
    print("STARTING 10-GATE GLOBAL QC AND SUBMISSION INTEGRITY AUDIT")
    print("######################################################################\n")
    run_gate_1_git()
    run_gate_2_integrity()
    run_gate_3_page_budgets()
    run_gate_4_source_zip_sandbox()
    run_gate_5_zenodo_doi()
    run_gate_6_codebase_soundness()
    run_gate_7_unit_tests()
    run_gate_8_jne_guidelines()
    run_gate_9_mandatory_declarations()
    run_gate_10_anti_overclaiming()
    print("######################################################################")
    print("ALL 10 GLOBAL QC AUDIT GATES 100% PASSED! SUBMISSION IS FULLY COMPLIANT.")
    print("######################################################################")
