"""
Standardized Shin et al. (2018) Cognitive n-back Working Memory Dataset Parser.
Parses continuous raw MAT files from local zip archives into synchronized epochs:
- Task: 0-back (low cognitive workload / sensory target detection, label 0)
        vs. 2-back (high cognitive workload / working memory maintenance, label 1).
- EEG: 30 channels @ 100 Hz, 10.0s duration (1000 time steps), bandpass 0.5-45 Hz + CAR.
- fNIRS: 72 channels (36 HbO + 36 HbR) @ 10.33 Hz, 12.0s duration (124 time steps), bandpass 0.01-0.10 Hz.
- Trials: 72 trials per subject (36 of 0-back, 36 of 2-back), total 1,872 trials across 26 participants.
- Output: data/processed_shin2018_nback/sub-XX/nback_epochs.pt.
"""

import io
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import scipy.io as sio
import scipy.signal as signal
import torch

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data.preprocessing import butter_bandpass_filter


EEG_TARGET_30 = [
    "Fp1", "AFF5h", "AFz", "F1", "FC5", "FC1", "T7", "C3", "Cz", "CP5",
    "CP1", "P7", "P3", "Pz", "POz", "O1", "Fp2", "AFF6h", "F2", "FC2",
    "FC6", "C4", "T8", "CP2", "CP6", "P4", "P8", "O2", "HEOG", "VEOG"
]


def common_average_reference(data: np.ndarray) -> np.ndarray:
    return data - data.mean(axis=0, keepdims=True)


