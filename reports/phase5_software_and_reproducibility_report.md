# Phase 5 Final Report: Standalone Temporal Fusion Package & Reproducibility Suite

This report documents the software modularization, packaging, review alignments, and reproducibility suite developed in **Phase 5** to satisfy the software openness and plug-and-play reproducibility standards of *Computer Methods and Programs in Biomedicine* (CMPB).

---

## 1. Package Decoupling: `temporal_fusion`

The core neurovascular temporal fusion mechanism has been decoupled from data-processing and experiment scripts into a standalone, pip-installable Python package:

```text
temporal_fusion/
├── __init__.py            # Top-level API exports & version metadata (__version__ = "1.0.0")
├── delay_attention.py     # PhysiologyDelayCrossAttention (timestamp-constrained cross-attention)
├── temporal_weights.py    # compute_nvc_temporal_envelopes & apply_temporal_weighting
├── buxton_dynamics.py     # BuxtonVasodilatoryInflow & HemodynamicReconstructor
├── joint_readout.py       # DualPathJointReadout (biophysical direct + latent MLP + proxy gating)
└── model.py               # Canonical NVCDelayFormer end-to-end architecture
```

### Modular Responsibilities

1. **`temporal_fusion.delay_attention`**:
   - Implements `PhysiologyDelayCrossAttention`.
   - Projects slow hemodynamic fNIRS features ($Q$) to query fast electrophysiological EEG features ($K, V$).
   - Adds a biological Gaussian prior centered around $\tau_{\mathrm{NVC}} = 5.0$\,s with strict causality masking ($t_{\mathrm{eeg}} \le t_{\mathrm{fnirs}}$).

2. **`temporal_fusion.temporal_weights`**:
   - Implements `compute_nvc_temporal_envelopes`.
   - Marginalizes the continuous 2D neurovascular coupling kernel $K(t_{\mathrm{nirs}}, t_{\mathrm{eeg}})$ into discrete 1D receptive envelopes $w_{\mathrm{nirs}}(t)$ and $w_{\mathrm{eeg}}(t)$.
   - Guarantees strict mathematical normalization ($\sum w_{\mathrm{nirs}} = 1.0$, $\sum w_{\mathrm{eeg}} = 1.0$).

3. **`temporal_fusion.buxton_dynamics`**:
   - Implements `BuxtonVasodilatoryInflow` ($D_{\mathrm{Buxton}}[X](t) = dX/dt + 0.15 X(t)$) with adaptive optical concentration scaling.
   - Implements `HemodynamicReconstructor` to map cross-modal tokens to predicted oxy-hemoglobin (HbO) waveforms.

4. **`temporal_fusion.joint_readout`**:
   - Implements `DualPathJointReadout`.
   - Combines latent cross-attention features (weight 0.02) and temporally weighted direct features (weight 0.98).
   - Dynamically modulates channel weights via the optical proxy reconstruction variance gate ($g_{\mathrm{recon}}$).

5. **`temporal_fusion.model`**:
   - Assembles the complete `NVCDelayFormer` (92,293 trainable parameters with fixed physiological latency prior).
   - Supports arbitrary sequence durations and physical window lengths ($10.0$\,s, $7.5$\,s, $5.0$\,s, $3.0$\,s).

---

## 2. Review Alignments & Discrepancy Resolution

Following the Phase 5 acceptance review, three essential alignments were executed and verified:

### 1. Training Entrypoint Alignment (`--train-fold`)
- **Issue**: Previously, `python reproduce_benchmark.py --train-fold <N>` imported a non-existent function (`run_phase1_suite`) and lacked the full 29-fold LOSO training protocol.
- **Resolution**: Implemented `train_single_loso_fold` in `src/train.py` exporting the standardized 29-fold LOSO training pipeline:
  - Subject seed: $42 + \text{sub\_id}$.
  - Validation split: 5 cyclic subjects starting at $(s-1) \bmod 28$.
  - Optimization: 12 epochs AdamW ($lr = 3\times 10^{-3}$, weight decay 0.05), batch size 256, 2-epoch linear warmup + cosine annealing, gradient clipping norm 1.0.
  - Validation checkpoint selection with tie-breaker cross-entropy.
- **Verification**: Executed `python reproduce_benchmark.py --train-fold 5` on real data. Completed in 3.9 seconds, obtaining **exactly 75.00%** test accuracy (matching Phase 1 Fold 5 to the hundredth of a percent).

