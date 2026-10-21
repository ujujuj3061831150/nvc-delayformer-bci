"""
Standardized Shin et al. (2018) Cognitive Word Generation Dataset Parser & Preprocessor.
Parses continuous raw MAT files into synchronized epochs:
- EEG: 30 channels @ 100 Hz, 10s duration (1000 time steps), bandpass 0.5-45 Hz + CAR.
- fNIRS: 72 channels (36 HbO + 36 HbR) @ 10.33 Hz, 12s duration (124 time steps), bandpass 0.01-0.10 Hz.
- Labels: 0 (Baseline / Rest), 1 (Word Generation / Verbal Fluency).
- Format: PyTorch dictionaries saved to data/processed_shin2018/sub-XX/wg_epochs.pt.
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import scipy.io as sio
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import scipy.signal as signal
import torch

from src.data.preprocessing import butter_bandpass_filter


def common_average_reference(data: np.ndarray) -> np.ndarray:
    """Compute common average reference across channels."""
    return data - data.mean(axis=0, keepdims=True)


# Official 30 channels in Shin et al. (2018) MAT files (28 scalp EEG + 2 EOG)
EEG_TARGET_30 = [
    "Fp1", "AFF5h", "AFz", "F1", "FC5", "FC1", "T7", "C3", "Cz", "CP5",
    "CP1", "P7", "P3", "Pz", "POz", "O1", "Fp2", "AFF6h", "F2", "FC2",
    "FC6", "C4", "T8", "CP2", "CP6", "P4", "P8", "O2", "HEOG", "VEOG"
]


def parse_subject_data(
    sub_id: int,
    eeg_dir: Path,
    nirs_dir: Path,
    output_dir: Path
) -> Path:
    """
    Parse a single subject's Word Generation EEG and NIRS data into standardized PyTorch format.
    Args:
        sub_id: Integer subject ID (1 to 26).
        eeg_dir: Directory containing 'cnt_wg.mat' and 'mrk_wg.mat' for EEG.
        nirs_dir: Directory containing 'cnt_wg.mat' and 'mrk_wg.mat' for NIRS.
        output_dir: Target output directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_pt = output_dir / "wg_epochs.pt"
    
    eeg_cnt_file = eeg_dir / "cnt_wg.mat"
    eeg_mrk_file = eeg_dir / "mrk_wg.mat"
    nirs_cnt_file = nirs_dir / "cnt_wg.mat"
    nirs_mrk_file = nirs_dir / "mrk_wg.mat"
    
    if not (eeg_cnt_file.exists() and eeg_mrk_file.exists()):
        raise FileNotFoundError(f"Missing EEG files for VP{sub_id:03d} in {eeg_dir}")
    if not (nirs_cnt_file.exists() and nirs_mrk_file.exists()):
        raise FileNotFoundError(f"Missing NIRS files for VP{sub_id:03d} in {nirs_dir}")
        
    print(f"[*] Processing Subject VP{sub_id:03d}...")
    
    # 1. Load EEG
    eeg_cnt_mat = sio.loadmat(eeg_cnt_file, squeeze_me=True, struct_as_record=False)
    eeg_mrk_mat = sio.loadmat(eeg_mrk_file, squeeze_me=True, struct_as_record=False)
    eeg_cnt = eeg_cnt_mat["cnt_wg"] if "cnt_wg" in eeg_cnt_mat else eeg_cnt_mat["cnt"]
    eeg_mrk = eeg_mrk_mat["mrk_wg"] if "mrk_wg" in eeg_mrk_mat else eeg_mrk_mat["mrk"]
    
    eeg_x = eeg_cnt.x  # shape: (T, channels)
    eeg_fs = float(eeg_cnt.fs)
    eeg_clab = list(eeg_cnt.clab)
    
    # Map 30 target channels
    ch_indices = []
    for target in EEG_TARGET_30:
        matches = [i for i, c in enumerate(eeg_clab) if str(c).strip().lower() == target.lower()]
        if not matches:
            matches = [i for i, c in enumerate(eeg_clab) if target.lower() in str(c).strip().lower()]
        if not matches:
            raise ValueError(f"Channel {target} not found in clab: {eeg_clab}")
        ch_indices.append(matches[0])
        
    eeg_30 = eeg_x[:, ch_indices].T  # shape: (30, T)
    eeg_filt = butter_bandpass_filter(eeg_30, lowcut=0.5, highcut=45.0, fs=eeg_fs)
    eeg_car = common_average_reference(eeg_filt)
    
    eeg_mrk_times = np.array(eeg_mrk.time)
    if hasattr(eeg_mrk, "event") and hasattr(eeg_mrk.event, "desc"):
        eeg_mrk_descs = np.array(eeg_mrk.event.desc)
    elif hasattr(eeg_mrk, "y"):
        eeg_mrk_descs = np.array(eeg_mrk.y)
    else:
        eeg_mrk_descs = np.array(eeg_mrk.desc)
        
    # 2. Load NIRS
    nirs_cnt_mat = sio.loadmat(nirs_cnt_file, squeeze_me=True, struct_as_record=False)
    nirs_mrk_mat = sio.loadmat(nirs_mrk_file, squeeze_me=True, struct_as_record=False)
    nirs_cnt = nirs_cnt_mat["cnt_wg"] if "cnt_wg" in nirs_cnt_mat else nirs_cnt_mat["cnt"]
    nirs_mrk = nirs_mrk_mat["mrk_wg"] if "mrk_wg" in nirs_mrk_mat else nirs_mrk_mat["mrk"]
    
    hbo_raw = nirs_cnt.oxy.x  # shape: (T, 36)
    hbr_raw = nirs_cnt.deoxy.x  # shape: (T, 36)
    nirs_fs = float(nirs_cnt.oxy.fs)
    
    hbo_filt = butter_bandpass_filter(hbo_raw.T, lowcut=0.01, highcut=0.10, fs=nirs_fs)  # (36, T)
    hbr_filt = butter_bandpass_filter(hbr_raw.T, lowcut=0.01, highcut=0.10, fs=nirs_fs)  # (36, T)
    
    nirs_mrk_times = np.array(nirs_mrk.time)
    if hasattr(nirs_mrk, "event") and hasattr(nirs_mrk.event, "desc"):
        nirs_mrk_descs = np.array(nirs_mrk.event.desc)
    elif hasattr(nirs_mrk, "y"):
        nirs_mrk_descs = np.array(nirs_mrk.y)
    else:
        nirs_mrk_descs = np.array(nirs_mrk.desc)

    # 3. Epoch Alignment & Slicing
    all_eeg = []
    all_fnirs = []
    all_labels = []
    
    # In Shin et al. WG:
    # In NIRS mrk_wg: desc=1 is Word Generation (WG=1), desc=2 is Baseline (Rest=0)
    # In EEG mrk_wg: desc=16 is WG (1), desc=32 is Baseline (0), or matching 1/2
    for idx_ev, (t_nirs_ms, desc_nirs) in enumerate(zip(nirs_mrk_times, nirs_mrk_descs)):
        if desc_nirs in (1, 16):
            lbl = 1  # Word Generation
        elif desc_nirs in (2, 32):
            lbl = 0  # Baseline
        else:
            continue
            
        t_nirs_sec = float(t_nirs_ms) / 1000.0
        
        # Match closest EEG marker
        time_diffs = np.abs(eeg_mrk_times - t_nirs_ms)
        best_eeg_idx = int(np.argmin(time_diffs))
        t_eeg_sec = float(eeg_mrk_times[best_eeg_idx]) / 1000.0
        
        # EEG Epoch: 10.0s task window @ 100 Hz (resampled from 200 Hz)
        eeg_start = int(t_eeg_sec * eeg_fs)
        eeg_end = eeg_start + int(10.0 * eeg_fs)
        if eeg_end > eeg_car.shape[1]:
            continue
            
        eeg_epoch = eeg_car[:, eeg_start:eeg_end]
        eeg_epoch = signal.resample(eeg_epoch, 1000, axis=-1)
        
        # EEG baseline subtraction (-2.0s to 0.0s)
        base_start = max(0, eeg_start - int(2.0 * eeg_fs))
        base_eeg = eeg_car[:, base_start:eeg_start].mean(axis=-1, keepdims=True)
        eeg_epoch = eeg_epoch - base_eeg
        
        # NIRS Epoch: 12.0s window resampled to 124 points
        nirs_start = int(t_nirs_sec * nirs_fs)
        nirs_end = nirs_start + int(12.0 * nirs_fs)
        if nirs_end > hbo_filt.shape[1]:
            continue
            
        # NIRS baseline subtraction (-2.0s to 0.0s)
        nirs_base_start = max(0, nirs_start - int(2.0 * nirs_fs))
        base_hbo = hbo_filt[:, nirs_base_start:nirs_start].mean(axis=-1, keepdims=True)
        base_hbr = hbr_filt[:, nirs_base_start:nirs_start].mean(axis=-1, keepdims=True)
        
        hbo_epoch = hbo_filt[:, nirs_start:nirs_end] - base_hbo
        hbr_epoch = hbr_filt[:, nirs_start:nirs_end] - base_hbr
        
        # Concatenate 36 HbO + 36 HbR = 72 channels
        fnirs_72 = np.concatenate([hbo_epoch, hbr_epoch], axis=0)  # (72, T)
        fnirs_resampled = signal.resample(fnirs_72, 124, axis=-1)
        
        all_eeg.append(eeg_epoch)
        all_fnirs.append(fnirs_resampled)
        all_labels.append(lbl)
        
    assert len(all_labels) > 0, f"No trials extracted for VP{sub_id:03d}."
    
    eeg_tensor = torch.from_numpy(np.stack(all_eeg)).float()
    fnirs_tensor = torch.from_numpy(np.stack(all_fnirs)).float()
    labels_tensor = torch.tensor(all_labels, dtype=torch.long)
    
    payload = {
        "eeg": eeg_tensor,
        "fnirs": fnirs_tensor,
        "labels": labels_tensor,
        "eeg_fs": 100.0,
        "fnirs_fs": 124.0 / 12.0,
        "metadata": {
            "source": "Shin et al. (2018) Cognitive Word Generation Dataset",
            "subject_id": sub_id,
            "total_trials": len(all_labels),
            "wg_trials": int((labels_tensor == 1).sum().item()),
            "baseline_trials": int((labels_tensor == 0).sum().item()),
            "eeg_channels": 30,
            "fnirs_channels": 72
        }
    }
    
    torch.save(payload, out_pt)
    print(f"[OK] Saved Sub-VP{sub_id:03d} to {out_pt} ({len(all_labels)} trials: {payload['metadata']['wg_trials']} WG / {payload['metadata']['baseline_trials']} Base)")
    return out_pt


