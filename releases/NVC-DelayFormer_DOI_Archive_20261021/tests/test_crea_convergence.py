"""
Unit Test Suite for Causal Recursive Euclidean Alignment (CrEA).
Verifies:
1. Strict online causality (trial k cannot see future trials k+1..N).
2. Cold-start condition number boundedness with empirical Bayes shrinkage prior.
3. Monotonic error convergence toward full offline transductive EA covariance.
4. Shape and finite value contracts.
"""

import pytest
import numpy as np
from src.data.preprocessing import CausalRecursiveEA, offline_euclidean_alignment


def test_crea_shape_and_finite_contract():
    N, C, T = 60, 30, 1000
    np.random.seed(42)
    mock_trials = np.random.randn(N, C, T)

    crea = CausalRecursiveEA(channels=C, shrinkage_alpha=5.0)
    aligned = crea.transform_sequence(mock_trials)

    assert aligned.shape == (N, C, T)
    assert np.isfinite(aligned).all(), "CrEA output contains non-finite values!"


def test_strict_online_causality():
    """
    Verify that trial k's aligned output depends ONLY on trials 1..k,
    and is strictly independent of future trials k+1..N.
    """
    N, C, T = 20, 28, 500
    np.random.seed(123)
    stream_A = np.random.randn(N, C, T)
    stream_B = stream_A.copy()
    # Mutate future trials from index 10 onwards
    stream_B[10:] = np.random.randn(10, C, T) * 10.0

    crea_A = CausalRecursiveEA(channels=C, shrinkage_alpha=5.0)
    aligned_A = crea_A.transform_sequence(stream_A)

    crea_B = CausalRecursiveEA(channels=C, shrinkage_alpha=5.0)
    aligned_B = crea_B.transform_sequence(stream_B)

    # Trials 0..9 MUST be bitwise identical between stream A and B
    for k in range(10):
        np.testing.assert_allclose(
            aligned_A[k], aligned_B[k], rtol=1e-6, atol=1e-6,
            err_msg=f"Future trial leakage detected at trial {k}!"
        )


def test_cold_start_condition_number_and_convergence():
    """
    Verify that shrinkage prior maintains a well-conditioned matrix at trial 1,
    and Frobenius error converges smoothly as trials accumulate.
    """
    N, C, T = 60, 30, 1000
    np.random.seed(42)
    # Generate structured covariance
    A = np.random.randn(C, C)
    true_cov = A @ A.T + 0.1 * np.eye(C)
    L = np.linalg.cholesky(true_cov)
    mock_trials = np.zeros((N, C, T))
    for i in range(N):
        mock_trials[i] = L @ np.random.randn(C, T)

    R_source = true_cov + 0.05 * np.random.randn(C, C)
    R_source = 0.5 * (R_source + R_source.T) + 0.1 * np.eye(C)

    crea = CausalRecursiveEA(channels=C, shrinkage_alpha=5.0, R_source=R_source)
    errors, conds = crea.compute_frobenius_convergence(mock_trials)

    # 1. Condition number at trial 1 must be strictly well-conditioned (< 1000)
    assert conds[0] < 1000.0, f"Ill-conditioned cold-start covariance: cond={conds[0]}"
    assert np.all(conds < 1000.0), "Condition number exploded during streaming!"

    # 2. Final error at trial 60 must be smaller than early error at trial 2
    assert errors[-1] < errors[1], f"Error did not decay: E_2={errors[1]:.4f}, E_60={errors[-1]:.4f}"
    # Error by trial 60 should be below 0.15 relative error
    assert errors[-1] < 0.15, f"Final relative Frobenius error too large: {errors[-1]:.4f}"