def parse_subject_from_zips(
    sub_id: int,
    z_eeg: zipfile.ZipFile,
    z_nirs: zipfile.ZipFile,
    output_dir: Path
) -> Path:
    sub_str = f"VP{sub_id:03d}"
    out_pt = output_dir / f"sub-{sub_id:02d}" / "nback_epochs.pt"
    out_pt.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load EEG
    e_cnt_bytes = z_eeg.read(f"{sub_str}-EEG/cnt_nback.mat")
    e_mrk_bytes = z_eeg.read(f"{sub_str}-EEG/mrk_nback.mat")
    e_cnt = sio.loadmat(io.BytesIO(e_cnt_bytes), struct_as_record=False, squeeze_me=True)["cnt_nback"]
    e_mrk = sio.loadmat(io.BytesIO(e_mrk_bytes), struct_as_record=False, squeeze_me=True)["mrk_nback"]

    eeg_x = e_cnt.x  # (T, ch)
    eeg_fs = float(e_cnt.fs)
    eeg_clab = list(e_cnt.clab)

    ch_indices = []
    for target in EEG_TARGET_30:
        matches = [i for i, c in enumerate(eeg_clab) if str(c).strip().lower() == target.lower()]
        if not matches:
            matches = [i for i, c in enumerate(eeg_clab) if target.lower() in str(c).strip().lower()]
        if not matches:
            raise ValueError(f"Channel {target} not found in clab for {sub_str}")
        ch_indices.append(matches[0])

    eeg_30 = eeg_x[:, ch_indices].T  # (30, T)
    eeg_filt = butter_bandpass_filter(eeg_30, lowcut=0.5, highcut=45.0, fs=eeg_fs)
    eeg_car = common_average_reference(eeg_filt)

    # 2. Load NIRS
    n_cnt_bytes = z_nirs.read(f"{sub_str}-NIRS/cnt_nback.mat")
    n_mrk_bytes = z_nirs.read(f"{sub_str}-NIRS/mrk_nback.mat")
    n_cnt = sio.loadmat(io.BytesIO(n_cnt_bytes), struct_as_record=False, squeeze_me=True)["cnt_nback"]
    n_mrk = sio.loadmat(io.BytesIO(n_mrk_bytes), struct_as_record=False, squeeze_me=True)["mrk_nback"]

    hbo_raw = n_cnt.oxy.x.T  # (36, T)
    hbr_raw = n_cnt.deoxy.x.T  # (36, T)
    nirs_fs = float(n_cnt.oxy.fs)

    hbo_filt = butter_bandpass_filter(hbo_raw, lowcut=0.01, highcut=0.10, fs=nirs_fs)
    hbr_filt = butter_bandpass_filter(hbr_raw, lowcut=0.01, highcut=0.10, fs=nirs_fs)

    # 3. Align Sessions
    # In EEG, classes 5, 6, 7 are 0-back, 2-back, 3-back sessions
    e_sess_idx = np.where((e_mrk.y[5] == 1) | (e_mrk.y[6] == 1) | (e_mrk.y[7] == 1))[0]
    assert len(e_sess_idx) == 27, f"Expected 27 sessions in EEG for {sub_str}, found {len(e_sess_idx)}"
    assert n_mrk.y.shape[1] == 27, f"Expected 27 sessions in NIRS for {sub_str}, found {n_mrk.y.shape[1]}"

    offsets = [2.0, 12.0, 22.0, 32.0]
    all_eeg, all_fnirs, all_labels = [], [], []

    for k in range(27):
        e_label = e_mrk.className[np.where(e_mrk.y[:, e_sess_idx[k]] == 1)[0][0]]
        if "0-back" in e_label:
            lbl = 0  # 0-back (low workload)
        elif "2-back" in e_label:
            lbl = 1  # 2-back (high workload)
        else:
            continue  # ignore 3-back for binary benchmark

        t_e_start = e_mrk.time[e_sess_idx[k]] / 1000.0
        t_n_start = n_mrk.time[k] / 1000.0

        for off in offsets:
            # EEG slice
            s_e = int((t_e_start + off) * eeg_fs)
            e_e = s_e + int(10.0 * eeg_fs)
            base_s_e = max(0, s_e - int(2.0 * eeg_fs))
            if e_e > eeg_car.shape[1]:
                continue
            e_chunk = eeg_car[:, s_e:e_e]
            base_eeg = eeg_car[:, base_s_e:s_e].mean(axis=-1, keepdims=True)
            e_norm = e_chunk - base_eeg
            e_res = signal.resample(e_norm, 1000, axis=-1)

            # NIRS slice
            s_n = int((t_n_start + off) * nirs_fs)
            e_n = s_n + int(12.0 * nirs_fs)
            base_s_n = max(0, s_n - int(2.0 * nirs_fs))
            if e_n > hbo_filt.shape[1]:
                continue
            hbo_chunk = hbo_filt[:, s_n:e_n] - hbo_filt[:, base_s_n:s_n].mean(axis=-1, keepdims=True)
            hbr_chunk = hbr_filt[:, s_n:e_n] - hbr_filt[:, base_s_n:s_n].mean(axis=-1, keepdims=True)
            fnirs_72 = np.concatenate([hbo_chunk, hbr_chunk], axis=0)
            n_res = signal.resample(fnirs_72, 124, axis=-1)

            all_eeg.append(e_res)
            all_fnirs.append(n_res)
            all_labels.append(lbl)

    assert len(all_labels) == 72, f"Expected 72 trials for {sub_str}, got {len(all_labels)}"

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
            "source": "Shin et al. (2018) Cognitive n-back Working Memory Dataset",
            "subject_id": sub_id,
            "total_trials": len(all_labels),
            "0back_trials": int((labels_tensor == 0).sum().item()),
            "2back_trials": int((labels_tensor == 1).sum().item()),
            "eeg_channels": 30,
            "fnirs_channels": 72
        }
    }
    torch.save(payload, out_pt)
    print(f"[OK] Saved {sub_str} to {out_pt} ({len(all_labels)} trials: 36 0-back / 36 2-back)")
    return out_pt


def process_all():
    eeg_zip_path = Path("data/downloads_shin2018/EEG_01-26_MATLAB.zip")
    nirs_zip_path = Path("data/downloads_shin2018/NIRS_01-26_MATLAB.zip")
    output_dir = Path("data/processed_shin2018_nback")

    assert eeg_zip_path.exists(), f"Missing {eeg_zip_path}"
    assert nirs_zip_path.exists(), f"Missing {nirs_zip_path}"

    with zipfile.ZipFile(eeg_zip_path, "r") as z_eeg:
        with zipfile.ZipFile(nirs_zip_path, "r") as z_nirs:
            for sub_id in range(1, 27):
                parse_subject_from_zips(sub_id, z_eeg, z_nirs, output_dir)
    print("All 26 subjects processed successfully.")


if __name__ == "__main__":
    process_all()
