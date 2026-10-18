# Cover Letter to Computers in Biology and Medicine

**Date:** October 12, 2026  
**To:**  
Editor-in-Chief  
*Computers in Biology and Medicine*  
Elsevier Science  

**Subject:** Submission of Original Research Article: *"Physiology-Guided Causal Cross-Attention Resolves the Neurovascular Latency Mismatch in Hybrid EEG--fNIRS Brain--Computer Interfaces"*

Dear Editor-in-Chief and Editorial Board,

We are pleased to submit our original research article entitled **"Physiology-Guided Causal Cross-Attention Resolves the Neurovascular Latency Mismatch in Hybrid EEG--fNIRS Brain--Computer Interfaces"** for consideration for publication as a Regular Research Paper in *Computers in Biology and Medicine*.

### Background & Significance to the Journal
Hybrid Brain-Computer Interfaces (hBCIs) combining electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) hold immense potential for clinical diagnostics and assistive technologies. However, existing multimodal machine learning models treat electrical fast potentials (millisecond scale) and delayed optical hemodynamics (second scale) as concurrent, leading unconstrained cross-attention to overfit to systemic 0.1 Hz arterial Mayer oscillations and electrical sensor artifacts.

In this work, we present **NVC-DelayFormer**, an end-to-end deep learning framework that directly embeds the physiological delay and temporal causality of neurovascular coupling (NVC) into a cross-attention Transformer. The architecture incorporates:
1. A **Gaussian Physiological Delay Prior** focusing multimodal attention on the canonical 5-second hemodynamic latency;
2. A **Strict Temporal Causality Mask** that prevents acausal backward attention leakage ($t_{\text{eeg}} \le t_{\text{fnirs}}$);
3. An **Auxiliary Hemodynamic Response Function (HRF) Reconstructor** that stabilizes multimodal representations against vascular baseline drift via multi-task regularization.

### Key Rigorous Findings & Validation
* **Zero-Leakage 29-Subject Cohort Benchmark**: Under strict 29-fold Leave-One-Subject-Out (LOSO) cross-validation with three-way subject isolation (Train 23 / Val 5 / Test 1) across all 29 human subjects of the open-access TU Berlin dataset (1,740 authentic trials), NVC-DelayFormer achieves **65.52% ± 10.58%** accuracy (Cohen's $\kappa = 0.3103$), significantly outperforming unimodal EEGNet (57.93%, $p = 0.0030$, Cohen's $d_z = 0.60$), unimodal fNIRS-CNN (54.31%, $p = 0.0002$, $d_z = 0.77$), Feature-Concat (59.54%, $p = 0.0051$), and Standard-Attention (58.16%, $p = 0.0015$) with all tests passing False Discovery Rate (FDR) correction ($q < 0.01$).
* **Definitive Double Dissociation via Phase Roll**: When circularly shifting EEG time-series by $\pm 5$ s, unimodal EEGNet ($p = 0.25$) and unconstrained Standard-Attention ($p = 0.46$) remain unaffected, whereas NVC-DelayFormer suffers a catastrophic $-6.90\%$ collapse ($p = 7.05 \times 10^{-8}$), rigorously proving model-specific biological delay tuning.
* **Real-Time Edge Feasibility**: On a standard edge GPU, single-trial inference executes in **1.61 ms** (P99 latency 3.06 ms) with TorchScript JIT bit-exactness, proving translational viability for continuous closed-loop BCI.

### Mandatory Submission Declarations
* This manuscript is original, has not been published previously, and is not under consideration for publication elsewhere.
* All authors have approved the manuscript and agree with its submission to *Computers in Biology and Medicine*.
* No conflicts of interest exist.
* The complete source code, PyTorch models, and reproducible evaluation pipelines will be made publicly available on GitHub and Zenodo upon acceptance.

Given the journal's prestigious leadership in biomedical computing, neural signal processing, and machine learning applications in medicine, we believe this manuscript is ideally suited for the readership of *Computers in Biology and Medicine*.

Thank you very much for your time and consideration of our work.

Sincerely,

**Antigravity BCI Research Collaborative**  
Laboratory for Neural Engineering & Neurovascular Computing  
Email: research@antigravity-bci.org  
