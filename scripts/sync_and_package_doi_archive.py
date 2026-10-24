"""
Synchronize all updated files into releases/NVC-DelayFormer_DOI_Archive_20261021
and generate the final releases/NVC-DelayFormer_DOI_Archive_20261021.zip
along with recomputed SHA-256 checksums.
"""

import os
import shutil
import hashlib
import zipfile
from pathlib import Path

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    root = Path(__file__).resolve().parent.parent
    archive_dir = root / "releases/NVC-DelayFormer_DOI_Archive_20261021"
    zip_path = root / "releases/NVC-DelayFormer_DOI_Archive_20261021.zip"
    sha_path = root / "releases/NVC-DelayFormer_DOI_Archive_20261021.zip.sha256"
    alt_sha_path = root / "releases/NVC-DOI_Archive_20261021.zip.sha256"

    # Files to sync from root workspace to archive directory
    files_to_sync = [
        # Scripts
        ("scripts/run_mi_delay_and_priors_investigation.py", "scripts/run_mi_delay_and_priors_investigation.py"),
        ("scripts/generate_supplementary_fig_s1.py", "scripts/generate_supplementary_fig_s1.py"),
        
        # Reports
        ("reports/mi_delay_and_priors_investigation_results.json", "reports/mi_delay_and_priors_investigation_results.json"),
        ("reports/Supplementary_Material.pdf", "reports/Supplementary_Material.pdf"),
        ("reports/Cover_Letter.tex", "reports/Cover_Letter.tex"),
        ("reports/Cover_Letter.pdf", "reports/Cover_Letter.pdf"),
        ("reports/Cover_Letter.md", "reports/Cover_Letter.md"),
        ("reports/Highlights.txt", "reports/Highlights.txt"),
        ("reports/Highlights.md", "reports/Highlights.md"),
        ("reports/Submission_Package_Checklist.md", "reports/Submission_Package_Checklist.md"),
        
        # Figures
        ("manuscript/figures/supplementary_fig_s1_delay_curves.pdf", "manuscript/figures/supplementary_fig_s1_delay_curves.pdf"),
        ("manuscript/figures/supplementary_fig_s1_delay_curves.png", "manuscript/figures/supplementary_fig_s1_delay_curves.png"),
        ("reports/figures/supplementary_fig_s1_delay_curves.pdf", "reports/figures/supplementary_fig_s1_delay_curves.pdf"),
        ("reports/figures/supplementary_fig_s1_delay_curves.png", "reports/figures/supplementary_fig_s1_delay_curves.png"),
        
        # Manuscript
        ("manuscript/main.tex", "manuscript/main.tex"),
        ("manuscript/main.pdf", "manuscript/main.pdf"),
        ("manuscript/supplementary.tex", "manuscript/supplementary.tex"),
        ("manuscript/supplementary.tex", "reports/Supplementary_Material.tex"),
    ]

    print("--- 1. Synchronizing updated files to archive directory ---")
    for src_rel, dst_rel in files_to_sync:
        src = root / src_rel
        dst = archive_dir / dst_rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"[SYNC] {src_rel} -> releases/NVC-DelayFormer_DOI_Archive_20261021/{dst_rel}")
        else:
            print(f"[WARN] Source file not found: {src}")

    print("\n--- 2. Packaging archive directory into zip ---")
    if zip_path.exists():
        zip_path.unlink()

    # Zip all files in archive_dir
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root_path, dirs, files in os.walk(archive_dir):
            for file in sorted(files):
                file_full = Path(root_path) / file
                arcname = file_full.relative_to(archive_dir.parent)
                zf.write(file_full, arcname)

    print(f"[OK] Created archive: {zip_path} ({zip_path.stat().st_size:,} bytes)")

    print("\n--- 3. Computing SHA-256 Checksum ---")
    checksum = compute_sha256(zip_path)
    sha_content = f"{checksum}  NVC-DelayFormer_DOI_Archive_20261021.zip\n"
    
    with open(sha_path, "w", encoding="utf-8") as f:
        f.write(sha_content)
    print(f"[OK] Wrote SHA-256 to: {sha_path}")
    print(f"     Checksum: {checksum}")

    # Also write alt sha path for robustness
    with open(alt_sha_path, "w", encoding="utf-8") as f:
        f.write(sha_content)
    print(f"[OK] Wrote SHA-256 to: {alt_sha_path}")

if __name__ == "__main__":
    main()
