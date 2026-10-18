"""Python figure workflow: computation, held-out performance, delay sensitivity.

Figure contract: the schematic specifies the computation, the benchmark shows
participant-level performance, and the sweep characterizes fixed-weight sensitivity.
All quantities come from saved records. Export vector PDF/SVG and 600-dpi PNG.
"""
from pathlib import Path
import json, shutil
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
ARCHIVE = ROOT / 'reports/archive/final_revision_20261013/figures_before_polishing'
ARCHIVE.mkdir(parents=True, exist_ok=True)
bench = json.loads((ROOT / 'reports/real_29sub_benchmark_and_ablation_summary.json').read_text(encoding='utf-8'))

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 8.5,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.7,
    'legend.frameon': False
})

def save(fig, name):
    for ext in ('pdf', 'svg', 'png'):
        dest = OUT / (name + '.' + ext)
        fig.savefig(dest, dpi=600, bbox_inches='tight', pad_inches=0.03)
        rep_dest = ROOT / 'reports/figures' / (name + '.' + ext)
        rep_dest.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(rep_dest, dpi=600, bbox_inches='tight', pad_inches=0.03)
    plt.close(fig)

# -------------------------------------------------------------------------
# Figure 1: NVC-DelayFormer Architectural Schematic (Clean & Non-overlapping)
# -------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14.0, 6.7))
ax.set(xlim=(0, 14.0), ylim=(0, 7.1))
ax.axis('off')

def box(x, y, w, h, text, color='#edf1f5', edgecolor='#51697a', lw=0.85, fontsize=8.2, bold_title=None, title_size=9.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.06', facecolor=color, edgecolor=edgecolor, lw=lw))
    if bold_title:
        ax.text(x + w / 2, y + h - 0.22, bold_title, ha='center', va='top', fontsize=title_size, fontweight='bold', color='#1a2d42')
        ax.text(x + w / 2, y + (h - 0.28) / 2, text, ha='center', va='center', fontsize=fontsize, color='#2c3e50', linespacing=1.28)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fontsize, color='#2c3e50', linespacing=1.28)

def arrow(points, color='#486581', lw=1.1):
    for start, end in zip(points[:-2], points[1:-1]):
        ax.plot([start[0], end[0]], [start[1], end[1]], color=color, lw=lw)
    ax.annotate('', xy=points[-1], xytext=points[-2],
                arrowprops=dict(arrowstyle='->', color=color, lw=lw, shrinkA=0, shrinkB=0))

# 1. Inputs (x: 0.2 to 2.4)
box(0.2, 5.0, 2.2, 1.65,
    r'Shape: $(B, 30, 1000)$' + '\n' +
    r'10.0 s at 100 Hz ($t \in [0, 10]$ s)' + '\n' +
    'Causal Recursive EA (CrEA)',
    color='#eef3f8', bold_title='Multichannel EEG')

box(0.2, 3.10, 2.2, 1.65,
    r'Shape: $(B, 72, 124)$' + '\n' +
    r'12.0 s at 10.33 Hz ($t \in [0, 12]$ s)' + '\n' +
    'Pre-Trial Baseline MBLL',
    color='#edf6f2', bold_title='Hemodynamic fNIRS')

# 2. Encoders (x: 2.8 to 5.4)
box(2.8, 5.0, 2.6, 1.65,
    r'Temporal Conv2D ($1 \times 64$)' + '\n' +
    r'Depthwise Spatial ($30 \times 1$)' + '\n' +
    r'AvgPool2D ($1 \times 4$) $\to$ SepConv' + '\n' +
    r'Tokens: $\mathbf{H}_e \in \mathbb{R}^{B \times 250 \times 64}$ (25 Hz)',
    color='#eef3f8', bold_title='EEGNet-2D Backbone')

box(2.8, 3.10, 2.6, 1.65,
    r'Spatial Conv1D ($72 \to 32$)' + '\n' +
    r'Temporal Conv1D ($32 \to 64$, $k=5$)' + '\n' +
    r'Tokens: $\mathbf{H}_n \in \mathbb{R}^{B \times 124 \times 64}$ (10.33 Hz)',
    color='#edf6f2', bold_title='fNIRS Conv1D Encoder')

