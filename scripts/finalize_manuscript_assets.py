"""Generate manuscript figures from the saved, reconciled records."""
from pathlib import Path
import json, shutil, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
destinations=[ROOT/'reports/figures',ROOT/'latex/figures',ROOT/'latex_cbm/figures']
for d in destinations: d.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'pdf.fonttype':42})
def save(fig,name):
    for d in destinations:
        fig.savefig(d/(name+'.png'),dpi=240,bbox_inches='tight')
        fig.savefig(d/(name+'.pdf'),bbox_inches='tight')
    plt.close(fig)

bench=json.loads((ROOT/'reports/real_29sub_benchmark_and_ablation_summary.json').read_text())
neg=json.loads((ROOT/'reports/negative_controls_rigorous_results.json').read_text())

# Computational schematic: every branch reflects the current forward path.
fig,ax=plt.subplots(figsize=(13,6.6))
ax.set_xlim(0,13); ax.set_ylim(0,6.6); ax.axis('off')
def box(x,y,w,h,label,color='#edf4fa'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08,rounding_size=0.08',facecolor=color,edgecolor='#44617a',linewidth=1))
    ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10)
def arrow(p,q,label=None):
    ax.annotate('',xy=q,xytext=p,arrowprops={'arrowstyle':'->','color':'#44617a','lw':1.2})
    if label: ax.text((p[0]+q[0])/2,(p[1]+q[1])/2+.1,label,fontsize=8,ha='center')
box(.2,5.2,2.4,1,'EEG\n(B, 30, 1000)\n100 Hz / 10 s')
box(.2,3.2,2.4,1,'HbO / HbR inputs\n(B, 72, 124)\n124/12 Hz / 12 s','#edf6f1')
box(3.2,5.2,2.6,1,'EEG encoder\nConv - pool(4) - conv\n(B, 250, 64)')
box(3.2,3.2,2.6,1,'fNIRS encoder\nSpatial / temporal conv\n(B, 124, 64)','#edf6f1')
arrow((2.68,5.7),(3.1,5.7)); arrow((2.68,3.7),(3.1,3.7))
box(6.5,4.2,2.8,1.8,'Cross-attention\n4 heads, head dim 16\nFixed delay: 5.0 s\nTimestamp mask + gating\nFused: (B, 124, 64)')
arrow((5.88,5.7),(6.4,5.4),'K, V'); arrow((5.88,3.7),(6.4,4.6),'Q')
box(10,4.7,2.6,1.3,'Pooled latent features\nEEG + fused: (B, 128)\nMLP logits: (B, 2)')
arrow((9.4,5.1),(9.9,5.1))
box(3.2,.4,3.1,1.7,'Temporal feature weights\nEEG log energy +\nhemodynamic proxy\nNormalized direct features\n(B, 102)','#f8f2e8')
arrow((1.4,3.1),(3.1,1.5)); arrow((1.4,5.1),(3.1,2.0))
box(6.9,1.0,2.8,1.6,'Reconstruction branch\nFused + proxy: (B, 100, 124)\nOutput / target: (B, 36, 124)\nSummary gates direct features','#edf6f1')
arrow((7.8,4.1),(8.3,2.7)); arrow((6.4,1.7),(6.8,1.7))
box(10,1.0,2.6,1.6,'Direct linear readout\n(B, 102) to (B, 2)\nFinal logits:\n0.02 MLP + 0.98 direct','#f8f2e8')
arrow((9.8,1.8),(9.9,1.8)); arrow((11.3,4.6),(11.3,2.7))
ax.text(.2,6.45,'NVC-DelayFormer: recorded computation and dimensions',fontsize=15,fontweight='bold')
save(fig,'nvc_delayformer_computation')

names=list(bench['models']); values=[bench['models'][k] for k in names]
fig,ax=plt.subplots(figsize=(7.2,4.5))
means=np.array([r['mean_acc'] for r in values]); ci=np.array([r['ci95'] for r in values])
ax.bar(range(5),means,yerr=np.vstack([means-ci[:,0],ci[:,1]-means]),capsize=4,
       color=['#8497b0']*4+['#237c88'],edgecolor='white')
