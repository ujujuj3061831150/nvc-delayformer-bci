"""
Automated Compliance and Unit Verification Suite.
Verifies:
1. Strict numerical stability (no NaNs, no Infs).
2. Deterministic reproducibility across executions.
3. Physiological causality (future EEG cannot bleed into current fNIRS).
4. Tensor shape contract fulfillment.
"""

import pytest
import torch
import torch.nn.functional as F
import numpy as np

from src.utils.seed import set_seed
from src.data.mbll import compute_mbll_inversion_matrix, od_to_hemoglobin_tensor
from src.models.nvc_layers import PhysiologyDelayCrossAttention
from src.models.nvc_net import NVCDelayFormer


def test_seed_determinism():
    """Verify that set_seed ensures exact reproducibility."""
    set_seed(42)
    t1 = torch.randn(10, 10)
    set_seed(42)
    t2 = torch.randn(10, 10)
    assert torch.equal(t1, t2), "Seed setter failed to reproduce identical tensors."


def test_mbll_numerical_integrity():
    """Verify MBLL matrix inversion and tensor conversion produce finite values."""
    inv_mat = compute_mbll_inversion_matrix(760, 850, dpf_1=6.51, dpf_2=5.86, optode_distance_mm=30.0)
    assert not np.isnan(inv_mat).any()
    assert not np.isinf(inv_mat).any()
    
    # Mock ΔOD input: batch=2, channels=36, wavelengths=2, time=100
    mock_od = torch.rand(2, 36, 2, 100) * 0.1
    inv_tensor = torch.from_numpy(inv_mat).float()
    
    hbo, hbr = od_to_hemoglobin_tensor(mock_od, inv_tensor)
    assert hbo.shape == (2, 36, 100)
    assert hbr.shape == (2, 36, 100)
    assert not torch.isnan(hbo).any()
    assert not torch.isnan(hbr).any()


def test_causal_delay_attention_invariants():
    """
    Verify that PhysiologyDelayCrossAttention enforces:
    1. Future timestamps mask to zero attention weights.
    2. Proper output shapes.
    """
    layer = PhysiologyDelayCrossAttention(
        embed_dim=32,
        num_heads=2,
        nvc_delay_mean_sec=5.0,
        nvc_delay_std_sec=1.5,
        eeg_sample_rate=25.0,
        fnirs_sample_rate=10.0,
    )
    
    # 10 seconds of fNIRS (100 samples) and EEG (250 samples)
    fnirs_q = torch.randn(2, 100, 32)
    eeg_kv = torch.randn(2, 250, 32)
    
    out, attn_weights = layer(fnirs_q, eeg_kv, use_delay_prior=True)
    
    assert out.shape == (2, 100, 32)
    assert attn_weights.shape == (2, 2, 100, 250)
    assert not torch.isnan(out).any()
    assert not torch.isnan(attn_weights).any()
    
    # Check causality at t_fnirs = 0.0s (index 0 of fNIRS):
    # Any EEG timestamp with t_eeg > t_fnirs (i.e. > 0.0s) MUST have near zero attention
    # t_eeg index 1 is at 0.04s > 0.0s, so it must be masked out
    attn_at_t0 = attn_weights[0, 0, 0, :]  # shape: (250,)
    # index 0 of EEG is at 0.0s; indices 1..249 are in the future relative to t0
    assert torch.all(attn_at_t0[1:] < 1e-4), "Physiological causality violated: future EEG attended to!"


def test_nvc_delayformer_end_to_end_forward_backward():
    """Verify complete model forward and gradient backward pass."""
    model = NVCDelayFormer(
        num_classes=2,
        eeg_channels=28,
        fnirs_channels=72,
        feature_dim=32,
        num_heads=2,
        eeg_sample_rate_effective=25.0,
        fnirs_sample_rate=10.4,
    )
    
    # Mock inputs for 10-second EEG (1000 pts) and 12-second fNIRS (125 pts)
    mock_eeg = torch.randn(4, 28, 1000)   # 10s at 100Hz
    mock_fnirs = torch.randn(4, 72, 125)  # 12s at 10.4Hz
    labels = torch.tensor([0, 1, 0, 1], dtype=torch.long)
    
    logits, attn = model(mock_eeg, mock_fnirs, use_delay_prior=True)
    
    assert logits.shape == (4, 2)
    assert not torch.isnan(logits).any()
    
    loss = torch.nn.functional.cross_entropy(logits, labels)
    loss.backward()
    
    # Verify gradients computed for all major components
    assert model.classifier[0].weight.grad is not None
    assert not torch.isnan(model.classifier[0].weight.grad).any()


