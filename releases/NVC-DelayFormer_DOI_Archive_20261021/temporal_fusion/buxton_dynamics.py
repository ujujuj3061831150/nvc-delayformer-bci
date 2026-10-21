"""
Temporal Fusion Module: Buxton Balloon Inflow Operator & Hemodynamic Reconstructor.

Implements the biophysical vasodilatory state transformation from Buxton's Balloon Model:
D_Buxton[X_fnirs](t) = dX_fnirs/dt + 0.15 * X_fnirs(t)
along with unit-conversion scaling and HbO reconstruction mapping.
"""

from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class BuxtonVasodilatoryInflow(nn.Module):
    """
    Computes Buxton's Balloon Model vasodilatory inflow state:
    D_Buxton[X_fnirs](t) = dX_fnirs/dt + 0.15 * X_fnirs(t)
    with adaptive optical concentration scale compensation.
    """

    def __init__(self, fnirs_sample_rate: float = 124.0 / 12.0):
        super().__init__()
        self.fnirs_sr = fnirs_sample_rate

    def forward(self, fnirs: torch.Tensor) -> torch.Tensor:
        """
        Args:
            fnirs: Tensor of shape (batch, channels, time_steps).

        Returns:
            df_dt + 0.15 * fnirs: Inflow state tensor of shape (batch, channels, time_steps).
        """
        f_rms = torch.sqrt((fnirs.detach() ** 2).mean(dim=(1, 2), keepdim=True) + 1e-12)
        unit_scale = 1.0 + 2500.0 * torch.sigmoid((0.05 - f_rms) * 100.0)

        # Central difference with forward/backward boundaries
        d_mid = (fnirs[:, :, 2:] - fnirs[:, :, :-2]) * (0.5 * self.fnirs_sr)
        d_left = (fnirs[:, :, 1:2] - fnirs[:, :, 0:1]) * self.fnirs_sr
        d_right = (fnirs[:, :, -1:] - fnirs[:, :, -2:-1]) * self.fnirs_sr
        df_dt = torch.cat([d_left, d_mid, d_right], dim=-1)

        return (df_dt + 0.15 * fnirs) * unit_scale


class HemodynamicReconstructor(nn.Module):
    """
    Convolutional reconstructor for task-evoked oxy-hemoglobin (HbO) channels.
    Combines latent cross-modal representations with raw optical inflow.
    """

    def __init__(
        self,
        feature_dim: int = 64,
        hbo_channels: int = 36,
        kernel_size: int = 5,
    ):
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv1d(feature_dim + hbo_channels, hbo_channels, kernel_size=kernel_size, padding=padding)
        nn.init.normal_(self.conv.weight, mean=0.0, std=1e-4)
        nn.init.zeros_(self.conv.bias)

    def forward(
        self,
        latent_features: torch.Tensor,
        inflow_features: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            latent_features: (batch, feature_dim, time_steps)
            inflow_features: (batch, hbo_channels, time_steps)

        Returns:
            recon_pred: (batch, hbo_channels, time_steps)
        """
        recon_in = torch.cat([latent_features, inflow_features], dim=1)
        return self.conv(recon_in)
