"""
Standardized Real TU Berlin BBCI Dataset Parser & Preprocessor.
Parses downloaded continuous raw MAT files into synchronized epochs:
- EEG: 28 channels @ 100 Hz, 10s duration (1000 time steps), bandpass 0.5-45 Hz + CAR.
- fNIRS: 72 channels (36 HbO + 36 HbR) @ 10.4 Hz, 12s duration (124 time steps), MBLL converted.
- Labels: 0 (Rest), 1 (Mental Arithmetic / Subtraction).
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import scipy.io as sio
import scipy.signal as signal
import torch

from src.data.mbll import compute_mbll_inversion_matrix, od_to_hemoglobin_tensor
from src.data.preprocessing import butter_bandpass_filter


def common_average_reference(data: np.ndarray) -> np.ndarray:
    """Compute common average reference across channels."""
    return data - data.mean(axis=0, keepdims=True)


# Standard 30 scalp EEG channels matching TU Berlin official montage (excluding VEOG, HEOG)
EEG_TARGET_30 = [
    "F7", "AFF5h", "F3", "AFp1", "AFp2", "AFF6h", "F4", "F8", "AFF1h", "AFF2h",
    "Cz", "Pz", "FCC5h", "FCC3h", "CCP5h", "CCP3h", "T7", "P7", "P3", "PPO1h",
    "POO1", "POO2", "PPO2h", "P4", "FCC4h", "FCC6h", "CCP4h", "CCP6h", "P8", "T8"
]


def parse_real_tuberlin_subject(
    subject_id: int,
    raw_root: Path,
    output_dir: Path
) -> Path:
    """
    Parse a single subject's downloaded real BBCI files into standardized ma_epochs.pt.
    Args:
        subject_id: Integer subject ID (1 to 29).
        raw_root: Directory containing 'EEG' and 'NIRS' subfolders.
        output_dir: Target processed directory for sub-XX.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_pt_path = output_dir / "ma_epochs.pt"
    
    eeg_sub_dir = raw_root / "EEG" / f"subject {subject_id:02d}" / "with occular artifact"
    nirs_sub_dir = raw_root / "NIRS" / f"subject {subject_id:02d}"
    
    eeg_cnt_file = eeg_sub_dir / "cnt.mat"
    eeg_mrk_file = eeg_sub_dir / "mrk.mat"
    nirs_cnt_file = nirs_sub_dir / "cnt.mat"
    nirs_mrk_file = nirs_sub_dir / "mrk.mat"
    
    if not (eeg_cnt_file.exists() and eeg_mrk_file.exists() and nirs_cnt_file.exists() and nirs_mrk_file.exists()):
        raise FileNotFoundError(f"Missing raw BBCI files for Sub-{subject_id:02d} under {raw_root}")
        
    print(f"[*] Parsing real TU Berlin data for Sub-{subject_id:02d}...")
    
    # 1. Load EEG continuous records & markers
    eeg_cnt = sio.loadmat(eeg_cnt_file, squeeze_me=True, struct_as_record=False)["cnt"]
    eeg_mrk = sio.loadmat(eeg_mrk_file, squeeze_me=True, struct_as_record=False)["mrk"]
    
    # 2. Load fNIRS continuous records & markers
    nirs_cnt = sio.loadmat(nirs_cnt_file, squeeze_me=True, struct_as_record=False)["cnt"]
    nirs_mrk = sio.loadmat(nirs_mrk_file, squeeze_me=True, struct_as_record=False)["mrk"]
    
    # MBLL Inversion Matrix
    inv_mat = compute_mbll_inversion_matrix(760, 850, dpf_1=6.51, dpf_2=5.86, optode_distance_mm=30.0)
    inv_tensor = torch.from_numpy(inv_mat).float()
    
    # Sessions 1, 3, 5 are Mental Arithmetic sessions in BBCI paradigm
    ma_sessions = [1, 3, 5]
    all_eeg_trials = []
    all_fnirs_trials = []
    all_labels = []
    
    for s_idx in ma_sessions:
        # --- Process EEG Session ---
        session_eeg = eeg_cnt[s_idx]
        session_eeg_mrk = eeg_mrk[s_idx]
        
        eeg_x = session_eeg.x  # shape: (T, channels)
        eeg_fs = float(session_eeg.fs)
        eeg_clab = list(session_eeg.clab)
        
        # Map 30 channels with strict zero-fallback validation
        ch_indices = []
        for target_ch in EEG_TARGET_30:
            matches = [i for i, c in enumerate(eeg_clab) if c.strip().lower() == target_ch.lower()]
            if not matches:
                raise ValueError(f"Channel {target_ch} not found in Sub-{subject_id:02d} clab: {eeg_clab}")
            ch_indices.append(matches[0])
        eeg_30 = eeg_x[:, ch_indices].T  # shape: (30, T)
        
        # Bandpass filter (0.5 - 45 Hz) & Common Average Reference (CAR)
        eeg_filt = butter_bandpass_filter(eeg_30, lowcut=0.5, highcut=45.0, fs=eeg_fs)
        eeg_car = common_average_reference(eeg_filt)
        
        # --- Process fNIRS Session (OD -> Bandpass -> MBLL) ---
        session_nirs = nirs_cnt[s_idx]
        session_nirs_mrk = nirs_mrk[s_idx]
        nirs_x = session_nirs.x  # shape: (T, channels_wavelengths)
        nirs_fs = float(session_nirs.fs)
        
        # Split 760nm and 850nm (36 channels each), ensure positive intensity
        n_optodes = 36
        nirs_760_raw = np.maximum(nirs_x[:, :n_optodes].T, 1e-4)
        nirs_850_raw = np.maximum(nirs_x[:, n_optodes:2*n_optodes].T, 1e-4)
        
        # Continuous session baseline I0
        i0_760 = nirs_760_raw.mean(axis=1, keepdims=True)
        i0_850 = nirs_850_raw.mean(axis=1, keepdims=True)
        
        # 1. Optical density change: Delta OD = -ln(I(t) / I0)
        od_760 = -np.log(nirs_760_raw / i0_760)
        od_850 = -np.log(nirs_850_raw / i0_850)
        
        # 2. Continuous bandpass filter (0.01 - 0.10 Hz)
        od_760_filt = butter_bandpass_filter(od_760, lowcut=0.01, highcut=0.1, fs=nirs_fs)
        od_850_filt = butter_bandpass_filter(od_850, lowcut=0.01, highcut=0.1, fs=nirs_fs)
        
        # Session Event Markers
        eeg_mrk_times = session_eeg_mrk.time
        nirs_mrk_times = session_nirs_mrk.time
        mrk_descs = session_eeg_mrk.event.desc
        
        for idx_ev, (t_eeg_ms, t_nirs_ms, desc) in enumerate(zip(eeg_mrk_times, nirs_mrk_times, mrk_descs)):
            # In BBCI mental arithmetic experiment: desc=16 is Subtraction (MA=1), desc=32 is Rest (Rest=0)
            if desc == 16:
                lbl = 1
            elif desc == 32:
                lbl = 0
            else:
                continue
                
            eeg_onset_sec = float(t_eeg_ms) / 1000.0
            nirs_onset_sec = float(t_nirs_ms) / 1000.0
            
            # Epoch EEG: 0.0s to 10.0s (1000 points @ 100Hz)
            eeg_start = int(eeg_onset_sec * eeg_fs)
            eeg_end = eeg_start + int(10.0 * eeg_fs)
            if eeg_end > eeg_car.shape[1]:
                continue
            eeg_epoch = eeg_car[:, eeg_start:eeg_end]
            # Resample EEG from eeg_fs (200Hz, 2000 points) to target 100Hz (1000 points)
            eeg_epoch = signal.resample(eeg_epoch, 1000, axis=-1)
                
            # Baseline subtract EEG (-2.0s to 0.0s)
            base_start = max(0, eeg_start - int(2.0 * eeg_fs))
            base_eeg = eeg_car[:, base_start:eeg_start].mean(axis=-1, keepdims=True)
            eeg_epoch = eeg_epoch - base_eeg
            
            # Epoch fNIRS: 0.0s to 12.0s
            nirs_start = int(nirs_onset_sec * nirs_fs)
            nirs_end = nirs_start + int(12.0 * nirs_fs)
            if nirs_end > od_760_filt.shape[1]:
                continue
                
            # Trial baseline subtraction on Delta OD [-2.0s, 0.0s]
            nirs_base_start = max(0, nirs_start - int(2.0 * nirs_fs))
            base_od_760 = od_760_filt[:, nirs_base_start:nirs_start].mean(axis=-1, keepdims=True)
            base_od_850 = od_850_filt[:, nirs_base_start:nirs_start].mean(axis=-1, keepdims=True)
            
            od_760_epoch = od_760_filt[:, nirs_start:nirs_end] - base_od_760
            od_850_epoch = od_850_filt[:, nirs_start:nirs_end] - base_od_850
            
            # 3. MBLL Inversion to micromolar hemoglobin concentrations
            od_stack = np.stack([od_760_epoch, od_850_epoch], axis=1)  # (36, 2, T)
            od_tensor = torch.from_numpy(od_stack).unsqueeze(0).float()
            
            hbo_tensor, hbr_tensor = od_to_hemoglobin_tensor(od_tensor, inv_tensor)
            fnirs_72 = torch.cat([hbo_tensor.squeeze(0), hbr_tensor.squeeze(0)], dim=0).numpy()  # (72, T)
            
            # Resample fNIRS to exact target 124 points (12.0s -> effective fs = 124/12 = 10.333 Hz)
            fnirs_resampled = signal.resample(fnirs_72, 124, axis=-1)
                
            all_eeg_trials.append(eeg_epoch)
            all_fnirs_trials.append(fnirs_resampled)
            all_labels.append(lbl)
            
    assert len(all_labels) > 0, f"No trials extracted for Sub-{subject_id:02d}."
    
    eeg_out = torch.from_numpy(np.stack(all_eeg_trials)).float()
    fnirs_out = torch.from_numpy(np.stack(all_fnirs_trials)).float()
    labels_out = torch.tensor(all_labels, dtype=torch.long)
    
    payload = {
        "eeg": eeg_out,
        "fnirs": fnirs_out,
        "labels": labels_out,
        "eeg_fs": 100.0,
        "fnirs_fs": 124.0 / 12.0,  # 10.333333333333334 Hz
        "metadata": {
            "source": "TU Berlin Real Open-Access Dataset",
            "subject_id": subject_id,
            "total_trials": len(all_labels),
            "ma_trials": int((labels_out == 1).sum().item()),
            "rest_trials": int((labels_out == 0).sum().item()),
            "eeg_channels": EEG_TARGET_30,
            "fnirs_channels": [f"Ch{i:02d}" for i in range(1, 37)],
            "pipeline_version": "v2_eeg30_clean_od_mbll"
        }
    }
    torch.save(payload, out_pt_path)
    print(f"[+] Successfully converted Sub-{subject_id:02d}: {len(all_labels)} trials saved to {out_pt_path}")
    return out_pt_path