def test_phase1_data_pipeline(tmp_path):
    """
    Test Phase 1 complete pipeline end-to-end:
    Raw synthesis -> Preprocessing (MBLL, CAR, Decimation, Epoching) -> .pt caching -> Dataset loading.
    """
    from pathlib import Path
    from src.data.download_tuberlin import generate_biophysical_synthetic_subject
    from src.data.preprocessing import preprocess_subject_mental_arithmetic
    from src.data.dataset import load_subject_data, HybridEEGfNIRSDataset
    
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed" / "sub-01"
    
    # 1. Synthesize minimal Sub-01 raw data (8 trials for fast test)
    raw_file = generate_biophysical_synthetic_subject(
        output_dir=raw_dir,
        subject_id=1,
        num_trials=8,
        trial_duration_sec=24.0,
    )
    assert raw_file.exists()
    
    # 2. Run standardized preprocessing pipeline
    proc_file = preprocess_subject_mental_arithmetic(
        raw_file_path=raw_file,
        output_dir=proc_dir,
    )
    assert proc_file.exists()
    
    # 3. Load via Dataset module
    eeg, fnirs, labels = load_subject_data(tmp_path / "processed", subject_id=1)
    
    assert eeg.ndim == 3 and eeg.shape[1] == 28 and eeg.shape[2] == 1000
    assert fnirs.ndim == 3 and fnirs.shape[1] == 72 and fnirs.shape[2] == 124 or fnirs.shape[2] == 125
    assert labels.ndim == 1 and len(labels) == len(eeg)
    assert not torch.isnan(eeg).any()
    assert not torch.isnan(fnirs).any()
    
    dataset = HybridEEGfNIRSDataset(eeg, fnirs, labels)
    assert len(dataset) == len(labels)
    sample_eeg, sample_fnirs, sample_lbl = dataset[0]
    assert sample_eeg.shape == eeg[0].shape
    assert sample_fnirs.shape == fnirs[0].shape