# 3. Deep Latent Pathway (x: 5.8 to 9.7)
box(5.8, 3.10, 3.9, 3.45,
    r'4 Attention Heads $\times$ 16 Features' + '\n' +
    r'Query: $\mathbf{Q} = \mathbf{H}_n \mathbf{W}_q \in \mathbb{R}^{B \times 124 \times 64}$' + '\n' +
    r'Key/Value: $\mathbf{K}, \mathbf{V} = \mathbf{H}_e \mathbf{W}_{k,v} \in \mathbb{R}^{B \times 250 \times 64}$' + '\n' +
    r'Dispersive Delay Prior (Eq. 6):' + '\n' +
    r'$P_{ij}^{(h)} = -\frac{(\delta_{ij} - \tau_h)^2}{2\sigma_h^2} \cdot [1 + 0.3 \max(0, \delta_{ij} - \tau_h)]$' + '\n' +
    r'Multi-Scale Latencies: $\tau_h \in \{3.5, 4.5, 5.5, 6.5\}$ s' + '\n' +
    r'Strict Causal Mask (Eq. 7): $M_{ij} = -\infty$ for $\delta_{ij} < 0$' + '\n' +
    r'LayerNorm$(\mathbf{H}_n + \mathbf{A}\mathbf{V}) \to \mathbf{H}_f \in \mathbb{R}^{B \times 124 \times 64}$',
    color='#e8eff7', bold_title='Multi-Head Delay Cross-Attention')

# 4. Deep TPP Stream (x: 10.1 to 13.8, top)
box(10.1, 4.50, 3.7, 2.05,
    'Attentive Temporal Pyramid Pooling (TPP):\n' +
    r'$\mathbf{H}_e$ pooled over $[0, 3], (3, 7], (7, 10]$ s' + '\n' +
    r'$\mathbf{H}_f$ pooled over $[0, 4], (4, 8], (8, 12]$ s' + '\n' +
    'Attention-Weighted Multiscale Aggregation\n' +
    r'Deep Latent Token: $\mathbf{z}_{\mathrm{deep}} \in \mathbb{R}^{B \times 64}$',
    color='#e8eff7', bold_title='Attentive TPP Deep Stream')

# 5. Shallow Biophysical Stream (Bottom)
box(0.2, 0.35, 4.2, 2.4,
    'Sub-Band EEG Oscillatory Power:\n' +
    r'$\theta$ (4–8 Hz), $\alpha$ (8–13 Hz), $\beta$ (13–30 Hz) $\in \mathbb{R}^{B \times 90}$' + '\n\n' +
    'Delayed Capillary Optical Amplitude & Slope:\n' +
    r'Mean Perfusion ($t \geq 3.5$ s) & Gradient $\in \mathbb{R}^{B \times 144}$' + '\n\n' +
    r'Raw Biophysical Vector: $\mathbf{x}_{\mathrm{bio}} \in \mathbb{R}^{B \times 234}$',
    color='#fbf5ea', bold_title='Sub-Band & Vascular Slope Stream')

box(4.8, 0.35, 4.2, 2.4,
    'Low-Rank Bottleneck Dimension Reduction:\n' +
    r'Linear($234 \to 32$) $\to$ LayerNorm $\to$ GELU' + '\n' +
    r'Dropout($0.15$) $\to$ Linear($32 \to 64$)' + '\n' +
    r'Shallow Vector: $\mathbf{z}_{\mathrm{shallow}} \in \mathbb{R}^{B \times 64}$' + '\n' +
    'Bottleneck Parameters: 9,568',
    color='#fbf5ea', bold_title='Biophysical Feature Projection')

# 6. Gated Fusion & Readout (x: 9.4 to 13.8, bottom)
box(9.4, 0.35, 4.4, 3.85,
    'Entropy-Guided Feature-Wise Gating Network:\n' +
    r'$\mathbf{g}_b = \sigma(\mathcal{F}_g([\mathbf{z}_{\mathrm{deep}}; \mathbf{z}_{\mathrm{shallow}}; H(\hat{\mathbf{p}}_{\mathrm{deep}}); H(\hat{\mathbf{p}}_{\mathrm{shallow}})]))$' + '\n' +
    r'$\mathbf{g}_b \in (0, 1)^{64}$, MLP $130 \to 32 \to 64$' + '\n' +
    r'Stream DropPath Regularization ($p = 0.15$)' + '\n\n' +
    'Channel-Wise Convex Blending:\n' +
    r'$\mathbf{z}_{\mathrm{fused}} = \mathbf{g}_b \odot \mathbf{z}_{\mathrm{deep}} + (\mathbf{1} - \mathbf{g}_b) \odot \mathbf{z}_{\mathrm{shallow}} \in \mathbb{R}^{B \times 64}$' + '\n\n' +
    r'Linear Readout: $\boldsymbol{\ell} = \mathbf{W}_{\mathrm{out}} \mathbf{z}_{\mathrm{fused}} + \mathbf{b}_{\mathrm{out}} \in \mathbb{R}^{B \times 2}$' + '\n' +
    r'Total Trainable Parameters: 63,940 ($<65\mathrm{k}$)',
    color='#f2edf7', bold_title='Entropy-Guided Gated Fusion')

