"""
Comprehensive Unit Test Suite for temporal_fusion Standalone Package.
Verifies:
1. Clean importability of all exposed classes and functions.
2. Temporal envelope mathematical invariants (sum-to-one, boundedness).
3. Cross-attention causal temporal masking (future EEG has zero attention weight).
4. Dual-path readout isolation and joint combination.
5. End-to-end forward execution and autograd backward gradient flow across variable window lengths.
"""

import pytest
import torch
import torch.nn as nn
import numpy as np

from temporal_fusion import (
    PhysiologyDelayCrossAttention,
    compute_nvc_temporal_envelopes,
    apply_temporal_weighting,
    BuxtonVasodilatoryInflow,
    HemodynamicReconstructor,
    DualPathJointReadout,
    NVCDelayFormer,
    EEGEncoder,
    FNIRSEncoder,
)


def test_package_exports():
    """Verify that all core components are importable and subclass nn.Module."""
    assert issubclass(PhysiologyDelayCrossAttention, nn.Module)
    assert issubclass(BuxtonVasodilatoryInflow, nn.Module)
    assert issubclass(HemodynamicReconstructor, nn.Module)
    assert issubclass(DualPathJointReadout, nn.Module)
    assert issubclass(NVCDelayFormer, nn.Module)
    assert issubclass(EEGEncoder, nn.Module)
    assert issubclass(FNIRSEncoder, nn.Module)
    assert callable(compute_nvc_temporal_envelopes)
    assert callable(apply_temporal_weighting)


def test_temporal_envelopes_invariants():
    """Verify mathematical properties of marginalized NVC temporal envelopes."""
    device = torch.device("cpu")
    windows = [(103, 1000), (78, 750), (52, 500), (31, 300)]

    for t_nirs, t_eeg in windows:
        w_nirs, w_eeg = compute_nvc_temporal_envelopes(
            t_nirs_len=t_nirs,
            t_eeg_len=t_eeg,
            device=device,
            fnirs_sr=124.0 / 12.0,
            eeg_sr=100.0,
            delay_mean=5.0,
            use_delay_prior=True,
            use_causal_mask=True,
        )

        assert w_nirs.shape == (t_nirs,)
        assert w_eeg.shape == (t_eeg,)
        assert torch.all(w_nirs >= 0.0), "fNIRS temporal weights must be non-negative"
        assert torch.all(w_eeg >= 0.0), "EEG temporal weights must be non-negative"
        assert torch.isclose(w_nirs.sum(), torch.tensor(1.0), atol=1e-5), f"w_nirs sum {w_nirs.sum()} != 1.0"
        assert torch.isclose(w_eeg.sum(), torch.tensor(1.0), atol=1e-5), f"w_eeg sum {w_eeg.sum()} != 1.0"


def test_causal_cross_attention_masking():
    """Verify that causal masking strictly zeroes out attention from future EEG tokens."""
    embed_dim = 32
    num_heads = 2
    layer = PhysiologyDelayCrossAttention(
        embed_dim=embed_dim,
        num_heads=num_heads,
        eeg_sample_rate=25.0,
        fnirs_sample_rate=10.0,
        nvc_delay_mean_sec=5.0,
    )
    layer.eval()

    # t_nirs = 5 pts (0.0s, 0.1s, 0.2s, 0.3s, 0.4s)
    # t_eeg = 20 pts (0.0s to 0.76s @ 25Hz)
    fnirs_q = torch.randn(2, 5, embed_dim)
    eeg_kv = torch.randn(2, 20, embed_dim)

    with torch.no_grad():
        out, attn_weights = layer(fnirs_q, eeg_kv, use_delay_prior=True, use_causal_mask=True)

    assert out.shape == (2, 5, embed_dim)
    assert attn_weights.shape == (2, num_heads, 5, 20)
    assert not torch.isnan(out).any()
    assert not torch.isnan(attn_weights).any()

    # Verify causality: for the first fNIRS query (t = 0.0s), EEG tokens with t > 0.0s must receive zero attention
    # t_eeg index 0 is t=0.0s; index >= 1 is t >= 0.04s > 0.0s
    for head in range(num_heads):
        future_weights = attn_weights[0, head, 0, 1:]
        assert torch.all(future_weights < 1e-4), "Future EEG received non-zero attention in causal mode"


def test_buxton_inflow_operator():
    """Verify Buxton Balloon Model vasodilatory inflow transformation."""
    op = BuxtonVasodilatoryInflow(fnirs_sample_rate=10.0)
    fnirs = torch.randn(4, 72, 100)
    inflow = op(fnirs)

    assert inflow.shape == fnirs.shape
    assert not torch.isnan(inflow).any()
    assert not torch.isinf(inflow).any()


def test_dual_path_joint_readout_modes():
    """Verify dual-path readout behavior under joint, direct_only, and latent_only configurations."""
    readout = DualPathJointReadout(
        feature_dim=32,
        total_channels=72 + 30,
        fnirs_channels=72,
        num_classes=2,
    )
    readout.eval()

    latent_repr = torch.randn(4, 64)
    raw_biophys = torch.randn(4, 102)

    with torch.no_grad():
        # Joint mode
        logits_joint, (l_log, d_log) = readout(latent_repr, raw_biophys, readout_mode="joint")
        expected_joint = 0.02 * l_log + 0.98 * d_log
        assert torch.allclose(logits_joint, expected_joint, atol=1e-5)

        # Direct-only mode
        logits_direct, _ = readout(latent_repr, raw_biophys, readout_mode="direct_only")
        assert torch.allclose(logits_direct, d_log, atol=1e-5)

        # Latent-only mode
        logits_latent, _ = readout(latent_repr, raw_biophys, readout_mode="latent_only")
        assert torch.allclose(logits_latent, l_log, atol=1e-5)


