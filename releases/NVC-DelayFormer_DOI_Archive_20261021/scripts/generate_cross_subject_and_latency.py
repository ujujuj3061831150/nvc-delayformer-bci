"""Plot archived paired participant gains and GPU latency percentiles.

Each gain is the proposed model minus a control for the same participant,
after averaging that participant's three seeds. No experiments are rerun.
Latency intervals connect the median and P99; they are not confidence intervals.
"""
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter

from scripts.figure_support import setup_style, audit_layout, print_report, export_figure


def main():
    setup_style()
    multi = json.loads((ROOT / 'reports/multiseed_grand_benchmark_summary.json').read_text(encoding='utf-8'))
    engineering = json.loads((ROOT / 'reports/engineering_benchmarks_round3.json').read_text(encoding='utf-8'))
    proposed = np.asarray(multi['NVC-DelayFormer']['sub_means'], dtype=float)
    assert proposed.shape == (29,) and np.isfinite(proposed).all()
    comparisons = [('2D-EEGNet', 'Authentic 2D-EEGNet'),
                   ('Feature-Concat', 'Multi-View Hybrid CNN'),
                   ('Standard-Attention', 'Cross-Modal Transformer')]
    blue = '#0F4D92'
    grey = '#747D88'
    fig = plt.figure(figsize=(7.16, 2.65), dpi=300)
    left = fig.add_axes([0.195, 0.22, 0.285, 0.59])
    right = fig.add_axes([0.745, 0.22, 0.235, 0.59])
    rng = np.random.default_rng(42)
    summaries = []
    for row, (label, key) in enumerate(comparisons):
        control = np.asarray(multi['baselines'][key]['sub_means'], dtype=float)
        assert control.shape == proposed.shape and np.isfinite(control).all()
        gain = proposed - control
        mean = float(gain.mean())
        half = float(stats.t.ppf(0.975, len(gain)-1) * stats.sem(gain))
        left.scatter(gain, row + rng.uniform(-0.13, 0.13, len(gain)),
                     s=11, color=grey, alpha=0.55, linewidth=0, zorder=2)
        left.errorbar(mean, row, xerr=half, fmt='D', markersize=4.3,
                      color=blue, ecolor=blue, elinewidth=1.8, capsize=3, zorder=4)
        left.text(1.035, row, f'+{mean:.2f}', transform=left.get_yaxis_transform(),
                  va='center', ha='left', clip_on=False,
                  fontsize=8.0, color=blue, fontweight='bold')
        summaries.append({'control': label, 'n_participants':len(gain),
                          'mean_gain_pp':mean, 't_ci95_pp':[mean-half,mean+half],
                          'n_positive_participants':int(np.count_nonzero(gain > 0))})
    left.axvline(0, color='#999999', lw=.8, ls='--', zorder=1)
    left.set(xlim=(-12.5, 32.5), ylim=(2.5, -.5), yticks=range(3),
             yticklabels=[v[0] for v in comparisons], xticks=[-10, 0, 10, 20, 30])
    left.tick_params(axis='y', length=0, pad=5, labelsize=8.0)
    left.set_xlabel('Paired accuracy gain (pp)', fontsize=8, labelpad=4)
    left.set_title(r'$\bf{(a)}$ Cross-Subject Gains', loc='left', fontsize=9.1,
                   color='#1A2D42', y=1.17, pad=0)
    left.legend(handles=[Line2D([], [], marker='o', color=grey, ls='', markersize=3,
                                label='Participant'),
                         Line2D([], [], marker='D', color=blue, markersize=3,
                                label='Mean / 95% CI')],
                loc='lower left', bbox_to_anchor=(0, 1.005), ncol=2,
                fontsize=8, frameon=False, columnspacing=.8, handlelength=1,
                borderaxespad=0)

    order = ['fNIRS-CNN', 'EEG-CNN', 'Feature-Concat', 'Standard-Attention',
             'NVC-DelayFormer', 'ATCNet', 'EEG Conformer']
    for row, name in enumerate(order):
        data = engineering[name]
        med, p99 = data['median_ms'], data['p99_ms']
        assert 0 < med <= p99
        color = blue if name == 'NVC-DelayFormer' else grey
        right.plot([med, p99], [row, row], lw=1.6, color=color, zorder=2)
        right.scatter(med, row, marker='o', s=19, color=color, zorder=3)
        right.scatter(p99, row, marker='s', s=19, facecolors='white', edgecolors=color,
                      linewidths=1.0, zorder=3)
    right.set_xscale('log')
    right.set(xlim=(.28, 36), ylim=(6.6, -.6), yticks=range(7), yticklabels=order)
    right.xaxis.set_major_locator(FixedLocator([.5, 1, 5, 10, 30]))
    right.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
    right.tick_params(which='minor', bottom=False)
    right.tick_params(axis='y', length=0, pad=5, labelsize=8.0)
    for label in right.get_yticklabels():
        if label.get_text() == 'NVC-DelayFormer':
            label.set_color(blue)
            label.set_fontweight('bold')
    right.set_xlabel('GPU forward latency (ms; log scale)', fontsize=8, labelpad=4)
    right.set_title(r'$\bf{(b)}$ Forward Latency', loc='left', fontsize=9.1,
                    color='#1A2D42', y=1.17, pad=0)
    right.legend(handles=[Line2D([], [], marker='o', color=grey, ls='', markersize=3,
                                 label='Median'),
                          Line2D([], [], marker='s', markerfacecolor='white', color=grey,
                                 ls='', markersize=3, label='P99')],
                 loc='lower left', bbox_to_anchor=(0, 1.005), ncol=2,
                 fontsize=8, frameon=False, columnspacing=1, handlelength=1,
                 borderaxespad=0)

    issues = audit_layout(fig)
    print_report(issues)
    if issues:
        raise RuntimeError('Figure text extends outside the canvas.')
    for folder in [ROOT / 'manuscript/figures', ROOT / 'reports/figures']:
        export_figure(fig, folder / 'cross_subject_gain_and_latency',
                      formats=['pdf','svg','png'], dpi=300, grayscale_preview=True)
    audit_dir = ROOT / 'tmp/figure_selection_20261028'
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / 'paired_gain_plot_values.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    plt.close(fig)
    print('Saved cross_subject_gain_and_latency figure.')


if __name__ == '__main__':
    main()
