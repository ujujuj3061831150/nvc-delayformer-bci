# Phase 6 Report: Independent External Dataset Cross-Subject Validation (Buccino et al. 2016)

This report documents the execution and empirical findings of **Phase 6** of the CMPB strategic upgrade: evaluating the proposed **NVC-DelayFormer** architecture on a completely independent external multimodal dataset ([Buccino et al., *PLOS ONE* 2016](https://doi.org/10.1371/journal.pone.0146610); DOI: `10.1371/journal.pone.0146610`).

---

## 1. Dataset & Acquisition Overview

The Buccino et al. (2016) dataset provides simultaneous, synchronized scalp EEG and continuous-wave fNIRS recordings gathered from 15 healthy human participants performing sensory-motor rhythm (SMR) tasks:

| Parameter | Specification | Note |
| :--- | :--- | :--- |
| **Participants** | 15 healthy adults ($N=15$, S1–S15) | Independent geographic cohort & laboratory (Univ. of Houston) |
| **Recording Hardware** | microEEG (BioSignal Group) + NIRScout 8-16 (NIRx) | Independent from TU Berlin hardware |
| **EEG Montages** | 21 scalp electrodes (10–5 international system) | F3, Fz, F4, Fc5, Fc1, Fc2, Fc6, T3, C3, C1, Cz, C2, C4, T4, Cp5, Cp1, Cp2, Cp6, P3, Pz, P4 |
| **EEG Sampling Rate** | Raw 250 Hz $\rightarrow$ resampled to 100 Hz | Exact polyphase 2/5 factor conversion |
| **fNIRS Channels** | 34 optode pairs (dual wavelength: 760nm / 850nm) | Motor cortex coverage; converted to 34 HbO + 34 HbR (68 channels) via MBLL |
| **fNIRS Sampling Rate**| 10.42 Hz (10.4167 Hz) | Effective token grid rate |
| **Task Paradigm** | SMR Motor Execution: Movement vs. Baseline Rest | 100 Movement trials (RH, LH, RA, LA) vs. 100 Rest trials |
| **Total Samples** | **3,000 samples** ($15 \times 200$ samples) | 1,500 movement samples and 1,500 baseline rest samples |
| **Window Duration** | $6.0$\,s ($T_{\mathrm{eeg}} = 600$, $T_{\mathrm{fnirs}} = 63$) | Preserves physiological hemodynamic onset delay |

---

## 2. Standardized Preprocessing Pipeline

The preprocessing pipeline ([`src/data/parse_buccino.py`](file:///e:/课题4/src/data/parse_buccino.py)) standardizes all 15 subjects into PyTorch format:

1. **EEG Stream**:
   - Polyphase FIR resampling from 250 Hz to 100 Hz (`scipy.signal.resample_poly`, ratio $2/5$).
   - 4th-order zero-phase Butterworth bandpass filter (0.5–45.0 Hz).
   - Common Average Reference (CAR) across the 21 spatial scalp channels.
2. **fNIRS Stream**:
   - Baseline intensity $I_0$ per channel across the continuous recording.
   - Optical density change: $\Delta \mathrm{OD}(\lambda) = -\ln(I(\lambda, t) / I_0(\lambda))$.
   - Bandpass filter on optical density: 0.01–0.10 Hz.
   - Modified Beer-Lambert Law (MBLL) inversion with adult dispersion DPF ($6.51$ at 760nm, $5.86$ at 850nm) mapping dual wavelengths to molar concentrations $\Delta [\mathrm{HbO}]$ and $\Delta [\mathrm{HbR}]$ (68 total channels: 34 HbO + 34 HbR).
3. **Epoch Extraction**:
   - Movement trials: $[t_{\mathrm{onset}}, t_{\mathrm{onset}} + 6.0\,\mathrm{s}]$ (event codes 3, 4, 7, 8).
   - Rest trials: $[t_{\mathrm{onset}} + 1.0\,\mathrm{s}, t_{\mathrm{onset}} + 7.0\,\mathrm{s}]$ (event code 1, allowing movement transition decay).

---

## 3. Cross-Subject 15-Fold LOSO Benchmark Results

Evaluation used strict **within-cohort 15-fold Leave-One-Subject-Out (LOSO)** cross-validation under the unified training objective (cross-entropy + $0.08 \|w_1 - w_0\|^2$ direct weight regularization + $1.0 \times \text{MSE}$ auxiliary proxy reconstruction loss on 34 HbO channels). For each held-out test participant $s \in \{1,\ldots,15\}$, 2 cyclic participants supplied 400 validation trials and 12 participants supplied 2,400 training trials:

### Table S1: Cross-Subject Benchmark Performance on Buccino et al. 2016

| Model Architecture | Parameters | Accuracy (%) | 95% CI (%) | Macro F1 (%) | Diff vs Full (pp) | Wilcoxon $p$ | BH FDR $q$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Proposed NVC-DelayFormer (Full Model)** | **90,509** | **$81.03 \pm 11.07$** | **[74.90, 87.16]** | **$80.77 \pm 11.33$** | — | — | — |
| — Factorial [Off, Uniform] Ablation | 90,509 | $78.60 \pm 8.97$ | [73.63, 83.57] | $78.40 \pm 9.28$ | $+2.43$ | $0.2524$ | $0.3786$ (ns) |
| — Direct-Only Readout (Biophysical) | 90,509 | $80.43 \pm 10.99$ | [74.35, 86.52] | $80.28 \pm 11.08$ | $+0.60$ | $1.0000$ | $1.0000$ (ns) |
| — Latent-Only Readout (Cross-Attention) | 90,509 | $73.70 \pm 14.60$ | [65.61, 81.79] | $73.41 \pm 14.93$ | $+7.33$ | $0.0899$ | $0.2838$ (ns) |
| Authentic 2D-EEGNet (Lawhern 2018) | 2,018 | $74.27 \pm 15.98$ | [65.42, 83.12] | $73.89 \pm 16.13$ | $+6.77$ | $0.0946$ | $0.2838$ (ns) |
| Handcrafted Multimodal Shrinkage-LDA | — | $85.23 \pm 5.96$ | [81.93, 88.53] | $85.13 \pm 6.09$ | $-4.20$ | $0.2293$ | $0.3786$ (ns) |
| Handcrafted Multimodal RBF-SVM | — | $84.13 \pm 6.44$ | [80.57, 87.70] | $83.86 \pm 6.81$ | $-3.10$ | $0.5245$ | $0.6294$ (ns) |

*Notes: Evaluated under 15-fold LOSO (200 samples per participant; 3,000 samples total, balanced 1,500 movement / 1,500 rest). Differences are Full Model minus comparison model. All Benjamini-Hochberg FDR $q$-values exceed 0.25 ($q \in [0.2838, 1.0000]$), indicating comparable performance tiers across all baseline models.*

---

## 4. Key Scientific & Comparative Findings

1. **Independent External Cohort Evaluation**:
   - On this independent dataset collected by a different laboratory using distinct acquisition hardware (microEEG + NIRScout 8-16) under a distinct task (motor execution vs. baseline rest), `NVC-DelayFormer` achieved **$81.03\% \pm 11.07\%$** cross-subject accuracy and **$80.77\%$** Macro F1.
   - This represents an increase of **$+6.77$\,pp** over Authentic 2D-EEGNet ($74.27\%$, Wilcoxon $p = 0.0946$), which showed high inter-subject volatility ($29.0\%$ on Sub-12).

2. **Consistent Readout Pathway Hierarchy**:
   - Direct-Only achieved $80.43\% \pm 10.99\%$ vs. Latent-Only $73.70\% \pm 14.60\%$ (mean difference $+6.73$\,pp, paired Wilcoxon $p = 0.1354$), reproducing the mean ranking pattern observed on TU Berlin.
   - Combining both streams in the dual-path joint readout achieved the highest mean accuracy among the readout variants ($81.03\%$).

3. **Comparison with Domain-Engineered Baselines**:
   - Ledoit-Wolf shrinkage LDA achieved $85.23\% \pm 5.96\%$ and RBF-SVM achieved $84.13\% \pm 6.44\%$, exhibiting the highest mean accuracies across all compared baselines.
   - After Benjamini-Hochberg FDR correction across all comparison baselines against Full Model, differences were not statistically significant ($q \in [0.2838, 1.0000]$), reproducing the exact non-significant comparison tier observed on the TU Berlin benchmark ($q > 0.20$).

---

## 5. Artifacts & Code Deliverables

1. **Downloader**: [`src/data/download_buccino.py`](file:///e:/课题4/src/data/download_buccino.py)
2. **Preprocessing Pipeline**: [`src/data/parse_buccino.py`](file:///e:/课题4/src/data/parse_buccino.py)
3. **15-Fold LOSO Benchmark**: [`src/run_phase6_buccino_benchmark.py`](file:///e:/课题4/src/run_phase6_buccino_benchmark.py)
4. **Locked Results JSON**: [`reports/phase6_external_dataset_buccino_results.json`](file:///e:/课题4/reports/phase6_external_dataset_buccino_results.json)
5. **Manuscript Alignment**:
   - Updated [`latex_cbm/main_cbm.tex`](file:///e:/课题4/latex_cbm/main_cbm.tex) Section 5.3 with the $81.03\%$ quantitative finding.
   - Compiled [`latex_cbm/main_cbm.pdf`](file:///e:/课题4/latex_cbm/main_cbm.pdf) strictly maintaining **8 pages**, 0 overfull hboxes.
   - SHA-256 Hash: `F1C80C32EA59D2C2935E052287704A85E80E354B0D91023A39814031F97DE5DF`.
