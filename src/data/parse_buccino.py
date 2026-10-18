"""
Standardized Preprocessing Pipeline for Buccino et al. 2016 Dataset.
Parses raw MATLAB records into synchronized PyTorch tensors:
- EEG: 21 channels, resampled to 100 Hz (polyphase 2/5 factor from 250 Hz),
  bandpass filtered (0.5 - 45 Hz) + Common Average Reference (CAR).
- fNIRS: 34 optode pairs (dual wavelength 760nm/850nm), ΔOD conversion,
  bandpass filtered (0.01 - 0.10 Hz), MBLL converted to 34 HbO + 34 HbR (68 total channels).
- Epoch Extraction:
  - Mode 1 ('movement_vs_rest'): 100 Rest trials (code 1) vs 100 Movement trials (codes 3, 4, 7, 8).
  - Mode 2 ('right_vs_left'): 50 Right (codes 3, 7) vs 50 Left (codes 4, 8).

Reference:
Buccino et al., PLOS ONE 2016. DOI: 10.1371/journal.pone.0146610.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import scipy.io as sio
import scipy.signal as signal
import torch

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data.mbll import compute_mbll_inversion_matrix
from src.data.preprocessing import butter_bandpass_filter


def common_average_reference(data: np.ndarray) -> np.ndarray:
    """Compute Common Average Reference (CAR) across spatial channel axis."""
    return data - data.mean(axis=0, keepdims=True)


def parse_buccino_subject(
    subject_id: int,
    raw_root: Path,
    output_dir: Path,
    task_mode: str = "movement_vs_rest",
    epoch_duration: float = 6.0,
    target_eeg_fs: float = 100.0,
) -> Path:
    """
    Parse a single Buccino participant's raw .mat file into synchronized smr_epochs.pt.

    Args:
        subject_id: Integer subject ID (1 to 15).
        raw_root: Root directory containing extracted Buccino zip subfolders.
        output_dir: Destination directory for sub-XX.
        task_mode: Either 'movement_vs_rest' (200 trials) or 'right_vs_left' (100 trials).
        epoch_duration: Duration of each extracted window in seconds (default: 6.0s).
        target_eeg_fs: Target resampling frequency for EEG (default: 100.0 Hz).

    Returns:
        Path to the saved PyTorch tensor dictionary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_pt_path = output_dir / "smr_epochs.pt"

    # Locate raw .mat file
    if 1 <= subject_id <= 8:
        sub_folder = raw_root / "extracted" / "EEG-fNIRS hybrid SMR BCI data S1-S8"
    elif 9 <= subject_id <= 15:
        sub_folder = raw_root / "extracted" / "EEG-fNIRS hybrid SMR BCI data S9-S15"
    else:
        raise ValueError(f"Invalid subject_id {subject_id}. Buccino dataset has 15 subjects (1-15).")

    mat_file = sub_folder / f"S{subject_id}.mat"
    if not mat_file.exists():
        raise FileNotFoundError(f"Missing raw file for S{subject_id}: {mat_file}")

    print(f"[*] Parsing Buccino dataset for Sub-{subject_id:02d} from {mat_file.name}...")

    # Load MATLAB structure
    mat = sio.loadmat(str(mat_file), squeeze_me=True, struct_as_record=False)
    data = mat["data"]
    eeg_struct = data[0]
    nirs_struct = data[1]
    evt_matrix = data[2]

    # --- 1. Process Continuous Scalp EEG ---
    raw_fs_eeg = float(eeg_struct[0])  # 250 Hz
    eeg_labels = [str(c).strip() for c in eeg_struct[2]]  # 21 channels
    eeg_raw = eeg_struct[4]  # shape: (T_eeg, 21)

    # Polyphase resampling from 250 Hz to 100 Hz (exact ratio 2 / 5)
    up, down = 2, 5
    if abs(raw_fs_eeg - 250.0) < 1e-2 and abs(target_eeg_fs - 100.0) < 1e-2:
        eeg_resampled = signal.resample_poly(eeg_raw, up, down, axis=0)
        eeg_fs = target_eeg_fs
    else:
        num_target_samples = int(round(eeg_raw.shape[0] * target_eeg_fs / raw_fs_eeg))
        eeg_resampled = signal.resample(eeg_raw, num_target_samples, axis=0)
        eeg_fs = target_eeg_fs

    # Bandpass filter (0.5 - 45 Hz) & CAR
    eeg_filtered = butter_bandpass_filter(eeg_resampled.T, lowcut=0.5, highcut=45.0, fs=eeg_fs)  # (21, T)
    eeg_car = common_average_reference(eeg_filtered)  # (21, T)

    # --- 2. Process Continuous Dual-Wavelength fNIRS (760nm & 850nm) ---
    nirs_fs = float(nirs_struct[0])  # 10.4167 Hz
    nirs_labels_raw = [str(c).strip() for c in nirs_struct[2]]  # 34 optode pairs
    wl1 = np.maximum(nirs_struct[4].T, 1e-4)  # (34, T_nirs)
    wl2 = np.maximum(nirs_struct[5].T, 1e-4)  # (34, T_nirs)

    # Baseline intensity per channel
    i0_1 = wl1.mean(axis=1, keepdims=True)
    i0_2 = wl2.mean(axis=1, keepdims=True)

    # Optical density changes: ΔOD = -ln(I(t) / I_0)
    od_1 = -np.log(wl1 / i0_1)
    od_2 = -np.log(wl2 / i0_2)

    # Bandpass filter optical density (0.01 - 0.10 Hz)
    od_1_filt = butter_bandpass_filter(od_1, lowcut=0.01, highcut=0.10, fs=nirs_fs)
    od_2_filt = butter_bandpass_filter(od_2, lowcut=0.01, highcut=0.10, fs=nirs_fs)

    # Modified Beer-Lambert Law (MBLL) inversion to HbO and HbR
    inv_mat = compute_mbll_inversion_matrix(760, 850, dpf_1=6.51, dpf_2=5.86, optode_distance_mm=30.0)
    inv_tensor = torch.from_numpy(inv_mat).float()

    # Stack [ΔOD_1, ΔOD_2] -> (34, 2, T)
    od_stack = np.stack([od_1_filt, od_2_filt], axis=1)
    od_torch = torch.from_numpy(od_stack).float()
    hbo_hbr = torch.einsum("ij, cjt -> cit", inv_tensor, od_torch)  # (34, 2, T)
    hbo = hbo_hbr[:, 0, :].numpy()  # (34, T)
    hbr = hbo_hbr[:, 1, :].numpy()  # (34, T)

    # Concatenate 34 HbO + 34 HbR -> 68 channels (matching standard dual-stream convention)
    fnirs_68 = np.concatenate([hbo, hbr], axis=0)  # (68, T)
    nirs_labels_68 = [f"{lbl}_HbO" for lbl in nirs_labels_raw] + [f"{lbl}_HbR" for lbl in nirs_labels_raw]

    # --- 3. Slice Synchronized Trial Epochs ---
    evt_times = evt_matrix[:, 0]
    evt_codes = evt_matrix[:, 1].astype(int)

    n_eeg_pts = int(round(epoch_duration * eeg_fs))
    n_nirs_pts = int(round(epoch_duration * nirs_fs))

    trials_eeg: List[np.ndarray] = []
    trials_fnirs: List[np.ndarray] = []
    labels: List[int] = []

    for idx, (t_sec, code) in enumerate(zip(evt_times, evt_codes)):
        if task_mode == "movement_vs_rest":
            if code == 1:
                # Rest trial: shift onset by +1.0s to allow movement decay from previous trial
                start_sec = t_sec + 1.0
                lbl = 0  # Rest
            elif code in [3, 4, 7, 8]:
                # Motor task trial: start at cue onset
                start_sec = t_sec
                lbl = 1  # Movement
            else:
                continue
        elif task_mode == "right_vs_left":
            if code in [3, 7]:  # Right Arm (3), Right Hand (7)
                start_sec = t_sec
                lbl = 1  # Right
            elif code in [4, 8]:  # Left Arm (4), Left Hand (8)
                start_sec = t_sec
                lbl = 0  # Left
            else:
                continue
        else:
            raise ValueError(f"Unknown task_mode: {task_mode}")

        eeg_start_idx = int(round(start_sec * eeg_fs))
        eeg_end_idx = eeg_start_idx + n_eeg_pts

        nirs_start_idx = int(round(start_sec * nirs_fs))
        nirs_end_idx = nirs_start_idx + n_nirs_pts

        if eeg_end_idx > eeg_car.shape[1] or nirs_end_idx > fnirs_68.shape[1]:
            continue

        eeg_epoch = eeg_car[:, eeg_start_idx:eeg_end_idx]  # (21, n_eeg_pts)
        nirs_epoch = fnirs_68[:, nirs_start_idx:nirs_end_idx]  # (68, n_nirs_pts)

        trials_eeg.append(eeg_epoch)
        trials_fnirs.append(nirs_epoch)
        labels.append(lbl)

    eeg_tensor = torch.from_numpy(np.stack(trials_eeg, axis=0)).float()
    fnirs_tensor = torch.from_numpy(np.stack(trials_fnirs, axis=0)).float()
    labels_tensor = torch.tensor(labels, dtype=torch.long)

    payload = {
        "eeg": eeg_tensor,
        "fnirs": fnirs_tensor,
        "labels": labels_tensor,
        "subject_id": subject_id,
        "fs_eeg": eeg_fs,
        "fs_fnirs": nirs_fs,
        "epoch_duration_sec": epoch_duration,
        "task_mode": task_mode,
        "channel_names_eeg": eeg_labels,
        "channel_names_fnirs": nirs_labels_68,
        "n_trials": len(labels),
    }

    torch.save(payload, str(out_pt_path))
    print(
        f"[+] Sub-{subject_id:02d}: Extracted {len(labels)} trials "
        f"(EEG: {list(eeg_tensor.shape)}, fNIRS: {list(fnirs_tensor.shape)}) -> {out_pt_path}"
    )
    return out_pt_path


