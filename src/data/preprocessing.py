"""
Standardized Preprocessing Pipeline for EEG-fNIRS Hybrid BCI.
Compliant with Phase 1 decisions:
- EEG: 0.5-40Hz Bandpass, CAR Rereferencing, Downsampled to 100Hz, 0~10s window (1000 pts).
- fNIRS: Dual-wavelength ΔOD, MBLL to Δ[HbO] & Δ[HbR], 0.01-0.2Hz Bandpass, 0~12s window (125 pts).
- Baseline Correction: -2.0s ~ 0.0s pre-stimulus mean subtraction.
- Output: PyTorch .pt tensor cache.
"""

from pathlib import Path
from typing import Dict, Tuple, Optional
import numpy as np
import scipy.io as sio
import scipy.signal as signal
import torch

from src.data.mbll import compute_mbll_inversion_matrix


def butter_bandpass_filter(
    data: np.ndarray,
    lowcut: float,
    highcut: float,
    fs: float,
    order: int = 4
) -> np.ndarray:
    """Zero-phase forward-backward Butterworth bandpass filter using SOS format."""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = signal.butter(order, [low, high], btype="band", output="sos")
    filtered = signal.sosfiltfilt(sos, data, axis=-1)
    return filtered


def preprocess_subject_mental_arithmetic(
    raw_file_path: Path,
    output_dir: Path,
    target_eeg_fs: float = 100.0,
    dpf: float = 6.0,
    optode_distance_mm: float = 30.0,
) -> Path:
    """
    Process raw subject data into trial-level PyTorch tensor epochs.
    """
    assert raw_file_path.exists(), f"Raw file {raw_file_path} not found."
    mat = sio.loadmat(raw_file_path)
    
    # 1. Unpack Raw Arrays
    eeg_raw = mat["eeg_data"]         # (30, T_eeg) scalp channels
    eeg_fs = float(mat["eeg_fs"][0, 0])
    
    fnirs_760 = mat["fnirs_760"]       # (36, T_fnirs)
    fnirs_850 = mat["fnirs_850"]       # (36, T_fnirs)
    fnirs_fs = float(mat["fnirs_fs"][0, 0])
    
    onsets = mat["trial_onsets_sec"].flatten()  # (N_trials,)
    # Convert labels from 1/2 to 0/1 (0: Mental Arithmetic, 1: Rest)
    raw_labels = mat["labels"].flatten()
    labels = np.where(raw_labels == 1, 0, 1).astype(np.int64)
    
    # 2. Preprocess EEG: Bandpass (0.5 - 40 Hz) & CAR
    eeg_filtered = butter_bandpass_filter(eeg_raw, lowcut=0.5, highcut=40.0, fs=eeg_fs)
    # Common Average Reference (CAR)
    car = np.mean(eeg_filtered, axis=0, keepdims=True)
    eeg_car = eeg_filtered - car
    
    # Linear-phase polyphase FIR downsampling to 100 Hz (avoids IIR boundary transient ripples)
    decimation_factor = int(round(eeg_fs / target_eeg_fs))
    eeg_downsampled = signal.resample_poly(eeg_car, up=1, down=decimation_factor, axis=-1)
    actual_eeg_fs = eeg_fs / decimation_factor
    
    # 3. Preprocess fNIRS: Intensity -> ΔOD -> MBLL -> Bandpass (0.01 - 0.2 Hz)
    # Baseline intensity I0 across time
    I0_760 = np.mean(fnirs_760, axis=-1, keepdims=True)
    I0_850 = np.mean(fnirs_850, axis=-1, keepdims=True)
    
    # Optical density change: ΔOD = -ln(I / I0)
    delta_od_760 = -np.log(np.clip(fnirs_760 / (I0_760 + 1e-8), 1e-6, None))
    delta_od_850 = -np.log(np.clip(fnirs_850 / (I0_850 + 1e-8), 1e-6, None))
    
    # Solve MBLL with wavelength-specific DPF (760nm: 6.51, 850nm: 5.86)
    inv_mat = compute_mbll_inversion_matrix(
        wavelength_1=760,
        wavelength_2=850,
        dpf_1=6.51,
        dpf_2=5.86,
        optode_distance_mm=optode_distance_mm
    )
    
    # delta_od: shape (36, 2, T)
    delta_od = np.stack([delta_od_760, delta_od_850], axis=1)
    # Reshape for matrix multiplication: (36, T, 2) @ (2, 2).T -> (36, T, 2)
    conc = np.matmul(delta_od.transpose(0, 2, 1), inv_mat.T)
    # Convert from mol/L to μmol/L (multiply by 1e6)
    delta_hbo = conc[:, :, 0] * 1e6  # (36, T)
    delta_hbr = conc[:, :, 1] * 1e6  # (36, T)
    
    # Bandpass filter (0.01 - 0.2 Hz)
    hbo_filtered = butter_bandpass_filter(delta_hbo, lowcut=0.01, highcut=0.20, fs=fnirs_fs)
    hbr_filtered = butter_bandpass_filter(delta_hbr, lowcut=0.01, highcut=0.20, fs=fnirs_fs)
    # Stack into 72 channels: 36 HbO + 36 HbR
    fnirs_72ch = np.concatenate([hbo_filtered, hbr_filtered], axis=0)  # (72, T_fnirs)
    
    # 4. Epoching & Baseline Subtraction
    # EEG window: 0.0s to 10.0s (1000 points @ 100Hz), baseline: -2.0s to 0.0s
    # fNIRS window: 0.0s to 12.0s (125 points @ 10.4Hz), baseline: -2.0s to 0.0s
    eeg_epochs = []
    fnirs_epochs = []
    valid_labels = []
    
    eeg_win_len = int(10.0 * actual_eeg_fs)    # 1000 points
    fnirs_win_len = int(12.0 * fnirs_fs)       # 124-125 points
    
    for onset_sec, lbl in zip(onsets, labels):
        # EEG indices
        base_eeg_start = int((onset_sec - 2.0) * actual_eeg_fs)
        base_eeg_end = int(onset_sec * actual_eeg_fs)
        task_eeg_start = base_eeg_end
        task_eeg_end = task_eeg_start + eeg_win_len
        
        # fNIRS indices
        base_fnirs_start = int((onset_sec - 2.0) * fnirs_fs)
        base_fnirs_end = int(onset_sec * fnirs_fs)
        task_fnirs_start = base_fnirs_end
        task_fnirs_end = task_fnirs_start + fnirs_win_len
        
        # Boundary check
        if (task_eeg_end <= eeg_downsampled.shape[-1] and 
            task_fnirs_end <= fnirs_72ch.shape[-1] and 
            base_eeg_start >= 0 and 
            base_fnirs_start >= 0):
            
            # EEG baseline correction
            eeg_baseline = np.mean(eeg_downsampled[:, base_eeg_start:base_eeg_end], axis=-1, keepdims=True)
            eeg_trial = eeg_downsampled[:, task_eeg_start:task_eeg_end] - eeg_baseline
            
            # fNIRS baseline correction
            fnirs_baseline = np.mean(fnirs_72ch[:, base_fnirs_start:base_fnirs_end], axis=-1, keepdims=True)
            fnirs_trial = fnirs_72ch[:, task_fnirs_start:task_fnirs_end] - fnirs_baseline
            
            eeg_epochs.append(eeg_trial)
            fnirs_epochs.append(fnirs_trial)
            valid_labels.append(lbl)
            
    # Convert to Tensors
    eeg_tensor = torch.from_numpy(np.stack(eeg_epochs, axis=0)).float()       # (N, 28, 1000)
    fnirs_tensor = torch.from_numpy(np.stack(fnirs_epochs, axis=0)).float()   # (N, 72, 125)
    labels_tensor = torch.from_numpy(np.array(valid_labels)).long()           # (N,)
    
    # 5. Persist as PyTorch Cache
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "ma_epochs.pt"
    torch.save({
        "eeg": eeg_tensor,
        "fnirs": fnirs_tensor,
        "labels": labels_tensor,
        "eeg_fs": actual_eeg_fs,
        "fnirs_fs": fnirs_fs,
        "metadata": {
            "eeg_channels": 28,
            "fnirs_channels": 72,
            "num_trials": len(valid_labels),
            "classes": ["Mental_Arithmetic", "Rest"]
        }
    }, out_file)
    
    print(f"Preprocessed {len(valid_labels)} trials successfully saved to {out_file}")
    print(f"Tensor shapes -> EEG: {eeg_tensor.shape}, fNIRS: {fnirs_tensor.shape}, Labels: {labels_tensor.shape}")
    return out_file


