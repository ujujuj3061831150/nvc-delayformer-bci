"""Portable plotting utilities for the manuscript figure scripts."""
from pathlib import Path
import matplotlib.pyplot as plt


def setup_style(journal='ieee', lang='en', constrained_layout=False):
    plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
                         'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8.6,
                         'xtick.labelsize': 8, 'ytick.labelsize': 8,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.linewidth': .7, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'svg.fonttype': 'none', 'figure.constrained_layout.use': constrained_layout})


def audit_layout(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    issues = []
    texts = list(fig.texts)
    for ax in fig.axes:
        texts.extend([ax.title, ax._left_title, ax._right_title, ax.xaxis.label,
                      ax.yaxis.label, *ax.texts, *ax.get_xticklabels(), *ax.get_yticklabels()])
    legends = list(fig.legends) + [ax.get_legend() for ax in fig.axes if ax.get_legend() is not None]
    for legend in legends:
        texts.extend(legend.get_texts())
    for text in texts:
        if not text.get_visible() or not text.get_text():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < bounds.x0 - 1 or box.y0 < bounds.y0 - 1 or box.x1 > bounds.x1 + 1 or box.y1 > bounds.y1 + 1:
            issues.append(f'Text outside figure: {text.get_text()}')
    return issues


def print_report(issues):
    print('Layout bounds: PASS' if not issues else '\n'.join(issues))


def export_figure(fig, basename, formats=('pdf', 'png'), dpi=300, grayscale_preview=False, **kwargs):
    from PIL import Image, ImageOps
    base = Path(basename)
    base.parent.mkdir(parents=True, exist_ok=True)
    for suffix in formats:
        fig.savefig(base.with_suffix('.' + suffix), dpi=dpi, facecolor='white')
    if grayscale_preview:
        png = base.with_suffix('.png')
        if not png.exists():
            fig.savefig(png, dpi=dpi, facecolor='white')
        with Image.open(png) as img:
            ImageOps.grayscale(img).save(base.parent / (base.name + '_grayscale.png'))
