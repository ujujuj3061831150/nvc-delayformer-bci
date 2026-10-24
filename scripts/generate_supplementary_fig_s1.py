"""
Generate Supplementary Figure S1:
Candidate Delay Sensitivity and Prior Ablation Contrast between Mental Arithmetic (MA)
and Motor Imagery (MI) across 29 LOSO Folds.
"""

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.interpolate import make_interp_spline

def set_ieee_style():
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 8.0,
        'axes.labelsize': 8.5,
        'axes.titlesize': 9.0,
        'xtick.labelsize': 7.5,
        'ytick.labelsize': 7.5,
        'legend.fontsize': 7.5,
        'figure.titlesize': 10.0,
        'lines.linewidth': 1.6,
        'lines.markersize': 5.0,
        'axes.linewidth': 0.8,
        'grid.linewidth': 0.5,
        'grid.alpha': 0.35,
        'grid.linestyle': ':',
        'pdf.fonttype': 42,
        'ps.fonttype': 42,
    })

def main():
    set_ieee_style()
    root = Path(__file__).resolve().parent.parent

    # 1. Load Data
    ma_summary_path = root / "reports/real_29sub_benchmark_and_ablation_summary.json"
    mi_investigation_path = root / "reports/mi_delay_and_priors_investigation_results.json"
    ma_factorial_path = root / "reports/factorial_and_attention_results.json"

    with open(ma_summary_path, "r", encoding="utf-8") as f:
        ma_summary = json.load(f)
    with open(mi_investigation_path, "r", encoding="utf-8") as f:
        mi_investigation = json.load(f)
    with open(ma_factorial_path, "r", encoding="utf-8") as f:
        ma_factorial = json.load(f)["factorial_ablation"]

    # MA Delay Sweep: tau in [0.0, 2.0, 4.0, 5.0, 6.0, 8.0]
    ma_sweep = ma_summary["delay_sweep"]
    ma_taus = np.array([float(k) for k in sorted(ma_sweep.keys(), key=float)])
    ma_means = np.array([ma_sweep[f"{t:.1f}" if f"{t:.1f}" in ma_sweep else str(t)]["mean_acc"] for t in ma_taus])
    ma_stds = np.array([ma_sweep[f"{t:.1f}" if f"{t:.1f}" in ma_sweep else str(t)]["std_acc"] for t in ma_taus])
    ma_ses = ma_stds / np.sqrt(29)

    # MI Delay Sweep: tau in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    mi_sweep = mi_investigation["experiment1_delay_sweep"]
    mi_taus = np.array([float(k) for k in sorted(mi_sweep.keys(), key=float)])
    mi_means = np.array([mi_sweep[f"{t:.1f}"]["mean"] for t in mi_taus])
    mi_stds = np.array([mi_sweep[f"{t:.1f}"]["std"] for t in mi_taus])
    mi_ses = mi_stds / np.sqrt(29)

    # Palettes
    COLOR_MA = "#1B3B6F"      # Hero Navy
    COLOR_MI = "#D95F02"      # Vibrant Coral/Orange
    COLOR_WINDOW = "#EAEFF7"  # Soft blue window
    COLOR_GRAY = "#666666"

    # Create figure with 2 panels
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.16, 2.95), dpi=600)
    plt.subplots_adjust(wspace=0.28, left=0.08, right=0.97, top=0.86, bottom=0.17)

    # ==========================================
    # Panel (a): Candidate Delay Sensitivity Sweep
    # ==========================================
    ax_a.axvspan(3.5, 6.5, color=COLOR_WINDOW, alpha=0.9, zorder=1, label="Physiological Prior Window (3.5--6.5s)")

    # MA interpolation curve
    ma_dense_x = np.linspace(ma_taus.min(), ma_taus.max(), 200)
    ma_spl = make_interp_spline(ma_taus, ma_means, k=2)
    ma_dense_y = ma_spl(ma_dense_x)
    ax_a.plot(ma_dense_x, ma_dense_y, color=COLOR_MA, lw=1.6, zorder=2)
    ax_a.errorbar(ma_taus, ma_means, yerr=ma_ses, fmt="o", color=COLOR_MA,
                  ecolor=COLOR_MA, elinewidth=1.2, capsize=3.0, capthick=1.0,
                  markersize=4.8, zorder=4, label="Mental Arithmetic (MA, N=29)")

    # MI interpolation curve
    mi_dense_x = np.linspace(mi_taus.min(), mi_taus.max(), 200)
    mi_spl = make_interp_spline(mi_taus, mi_means, k=2)
    mi_dense_y = mi_spl(mi_dense_x)
    ax_a.plot(mi_dense_x, mi_dense_y, color=COLOR_MI, lw=1.6, linestyle="--", zorder=3)
    ax_a.errorbar(mi_taus, mi_means, yerr=mi_ses, fmt="s", color=COLOR_MI,
                  ecolor=COLOR_MI, elinewidth=1.2, capsize=3.0, capthick=1.0,
                  markersize=4.5, zorder=4, label="Motor Imagery (MI, N=29)")

    ax_a.set_xlabel(r"Inference Candidate Delay Latency $\tau$ (s)", fontweight="bold")
    ax_a.set_ylabel("Grand Mean LOSO Accuracy (%)", fontweight="bold")
    ax_a.set_xlim(-0.4, 8.4)
    ax_a.set_ylim(63.0, 84.5)
    ax_a.grid(True, linestyle=":", alpha=0.5)

    ax_a.set_title("(a) Candidate Delay Sensitivity Across Tasks", loc="left", pad=9,
                   fontsize=8.2, fontweight="bold")

    ax_a.annotate("MA: Delay Resonance\n(+5.12 pp, $p < 0.001$)",
                  xy=(8.0, ma_means[-1]), xytext=(4.3, 74.8),
                  arrowprops=dict(arrowstyle="->", lw=0.9, color=COLOR_MA),
                  fontsize=6.8, fontweight="bold", color=COLOR_MA)

    ax_a.annotate("MI: Delay-Invariant\n(flat: $\\Delta \\leq 0.69$ pp, $p=\\mathrm{n.s.}$)",
                  xy=(1.0, mi_means[1]), xytext=(0.2, 64.2),
                  arrowprops=dict(arrowstyle="->", lw=0.9, color=COLOR_MI),
                  fontsize=6.8, fontweight="bold", color=COLOR_MI)

    ax_a.legend(loc="upper left", frameon=True, framealpha=0.92, edgecolor="none", fontsize=6.6)

    # ==========================================
    # Panel (b): Factorial Retraining Ablation
    # ==========================================
    cond_labels = ["Full Model\n($P_{\\mathrm{on}}, M_{\\mathrm{on}}$)",
                   "Delay Only\n($P_{\\mathrm{on}}, M_{\\mathrm{off}}$)",
                   "Mask Only\n($P_{\\mathrm{off}}, M_{\\mathrm{on}}$)",
                   "Both Off\n($P_{\\mathrm{off}}, M_{\\mathrm{off}}$)"]

    ma_fact_means = [
        ma_factorial["P_on_M_on (Full Architecture)"]["mean"],
        ma_factorial["P_on_M_off (Delay Prior Only)"]["mean"],
        ma_factorial["P_off_M_on (Causal Mask Only)"]["mean"],
        ma_factorial["P_off_M_off (Uniform / Standard)"]["mean"],
    ]
    ma_fact_stds = [
        ma_factorial["P_on_M_on (Full Architecture)"]["std"],
        ma_factorial["P_on_M_off (Delay Prior Only)"]["std"],
        ma_factorial["P_off_M_on (Causal Mask Only)"]["std"],
        ma_factorial["P_off_M_off (Uniform / Standard)"]["std"],
    ]
    ma_fact_ses = np.array(ma_fact_stds) / np.sqrt(29)

    mi_factorial = mi_investigation["experiment2_factorial_priors"]
    mi_fact_means = [
        mi_factorial["Full Model (P_on, M_on)"]["mean_acc"],
        mi_factorial["Delay Only (P_on, M_off)"]["mean_acc"],
        mi_factorial["Mask Only (P_off, M_on)"]["mean_acc"],
        mi_factorial["Both Priors Off (P_off, M_off)"]["mean_acc"],
    ]
    mi_fact_stds = [
        mi_factorial["Full Model (P_on, M_on)"]["std_acc"],
        mi_factorial["Delay Only (P_on, M_off)"]["std_acc"],
        mi_factorial["Mask Only (P_off, M_on)"]["std_acc"],
        mi_factorial["Both Priors Off (P_off, M_off)"]["std_acc"],
    ]
    mi_fact_ses = np.array(mi_fact_stds) / np.sqrt(29)

    x = np.arange(len(cond_labels))
    width = 0.36

    rects_ma = ax_b.bar(x - width/2, ma_fact_means, width, yerr=ma_fact_ses,
                        label="Mental Arithmetic (MA)", color=COLOR_MA, alpha=0.92,
                        edgecolor="#0E2343", lw=0.8, capsize=3.0, zorder=3)
    rects_mi = ax_b.bar(x + width/2, mi_fact_means, width, yerr=mi_fact_ses,
                        label="Motor Imagery (MI)", color=COLOR_MI, alpha=0.92,
                        edgecolor="#8F3E01", lw=0.8, capsize=3.0, zorder=3)

    # Value text on top of bars
    for rect in rects_ma:
        h = rect.get_height()
        ax_b.text(rect.get_x() + rect.get_width()/2.0, h + 1.0, f"{h:.1f}%",
                  ha="center", va="bottom", fontsize=6.2, fontweight="bold", color=COLOR_MA)

    for rect in rects_mi:
        h = rect.get_height()
        ax_b.text(rect.get_x() + rect.get_width()/2.0, h + 1.0, f"{h:.1f}%",
                  ha="center", va="bottom", fontsize=6.2, fontweight="bold", color=COLOR_MI)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(cond_labels, fontsize=6.8)
    ax_b.set_ylabel("Retrained LOSO Accuracy (%)", fontweight="bold")
    ax_b.set_ylim(58.0, 88.0)
    ax_b.grid(True, axis="y", linestyle=":", alpha=0.5)

    ax_b.set_title("(b) Retrained Factorial Prior Decomposition", loc="left", pad=9,
                   fontsize=8.2, fontweight="bold")

    # Significance annotation bracket for MA (Full Model vs Both Off)
    y_sig_ma = 83.5
    ax_b.plot([0 - width/2, 3 - width/2], [y_sig_ma, y_sig_ma], lw=0.9, color=COLOR_MA)
    ax_b.plot([0 - width/2, 0 - width/2], [y_sig_ma - 0.7, y_sig_ma], lw=0.9, color=COLOR_MA)
    ax_b.plot([3 - width/2, 3 - width/2], [y_sig_ma - 0.7, y_sig_ma], lw=0.9, color=COLOR_MA)
    ax_b.text(1.5 - width/2, y_sig_ma + 0.4, "$\\Delta = -4.94$ pp (*** $p=6.05\\times 10^{-5}$)",
              ha="center", va="bottom", fontsize=6.3, fontweight="bold", color=COLOR_MA)

    # Significance annotation for MI
    y_sig_mi = 73.2
    ax_b.plot([0 + width/2, 3 + width/2], [y_sig_mi, y_sig_mi], lw=0.9, color=COLOR_MI, linestyle="--")
    ax_b.plot([0 + width/2, 0 + width/2], [y_sig_mi - 0.7, y_sig_mi], lw=0.9, color=COLOR_MI)
    ax_b.plot([3 + width/2, 3 + width/2], [y_sig_mi - 0.7, y_sig_mi], lw=0.9, color=COLOR_MI)
    ax_b.text(1.5 + width/2, y_sig_mi + 0.4, "$\\Delta = -0.92$ pp (n.s. $p=0.2128$)",
              ha="center", va="bottom", fontsize=6.3, fontweight="bold", color=COLOR_MI)

    ax_b.legend(loc="lower left", frameon=True, framealpha=0.92, edgecolor="none", fontsize=6.6)

    # Save to all target paths
    out_paths = [
        root / "manuscript/figures/supplementary_fig_s1_delay_curves.pdf",
        root / "manuscript/figures/supplementary_fig_s1_delay_curves.png",
        root / "reports/figures/supplementary_fig_s1_delay_curves.pdf",
        root / "reports/figures/supplementary_fig_s1_delay_curves.png",
    ]

    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=600, bbox_inches="tight")
        print(f"[OK] Saved figure to: {p}")

    plt.close(fig)

if __name__ == "__main__":
    main()
