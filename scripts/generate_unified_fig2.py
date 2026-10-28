"""
Generate the temporal diagnostics figure for NVC-DelayFormer.
Engineered using scipilot-figure-skill (IEEE / Journal of Neural Engineering Specs).

Core Principles:
- "图不需要有太多的文字说明，尽量精简直观，图是来支撑结果的"
- High Data-Ink Ratio, Minimal Text, Pure Empirical Evidence
- Panel (a): Delay Attention Profile (Learned Attention vs Prior Kernels, Acausal Mask)
- Panel (b): Saved attention matrix with the token timestamp boundary
- Panel (c): Branch Gating Balance (Raincloud Plot: Half-Violin + Box + Jitter Points)
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scripts.figure_support import setup_style, audit_layout, print_report, export_figure

OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = ROOT / 'tmp/figure_layout_revision_20261028'

def generate_figure():
    # Configure IEEE style
    setup_style(journal='ieee', lang='en', constrained_layout=False)

    real_diag = json.loads((ROOT / 'reports/real_diagnostics_data.json').read_text(encoding='utf-8'))
    A = np.array(real_diag['attention_matrix'])
    gates_ma = np.array(real_diag['ma_gate_channels'])
    gates_mi = np.array(real_diag['mi_gate_channels'])
    gates_nback = np.array(real_diag['nback_gate_channels'])

    # IEEE double-column width = 7.16 inches (181.9 mm), Height = 2.65 inches
    fig = plt.figure(figsize=(7.16, 2.65), dpi=300)

    # 1 Row x 3 Columns Layout with ample breathing room
    gs = fig.add_gridspec(1, 3, left=0.080, right=0.985, top=0.76, bottom=0.23,
                          width_ratios=[1.10, 1.45, 1.05], wspace=0.36)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    # =========================================================================
    # Panel (a): Delay Attention Profile (Pure visual evidence of time-lag alignment)
    # =========================================================================
    delta_grid = np.linspace(-2.0, 10.0, 300)

    # Shaded physiological HRF window
    ax1.axvspan(3.5, 6.5, color='#F0F4F8', zorder=1, label='_nolegend_')
    # Acausal rejection zone
    ax1.axvspan(-2.0, 0.0, color='#FFF1F0', alpha=0.8, zorder=1, label='_nolegend_')

    # Plot Prior Gaussian Kernels
    delays = [3.5, 4.5, 5.5, 6.5]
    colors_tau = ['#F59E0B', '#D97706', '#B45309', '#92400E']
    for idx, (tau, c) in enumerate(zip(delays, colors_tau)):
        penalty = -0.5 * ((delta_grid - tau) / 1.5) ** 2
        tail = 1.0 + 0.3 * np.maximum(0.0, delta_grid - tau)
        kernel = np.exp(penalty * tail)
        kernel[delta_grid < 0] = 0.0
        ax1.plot(delta_grid, kernel, color=c, lw=1.1, ls='--', alpha=0.85,
                 label='Prior kernels' if idx == 0 else None, zorder=3)

    # Calculate empirical cross-attention density profile
    t_eeg = np.arange(A.shape[1]) / 25.0
    t_fnirs = np.arange(A.shape[0]) / (124.0 / 12.0)
    delays_grid = t_fnirs[:, None] - t_eeg[None, :]
    bins = np.linspace(-2.0, 10.0, 61)
    hist, bin_edges = np.histogram(delays_grid.ravel(), bins=bins, weights=A.ravel())
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    hist_smooth = hist.astype(float).copy()
    # Smooth the two sides separately without erasing measured negative-lag weights.
    for side in (bin_centers < 0, bin_centers >= 0):
        hist_smooth[side] = np.convolve(hist[side], np.ones(5) / 5, mode='same')
    hist_norm = hist_smooth / hist_smooth.max()

    ax1.plot(bin_centers, hist_norm, color='#0F4D92', lw=2.0, label='Attention', zorder=4)
    ax1.fill_between(bin_centers, 0, hist_norm, color='#0F4D92', alpha=0.18, zorder=2)

    ax1.set_xlabel(r'Hemodynamic Delay $\delta = t_j - t_i$ (s)', fontsize=9.0, labelpad=3)
    ax1.set_ylabel('Normalized lag profile', fontsize=8.0, labelpad=3)
    ax1.set_xlim(-2.0, 10.0)
    ax1.set_ylim(0.0, 1.30)
    ax1.tick_params(labelsize=8.0)
    ax1.set_title(r'$\bf{(a)}$ Delay Attention Profile', fontsize=9.1, pad=0, y=1.32, loc='left', color='#1A2D42')
    ax1.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), fontsize=8.0, frameon=False, borderaxespad=0, handlelength=1.6, labelspacing=0.2)

    # =========================================================================
    # Panel (b): Saved trial- and head-averaged Sub-05 MA attention weights.
    # =========================================================================
    pos2 = ax2.get_position()
    ax2.set_position([pos2.x0 + 0.015, pos2.y0, pos2.width - 0.055, pos2.height])
    cmap = plt.get_cmap('cividis').copy()
    cmap.set_bad('white')
    # Use every stored positive weight. Exact zeros remain white rather than
    # receiving an arbitrary pseudocount before the logarithm.
    logged = np.ma.masked_all(A.shape)
    logged[A > 0] = np.log10(A[A > 0])
    step_e = 1.0 / 25.0
    step_n = 12.0 / 124.0
    heat = ax2.imshow(logged, origin='lower', aspect='auto', interpolation='nearest',
                      extent=[-step_e/2, t_eeg[-1]+step_e/2,
                              -step_n/2, t_fnirs[-1]+step_n/2],
                      cmap=cmap, vmin=np.log10(A[A > 0].min()), vmax=np.log10(A.max()))
    ax2.plot([0, 10], [0, 10], color='#777777', lw=0.7, ls='--')
    ax2.set(xlim=(0, 10), ylim=(0, 12), xticks=[0, 5, 10], yticks=[0, 6, 12])
    ax2.set_xlabel('EEG token time (s)', fontsize=8.0, labelpad=3)
    ax2.set_ylabel('fNIRS token time (s)', fontsize=8.0, labelpad=3)
    ax2.tick_params(labelsize=8.0)
    ax2.set_title(r'$\bf{(b)}$ Empirical Attention', fontsize=9.1, pad=0, y=1.32,
                  loc='left', color='#1A2D42')
    cax = fig.add_axes([pos2.x1 - 0.023, pos2.y0, 0.010, pos2.height])
    cb = fig.colorbar(heat, cax=cax, ticks=[-6, -3, 0])
    cb.ax.tick_params(labelsize=8.0, length=2)
    cb.ax.set_title('log10 A', fontsize=8.0, pad=5)
    cb.outline.set_linewidth(0.5)

    # =========================================================================
    # Panel (c): Branch Gating Balance (Raincloud Plot: Direct distribution proof)
    # =========================================================================
    gate_data = [gates_ma, gates_nback, gates_mi]
    labels = ['Mental\nArith.', 'Working\nMemory', 'Motor\nImagery']
    colors_fill = ['#385723', '#1F4E79', '#C65911']

    positions = [1.0, 2.0, 3.0]
    rng = np.random.default_rng(42)

    for pos, vals, col in zip(positions, gate_data, colors_fill):
        # 1. Half-violin (KDE) on left side
        kde = stats.gaussian_kde(vals, bw_method=0.35)
        y_kde = np.linspace(vals.min() - 0.05, vals.max() + 0.05, 100)
        dens = kde(y_kde)
        dens_norm = (dens / dens.max()) * 0.28
        ax3.fill_betweenx(y_kde, pos - dens_norm, pos, color=col, alpha=0.30, zorder=2, lw=0)
        ax3.plot(pos - dens_norm, y_kde, color=col, lw=1.0, zorder=3)

        # 2. Narrow boxplot in center
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        iqr = q3 - q1
        w_low = max(vals.min(), q1 - 1.5 * iqr)
        w_high = min(vals.max(), q3 + 1.5 * iqr)

        ax3.fill_between([pos - 0.04, pos + 0.04], q1, q3, color='#FFFFFF', edgecolor=col, lw=1.1, zorder=4)
        ax3.plot([pos - 0.04, pos + 0.04], [med, med], color='#111111', lw=1.8, zorder=5)
        ax3.plot([pos, pos], [q3, w_high], color=col, lw=1.0, zorder=4)
        ax3.plot([pos, pos], [q1, w_low], color=col, lw=1.0, zorder=4)

        # 3. Jittered scatter dots on right side
        jitter = rng.uniform(0.06, 0.24, size=len(vals))
        ax3.scatter(pos + jitter, vals, color=col, alpha=0.45, s=7, edgecolors='none', zorder=3)

    ax3.axhline(0.5, color='#888888', ls=':', lw=0.9, zorder=1)
    ax3.set_xticks(positions)
    ax3.set_xticklabels(labels, fontsize=8.0)
    ax3.set_ylabel(r'Branch Gate Weight $g_{b}$', labelpad=3.0, fontsize=9.0)
    ax3.set_xlim(0.5, 3.5)
    ax3.set_ylim(0.10, 0.85)
    ax3.set_yticks([0.2, 0.4, 0.5, 0.6, 0.8])
    ax3.tick_params(labelsize=8.0)
    ax3.set_title(r'$\bf{(c)}$ Branch Gating Balance', fontsize=9.1, pad=0, y=1.32, loc='left', color='#1A2D42')

    # Visual QA Layout Audit
    issues = audit_layout(fig)
    print("--- Running visual QA on the temporal diagnostics figure ---")
    print_report(issues)

    # Export to manuscript/figures, reports/figures, and artifacts
    for folder in (OUT, REPORTS_FIG):
        export_figure(fig, basename=str(folder / 'attention_and_delay_diagnostics'),
                      formats=['pdf', 'svg', 'png'], dpi=300, grayscale_preview=True)

    export_figure(fig, basename=str(ARTIFACT_DIR / 'minimalist_pure_evidence_fig2'),
                  formats=['png'], dpi=300, grayscale_preview=True)

    plt.close(fig)
    print(f"[+] Temporal diagnostics figure generated: {OUT / 'attention_and_delay_diagnostics.pdf'}")

if __name__ == '__main__':
    generate_figure()
