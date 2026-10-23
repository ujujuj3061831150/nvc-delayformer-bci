"""
Temporal Fusion Module: Physiology-Guided Delay Cross-Attention Layer.

Embodies the Neurovascular Coupling (NVC) delay mechanism:
Slow hemodynamic fNIRS features at time t query fast electrophysiological EEG
features at time t - tau, constrained by a biological Gaussian delay prior
centered around tau_NVC ≈ 4.5~5.5 s and strict temporal causality (t_eeg <= t_nirs).
"""

import math
from typing import Tuple, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from .temporal_weights import compute_nvc_temporal_envelopes


class PhysiologyDelayCrossAttention(nn.Module):
    """
    Cross-Attention layer with explicit biological delay Gaussian bias,
    causal temporal masking, and phase-gated receptive envelopes.

    Q (Query): Derived from slow hemodynamic fNIRS features (batch, T_nirs, dim).
    K, V (Key, Value): Derived from fast electrophysiological EEG features (batch, T_eeg, dim).
    """

    def __init__(
        self,
        embed_dim: int = 64,
        num_heads: int = 4,
        nvc_delay_mean_sec: float = 5.0,
        nvc_delay_std_sec: float = 1.5,
        eeg_sample_rate: float = 25.0,  # effective sequence rate
        fnirs_sample_rate: float = 124.0 / 12.0,  # ~10.333 Hz
        learnable_delay: bool = False,
        dropout: float = 0.1,
    ):
        super().__init__()
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads."

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.eeg_sr = eeg_sample_rate
        self.fnirs_sr = fnirs_sample_rate

        # Projection linear layers
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.gate_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)
        self.prior_scale = nn.Parameter(torch.tensor(1.0))

        # Physiological delay parameters (in seconds)
        if learnable_delay:
            self.delay_mean = nn.Parameter(torch.tensor(float(nvc_delay_mean_sec)))
            self.delay_std = nn.Parameter(torch.tensor(float(nvc_delay_std_sec)))
        else:
            self.register_buffer("delay_mean", torch.tensor(float(nvc_delay_mean_sec)))
            self.register_buffer("delay_std", torch.tensor(float(nvc_delay_std_sec)))

    @property
    def tau(self) -> torch.Tensor:
        return self.delay_mean

    @tau.setter
    def tau(self, val: Any) -> None:
        if isinstance(val, nn.Parameter):
            self.delay_mean = val
        elif isinstance(val, torch.Tensor):
            if isinstance(self.delay_mean, nn.Parameter):
                self.delay_mean.data.copy_(val)
            else:
                self.delay_mean = val
        else:
            if isinstance(self.delay_mean, nn.Parameter):
                self.delay_mean.data.fill_(float(val))
            else:
                self.delay_mean = torch.tensor(float(val), device=self.delay_mean.device)

    @property
    def sigma(self) -> torch.Tensor:
        return self.delay_std

    @sigma.setter
    def sigma(self, val: Any) -> None:
        if isinstance(val, nn.Parameter):
            self.delay_std = val
        elif isinstance(val, torch.Tensor):
            if isinstance(self.delay_std, nn.Parameter):
                self.delay_std.data.copy_(val)
            else:
                self.delay_std = val
        else:
            if isinstance(self.delay_std, nn.Parameter):
                self.delay_std.data.fill_(float(val))
            else:
                self.delay_std = torch.tensor(float(val), device=self.delay_std.device)

    def compute_delay_prior_matrix(
        self,
        t_nirs_len: int,
        t_eeg_len: int,
        device: torch.device,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute Gaussian delay prior and causal mask:
        prior_bias = -0.35 * ((t_nirs - t_eeg) - tau_NVC)^2 / (2 * sigma^2)
        causal_mask: boolean mask where t_eeg > t_nirs (future EEG relative to fNIRS).
        """
        t_nirs = torch.arange(t_nirs_len, device=device, dtype=torch.float32) / self.fnirs_sr
        t_eeg = torch.arange(t_eeg_len, device=device, dtype=torch.float32) / self.eeg_sr

        delta_t = t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)  # (t_nirs_len, t_eeg_len)

        delay_mean_clamped = torch.clamp(self.delay_mean, min=0.0, max=8.0)
        std_clamped = torch.clamp(self.delay_std, min=0.5, max=4.0)
        delay_penalty = ((delta_t - delay_mean_clamped) ** 2) / (2.0 * (std_clamped ** 2) + 1e-8)

        prior_bias = -0.35 * delay_penalty
        causal_mask = (delta_t < -1e-4)

        return prior_bias, causal_mask

    def compute_nvc_temporal_envelopes(
        self,
        t_nirs_len: int,
        t_eeg_len: int,
        device: torch.device,
        use_delay_prior: bool = True,
        use_causal_mask: bool = True,
        eeg_sr_override: float = 0.0,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Convenience wrapper delegating to compute_nvc_temporal_envelopes.
        """
        eff_eeg_sr = eeg_sr_override if eeg_sr_override > 0.0 else self.eeg_sr
        delay_val = float(torch.clamp(self.delay_mean, min=0.0, max=8.0).item())
        return compute_nvc_temporal_envelopes(
            t_nirs_len=t_nirs_len,
            t_eeg_len=t_eeg_len,
            device=device,
            fnirs_sr=self.fnirs_sr,
            eeg_sr=eff_eeg_sr,
            delay_mean=delay_val,
            delay_std=1.1,
            use_delay_prior=use_delay_prior,
            use_causal_mask=use_causal_mask,
        )

    def forward(
        self,
        fnirs_q: torch.Tensor,
        eeg_kv: torch.Tensor,
        use_delay_prior: bool = True,
        use_causal_mask: bool = True,
        keep_row_weights_prior: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            fnirs_q: (batch_size, T_nirs, embed_dim)
            eeg_kv: (batch_size, T_eeg, embed_dim)
            use_delay_prior: bool, whether to add the Gaussian biological bias
            use_causal_mask: bool, whether to enforce strict temporal causality
            keep_row_weights_prior: bool, whether to preserve physiological envelope for row scaling

        Returns:
            out: (batch_size, T_nirs, embed_dim)
            attn_weights: (batch_size, num_heads, T_nirs, T_eeg)
        """
        batch_size, t_nirs, _ = fnirs_q.shape
        _, t_eeg, _ = eeg_kv.shape

        Q = self.q_proj(fnirs_q).view(batch_size, t_nirs, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(eeg_kv).view(batch_size, t_eeg, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(eeg_kv).view(batch_size, t_eeg, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
        prior_bias, causal_mask = self.compute_delay_prior_matrix(t_nirs, t_eeg, fnirs_q.device)

        if use_delay_prior:
            scores = scores + torch.abs(self.prior_scale) * prior_bias.unsqueeze(0).unsqueeze(0)

        if use_causal_mask:
            scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        scores = torch.nan_to_num(scores, nan=-1e4)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = torch.nan_to_num(attn_weights, nan=0.0)
        if use_causal_mask:
            attn_weights = attn_weights.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), 0.0)

        context = torch.matmul(attn_weights, V)
        context = context.transpose(1, 2).contiguous().view(batch_size, t_nirs, self.embed_dim)

        proj_context = self.dropout(self.out_proj(context))
        phase_gate = torch.tanh(self.gate_proj(proj_context))
        coupled = fnirs_q * (1.0 + 0.5 * phase_gate) + proj_context
        normed = self.norm(coupled)

        envelope_delay_prior = True if keep_row_weights_prior else use_delay_prior
        w_nirs, _ = self.compute_nvc_temporal_envelopes(
            t_nirs, t_eeg, fnirs_q.device,
            use_delay_prior=envelope_delay_prior,
            use_causal_mask=use_causal_mask
        )
        scale_t = float(t_nirs) if not torch.jit.is_tracing() else 1.0 * t_nirs
        out = normed * (0.2 + 0.8 * w_nirs.view(1, t_nirs, 1) * scale_t)
        return out, attn_weights
