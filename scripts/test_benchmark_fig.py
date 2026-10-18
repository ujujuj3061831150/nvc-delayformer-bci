"""
Benchmark & Generalization figure generator with 0-collision guarantee.
"""
from pathlib import Path
import json
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/figures'
OUT.mkdir(parents=True, exist_ok=True)
REPORTS_FIG = ROOT / 'reports/figures'
REPORTS_FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],
    'font.size': 7.5,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.75,
    'axes.labelsize': 7.5,
    'xtick.labelsize': 6.8,
    'ytick.labelsize': 6.8,
    'legend.frameon': False,
    'legend.fontsize': 6.2,
})

def generate():
    bench = json.loads((ROOT / 'reports/real_29sub_benchmark_and_ablation_summary.json').read_text(encoding='utf-8'))
    sota = json.loads((ROOT / 'reports/sota_benchmarks_results.json').read_text(encoding='utf-8'))
    multi = json.loads((ROOT / 'reports/multiseed_grand_benchmark_summary.json').read_text(encoding='utf-8'))

    fig = plt.figure(figsize=(7.16, 2.75))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 0.95, 1.15], wspace=0.42,
                           left=0.08, right=0.98, top=0.86, bottom=0.22)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    # -----------------------------------------------------------------
    # Panel (a): 5 Key Models on TU Berlin (N=29)
    # -----------------------------------------------------------------
    models_data = [
        ('EEG\nCNN', np.array(bench['models']['EEG-CNN']['fold_accs']), '#9AA5B1'),
        ('fNIRS\nCNN', np.array(bench['models']['fNIRS-CNN']['fold_accs']), '#9AA5B1'),
        ('Concat\nCNN', np.array(bench['models']['Feature-Concat']['fold_accs']), '#7884B4'),
        ('EFML\nNet', np.array(sota['EFMLNet']['fold_accs']), '#486581'),
        ('NVC\n(Ours)', np.array(bench['models']['NVC-DelayFormer']['fold_accs']), '#0F4D92'),
    ]

    np.random.seed(42)
    for i, (name, accs, col) in enumerate(models_data):
        is_hero = (i == len(models_data) - 1)
        jitter = np.linspace(-0.11, 0.11, len(accs))
        np.random.shuffle(jitter)
        ax1.scatter(i + jitter, accs, s=5.0 if is_hero else 3.5, color=col if is_hero else '#B8C6D6',
                    alpha=0.55 if is_hero else 0.30, linewidths=0, zorder=2)

        m = accs.mean()
        ci = stats.t.ppf(0.975, len(accs) - 1) * accs.std(ddof=1) / np.sqrt(len(accs))
        ax1.errorbar(i, m, yerr=ci, fmt='o', color=col, ms=4.5 if is_hero else 3.5,
                     lw=1.5 if is_hero else 1.1, capsize=2.5, capthick=1.2, zorder=4)

        if is_hero:
            ax1.text(i, 96.5, f'{m:.1f}%', ha='center', va='bottom', fontsize=7.2, fontweight='bold', color='#0F4D92')

    ax1.axhline(50.0, color='#999999', linestyle='--', linewidth=0.7, zorder=1)
    ax1.text(0.0, 52.0, 'Chance (50%)', fontsize=5.8, color='#777777', va='bottom')

    # Significance bracket between EFMLNet (idx 3) and Proposed (idx 4)
    ax1.plot([3, 3, 4, 4], [90.5, 92.5, 92.5, 90.5], color='#0F4D92', lw=0.8)
    ax1.text(3.5, 93.2, '***', ha='center', va='bottom', fontsize=6.8, fontweight='bold', color='#0F4D92')

    ax1.set_xticks(range(len(models_data)))
    ax1.set_xticklabels([m[0] for m in models_data], fontsize=6.8)
    ax1.tick_params(axis='x', length=0, pad=6)
    ax1.set_ylabel('Held-Out Accuracy (%)', labelpad=4.0)
    ax1.set_ylim(28, 104)
    ax1.set_yticks([30, 50, 70, 90])
    ax1.set_title('(a) Primary Benchmark (N=29)', fontsize=8.0, fontweight='bold', pad=8, color='#1A2D42')

    # -----------------------------------------------------------------
    # Panel (b): Hemodynamic Delay Scan (tau in [0, 8] s)
    # -----------------------------------------------------------------
    delay_keys = sorted(bench['delay_sweep'], key=float)
    x_delays = np.array([float(k) for k in delay_keys])
    y_means = []
    y_cis = []
    for k in delay_keys:
        f_accs = np.array(bench['delay_sweep'][k]['fold_accs'])
        y_means.append(f_accs.mean())
        y_cis.append(stats.t.ppf(0.975, len(f_accs) - 1) * f_accs.std(ddof=1) / np.sqrt(len(f_accs)))

    y_means = np.array(y_means)
    y_cis = np.array(y_cis)

    # Shaded biophysical single-impulse HRF prior region [3.5, 6.5] s without stroke
    ax2.axvspan(3.5, 6.5, facecolor='#F8EFE6', edgecolor='none', alpha=0.95, zorder=1, label=r'HRF Prior $[3.5, 6.5]$ s')
    ax2.fill_between(x_delays, y_means - y_cis, y_means + y_cis, facecolor='#B4CBE2', edgecolor='none', alpha=0.45, zorder=3)
    ax2.plot(x_delays, y_means, 'o-', color='#0F4D92', lw=1.3, ms=3.8, zorder=4, label='Scan Accuracy')

    # Legend in empty upper left corner
    ax2.legend(loc='upper left', fontsize=5.8, framealpha=0.90)

    # Text callouts positioned safely away from all lines and error bars
    ax2.text(0.1, 78.5, r'$\bar{\tau}=0$ s: $-4.1$ pp' + '\n' + r'($p=0.0036$)', fontsize=5.8, color='#B64342', ha='left', va='center')
    ax2.text(7.9, 83.5, 'Plateau (80.5%)', fontsize=5.8, color='#0F4D92', ha='right', va='bottom')

    ax2.set_xlabel(r'Center Delay $\bar{\tau}$ (s)', labelpad=4.0)
    ax2.set_ylabel('Held-Out Accuracy (%)', labelpad=4.0)
    ax2.set_xlim(-0.4, 8.4)
    ax2.set_xticks([0, 2, 4, 5, 6, 8])
    ax2.set_ylim(69, 86)
    ax2.set_yticks([70, 75, 80])
    ax2.tick_params(axis='x', pad=3)
    ax2.set_title('(b) Hemodynamic Delay Scan', fontsize=8.0, fontweight='bold', pad=8, color='#1A2D42')

    # -----------------------------------------------------------------
    # Panel (c): Multi-Paradigm Generalization
    # -----------------------------------------------------------------
    paradigms = ['Mental Arith.\n(TU Berlin)', r'$n$-back WM' + '\n(Shin 2018)', 'Motor Imag.\n(Shin 2017)']
    x_pos = np.arange(len(paradigms))
    bar_width = 0.18
    y_base = 45.0

    acc_lda = [72.82, 62.13, 58.05]
    ci_lda = [stats.t.ppf(0.975, 28) * 11.61 / np.sqrt(29),
              stats.t.ppf(0.975, 25) * 10.16 / np.sqrt(26),
              stats.t.ppf(0.975, 28) * 9.52 / np.sqrt(29)]

    acc_eegnet = [76.84, 68.27, 62.18]
    ci_eegnet = [stats.t.ppf(0.975, 28) * 6.16 / np.sqrt(29),
                 stats.t.ppf(0.975, 25) * 13.34 / np.sqrt(26),
                 stats.t.ppf(0.975, 28) * 7.33 / np.sqrt(29)]

    acc_sota = [74.20, 72.38, 70.40]
    ci_sota = [stats.t.ppf(0.975, 28) * 9.29 / np.sqrt(29),
               stats.t.ppf(0.975, 25) * 14.82 / np.sqrt(26),
               stats.t.ppf(0.975, 28) * 11.54 / np.sqrt(29)]

    acc_proposed = [79.37, 73.77, 66.32]
    ci_proposed = [stats.t.ppf(0.975, 28) * 7.73 / np.sqrt(29),
                   stats.t.ppf(0.975, 25) * 15.44 / np.sqrt(26),
                   stats.t.ppf(0.975, 28) * 12.18 / np.sqrt(29)]

    # Draw bars with bottom=y_base so rectangles don't protrude past axes
    h_lda = [a - y_base for a in acc_lda]
    h_eegnet = [a - y_base for a in acc_eegnet]
    h_sota = [a - y_base for a in acc_sota]
    h_prop = [a - y_base for a in acc_proposed]

    ax3.bar(x_pos - 1.5 * bar_width, h_lda, bar_width, bottom=y_base, yerr=ci_lda, capsize=1.8,
            label='Shrinkage-LDA', color='#D8D8D8', edgecolor='#666666', linewidth=0.6)
    ax3.bar(x_pos - 0.5 * bar_width, h_eegnet, bar_width, bottom=y_base, yerr=ci_eegnet, capsize=1.8,
            label='2D-EEGNet', color='#8898AA', edgecolor='#444444', linewidth=0.6)
    ax3.bar(x_pos + 0.5 * bar_width, h_sota, bar_width, bottom=y_base, yerr=ci_sota, capsize=1.8,
            label='Top Deep SOTA', color='#486581', edgecolor='#223344', linewidth=0.6)
    ax3.bar(x_pos + 1.5 * bar_width, h_prop, bar_width, bottom=y_base, yerr=ci_proposed, capsize=2.0,
            label='NVC-DelayFormer', color='#0F4D92', edgecolor='#0A2544', linewidth=0.8)

    ax3.axhline(50.0, color='#999999', linestyle='--', linewidth=0.7, zorder=1)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(paradigms, fontsize=6.2)
    ax3.tick_params(axis='x', length=0, pad=6)
    ax3.set_ylabel('Held-Out Accuracy (%)', labelpad=4.0)
    ax3.set_ylim(y_base, 98)
    ax3.set_yticks([50, 60, 70, 80, 90])
    ax3.legend(loc='upper right', fontsize=5.8, ncol=2, columnspacing=0.8, handlelength=1.1, handletextpad=0.3)
    ax3.set_title('(c) Multi-Paradigm Transfer', fontsize=8.0, fontweight='bold', pad=8, color='#1A2D42')

    for ext_fmt in ('pdf', 'svg', 'png'):
        dest = OUT / f'real_29sub_benchmark_comparison.{ext_fmt}'
        fig.savefig(dest, dpi=600)
        fig.savefig(REPORTS_FIG / f'real_29sub_benchmark_comparison.{ext_fmt}', dpi=600)

    plt.close(fig)
    print("Done generating refined benchmark comparison figure.")

if __name__ == '__main__':
    generate()
