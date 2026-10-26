# Manuscript Cover Letter for Journal of Neural Engineering (JNE)

**College of Information Science and Engineering, Huaqiao University**  
No. 668 Jimei Avenue, Xiamen, Fujian 361021, P. R. China  
Corresponding Author: Fang Duan, E-mail: `nkfetsh@gmail.com`

---

**Date:** October 26, 2026  
**Topic / Section:** Brain–Computer Interfaces & Neural Signal Processing  

**To:**  
Prof. Warren M. Grill, Editor-in-Chief  
*Journal of Neural Engineering* (JNE)  
Department of Biomedical Engineering, Duke University, Durham, NC 27708, USA  

**Subject:** Submission of Research Paper: **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”**  

Dear Prof. Grill and Members of the Editorial Board,

We are pleased to submit our original research manuscript entitled **“Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces”** for consideration for publication in the *Journal of Neural Engineering* (JNE).

### Context & Neural Engineering Challenge
Hybrid EEG–fNIRS interfaces offer a powerful non-invasive window into neural function by pairing high-temporal-resolution electrophysiology with localized capillary hemodynamics. However, developing zero-calibration, cross-subject brain–computer interfaces (BCIs) remains constrained by the fundamental biological timescale disparity between electrophysiological transients (milliseconds) and capillary hemodynamic responses (seconds). When unconstrained deep cross-attention networks are trained in cross-subject leave-one-subject-out (LOSO) regimes, they frequently learn spurious, acausal alignments where sluggish hemodynamic tokens mistakenly attend to future neural activations ($\delta_{ij} < 0$), impairing generalization to unseen participants.

### Key Contributions & Empirical Rigor
To resolve this biophysical bottleneck, we propose **NVC-DelayFormer**, an architecture that embeds biophysical neurovascular timing priors directly into multimodal cross-attention. Our contributions are substantiated through rigorous participant-isolated evaluations and open-science benchmarking:

1. **Physiology-Guided Cross-Attention Formulation:** Multi-head cross-attention is parameterized by multicenter Gaussian delay priors grounded in canonical hemodynamic response delay windows ($\tau_h \in \{3.5, 4.5, 5.5, 6.5\}$ s) and token timestamp masks that explicitly eliminate acausal backwards-in-time connections, ensuring temporal precedence across modalities.
2. **Factorial Ablation & Dual-Cohort LOSO Validation:** Under strict leave-one-subject-out (LOSO) protocols across both the primary 29-participant cohort (TU Berlin) and an independent 15-participant external cohort (Buccino et al., 81.03% accuracy; Supplementary Section S.V), factorial ablations explicitly confirm cross-hardware generalizability and isolate the distinct marginal contributions of the delay prior versus the causal mask.
3. **Unsupervised Recursive Covariance Alignment (CrEA):** To tackle inter-subject covariance drift during test time, we introduce Causal Recursive Euclidean Alignment (CrEA), which recursively updates reference covariances online without session lookahead, reducing relative covariance error from 45.15% to 29.38% within the first 8 trials. Across 29 participants and three random seeds, NVC-DelayFormer achieves a grand mean accuracy of **78.22% ± 1.00%** (primary seed: **79.37% ± 7.73%**), significantly exceeding standard 2D-EEGNet (72.89%, $p = 1.10\times 10^{-4}$) and unconstrained cross-attention ($p = 7.18\times 10^{-4}$). In task-specific training, accuracy reaches **73.24%** for working memory and **66.32%** for motor imagery.
4. **Compact Embedded Footprint:** With only **63,932 trainable parameters** and **24.79 M MACs**, the model requires $17.5\times$ fewer parameters than EEG Conformer and operates with a batch-one forward latency of **2.22 ms** on an NVIDIA RTX 4060 Laptop GPU, satisfying the operational envelope of wearable neural interfaces.

### Mandatory Declarations & Compliance
- **Originality:** This manuscript represents original work not published previously and not currently under consideration elsewhere.
- **Authorship Approval:** All authors have read and approved the final manuscript and agree with its submission to the *Journal of Neural Engineering*.
- **Ethical Approval:** All human participant analyses used de-identified open-access data approved by the Ethics Committee of the Institute of Psychology and Ergonomics, Technische Universität Berlin (protocol SH_01_20150330), in accordance with the Declaration of Helsinki.
- **Conflict of Interest & Funding:** The authors declare no competing financial or non-financial interests. No specific external grant supported this research.
- **Reproducibility & Open Science:** Full source code, pre-trained checkpoints, test suites, and audit logs are openly accessible at [GitHub Repository (ujujuj3061831150/nvc-delayformer-bci)](https://github.com/ujujuj3061831150/nvc-delayformer-bci).

Thank you very much for your time and consideration of our manuscript.

Sincerely,  
**Fang Duan** (Corresponding Author, E-mail: `nkfetsh@gmail.com`)  
**Hongjie Chen** (First Author, E-mail: `chenhj976@gmail.com`)  
College of Information Science and Engineering, Huaqiao University, Xiamen 361021, Fujian, China  
