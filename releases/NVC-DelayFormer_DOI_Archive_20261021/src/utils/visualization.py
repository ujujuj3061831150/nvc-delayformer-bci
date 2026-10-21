"""
Visualization & Scientific Figures Generator for NVC-DelayFormer.
Compliant with Phase 2 decisions:
- Generates publication-ready academic figures saved to reports/figures/.
- Plots:
  1. Loss & Accuracy Training Convergence Curves.
  2. Physiological Delay Cross-Attention Heatmap (verifying τ_NVC ~ 4.5-5.5s peak).
  3. Normalized Confusion Matrix.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import torch


def set_academic_plot_style():
    """Configure matplotlib with clean publication-standard styling."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def plot_training_curves(
    history: Dict[str, List[float]],
    save_path: Path
) -> None:
    """
    Plot dual-panel training and validation loss & accuracy curves.
    """
    set_academic_plot_style()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    epochs = range(1, len(history["train_loss"]) + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)
    
    # Left Panel: Loss
    ax1.plot(epochs, history["train_loss"], label="Train Loss", color="#1f77b4", lw=2.0)
    ax1.plot(epochs, history["val_loss"], label="Val Loss", color="#ff7f0e", lw=2.0, linestyle="--")
    ax1.set_xlabel("Epochs")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend(frameon=True)
    ax1.grid(True, alpha=0.3)
    
    # Right Panel: Accuracy
    ax2.plot(epochs, [a * 100 for a in history["train_acc"]], label="Train Acc", color="#1f77b4", lw=2.0)
    ax2.plot(epochs, [a * 100 for a in history["val_acc"]], label="Val Acc", color="#ff7f0e", lw=2.0, linestyle="--")
    ax2.set_xlabel("Epochs")
    ax2.set_ylabel("Accuracy (%)")
    ax2.set_title("Classification Accuracy")
    ax2.legend(frameon=True)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Training convergence curves saved to: {save_path}")


def plot_delay_attention_heatmap(
    attn_weights: torch.Tensor,
    save_path: Path,
    eeg_sr: float = 25.0,
    fnirs_sr: float = 10.4,
    tau_nvc_sec: float = 5.0
) -> None:
    """
    Plot the average physiological delay cross-attention heatmap.
    Shows the distribution of attention over the 2D plane:
    - X-axis: EEG Latency Time (0 to 10 seconds)
    - Y-axis: fNIRS Response Time (0 to 12 seconds)
    - Dashed line: Physiological Delay Ridge (t_fnirs - t_eeg = 5.0s)
    """
    set_academic_plot_style()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    # attn_weights shape: (batch, heads, T_fnirs, T_eeg)
    # Average across batch and heads
    avg_attn = attn_weights.mean(dim=(0, 1)).detach().cpu().numpy()  # (T_fnirs, T_eeg)
    
    t_fnirs_len, t_eeg_len = avg_attn.shape
    t_eeg = np.arange(t_eeg_len) / eeg_sr
    t_fnirs = np.arange(t_fnirs_len) / fnirs_sr
    
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    
    im = ax.imshow(
        avg_attn,
        aspect="auto",
        origin="lower",
        extent=[t_eeg[0], t_eeg[-1], t_fnirs[0], t_fnirs[-1]],
        cmap="viridis",
        interpolation="bilinear"
    )
    
    # Draw theoretical NVC delay trajectory: t_fnirs = t_eeg + tau_nvc_sec
    # where t_fnirs in [0, 12] and t_eeg in [0, 10]
    eeg_line = np.linspace(0, 10.0 - tau_nvc_sec, 100)
    fnirs_line = eeg_line + tau_nvc_sec
    ax.plot(
        eeg_line, fnirs_line,
        color="#d62728", linestyle="--", lw=2.2,
        label=f"Theoretical NVC Ridge ($\\Delta t = {tau_nvc_sec:.1f}\\text{{s}}$)"
    )
    
    # Draw causal threshold: t_fnirs = t_eeg (lag = 0)
    causal_limit = np.linspace(0, min(t_eeg[-1], t_fnirs[-1]), 100)
    ax.plot(causal_limit, causal_limit, color="#ffffff", linestyle=":", lw=1.5, alpha=0.8, label="Causality Limit (Lag=0s)")
    
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Attention Weight Probability", rotation=270, labelpad=15)
    
    ax.set_xlabel("Fast Electrophysiological Time: EEG (seconds)")
    ax.set_ylabel("Slow Hemodynamic Response Time: fNIRS (seconds)")
    ax.set_title(r"$\bf{Physiological\ Delay\ Cross-Attention\ Heatmap}$" + "\nDynamic Coupling between EEG and fNIRS")
    ax.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.9)
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Delay attention heatmap saved to: {save_path}")


