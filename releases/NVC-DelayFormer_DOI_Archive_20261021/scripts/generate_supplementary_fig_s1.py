"""
Generate Publication-Quality Supplementary Figure S1:
Candidate Delay Sensitivity and Factorial Prior Ablation Contrast between Mental Arithmetic (MA)
and Motor Imagery (MI) across 29 LOSO Folds.

Adheres strictly to Nature / IEEE publication guidelines:
- Minimum glyph floor >= 5.0 pt
- Clean direct presentation of statistical effects (+4.94 pp, p = 6.05e-5)
- Standard chance level reference line (50.0%)
"""

import sys
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],
    'font.size': 8.0,
    'axes.labelsize': 8.5,
    'axes.titlesize': 9.0,
    'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5,
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
})

def main():
    ma_summary = json.loads((ROOT / "reports/real_29sub_benchmark_and_ablation_summary.json").read_text(encoding="utf-8"))
    mi_investigation = json.loads((ROOT / "reports/mi_delay_and_priors_investigation_results.json").read_text(encoding="utf-8"))
    ma_factorial = json.loads((ROOT / "reports/factorial_and_attention_results.json").read_text(encoding="utf-8"))["factorial_ablation"]

    ma_sweep = ma_summary["delay_sweep"]
    ma_taus = np.array([float(k) for k in sorted(ma_sweep.keys(), key=float)])
    ma_means = np.array([ma_sweep[f"{t:.1f}" if f"{t:.1f}" in ma_sweep else str(t)]["mean_acc"] for t in ma_taus])
    ma_ses = np.array([ma_sweep[f"{t:.1f}" if f"{t:.1f}" in ma_sweep else str(t)]["std_acc"] for t in ma_taus]) / np.sqrt(29)

    mi_sweep = mi_investigation["experiment1_delay_sweep"]
    mi_taus = np.array([float(k) for k in sorted(mi_sweep.keys(), key=float)])
    mi_means = np.array([mi_sweep[f"{t:.1f}"]["mean"] for t in mi_taus])
    mi_ses = np.array([mi_sweep[f"{t:.1f}"]["std"] for t in mi_taus]) / np.sqrt(29)

    COLOR_MA = "#0F4D92"
    COLOR_MI = "#D95F02"

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.16, 2.95), dpi=300)
    plt.subplots_adjust(wspace=0.28, left=0.08, right=0.98, top=0.84, bottom=0.17)

    # (a) Delay Sensitivity
    ax_a.axvspan(3.5, 6.5, color='#F0F4F8', zorder=1, label=r'HRF Prior [3.5, 6.5]\,s')

    ma_dense_x = np.linspace(ma_taus.min(), ma_taus.max(), 200)
    ma_spl = make_interp_spline(ma_taus, ma_means, k=2)
    ax_a.plot(ma_dense_x, ma_spl(ma_dense_x), color=COLOR_MA, lw=1.8, zorder=3)
    ax_a.errorbar(ma_taus, ma_means, yerr=ma_ses, fmt='o', color=COLOR_MA,
                  ecolor=COLOR_MA, elinewidth=1.1, capsize=2.5, capthick=0.9,
                  markersize=4.8, zorder=4, label='Mental Arithmetic (MA)')

    mi_dense_x = np.linspace(mi_taus.min(), mi_taus.max(), 200)
    mi_spl = make_interp_spline(mi_taus, mi_means, k=2)
    ax_a.plot(mi_dense_x, mi_spl(mi_dense_x), color=COLOR_MI, lw=1.8, linestyle='--', zorder=3)
    ax_a.errorbar(mi_taus, mi_means, yerr=mi_ses, fmt='s', color=COLOR_MI,
                  ecolor=COLOR_MI, elinewidth=1.1, capsize=2.5, capthick=0.9,
                  markersize=4.5, zorder=4, label='Motor Imagery (MI)')

    ax_a.text(8.2, ma_means[-1] + 0.3, "MA (+5.12 pp)\n($p < 0.001$)", va="center", ha="left",
              fontsize=7.2, fontweight="bold", color=COLOR_MA)
    ax_a.text(8.2, mi_means[-1] - 0.3, "MI (flat response)\n($p = 0.58$, n.s.)", va="center", ha="left",
              fontsize=7.2, fontweight="bold", color=COLOR_MI)

    ax_a.set_xlabel(r"Inference Candidate Delay $\tau$ (s)", fontweight="bold")
    ax_a.set_ylabel("Grand Mean LOSO Accuracy (%)", fontweight="bold")
    ax_a.set_xlim(-0.4, 10.4)
    ax_a.set_ylim(63.0, 85.0)
    ax_a.legend(loc="lower left", fontsize=7.0, frameon=False)
    ax_a.set_title(r"$\bf{(a)}$ Delay Sensitivity Across Paradigms", loc="left", pad=6,
                   fontsize=8.5, color='#1A2D42')

    # (b) Factorial Ablation
    cond_labels = ["Full Model", "Delay Only", "Mask Only", "Both Off"]

    ma_fact_means = [ma_factorial["P_on_M_on (Full Architecture)"]["mean"],
                     ma_factorial["P_on_M_off (Delay Prior Only)"]["mean"],
                     ma_factorial["P_off_M_on (Causal Mask Only)"]["mean"],
                     ma_factorial["P_off_M_off (Uniform / Standard)"]["mean"]]
    ma_fact_ses = np.array([ma_factorial["P_on_M_on (Full Architecture)"]["std"],
                            ma_factorial["P_on_M_off (Delay Prior Only)"]["std"],
                            ma_factorial["P_off_M_on (Causal Mask Only)"]["std"],
                            ma_factorial["P_off_M_off (Uniform / Standard)"]["std"]]) / np.sqrt(29)

    mi_factorial = mi_investigation["experiment2_factorial_priors"]
    mi_fact_means = [mi_factorial["Full Model (P_on, M_on)"]["mean_acc"],
                     mi_factorial["Delay Only (P_on, M_off)"]["mean_acc"],
                     mi_factorial["Mask Only (P_off, M_on)"]["mean_acc"],
                     mi_factorial["Both Priors Off (P_off, M_off)"]["mean_acc"]]
    mi_fact_ses = np.array([mi_factorial["Full Model (P_on, M_on)"]["std_acc"],
                            mi_factorial["Delay Only (P_on, M_off)"]["std_acc"],
                            mi_factorial["Mask Only (P_off, M_on)"]["std_acc"],
                            mi_factorial["Both Priors Off (P_off, M_off)"]["std_acc"]]) / np.sqrt(29)

    x = np.arange(len(cond_labels))
    width = 0.32
    b_base = 50.0

    rects_ma = ax_b.bar(x - width/2 - 0.02, [m - b_base for m in ma_fact_means], width, bottom=b_base,
                        yerr=ma_fact_ses, color=COLOR_MA, alpha=0.92,
                        edgecolor="#0A2544", linewidth=0.7, capsize=2.5, label="Mental Arithmetic")

    rects_mi = ax_b.bar(x + width/2 + 0.02, [m - b_base for m in mi_fact_means], width, bottom=b_base,
                        yerr=mi_fact_ses, color=COLOR_MI, alpha=0.90,
                        edgecolor="#8A3B00", linewidth=0.7, capsize=2.5, label="Motor Imagery")

    ax_b.axhline(50.0, color="#888888", linestyle="--", linewidth=0.8, zorder=1)
    ax_b.text(3.5, 50.4, "50% Chance Level", ha="right", va="bottom", fontsize=6.5, color="#666666")

    for rect, val in zip(rects_ma, ma_fact_means):
        ax_b.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + b_base + 1.0,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=6.8, fontweight="bold", color=COLOR_MA)

    for rect, val in zip(rects_mi, mi_fact_means):
        ax_b.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + b_base + 1.0,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=6.8, fontweight="bold", color=COLOR_MI)

    # Statistical bracket: Full vs Both Off
    bracket_y = 83.2
    ax_b.plot([x[0] - width/2, x[0] - width/2, x[3] - width/2, x[3] - width/2],
              [bracket_y - 0.8, bracket_y, bracket_y, bracket_y - 0.8], color=COLOR_MA, lw=0.9)
    ax_b.text((x[0] + x[3]) / 2 - width/2, bracket_y + 0.5, r"$+4.94$\,pp ($p = 6.05\times 10^{-5}$)",
              ha="center", va="bottom", fontsize=7.0, fontweight="bold", color=COLOR_MA)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(cond_labels, fontsize=7.2)
    ax_b.set_ylabel("Held-Out LOSO Accuracy (%)", fontweight="bold")
    ax_b.set_ylim(48.0, 88.0)
    ax_b.set_yticks([50, 60, 70, 80])
    ax_b.legend(loc="upper right", fontsize=7.0, frameon=False)
    ax_b.set_title(r"$\bf{(b)}$ Factorial Constraint Decomposition", loc="left", pad=6,
                   fontsize=8.5, color='#1A2D42')

    for folder in (OUT, REPORTS_FIG):
        fig.savefig(folder / 'supplementary_fig_s1_delay_curves.pdf', dpi=600, bbox_inches='tight', pad_inches=0.02)
        fig.savefig(folder / 'supplementary_fig_s1_delay_curves.png', dpi=600, bbox_inches='tight', pad_inches=0.02)

    plt.close(fig)
    print(f"[+] Clean Fig S1 successfully generated: {OUT / 'supplementary_fig_s1_delay_curves.pdf'}")

if __name__ == '__main__':
    main()
