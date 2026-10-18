"""Finalize existing manuscript evidence without retraining or changing inference."""
from pathlib import Path
import json, shutil, re, hashlib
import numpy as np
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / 'reports/archive/final_revision_20261013'
BACKUP.mkdir(parents=True, exist_ok=True)
FILES = ['latex/main.tex', 'latex_cbm/main_cbm.tex',
         'reports/negative_controls_rigorous_results.json',
         'reports/negative_controls_fold_table.md',
         'reports/real_experimental_verification_and_manuscript_audit_report.md',
         'scripts/run_real_negative_controls_and_sub05_curves.py']
for name in FILES:
    target = BACKUP / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(ROOT / name, target)

source = BACKUP / 'reports/negative_controls_rigorous_results.json'
data = json.loads(source.read_text(encoding='utf-8'))
old_name = 'Streaming Causal Filtering'
new_name = 'Additional Causal EEG Smoothing'
data['controls'][new_name] = data['controls'].pop(old_name)

def recover(record, evaluations):
    # At 60 trials (or 60*10 pooled permutation trials), rounding to 0.01%
    # uniquely identifies the integer correct count. Never invent per-run predictions.
    rounded = np.asarray(record['fold_accs'], dtype=np.float64)
    denominator = 60 * evaluations
    counts = np.rint(rounded * denominator / 100).astype(int)
    exact = counts / denominator * 100
    assert np.max(np.abs(exact - rounded)) <= .00500001
    record['fold_correct_counts'] = counts.tolist()
    record['trials_per_subject'] = 60
    record['evaluations_per_subject'] = evaluations
    record['fold_accs'] = exact.tolist()
    record['mean_acc'] = float(exact.mean())
    record['std_acc'] = float(exact.std(ddof=1))
    record['se_acc'] = float(stats.sem(exact))
    record['ci95'] = list(stats.t.interval(.95, 28, loc=exact.mean(), scale=stats.sem(exact)))
    return exact

full = recover(data['full_model'], 1)
for name, row in data['controls'].items():
    values = recover(row, 10 if 'Permutation' in name else 1)
    # Compare exact count proportions; round arithmetic differences to resolve
    # equal rational differences consistently in SciPy ranks.
    diff = np.round(full - values, 10)
    tt = stats.ttest_1samp(diff, 0, alternative='two-sided')
    ww = stats.wilcoxon(diff, zero_method='wilcox', correction=False,
                        alternative='two-sided', method='approx')
    row.update(delta_mean=float(diff.mean()), delta_std=float(diff.std(ddof=1)),
               delta_se=float(stats.sem(diff)), t_statistic=float(tt.statistic),
               df=28, t_test_p=float(tt.pvalue), wilcoxon_stat=float(ww.statistic),
               wilcoxon_p=float(ww.pvalue))
q = stats.false_discovery_control([r['wilcoxon_p'] for r in data['controls'].values()], method='bh')
for row, value in zip(data['controls'].values(), q):
    row['fdr_q'] = float(value)