### 2. Direct-Only Gating Semantics & Exact Equivalence
- **Issue**: In `temporal_fusion/joint_readout.py`, line 82 erroneously skipped optical proxy gating when `cut_gate_latent=True`, whereas the Phase 1 benchmark definition severed latent inputs to the reconstructor while preserving the proxy gate on direct features.
- **Resolution**: Removed the erroneous condition in `joint_readout.py`. Added `test_equivalence_with_legacy_implementation()` to `tests/test_temporal_fusion.py`.
- **Verification**: Ran rigorous numerical equivalence test comparing `NVCDelayFormer` against `src/models/nvc_net.py`:
  - **Joint mode**: Maximum logit diff = $0.0000000000$, Attention diff = $0.0000000000$, Reconstruction diff = $0.0000000000$.
  - **Direct-Only mode**: Maximum logit diff = $0.0000000000$, Attention diff = $0.0000000000$, Reconstruction diff = $0.0000000000$.
  - **Latent-Only mode**: Maximum logit diff = $0.0000000000$, Attention diff = $0.0000000000$, Reconstruction diff = $0.0000000000$.

### 3. Publication Documentation & Metadata Synchronization
- **Issue**: `README.md` contained manual entry discrepancies (Seed 100 SD = 11.83 vs 12.53; Seed 2024 SD = 12.24 vs 11.54; Seed 42 F1 SD = 12.16 vs 11.76; missing shared-encoder baselines; missing LICENSE file).
- **Resolution**:
  - Created root [`LICENSE`](file:///e:/课题4/LICENSE) (MIT License).
  - Aligned paper title with `main_cbm.tex`: *"Physiology-guided temporal fusion for cross-subject EEG--fNIRS classification"*.
  - Aligned dataset citation and DOI: `10.1109/TNSRE.2016.2628057`.
  - Regenerated all tables directly from locked records (`phase3_baselines_and_seeds_results.json`, `real_29sub_benchmark_and_ablation_summary.json`, `phase4_window_sweep_results.json`).
  - Added data acquisition and preprocessing instructions (`download_real_tuberlin.py`, `batch_parse_real.py`).
  - Exported [`requirements-lock.txt`](file:///e:/课题4/requirements-lock.txt) containing the complete frozen pip environment (279 packages, Python 3.11.9, CUDA 12.8, PyTorch 2.11).

---

## 3. Packaging & Installation

The package includes modern build configuration compliant with PEP 517/518:
- [`pyproject.toml`](file:///e:/课题4/pyproject.toml): Modern metadata, build system specification, and dependencies.
- [`setup.py`](file:///e:/课题4/setup.py): Setuptools packaging specification for legacy compatibility.
- [`requirements.txt`](file:///e:/课题4/requirements.txt): Minimal dependencies.
- [`requirements-lock.txt`](file:///e:/课题4/requirements-lock.txt): Exact frozen environment snapshot.

```bash
# Standard installation
pip install -r requirements.txt
pip install -e .

# Or exact audited environment snapshot
pip install -r requirements-lock.txt
```

---

## 4. One-Click Reproducibility Suite (`reproduce_benchmark.py`)

A top-level CLI script provides a unified interface to audit, verify, and reproduce the paper's findings:

```bash
# Verify environment, parameter counts, dataset files, and causal invariants
python reproduce_benchmark.py --verify

# Display all locked benchmark comparison tables (Table 1, Table 2, Table 4)
python reproduce_benchmark.py --benchmark

# Run an instantaneous synthetic data forward pass demo
python reproduce_benchmark.py --demo

# Train a single LOSO subject fold on demand (e.g. Subject 5)
python reproduce_benchmark.py --train-fold 5
```

---

## 5. Automated Testing Suite

The repository contains 15 automated unit tests executed via `pytest`:
- [`tests/test_temporal_fusion.py`](file:///e:/课题4/tests/test_temporal_fusion.py): 7 tests covering standalone exports, envelope normalization invariants, causal attention masking, Buxton inflow operator, dual-readout combinations, autograd gradient flow, and exact numerical equivalence with legacy reference models.
- [`tests/test_compliance.py`](file:///e:/课题4/tests/test_compliance.py): 8 tests covering seed determinism, MBLL optical inversion, numerical finite limits, and temporal invariants.

**Pytest Execution**: 15 passed in 4.81s (100% pass rate).

---

## 6. Manuscript Alignment

- [`latex_cbm/main_cbm.tex`](file:///e:/课题4/latex_cbm/main_cbm.tex): Data and Code Availability section explicitly declares the standalone `temporal_fusion` package, MIT open-source license, and reproducibility scripts.
- [`latex_cbm/main_cbm.pdf`](file:///e:/课题4/latex_cbm/main_cbm.pdf): Strictly **8 pages**, 0 overfull hboxes, 0 undefined citations.
- SHA-256 Hash: `634A18492792E8BAD88ADCC13E2BA13B2FE733317315E895B9265A8E307005DC`.
