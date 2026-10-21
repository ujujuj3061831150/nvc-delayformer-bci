"""
Biophysical Solver: Modified Beer-Lambert Law (MBLL).
Transforms optical density changes (ΔOD) at dual wavelengths into
molar concentration changes of Oxy-hemoglobin (Δ[HbO]) and Deoxy-hemoglobin (Δ[HbR]).

Reference:
- Matcher et al. (1995), Phys. Med. Biol.
- Kocsis et al. (2006), NeuroImage.
"""

from typing import Tuple, Optional
import numpy as np
import torch


# Specific extinction coefficients (in mm^-1 * (mol/L)^-1)
# Values for standard dual wavelengths used in NIRScout (760nm and 850nm)
EXTINCTION_COEFFICIENTS = {
    760: {"HbO": 1.4866, "HbR": 3.8437},
    850: {"HbO": 2.5264, "HbR": 1.7989},
}

# Wavelength-dependent Differential Pathlength Factors (DPF)
# Source: Scholkmann & Wolf (2013), J. Biomed. Opt. (Adult human head dispersion model)
DEFAULT_DPF_TABLE = {
    760: 6.51,  # Higher scattering at shorter wavelength
    850: 5.86,  # Lower scattering at longer wavelength
}


def compute_mbll_inversion_matrix(
    wavelength_1: int = 760,
    wavelength_2: int = 850,
    dpf_1: Optional[float] = None,
    dpf_2: Optional[float] = None,
    optode_distance_mm: float = 30.0,
) -> np.ndarray:
    """
    Compute the inverse extinction matrix for MBLL with wavelength-dependent DPF.
    
    ΔOD(λ) = [ε_HbO(λ) * Δ[HbO] + ε_HbR(λ) * Δ[HbR]] * (d * DPF(λ))
    
    Returns:
        np.ndarray: 2x2 inversion matrix converting [ΔOD_λ1, ΔOD_λ2]^T to [Δ[HbO], Δ[HbR]]^T
    """
    d_1 = DEFAULT_DPF_TABLE.get(wavelength_1, 6.0) if dpf_1 is None else dpf_1
    d_2 = DEFAULT_DPF_TABLE.get(wavelength_2, 6.0) if dpf_2 is None else dpf_2
    
    eps_1_o = EXTINCTION_COEFFICIENTS[wavelength_1]["HbO"]
    eps_1_r = EXTINCTION_COEFFICIENTS[wavelength_1]["HbR"]
    eps_2_o = EXTINCTION_COEFFICIENTS[wavelength_2]["HbO"]
    eps_2_r = EXTINCTION_COEFFICIENTS[wavelength_2]["HbR"]
    
    # Forward matrix incorporating wavelength-specific effective path length
    forward_system = np.array([
        [eps_1_o * optode_distance_mm * d_1, eps_1_r * optode_distance_mm * d_1],
        [eps_2_o * optode_distance_mm * d_2, eps_2_r * optode_distance_mm * d_2]
    ], dtype=np.float64)
    
    # Invert to map ΔOD -> ΔConcentration
    inversion_matrix = np.linalg.inv(forward_system)
    return inversion_matrix


def od_to_hemoglobin_tensor(
    delta_od: torch.Tensor,
    inversion_matrix: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    PyTorch tensor implementation of MBLL for differentiability and GPU acceleration.
    
    Args:
        delta_od: Tensor of shape (batch, channels, 2, time_steps)
                  where index 0 is λ1 (760nm) and index 1 is λ2 (850nm).
        inversion_matrix: 2x2 Tensor.
        
    Returns:
        hbo: Tensor of shape (batch, channels, time_steps) in mol/L
        hbr: Tensor of shape (batch, channels, time_steps) in mol/L
    """
    assert delta_od.shape[2] == 2, "Expected 2 wavelengths in dimension 2."
    # delta_od: (B, C, 2, T) -> permute to (B, C, T, 2)
    od_permuted = delta_od.permute(0, 1, 3, 2)
    # Matrix multiplication with (2, 2) inversion matrix
    conc = torch.matmul(od_permuted, inversion_matrix.T) # (B, C, T, 2)
    
    hbo = conc[..., 0] # (B, C, T)
    hbr = conc[..., 1] # (B, C, T)
    return hbo, hbr