data['statistics_protocol'] = {
    'unit': 'subject', 'subjects': 29, 'standard_deviation_ddof': 1,
    'confidence_interval': 'two-sided Student t, df=28',
    'difference': 'full accuracy minus perturbed accuracy, percentage points',
    'difference_round_decimals': 10, 't_test': 'two-sided one-sample t on paired differences',
    'wilcoxon': {'alternative': 'two-sided', 'zero_method': 'wilcox',
                 'method': 'approx', 'continuity_correction': False},
    'fdr': 'Benjamini-Hochberg over the four perturbation Wilcoxon tests',
    'scipy_version': scipy.__version__,
    'recovery': 'Exact count proportions inferred from previously rounded fold accuracies and known 60-trial/10-permutation denominators; original record archived. Individual permutation predictions were not recovered.',
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
}
data['description'] = '30-channel subject-held-out perturbation experiments; causal smoothing is added after offline preprocessing'
(ROOT / 'reports/negative_controls_rigorous_results.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

rows = ['# Subject-level perturbation results (29 subjects)', '',
        'Changes are control minus full-model accuracy, in percentage points (pp).', '',
        '| Subject | Full | Within-class | Across-class | Circular roll 5 s | Added EEG smoothing |',
        '|---|---:|---:|---:|---:|---:|']
controls = list(data['controls'].values())
for i in range(29):
    rows.append('| Sub-%02d | '%(i+1) + ' | '.join(f'{v:.2f}%' for v in [full[i]] + [r['fold_accs'][i] for r in controls]) + ' |')
rows += ['', '| Condition | Mean ± sample SD | Change (pp) | t p | Wilcoxon p | BH q |',
         '|---|---:|---:|---:|---:|---:|']
for name, r in data['controls'].items():
    rows.append(f"| {name} | {r['mean_acc']:.2f}% ± {r['std_acc']:.2f}% | {-r['delta_mean']:+.2f} | {r['t_test_p']:.6g} | {r['wilcoxon_p']:.6g} | {r['fdr_q']:.6g} |")
rows += ['', 'The JSON retains full-precision count proportions and the statistical protocol. Fold percentages in this table are display-only rounding.',
         'Causal smoothing uses alpha=0.85 on offline-preprocessed EEG; fNIRS is unchanged. It is an input perturbation, not a replacement of the offline preprocessing pipeline.',
         'For a 1,000-sample epoch, +500 and -500 circular shifts are identical; one unique perturbation is reported.',
         'The archived JSON contains the previous rounded records and pre-reconciliation statistics.']
(ROOT / 'reports/negative_controls_fold_table.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')

roll = data['controls']['Temporal Phase Roll (±5s)']
within = data['controls']['Within-Class Permutation']
across = data['controls']['Across-Class Permutation']
smooth = data['controls'][new_name]
def ptex(value):
    if value >= .001:
        return f'{value:.4f}'
    coefficient, power = f'{value:.2e}'.split('e')
    return rf'{coefficient} \times 10^{{{int(power)}}}'

title = 'Physiology-Guided Temporal Fusion for Subject-Held-Out EEG--fNIRS Classification'
abstract = r'''Hybrid electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) provide complementary measurements of electrical and hemodynamic activity. We present NVC-DelayFormer, a temporal fusion model combining convolutional encoders, a Gaussian delay prior, a timestamp-based cross-attention mask, and direct and latent classification readouts. The primary benchmark uses a fixed delay of 5.0\,s and an auxiliary reconstruction loss. On mental arithmetic versus rest in the TU Berlin dataset, 29 subject-held-out folds use 23 training, 5 validation, and 1 test subject each. Across 1,740 test trials, accuracy is 66.44\% $\pm$ 10.85\% (between-subject sample SD; 95\% CI: 62.31\%, 70.57\%), Macro F1 is 65.13\%, and Cohen's $\kappa=0.3287$. Baseline accuracies are 59.02\% for EEGNet, 55.06\% for fNIRS-CNN, 59.48\% for feature concatenation, and 56.49\% for standard cross-attention; all four paired Wilcoxon comparisons have Benjamini--Hochberg $q<0.01$. A 5\,s circular EEG shift reduces accuracy to 59.83\%, a change of $-6.61$ percentage points (paired $t$-test $p=PTROLL$). The independently trained zero-delay model reaches 66.61\% (Wilcoxon $p=0.9636$ versus the full model). The model has 92,293 trainable parameters and 19.98\,M profiled MACs. Batch-one GPU forward latency has median 3.24\,ms, mean 3.62\,ms, and P99 5.89\,ms. These measurements characterize subject-held-out classification, temporal perturbation sensitivity, and forward execution cost.'''.replace('PTROLL', ptex(roll['t_test_p']))

controls_tex = r'''\section{Temporal Perturbation Experiments}
We evaluated the validation-selected full model on four test-input perturbations across 29 held-out subjects. The statistical unit is the subject. Changes below are control minus full-model accuracy in percentage points (pp). Within-class and across-class permutation results average ten permutations per subject.
\begin{enumerate}
\item \textbf{Circular EEG shift}: A 500-sample circular shift of the 1,000-sample EEG epoch preserves its discrete Fourier magnitude while changing sample order relative to fNIRS. Positive and negative 500-sample shifts produce the same sequence, so this is one unique 5\,s perturbation. Accuracy is 59.83\% $\pm$ 10.12\%, a change of $-6.61$\,pp (paired $t(28)=TROLL$, $p=PTROLL$; Wilcoxon $W=WROLL$, $p=PWROLL$, BH $q=QROLL$).
\item \textbf{Within-class permutation}: EEG trials are reassigned within the same held-out subject and class while fNIRS and test labels stay fixed. Accuracy is 66.57\% $\pm$ 9.84\%, a change of $+0.13$\,pp ($t(28)=TWITH$, $p=PTWITH$; Wilcoxon $p=PWWITH$).
\item \textbf{Across-class permutation}: EEG trials are reassigned across all trials of the held-out subject. Accuracy is 56.84\% $\pm$ 5.78\%, a change of $-9.60$\,pp ($t(28)=TACROSS$, $p=PTACROSS$; Wilcoxon $p=PWACROSS$).
\item \textbf{Additional causal EEG smoothing}: After the standard offline preprocessing, test EEG is transformed by $\widetilde{x}_0=x_0$ and $\widetilde{x}_t=0.85\widetilde{x}_{t-1}+0.15x_t$; fNIRS is unchanged. Accuracy is 64.43\% $\pm$ 11.08\%, a change of $-2.01$\,pp ($t(28)=TSMOOTH$, $p=PTSMOOTH$; Wilcoxon $p=PWSMOOTH$). This experiment measures sensitivity to an additional causal smoothing operation.
\end{enumerate}
For these four perturbations, two-sided Wilcoxon tests use the normal approximation, discard zero differences, apply tie correction, and omit continuity correction. Paired differences are rounded to ten decimal places to make equivalent count proportions receive identical ranks. Benjamini--Hochberg correction is applied to the four Wilcoxon comparisons. Full-precision subject-level proportions and count denominators are retained in the accompanying results file.
'''
for label, record in [('ROLL', roll), ('WITH', within), ('ACROSS', across), ('SMOOTH', smooth)]:
    for prefix, value in [('PW', ptex(record['wilcoxon_p'])), ('PT', ptex(record['t_test_p'])),
                          ('Q', ptex(record['fdr_q'])), ('W', f"{record['wilcoxon_stat']:.1f}"),
                          ('T', f"{record['t_statistic']:.4f}")]:
        controls_tex = controls_tex.replace(prefix+label, value)

discussion = r'''\section{Discussion}
The full model improves subject-held-out classification relative to all four benchmark baselines. Its output combines the latent MLP with a direct readout of temporally weighted features. Component ablations change accuracy by $-0.80$\,pp without the delay prior, $-0.29$\,pp without the mask, and $-1.15$\,pp without reconstruction loss; none of these Wilcoxon comparisons is significant at $p<0.05$. The zero-delay model reaches 66.61\% versus 66.44\% for the fixed 5\,s model ($p=0.9636$). The measured baseline improvement therefore applies to the complete architecture.

The 5\,s circular shift lowers full-model accuracy by 6.61\,pp. Across-class reassignment lowers it by 9.60\,pp, whereas within-class reassignment changes it by $+0.13$\,pp. These observations describe sensitivity to temporal order and class-compatible cross-modal inputs. Systemic-noise removal and physiological directionality were not measured by these comparisons.

The reconstructor is supervised to reproduce a derivative-based hemodynamic proxy and receives both fused features and the proxy as input. Its trajectory correlation changes from 0.8912 to 0.0012 when reconstruction supervision is removed. This measurement concerns the supervised reconstruction output; the associated classification comparison has Wilcoxon $p=0.3155$.

\subsection{Forward Execution Measurements}
The recorded environment uses Windows, Python 3.11.9, PyTorch 2.11.0+cu128, and an NVIDIA GeForce RTX 4060 Laptop GPU. Inputs are resident on the tested device, with EEG shape $(1,30,1000)$ and fNIRS shape $(1,72,124)$. Evaluation-mode forward calls run under \texttt{no\_grad}, with 1,000 warm-up calls and 5,000 timed calls; GPU measurements synchronize before and after each call. GPU latency is median 3.24\,ms, mean $3.62\pm0.81$\,ms, P95 4.98\,ms, and P99 5.89\,ms. CPU latency is median 3.81\,ms, mean $23.56\pm223.79$\,ms, P95 9.15\,ms, and P99 362.00\,ms. The timing records do not isolate the source of the CPU long tail. The reported standard deviations describe timed calls.

PyTorch \texttt{FlopCounterMode} reports 39.95\,M counted FLOPs for one forward call; dividing by two gives 19.98\,M MACs under the recorded counting convention. The model has 92,293 trainable parameters. These execution timings exclude preprocessing, input acquisition, and host-to-device transfer. EEG and fNIRS windows contain 10\,s and 12\,s of data, respectively.

\subsection{Evaluation Scope}
The study uses one public cohort for mental arithmetic versus rest, with a fixed 5\,s delay in the main benchmark. Offline preprocessing includes bidirectional filters, and the encoders use symmetric temporal padding. The attention mask constrains token-pair access according to their timestamps. Additional causal EEG smoothing was evaluated as a perturbation of offline-preprocessed inputs. Motor imagery, clinical populations, end-to-end streaming acquisition, and embedded hardware were not evaluated.
'''
conclusion = r'''\section{Conclusion}
NVC-DelayFormer combines timestamp-constrained cross-attention, temporal feature weighting, and joint direct and latent readouts for EEG--fNIRS classification. In 29 subject-held-out folds on mental arithmetic versus rest, it achieves 66.44\% $\pm$ 10.85\% accuracy and 65.13\% Macro F1. A 5\,s circular EEG shift changes accuracy by $-6.61$\,pp, while the separately trained zero-delay model reaches 66.61\%. Batch-one GPU forward latency has median 3.24\,ms and P99 5.89\,ms. These results describe the complete model's classification performance, temporal perturbation response, and execution cost on the tested system.
'''

attention = r'''\subsection{Timestamp-Constrained Multi-Head Cross-Attention}
The encoder outputs have shapes $\mathbf{H}_{\mathrm{eeg}}\in\mathbb{R}^{B\times250\times64}$ and $\mathbf{H}_{\mathrm{nirs}}\in\mathbb{R}^{B\times124\times64}$. Four heads split the feature dimension into $d_h=16$. Projected queries have shape $(B,4,124,16)$; keys and values have shape $(B,4,250,16)$. With $\Delta t_{ij}=t_i^{\mathrm{nirs}}-t_j^{\mathrm{eeg}}$, the additive prior and mask are
\begin{align}
P_{ij}&=-\frac{0.35|a|(\Delta t_{ij}-\tau)^2}{2\sigma^2+10^{-8}},\\
M_{ij}&=\begin{cases}0,&\Delta t_{ij}\ge-10^{-4}\,\mathrm{s},\\-\infty,&\Delta t_{ij}<-10^{-4}\,\mathrm{s}.\end{cases}
\end{align}
Here $a$ is a learned scalar initialized to 1. The main benchmark fixes $\tau=5.0$\,s and $\sigma=1.5$\,s; the implementation clamps them to $[0,8]$\,s and $[0.5,4]$\,s. The $10^{-4}$\,s mask tolerance includes equality. The head-wise weights are
\begin{equation}
\mathbf{A}_h=\operatorname{Softmax}_{j}\!\left(\frac{\mathbf{Q}_h\mathbf{K}_h^\top}{\sqrt{16}}+\mathbf{P}+\mathbf{M}\right).
\end{equation}
The prior and mask broadcast over batch and head axes. Thus $\mathbf{A}$ has shape $(B,4,124,250)$, and $\mathbf{A}_h\mathbf{V}_h$ has shape $(B,124,16)$. Concatenating the four contexts gives $(B,124,64)$ before output projection. The projected context $\mathbf{U}$ is combined with the fNIRS features using $\operatorname{LayerNorm}[\mathbf{H}_{\mathrm{nirs}}\odot(1+0.5\tanh(g(\mathbf{U})))+\mathbf{U}]$, followed by temporal-envelope scaling. Nominal token times are $t_j^{\mathrm{eeg}}=j/25$\,s and $t_i^{\mathrm{nirs}}=12i/124$\,s. This mask is defined by physical time on a rectangular matrix.
'''

readout = r'''\subsection{Temporal Weighting, Readout, and Reconstruction}
A nonnegative kernel combines the timestamp mask, a Gaussian with width 1.1\,s and center $\tau$, an EEG onset factor $\exp(-t_{\mathrm{eeg}}/1.2)$, and an fNIRS task factor $\operatorname{sigmoid}[(9.5-t_{\mathrm{nirs}})/0.5]$. Normalized row and column sums define the fNIRS and raw-EEG weights. The same prior/mask switches also control their corresponding factors in this weighting kernel during ablation.

The hemodynamic proxy is $\mathbf{F}=u(\partial_t\mathbf{X}_{\mathrm{nirs}}+0.15\mathbf{X}_{\mathrm{nirs}})$, using centered interior differences and one-sided boundary differences. Its amplitude scale is $u=1+2500\operatorname{sigmoid}[100(0.05-r)]$, where $r$ is the trial RMS of the input. The direct features concatenate 72 weighted proxy values with 30 log-energy EEG values, giving $(B,102)$ before non-affine batch normalization.

The reconstruction convolution receives $[0.1\mathbf{H}_{\mathrm{fused}}^\top;\mathbf{F}_{1:36}]$ of shape $(B,100,124)$ and returns $(B,36,124)$. Its target is $\mathbf{F}_{1:36}$. A weighted reconstruction summary is normalized with the direct-feature batch statistics. Its across-channel standard deviation, clipped to $[0,1]$, forms a gate $g_r$ that combines the fNIRS features as $g_r\mathbf{x}_{\mathrm{nirs}}+0.25(1-g_r)\operatorname{roll}_{18}(\mathbf{x}_{\mathrm{nirs}})$. The reconstruction signal uses $0.001\hat{\mathbf{F}}+0.999\operatorname{stopgrad}(\hat{\mathbf{F}})$ on this readout path.

Mean-pooled fused and EEG features concatenate to $(B,128)$ for the latent MLP. Final logits have shape $(B,2)$:
\begin{equation}
\hat{\mathbf{y}}=0.02\operatorname{MLP}(\mathbf{z}_{128})+0.98\operatorname{Linear}(\mathbf{x}_{102}).
\end{equation}
Training minimizes cross-entropy plus $0.08\|\mathbf{w}_{\mathrm{MA}}-\mathbf{w}_{\mathrm{Rest}}\|_2^2$ for the direct classifier and mean squared reconstruction error over $B\times36\times124$ values. Removing reconstruction loss sets its coefficient to zero.
'''

for filename in ['latex_cbm/main_cbm.tex', 'latex/main.tex']:
    text = (BACKUP / filename).read_text(encoding='utf-8')
    text = re.sub(r'\\title\{[^\n]*\}', lambda _: '\\title{'+title+'}', text, count=1)
    text = re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}', lambda _: '\\begin{abstract}\n'+abstract+'\n\\end{abstract}', text, flags=re.S)
    text = text.replace('Salim and Tiwari', 'Rukhsar and Tiwari')
    text = text.replace('upper-triangular causal mask', 'timestamp-based cross-attention mask')
    # Remove historical figures and the unsupported spatial/rank claims tied to them.
    for label in ['fig:topomap', 'fig:heatmap_sub05']:
        text = re.sub(r'\\begin\{figure\*?\}[^\n]*\n(?:(?!\\end\{figure).)*?\\label\{'+re.escape(label)+r'\}.*?\\end\{figure\*?\}', '', text, flags=re.S)
    text = re.sub(r'\\section\{Cortical Topographic[^\n]*\}.*?(?=\\section\{Discussion)', '', text, flags=re.S)
    text = re.sub(r'\\section\{Discussion[^\n]*\}.*?(?=\\section\{Conclusion)', lambda _: discussion+'\n', text, flags=re.S)
    end = r'(?=\\section\*\{CRediT)' if 'latex_cbm' in filename else r'(?=\\balance)'
    text = re.sub(r'\\section\{Conclusion\}.*?'+end, lambda _: conclusion+'\n', text, flags=re.S)
    text = text.replace("($W = 0.9603, p = 0.3337$) did not detect significant departure from normality.", 'were not used to select the primary benchmark test.')
    text = re.sub(r'^.*The Shapiro-Wilk test.*$', '', text, flags=re.M)
    text = re.sub(r"Shapiro-Wilk tests on paired accuracy differences.*?normality\.", '', text)
    text = text.replace('absolute zero-leakage evaluation', 'subject-held-out evaluation')
    text = text.replace('1,740 independent test trials', '1,740 held-out test trials')
    text = text.replace('Zero subject, trial, or normalization leakage occurs between splits.', 'Each held-out subject is excluded from training and validation; checkpoints are selected on validation subjects.')
    text = text.replace('30 scalp electrodes configured in the 10--20 system, sampled at 1,000\\,Hz, downsampled to 100\\,Hz', '30 scalp electrodes selected by their recorded channel names; the downloaded EEG at 200\\,Hz is resampled to 100\\,Hz')
    text = text.replace('dual-wavelength fNIRS optical densities', 'MBLL-derived HbO and HbR channels')
    text = text.replace('72 channels representing 36 optode pairs $\\times$ 2 wavelengths', '72 channels representing 36 HbO and 36 HbR traces')
    text = text.replace('72 optical channels', '72 HbO/HbR channels')
    text = text.replace('micromolar changes', 'concentration-scale changes')
    text = text.replace('to guarantee zero inter-trial information leakage', 'using the pre-stimulus baseline')
    text = text.replace('effectively suppressing spatially homogeneous volume-conducted noise while guaranteeing zero-sum conservation ($\\sum_{c=1}^C \\mathbf{X}_{\\text{eeg}}^{\\text{CAR}}(c, t) < 10^{-13}$)', 'subtracting the instantaneous channel mean')
    if 'latex_cbm' in filename:
        text = re.sub(r'\\begin\{highlights\}.*?\\end\{highlights\}', lambda _: r'''\begin{highlights}
\item Timestamp-constrained cross-attention combines EEG and fNIRS sequences.
\item The main benchmark uses a fixed 5.0 s Gaussian delay prior.
\item Twenty-nine subject-held-out folds yield 66.44\% mean accuracy.
\item Circular EEG shifting changes accuracy by -6.61 percentage points.
\item Batch-one GPU forward latency has median 3.24 ms and P99 5.89 ms.
\end{highlights}''', text, flags=re.S)
        text = re.sub(r'\\subsection\{The Temporal Multi-Scale.*?(?=\\section\{Related Work)', lambda _: r'''\subsection{Temporal Fusion}
EEG and fNIRS differ in sampling rate and response timescale. Feature concatenation combines modality summaries, whereas cross-attention operates on pairs of encoded time samples. Systemic Mayer oscillations are one source of variation in optical recordings \cite{julien2006enigma}. We use a Gaussian delay prior and a timestamp mask to specify temporal preferences in cross-modal attention.

\subsection{Contributions}
NVC-DelayFormer combines convolutional token encoders, timestamp-constrained attention, weighted direct features, and an auxiliary reconstruction head. We report a 29-fold subject-held-out benchmark, component ablations, a fixed-weight delay sweep, and four input perturbations. Accuracy is 66.44\% $\pm$ 10.85\%, Macro F1 is 65.13\%, and the four baseline comparisons have BH $q<0.01$.

''', text, flags=re.S)
        text = re.sub(r'\\subsection\{Physiology-Guided Causal Cross-Attention\}.*?(?=\\begin\{figure\}\[!t\]\n\\centering\n\\includegraphics\[width=\\columnwidth\]\{figures/real_29sub_benchmark)', lambda _: attention+'\n'+readout+'\n', text, flags=re.S)
        text = re.sub(r'\\section\{Negative Controls.*?(?=\\section\{Discussion)', lambda _: controls_tex+'\n', text, flags=re.S)
        text = re.sub(r'\\subsection\{Multi-Task Training Convergence Dynamics\}.*?(?=\\section\{Temporal Perturbation)', lambda _: '\\subsection{Recorded Training History}\nFigure~\\ref{fig:training_curves} shows the recorded classification loss, reconstruction loss, and validation accuracy for Sub-05 over 12 epochs. Checkpoint selection uses validation accuracy and, for ties, validation loss.\n\n', text, flags=re.S)
        text = re.sub(r'\\subsection\{Five-Way Systematic Ablation Analysis\}.*?(?=\\subsection\{Empirical Validation)', lambda _: r'''\subsection{Component Ablations}
Table~\ref{tab:ablation} reports each trained variant. The accuracy changes are $-0.80$\,pp without the delay prior, $-0.29$\,pp without the mask, and $-1.15$\,pp without reconstruction loss. Their Wilcoxon $p$-values are 0.3319, 0.6360, and 0.3155, respectively. The zero-delay model reaches 66.61\% ($+0.17$\,pp; Wilcoxon $p=0.9636$). Reconstruction correlation changes from 0.8912 to 0.0012 without reconstruction loss; the target is the derivative-based hemodynamic proxy described in the method.

''', text, flags=re.S)
    else:
        text = re.sub(r'Despite the clinical appeal.*?(?=\\begin\{figure\*\})', lambda _: r'''The modalities differ in response timescale. NVC-DelayFormer uses a fixed 5.0\,s Gaussian prior and a timestamp mask for cross-modal token access, together with a weighted direct readout and auxiliary reconstruction. We evaluate the full architecture against unimodal and multimodal baselines under subject-held-out validation and report component ablations and input perturbations. Systemic oscillations are a known component of optical recordings \cite{julien2006enigma}; their removal was not separately measured here.

''', text, flags=re.S)
        text = re.sub(r'\\subsection\{Physiology-Guided Causal Cross-Attention\}.*?(?=\\section\{Experimental Benchmark)', lambda _: attention+'\n'+readout+'\n', text, flags=re.S)
        text = re.sub(r'\\subsection\{Multi-Task Hemodynamic Regularization Efficacy\}.*?(?=\\section\{Discussion)', lambda _: r'''\subsection{Component and Delay Results}
The zero-delay model has 66.61\% accuracy (Wilcoxon $p=0.9636$ versus the full model). Removing reconstruction loss gives 65.29\% ($p=0.3155$) and changes reconstruction correlation from 0.8912 to 0.0012. The reconstruction target is a derivative-based hemodynamic proxy provided as part of the decoder input.

With trained weights held fixed, the delay sweep gives 65.17\%, 65.80\%, 66.21\%, 66.44\%, 67.18\%, and 66.55\% at 0, 2, 4, 5, 6, and 8\,s, respectively. Separately optimized initial delays of 2.5 and 3.0\,s reach 3.53 and 4.01\,s in the recorded optimization runs.

'''+controls_tex+'\n', text, flags=re.S)
        text = text.replace('For real-time streaming BCI emulation, single-pass minimum-phase causal IIR filtering is employed, where temporal causality is strictly preserved across sliding analysis windows.', 'The smoothing perturbation described below is applied after this offline preprocessing.')
    # Remove unsupported equivalence/peak-shape interpretations elsewhere.
    text = text.replace('This empirical curve mirrors the canonical post-stimulus oxygenation peak window observed in human functional optical neuroimaging.', 'The highest measured accuracy among these six fixed-weight settings occurs at 6.0\\,s.')
    text = text.replace('This indicates that the architecture naturally exhibits gradient flow consistent with hemodynamic temporal latency.', 'These are optimization trajectories for the stated initial values.')
    text = text.replace('Salim and Tiwari', 'Rukhsar and Tiwari')
    text = text.replace('cohort Binomial Chance-Level Rejection', 'Pooled Trial Count')
    text = text.replace('confirming that performance cannot be attributed to stochastic chance.', 'The pooled binomial calculation assumes independent trials; subject-level paired comparisons are used for the model comparisons.')
    text = re.sub(r'avoids high-frequency noise amplification', 'has the stated numerical condition number', text)
    text = re.sub(r'avoids numerical noise amplification', 'has the stated numerical condition number', text)
    text = text.replace('avoids high-frequency noise amplification', 'has the stated numerical condition number')
    text = re.sub(r'The highest mutual information.*?\\tau \\approx 5.0\$\\,s\.', 'The delay prior specifies a modeling preference for positive lags centered near 5\\,s.', text)
    text = text.replace('From this cascade, two physical invariants emerge:', 'The model uses the following temporal assumptions:')
    text = re.sub(r'\$\+([0-9.]+)\\%\$', lambda m: '$+'+m[1]+'$\\,pp', text)
    (ROOT / filename).write_text(text, encoding='utf-8')