ax.set_xticks(range(5),['EEGNet','fNIRS-CNN','Feature\nconcat.','Standard\nattention','NVC\nDelayFormer'])
ax.set_ylim(40,82); ax.set_ylabel('Accuracy (%)'); ax.axhline(50,color='#888',ls='--',lw=.8)
for i,m in enumerate(means): ax.text(i,ci[i,1]+1,f'{m:.2f}%',ha='center',fontsize=9)
ax.set_title('Subject-held-out benchmark: mean and 95% t interval')
fig.tight_layout();save(fig,'real_29sub_benchmark_comparison')

sweep=bench['delay_sweep']; keys=sorted(sweep,key=float)
fig,(ax,ax2)=plt.subplots(1,2,figsize=(9,3.6))
ys=np.array([sweep[k]['mean'] for k in keys]); se=np.array([sweep[k]['se'] for k in keys])
ax.errorbar(list(map(float,keys)),ys,yerr=se,fmt='o-',color='#237c88',capsize=3)
ax.set_xlabel('Fixed inference delay (s)');ax.set_ylabel('Accuracy (%)')
ax.set_title('A  Fixed-weight sweep (mean ± SE)',fontsize=10)
for k,v in bench['convergence_trajectories'].items():ax2.plot(range(len(v)),v,label=f'Initial {k} s')
ax2.set_xlabel('Optimization epoch');ax2.set_ylabel('Delay parameter (s)')
ax2.set_title('B  Recorded optimization trajectories',fontsize=10);ax2.legend(fontsize=8)
fig.tight_layout();save(fig,'delay_sensitivity_curve')

h=neg['sub05_training_history'];fig,(ax,ax2)=plt.subplots(1,2,figsize=(8,3.4))
ax.plot(h['epoch'],h['train_loss_ce'],label='Training CE');ax.plot(h['epoch'],h['val_loss_ce'],label='Validation CE')
ax.set_xlabel('Epoch');ax.set_ylabel('Cross-entropy');ax.legend(fontsize=8);ax.set_title('A  Recorded classification loss')
ax2.plot(h['epoch'],h['train_loss_recon'],color='#237c88',label='Training proxy MSE');axt=ax2.twinx()
axt.plot(h['epoch'],h['val_acc'],ls='--',color='#9f6346',label='Validation accuracy')
ax2.set_xlabel('Epoch');ax2.set_ylabel('Proxy reconstruction MSE');axt.set_ylabel('Validation accuracy (%)')
ax2.set_title('B  Reconstruction and validation');ax2.legend(loc='upper left',fontsize=7);axt.legend(loc='lower right',fontsize=7)
fig.tight_layout();save(fig,'training_curves_sub05')