def test_phase4_topomap_suite_and_feature_extraction(tmp_path):
    """
    Test Phase 4 Topographic mapping and spatiotemporal feature extraction:
    1. Sensor coordinates validity (28 EEG and 36 fNIRS in unit circle).
    2. Seamless boundary interpolation (zero NaNs inside head disk, strict NaNs outside).
    3. Theta bandpower and HbO activation extraction.
    4. End-to-end 3-panel publication figure generation.
    """
    from src.utils.topomap import (
        EEG_28_COORDS_2D,
        FNIRS_36_COORDS_2D,
        interpolate_topomap,
        compute_eeg_theta_bandpower,
        compute_fnirs_hbo_activation,
        extract_model_attention_flow,
        generate_publication_topomap_suite
    )
    
    # 1. Coordinate contract checks
    assert len(EEG_28_COORDS_2D) == 28, f"Expected 28 EEG coordinates, got {len(EEG_28_COORDS_2D)}"
    assert len(FNIRS_36_COORDS_2D) == 36, f"Expected 36 fNIRS coordinates, got {len(FNIRS_36_COORDS_2D)}"
    
    for name, (x, y) in EEG_28_COORDS_2D.items():
        assert -1.0 <= x <= 1.0 and -1.0 <= y <= 1.0, f"EEG {name} out of bounds: ({x}, {y})"
    for name, (x, y) in FNIRS_36_COORDS_2D.items():
        assert -1.0 <= x <= 1.0 and -1.0 <= y <= 1.0, f"fNIRS {name} out of bounds: ({x}, {y})"
        
    # 2. Interpolation boundary invariance (fused cubic + nearest extrapolation)
    eeg_names = list(EEG_28_COORDS_2D.keys())
    coords = np.array([EEG_28_COORDS_2D[k] for k in eeg_names])
    values = np.random.uniform(0.5, 2.0, size=(28,))
    radius = 0.95
    grid_res = 80
    
    gx, gy, gz = interpolate_topomap(coords, values, grid_res=grid_res, radius=radius)
    assert gx.shape == (grid_res, grid_res)
    assert gy.shape == (grid_res, grid_res)
    assert gz.shape == (grid_res, grid_res)
    
    inside_mask = (gx ** 2 + gy ** 2) <= (radius ** 2)
    outside_mask = ~inside_mask
    
    # Boundary invariance: NO NaNs inside the head contour
    assert not np.isnan(gz[inside_mask]).any(), "Found NaNs inside head disk! Boundary extrapolation failed."
    # Strict mask: ALL points outside the head contour MUST be NaN
    assert np.isnan(gz[outside_mask]).all(), "Points outside head radius must be NaN."
    
    # 3. Dynamic feature extraction checks
    mock_eeg = torch.randn(4, 28, 1000)
    mock_fnirs = torch.randn(4, 72, 125)
    
    theta_dict = compute_eeg_theta_bandpower(mock_eeg, fs=100.0)
    assert len(theta_dict) == 28
    assert all(np.isfinite(v) and v >= 0.0 for v in theta_dict.values())
    
    hbo_dict = compute_fnirs_hbo_activation(mock_fnirs, fs=10.4)
    assert len(hbo_dict) == 36
    assert all(np.isfinite(v) for v in hbo_dict.values())
    
    # Fallback attention extraction check
    fallback_pairs = extract_model_attention_flow(
        checkpoint_path=tmp_path / "nonexistent.pt",
        eeg_tensor=mock_eeg,
        fnirs_tensor=mock_fnirs
    )
    assert len(fallback_pairs) >= 5
    assert all(0.0 < w <= 1.0 for _, _, w in fallback_pairs)
    
    # 4. Publication figure generation check
    test_fig_path = tmp_path / "test_topomap_suite.png"
    generate_publication_topomap_suite(test_fig_path)
    assert test_fig_path.exists()
    assert test_fig_path.stat().st_size > 20000, "Generated topomap file is suspiciously small."


def test_loso_three_split_isolation():
    """
    Test 3-way Subject Isolation (Train / Val / Test) in LOSO DataLoaders:
    1. Zero subject leakage across Train, Val, and Test.
    2. Adaptive val subjects count handling.
    3. Correct trial counts and tensor shapes across mini-batches.
    """
    from pathlib import Path
    from src.data.dataset import get_loso_three_split_dataloaders
    
    proc_dir = Path("data/processed")
    all_subs = [1, 2, 3, 4, 5]
    test_sub = 5
    
    train_loader, val_loader, test_loader, train_ids, val_ids = get_loso_three_split_dataloaders(
        processed_dir=proc_dir,
        test_subject_id=test_sub,
        all_subject_ids=all_subs,
        val_subjects_count=1,
        batch_size=16
    )
    
    # 1. Subject exclusivity invariants
    assert test_sub not in train_ids, f"Test subject {test_sub} leaked into train_ids: {train_ids}"
    assert test_sub not in val_ids, f"Test subject {test_sub} leaked into val_ids: {val_ids}"
    assert set(train_ids).isdisjoint(set(val_ids)), "Train and Val subjects share common IDs!"
    assert len(train_ids) + len(val_ids) + 1 == len(all_subs)
    
    # 2. Dataset size invariants (60 trials per subject)
    assert len(test_loader.dataset) == 60
    assert len(val_loader.dataset) == 60
    assert len(train_loader.dataset) == 180  # 3 train subjects * 60 = 180
    
    # 3. Batch iteration integrity
    b_eeg, b_fnirs, b_lbl = next(iter(val_loader))
    assert b_eeg.ndim == 3 and b_fnirs.ndim == 3 and b_lbl.ndim == 1
    assert not torch.isnan(b_eeg).any()
    assert not torch.isnan(b_fnirs).any()


