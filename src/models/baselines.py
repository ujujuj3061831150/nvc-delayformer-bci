"""
Phase 3 Baseline Model Suite for EEG-fNIRS Hybrid BCI.
Implements:
1. EEGNetClassifier: Unimodal EEG gold standard baseline (Lawhern et al. 2018).
2. FNIRSClassifier: Unimodal fNIRS deep convolutional baseline.
3. ConcatFusionClassifier: Traditional multimodal feature concatenation + MLP (Fazli et al. 2012).
4. StandardCrossAttentionClassifier: Unconstrained cross-attention without NVC delay prior or causality (Buccino et al. 2016; Vaswani et al. 2017).
"""

from typing import Tuple, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F

from src.models.nvc_net import EEGEncoder, FNIRSEncoder


class AuthenticEEGNet2D(nn.Module):
    """
    Authentic EEGNet implementation following Lawhern et al. (J. Neural Eng. 2018).
    Block 1: Temporal Conv2D -> BatchNorm -> Depthwise Conv2D (spatial) -> BatchNorm -> ELU -> AvgPool -> Dropout
    Block 2: Separable Conv2D (Depthwise -> Pointwise) -> BatchNorm -> ELU -> AvgPool -> Dropout
    Classification: Flatten -> Linear
    """
    def __init__(
        self,
        in_channels: int = 30,
        num_classes: int = 2,
        F1: int = 8,
        D: int = 2,
        F2: int = 16,
        kernel_len: int = 64,
        dropout: float = 0.25,
        time_points: int = 1000
    ):
        super().__init__()
        self.in_channels = in_channels
        self.F1 = F1
        self.D = D
        self.F2 = F2

        # Block 1
        self.conv1 = nn.Conv2d(1, F1, (1, kernel_len), padding=(0, kernel_len // 2), bias=False)
        self.bn1 = nn.BatchNorm2d(F1)
        self.depthwise = nn.Conv2d(F1, F1 * D, (in_channels, 1), groups=F1, bias=False)
        self.bn2 = nn.BatchNorm2d(F1 * D)
        self.act1 = nn.ELU()
        self.pool1 = nn.AvgPool2d((1, 4))
        self.drop1 = nn.Dropout(dropout)

        # Block 2
        self.separable_depth = nn.Conv2d(F1 * D, F1 * D, (1, 16), padding=(0, 8), groups=F1 * D, bias=False)
        self.separable_point = nn.Conv2d(F1 * D, F2, (1, 1), bias=False)
        self.bn3 = nn.BatchNorm2d(F2)
        self.act2 = nn.ELU()
        self.pool2 = nn.AvgPool2d((1, 8))
        self.drop2 = nn.Dropout(dropout)

        # Dynamic dimension check for classifier
        with torch.no_grad():
            dummy = torch.zeros(1, 1, in_channels, time_points)
            feats = self.forward_features(dummy)
            n_features = feats.shape[1]

        self.classifier = nn.Linear(n_features, num_classes)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 1, C, T)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.depthwise(x)
        x = self.bn2(x)
        x = self.act1(x)
        x = self.pool1(x)
        x = self.drop1(x)

        x = self.separable_depth(x)
        x = self.separable_point(x)
        x = self.bn3(x)
        x = self.act2(x)
        x = self.pool2(x)
        x = self.drop2(x)

        return torch.flatten(x, 1)

    def forward(self, eeg: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        # eeg: (B, C, T) -> (B, 1, C, T)
        if eeg.dim() == 3:
            eeg = eeg.unsqueeze(1)
        feats = self.forward_features(eeg)
        return self.classifier(feats)


class EEGNetClassifier(nn.Module):
    """Unimodal EEG-only classifier (1D CNN encoder)."""
    def __init__(self, in_channels: int = 30, num_classes: int = 2, feature_dim: int = 64, dropout: float = 0.25):
        super().__init__()
        self.encoder = EEGEncoder(in_channels=in_channels, out_dim=feature_dim, dropout=dropout)
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        feat = self.encoder(eeg)         # (B, T_red, D)
        pooled = feat.mean(dim=1)        # (B, D)
        logits = self.classifier(pooled) # (B, num_classes)
        return logits


class FNIRSClassifier(nn.Module):
    """Unimodal fNIRS-only classifier."""
    def __init__(self, in_channels: int = 72, num_classes: int = 2, feature_dim: int = 64, dropout: float = 0.25):
        super().__init__()
        self.encoder = FNIRSEncoder(in_channels=in_channels, out_dim=feature_dim, dropout=dropout)
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, fnirs: Optional[torch.Tensor] = None, *args, **kwargs) -> torch.Tensor:
        target_fnirs = fnirs if fnirs is not None else eeg
        feat = self.encoder(target_fnirs) # (B, T_fnirs, D)
        pooled = feat.mean(dim=1)         # (B, D)
        logits = self.classifier(pooled)  # (B, num_classes)
        return logits


class ConcatFusionClassifier(nn.Module):
    """Traditional Multimodal Feature Concatenation + MLP."""
    def __init__(self, eeg_channels: int = 30, fnirs_channels: int = 72, num_classes: int = 2, feature_dim: int = 64, dropout: float = 0.25):
        super().__init__()
        self.eeg_encoder = EEGEncoder(in_channels=eeg_channels, out_dim=feature_dim, dropout=dropout)
        self.fnirs_encoder = FNIRSEncoder(in_channels=fnirs_channels, out_dim=feature_dim, dropout=dropout)
        
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, fnirs: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        eeg_feat = self.eeg_encoder(eeg).mean(dim=1)        # (B, D)
        fnirs_feat = self.fnirs_encoder(fnirs).mean(dim=1)  # (B, D)
        concat = torch.cat([eeg_feat, fnirs_feat], dim=-1)  # (B, 2*D)
        logits = self.classifier(concat)                    # (B, num_classes)
        return logits


class StandardCrossAttentionClassifier(nn.Module):
    """
    SOTA Unconstrained Multimodal Cross-Attention.
    Standard Transformer Cross-Attention without Gaussian physiological delay prior and without causality mask.
    """
    def __init__(self, eeg_channels: int = 30, fnirs_channels: int = 72, num_classes: int = 2, feature_dim: int = 64, num_heads: int = 4, dropout: float = 0.25):
        super().__init__()
        self.eeg_encoder = EEGEncoder(in_channels=eeg_channels, out_dim=feature_dim, dropout=dropout)
        self.fnirs_encoder = FNIRSEncoder(in_channels=fnirs_channels, out_dim=feature_dim, dropout=dropout)
        
        self.cross_attn = nn.MultiheadAttention(embed_dim=feature_dim, num_heads=num_heads, dropout=dropout, batch_first=True)
        self.norm = nn.LayerNorm(feature_dim)
        
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, fnirs: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        eeg_feat = self.eeg_encoder(eeg)        # (B, T_eeg, D)
        fnirs_feat = self.fnirs_encoder(fnirs)  # (B, T_fnirs, D)
        
        # Standard unconstrained cross attention: Query=fnirs, Key/Val=eeg
        attn_out, _ = self.cross_attn(query=fnirs_feat, key=eeg_feat, value=eeg_feat)
        fused_feat = self.norm(fnirs_feat + attn_out)  # Residual connection + LayerNorm
        
        fused_pool = fused_feat.mean(dim=1)    # (B, D)
        eeg_pool = eeg_feat.mean(dim=1)        # (B, D)
        joint_repr = torch.cat([fused_pool, eeg_pool], dim=-1)
        logits = self.classifier(joint_repr)
        return logits


class FGANetClassifier(nn.Module):
    """
    FGANet: fNIRS-Guided Attention Network for Hybrid EEG-fNIRS Brain-Computer Interfaces.
    Reference: Kwak, Song, Kim (IEEE Trans. Neural Syst. Rehabil. Eng., 2022).
    Core Mechanism:
    - Independent spatio-temporal feature extraction for EEG and fNIRS.
    - fNIRS-guided attention module: fNIRS temporal representations generate attention
      weights that modulate electrophysiological features.
    - Dual-stream score fusion combining standalone EEG predictions with fNIRS-guided attention features.
    """
    def __init__(
        self,
        eeg_channels: int = 30,
        fnirs_channels: int = 72,
        num_classes: int = 2,
        feature_dim: int = 64,
        dropout: float = 0.25
    ):
        super().__init__()
        self.eeg_encoder = EEGEncoder(in_channels=eeg_channels, out_dim=feature_dim, dropout=dropout)
        self.fnirs_encoder = FNIRSEncoder(in_channels=fnirs_channels, out_dim=feature_dim, dropout=dropout)

        # fNIRS-guided attention mapping: maps fNIRS temporal features to attention mask
        self.fnirs_attn_proj = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.Tanh(),
            nn.Linear(feature_dim, feature_dim),
            nn.Sigmoid()
        )

        # Standalone EEG classifier
        self.eeg_classifier = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

        # fNIRS-guided attended feature classifier
        self.guided_classifier = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

        # Learnable score fusion parameter (alpha in (0, 1))
        self.fusion_weight = nn.Parameter(torch.tensor([0.5]))

    def forward(self, eeg: torch.Tensor, fnirs: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        eeg_feat = self.eeg_encoder(eeg)        # (B, T_eeg, D)
        fnirs_feat = self.fnirs_encoder(fnirs)  # (B, T_fnirs, D)

        # Global fNIRS representation generates attention guidance
        fnirs_summary = fnirs_feat.mean(dim=1, keepdim=True)  # (B, 1, D)
        guidance_mask = self.fnirs_attn_proj(fnirs_summary)   # (B, 1, D)

        # Modulate EEG features via fNIRS guidance
        guided_eeg = eeg_feat * guidance_mask                  # (B, T_eeg, D)

        # Pool features across time
        eeg_pool = eeg_feat.mean(dim=1)                        # (B, D)
        guided_pool = guided_eeg.mean(dim=1)                   # (B, D)

        # Branch predictions
        logits_eeg = self.eeg_classifier(eeg_pool)
        logits_guided = self.guided_classifier(guided_pool)

        # Weighted score fusion
        alpha = torch.sigmoid(self.fusion_weight)
        logits = alpha * logits_guided + (1.0 - alpha) * logits_eeg
        return logits


class EFMLNetClassifier(nn.Module):
    """
    EFMLNet: End-to-End Mutual Information Learning-Based Fusion Network for Hybrid EEG-fNIRS.
    Reference: Qiu et al. (IEEE Trans. Instrum. Meas., 2025).
    Core Mechanism:
    - Multi-branch convolutional feature extractors for EEG and fNIRS.
    - Parallel cross-modal mutual representation learning module maximizing shared correlation.
    - Mutual interaction projection and joint end-to-end classification.
    """
    def __init__(
        self,
        eeg_channels: int = 30,
        fnirs_channels: int = 72,
        num_classes: int = 2,
        feature_dim: int = 64,
        dropout: float = 0.25
    ):
        super().__init__()
        self.eeg_encoder = EEGEncoder(in_channels=eeg_channels, out_dim=feature_dim, dropout=dropout)
        self.fnirs_encoder = FNIRSEncoder(in_channels=fnirs_channels, out_dim=feature_dim, dropout=dropout)

        # Cross-modal mutual interaction projection
        self.eeg_mutual_proj = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU()
        )
        self.fnirs_mutual_proj = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU()
        )

        # Bilinear interaction matrix capturing mutual information correlation
        self.mutual_weight = nn.Parameter(torch.empty(feature_dim, feature_dim))
        nn.init.xavier_uniform_(self.mutual_weight)

        # Joint classification head
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, fnirs: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        eeg_feat = self.eeg_encoder(eeg).mean(dim=1)        # (B, D)
        fnirs_feat = self.fnirs_encoder(fnirs).mean(dim=1)  # (B, D)

        # Mutual interaction features
        z_eeg_m = self.eeg_mutual_proj(eeg_feat)            # (B, D)
        z_fnirs_m = self.fnirs_mutual_proj(fnirs_feat)      # (B, D)

        # Cross-modal correlated representation: z_interact = z_eeg_m @ W @ z_fnirs_m.T
        interaction = z_eeg_m @ self.mutual_weight          # (B, D)
        correlated_fnirs = torch.sigmoid(interaction) * z_fnirs_m
        correlated_eeg = torch.sigmoid(z_fnirs_m @ self.mutual_weight.T) * z_eeg_m

        fused = torch.cat([correlated_eeg, correlated_fnirs], dim=-1) # (B, 2*D)
        logits = self.classifier(fused)
        return logits


