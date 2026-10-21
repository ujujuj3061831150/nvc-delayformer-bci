import argparse
from pathlib import Path
from src.data.download_tuberlin import generate_biophysical_synthetic_subject
from src.data.preprocessing import preprocess_subject_mental_arithmetic


def batch_process(num_subjects: int = 5, force: bool = False):
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    
    print(f"Batch processing Sub-01 to Sub-{num_subjects:02d} (force={force})...")
    for sub_id in range(1, num_subjects + 1):
        raw_file = raw_dir / f"sub-{sub_id:02d}_raw_ma.mat"
        if force or not raw_file.exists():
            print(f"-> Generating synthetic raw for Sub-{sub_id:02d}...")
            raw_file = generate_biophysical_synthetic_subject(
                output_dir=raw_dir,
                subject_id=sub_id,
                num_trials=60,
                trial_duration_sec=24.0
            )
            
        sub_proc_dir = processed_dir / f"sub-{sub_id:02d}"
        proc_file = sub_proc_dir / "ma_epochs.pt"
        if force or not proc_file.exists():
            print(f"-> Preprocessing Sub-{sub_id:02d}...")
            preprocess_subject_mental_arithmetic(
                raw_file_path=raw_file,
                output_dir=sub_proc_dir,
            )
        else:
            print(f"-> Sub-{sub_id:02d} already preprocessed at {proc_file}")
            
    print("Batch processing complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_subs", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="Force regenerate and preprocess")
    args = parser.parse_args()
    batch_process(args.num_subs, force=args.force)
