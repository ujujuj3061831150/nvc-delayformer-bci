"""
Batch Preprocessing for All 26 Real TU Berlin Human Subjects.
Converts raw downloaded MAT files from data/raw/real_tuberlin/ into
synchronized, MBLL-converted PyTorch tensors under data/processed/sub-XX/ma_epochs.pt.
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data.parse_real_tuberlin import parse_real_tuberlin_subject


def batch_parse_all_subjects(num_subjects: int = 26, raw_dir: str = "data/raw/real_tuberlin", out_dir: str = "data/processed"):
    raw_root = Path(raw_dir)
    proc_root = Path(out_dir)
    proc_root.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print(f"BATCH PROCESSING REAL TU BERLIN DATASET: Sub-01 to Sub-{num_subjects:02d}")
    print(f"Raw Source: {raw_root}")
    print(f"Target Output: {proc_root}")
    print("=" * 80)
    
    start_time = time.time()
    success_count = 0
    
    for sub_id in range(1, num_subjects + 1):
        sub_out = proc_root / f"sub-{sub_id:02d}"
        t0 = time.time()
        try:
            pt_path = parse_real_tuberlin_subject(
                subject_id=sub_id,
                raw_root=raw_root,
                output_dir=sub_out
            )
            elapsed = time.time() - t0
            print(f"[OK] Sub-{sub_id:02d} processed in {elapsed:.2f}s -> {pt_path}")
            success_count += 1
        except Exception as e:
            print(f"[FAIL] Sub-{sub_id:02d} failed: {e}")
            
    total_time = time.time() - start_time
    print("=" * 80)
    print(f"Batch Processing Complete: {success_count}/{num_subjects} subjects successfully converted in {total_time:.1f}s.")
    print("=" * 80)


if __name__ == "__main__":
    n = 29
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        n = int(sys.argv[1])
    batch_parse_all_subjects(num_subjects=n)