class MBCATTClassifier(nn.Module):
    """
    MBC-ATT: Multi-Branch Convolutional Network with Cross-Modality Attentional Fusion for EEG-fNIRS.
    Reference: Li et al. (Frontiers in Human Neuroscience, 2024/2025).
    Core Mechanism:
    - Multi-branch convolutional pathways extracting multi-scale temporal dynamics.
    - Symmetric cross-modality attention mechanism (EEG attends to fNIRS, fNIRS attends to EEG).
    - Dense fused concatenation and multi-class readout.
    """
    def __init__(
        self,
        eeg_channels: int = 30,
        fnirs_channels: int = 72,
        num_classes: int = 2,
        feature_dim: int = 64,
        num_heads: int = 4,
        dropout: float = 0.25
    ):
        super().__init__()
        self.eeg_encoder = EEGEncoder(in_channels=eeg_channels, out_dim=feature_dim, dropout=dropout)
        self.fnirs_encoder = FNIRSEncoder(in_channels=fnirs_channels, out_dim=feature_dim, dropout=dropout)

        # Bidirectional cross-modal attention
        self.attn_eeg2fnirs = nn.MultiheadAttention(
            embed_dim=feature_dim, num_heads=num_heads, dropout=dropout, batch_first=True
        )
        self.attn_fnirs2eeg = nn.MultiheadAttention(
            embed_dim=feature_dim, num_heads=num_heads, dropout=dropout, batch_first=True
        )

        self.norm_eeg = nn.LayerNorm(feature_dim)
        self.norm_fnirs = nn.LayerNorm(feature_dim)

        self.classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(feature_dim, num_classes)
        )

    def forward(self, eeg: torch.Tensor, fnirs: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        eeg_feat = self.eeg_encoder(eeg)        # (B, T_eeg, D)
        fnirs_feat = self.fnirs_encoder(fnirs)  # (B, T_fnirs, D)

        # Cross-modality attention: fNIRS queries EEG, EEG queries fNIRS
        eeg_attended, _ = self.attn_fnirs2eeg(query=eeg_feat, key=fnirs_feat, value=fnirs_feat)
        fnirs_attended, _ = self.attn_eeg2fnirs(query=fnirs_feat, key=eeg_feat, value=eeg_feat)

        eeg_out = self.norm_eeg(eeg_feat + eeg_attended).mean(dim=1)       # (B, D)
        fnirs_out = self.norm_fnirs(fnirs_feat + fnirs_attended).mean(dim=1) # (B, D)

        fused = torch.cat([eeg_out, fnirs_out], dim=-1)                    # (B, 2*D)
        logits = self.classifier(fused)
        return logits

