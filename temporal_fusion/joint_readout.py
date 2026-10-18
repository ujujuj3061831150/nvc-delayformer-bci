"""
Temporal Fusion Module: Dual-Path Joint Readout & Proxy Gating.

Implements the decoupled dual-path decision mechanism:
- Path 1 (Latent Cross-Attention): MLP over globally pooled cross-modal tokens.
- Path 2 (Direct Biophysical): Linear classifier over temporally weighted channel features.
- Dynamic Gating: Optical proxy reconstruction variance modulates channel blending.
- Readout Combination: logits = 0.02 * latent_logits + 0.98 * direct_logits.
"""

from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class DualPathJointReadout(nn.Module):
    """
    Combines latent cross-modal representations and temporally weighted
    direct channel features into joint classification decisions.
    """

    def __init__(
        self,
        feature_dim: int = 64,
        total_channels: int = 72 + 30,  # 72 fNIRS + 30 EEG
        fnirs_channels: int = 72,
        hbo_channels: Optional[int] = None,
        num_classes: int = 2,
        dropout: float = 0.25,
        readout_mode: str = "joint",
        cut_gate_latent: bool = False,
    ):
        super().__init__()
        self.readout_mode = readout_mode
        self.cut_gate_latent = cut_gate_latent
        self.fnirs_channels = fnirs_channels
        self.hbo_channels = hbo_channels if hbo_channels is not None else (36 if fnirs_channels == 72 else fnirs_channels // 2)
        self.roll_shift = max(1, self.fnirs_channels // 4)

        # 1. Latent MLP Classifier
        self.latent_classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

        # 2. Direct Biophysical Readout
        self.direct_readout = nn.Linear(total_channels, num_classes)

        # 3. Biophysical Batch Normalization (non-affine, tracking statistics)
        self.biophys_norm = nn.BatchNorm1d(total_channels, affine=False, momentum=0.5)

    def forward(
        self,
        latent_repr: torch.Tensor,
        raw_biophys: torch.Tensor,
        recon_detached: Optional[torch.Tensor] = None,
        w_nirs: Optional[torch.Tensor] = None,
        readout_mode: Optional[str] = None,
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Args:
            latent_repr: Concatenated pooled latent features of shape (batch, 2 * feature_dim).
            raw_biophys: Raw aggregated channel features of shape (batch, total_channels).
            recon_detached: Reconstructed optical HbO tensor of shape (batch, 36, T_fnirs).
            w_nirs: Normalized temporal weights for fNIRS of shape (T_fnirs,).
            readout_mode: Override for readout mode ('joint', 'direct_only', 'latent_only').

        Returns:
            logits: Final combined classification logits of shape (batch, num_classes).
            (latent_logits, direct_logits): Individual branch logits for diagnostic auditing.
        """
        eff_mode = self.readout_mode if readout_mode is None else readout_mode

        # 1. Latent logits
        latent_logits = self.latent_classifier(latent_repr)

        # 2. Direct biophysical normalization & optional reconstruction gating
        norm_biophys = self.biophys_norm(raw_biophys)

        if recon_detached is not None and w_nirs is not None and not getattr(self, "disable_gating", False):
            hbo_c = self.hbo_channels
            recon_pool = (recon_detached * w_nirs.view(1, 1, -1)).sum(dim=-1)
            scale_hbo = torch.sqrt(self.biophys_norm.running_var[:hbo_c] + 1e-5)
            mean_hbo = self.biophys_norm.running_mean[:hbo_c]
            norm_recon_hbo = (recon_pool - mean_hbo) / scale_hbo
            g_recon = torch.clamp(torch.sqrt(norm_recon_hbo.detach().var(dim=-1, keepdim=True) + 1e-8), min=0.0, max=1.0)

            f_c = self.fnirs_channels
            effective_fnirs = g_recon * norm_biophys[:, :f_c] + (1.0 - g_recon) * torch.roll(norm_biophys[:, :f_c], shifts=self.roll_shift, dims=-1) * 0.25
            effective_biophys = torch.cat([effective_fnirs, norm_biophys[:, f_c:]], dim=-1)
        else:
            effective_biophys = norm_biophys

        # 3. Direct logits
        direct_logits = self.direct_readout(effective_biophys)

        # 4. Mode-guided combination
        if eff_mode == "direct_only":
            logits = direct_logits
        elif eff_mode == "latent_only":
            logits = latent_logits
        else:
            logits = 0.02 * latent_logits + 0.98 * direct_logits

        return logits, (latent_logits, direct_logits)