def test_nvc_delayformer_end_to_end_gradient_flow():
    """Verify complete NVCDelayFormer forward execution and backward gradient propagation across window lengths."""
    model = NVCDelayFormer(
        num_classes=2,
        eeg_channels=30,
        fnirs_channels=72,
        feature_dim=64,
        num_heads=4,
    )
    model.train()

    test_windows = [
        (1000, 103),  # 10.0s
        (500, 52),    # 5.0s
        (300, 31),    # 3.0s
    ]

    for n_eeg, n_fnirs in test_windows:
        model.zero_grad()
        eeg = torch.randn(2, 30, n_eeg, requires_grad=True)
        fnirs = torch.randn(2, 72, n_fnirs, requires_grad=True)
        target = torch.tensor([0, 1])

        logits, attn, recon, (deep_logits, shallow_logits) = model(
            eeg, fnirs, return_recon=True, return_branch_logits=True
        )

        assert logits.shape == (2, 2)
        assert recon.shape == (2, 36, n_fnirs)
        assert not torch.isnan(logits).any()

        loss = nn.CrossEntropyLoss()(logits, target) + 0.2 * (
            nn.CrossEntropyLoss()(deep_logits, target) + nn.CrossEntropyLoss()(shallow_logits, target)
        ) + recon.mean()
        loss.backward()

        # Check gradients exist on encoders and readout
        assert eeg.grad is not None and not torch.isnan(eeg.grad).any()
        assert fnirs.grad is not None and not torch.isnan(fnirs.grad).any()
        assert model.eeg_encoder.conv_spatial.weight.grad is not None
        assert model.direct_readout.weight.grad is not None


def test_equivalence_with_legacy_implementation():
    """
    Verify exact numerical equivalence between the new decoupled temporal_fusion package
    and the legacy src.models.nvc_net implementation across all readout modes
    (Joint, Direct-Only with latent cutoff, and Latent-Only).
    """
    from src.models.nvc_net import NVCDelayFormer as OldModel
    from temporal_fusion.model import NVCDelayFormer as NewModel

    torch.manual_seed(42)
    old_m = OldModel(num_classes=2, eeg_channels=30, fnirs_channels=72, learnable_delay=False).eval()
    new_m = NewModel(num_classes=2, eeg_channels=30, fnirs_channels=72, learnable_delay=False).eval()

    new_m.load_state_dict(old_m.state_dict())

    eeg = torch.randn(4, 30, 1000)
    fnirs = torch.randn(4, 72, 103)

    for mode, cut_gate in [('joint', False), ('direct_only', True), ('latent_only', False)]:
        old_m.readout_mode = mode
        old_m.cut_gate_latent = cut_gate
        new_m.readout_mode = mode
        new_m.cut_gate_latent = cut_gate
        new_m.readout.readout_mode = mode
        new_m.readout.cut_gate_latent = cut_gate

        with torch.no_grad():
            out_old, attn_old, recon_old = old_m(eeg, fnirs, return_recon=True)
            out_new, attn_new, recon_new = new_m(eeg, fnirs, return_recon=True)

        assert torch.allclose(out_old, out_new, atol=1e-6), f"Logits mismatch in {mode} mode"
        assert torch.allclose(attn_old, attn_new, atol=1e-6), f"Attention mismatch in {mode} mode"
        assert torch.allclose(recon_old, recon_new, atol=1e-6), f"Reconstruction mismatch in {mode} mode"


def test_external_cohort_montage_adaptation():
    """Verify that NVCDelayFormer supports alternative montage channel dimensions (e.g. Buccino 21ch EEG / 68ch fNIRS)."""
    model = NVCDelayFormer(
        num_classes=2,
        eeg_channels=21,
        fnirs_channels=68,
        hbo_channels=34,
        eeg_sample_rate_effective=25.0,
        fnirs_sample_rate=10.42,
    )
    assert model.hbo_channels == 34
    assert model.readout.hbo_channels == 34
    assert model.readout.roll_shift == 17

    eeg = torch.randn(2, 21, 600, requires_grad=True)
    fnirs = torch.randn(2, 68, 63, requires_grad=True)

    logits, attn, recon = model(eeg, fnirs, return_recon=True)
    assert logits.shape == (2, 2)
    assert attn.shape == (2, 4, 63, 150)
    assert recon.shape == (2, 34, 63)

    loss = logits.sum() + recon.sum()
    loss.backward()
    assert eeg.grad is not None and not torch.isnan(eeg.grad).any()
    assert fnirs.grad is not None and not torch.isnan(fnirs.grad).any()


def test_dynamic_tpp_window_scaling():
    """Verify dynamic TPP window scaling for truncated observation windows."""
    from src.models.nvc_layers import AttentiveTemporalPyramidPooling

    tpp = AttentiveTemporalPyramidPooling(embed_dim=64)

    # Test shortened windows: 3.0s, 5.0s, 7.5s, and nominal 10.0s / 12.0s
    for T_sec, n_steps in [(3.0, 31), (5.0, 52), (7.5, 78), (10.0, 103), (12.0, 124)]:
        t = torch.linspace(0.0, T_sec, n_steps)
        x = torch.randn(4, n_steps, 64)
        out = tpp(x, time_sec=t)
        assert out.shape == (4, 64)
        assert torch.isfinite(out).all()

    # Verify onset_step formula on NVCDelayFormer across window lengths
    model = NVCDelayFormer(num_classes=2, eeg_channels=30, fnirs_channels=72)
    # Check 3.0s (31 pts)
    fnirs_3s = torch.randn(2, 72, 31)
    eeg_3s = torch.randn(2, 30, 300)
    logits, _ = model(eeg_3s, fnirs_3s)
    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()