def batch_process_all_subjects(
    raw_dir: Path = Path("data/raw/shin2018"),
    output_root: Path = Path("data/processed_shin2018"),
    num_subjects: int = 26
):
    """Batch preprocess all 26 subjects."""
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {}
    
    for sub in range(1, num_subjects + 1):
        eeg_sub_dir = raw_dir / "EEG" / f"VP{sub:03d}-EEG"
        nirs_sub_dir = raw_dir / "NIRS" / f"VP{sub:03d}-NIRS"
        
        if not (eeg_sub_dir.exists() and nirs_sub_dir.exists()):
            # Also check alternative folder naming (VP001 vs VP001-EEG)
            alt_eeg = raw_dir / "EEG" / f"VP{sub:03d}"
            alt_nirs = raw_dir / "NIRS" / f"VP{sub:03d}"
            if alt_eeg.exists():
                eeg_sub_dir = alt_eeg
            if alt_nirs.exists():
                nirs_sub_dir = alt_nirs
                
        if not (eeg_sub_dir.exists() and nirs_sub_dir.exists()):
            print(f"[!] Skipping VP{sub:03d}: Missing folders (EEG: {eeg_sub_dir.exists()}, NIRS: {nirs_sub_dir.exists()})")
            continue
            
        sub_out = output_root / f"sub-{sub:02d}"
        
        try:
            pt_path = parse_subject_data(sub, eeg_sub_dir, nirs_sub_dir, sub_out)
            data = torch.load(pt_path)
            summary[f"sub-{sub:02d}"] = data["metadata"]
        except Exception as e:
            print(f"[FAIL] Error processing VP{sub:03d}: {e}")
            
    summary_file = output_root / "preprocessing_summary.json"
    import json
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[OK] Finished batch processing! Summary saved to {summary_file}")


if __name__ == "__main__":
    raw_path = Path("data/raw/shin2018")
    out_path = Path("data/processed_shin2018")
    batch_process_all_subjects(raw_path, out_path, num_subjects=26)
