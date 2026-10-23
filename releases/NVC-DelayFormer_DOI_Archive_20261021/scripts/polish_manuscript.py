"""
Script to apply fine-grained polishing to manuscript/main.tex
adhering strictly to IEEE TBME standards and AGENTS.md rules.
"""
import re

with open('manuscript/main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Polish Abstract
old_abstract = r"""\begin{abstract}
Hybrid brain--computer interfaces (BCIs) combining electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) improve decoding by capturing complementary electrophysiological and hemodynamic cortical dynamics. However, disparate temporal scales---millisecond electrical transients versus multi-second capillary delays---impair cross-subject decoding when unconstrained neural attention overfits subject-specific timings. We present NVC-DelayFormer, an end-to-end temporal fusion network parameterized by biophysical neurovascular coupling (NVC) priors for calibration-free, subject-independent BCI decoding. The architecture pairs an authentic 2D-EEGNet backbone with a continuous fNIRS encoder into multi-head cross-attention governed by dispersive hemodynamic delay priors ($\tau_h \in [3.5, 6.5]$\,s) and strict physical causal masks ($t_{\mathrm{nirs}} \ge t_{\mathrm{eeg}}$). An uncertainty-aware entropy-guided gating network dynamically arbitrates between deep cross-modal tokens and shallow biophysical spectral summaries without heuristic hyperparameter tuning. Evaluated across 29 participants on the TU Berlin mental arithmetic benchmark (1,740 trials) under leave-one-subject-out (LOSO) cross-validation, NVC-DelayFormer achieved a primary 3-seed grand mean accuracy of 78.22\% $\pm$ 1.00\% (primary single seed: 79.37\% $\pm$ 7.73\%), significantly outperforming authentic 2D-EEGNet (72.89\%, $p = 1.10\times 10^{-4}$), covariance-engineered Shrinkage-LDA with Euclidean alignment (72.82\%, $p = 0.0167$), shared-encoder feature concatenation (72.84\%, $p = 6.35\times 10^{-4}$), and unconstrained cross-attention (72.49\%, $p = 7.18\times 10^{-4}$). In streaming deployment, Causal Recursive Euclidean Alignment (CrEA) achieved 78.91\% streaming accuracy with zero session lookahead. Across two external cohorts comprising 3,612 held-out trials, the architecture demonstrated robust generalization: 73.77\% on $n$-back working memory and 66.32\% on motor imagery. Operating with 63,940 weights and 2.22\,ms median GPU latency, NVC-DelayFormer establishes an accurate, calibration-free temporal fusion framework for bedside assistive neurotechnologies.
\end{abstract}"""

new_abstract = r"""\begin{abstract}
Hybrid brain--computer interfaces (BCIs) integrating electroencephalography (EEG) and functional near-infrared spectroscopy (fNIRS) improve decoding accuracy by capturing complementary electrophysiological and localized hemodynamic cortical dynamics. However, translating hybrid systems across unseen individuals is constrained by disparate temporal scales: millisecond-scale electrical oscillations versus multi-second capillary blood flow transitions. Unconstrained neural attention networks tend to overfit subject-specific latency alignments, undermining cross-subject generalization. We present NVC-DelayFormer, an end-to-end temporal fusion framework parameterized by neurovascular coupling (NVC) biophysical priors for calibration-free, subject-independent BCI decoding. The architecture couples an authentic 2D-EEGNet backbone with a continuous fNIRS encoder via multi-head cross-attention constrained by dispersive hemodynamic delay priors ($\tau_h \in [3.5, 6.5]$\,s) and physical causal masks ($t_{\mathrm{nirs}} \ge t_{\mathrm{eeg}}$). In parallel, an uncertainty-aware entropy-guided gating module dynamically arbitrates between deep cross-modal tokens and shallow sub-band biophysical summaries without manual hyperparameter tuning. Evaluated across 29 participants on the open TU Berlin mental arithmetic benchmark (1,740 trials) under leave-one-subject-out (LOSO) cross-validation, NVC-DelayFormer achieves a primary 3-seed grand mean accuracy of 78.22\% $\pm$ 1.00\% (primary single seed: 79.37\% $\pm$ 7.73\%), significantly outperforming authentic 2D-EEGNet (72.89\%, $p = 1.10\times 10^{-4}$), covariance-aligned Shrinkage-LDA with Euclidean alignment (72.82\%, $p = 0.0167$), shared-encoder feature concatenation (72.84\%, $p = 6.35\times 10^{-4}$), and unconstrained cross-attention (72.49\%, $p = 7.18\times 10^{-4}$). In streaming mode, Causal Recursive Euclidean Alignment (CrEA) yields 78.91\% causal decoding accuracy with zero session lookahead. Benchmarked across two external cohorts comprising 3,612 held-out trials, the architecture demonstrates robust multi-paradigm transfer: 73.77\% on $n$-back working memory and 66.32\% on motor imagery. Requiring only 63,940 parameters and 2.22\,ms median GPU forward latency, NVC-DelayFormer provides an accurate, calibration-free temporal fusion foundation for bedside assistive neurotechnologies.
\end{abstract}"""

# Normalize line breaks for search
def replace_chunk(text, old_chunk, new_chunk):
    old_clean = '\n'.join([line.strip() for line in old_chunk.strip().splitlines()])
    # find where this pattern matches in text
    lines = text.splitlines()
    # Let's search for exact or normalized
    if old_chunk in text:
        return text.replace(old_chunk, new_chunk, 1)
    # try replacing CRLF/LF variations
    old_crlf = old_chunk.replace('\n', '\r\n')
    if old_crlf in text:
        return text.replace(old_crlf, new_chunk.replace('\n', '\r\n'), 1)
    raise ValueError("Chunk not found!")

content = replace_chunk(content, old_abstract, new_abstract)
print("Abstract replaced successfully.")

# 2. Polish Introduction opening
old_intro_open = r"""\IEEEPARstart{I}{n} clinical neurorehabilitation and bedside assistive technology, brain--computer interfaces (BCIs) require immediate, calibration-free operation to eliminate prolonged, fatiguing patient calibrations that impede clinical adoption."""
new_intro_open = r"""\IEEEPARstart{B}{edside} assistive neurotechnologies and neurorehabilitation systems require immediate, calibration-free operation to eliminate prolonged, fatiguing patient calibration routines that impede practical translation."""

content = replace_chunk(content, old_intro_open, new_intro_open)
print("Intro opening replaced successfully.")

# 3. Polish Introduction paragraph 3
old_intro_p3 = r"""When fusing both streams, standard cross-attention mechanisms \cite{vaswani2017attention, wang2023cross} compute pairwise token interactions without inductive constraints. However, unconstrained cross-attention permits unphysiological alignments, including acausal queries where future hemodynamic states attend to subsequent electrophysiology, producing optimization artifacts that fail to transfer across subjects."""
new_intro_p3 = r"""When fusing both modalities, standard cross-attention mechanisms \cite{vaswani2017attention, wang2023cross} compute pairwise token interactions across time. However, unconstrained cross-modal attention permits acausal alignments where delayed hemodynamic queries attend to future electrophysiological activations ($\delta_{ij} < 0$), generating optimization artifacts that fail to generalize across individuals."""

content = replace_chunk(content, old_intro_p3, new_intro_p3)
print("Intro p3 replaced successfully.")

# 4. Polish Section III-D description of delay prior and causal mask
old_prior_desc = r"""where fixed head-specific centers $\tau_h \in \{3.5, 4.5, 5.5, 6.5\}$\,s parameterize multi-scale dispersive hemodynamic delays across attention heads ($\sigma_h = 1.5$\,s) to model microvascular transit across early arteriolar dilation, peak capillary exchange, and venular outflow. The asymmetric penalty factor models post-stimulus undershoot attenuation for $\delta_{ij} > \tau_h$. The causal mask $\mathbf{M}$ prevents hemodynamic queries from attending to subsequent electrophysiology ($\delta_{ij} < 0$\,s)."""
new_prior_desc = r"""where fixed head-specific centers $\tau_h \in \{3.5, 4.5, 5.5, 6.5\}$\,s parameterize multi-scale dispersive hemodynamic delays across attention heads ($\sigma_h = 1.5$\,s) to model microvascular transit across early arteriolar dilation, peak capillary exchange, and venular outflow. The asymmetric penalty factor models post-stimulus response attenuation for long delays ($\delta_{ij} > \tau_h$), while the causal mask $\mathbf{M}$ restricts queries to antecedent electrophysiology ($\delta_{ij} \ge 0$\,s)."""

content = replace_chunk(content, old_prior_desc, new_prior_desc)
print("Section III-D prior description replaced successfully.")

# 5. Polish Section IV Ethical Approval heading hierarchy
old_ethics_head = r"""\subsubsection{Ethical Approval and Participant Consent}"""
new_ethics_head = r"""\subsection{Ethical Approval and Participant Consent}"""

content = replace_chunk(content, old_ethics_head, new_ethics_head)
print("Section IV Ethical Approval heading updated to subsection.")

# 6. Fix Underfull \hbox in Section IV-D (External Evaluation Paradigms)
old_ext_intro = r"""To evaluate task transfer across distinct neurocognitive and sensorimotor regimes, we benchmarked two independent external cohorts comprising 3,612 held-out trials under identical participant-isolated LOSO protocols with standardized 10.0\,s EEG (1,000 samples at 100\,Hz) and 12.0\,s fNIRS observation windows (124 samples at 10.33\,Hz):"""
new_ext_intro = r"""To evaluate task transfer across distinct neurocognitive and sensorimotor regimes, we evaluated two independent external cohorts comprising 3,612 held-out trials under participant-isolated LOSO cross-validation with standardized 10.0\,s EEG (1,000 samples at 100\,Hz) and 12.0\,s fNIRS observation windows (124 samples at 10.33\,Hz):"""

content = replace_chunk(content, old_ext_intro, new_ext_intro)
print("Section IV External intro updated.")

# 7. Fix Underfull \hbox in Section VI-B (Discussion)
old_disc_b = r"""Contextualized with modern BCI architectures, NVC-DelayFormer achieves high parameter efficiency: with 63,940 parameters, it operates with $17.5\times$ fewer weights than EEG Conformer (1.12\,M) and $1.8\times$ fewer than ATCNet (115.2\,k), while processing both 30-channel EEG and 72-channel fNIRS streams simultaneously. Forward GPU latency of 2.22\,ms (P99: 4.48\,ms, 24.84\,M MACs) demonstrates that computational overhead is negligible compared to physical sensor accumulation intervals, satisfying requirements for closed-loop clinical BCI operation."""
new_disc_b = r"""Contextualized with modern deep BCI architectures, NVC-DelayFormer achieves notable parameter efficiency: with 63,940 weights, it operates with $17.5\times$ fewer parameters than EEG Conformer (1.12\,M) and $1.8\times$ fewer than ATCNet (115.2\,k), while concurrently processing 30-channel EEG and 72-channel optical streams. A forward GPU latency of 2.22\,ms (P99: 4.48\,ms, 24.84\,M MACs) confirms that computational overhead remains negligible relative to physical sensor acquisition windows, satisfying requirements for closed-loop bedside deployment."""

content = replace_chunk(content, old_disc_b, new_disc_b)
print("Section VI-B Discussion updated.")

with open('manuscript/main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("All modifications written to manuscript/main.tex successfully.")
