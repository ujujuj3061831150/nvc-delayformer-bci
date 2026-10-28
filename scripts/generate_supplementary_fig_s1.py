"""
Generate Supplementary Figure S1:
Candidate Delay Sensitivity and Factorial Prior Ablation Contrast between Mental Arithmetic (MA)
and Motor Imagery (MI) across 29 LOSO Folds.
Engineered using scipilot-figure-skill (IEEE / Journal of Neural Engineering Specs).
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

from scripts.figure_support import setup_style, audit_layout, print_report, export_figure

OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

def main():
    setup_style(journal='ieee', lang='en', constrained_layout=False)

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

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.16, 2.90), dpi=300)
    plt.subplots_adjust(wspace=0.30, left=0.088, right=0.98, top=0.86, bottom=0.28)

    # -------------------------------------------------------------------------
    # (a) Delay Sensitivity
    # -------------------------------------------------------------------------
    ax_a.axvspan(3.5, 6.5, color='#F0F4F8', zorder=1, label=r'HRF Prior [3.5, 6.5] s')

    ax_a.plot(ma_taus, ma_means, color=COLOR_MA, lw=1.8, zorder=3)
    ax_a.errorbar(ma_taus, ma_means, yerr=ma_ses, fmt='o', color=COLOR_MA,
                  ecolor=COLOR_MA, elinewidth=1.1, capsize=2.5, capthick=0.9,
                  markersize=4.8, zorder=4, label='Mental Arithmetic (MA)')

    ax_a.plot(mi_taus, mi_means, color=COLOR_MI, lw=1.8, linestyle='--', zorder=3)
    ax_a.errorbar(mi_taus, mi_means, yerr=mi_ses, fmt='s', color=COLOR_MI,
                  ecolor=COLOR_MI, elinewidth=1.1, capsize=2.5, capthick=0.9,
                  markersize=4.5, zorder=4, label='Motor Imagery (MI)')

    ax_a.text(0.03, 0.94, "MA (+5.12 pp, $p < 0.001$)", transform=ax_a.transAxes, va="top", ha="left",
              fontsize=8.0, fontweight="bold", color=COLOR_MA)
    ax_a.text(0.98, 0.05, "MI ($p = 0.58$)", transform=ax_a.transAxes, va="bottom", ha="right",
              fontsize=8.0, fontweight="bold", color=COLOR_MI)

    ax_a.set_xlabel(r"Inference Candidate Delay $\bar{\tau}$ (s)", fontsize=8.0, labelpad=3)
    ax_a.set_ylabel("Grand Mean LOSO Accuracy (%)", fontsize=8.0, labelpad=3)
    ax_a.set_xlim(-0.4, 8.4)
    ax_a.set_xticks([0, 2, 4, 5, 6, 8])
    ax_a.set_ylim(63.0, 85.0)
    ax_a.tick_params(labelsize=8.0)

    ax_a.set_title(r"$\bf{(a)}$ Delay Sensitivity Across Paradigms", loc="left", pad=7,
                   fontsize=9.1, color='#1A2D42')

    # -------------------------------------------------------------------------
    # (b) Factorial Ablation
    # -------------------------------------------------------------------------
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
    # Point-and-interval summaries do not imply a bar-length baseline. Raw
    # participant arrays are not available for every archived condition.
    ax_b.errorbar(x - width/2 - 0.02, ma_fact_means, yerr=ma_fact_ses,
                  fmt='o', color=COLOR_MA, elinewidth=1.2, capsize=2.5,
                  markersize=5, label='Mental Arithmetic')
    ax_b.errorbar(x + width/2 + 0.02, mi_fact_means, yerr=mi_fact_ses,
                  fmt='s', color=COLOR_MI, elinewidth=1.2, capsize=2.5,
                  markersize=4.5, label='Motor Imagery')

    ax_b.axhline(50.0, color="#888888", linestyle="--", linewidth=0.8, zorder=1)

    # Statistical bracket: Full vs Both Off
    bracket_y = 82.5
    ax_b.plot([x[0] - width/2, x[0] - width/2, x[3] - width/2, x[3] - width/2],
              [bracket_y - 0.8, bracket_y, bracket_y, bracket_y - 0.8], color=COLOR_MA, lw=0.9)
    ax_b.text((x[0] + x[3]) / 2 - width/2, bracket_y + 0.5, r"$+4.94\,\mathrm{pp}$ ($p = 6.05\times 10^{-5}$)",
              ha="center", va="bottom", fontsize=9.0, fontweight="bold", color=COLOR_MA)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(cond_labels, fontsize=8.0)
    ax_b.set_ylabel("Held-Out LOSO Accuracy (%)", fontsize=8.0, labelpad=3)
    ax_b.set_ylim(48.0, 88.0)
    ax_b.set_yticks([50, 60, 70, 80])
    ax_b.tick_params(labelsize=8.0)
    handles, labels = ax_a.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, 0.005),
               ncol=3, fontsize=8.0, frameon=False, columnspacing=1.6)
    ax_b.set_title(r"$\bf{(b)}$ Factorial Constraint Decomposition", loc="left", pad=7,
                   fontsize=9.1, color='#1A2D42')

    # Visual QA Layout Audit
    issues = audit_layout(fig)
    print("--- Running SciPilot Visual QA Audit on Fig S1 ---")
    print_report(issues)

    for folder in (OUT, REPORTS_FIG):
        export_figure(fig, basename=str(folder / 'supplementary_fig_s1_delay_curves'),
                      formats=['pdf', 'png'], dpi=300, grayscale_preview=True)

    plt.close(fig)
    print(f"[+] SciPilot Fig S1 successfully generated: {OUT / 'supplementary_fig_s1_delay_curves.pdf'}")

if __name__ == '__main__':
    main()
