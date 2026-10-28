"""
Generate Supplementary Figure S2:
Causal Recursive Euclidean Alignment (CrEA) Online Adaptation Convergence Dynamics
across all 29 Participants (60 Trials).
Engineered using scipilot-figure-skill (IEEE / Journal of Neural Engineering Specs).
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
SCIPILOT_SCRIPTS = Path(r"C:\Users\ikunccc\.gemini\config\skills\scipilot-figure\scripts")
if str(SCIPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCIPILOT_SCRIPTS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from setup_style import setup_style
from visual_qa import audit_layout, print_report
from export_figure import export_figure

OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

def main():
    setup_style(journal='ieee', lang='en', constrained_layout=False)

    diag_path = ROOT / "reports" / "real_diagnostics_data.json"
    with open(diag_path, "r", encoding="utf-8") as f:
        real_diag = json.load(f)

    k_trials = np.array(real_diag["crea_trials"])
    err_shrinkage = np.array(real_diag["crea_error_shrinkage"])
    err_naive = np.array(real_diag["crea_error_naive"])

    COLOR_SHRINKAGE = "#0F4D92"
    COLOR_NAIVE = "#D95F02"

    fig, ax = plt.subplots(figsize=(3.5, 2.5), dpi=300)
    plt.subplots_adjust(left=0.17, right=0.96, top=0.88, bottom=0.22)

    # Shaded adaptation window (Trials 1-8)
    ax.axvspan(1, 8, color='#F0F4F8', zorder=1, label=r'Bedside adaptation ($k \leq 8$)')
    ax.axvline(8.0, color='#2A9D8F', ls=':', lw=0.9, zorder=2)

    ax.plot(k_trials, err_shrinkage, color=COLOR_SHRINKAGE, lw=1.8, zorder=3,
            label=r'CrEA: $\widetilde{\mathbf{R}}_{\mathrm{src}}$ (Trace-Matched)')
    ax.plot(k_trials, err_naive, color=COLOR_NAIVE, lw=1.4, ls='--', zorder=3,
            label=r'CrEA: Identity Prior $\mathbf{I}$')

    # Direct points & callout
    ax.scatter([8], [err_shrinkage[7]], color=COLOR_SHRINKAGE, s=26, zorder=4)
    ax.scatter([8], [err_naive[7]], color=COLOR_NAIVE, s=26, zorder=4)

    ax.plot([8, 14], [err_shrinkage[7], 44], color=COLOR_SHRINKAGE, lw=0.7)
    ax.text(15, 44, 'Trial 8: 29.38%\n(unscaled: 36.47%)', va='center',
            fontsize=6.8, fontweight='bold', color=COLOR_SHRINKAGE)

    ax.set_xlabel('Online Test Trial $k$', fontsize=8.0, labelpad=3)
    ax.set_ylabel('Relative Covariance Error (%)', fontsize=8.0, labelpad=3)
    ax.set_xlim(1, 60)
    ax.set_ylim(0, 95)
    ax.set_yticks([0, 25, 50, 75])
    ax.tick_params(labelsize=7.5)
    ax.legend(loc='upper right', fontsize=6.6, frameon=False)
    ax.set_title(r"$\bf{CrEA\ Whitening\ Convergence}$", loc='left', pad=6,
                 fontsize=8.6, color='#1A2D42')

    # Visual QA Layout Audit
    issues = audit_layout(fig)
    print("--- Running SciPilot Visual QA Audit on Fig S2 ---")
    print_report(issues)

    for folder in (OUT, REPORTS_FIG):
        export_figure(fig, basename=str(folder / 'supplementary_fig_s2_crea_convergence'),
                      formats=['pdf', 'png'], dpi=300)

    plt.close(fig)
    print(f"[+] SciPilot Fig S2 successfully generated: {OUT / 'supplementary_fig_s2_crea_convergence.pdf'}")

if __name__ == '__main__':
    main()