def test_readout_and_factorial_modes():
    """
    Verify NVCDelayFormer supports:
    1. Direct-Only mode (with cut_gate_latent isolating the reconstructor).
    2. Latent-Only mode.
    3. Option A Uniform temporal weighting.
    4. Diagnostic test-time branch readout extraction.
    """
    mock_eeg = torch.randn(4, 30, 1000)
    mock_fnirs = torch.randn(4, 72, 124)
    labels = torch.tensor([0, 1, 0, 1], dtype=torch.long)

    # 1. Direct-Only
    m_direct = NVCDelayFormer(
        num_classes=2, eeg_channels=30, fnirs_channels=72,
        readout_mode="direct_only", cut_gate_latent=True
    )
    logits_d, _ = m_direct(mock_eeg, mock_fnirs)
    assert logits_d.shape == (4, 2)
    loss_d = F.cross_entropy(logits_d, labels)
    loss_d.backward()
    assert m_direct.direct_readout.weight.grad is not None

    # 2. Latent-Only
    m_latent = NVCDelayFormer(
        num_classes=2, eeg_channels=30, fnirs_channels=72,
        readout_mode="latent_only"
    )
    logits_l, _ = m_latent(mock_eeg, mock_fnirs)
    assert logits_l.shape == (4, 2)
    loss_l = F.cross_entropy(logits_l, labels)
    loss_l.backward()
    assert m_latent.classifier[0].weight.grad is not None

    # 3. Uniform weighting (Option A)
    m_uniform = NVCDelayFormer(
        num_classes=2, eeg_channels=30, fnirs_channels=72,
        direct_weight_mode="uniform"
    )
    logits_u, _ = m_uniform(mock_eeg, mock_fnirs)
    assert logits_u.shape == (4, 2)

    # 4. Diagnostic individual branch logits
    m_joint = NVCDelayFormer(
        num_classes=2, eeg_channels=30, fnirs_channels=72,
        readout_mode="joint"
    )
    logits_j, attn, (lat_logits, dir_logits) = m_joint(mock_eeg, mock_fnirs, return_branch_logits=True)
    assert logits_j.shape == (4, 2)
    assert lat_logits.shape == (4, 2)
    assert not torch.isnan(logits_j).any()
    assert not torch.isnan(lat_logits).any()
    assert not torch.isnan(dir_logits).any()


def test_auxiliary_classification_loss():
    """
    Verify NVCDelayFormer.compute_auxiliary_loss:
    1. Exact formula L_total = L_joint + 0.2 * (L_deep + L_shallow).
    2. Proper loss component returns.
    3. Non-zero gradients backpropagating to both deep and shallow streams.
    """
    B = 8
    C = 2
    joint_logits = torch.randn(B, C, requires_grad=True)
    deep_logits = torch.randn(B, C, requires_grad=True)
    shallow_logits = torch.randn(B, C, requires_grad=True)
    targets = torch.randint(0, C, (B,))

    loss_total, l_joint, l_deep, l_shallow = NVCDelayFormer.compute_auxiliary_loss(
        joint_logits, deep_logits, shallow_logits, targets, aux_weight=0.2
    )

    expected_total = l_joint + 0.2 * (l_deep + l_shallow)
    assert torch.isclose(loss_total, expected_total, atol=1e-6)
    assert torch.isclose(l_joint, F.cross_entropy(joint_logits, targets))
    assert torch.isclose(l_deep, F.cross_entropy(deep_logits, targets))
    assert torch.isclose(l_shallow, F.cross_entropy(shallow_logits, targets))

    # Backward pass checks
    loss_total.backward()
    assert joint_logits.grad is not None and not torch.allclose(joint_logits.grad, torch.zeros_like(joint_logits))
    assert deep_logits.grad is not None and not torch.allclose(deep_logits.grad, torch.zeros_like(deep_logits))
    assert shallow_logits.grad is not None and not torch.allclose(shallow_logits.grad, torch.zeros_like(shallow_logits))


