"""
Temporal Fusion Module: Neurovascular Kernel Marginalization & Feature Weighting.

Implements the continuous 2D neurovascular coupling kernel:
K(t_nirs, t_eeg; tau, sigma) = Causal(t_nirs - t_eeg) * Gauss(t_nirs - t_eeg - tau; sigma)
                             * exp(-t_eeg / 1.2) * sigmoid((9.5 - t_nirs) / 0.5)

Marginalizes K into 1D normalized temporal weighting envelopes:
w_nirs(t) and w_eeg(t), such that sum(w_nirs) = 1.0 and sum(w_eeg) = 1.0.
"""

from typing import Tuple
import torch
import torch.nn as nn


def compute_nvc_temporal_envelopes(
    t_nirs_len: int,
    t_eeg_len: int,
    device: torch.device,
    fnirs_sr: float = 124.0 / 12.0,
    eeg_sr: float = 100.0,
    delay_mean: float = 5.0,
    delay_std: float = 1.1,
    use_delay_prior: bool = True,
    use_causal_mask: bool = True,
    task_gate_sec: float = 9.5,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Marginalize the continuous 2D neurovascular coupling kernel into
    discrete normalized 1D temporal receptive envelopes.

    Args:
        t_nirs_len: Length of fNIRS temporal sequence (time points).
        t_eeg_len: Length of EEG temporal sequence (time points).
        device: Torch compute device.
        fnirs_sr: Effective sampling rate of fNIRS (Hz).
        eeg_sr: Effective sampling rate of EEG (Hz).
        delay_mean: Mean hemodynamic latency in seconds (tau_NVC).
        delay_std: Hemodynamic response dispersion in seconds.
        use_delay_prior: Whether to apply Gaussian physiological bias.
        use_causal_mask: Whether to strictly enforce causality (t_eeg <= t_nirs).
        task_gate_sec: Task active duration cutoff (seconds).

    Returns:
        w_nirs: Normalized 1D temporal weight tensor for fNIRS (shape: [t_nirs_len]).
        w_eeg: Normalized 1D temporal weight tensor for EEG (shape: [t_eeg_len]).
    """
    t_nirs = torch.arange(t_nirs_len, device=device, dtype=torch.float32) / fnirs_sr
    t_eeg = torch.arange(t_eeg_len, device=device, dtype=torch.float32) / eeg_sr
    delta_t = t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)  # (t_nirs_len, t_eeg_len)

    delay_mean_clamped = torch.clamp(torch.tensor(float(delay_mean), device=device), min=0.0, max=8.0)

    if use_causal_mask:
        causal = (delta_t >= -1e-4).float()
    else:
        causal = torch.ones_like(delta_t)

    if use_delay_prior:
        gauss = torch.exp(-((delta_t - delay_mean_clamped) ** 2) / (2.0 * (delay_std ** 2) + 1e-8))
    else:
        gauss = torch.ones_like(delta_t)

    eeg_onset = torch.exp(-t_eeg / 1.2)
    task_gate = torch.sigmoid((task_gate_sec - t_nirs) / 0.5)

    K = causal * gauss * eeg_onset.unsqueeze(0) * task_gate.unsqueeze(1)

    k_sum = K.sum() + 1e-8
    w_nirs = K.sum(dim=1) / k_sum
    w_eeg = K.sum(dim=0) / k_sum

    return w_nirs, w_eeg


def apply_temporal_weighting(
    eeg: torch.Tensor,
    fnirs: torch.Tensor,
    w_eeg: torch.Tensor,
    w_nirs: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Apply normalized temporal receptive weights to extract temporally-weighted
    channel features:
    - fNIRS: Weighted linear aggregation across time.
    - EEG: Weighted log-bandpower/energy across time.

    Args:
        eeg: EEG tensor of shape (batch, channels, time_eeg).
        fnirs: fNIRS tensor of shape (batch, channels, time_fnirs).
        w_eeg: EEG weight vector of shape (time_eeg,).
        w_nirs: fNIRS weight vector of shape (time_fnirs,).

    Returns:
        e_feat: Aggregated EEG energy feature of shape (batch, channels_eeg).
        f_feat: Aggregated fNIRS feature of shape (batch, channels_fnirs).
    """
    f_feat = (fnirs * w_nirs.view(1, 1, -1)).sum(dim=-1)
    e_feat = torch.log(((eeg ** 2) * w_eeg.view(1, 1, -1)).sum(dim=-1) + 1e-6)
    return e_feat, f_feat