def offline_euclidean_alignment(X: np.ndarray, reg_eps: float = 1e-5) -> np.ndarray:
    """
    Standard Offline Transductive Euclidean Alignment (He & Wu, IEEE TBME 2020).
    X: (N, C, T)
    """
    N, C, T = X.shape
    covs = np.zeros((N, C, C))
    for i in range(N):
        covs[i] = np.cov(X[i]) + reg_eps * np.eye(C)
    R_bar = np.mean(covs, axis=0)

    u, s, vh = np.linalg.svd(R_bar)
    inv_sqrt = u @ np.diag(1.0 / np.sqrt(s)) @ vh
    X_aligned = np.zeros_like(X)
    for i in range(N):
        X_aligned[i] = inv_sqrt @ X[i]
    return X_aligned


class CausalRecursiveEA:
    """
    Causal Recursive Euclidean Alignment (CrEA) for zero-leakage streaming BCI.
    
    Mathematically eliminates transductive future-information leakage:
    When trial k arrives, only trials 1 ... k and an empirical Bayes source prior
    R_source (from training participants) are used to update reference covariance:
        R_k = ( (k - 1 + alpha) / (k + alpha) ) * R_{k-1} + ( 1 / (k + alpha) ) * C_k
        tilde{X}_k = R_k^{-1/2} X_k
    """
    def __init__(
        self,
        channels: int = 30,
        reg_eps: float = 1e-5,
        shrinkage_alpha: float = 5.0,
        R_source: Optional[np.ndarray] = None
    ):
        self.channels = channels
        self.reg_eps = reg_eps
        self.alpha = float(shrinkage_alpha)
        if R_source is not None:
            self.R_source = np.array(R_source, dtype=np.float64)
        else:
            self.R_source = np.eye(channels, dtype=np.float64)
        self.reset()

    def reset(self) -> None:
        self.k = 0
        self.R_acc = self.alpha * self.R_source.copy()
        self.total_weight = self.alpha

    def update_and_align_trial(self, x_trial: np.ndarray) -> np.ndarray:
        """
        Stream a single trial X_k: (C, T) -> returns aligned trial tilde{X}_k: (C, T).
        """
        C, T = x_trial.shape
        c_k = np.cov(x_trial) + self.reg_eps * np.eye(C)
        self.k += 1
        self.R_acc += c_k
        self.total_weight += 1.0

        R_bar = self.R_acc / self.total_weight
        u, s, vh = np.linalg.svd(R_bar)
        inv_sqrt = u @ np.diag(1.0 / np.sqrt(s)) @ vh
        return inv_sqrt.astype(x_trial.dtype) @ x_trial

    def transform_sequence(self, X: np.ndarray) -> np.ndarray:
        """
        Process a sequence of trials (N, C, T) in strict causal temporal arrival order.
        """
        self.reset()
        N, C, T = X.shape
        X_out = np.zeros_like(X)
        for i in range(N):
            X_out[i] = self.update_and_align_trial(X[i])
        return X_out

    def compute_frobenius_convergence(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Diagnose trial-by-trial relative Frobenius error vs full offline covariance:
        E_k = || R_k - R_offline ||_F / || R_offline ||_F
        Returns:
            errors: (N,) relative Frobenius errors for k=1..N
            condition_numbers: (N,) condition numbers of R_k
        """
        N, C, T = X.shape
        covs = np.zeros((N, C, C))
        for i in range(N):
            covs[i] = np.cov(X[i]) + self.reg_eps * np.eye(C)
        R_offline = np.mean(covs, axis=0)
        norm_offline = np.linalg.norm(R_offline, "fro")

        self.reset()
        errors = np.zeros(N)
        conds = np.zeros(N)

        for i in range(N):
            self.k += 1
            self.R_acc += covs[i]
            self.total_weight += 1.0
            R_k = self.R_acc / self.total_weight
            errors[i] = np.linalg.norm(R_k - R_offline, "fro") / norm_offline
            conds[i] = np.linalg.cond(R_k)

        return errors, conds

