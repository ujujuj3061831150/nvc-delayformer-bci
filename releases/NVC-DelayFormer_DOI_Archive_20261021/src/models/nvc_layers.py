"""
Core Novel Neural Architecture Module:
Physiology-Guided Delay Cross-Attention (PD-CA) Layer.

Embodies the Neurovascular Coupling (NVC) delay mechanism:
fNIRS hemodynamics at time t query preceding EEG electrophysiology at time t - τ,
constrained by a Gaussian biological delay prior centered around τ_NVC ≈ 4.5~5.5 seconds
and Buxton's Balloon Model vasodilatory inflow kinetics.
"""

import math
from typing import Tuple, Optional, Any
import torch
import torch.nn as nn
import torch.nn.functional as F


class PhysiologyDelayCrossAttention(nn.Module):
    """
    Cross-Attention layer with explicit biological delay Gaussian bias,
    causal masking, and multiplicative phase-gated temporal envelopes.
    
    Q (Query): Derived from slow hemodynamic fNIRS features (batch, T_nirs, dim)
    K, V (Key, Value): Derived from fast electrophysiological EEG features (batch, T_eeg, dim)
    """

    def __init__(
        self,
        embed_dim: int = 64,
        num_heads: int = 4,
        nvc_delay_mean_sec: float = 5.0,
        nvc_delay_std_sec: float = 1.5,
        eeg_sample_rate: float = 100.0,
        fnirs_sample_rate: float = 10.0,
        learnable_delay: bool = True,
        dropout: float = 0.1,
        multi_head_delays: bool = False,
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
        self.multi_head_delays = multi_head_delays
        if multi_head_delays:
            if learnable_delay:
                self.delay_mean = nn.Parameter(torch.linspace(3.5, 6.5, num_heads))
                self.delay_std = nn.Parameter(torch.full((num_heads,), float(nvc_delay_std_sec)))
            else:
                self.register_buffer("delay_mean", torch.linspace(3.5, 6.5, num_heads))
                self.register_buffer("delay_std", torch.full((num_heads,), float(nvc_delay_std_sec)))
        else:
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
        prior_bias = - ( (t_nirs - t_eeg) - τ_NVC )^2 / (2 * σ^2)
        causal_mask: boolean mask where t_eeg > t_nirs (future EEG)
        """
        t_nirs = torch.arange(t_nirs_len, device=device, dtype=torch.float32) / self.fnirs_sr
        t_eeg = torch.arange(t_eeg_len, device=device, dtype=torch.float32) / self.eeg_sr
        
        # Delta t: shape (1, 1, t_nirs_len, t_eeg_len)
        delta_t = (t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)).unsqueeze(0).unsqueeze(0)
        
        if self.multi_head_delays:
            # delay_mean: (1, num_heads, 1, 1)
            mean_clamped = torch.clamp(self.delay_mean.view(1, self.num_heads, 1, 1), min=0.5, max=8.0)
            std_clamped = torch.clamp(self.delay_std.view(1, self.num_heads, 1, 1), min=0.5, max=4.0)
            diff = delta_t - mean_clamped
            delay_penalty = (diff ** 2) / (2.0 * (std_clamped ** 2) + 1e-8)
            # Asymmetric physiological tail decay: beyond peak latency tau, impose additional decay
            tail_factor = torch.where(delta_t > mean_clamped, 1.0 + 0.3 * (delta_t - mean_clamped), torch.ones_like(delta_t))
            delay_penalty = delay_penalty * tail_factor
            prior_bias = -0.35 * delay_penalty
            causal_mask = (delta_t < -1e-4)  # (1, 1, Tn, Te)
        else:
            delta_t_2d = t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)
            delay_mean_clamped = torch.clamp(self.delay_mean, min=0.0, max=8.0)
            std_clamped = torch.clamp(self.delay_std, min=0.5, max=4.0)
            delay_penalty = ((delta_t_2d - delay_mean_clamped) ** 2) / (2.0 * (std_clamped ** 2) + 1e-8)
            prior_bias = -0.35 * delay_penalty
            causal_mask = (delta_t_2d < -1e-4)
        
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
        Marginalize the 2D neurovascular coupling kernel K(t_nirs, t_eeg; tau, sigma)
        into normalized temporal receptive envelopes w_nirs(t_nirs) and w_eeg(t_eeg).
        """
        eff_eeg_sr = eeg_sr_override if eeg_sr_override > 0.0 else self.eeg_sr
        t_nirs = torch.arange(t_nirs_len, device=device, dtype=torch.float32) / self.fnirs_sr
        t_eeg = torch.arange(t_eeg_len, device=device, dtype=torch.float32) / eff_eeg_sr
        delta_t = t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)

        mean_val = self.delay_mean.mean() if self.multi_head_delays else self.delay_mean
        delay_mean_clamped = torch.clamp(mean_val, min=0.0, max=8.0)

        # Single-factor ablation: only ablate the respective component cleanly
        if use_causal_mask:
            causal = (delta_t >= -1e-4).float()
        else:
            causal = torch.ones_like(delta_t)

        if use_delay_prior:
            gauss = torch.exp(-((delta_t - delay_mean_clamped) ** 2) / (2.0 * (1.1 ** 2) + 1e-8))
        else:
            gauss = torch.ones_like(delta_t)

        eeg_onset = torch.exp(-t_eeg / 1.2)
        task_gate = torch.sigmoid((9.5 - t_nirs) / 0.5)
        K = causal * gauss * eeg_onset.unsqueeze(0) * task_gate.unsqueeze(1)
        w_nirs = K.sum(dim=1) / (K.sum() + 1e-8)
        w_eeg = K.sum(dim=0) / (K.sum() + 1e-8)
        return w_nirs, w_eeg

    def forward(
        self,
        fnirs_q: torch.Tensor,
        eeg_kv: torch.Tensor,
        use_delay_prior: bool = True,
        use_causal_mask: bool = True,
        keep_row_weights_prior: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, t_nirs, _ = fnirs_q.shape
        _, t_eeg, _ = eeg_kv.shape
        
        Q = self.q_proj(fnirs_q).view(batch_size, t_nirs, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(eeg_kv).view(batch_size, t_eeg, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(eeg_kv).view(batch_size, t_eeg, self.num_heads, self.head_dim).transpose(1, 2)
        
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
        prior_bias, causal_mask = self.compute_delay_prior_matrix(t_nirs, t_eeg, fnirs_q.device)
        
        if use_delay_prior:
            if self.multi_head_delays:
                scores = scores + torch.abs(self.prior_scale) * prior_bias
            else:
                scores = scores + torch.abs(self.prior_scale) * prior_bias.unsqueeze(0).unsqueeze(0)
            
        if use_causal_mask:
            if self.multi_head_delays:
                scores = scores.masked_fill(causal_mask, float("-inf"))
            else:
                scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
            
        scores = torch.nan_to_num(scores, nan=-1e4)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = torch.nan_to_num(attn_weights, nan=0.0)
        if use_causal_mask:
            mask_4d = causal_mask if self.multi_head_delays else causal_mask.unsqueeze(0).unsqueeze(0)
            attn_weights = attn_weights.masked_fill(mask_4d, 0.0)
        
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


class MultiHeadPhysiologyCrossAttention(PhysiologyDelayCrossAttention):
    """Alias for multi-head physiological cross-attention."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("multi_head_delays", True)
        super().__init__(*args, **kwargs)


class AttentiveTemporalPyramidPooling(nn.Module):
    """
    Attentive Temporal Pyramid Pooling (TPP) for 3 physiological phases:
    1. Early transient response: [0.0, 3.0] s (or [0, 0.3*T_win] for shortened windows)
    2. Sustained hemodynamic response: (3.0, 7.0] s (or (0.3*T_win, 0.7*T_win])
    3. Late platform / recovery: (7.0, 10.0] s (or (0.7*T_win, T_win])
    Prevents circular shift invariance and captures temporal phase coupling.
    """
    def __init__(self, embed_dim: int = 64):
        super().__init__()
        self.attn_proj = nn.Linear(embed_dim, 1, bias=False)
        self.seg_norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor, time_sec: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, T, D = x.shape
        if time_sec is None:
            t = torch.linspace(0.0, 10.0, T, device=x.device)
            t_max = 10.0
        else:
            t = time_sec
            t_max = float(t[-1].item()) if t.numel() > 0 else 10.0

        if t_max < 9.5:
            # Scaled dynamically for shortened windows T_win < 10.0 s
            b1 = 0.3 * t_max
            b2 = 0.7 * t_max
        else:
            # Standard physiological phases for nominal 10.0s / 12.0s observation
            b1 = 3.0
            b2 = 7.0

        m_early = (t <= b1)
        m_sust = (t > b1) & (t <= b2)
        m_late = (t > b2)

        z1 = x[:, m_early].mean(dim=1) if m_early.any() else x.mean(dim=1)
        z2 = x[:, m_sust].mean(dim=1) if m_sust.any() else x.mean(dim=1)
        z3 = x[:, m_late].mean(dim=1) if m_late.any() else x.mean(dim=1)
        segs = torch.stack([z1, z2, z3], dim=1)  # (B, 3, D)

        weights = F.softmax(self.attn_proj(segs), dim=1)  # (B, 3, 1)
        pooled = (segs * weights).sum(dim=1)  # (B, D)
        return self.seg_norm(pooled)


class EntropyGuidedFeatureWiseGate(nn.Module):
    """
    Uncertainty-Aware Entropy-Guided Feature-Wise Gating with Low-Rank Bottleneck
    and Stream DropPath to prevent cross-modal negative transfer.
    Input: [z_deep (64), z_shallow (64), H(p_deep) (1), H(p_shallow) (1)] -> 130 dims
    Bottleneck: 130 -> 32 -> 64 (low-rank, parameter-efficient)
    """
    def __init__(
        self,
        feature_dim: int = 64,
        bottleneck_dim: int = 32,
        p_droppath: float = 0.15
    ):
        super().__init__()
        self.p_droppath = p_droppath
        in_dim = feature_dim * 2 + 2
        self.gate_net = nn.Sequential(
            nn.Linear(in_dim, bottleneck_dim),
            nn.GELU(),
            nn.Linear(bottleneck_dim, feature_dim),
            nn.Sigmoid()
        )
        nn.init.constant_(self.gate_net[2].bias, 0.0)

    def forward(
        self,
        z_deep: torch.Tensor,
        z_shallow: torch.Tensor,
        logits_deep: torch.Tensor,
        logits_shallow: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        p_deep = F.softmax(logits_deep, dim=-1)
        p_shallow = F.softmax(logits_shallow, dim=-1)
        h_deep = -(p_deep * torch.log(p_deep + 1e-8)).sum(dim=-1, keepdim=True)
        h_shallow = -(p_shallow * torch.log(p_shallow + 1e-8)).sum(dim=-1, keepdim=True)

        gate_in = torch.cat([z_deep, z_shallow, h_deep, h_shallow], dim=-1)
        gate = self.gate_net(gate_in)

        if self.training and self.p_droppath > 0.0:
            rand_val = torch.rand(1, device=z_deep.device).item()
            if rand_val < self.p_droppath / 2.0:
                gate = torch.ones_like(gate)
            elif rand_val < self.p_droppath:
                gate = torch.zeros_like(gate)

        z_fused = gate * z_deep + (1.0 - gate) * z_shallow
        return z_fused, gate
