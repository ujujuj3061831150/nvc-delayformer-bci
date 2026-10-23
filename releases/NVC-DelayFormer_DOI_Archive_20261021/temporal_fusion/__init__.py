"""
temporal_fusion: Standalone Python Package for Neurovascular Temporal Fusion.

A plug-and-play PyTorch library implementing physiologically constrained temporal
fusion for multimodal electrophysiological and hemodynamic biosignals (EEG + fNIRS).

Modules:
- PhysiologyDelayCrossAttention: Continuous cross-attention with biological Gaussian delay prior.
- compute_nvc_temporal_envelopes: 2D neurovascular kernel marginalization into 1D temporal envelopes.
- apply_temporal_weighting: Applies receptive temporal envelopes to extract energy/concentration features.
- BuxtonVasodilatoryInflow: Biophysical balloon model vasodilatory inflow operator.
- HemodynamicReconstructor: Convolutional reconstruction head for hemodynamic proxies.
- DualPathJointReadout: Combines deep cross-attention tokens with shallow direct features and proxy gating.
- NVCDelayFormer: Canonical end-to-end multimodal classification architecture.
"""

__version__ = "1.0.0"
__author__ = "Hongjie Chen, Fang Duan"

from .delay_attention import PhysiologyDelayCrossAttention
from .temporal_weights import (
    compute_nvc_temporal_envelopes,
    apply_temporal_weighting,
)
from .buxton_dynamics import (
    BuxtonVasodilatoryInflow,
    HemodynamicReconstructor,
)
from .joint_readout import DualPathJointReadout
from .model import (
    NVCDelayFormer,
    EEGEncoder,
    FNIRSEncoder,
)

__all__ = [
    "PhysiologyDelayCrossAttention",
    "compute_nvc_temporal_envelopes",
    "apply_temporal_weighting",
    "BuxtonVasodilatoryInflow",
    "HemodynamicReconstructor",
    "DualPathJointReadout",
    "NVCDelayFormer",
    "EEGEncoder",
    "FNIRSEncoder",
]
