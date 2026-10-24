# Manuscript Cover Letter for IEEE Transactions on Biomedical Engineering (TBME)

**College of Information Science and Engineering, Huaqiao University**  
No. 668 Jimei Avenue, Xiamen, Fujian 361021, P. R. China  
Corresponding Author: Fang Duan, E-mail: `nkfetsh@gmail.com`

---

**Date:** October 24, 2026  

**To:**  
Prof. Amir A. Amini, Editor-in-Chief  
*IEEE Transactions on Biomedical Engineering* (TBME)  
Department of Electrical and Computer Engineering, University of Louisville  
Louisville, KY 40292, USA  

**Subject:** Submission of Regular Paper: **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”**  
**Suggested Track:** Neural Engineering & Brain–Computer Interfaces (Biomedical Signal Processing)

Dear Prof. Amini and Members of the Editorial Board,

We are pleased to submit our original research manuscript entitled **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”** for consideration as a **Regular Paper** in the *IEEE Transactions on Biomedical Engineering* (TBME).

### Biomedical Context & Clinical Rationale
Hybrid EEG–fNIRS non-invasively captures complementary electrophysiological transients and localized capillary hemodynamics. Translating hybrid systems to zero-calibration clinical BCIs (e.g., for motor-impaired or locked-in individuals unable to undergo tedious calibrations) faces a fundamental biophysical bottleneck: disparate biological timescales (milliseconds vs. 3.5–6.5 s). Standard unconstrained cross-attention architectures exploit spurious temporal coincidences in leave-one-subject-out (LOSO) regimes, degrading generalization across unseen individuals.

### Key Contributions & Empirical Rigor
We present **NVC-DelayFormer**, which embeds neurovascular timing constraints into multimodal decoding. The study connects physiological modeling with participant-isolated evaluation and computational profiling for calibration-free BCI development:
1. **Biophysically Constrained Cross-Attention:** Multi-head attention is regularized by continuous Gaussian hemodynamic delay kernels ($\tau_h \in [3.5, 6.5]$\,s) and token timestamp masks ($t_{\mathrm{nirs}} \ge t_{\mathrm{eeg}}$), enforcing temporal precedence across modalities.
2. **Entropy-Guided Dual-Stream Gating:** An adaptive bottleneck dynamically balances deep cross-modal tokens against shallow biophysical spectral summaries conditioned on predictive distribution entropy, safeguarded by auxiliary waveform reconstruction.
3. **Causal Online Adaptation & Multi-Task Generalization:** We introduce Causal Recursive Euclidean Alignment (CrEA), eliminating session lookahead and stabilizing reference covariances within 5–8 trials under empirical Bayes shrinkage (retaining 94.9% of offline performance in trial-causal streaming evaluation). Across 29 participants on the TU Berlin benchmark under LOSO cross-validation, NVC-DelayFormer achieves a 3-seed grand mean accuracy of **78.22% ± 1.00%** (primary seed: **79.37% ± 7.73%**), significantly outperforming standard 2D-EEGNet ($p = 1.10\times 10^{-4}$), covariance-aligned Shrinkage-LDA ($p = 0.0167$), and unconstrained cross-attention ($p = 7.18\times 10^{-4}$). Task-specific LOSO evaluations across 3,612 held-out trials yielded accuracies of **73.24%** for working memory and **66.32%** for motor imagery.
4. **Computational Efficiency:** The architecture uses **63,932 parameters** and **24.79 M MACs**, with a batch-one forward latency of **2.22 ms** on an NVIDIA RTX 4060 Laptop GPU (P99: 4.48 ms).

### Mandatory Declarations & Compliance
- **Originality & Conference Status:** This manuscript represents original work that has not been published previously and is not under consideration elsewhere. It is entirely new and is not an extension of any conference proceeding.
- **Preprint Status:** This manuscript has not been posted to any preprint repository (e.g., arXiv, TechRxiv, bioRxiv).
- **Authorship Approval:** All authors have read and approved the final manuscript and agree with its submission to IEEE TBME.
- **Ethical Approval:** All human participant analyses used de-identified open-access data approved by the Ethics Committee of the Institute of Psychology and Ergonomics, Technische Universität Berlin (protocol SH_01_20150330), in accordance with the Declaration of Helsinki.
- **Conflict of Interest & Funding:** The authors declare no competing financial or non-financial interests, and no external grant funding directly supported this specific research.
- **Manuscript Length & Supplementary Material:** The submitted manuscript comprises eight pages in IEEE Transactions format, accompanied by a 3-page Supplementary Material document containing paradigm-specific delay sensitivity analyses (Supplementary Fig. S1), 29-subject fold breakdowns (Supplementary Table S1), and streaming algorithm details.
- **Reproducibility:** Complete source code, test suites, and DOI archive are openly accessible at https://github.com/ujujuj3061831150/nvc-delayformer-bci.

Thank you very much for your time and consideration of our work.

Sincerely,  
**Fang Duan** (Corresponding Author, E-mail: `nkfetsh@gmail.com`)  
**Hongjie Chen** (First Author, E-mail: `chenhj976@gmail.com`)  
College of Information Science and Engineering, Huaqiao University, Xiamen 361021, Fujian, China  