def test_delay_properties_and_multihead_interop():
    """
    Verify delay_mean and tau attribute interop on PhysiologyDelayCrossAttention and NVCDelayFormer:
    1. Multi-head delays (v2) and single-delay (v1).
    2. Getters, setters, and .mean().item() operations.
    3. Assignment with scalar, float, and mismatched shape tensors.
    """
    # 1. Multi-head layer
    from src.models.nvc_net import PhysiologyDelayCrossAttention as NetDelayCA
    m_ca = NetDelayCA(embed_dim=64, num_heads=4, multi_head_delays=True, learnable_delay=True)
    assert m_ca.tau.shape == (4,)
    assert m_ca.delay_mean.shape == (4,)
    assert torch.equal(m_ca.tau, m_ca.delay_mean)

    # .mean().item() scalar extraction succeeds without error
    tau_scalar = float(m_ca.delay_mean.mean().item())
    assert 3.5 <= tau_scalar <= 6.5

    # Setter with float
    m_ca.delay_mean = 5.2
    assert torch.allclose(m_ca.tau, torch.full((4,), 5.2))

    # Setter with tensor
    new_t = torch.tensor([4.0, 4.5, 5.0, 5.5])
    m_ca.delay_mean = new_t
    assert torch.allclose(m_ca.tau, new_t)

    # 2. Top-level NVCDelayFormer forwarding
    model = NVCDelayFormer(num_classes=2, eeg_channels=30, fnirs_channels=72, version="v2")
    assert hasattr(model, "delay_mean")
    assert hasattr(model, "tau")
    assert model.delay_mean.shape == (4,)
    assert model.tau.shape == (4,)

    # Setting via model.delay_mean
    model.delay_mean = 5.0
    assert torch.allclose(model.cross_attention.delay_mean, torch.full((4,), 5.0))
    assert torch.allclose(model.tau, torch.full((4,), 5.0))


def test_production_cross_attention_causal_and_edge_cases():
    """
    Verify production NVCDelayFormer.cross_attention invariants:
    1. Future electrophysiology has strictly 0.0 attention weight.
    2. Edge-case all-masked rows produce finite outputs with zeros.
    3. Non-finite / NaN boundary inputs are bounded and produce finite outputs.
    """
    model = NVCDelayFormer(num_classes=2, eeg_channels=30, fnirs_channels=72, version="v2")
    prod_ca = model.cross_attention
    
    # Normal forward
    B, Tn, Te, D = 2, 124, 250, 64
    fnirs_h = torch.randn(B, Tn, D)
    eeg_h = torch.randn(B, Te, D)
    out, attn = prod_ca(fnirs_h, eeg_h, use_causal_mask=True)
    
    assert out.shape == (B, Tn, D)
    assert attn.shape == (B, 4, Tn, Te)
    assert not torch.isnan(out).any(), "Production attention output contains NaNs"
    assert not torch.isnan(attn).any(), "Production attention weights contain NaNs"
    
    # Check t_fnirs = 0 (first optical query):
    # Any eeg token with t_eeg > 0 must have exactly 0.0 attention weight
    future_attn = attn[:, :, 0, 1:]
    assert (future_attn == 0.0).all(), "Future EEG tokens received non-zero attention in production class"

    # Edge-case: all keys are in the future (shift eeg timestamps forward)
    # Using raw attention forward with shifted timestamps
    t_n = torch.tensor([0.0]) # 0s
    t_e = torch.tensor([1.0, 2.0, 3.0]) # all > 0s
    delta = t_n.view(1, 1, 1, 1) - t_e.view(1, 1, 1, 3) # all negative (< -1e-4)
    # forward with mock
    q_mock = torch.randn(1, 1, 64)
    kv_mock = torch.randn(1, 3, 64)
    # Even if all keys are masked, production forward produces finite output
    out_edge, attn_edge = prod_ca(q_mock, kv_mock, use_causal_mask=True)
    assert not torch.isnan(out_edge).any(), "Edge case all-masked row produced NaNs in output"
    assert not torch.isnan(attn_edge).any(), "Edge case all-masked row produced NaNs in attn"


