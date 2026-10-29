"""
Synchronize all updated files into releases/NVC-DelayFormer_DOI_Archive_20261021
and generate the final releases/NVC-DelayFormer_DOI_Archive_20261021.zip
along with validated MANIFEST.sha256 and recomputed checksums.
"""

import sys
import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    builder_script = root / "scripts" / "build_doi_archive.py"
    
    print(f"--- Running verified DOI archive builder ({builder_script}) ---")
    result = subprocess.run([sys.executable, str(builder_script)], cwd=str(root))
    if result.returncode != 0:
        raise RuntimeError(f"DOI archive packaging failed with exit code {result.returncode}")
    print("[OK] Verified DOI archive and checksums successfully generated.")

if __name__ == "__main__":
    main()