def batch_parse_all_buccino_subjects(
    num_subjects: int = 15,
    raw_root: str = "data/raw/buccino",
    output_dir: str = "data/processed_buccino",
    task_mode: str = "movement_vs_rest",
    epoch_duration: float = 6.0,
) -> None:
    """Batch preprocess all 15 Buccino participants into synchronized PyTorch epochs."""
    raw_path = Path(raw_root)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f"BATCH PROCESSING BUCCINO ET AL. 2016 DATASET (1 to {num_subjects})")
    print(f"Task Mode: {task_mode} | Duration: {epoch_duration}s")
    print(f"Source Root: {raw_path.resolve()}")
    print(f"Target Output: {out_path.resolve()}")
    print("=" * 80)

    start_time = time.time()
    success_count = 0

    for sub_id in range(1, num_subjects + 1):
        sub_out = out_path / f"sub-{sub_id:02d}"
        try:
            parse_buccino_subject(
                subject_id=sub_id,
                raw_root=raw_path,
                output_dir=sub_out,
                task_mode=task_mode,
                epoch_duration=epoch_duration,
            )
            success_count += 1
        except Exception as e:
            print(f"[FAIL] Sub-{sub_id:02d} failed: {e}")

    elapsed = time.time() - start_time
    print("=" * 80)
    print(f"Batch Processing Complete: {success_count}/{num_subjects} subjects converted in {elapsed:.1f}s.")
    print("=" * 80)


if __name__ == "__main__":
    mode = "movement_vs_rest"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    batch_parse_all_buccino_subjects(num_subjects=15, task_mode=mode)
