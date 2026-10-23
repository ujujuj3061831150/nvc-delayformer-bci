# Manuscript Cover Letter for IEEE Transactions on Biomedical Engineering (TBME)

**Date:** October 23, 2026

**To:**  
Editor-in-Chief  
*IEEE Transactions on Biomedical Engineering*  

**Subject:** Submission of Regular Paper entitled **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”**  
**Authors:** Hongjie Chen and Fang Duan (Corresponding Author)  
**Affiliation:** College of Information Science and Engineering, Huaqiao University, Xiamen, China  

Dear Editor-in-Chief,

We are pleased to submit our original research manuscript entitled **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”** for consideration as a **Regular Paper** in *IEEE Transactions on Biomedical Engineering* (TBME).

### Background and Biomedical Significance
Hybrid electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) non-invasively probe complementary electrophysiological transients and localized hemodynamic oxygenation dynamics. However, translating hybrid systems to zero-calibration cross-subject clinical BCIs faces a fundamental biophysical bottleneck: the profound timescale disparity between millisecond-scale electrical oscillations and multi-second capillary hemodynamics. Standard unconstrained cross-modal attention mechanisms frequently overfit spurious temporal coincidences in leave-one-subject-out (LOSO) regimes, failing to generalize across individuals.

### Key Contributions & Empirical Rigor
In this manuscript, we present **NVC-DelayFormer**, an end-to-end biophysically constrained architecture that couples electrophysiological and optical feature streams through explicit neurovascular coupling inductive priors:
1. **Biophysically Constrained Cross-Attention:** Multi-head cross-attention is regularized by continuous Gaussian hemodynamic delay kernels ($\tau_h \in [3.5, 6.5]$\,s) and strict token timestamp causal masking ($t_{\mathrm{nirs}} \ge t_{\mathrm{eeg}}$), eliminating acausal optimization shortcuts.
2. **Uncertainty-Aware Entropy-Guided Dual-Stream Gating:** An adaptive bottleneck network dynamically weights deep cross-attention tokens against shallow biophysical spectral summaries based on predictive distribution entropy, reinforced by auxiliary waveform reconstruction and shallow margin regularization.
3. **Causal Online Adaptation & Cross-Paradigm Validation:** We introduce Causal Recursive Euclidean Alignment (CrEA), which eliminates transductive session lookahead and stabilizes reference covariances within 5–8 trials under empirical Bayes shrinkage (retaining 94.9% of offline performance in trial-causal streaming evaluation). Across 29 participants on the TU Berlin benchmark under LOSO cross-validation, NVC-DelayFormer achieves a 3-seed grand mean accuracy of **78.22% ± 1.00%** (primary seed: **79.37% ± 7.73%**), significantly outperforming authentic 2D-EEGNet ($p = 1.10 \times 10^{-4}$), covariance-aligned Shrinkage-LDA ($p = 0.0167$), and unconstrained cross-modal attention ($p = 7.18 \times 10^{-4}$). External evaluations across 3,612 held-out trials demonstrate robust cross-paradigm generalizability on $n$-back working memory (73.24%) and motor imagery (66.32%).
4. **Bedside-Ready Edge Profile:** The model operates with only **63,932 trainable parameters** and **24.79 M MACs**, executing forward inference in **2.22 ms** on a consumer laptop GPU (P99: 4.48 ms, >400 Hz throughput), providing a compact, calibration-free core for bedside assistive neurotechnologies.

### Compliance and Declarations
- **Originality & Prior Publication:** This manuscript represents original work that has not been published previously and is not under consideration for publication elsewhere.
- **Ethical Standards:** All human participant investigations used de-identified open-access data approved by the Ethics Committee of the Institute of Psychology and Ergonomics, Technische Universität Berlin (protocol SH_01_20150330), in accordance with the Declaration of Helsinki.
- **Conflict of Interest:** The authors declare that they have no competing financial or non-financial interests.
- **Page Budget:** The manuscript is formatted in standard IEEE Transactions dual-column style and strictly spans **8 pages** with zero overlength pages ($0 overlength fee).
- **Open Reproducibility:** Complete source code, PyTorch implementation, verification test suites, and reproduction scripts are openly accessible at our public repository: https://github.com/ujujuj3061831150/nvc-delayformer-bci.

Thank you very much for your time and consideration of our work.

Sincerely,

**Fang Duan** (Corresponding Author)  
College of Information Science and Engineering, Huaqiao University  
Xiamen 361021, Fujian, China  
E-mail: nkfetsh@gmail.com  

**Hongjie Chen**  
College of Information Science and Engineering, Huaqiao University  
Xiamen 361021, Fujian, China  
E-mail: chenhj976@gmail.com  