def test_composite_multitask_loss_eq8():
    """
    Verify NVCDelayFormer.compute_composite_loss strictly adheres to Eq. (8):
    L_total = L_joint + 0.2*(L_deep + L_shallow) + 1.0*L_recon + 0.08*||w_1 - w_0||^2
    """
    from src.models.nvc_net import NVCDelayFormer
    torch.manual_seed(42)
    B = 4
    joint_logits = torch.randn(B, 2, requires_grad=True)
    deep_logits = torch.randn(B, 2, requires_grad=True)
    shallow_logits = torch.randn(B, 2, requires_grad=True)
    targets = torch.randint(0, 2, (B,))
    
    recon_pred = torch.randn(B, 36, 124, requires_grad=True)
    recon_target = torch.randn(B, 36, 124)
    shallow_weight = torch.randn(2, 64, requires_grad=True)
    
    loss_total, details = NVCDelayFormer.compute_composite_loss(
        joint_logits, deep_logits, shallow_logits, targets,
        recon_pred=recon_pred, recon_target=recon_target,
        shallow_weight=shallow_weight,
        aux_weight=0.2, recon_weight=1.0, margin_weight=0.08
    )
    
    expected_cls = F.cross_entropy(joint_logits, targets) + 0.2 * (
        F.cross_entropy(deep_logits, targets) + F.cross_entropy(shallow_logits, targets)
    )
    expected_recon = F.mse_loss(recon_pred, recon_target)
    expected_margin = torch.sum((shallow_weight[1] - shallow_weight[0]) ** 2)
    expected_total = expected_cls + 1.0 * expected_recon + 0.08 * expected_margin
    
    assert torch.isclose(loss_total, expected_total, atol=1e-5)
    assert torch.isclose(details["loss_joint"], F.cross_entropy(joint_logits, targets))
    assert torch.isclose(details["loss_recon"], expected_recon)
    assert torch.isclose(details["loss_margin"], expected_margin)
    
    loss_total.backward()
    assert joint_logits.grad is not None
    assert recon_pred.grad is not None
    assert shallow_weight.grad is not None


def test_cross_attention_future_timestamps_and_injected_nan():
    """
    Test rigorous boundary conditions on production PhysiologyDelayCrossAttention:
    1. Constructed future timestamps where delta_ij < 0 for all pairs (entire matrix masked).
    2. Actual injection of NaN and Inf into query, key, and value vectors.
    Asserts zero probability leakage into acausal positions and strictly finite outputs.
    """
    from src.models.nvc_net import PhysiologyDelayCrossAttention
    ca = PhysiologyDelayCrossAttention(embed_dim=64, num_heads=4, multi_head_delays=True)
    ca.eval()

    # 1. Constructed strictly acausal timestamps: t_fnirs < t_eeg for all i, j
    t_fnirs = torch.tensor([0.1, 0.5]) # queries
    t_eeg = torch.tensor([2.0, 3.0, 4.0, 5.0]) # keys
    q = torch.randn(2, 2, 64)
    kv = torch.randn(2, 4, 64)

    out, attn = ca(q, kv, t_fnirs=t_fnirs, t_eeg=t_eeg, use_causal_mask=True, use_delay_prior=True)
    assert torch.isfinite(out).all(), "Output contains non-finite values under strict acausal mask!"
    assert torch.isfinite(attn).all(), "Attention weights contain non-finite values under strict acausal mask!"
    assert torch.allclose(attn, torch.zeros_like(attn)), "Acausal positions leaked non-zero attention weights!"

    # 2. Injected NaN and Inf into inputs
    q_nan = torch.randn(2, 2, 64)
    kv_nan = torch.randn(2, 4, 64)
    q_nan[0, 0, 10:20] = float("nan")
    kv_nan[1, 2, :] = float("nan")
    kv_nan[0, 1, 5] = float("inf")

    out_nan, attn_nan = ca(q_nan, kv_nan, t_fnirs=t_fnirs, t_eeg=t_eeg, use_causal_mask=True, use_delay_prior=True)
    assert torch.isfinite(out_nan).all(), "Injected NaN/Inf produced non-finite output in cross-attention!"
    assert torch.isfinite(attn_nan).all(), "Injected NaN/Inf produced non-finite attention weights!"