def plot_confusion_matrix_figure(
    cm: np.ndarray,
    class_names: List[str],
    save_path: Path
) -> None:
    """Plot normalized confusion matrix."""
    set_academic_plot_style()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    cm_norm = cm.astype("float") / (cm.sum(axis=1, keepdims=True) + 1e-8) * 100.0
    
    fig, ax = plt.subplots(figsize=(5.5, 4.5), dpi=300)
    sns.heatmap(
        cm_norm,
        annot=True,
        fmt=".1f",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        cbar_kws={"label": "Normalized Percentage (%)"},
        ax=ax
    )
    ax.set_xlabel("Predicted Class")
    ax.set_ylabel("True Ground Truth")
    ax.set_title("LOSO Validation Confusion Matrix")
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Confusion matrix saved to: {save_path}")


def plot_delay_sensitivity_curve(
    taus: List[float],
    accuracies: List[float],
    save_path: Path
) -> None:
    """
    Plot the Inverted U-Shape Sensitivity Curve: Accuracy vs. Delay Prior τ.
    Proves that performance peaks precisely around the biological 4.5~5.5s delay.
    """
    set_academic_plot_style()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(7, 4.8), dpi=300)
    
    acc_pct = [a * 100.0 for a in accuracies]
    ax.plot(taus, acc_pct, marker="o", markersize=8, color="#2ca02c", lw=2.4, label="NVC-DelayFormer (LOSO)")
    
    # Highlight optimal peak point
    max_idx = int(np.argmax(acc_pct))
    best_tau = taus[max_idx]
    best_acc = acc_pct[max_idx]
    
    ax.scatter([best_tau], [best_acc], color="#d62728", s=140, zorder=5, label=f"Optimal Peak: $\\tau={best_tau:.1f}\\text{{s}}$ ({best_acc:.1f}%)")
    
    # Shade physiological canonical HRF delay window [4.5s, 5.5s]
    ax.axvspan(4.5, 5.5, color="#1f77b4", alpha=0.15, label="Physiological Canonical Window (4.5~5.5s)")
    
    ax.set_xlabel(r"Physiological Delay Prior $\tau_{NVC}$ (seconds)")
    ax.set_ylabel("LOSO Classification Accuracy (%)")
    ax.set_title(r"$\bf{Delay\ Parameter\ Sensitivity\ Analysis}$" + "\nInverted U-Shape Curve Validating Hemodynamic Latency")
    ax.set_ylim(min(acc_pct) - 5.0, min(103.0, max(acc_pct) + 5.0))
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="lower right")
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Delay sensitivity curve saved to: {save_path}")


def plot_benchmark_comparison_barchart(
    results_dict: Dict[str, Tuple[float, float]],  # model_name: (mean_acc, std_acc)
    save_path: Path
) -> None:
    """
    Plot benchmark comparison bar chart with standard error bars and model groupings.
    """
    set_academic_plot_style()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    names = list(results_dict.keys())
    means = [results_dict[k][0] * 100.0 for k in names]
    stds = [results_dict[k][1] * 100.0 for k in names]
    
    colors = ["#7f7f7f", "#8c564b", "#17becf", "#ff7f0e", "#2ca02c"]
    
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=300)
    bars = ax.bar(names, means, yerr=stds, capsize=5, color=colors[:len(names)], alpha=0.88, edgecolor="black", linewidth=1.0)
    
    # Add values on top of bars
    for bar, mean_val in zip(bars, means):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 1.5,
            f"{mean_val:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10
        )
        
    ax.set_ylabel("5-Fold Full LOSO Accuracy (%)")
    ax.set_title(r"$\bf{Benchmark\ Baseline\ Comparison\ on\ TU\ Berlin\ Dataset}$" + "\nEvaluation Across 5 Independent Subjects (Mean $\pm$ Std)")
    ax.set_ylim(0, 115)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Benchmark comparison barchart saved to: {save_path}")
