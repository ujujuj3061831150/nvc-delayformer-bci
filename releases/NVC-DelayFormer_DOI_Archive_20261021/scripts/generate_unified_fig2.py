"""
Generate Figure 1: Consolidated Diagnostics for NVC-DelayFormer
Includes:
- Panel (a): Multi-Head Cross-Modal Attention Matrix Heatmap
- Panel (b): Hemodynamic Delay Parameter Scan (tau in [0, 8] s)
- Panel (c): Online CrEA Streaming Convergence (k=1..60)
- Panel (d): Multi-Task Adaptive Gating Distributions
- Panel (e): Cortical Spatial Coupling Topographies (Dual-Task)

Target height: 263 pt (3.65 inches)
Width: 7.16 inches (IEEE textwidth)
"""
from pathlib import Path
import json
from audit_panel_alignment import require_matplotlib_panel_alignment
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],
    'font.size': 7.2,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.7,
    'axes.labelsize': 8.0,
    'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5,
    'legend.frameon': False,
    'legend.fontsize': 7.5,
})

def draw_head(ax, cx, cy, r):
    """Draw a clean human head contour with nose and ears."""
    head = plt.Circle((cx, cy), r, facecolor='none', edgecolor='#333333', lw=0.9, zorder=2)
    ax.add_patch(head)
    nw = 0.12 * r
    nh = 0.18 * r
    ax.plot([cx - nw, cx, cx + nw], [cy + 0.98 * r, cy + r + nh, cy + 0.98 * r], color='#333333', lw=0.9, solid_capstyle='round', zorder=3)
    ew = 0.14 * r
    eh = 0.34 * r
    ear_l = patches.Arc((cx - r - 0.01 * r, cy), ew, eh, angle=0, theta1=90, theta2=270, edgecolor='#333333', lw=0.9, zorder=3)
    ear_r = patches.Arc((cx + r + 0.01 * r, cy), ew, eh, angle=0, theta1=-90, theta2=90, edgecolor='#333333', lw=0.9, zorder=3)
    ax.add_patch(ear_l)
    ax.add_patch(ear_r)

