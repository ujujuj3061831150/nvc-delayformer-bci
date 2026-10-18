# Manuscript Cover Letter

October 17, 2026

Dear Editor,

We submit the manuscript entitled **“Physiology-guided temporal fusion for cross-subject EEG--fNIRS classification”** for consideration for publication in your journal.

Hybrid electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) non-invasively probe complementary electrical and hemodynamic signatures of cerebral activity. However, cross-subject decoding is hampered by substantial latency disparities between millisecond-scale electrophysiological oscillations and delayed vascular responses peaking 4–6\,s later. Standard cross-modal architectures often overfit spurious temporal correspondences in participant-held-out regimes.

To resolve this limitation, we introduce **NVC-DelayFormer**, a biophysically constrained architecture that couples multi-channel electrophysiological and optical dynamics through neurovascular coupling inductive priors. The architecture integrates an authentic 2D-EEGNet tokenizer, continuous optical temporal convolution, and a cross-modal attention mechanism regularized by a continuous Gaussian delay prior centered at canonical physiological latency ($\tau \approx 5.0\,\text{s}$) alongside strict physical causal masking. A convex adaptive gate dynamically balances deep cross-modal representations against shallow biophysical energy features.

Under rigorous leave-one-subject-out (LOSO) cross-validation across three experimental tasks encompassing 5,352 trials over 84 total cross-subject folds, the framework establishes the following verified empirical findings:
1. **Primary 29-Subject Benchmark (TU Berlin Mental Arithmetic):** Evaluated across 29 participants, NVC-DelayFormer achieves **79.37% ± 7.73%** accuracy and **79.15%** Macro F1 (95% CI: [76.43, 82.31]%), with a multi-seed grand mean of **78.22% ± 1.00%**. This performance decisively surpasses authentic unimodal 2D-EEGNet (76.84% single seed; 72.89% across seeds; paired $p = 1.10 \times 10^{-4}, q = 3.31 \times 10^{-4}$), domain-engineered Shrinkage-LDA (72.82%; $p = 0.0167, q = 0.0209$), and multimodal deep learning baselines (Multi-View Hybrid CNN: 72.53%, $p = 6.35 \times 10^{-4}$; Cross-Modal Transformer: 71.67%, $p = 7.18 \times 10^{-4}$).
2. **Ablation & Factorial Decomposition:** A systematic $2 \times 2$ factorial evaluation establishes a **+4.94 pp** net two-prior effect over the dual-prior-off baseline (74.43% ± 8.34%, paired Wilcoxon $p = 6.05 \times 10^{-5}$). The Gaussian delay prior serves as the primary regularizer (+4.31 pp average marginal contribution), the causal mask provides local temporal ordering (+0.64 pp), and their interaction confers +0.81 pp positive synergy.
3. **External Task-Adaptation Across Dual Evaluation Paradigms (3,612 Held-Out Trials Across 55 Folds):**
   - *$n$-back Working Memory (Shin et al., 2018, 26 subjects, 1,872 trials):* Where both electrical oscillations and hemodynamic oxygenation exhibit strong task-evoked modulations, NVC-DelayFormer attains top cross-subject performance in its physiological delay stream at **70.03% ± 14.34%** accuracy and **67.89% ± 16.59%** Macro F1 (with the dual-path gated configuration reaching **68.54% ± 14.07%**), outperforming covariance Shrinkage-LDA (**62.13% ± 10.16%**, $\Delta = +7.90$ pp, $p = 0.0159$), Multimodal SVM (**61.06% ± 8.76%**, $\Delta = +8.97$ pp, $p = 0.0078$), and authentic 2D-EEGNet (**68.27% ± 13.34%**, $\Delta = +1.76$ pp).
   - *Motor Imagery: Left vs. Right Hand (Shin et al., 2017, 29 subjects, 1,740 trials):* Across 10.0\,s kinesthetic motor imagery epochs with contralateral ERD and delayed hemodynamics, NVC-DelayFormer attains top cross-subject performance at **66.32% ± 12.18%** accuracy (95% CI: [61.69, 70.95]%) and **65.49% ± 12.55%** Macro F1 in the delay stream, significantly outperforming Handcrafted Shrinkage-LDA (**58.05% ± 9.52%**, $\Delta = +8.27$ pp, paired Wilcoxon $p = 0.0014, q = 0.0036$), Multimodal SVM (**55.63% ± 7.38%**, $\Delta = +10.69$ pp, $p = 7.58 \times 10^{-6}, q = 3.79 \times 10^{-5}$), and authentic 2D-EEGNet (**62.18% ± 7.33%**, $\Delta = +4.14$ pp, $p = 0.0163, q = 0.0271$).
4. **Device-Resident GPU Execution Latency & Streaming Online Adaptability:** Profiling confirms that the complete network requires only **63,942 parameters** ($<65$\,k) and **24.84 M MACs**, executing forward inference in **2.22 ms** (median GPU latency; P99: 4.48 ms). Decision latency is therefore governed by sensor window accumulation rather than computational overhead. Furthermore, online Causal Recursive Euclidean Alignment (CrEA) eliminates transductive lookahead, achieving rapid covariance convergence within 5--8 trials under empirical Bayes shrinkage.

The complete codebase, reproduction pipelines, test suites, and standalone `temporal_fusion` package are made openly available under an open-source license. We believe this work offers substantial clinical, theoretical, and engineering relevance for calibration-free neurotechnologies.

Thank you for your consideration of our manuscript.

Sincerely,

Antigravity BCI Research Collaborative  
Laboratory for Neural Engineering & Neurovascular Computing  
research@antigravity-bci.org
