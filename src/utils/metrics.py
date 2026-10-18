"""
Evaluation Metrics for BCI Classification.
Includes:
- Classification Accuracy
- Cohen's Kappa Coefficient (standard for BCI competitions)
- Macro-averaged F1 Score
- Confusion Matrix
"""

from typing import Dict, Tuple
import numpy as np
import torch
from sklearn.metrics import accuracy_score, cohen_kappa_score, f1_score, confusion_matrix


def compute_bci_metrics(
    y_true: torch.Tensor,
    y_pred: torch.Tensor
) -> Dict[str, float]:
    """
    Compute comprehensive BCI classification metrics.
    
    Args:
        y_true: Ground truth labels (N,)
        y_pred: Predicted class indices (N,)
        
    Returns:
        Dict containing accuracy, kappa, macro_f1.
    """
    if isinstance(y_true, torch.Tensor):
        y_true_np = y_true.detach().cpu().numpy()
    else:
        y_true_np = np.asarray(y_true)
        
    if isinstance(y_pred, torch.Tensor):
        y_pred_np = y_pred.detach().cpu().numpy()
    else:
        y_pred_np = np.asarray(y_pred)
        
    acc = float(accuracy_score(y_true_np, y_pred_np))
    kappa = float(cohen_kappa_score(y_true_np, y_pred_np))
    f1 = float(f1_score(y_true_np, y_pred_np, average="macro", zero_division=0))
    
    return {
        "accuracy": acc,
        "cohen_kappa": kappa,
        "macro_f1": f1
    }


def compute_confusion_matrix(
    y_true: torch.Tensor,
    y_pred: torch.Tensor
) -> np.ndarray:
    """Compute confusion matrix array."""
    if isinstance(y_true, torch.Tensor):
        y_true_np = y_true.detach().cpu().numpy()
    else:
        y_true_np = np.asarray(y_true)
        
    if isinstance(y_pred, torch.Tensor):
        y_pred_np = y_pred.detach().cpu().numpy()
    else:
        y_pred_np = np.asarray(y_pred)
        
    return confusion_matrix(y_true_np, y_pred_np)
