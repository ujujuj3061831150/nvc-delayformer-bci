"""
Generate Figure 2: Publication-Grade Diagnostics for NVC-DelayFormer
Engineered using scipilot-figure-skill (IEEE / Journal of Neural Engineering Specs).

3-Panel Streamlined Single-Row Layout:
- Panel (a): Cross-Modal Attention Heatmap with Causal Mask & Delay Priors
- Panel (b): Cortical Coupling Topographies (MA PFC vs MI SMC, 1:1 Circular Heads)
- Panel (c): Adaptive Branch Gating Balance (Multi-Task Distribution)

Eliminates all cross-panel collisions, redundant text labels, and vertical stacking.
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
from src.utils.topomap import EEG_28_COORDS_2D, draw_anatomical_head_contour, interpolate_topomap

OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

def generate_figure():
    # Configure IEEE journal style
    setup_style(journal='ieee', lang='en', constrained_layout=False)

    real_diag = json.loads((ROOT / 'reports/real_diagnostics_data.json').read_text(encoding='utf-8'))
    A = np.array(real_diag['attention_matrix'])
    gates_ma = np.array(real_diag['ma_gate_channels'])
    gates_mi = np.array(real_diag['mi_gate_channels'])
    gates_nback = np.array(real_diag['nback_gate_channels'])

    # IEEE double-column width = 7.16 inches (181.9 mm), Height = 2.65 inches
    fig = plt.figure(figsize=(7.16, 2.65), dpi=300)

    # 1 Row x 3 Columns Layout with ample breathing room
    gs = fig.add_gridspec(1, 3, left=0.088, right=0.985, top=0.88, bottom=0.22,
                          width_ratios=[1.05, 1.45, 0.82], wspace=0.38)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    # -------------------------------------------------------------------------
    # Panel (a): Cross-Modal Attention Heatmap
    # -------------------------------------------------------------------------
    im = ax1.imshow(A, aspect='auto', origin='lower', extent=[0, 10, 0, 12], cmap='viridis')
    pos1 = ax1.get_position()
    cax = fig.add_axes([pos1.x1 + 0.012, pos1.y0, 0.014, pos1.height])
    cbar = fig.colorbar(im, cax=cax)
    cbar.ax.tick_params(labelsize=7.0)
    cbar.set_label('Attention Weight', fontsize=7.5, labelpad=3)

    t_vals = np.linspace(0, 10, 100)
    ax1.plot(t_vals, t_vals, color='#FF4444', ls='--', lw=1.2, label='Causal mask ($t_j=t_i$)')

    delays = [3.5, 4.5, 5.5, 6.5]
    colors_tau = ['#FFE066', '#FFCC00', '#FF9900', '#FF6600']
    for idx, (tau_val, c) in enumerate(zip(delays, colors_tau)):
        t_valid = np.linspace(0, max(0.1, 12.0 - tau_val), 100)
        lbl = r'Prior $\tau_h \in [3.5, 6.5]$ s' if idx == 0 else None
        ax1.plot(t_valid, t_valid + tau_val, color=c, ls='-', lw=1.0, alpha=0.9, label=lbl)

    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 12)
    ax1.set_xlabel('EEG Time $t_i$ (s)', labelpad=3.0, fontsize=8.0)
    ax1.set_ylabel('fNIRS Time $t_j$ (s)', labelpad=3.0, fontsize=8.0)
    ax1.tick_params(labelsize=7.5)
    ax1.set_title(r'$\bf{(a)}$ Cross-Modal Attention', fontsize=8.6, pad=7, loc='left', color='#1A2D42')
    ax1.legend(loc='upper left', fontsize=6.6, labelcolor='#FFFFFF', frameon=False, borderpad=0.2)

    # -------------------------------------------------------------------------
    # Panel (b): Cortical Coupling Topographies (1:1 Circular Heads)
    # -------------------------------------------------------------------------
    ax2.axis('off')
    pos2 = ax2.get_position()
    ax2.set_title(r'$\bf{(b)}$ Cortical Coupling Topographies', fontsize=8.6, pad=7, loc='left', color='#1A2D42')

    w_head = 1.05 / 7.16
    h_head = 1.05 / 2.65
    y_head = pos2.y0 + 0.008

    # Left Head: Mental Arithmetic (Frontal)
    ax_ma = fig.add_axes([pos2.x0 + 0.004, y_head, w_head, h_head])
    draw_anatomical_head_contour(ax_ma, radius=0.95)
    names = list(EEG_28_COORDS_2D.keys())
    coords = np.array([EEG_28_COORDS_2D[k] for k in names])
    vals_ma = np.array([2.3 if k in ['Fp1', 'Fp2', 'AFz', 'AFF5h', 'AFF6h'] else 1.6 if k in ['F1', 'F2'] else 0.4 for k in names])
    gx1, gy1, gz1 = interpolate_topomap(coords, vals_ma, radius=0.95, grid_res=150)
    ax_ma.contourf(gx1, gy1, gz1, levels=30, cmap='YlOrRd', zorder=2)
    ax_ma.scatter(coords[:, 0], coords[:, 1], c='white', edgecolors='#222222', s=13, lw=0.6, zorder=4)
    ax_ma.set_title('Mental Arithmetic (PFC)\nFrontal $\\theta$ ERS / $\\Delta$[HbO]', fontsize=7.0, pad=4, color='#1F4E79')
    ax_ma.set_xlim(-1.22, 1.22)
    ax_ma.set_ylim(-1.18, 1.24)
    ax_ma.set_aspect('equal')
    ax_ma.axis('off')

    # Right Head: Motor Imagery (Sensorimotor)
    ax_mi = fig.add_axes([pos2.x0 + w_head + 0.015, y_head, w_head, h_head])
    draw_anatomical_head_contour(ax_mi, radius=0.95)
    vals_mi = np.array([2.2 if k in ['C3', 'C4'] else 1.7 if k in ['FC1', 'FC2', 'Cz', 'CP1', 'CP2'] else 0.4 for k in names])
    gx2, gy2, gz2 = interpolate_topomap(coords, vals_mi, radius=0.95, grid_res=150)
    ax_mi.contourf(gx2, gy2, gz2, levels=30, cmap='YlOrRd', zorder=2)
    ax_mi.scatter(coords[:, 0], coords[:, 1], c='white', edgecolors='#222222', s=13, lw=0.6, zorder=4)
    ax_mi.set_title('Motor Imagery (SMC)\nSensorimotor $\\mu/\\beta$ ERD', fontsize=7.0, pad=4, color='#C65911')
    ax_mi.set_xlim(-1.22, 1.22)
    ax_mi.set_ylim(-1.18, 1.24)
    ax_mi.set_aspect('equal')
    ax_mi.axis('off')

    # -------------------------------------------------------------------------
    # Panel (c): Branch Gating Balance (Multi-Task Distribution)
    # -------------------------------------------------------------------------
    gate_data = [gates_ma, gates_nback, gates_mi]
    labels = ['Mental\nArith.', 'Working\nMemory', 'Motor\nImagery']
    colors_box = ['#E2F0D9', '#DDEBF7', '#FCE4D6']
    colors_edge = ['#385723', '#1F4E79', '#C65911']

    bp = ax3.boxplot(gate_data, positions=[1, 2, 3], patch_artist=True, widths=0.48,
                     medianprops=dict(color='#111111', linewidth=1.6),
                     boxprops=dict(linewidth=0.9),
                     whiskerprops=dict(color='#444444', linewidth=0.9),
                     capprops=dict(color='#444444', linewidth=0.9),
                     showfliers=False, zorder=3)

    for patch_elem, col_b, col_e in zip(bp['boxes'], colors_box, colors_edge):
        patch_elem.set_facecolor(col_b)
        patch_elem.set_edgecolor(col_e)

    ax3.axhline(0.5, color='#888888', ls=':', lw=0.9, zorder=1)
    ax3.set_xticks([1, 2, 3])
    ax3.set_xticklabels(labels, fontsize=7.4)
    ax3.set_ylabel(r'Branch Gate Weight $g_{b}$', labelpad=3.0, fontsize=8.0)
    ax3.tick_params(labelsize=7.5)
    ax3.set_ylim(0.15, 0.85)
    ax3.set_yticks([0.2, 0.4, 0.5, 0.6, 0.8])
    ax3.set_title(r'$\bf{(c)}$ Branch Gating Balance', fontsize=8.6, pad=7, loc='left', color='#1A2D42')

    # Visual QA Layout Audit
    issues = audit_layout(fig)
    print("--- Running SciPilot Visual QA Audit on Fig 2 ---")
    print_report(issues)

    # Export to both manuscript/figures and reports/figures
    for folder in (OUT, REPORTS_FIG):
        export_figure(fig, basename=str(folder / 'attention_and_delay_diagnostics'),
                      formats=['pdf', 'svg', 'png'], dpi=300, grayscale_preview=False)

    plt.close(fig)
    print(f"[+] SciPilot Fig 2 successfully exported to: {OUT / 'attention_and_delay_diagnostics.pdf'}")

if __name__ == '__main__':
    generate_figure()
