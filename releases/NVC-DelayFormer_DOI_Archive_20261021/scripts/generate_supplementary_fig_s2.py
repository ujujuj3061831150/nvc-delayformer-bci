"""
Generate Publication-Quality Supplementary Figure S2:
Causal Recursive Euclidean Alignment (CrEA) Online Adaptation Convergence Dynamics
across all 29 Participants (60 Trials).

Adheres strictly to Nature / IEEE publication guidelines:
- Minimum glyph floor >= 5.0 pt
- Clean direct presentation of rapid bedside convergence
- Standard single-column IEEE fit: width = 3.5 inches
"""

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
    'legend.fontsize': 7.0,
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
})

def main():
    diag_path = ROOT / "reports" / "real_diagnostics_data.json"
    with open(diag_path, "r", encoding="utf-8") as f:
        real_diag = json.load(f)

    k_trials = np.array(real_diag["crea_trials"])
    err_shrinkage = np.array(real_diag["crea_error_shrinkage"])
    err_naive = np.array(real_diag["crea_error_naive"])

    COLOR_SHRINKAGE = "#0F4D92"
    COLOR_NAIVE = "#D95F02"

    fig, ax = plt.subplots(figsize=(3.5, 2.5), dpi=300)
    plt.subplots_adjust(left=0.16, right=0.96, top=0.88, bottom=0.17)

    # Shaded adaptation window (Trials 1-8)
    ax.axvspan(1, 8, color='#F0F4F8', zorder=1, label=r'Bedside adaptation ($k \leq 8$)')
    ax.axvline(8.0, color='#2A9D8F', ls=':', lw=0.9, zorder=2)

    ax.plot(k_trials, err_shrinkage, color=COLOR_SHRINKAGE, lw=1.8, zorder=3,
            label=r'CrEA: $\widetilde{\mathbf{R}}_{\mathrm{src}}$ (Trace-Matched)')
    ax.plot(k_trials, err_naive, color=COLOR_NAIVE, lw=1.4, ls='--', zorder=3,
            label=r'CrEA: Identity Prior $\mathbf{I}$')

    # Direct points & labels
    ax.scatter([8], [err_shrinkage[7]], color=COLOR_SHRINKAGE, s=30, zorder=4)
    ax.scatter([8], [err_naive[7]], color=COLOR_NAIVE, s=30, zorder=4)

    ax.plot([8, 14], [err_shrinkage[7], 44], color=COLOR_SHRINKAGE, lw=0.7)
    ax.text(15, 44, 'Trial 8: 29.38%\n(unscaled: 36.47%)', va='center',
            fontsize=6.8, fontweight='bold', color=COLOR_SHRINKAGE)

    ax.set_xlabel('Online Test Trial $k$', fontweight='bold')
    ax.set_ylabel('Relative Covariance Error (%)', fontweight='bold')
    ax.set_xlim(1, 60)
    ax.set_ylim(0, 95)
    ax.set_yticks([0, 25, 50, 75])
    ax.legend(loc='upper right', fontsize=6.8, frameon=False)
    ax.set_title(r'CrEA Online Adaptation Convergence ($N=29$)', loc='left', pad=6,
                 fontsize=8.0, fontweight='bold', color='#1A2D42')

    for folder in (OUT, REPORTS_FIG):
        fig.savefig(folder / 'supplementary_fig_s2_crea_convergence.pdf', dpi=600, bbox_inches='tight', pad_inches=0.02)
        fig.savefig(folder / 'supplementary_fig_s2_crea_convergence.png', dpi=600, bbox_inches='tight', pad_inches=0.02)

    plt.close(fig)
    print(f"[+] Clean Fig S2 successfully generated: {OUT / 'supplementary_fig_s2_crea_convergence.pdf'}")

if __name__ == '__main__':
    main()