caption=r'Current model computation. EEG and HbO/HbR encoder outputs have 250 and 124 tokens, respectively. Four-head timestamp-constrained attention feeds the latent readout and reconstruction branch. Temporally weighted raw features form the direct readout; its logits are combined with latent logits using coefficients 0.98 and 0.02.'
for name in ['latex/main.tex','latex_cbm/main_cbm.tex']:
    path=ROOT/name; text=path.read_text(encoding='utf-8')
    text=text.replace('figures/nvc_delayformer_architecture_schematic.png','figures/nvc_delayformer_computation.pdf')
    text=re.sub(r'\\caption\{.*?\}\n\\label\{fig:architecture\}',lambda _: '\\caption{'+caption+'}\n\\label{fig:architecture}',text,count=1,flags=re.S)
    # Above match begins at the first caption; architecture is the first figure.
    text=text.replace('keys and values $\\mathbf{K}, \\mathbf{V} \\in \\mathbb{R}^{B \\times 250 \\times d_k}$ ($d_k=64$)', 'keys and values before splitting into heads, each of shape $(B,250,64)$')
    text=text.replace('Keys and Values $\\mathbf{K}, \\mathbf{V} \\in \\mathbb{R}^{B \\times 250 \\times d_k}$ ($d_k=64$)', 'keys and values before splitting into heads, each of shape $(B,250,64)$')
    text=text.replace('Queries $\\mathbf{Q} \\in \\mathbb{R}^{B \\times 124 \\times d_k}$', 'queries before splitting into heads, of shape $(B,124,64)$')
    text=text.replace('channels representing 36 optode pairs $\\times$ 2 wavelengths','channels representing 36 HbO and 36 HbR traces')
    text=text.replace('spontaneous convergence from non-5s initializations','recorded optimization trajectories from three initial values')
    text=text.replace('demonstrating an inverted U-shaped resonance plateau peaking between 5.0 and 6.0\\,s', 'with the highest sampled accuracy at 6.0\\,s; Panel A error bars show SE and Panel B shows recorded optimization trajectories')
    text=text.replace('showing concurrent minimization of classification cross-entropy loss and auxiliary reconstruction MSE loss alongside validation accuracy stability', 'showing the recorded training and validation losses, proxy reconstruction MSE, and validation accuracy')
    text=text.replace('showing mean accuracy, Cohen\'s kappa, and statistical significance', 'showing mean accuracy and 95\\% Student-$t$ confidence intervals')
    text=text.replace('a rich, non-degenerate', 'a measured')
    text=text.replace('with a learnable Gaussian kernel reflecting the canonical impulse response of neurovascular coupling', 'with a Gaussian lag preference')
    text=text.replace('NVC-DelayFormer embeds physiological laws directly into the model\'s inductive bias, bridging pure data-driven deep learning with biophysical neural engineering', 'NVC-DelayFormer specifies a temporal inductive bias for cross-modal fusion')
    text=text.replace('standard cross-attention assumes temporal permutability unless constrained by positional encodings', 'cross-attention computes affinities between encoded time samples')
    text=text.replace('which violates physical causality and leads to severe cross-subject over-fitting', 'unless its token-pair access is constrained by timestamps')
    text=text.replace('standard cross-attention lacks any concept of biological causality', 'standard cross-attention has no explicit physiological lag constraint')
    # The HRF convolution is motivation, not an executed or fitted model.
    text=re.sub(r'\\begin\{equation\}\nh_\{\\text\{canonical\}\}.*?\\end\{equation\}\nwhere .*?Mayer waves\.', lambda _: r'The causal kernel $h_{\mathrm{canonical}}(u)$ is zero for $u<0$ and represents the delayed hemodynamic response; $\eta_{\mathrm{sys}}$ collects other optical-signal contributions. This convolution motivates the lag preference and is not fitted as part of the classifier.',text,flags=re.S)
    # Replace unsupported mutual-information maximum with an explicit modeling choice.
    text=re.sub(r'\\item \\textbf\{Delayed Resonance\}:.*?(?=\n\\end\{enumerate\})',lambda _: r'\item \textbf{Delay Preference}: The main benchmark sets the Gaussian center to $\tau=5.0$\,s; component and inference-time experiments report its measured effect.',text,flags=re.S)
    text=text.replace('a spatial $1 \\times 1$ convolution projects optode pairs', 'a spatial $1 \\times 1$ convolution projects the 72 input channels')
    text=text.replace('with optode separation $d = 3.0$\\,cm', 'with the recorded computational optode-distance value $d = 30.0$\\,mm')
    text=text.replace('$d = 3.0$\\,cm is the inter-optode distance', '$d = 30.0$\\,mm is the optode-distance value used by the inversion routine')
    text=text.replace('($\\text{mM}^{-1}\\text{cm}^{-1}$)', '(in the coefficient scale used by the inversion routine)')
    text=text.replace(r'\end{bmatrix}\,\text{mM}^{-1}\text{cm}^{-1}',r'\end{bmatrix}')
    text=text.replace('The molar extinction coefficient matrix', 'The numerical extinction coefficient matrix')
    text=text.replace('full inversion operator $\\mathbf{M}', 'full inversion operator $\\mathbf{R}')
    # Distinguish MBLL inversion from the attention mask.
    start=text.find('\\subsection{Modified Beer-Lambert')
    end=text.find('\\subsection{',start+12)
    if start>=0 and end>=0:
        text=text[:start]+text[start:end].replace(r'\mathbf{M}',r'\mathbf{R}').replace(r'\mathbf{D}',r'\mathbf{D}_{\mathrm{DPF}}')+text[end:]
    text=text.replace('followed by temporal-envelope scaling.', 'followed by row-envelope scaling $0.2+0.8\\,(124)\\,w_{\\mathrm{nirs},i}$.')
    path.write_text(text,encoding='utf-8')
print('Saved source-derived figures and synchronized figure assets.')