# Keep future experiment outputs at full precision and use count-based accuracy.
script_path = ROOT / 'scripts/run_real_negative_controls_and_sub05_curves.py'
script = (BACKUP / 'scripts/run_real_negative_controls_and_sub05_curves.py').read_text(encoding='utf-8')
script = script.replace('Streaming Causal Filtering Emulation', 'Additional Causal EEG Smoothing')
script = script.replace('Streaming Causal Filtering', new_name)
script = script.replace('[round(float(x), 2) for x in c_arr]', '[float(x) for x in c_arr]')
script = script.replace('[round(float(x), 2) for x in full_arr]', '[float(x) for x in full_arr]')
script = script.replace('(preds.argmax(-1) == te_l).float().mean().item() * 100.0', '(preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()')
script = script.replace('diff = full_arr - c_arr', 'diff = np.round(full_arr - c_arr, 10)')
script = script.replace('stats.ttest_rel(full_arr, c_arr)', "stats.ttest_1samp(diff, 0, alternative='two-sided')")
script = script.replace('stats.wilcoxon(full_arr, c_arr)', "stats.wilcoxon(diff, zero_method='wilcox', correction=False, alternative='two-sided', method='approx')")
script = script.replace('single-pass minimum-phase IIR sosfilt vs zero-phase', 'exponential smoothing added to offline-preprocessed EEG; fNIRS unchanged')
script = script.replace('on test EEG and fNIRS tokens along time axis', 'on offline-preprocessed test EEG only; fNIRS unchanged')
script = script.replace('for shift in [+500, -500]:', 'for shift in [500]:  # +/-500 are identical for 1000-sample epochs')
script_path.write_text(script, encoding='utf-8')
print('Reconciled negative controls:')
for name, r in data['controls'].items():
    print(name, 'mean', r['mean_acc'], 't-p', r['t_test_p'], 'W', r['wilcoxon_stat'], 'W-p', r['wilcoxon_p'], 'q', r['fdr_q'])
print('Updated manuscript sources and archived previous versions at', BACKUP)