def generate_figure():
    bench = json.loads((ROOT / 'reports/real_29sub_benchmark_and_ablation_summary.json').read_text(encoding='utf-8'))
    diag = json.loads((ROOT / 'reports/factorial_and_attention_results.json').read_text(encoding='utf-8'))
    real_diag = json.loads((ROOT / 'reports/real_diagnostics_data.json').read_text(encoding='utf-8'))

    A = np.array(real_diag['attention_matrix'])
    assert A.shape == (124, 250), 'Unexpected attention matrix shape'

    gates_ma = np.array(real_diag['ma_gate_channels'])
    gates_mi = np.array(real_diag['mi_gate_channels'])
    gates_nback = np.array(real_diag['nback_gate_channels'])

    # 7.16 inches wide, 2.95 inches high (~212 pt)
    fig = plt.figure(figsize=(7.16, 3.65))
    gs_row1 = fig.add_gridspec(1, 3, left=0.06, right=0.98, top=0.95, bottom=0.64,
                                width_ratios=[1, 1, 1], wspace=0.68)
    ax1 = fig.add_subplot(gs_row1[0, 0])
    ax2 = fig.add_subplot(gs_row1[0, 1])
    ax3 = fig.add_subplot(gs_row1[0, 2])

    gs_row2 = fig.add_gridspec(1, 2, left=0.06, right=0.98, top=0.42, bottom=0.08,
                                width_ratios=[1.0, 1.0], wspace=0.35)
    ax4 = fig.add_subplot(gs_row2[0, 0])
    ax5 = fig.add_subplot(gs_row2[0, 1])

    # -------------------------------------------------------------
    # (a) Attention Matrix
    # -------------------------------------------------------------
    im = ax1.imshow(A, aspect='auto', origin='lower', extent=[0, 10, 0, 12], cmap='viridis')
    pos = ax1.get_position()
    cax = fig.add_axes([pos.x1 + 0.008, pos.y0, 0.009, pos.height])
    cbar = fig.colorbar(im, cax=cax)
    cbar.ax.set_title(r'$A_{ij}$', fontsize=8, pad=4)
    cbar.ax.tick_params(labelsize=7.5)

    t_vals = np.linspace(0, 10, 150)
    ax1.plot(t_vals, t_vals, color='#FF5555', ls='--', lw=1.0, label='Time boundary')
    delays = [3.5, 4.5, 5.5, 6.5]
    colors_tau = ['#FFE066', '#FFCC00', '#FF9900', '#FF6600']
    for idx, (tau_val, c) in enumerate(zip(delays, colors_tau)):
        t_valid = np.linspace(0, max(0.1, 12.0 - tau_val), 100)
        lbl = 'Delay prior' if idx == 0 else None
        ax1.plot(t_valid, t_valid + tau_val, color=c, ls='-', lw=0.8, alpha=0.9, label=lbl)

    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 12)
    ax1.set_xlabel('EEG time (s)', labelpad=2)
    ax1.set_ylabel('fNIRS time (s)', labelpad=2)
    leg = ax1.legend(loc='lower right', fontsize=7.5, frameon=False, borderpad=0.2, handlelength=0.8, labelcolor='white')
    for txt in leg.get_texts():
        txt.set_color('white')
    ax1.set_title('(a) Cross-Modal Attention', fontsize=7.5, pad=4, fontweight='bold', color='#1A2D42')

    # -------------------------------------------------------------
    # (b) Delay Parameter Scan
    # -------------------------------------------------------------
    delay_keys = sorted(bench['delay_sweep'], key=float)
    x_delays = np.array([float(k) for k in delay_keys])
    y_means = []
    y_cis = []
    for k in delay_keys:
        f_accs = np.array(bench['delay_sweep'][k]['fold_accs'])
        y_means.append(f_accs.mean())
        y_cis.append(stats.t.ppf(0.975, len(f_accs) - 1) * f_accs.std(ddof=1) / np.sqrt(len(f_accs)))

    ax2.errorbar(x_delays, y_means, y_cis, fmt='o-', color='#0F4D92', lw=1.2, ms=3.5, capsize=2.5, label='Mean ± 95% CI')
    ax2.axvspan(3.5, 6.5, color='#FFE066', alpha=0.25, label=r'Prior Band')
    ax2.axvline(5.0, color='#D97736', ls=':', lw=1.0)
    ax2.set_xlabel(r'Inference Delay $\bar{\tau}$ (s)', labelpad=2)
    ax2.set_ylabel('Accuracy (%)', labelpad=2)
    ax2.set_xticks([0, 2, 4, 5, 6, 8])
    ax2.set_ylim(72, max(np.array(y_means) + np.array(y_cis)) + 0.7)
    ax2.set_yticks([74, 77, 80])
    ax2.set_title('(b) Delay Parameter Scan', fontsize=7.5, pad=4, fontweight='bold', color='#1A2D42')

    # -------------------------------------------------------------
    # (c) Online CrEA Convergence
    # -------------------------------------------------------------
    k_trials = np.array(real_diag['crea_trials'])
    err_shrinkage = np.array(real_diag['crea_error_shrinkage'])
    err_naive = np.array(real_diag['crea_error_naive'])

    ax3.plot(k_trials, err_shrinkage, color='#0F4D92', lw=1.3, label='Source prior')
    ax3.plot(k_trials, err_naive, color='#D97736', lw=1.1, ls='--', label='Identity prior')
    ax3.axvline(8.0, color='#2A9D8F', ls=':', lw=0.9)
    ax3.text(22, 42, 'Trial 8: 29.38%', fontsize=7.5, color='#0A3663', fontweight='bold')
    ax3.set_xlabel('Online Trial $k$', labelpad=2)
    ax3.set_ylabel('Relative cov. error (%)', labelpad=2)
    ax3.set_xlim(1, 60)
    ax3.set_ylim(0, 95)
    ax3.set_yticks([0, 25, 50, 75])
    ax3.legend(loc='upper right', fontsize=7.5, framealpha=0.9, borderpad=0.2)
    ax3.set_title('(c) Online CrEA Adaptation', fontsize=7.5, pad=4, fontweight='bold', color='#1A2D42')

    # -------------------------------------------------------------
    # (d) Multi-Task Adaptive Gating
    # -------------------------------------------------------------
    gate_data = [gates_ma, gates_nback, gates_mi]
    labels = ['Mental\nArith.', 'Working\nMemory', 'Motor\nImagery']
    box_colors = ['#AADCA9', '#B4C0E4', '#E9A6A1']

    bp = ax4.boxplot(gate_data, patch_artist=True, widths=0.42,
                     medianprops=dict(color='#1A2D42', linewidth=1.2),
                     whiskerprops=dict(color='#555555', linewidth=0.7),
                     capprops=dict(color='#555555', linewidth=0.7),
                     showfliers=False)

    for patch_elem, col in zip(bp['boxes'], box_colors):
        patch_elem.set_facecolor(col)
        patch_elem.set_alpha(0.80)
        patch_elem.set_edgecolor('#333333')
        patch_elem.set_linewidth(0.6)

    for idx, (vals, col) in enumerate(zip(gate_data, ['#2E7D32', '#1565C0', '#C62828'])):
        jitter = np.linspace(-0.08, 0.08, len(vals))
        # Deterministic horizontal jitter only; all measured y values are unchanged.
        jitter = jitter[(np.arange(len(vals)) * 73) % len(vals)]
        ax4.scatter(np.full_like(vals, idx + 1) + jitter, vals, color=col, s=4.5, alpha=0.35, edgecolors='none', zorder=3)

    ax4.set_xticks([1, 2, 3])
    ax4.set_xticklabels(labels, fontsize=7.5)
    ax4.tick_params(axis='x', pad=2)
    ax4.set_ylabel(r'Gate Weight $g_{b,d}$', labelpad=2)
    ax4.set_ylim(0.05, 1.05)
    ax4.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax4.axhline(0.5, color='#999999', ls=':', lw=0.7, alpha=0.7)
    ax4.set_title('(d) Gating Across Tasks', fontsize=7.5, pad=4, fontweight='bold', color='#1A2D42')

    # -------------------------------------------------------------
    # (e) Cortical Spatial Coupling Topographies
    # -------------------------------------------------------------
    ax5.set_xlim(0, 2.4)
    ax5.set_ylim(-0.05, 1.05)
    ax5.axis('off')

    cx1, cx2 = 0.58, 1.82
    draw_head(ax5, cx=cx1, cy=0.52, r=0.28)
    ax5.text(cx1, 0.96, 'Mental Arithmetic (PFC)', ha='center', fontsize=7.5, fontweight='bold', color='#1A2D42')

    theta = np.linspace(0, 2 * np.pi, 60)
    pfc_x = cx1 + 0.16 * np.cos(theta)
    pfc_y = 0.60 + 0.10 * np.sin(theta)
    ax5.fill(pfc_x, pfc_y, facecolor='#E63946', edgecolor='none', alpha=0.65, zorder=2)
    ax5.scatter([cx1, cx1 - 0.07, cx1 + 0.07], [0.66, 0.61, 0.61], s=3.5, color='#FFFFFF', zorder=4)
    ax5.text(cx1, 0.10, 'Prefrontal cortex\n$\\theta$ ERS + $\\Delta$[HbO]',
             ha='center', va='top', fontsize=7.5, color='#222222', linespacing=1.15)

    draw_head(ax5, cx=cx2, cy=0.52, r=0.28)
    ax5.text(cx2, 0.96, 'Motor Imagery (SMC)', ha='center', fontsize=7.5, fontweight='bold', color='#1A2D42')

    smc_l_x = cx2 - 0.11 + 0.07 * np.cos(theta)
    smc_l_y = 0.52 + 0.10 * np.sin(theta)
    ax5.fill(smc_l_x, smc_l_y, facecolor='#2A9D8F', edgecolor='none', alpha=0.70, zorder=2)

    smc_r_x = cx2 + 0.11 + 0.07 * np.cos(theta)
    smc_r_y = 0.52 + 0.10 * np.sin(theta)
    ax5.fill(smc_r_x, smc_r_y, facecolor='#E76F51', edgecolor='none', alpha=0.70, zorder=2)
    ax5.scatter([cx2 - 0.11, cx2 + 0.11], [0.52, 0.52], s=3.5, color='#FFFFFF', zorder=4)
    ax5.text(cx2, 0.10, 'Sensorimotor cortex\n$\\mu/\\beta$ ERD + hemodynamics',
             ha='center', va='top', fontsize=7.5, color='#222222', linespacing=1.15)

    ax5.set_title('(e) Neurovascular Coupling Schematics', fontsize=7.5, pad=4, fontweight='bold', color='#1A2D42')

    require_matplotlib_panel_alignment(fig, axes=[ax1, ax2, ax3, ax4, ax5],
        panel_ids=['a', 'b', 'c', 'd', 'e'],
        row_groups=[['a', 'b', 'c'], ['d', 'e']],
        json_out=OUT / 'attention_and_delay_diagnostics.alignment.json', strict=True)

    for folder in (OUT, REPORTS_FIG):
        fig.savefig(folder / 'attention_and_delay_diagnostics.pdf', dpi=600, bbox_inches='tight', pad_inches=0.02)
        fig.savefig(folder / 'attention_and_delay_diagnostics.svg', dpi=600, bbox_inches='tight', pad_inches=0.02)
        fig.savefig(folder / 'attention_and_delay_diagnostics.png', dpi=600, bbox_inches='tight', pad_inches=0.02)

        svg = folder / 'attention_and_delay_diagnostics.svg'
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')

    plt.close(fig)
    print(f"[+] Consolidated Fig 1 generated: {OUT / 'attention_and_delay_diagnostics.pdf'}")

if __name__ == '__main__':
    generate_figure()
