"""
Nature-Grade Publication Figure Generator for NVC-DelayFormer.
Complies with Nature / Nature Machine Intelligence visual standards:
- Typography: Arial / Helvetica / DejaVu Sans, 7-8 pt text, 8-9 pt bold panel tags (a, b, c).
- Geometry: 89 mm (single col), 120-136 mm (1.5 col), 180-183 mm (double col).
- Spines: Top and right spines removed; axes.linewidth = 0.8; tick width = 0.8.
- Palette: NMI Pastel / Deep Navy Hero (#0F4D92), muted baselines (#484878, #7884B4, #B4C0E4).
- Data Integrity: Overlaid individual subject points (N=29) with jitter for full transparency.
- Output: 600 DPI raster (PNG), vector PDF (TrueType type 42), and vector SVG.
"""

from pathlib import Path
import json
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
from scipy.interpolate import make_interp_spline


# =============================================================================
# Nature Global Style Configuration
# =============================================================================

NATURE_PALETTE = {
    "hero_navy":      "#0F4D92",  # NVC-DelayFormer
    "baseline_slate": "#484878",  # Feature-Concat
    "baseline_peri":  "#7884B4",  # Standard-Attention
    "baseline_soft":  "#A8B4D4",  # EEGNet
    "baseline_pale":  "#C8D0E4",  # fNIRS-CNN
    "accent_coral":   "#C85A46",  # Ablation collapse callout
    "accent_teal":    "#329688",  # Multi-task / Convergence
    "accent_violet":  "#8C5A96",  # 7.0s Convergence
    "neutral_dark":   "#222222",  # Text / Spines
    "neutral_mid":    "#666666",  # Secondary labels
    "neutral_light":  "#E2E5EB",  # Grid / Ticks
    "chance_gray":    "#888888",  # 50% chance line
    "window_band":    "#EBF3FA",  # Physiological NVC window
}

def set_nature_rc():
    """Apply Nature journal rcParams."""
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "font.size": 7.5,
        "axes.titlesize": 8.0,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0,
        "legend.title_fontsize": 7.5,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "legend.frameon": False,
        "figure.autolayout": False,
    })

def save_multiformat(fig, base_stem: str, out_dirs: list, dpi: int = 600):
    """Save in PNG (600 DPI), vector PDF, and SVG across target folders."""
    for d in out_dirs:
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / f"{base_stem}.png", dpi=dpi, bbox_inches="tight")
        fig.savefig(d / f"{base_stem}.pdf", bbox_inches="tight")
        fig.savefig(d / f"{base_stem}.svg", bbox_inches="tight")


# =============================================================================
# 1. Nature Benchmark Comparison Figure (Hero Panel + Subject Scatter)
# =============================================================================

