"""
Standardized Shin et al. (2017) Motor Imagery (MI: Left Hand vs. Right Hand) Dataset Parser.
Parses continuous raw MAT files from data/raw/real_tuberlin/ into synchronized epochs:
- Task: Motor Imagery (Left Hand = 0 vs. Right Hand = 1).
- EEG: 30 channels @ 100 Hz, 10.0s duration (1000 time steps), bandpass 0.5-45 Hz + CAR.
- fNIRS: 72 channels (36 HbO + 36 HbR) @ 10.4 Hz, 12.0s duration (124 time steps), MBLL converted.
- Trials: 60 trials per subject (30 left, 30 right), total 1,740 trials across 29 participants.
- Output: data/processed_shin2017_mi/sub-XX/mi_epochs.pt.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import scipy.io as sio
import scipy.signal as signal
import torch

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data.mbll import compute_mbll_inversion_matrix
from src.data.preprocessing import butter_bandpass_filter


EEG_TARGET_30 = [
    "F7", "AFF5h", "F3", "AFp1", "AFp2", "AFF6h", "F4", "F8", "AFF1h", "AFF2h",
    "Cz", "Pz", "FCC5h", "FCC3h", "CCP5h", "CCP3h", "T7", "P7", "P3", "PPO1h",
    "POO1", "POO2", "PPO2h", "P4", "FCC4h", "FCC6h", "CCP4h", "CCP6h", "P8", "T8"
]


def common_average_reference(data: np.ndarray) -> np.ndarray:
    return data - data.mean(axis=0, keepdims=True)


def parse_shin2017_mi_subject(
    subject_id: int,
    raw_root: Path,
    output_dir: Path,
    inv_tensor: torch.Tensor
) -> Path:
    out_dir = output_dir / f"sub-{subject_id:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pt_path = out_dir / "mi_epochs.pt"

    eeg_sub_dir = raw_root / "EEG" / f"subject {subject_id:02d}" / "with occular artifact"
    nirs_sub_dir = raw_root / "NIRS" / f"subject {subject_id:02d}"

    eeg_cnt = sio.loadmat(eeg_sub_dir / "cnt.mat", squeeze_me=True, struct_as_record=False)["cnt"]
    eeg_mrk = sio.loadmat(eeg_sub_dir / "mrk.mat", squeeze_me=True, struct_as_record=False)["mrk"]
    nirs_cnt = sio.loadmat(nirs_sub_dir / "cnt.mat", squeeze_me=True, struct_as_record=False)["cnt"]
    nirs_mrk = sio.loadmat(nirs_sub_dir / "mrk.mat", squeeze_me=True, struct_as_record=False)["mrk"]

    # Sessions 0, 2, 4 are Motor Imagery (MI) sessions
    mi_sessions = [0, 2, 4]
    all_eeg, all_fnirs, all_labels = [], [], []

    for s_idx in mi_sessions:
        s_eeg = eeg_cnt[s_idx]
        s_eeg_mrk = eeg_mrk[s_idx]
        eeg_x = s_eeg.x
        eeg_fs = float(s_eeg.fs)
        eeg_clab = list(s_eeg.clab)

        ch_indices = []
        for target in EEG_TARGET_30:
            matches = [i for i, c in enumerate(eeg_clab) if c.strip().lower() == target.lower()]
            if not matches:
                raise ValueError(f"Channel {target} not found for sub {subject_id}")
            ch_indices.append(matches[0])

        eeg_30 = eeg_x[:, ch_indices].T
        eeg_filt = butter_bandpass_filter(eeg_30, lowcut=0.5, highcut=45.0, fs=eeg_fs)
        eeg_car = common_average_reference(eeg_filt)

        s_nirs = nirs_cnt[s_idx]
        s_nirs_mrk = nirs_mrk[s_idx]
        nirs_x = s_nirs.x
        nirs_fs = float(s_nirs.fs)

        n_optodes = 36
        nirs_760_raw = np.maximum(nirs_x[:, :n_optodes].T, 1e-4)
        nirs_850_raw = np.maximum(nirs_x[:, n_optodes:2*n_optodes].T, 1e-4)
        i0_760 = nirs_760_raw.mean(axis=1, keepdims=True)
        i0_850 = nirs_850_raw.mean(axis=1, keepdims=True)
        od_760 = -np.log(nirs_760_raw / i0_760)
        od_850 = -np.log(nirs_850_raw / i0_850)
        od_760_filt = butter_bandpass_filter(od_760, lowcut=0.01, highcut=0.1, fs=nirs_fs)
        od_850_filt = butter_bandpass_filter(od_850, lowcut=0.01, highcut=0.1, fs=nirs_fs)

        for t_eeg_ms, t_nirs_ms, desc in zip(s_eeg_mrk.time, s_nirs_mrk.time, s_eeg_mrk.event.desc):
            if desc == 16:
                lbl = 0  # Left hand motor imagery
            elif desc == 32:
                lbl = 1  # Right hand motor imagery
            else:
                continue

            e_on = float(t_eeg_ms) / 1000.0
            n_on = float(t_nirs_ms) / 1000.0

            e_s = int(e_on * eeg_fs)
            e_e = e_s + int(10.0 * eeg_fs)
            if e_e > eeg_car.shape[1]:
                continue
            e_epoch = signal.resample(eeg_car[:, e_s:e_e], 1000, axis=-1)
            b_s = max(0, e_s - int(2.0 * eeg_fs))
            e_epoch = e_epoch - eeg_car[:, b_s:e_s].mean(axis=-1, keepdims=True)

            n_s = int(n_on * nirs_fs)
            n_e = n_s + int(12.0 * nirs_fs)
            if n_e > od_760_filt.shape[1]:
                continue
            nb_s = max(0, n_s - int(2.0 * nirs_fs))
            od_760_epoch = od_760_filt[:, n_s:n_e] - od_760_filt[:, nb_s:n_s].mean(axis=-1, keepdims=True)
            od_850_epoch = od_850_filt[:, n_s:n_e] - od_850_filt[:, nb_s:n_s].mean(axis=-1, keepdims=True)

            od_stack = np.stack([od_760_epoch, od_850_epoch], axis=1)  # (36, 2, T)
            t_pts = od_stack.shape[-1]
            od_flat = torch.from_numpy(od_stack).permute(0, 2, 1).reshape(-1, 2).float()
            c_flat = torch.matmul(od_flat, inv_tensor.T)
            c_tensor = c_flat.view(36, t_pts, 2).permute(0, 2, 1)  # (36, 2, T)
            hbo_epoch = c_tensor[:, 0, :].numpy()
            hbr_epoch = c_tensor[:, 1, :].numpy()
            fnirs_72 = np.concatenate([hbo_epoch, hbr_epoch], axis=0)
            fnirs_epoch = signal.resample(fnirs_72, 124, axis=-1)

            all_eeg.append(e_epoch)
            all_fnirs.append(fnirs_epoch)
            all_labels.append(lbl)

    eeg_arr = np.stack(all_eeg, axis=0).astype(np.float32)      # (60, 30, 1000)
    fnirs_arr = np.stack(all_fnirs, axis=0).astype(np.float32)  # (60, 72, 124)
    labels_arr = np.array(all_labels, dtype=np.int64)          # (60,)

    torch.save({
        "eeg": torch.from_numpy(eeg_arr),
        "fnirs": torch.from_numpy(fnirs_arr),
        "labels": torch.from_numpy(labels_arr),
        "subject_id": subject_id,
        "task": "Motor Imagery (Left Hand vs. Right Hand)",
        "fs_eeg": 100,
        "fs_nirs": 10.33,
        "channel_names_eeg": EEG_TARGET_30
    }, out_pt_path)

    return out_pt_path


def parse_all_29_subjects(raw_dir: str = "data/raw/real_tuberlin", out_dir: str = "data/processed_shin2017_mi"):
    raw_root = Path(raw_dir)
    proc_root = Path(out_dir)
    proc_root.mkdir(parents=True, exist_ok=True)

    inv_mat = compute_mbll_inversion_matrix(760, 850, dpf_1=6.51, dpf_2=5.86, optode_distance_mm=30.0)
    inv_tensor = torch.from_numpy(inv_mat).float()

    print("=" * 80)
    print(f"BATCH PARSING SHIN ET AL. (2017) MOTOR IMAGERY: Sub-01 to Sub-29")
    print(f"Raw Source: {raw_root}")
    print(f"Target Output: {proc_root}")
    print("=" * 80)

    t0 = time.time()
    for sub_id in range(1, 30):
        t_sub = time.time()
        pt_path = parse_shin2017_mi_subject(sub_id, raw_root, proc_root, inv_tensor)
        print(f"[OK] Sub-{sub_id:02d} processed in {time.time() - t_sub:.2f}s -> {pt_path}")

    print(f"All 29 subjects parsed in {time.time() - t0:.2f}s.")


if __name__ == "__main__":
    parse_all_29_subjects()