# Connections & Arrows
arrow([(2.4, 5.82), (2.8, 5.82)])
arrow([(2.4, 3.92), (2.8, 3.92)])

arrow([(5.4, 5.82), (5.58, 5.82), (5.8, 5.2)])
ax.text(5.50, 5.95, 'K, V', fontsize=8.2, fontweight='bold', color='#1a2d42')

arrow([(5.4, 3.92), (5.8, 3.92)])
ax.text(5.55, 4.08, 'Q', fontsize=8.2, fontweight='bold', color='#1a2d42')

arrow([(9.7, 5.50), (10.1, 5.50)])

arrow([(5.4, 6.25), (5.6, 6.75), (9.8, 6.75), (10.1, 6.15)])
ax.text(7.7, 6.85, r'EEG Tokens $\mathbf{H}_e$ to TPP', fontsize=8.2, ha='center', color='#334e68', fontweight='bold')

arrow([(0.8, 3.10), (0.8, 2.75)])
arrow([(1.8, 3.10), (1.8, 2.75)])
ax.text(0.8, 2.92, 'EEG', fontsize=7.2, color='#486581', ha='center', va='center', backgroundcolor='#ffffff')
ax.text(1.8, 2.92, 'fNIRS', fontsize=7.2, color='#486581', ha='center', va='center', backgroundcolor='#ffffff')

arrow([(4.4, 1.55), (4.8, 1.55)])

arrow([(9.0, 1.55), (9.4, 1.55)])
ax.text(9.2, 1.82, r'$\mathbf{z}_{\mathrm{shallow}}$', fontsize=8.5, ha='center', color='#1a2d42')

arrow([(11.95, 4.50), (11.95, 4.20)])
ax.text(12.18, 4.35, r'$\mathbf{z}_{\mathrm{deep}}$', fontsize=8.5, ha='left', color='#1a2d42')

save(fig, 'nvc_delayformer_computation')

# -------------------------------------------------------------------------
# Figure 2: Benchmark Comparison (Generous headroom, zero dot collision)
# -------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.5, 2.15))
names = list(bench['models'])
tick = ['EEG-\nCNN', 'fNIRS-\nCNN', 'Feature\nconcat.', 'Standard\nattention', 'NVC-\nDelayFormer']
for i, key in enumerate(names):
    r = bench['models'][key]
    a = np.asarray(r['fold_accs'])
    color = '#237c88' if i == 4 else '#667e97'
    jitter = np.linspace(-.15, .15, len(a))
    ax.scatter(i + jitter, a, s=5, c=color, alpha=.28, linewidths=0, zorder=1)
    m = r['mean_acc']
    low, high = r['ci95']
    ax.errorbar(i, m, yerr=[[m - low], [high - m]], fmt='o', ms=3.5, color=color, lw=1.1, capsize=2.5, zorder=3)
    ax.text(i, 96, f'{m:.2f}', ha='center', fontsize=6.8, color=color, fontweight='bold')

ax.set_xticks(range(5), tick, fontsize=6.8)
ax.set_ylabel('Held-out accuracy (%)', fontsize=7.5)
ax.set_ylim(28, 102)
ax.set_yticks([30, 50, 70, 90])
ax.tick_params(labelsize=6.8)
ax.axhline(50, color='#999999', ls='--', lw=.6, zorder=0)
ax.set_title('29 participants; mean and 95% CI', fontsize=7.8, pad=6)
fig.tight_layout(pad=.3)
save(fig, 'real_29sub_benchmark_comparison')

# -------------------------------------------------------------------------
# Figure: Delay Sensitivity Sweep
# -------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.5, 2.5))
keys = sorted(bench['delay_sweep'], key=float)
x = np.asarray(list(map(float, keys)))
arrays = [np.array(bench['delay_sweep'][k]['fold_accs']) for k in keys]
y = np.array([a.mean() for a in arrays])
ci = np.array([stats.t.ppf(.975, 28) * a.std(ddof=1) / np.sqrt(29) for a in arrays])
ax.errorbar(x, y, yerr=ci, fmt='o-', color='#237c88', lw=1, ms=3.5, capsize=3)
ax.axvline(5, color='#a87146', ls='--', lw=.8, label='Primary setting (5 s)')
ax.set_xlabel('Fixed inference delay (s)')
ax.set_ylabel('Held-out accuracy (%)')
ax.set_xticks([0, 2, 4, 5, 6, 8])
ax.set_ylim(70, 85)
ax.set_yticks([70, 75, 80, 85])
ax.legend(fontsize=6.5, loc='lower right')
ax.set_title('Fixed weights; 29 participants', fontsize=8)
fig.tight_layout(pad=.5)
save(fig, 'delay_sensitivity_curve')
print('Updated computation, benchmark labels, and delay sensitivity figures.')