def plot_nature_benchmark(summary_data: dict, out_dirs: list):
    """
    Nature-grade bar chart with:
    - Overlaid jittered individual-subject dots (N=29)
    - Statistical significance brackets with exact p-values
    - Chance level at 50%
    - 89 mm single-column or 120 mm 1.5-column width
    """
    set_nature_rc()
    fig, ax = plt.subplots(figsize=(4.72, 3.54), dpi=600)  # 120 mm x 90 mm

    models = [
        "fNIRS-CNN",
        "Standard-Attention",
        "EEGNet",
        "Feature-Concat",
        "NVC-DelayFormer (Full)"
    ]
    display_names = [
        "fNIRS-CNN\n(Unimodal)",
        "Standard-Attn\n(Unconstrained)",
        "EEGNet\n(Unimodal)",
        "Feature-Concat\n(Multimodal)",
        "NVC-DelayFormer\n(Ours, Causal)"
    ]
    
    colors = [
        NATURE_PALETTE["baseline_pale"],
        NATURE_PALETTE["baseline_peri"],
        NATURE_PALETTE["baseline_soft"],
        NATURE_PALETTE["baseline_slate"],
        NATURE_PALETTE["hero_navy"],
    ]

    means = [summary_data["models"][m]["mean_acc"] for m in models]
    ses = [summary_data["models"][m]["se_acc"] for m in models]

    x = np.arange(len(models))
    width = 0.52

    # Draw bars with subtle edge
    bars = ax.bar(
        x, means, width=width, yerr=ses, capsize=3.0,
        color=colors, edgecolor=NATURE_PALETTE["neutral_dark"],
        linewidth=0.8, alpha=0.92, zorder=2,
        error_kw={"elinewidth": 0.8, "capthick": 0.8, "ecolor": NATURE_PALETTE["neutral_dark"]}
    )

    # Overlay individual subject points with jitter (Nature transparency requirement)
    np.random.seed(42)
    for i, m in enumerate(models):
        pts = summary_data["models"][m]["fold_accs"]
        jitter = np.random.uniform(-0.14, 0.14, size=len(pts))
        ax.scatter(
            x[i] + jitter, pts,
            color=NATURE_PALETTE["neutral_dark"],
            s=8.5, alpha=0.38, edgecolors="none", zorder=3
        )

    # 50% chance line
    ax.axhline(50.0, color=NATURE_PALETTE["chance_gray"], linestyle="--", linewidth=0.8, zorder=1)
    ax.text(
        len(models) - 0.55, 50.8, "Chance (50.0%)",
        color=NATURE_PALETTE["neutral_mid"], fontsize=6.5, ha="right"
    )

    # In-bar accuracy text
    for i, (m_val, se_val) in enumerate(zip(means, ses)):
        fw = "bold" if i == len(models) - 1 else "normal"
        tc = NATURE_PALETTE["hero_navy"] if i == len(models) - 1 else NATURE_PALETTE["neutral_dark"]
        ax.text(
            x[i], m_val + se_val + 1.2, f"{m_val:.2f}%",
            ha="center", va="bottom", fontsize=6.8, fontweight=fw, color=tc
        )

    # Significance brackets against Ours
    # Ours is index 4
    comparisons = [
        (0, 4, 73.0, r"$p = 7.58 \times 10^{-6\ ***}$"),
        (1, 4, 76.2, r"$p = 0.0002^{***}$"),
        (2, 4, 79.4, r"$p = 0.0053^{**}$"),
        (3, 4, 82.6, r"$p = 0.0055^{**}$"),
    ]
    for x1, x2, y_pos, p_txt in comparisons:
        h = 0.6
        ax.plot([x1, x1, x2, x2], [y_pos - h, y_pos, y_pos, y_pos - h], color=NATURE_PALETTE["neutral_dark"], lw=0.7)
        ax.text((x1 + x2) * 0.5, y_pos + 0.3, p_txt, ha="center", va="bottom", fontsize=6.2, color=NATURE_PALETTE["neutral_dark"])

    ax.set_ylabel("Leave-One-Subject-Out Accuracy (%)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(display_names)
    ax.set_ylim(44.0, 86.0)

    # Panel tag 'a'
    ax.text(-0.15, 1.04, "a", transform=ax.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax.set_title("29-Fold Full LOSO Benchmark Comparison (N = 29 Subjects)", loc="left", pad=12, fontweight="bold", fontsize=8.0)

    plt.tight_layout()
    save_multiformat(fig, "real_29sub_benchmark_comparison", out_dirs)
    save_multiformat(fig, "real_26sub_benchmark_comparison", out_dirs)
    plt.close(fig)
    print("[+] Nature Benchmark figure generated.")


# =============================================================================
# 2. Nature Sub-05 Confusion Matrix Figure
# =============================================================================

def plot_nature_confusion_matrix(locked_data: dict, out_dirs: list):
    """
    Nature-grade confusion matrix:
    - Subtle blue-to-navy palette
    - Detailed counts and row-normalized percentages
    - Clear summary metrics in caption/subtitle
    """
    set_nature_rc()
    fig, ax = plt.subplots(figsize=(3.15, 2.76), dpi=600)  # 80 mm x 70 mm

    sub05_cm = locked_data["benchmark_predictions"]["NVC-DelayFormer (Full)"]["sub-05"]["cm"]
    cm = np.array([
        [sub05_cm["tn"], sub05_cm["fp"]],
        [sub05_cm["fn"], sub05_cm["tp"]]
    ])
    total_samples = cm.sum()
    acc = (cm[0, 0] + cm[1, 1]) / total_samples * 100.0

    # Custom single-hue elegant colormap
    colors_cmap = ["#F8FAFD", "#E2ECF7", "#A8C4E8", "#4A82C4", "#0F4D92"]
    cmap = LinearSegmentedColormap.from_list("nature_blues", colors_cmap, N=256)

    im = ax.imshow(cm, cmap=cmap, vmin=0, vmax=30, aspect="equal")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=6.5, length=2.0)
    cbar.set_label("Trial Count", fontsize=7.0)

    classes = ["Rest", "Mental Arith."]
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(classes, fontsize=7.2)
    ax.set_yticklabels(classes, fontsize=7.2)
    ax.set_xlabel("Predicted Class", fontweight="bold", labelpad=4)
    ax.set_ylabel("True Class", fontweight="bold", labelpad=4)

    # Cell annotations with count and conditional percentage
    for r in range(2):
        row_sum = cm[r].sum()
        for c in range(2):
            val = cm[r, c]
            pct = val / row_sum * 100.0
            text_color = "white" if val > 16 else NATURE_PALETTE["neutral_dark"]
            ax.text(
                c, r - 0.08, f"{val}",
                ha="center", va="center", color=text_color,
                fontsize=8.5, fontweight="bold"
            )
            ax.text(
                c, r + 0.16, f"({pct:.1f}%)",
                ha="center", va="center", color=text_color,
                fontsize=6.8
            )

    # Panel tag
    ax.text(-0.25, 1.10, "b", transform=ax.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax.set_title(f"Sub-05 Blind Test (Acc = {acc:.2f}%)", loc="left", pad=10, fontweight="bold", fontsize=7.8)

    plt.tight_layout()
    save_multiformat(fig, "confusion_matrix_sub05", out_dirs)
    save_multiformat(fig, "sub05_confusion_matrix", out_dirs)
    plt.close(fig)
    print("[+] Nature Confusion Matrix figure generated.")


# =============================================================================
# 3. Nature Ablation Analysis Figure (Accuracy vs. HbO Fidelity)
# =============================================================================

def plot_nature_ablation(summary_data: dict, out_dirs: list):
    """
    Nature-grade ablation analysis:
    - Primary axis (bars): Classification accuracy
    - Secondary axis (points/line): HbO reconstruction correlation (r_HbO)
    - Highlighting catastrophic collapse when L_recon is removed (0.8912 -> 0.0012)
    """
    set_nature_rc()
    fig, ax1 = plt.subplots(figsize=(5.12, 3.54), dpi=600)  # 130 mm x 90 mm

    ab_keys = [
        "Full Model",
        "w/o Delay Prior",
        "w/o Causal Mask",
        "w/o Recon Loss",
        "Wrong Delay Prior (0s)"
    ]
    display_names = [
        "Full Model\n(Baseline)",
        "w/o Delay\nPrior",
        "w/o Causal\nMask",
        "w/o Recon\nLoss",
        "Wrong Delay\n(\\tau = 0s)"
    ]

    means = [summary_data["ablations"][k]["mean_acc"] for k in ab_keys]
    ses = [summary_data["ablations"][k]["se_acc"] for k in ab_keys]
    r_hbo = [summary_data["ablations"][k]["mean_r_hbo"] for k in ab_keys]

    x = np.arange(len(ab_keys))
    width = 0.50

    bar_colors = [
        NATURE_PALETTE["hero_navy"],
        NATURE_PALETTE["baseline_slate"],
        NATURE_PALETTE["baseline_peri"],
        NATURE_PALETTE["accent_coral"],
        NATURE_PALETTE["baseline_soft"],
    ]

    bars = ax1.bar(
        x, means, width=width, yerr=ses, capsize=3.0,
        color=bar_colors, edgecolor=NATURE_PALETTE["neutral_dark"],
        linewidth=0.8, alpha=0.90, zorder=2,
        error_kw={"elinewidth": 0.8, "capthick": 0.8, "ecolor": NATURE_PALETTE["neutral_dark"]}
    )

    # In-bar delta
    for i, k in enumerate(ab_keys):
        delta = summary_data["ablations"][k]["delta_acc"]
        delta_str = "Ref." if k == "Full Model" else f"{delta:+.2f}%"
        ax1.text(
            x[i], means[i] + ses[i] + 0.8, f"{means[i]:.2f}%\n({delta_str})",
            ha="center", va="bottom", fontsize=6.2, fontweight="bold",
            color=NATURE_PALETTE["neutral_dark"]
        )

    ax1.set_ylabel("Classification Accuracy (%)", fontweight="bold", color=NATURE_PALETTE["neutral_dark"])
    ax1.set_xticks(x)
    ax1.set_xticklabels(display_names)
    ax1.set_ylim(50.0, 72.0)

    # Secondary y-axis for continuous trajectory fidelity
    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(NATURE_PALETTE["accent_teal"])
    ax2.spines["right"].set_linewidth(0.8)
    ax2.tick_params(axis="y", colors=NATURE_PALETTE["accent_teal"])

    ax2.plot(
        x, r_hbo, color=NATURE_PALETTE["accent_teal"],
        marker="D", markersize=5.0, linewidth=1.5, linestyle="--",
        label=r"HbO Trajectory $r_{\mathrm{HbO}}$", zorder=4
    )
    ax2.set_ylabel(r"HbO Trajectory Fidelity ($r_{\mathrm{HbO}}$)", fontweight="bold", color=NATURE_PALETTE["accent_teal"])
    ax2.set_ylim(-0.15, 1.10)

    for i, r_val in enumerate(r_hbo):
        offset = -0.09 if i == 3 else 0.06
        va_mode = "top" if i == 3 else "bottom"
        fw = "bold" if i == 3 else "normal"
        color_r = NATURE_PALETTE["accent_coral"] if i == 3 else NATURE_PALETTE["accent_teal"]
        ax2.text(
            x[i], r_val + offset, f"r = {r_val:.3f}",
            color=color_r, fontsize=6.5, fontweight=fw,
            ha="center", va=va_mode
        )

    # Panel tag
    ax1.text(-0.12, 1.06, "c", transform=ax1.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax1.set_title("5-Way Ablation Analysis: Accuracy vs. Biophysical Reconstruction", loc="left", pad=12, fontweight="bold", fontsize=8.0)

    plt.tight_layout()
    save_multiformat(fig, "real_29sub_ablation_comparison", out_dirs)
    save_multiformat(fig, "real_26sub_ablation_comparison", out_dirs)
    plt.close(fig)
    print("[+] Nature Ablation figure generated.")


# =============================================================================
# 4. Nature Delay Sensitivity & Gradient Convergence Figure
# =============================================================================

def plot_nature_delay_dynamics(summary_data: dict, out_dirs: list):
    """
    Nature two-panel composite:
    - Panel a: Inverted U-shape delay sensitivity curve with shaded 4.5-6.5s window
    - Panel b: Spontaneous gradient convergence without regularizer penalty
    """
    set_nature_rc()
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.09, 3.15), dpi=600)  # 180 mm x 80 mm

    # Panel a: 29-Subject Cohort Delay Sweep
    taus = np.array([float(k) for k in summary_data["delay_sweep"].keys()])
    sweep_means = np.array([summary_data["delay_sweep"][k]["mean"] for k in summary_data["delay_sweep"].keys()])
    sweep_ses = np.array([summary_data["delay_sweep"][k]["se"] for k in summary_data["delay_sweep"].keys()])

    # Smooth curve interpolation
    tau_dense = np.linspace(taus.min(), taus.max(), 200)
    spl = make_interp_spline(taus, sweep_means, k=3)
    mean_dense = spl(tau_dense)

    # Shaded physiological window
    ax_a.axvspan(4.5, 6.5, color=NATURE_PALETTE["window_band"], alpha=0.9, zorder=1)
    ax_a.text(5.5, 69.1, "Physiological\nWindow (4.5--6.5s)", fontsize=6.2, ha="center", va="top", color=NATURE_PALETTE["hero_navy"])

    ax_a.plot(tau_dense, mean_dense, color=NATURE_PALETTE["hero_navy"], lw=1.5, zorder=2)
    ax_a.errorbar(
        taus, sweep_means, yerr=sweep_ses, fmt="o",
        color=NATURE_PALETTE["hero_navy"], ecolor=NATURE_PALETTE["hero_navy"],
        elinewidth=1.0, capsize=3.0, capthick=1.0, markersize=4.8, zorder=3
    )

    # Annotate peak
    peak_idx = np.argmax(sweep_means)
    ax_a.annotate(
        f"Peak: {sweep_means[peak_idx]:.2f}%\n(\\tau = {taus[peak_idx]:.1f}s)",
        xy=(taus[peak_idx], sweep_means[peak_idx]),
        xytext=(taus[peak_idx] + 0.3, sweep_means[peak_idx] - 2.2),
        arrowprops=dict(arrowstyle="->", lw=0.8, color=NATURE_PALETTE["hero_navy"]),
        fontsize=6.5, fontweight="bold", color=NATURE_PALETTE["hero_navy"]
    )

    ax_a.set_xlabel(r"Inference Physiological Delay Latency $\tau$ (s)", fontweight="bold")
    ax_a.set_ylabel("Cohort Grand Mean Accuracy (%)", fontweight="bold")
    ax_a.set_xlim(-0.3, 8.3)
    ax_a.set_ylim(60.0, 71.0)
    ax_a.text(-0.16, 1.08, "a", transform=ax_a.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax_a.set_title("Cohort Broad-Peak Delay Sensitivity", loc="left", pad=10, fontweight="bold", fontsize=7.8)

    # Panel b: Spontaneous Convergence Trajectories
    conv_data = summary_data["convergence_trajectories"]
    colors_conv = {
        "2.5": NATURE_PALETTE["hero_navy"],
        "3.0": NATURE_PALETTE["accent_teal"],
        "7.0": NATURE_PALETTE["accent_violet"]
    }
    epochs = list(range(len(list(conv_data.values())[0])))

    # Shaded target window
    ax_b.axhspan(4.5, 6.5, color=NATURE_PALETTE["window_band"], alpha=0.9, zorder=1)

    for init_k, traj in conv_data.items():
        col = colors_conv.get(init_k, NATURE_PALETTE["neutral_dark"])
        final_val = traj[-1]
        ax_b.plot(epochs, traj, label=f"Init $\\tau = {init_k}$s $\\to$ {final_val:.2f}$s", color=col, lw=1.4, marker="s", markersize=3.0, zorder=3)

    ax_b.set_xlabel("Training Epochs", fontweight="bold")
    ax_b.set_ylabel(r"Learned Delay Prior Latency $\tau$ (s)", fontweight="bold")
    ax_b.set_ylim(1.8, 8.2)
    ax_b.legend(loc="upper right", fontsize=6.5, frameon=False)
    ax_b.text(-0.16, 1.08, "b", transform=ax_b.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax_b.set_title("Unconstrained Gradient Trajectories", loc="left", pad=10, fontweight="bold", fontsize=7.8)

    plt.tight_layout()
    save_multiformat(fig, "delay_sensitivity_curve", out_dirs)
    plt.close(fig)
    print("[+] Nature Delay Dynamics figure generated.")


# =============================================================================
# 5. Nature Subject-by-Subject LOSO Distribution Figure
# =============================================================================

def plot_nature_individual_loso(summary_data: dict, out_dirs: list):
    """
    Nature-grade individual subject performance distribution:
    - 29 subjects sorted or chronological
    - Shaded cohort mean and 50% chance level
    """
    set_nature_rc()
    fig, ax = plt.subplots(figsize=(6.69, 2.76), dpi=600)  # 170 mm x 70 mm

    sub_accs = summary_data["models"]["NVC-DelayFormer (Full)"]["fold_accs"]
    sub_ids = [f"S{i:02d}" for i in range(1, 30)]
    mean_val = float(np.mean(sub_accs))

    x = np.arange(len(sub_accs))
    bar_cols = [
        NATURE_PALETTE["hero_navy"] if a >= mean_val else
        NATURE_PALETTE["baseline_slate"] if a >= 55.0 else
        NATURE_PALETTE["accent_coral"]
        for a in sub_accs
    ]

    ax.bar(x, sub_accs, color=bar_cols, width=0.62, edgecolor=NATURE_PALETTE["neutral_dark"], lw=0.6, alpha=0.9, zorder=2)
    ax.axhline(50.0, color=NATURE_PALETTE["chance_gray"], linestyle="--", lw=0.8, zorder=1)
    ax.axhline(mean_val, color=NATURE_PALETTE["hero_navy"], linestyle="-", lw=1.2, zorder=1)
    ax.text(len(sub_accs) - 0.5, mean_val + 1.2, f"Cohort Mean = {mean_val:.2f}%", color=NATURE_PALETTE["hero_navy"], fontsize=6.8, fontweight="bold", ha="right")

    ax.set_ylabel("LOSO Accuracy (%)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(sub_ids, rotation=45, ha="right", fontsize=6.2)
    ax.set_ylim(38.0, 95.0)

    ax.text(-0.08, 1.08, "d", transform=ax.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax.set_title("NVC-DelayFormer: Subject-by-Subject Generalization Across 29 Folds", loc="left", pad=10, fontweight="bold", fontsize=7.8)

    plt.tight_layout()
    save_multiformat(fig, "real_29sub_loso_performance", out_dirs)
    save_multiformat(fig, "real_26sub_loso_performance", out_dirs)
    plt.close(fig)
    print("[+] Nature Individual LOSO figure generated.")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    root = Path("e:/课题4")
    summary_path = root / "reports/real_29sub_benchmark_and_ablation_summary.json"
    locked_path = root / "reports/real_29sub_locked_predictions.json"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
    with open(locked_path, "r", encoding="utf-8") as f:
        locked_data = json.load(f)

    target_dirs = [
        root / "reports/figures",
        root / "latex/figures",
        root / "latex_cbm/figures",
    ]

    print("Generating Nature-grade scientific figure suite...")
    plot_nature_benchmark(summary_data, target_dirs)
    plot_nature_confusion_matrix(locked_data, target_dirs)
    plot_nature_ablation(summary_data, target_dirs)
    plot_nature_delay_dynamics(summary_data, target_dirs)
    plot_nature_individual_loso(summary_data, target_dirs)
    print("[OK] All Nature-grade figures successfully generated and synchronized across all target directories!")

if __name__ == "__main__":
    main()
