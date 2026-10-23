"""
Script to apply comprehensive fixes to manuscript/main.tex:
- Citations aligned with the 36 clean verified references in references.bib
- Eq. (12) Ridge Regularization for CAR invertibility
- Cohort definition accuracy (Shin 2018 independent cohort vs Shin 2017 cross-task)
- Shin 2018 28 EEG + 2 EOG disclosure
- Figure 2(e) schematic framing and authentic TU Berlin electrode positions
- Remove -4.2pt negative bibitemsep to eliminate overlapping references
"""

with open('manuscript/main.tex', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Abstract cohort update
old_abs_cohort = r"""Benchmarked across two external cohorts comprising 3,612 held-out trials, the architecture demonstrates robust multi-paradigm transfer: 73.77\% on $n$-back working memory and 66.32\% on motor imagery."""
new_abs_cohort = r"""Benchmarked across two distinct task paradigms (3,612 held-out trials total, including an independent external cohort of 26 participants for $n$-back working memory and a cross-task evaluation on 29 participants for motor imagery), the architecture demonstrates robust transfer: 73.77\% on $n$-back and 66.32\% on motor imagery."""

text = text.replace(old_abs_cohort, new_abs_cohort)

# 2. Intro citations
text = text.replace(
    r"\cite{fazli2012enhanced, shin2017open, li2022hybrid, zhang2024multimodal}",
    r"\cite{fazli2012enhanced, shin2017open, li2022hybrid}"
)
text = text.replace(
    r"\cite{he2020transfer, zanini2018transfer, yger2017review, congedo2017riemannian}",
    r"\cite{he2020transfer, zanini2018transfer, yger2017review}"
)
text = text.replace(
    r", and modern convolutional variants like EEGConvNeXt \cite{acharya2025eegconvnext} extract spatial filters across scalp montages.",
    r" extract spatial filters across scalp montages."
)
text = text.replace(
    r"\cite{vaswani2017attention, wang2023cross}",
    r"\cite{vaswani2017attention}"
)
text = text.replace(
    r"Furthermore, evaluation across two independent external cohorts (3,612 held-out trials) demonstrates robust multi-paradigm transfer (73.77\% on $n$-back Working Memory, 66.32\% on Motor Imagery) with 2.22\,ms median GPU latency.",
    r"Furthermore, evaluation across two distinct task paradigms (3,612 held-out trials total, including an independent external cohort of 26 participants for $n$-back working memory and a cross-task evaluation on 29 participants for motor imagery) demonstrates robust transfer (73.77\% on $n$-back, 66.32\% on motor imagery) with 2.22\,ms median GPU latency."
)

# 3. Related Work citations
old_rw2 = r"""Recent architectures incorporate attention and transformers: ATCNet \cite{altaheri2023atcnet} combines temporal convolutions with self-attention; EEG Conformer \cite{song2022eeg} fuses local convolutions with global self-attention; EEGConvNeXt \cite{acharya2025eegconvnext} and lightweight transformers \cite{salim2023lightweight} improve biomarker identification and seizure detection; while self-supervised methods \cite{kostas2021bendr, banville2021robust} extract robust representations from large-scale archives. For optical imaging, fNIRSNET \cite{pandey2024fnirsnet} separates hemoglobin dynamics through multi-view convolutions. In multimodal fusion, early deep models applied parallel feature concatenation \cite{yin2020locally, sun2022multi}. Recent networks introduce dedicated cross-modal interaction: FGANet \cite{kwak2022fganet} guides electrophysiology with optical dynamics; EFMLNet \cite{sun2023efmlnet} enforces mutual information learning; MBC-ATT \cite{li2024mbcatt} deploys bidirectional attentional fusion; Wang et al.\ \cite{wang2023cross} apply cross-modal transformers; and Shapley attribution \cite{perez2024unraveling} reveals functional neural interactions."""

new_rw2 = r"""Recent architectures incorporate attention and transformers: ATCNet \cite{altaheri2023atcnet} combines temporal convolutions with self-attention, while EEG Conformer \cite{song2022eeg} fuses local convolutions with global self-attention. For optical imaging, fNIRSNet \cite{pandey2024fnirsnet} separates hemoglobin dynamics through multi-view convolutions. In multimodal fusion, early deep models applied parallel feature concatenation \cite{yin2020locally}. Recent networks introduce dedicated cross-modal interaction: FGANet \cite{kwak2022fganet} guides electrophysiology with optical dynamics; EFMLNet \cite{sun2023efmlnet} enforces mutual information learning; and MBC-ATT \cite{li2024mbcatt} deploys bidirectional attentional fusion."""

text = text.replace(old_rw2, new_rw2)

text = text.replace(
    r"\cite{attwell2010glial, iadecola2004neurovascular, girouard2006neurovascular}",
    r"\cite{attwell2010glial, iadecola2004neurovascular}"
)

# 4. Section IV-B CrEA formula and Ridge Regularization (C06)
old_crea_desc = r"""where $\mathbf{R}_{\mathrm{src}}$ is mean resting covariance from training participants, $\kappa_0 = 5$ acts as pseudo-trial shrinkage weight, and $\mathbf{C}_m = \frac{1}{T_e}\mathbf{X}_m\mathbf{X}_m^\top$ denotes single-trial sample covariance."""
new_crea_desc = r"""where $\mathbf{R}_{\mathrm{src}}$ is mean resting covariance from training participants, $\kappa_0 = 5$ acts as pseudo-trial shrinkage weight, and $\mathbf{C}_m = \frac{1}{T_e}\mathbf{X}_m\mathbf{X}_m^\top + \epsilon\mathbf{I}$ denotes single-trial sample covariance with ridge parameter $\epsilon = 10^{-5}$ guaranteeing positive definiteness and invertibility under Common Average Referencing (CAR)."""

text = text.replace(old_crea_desc, new_crea_desc)

# 5. Section IV-C Baselines text
text = text.replace(
    r"Feature-Concat \cite{yin2020locally, sun2022multi} and Standard-Attention \cite{wang2023cross}",
    r"Feature-Concat \cite{yin2020locally} and Standard-Attention \cite{vaswani2017attention}"
)

# 6. Table I citation updates
text = text.replace(
    r"Feature-Concat (Multi-View Hybrid CNN) \cite{yin2020locally, sun2022multi}",
    r"Feature-Concat (Multi-View Hybrid CNN) \cite{yin2020locally}"
)
text = text.replace(
    r"Standard-Attention (Cross-Modal Transformer) \cite{wang2023cross}",
    r"Standard-Attention (Cross-Modal Transformer) \cite{vaswani2017attention}"
)
text = text.replace(
    r"\multicolumn{6}{l}{\textbf{Recent Deep Multimodal SOTA (2022--2024)}}",
    r"\multicolumn{6}{l}{\textbf{Recent Deep Multimodal Baselines (2022--2025)}}"
)
text = text.replace(
    r"EFMLNet (Sun et al.\ 2023) \cite{sun2023efmlnet}",
    r"EFMLNet (Sun et al.\ 2025) \cite{sun2023efmlnet}"
)
text = text.replace(
    r"MBC-ATT (Li et al.\ 2024) \cite{li2024mbcatt}",
    r"MBC-ATT (Li et al.\ 2025) \cite{li2024mbcatt}"
)

# 7. Section IV-D Shin 2018 EEG + EOG disclosure (C04)
old_nback_desc = r"""\item \textbf{$n$-back Working Memory:} 0-back sensory target matching versus 2-back working memory updating (26 participants, 1,872 trials; 30 EEG channels, 72 fNIRS channels) from Shin et al.\ (2018) \cite{shin2018simultaneous};"""
new_nback_desc = r"""\item \textbf{$n$-back Working Memory:} 0-back sensory target matching versus 2-back working memory updating (26 participants, 1,872 block-derived trials; 30 electrophysiological channels comprising 28 scalp EEG channels and 2 bipolar EOG channels [HEOG, VEOG], and 72 fNIRS channels) from Shin et al.\ (2018) \cite{shin2018simultaneous};"""

text = text.replace(old_nback_desc, new_nback_desc)

# 8. Figure 2 caption and text (C01, C02)
old_fig2_cap = r"""(e) Cortical cross-modal spatial coupling topographies: prefrontal coupling (PFC: Fp1/AFz/Fp2 $\leftrightarrow$ Ch01--Ch08) between frontal midline $\theta$ ERS and capillary $\Delta[\mathrm{HbO}]$ hyperoxygenation in mental arithmetic versus bilateral sensorimotor coupling (SMC: C3/C4 $\leftrightarrow$ Ch17--Ch36) between $\mu/\beta$ ERD and motor hemodynamics in motor imagery."""
new_fig2_cap = r"""(e) Neurovascular functional coupling schematics across task regimes: prefrontal cognitive executive activation (PFC: AFp1/AFp2/AFF1h/AFF2h $\leftrightarrow$ Ch01--Ch08) coupling frontal midline $\theta$ ERS with capillary $\Delta[\mathrm{HbO}]$ hyperoxygenation in mental arithmetic, versus bilateral sensorimotor coordination (SMC: FCC3h/CCP3h $\leftrightarrow$ Ch17--Ch36) coupling $\mu/\beta$ ERD with motor hemodynamics in motor imagery."""

text = text.replace(old_fig2_cap, new_fig2_cap)

# 9. Section V-C text (C02, M05)
old_scan_delta = r"""Collapsing latency to $\bar{\tau} = 0$\,s degraded accuracy to 75.34\% $\pm$ 8.35\% ($\Delta = -4.14$\,pp, $p = 0.0036$), proving that enforcing physiological delay precedence is critical."""
new_scan_delta = r"""Collapsing latency to $\bar{\tau} = 0$\,s degraded accuracy to 75.34\% $\pm$ 8.35\% ($\Delta = -4.02$\,pp, $p = 3.67\times 10^{-4}$ vs.\ full model), confirming that enforcing physiological delay precedence is critical."""

text = text.replace(old_scan_delta, new_scan_delta)

old_topo_desc = r"""Cortical spatial coupling topographies (Fig.~\ref{fig:diagnostics}e) illustrate distinct functional circuits across domains:
\textit{1) Cognitive executive control (Mental Arithmetic):} Cross-modal attention concentrates over prefrontal cortex (PFC: Fp1, AFz, Fp2 $\leftrightarrow$ Ch01--Ch08), where frontal midline theta synchronization ($\theta$ ERS, 4--8\,Hz) couples with localized capillary hyperoxygenation ($\Delta[\mathrm{HbO}]$ elevation and $\Delta[\mathrm{HbR}]$ washout), reflecting working memory load and executive maintenance mediated by anterior cingulate and dorsolateral prefrontal cortex (dlPFC) \cite{gevins1997high}.
\textit{2) Sensorimotor lateralization (Motor Imagery):} Cross-modal attention shifts bilaterally to sensorimotor cortex (SMC: C3, C4 $\leftrightarrow$ Ch17--Ch36). Kinesthetic movement imagination elicits focal sensorimotor $\mu$ (8--12\,Hz) and $\beta$ (13--30\,Hz) desynchronization (ERD) over contralateral motor strip (C3 for right hand, C4 for left hand) \cite{pfurtscheller1999event, mcfarland2000mu}, accompanied by contralateral capillary hyperoxygenation and ipsilateral suppression."""

new_topo_desc = r"""Neurovascular functional coupling schematics (Fig.~\ref{fig:diagnostics}e) illustrate distinct regional circuits across domains:
\textit{1) Cognitive executive control (Mental Arithmetic):} Functional coupling aligns over the prefrontal cortex (PFC: AFp1, AFp2, AFF1h, AFF2h $\leftrightarrow$ Ch01--Ch08), where frontal midline theta synchronization ($\theta$ ERS, 4--8\,Hz) couples with localized capillary hyperoxygenation ($\Delta[\mathrm{HbO}]$ elevation and $\Delta[\mathrm{HbR}]$ washout), reflecting working memory load and executive maintenance mediated by anterior cingulate and dorsolateral prefrontal cortex (dlPFC) \cite{gevins1997high}.
\textit{2) Sensorimotor lateralization (Motor Imagery):} Functional coupling shifts bilaterally to the sensorimotor cortex (SMC: FCC3h, CCP3h, FCC4h, CCP4h $\leftrightarrow$ Ch17--Ch36). Kinesthetic movement imagination elicits focal sensorimotor $\mu$ (8--12\,Hz) and $\beta$ (13--30\,Hz) desynchronization (ERD) over the contralateral motor strip (FCC3h/CCP3h for right hand, FCC4h/CCP4h for left hand) \cite{pfurtscheller1999event, mcfarland2000mu}, accompanied by localized capillary hyperoxygenation and ipsilateral suppression."""

text = text.replace(old_topo_desc, new_topo_desc)

# 10. Table IV and Section V-E citations
text = text.replace(
    r"Feature-Concat \cite{yin2020locally, sun2022multi} & 23,682 & 17.74 & 0.80 & 2.07 \\",
    r"Feature-Concat \cite{yin2020locally} & 23,682 & 17.74 & 0.80 & 2.07 \\"
)
text = text.replace(
    r"Standard-Attention \cite{wang2023cross} & 40,450 & 24.80 & 1.37 & 2.90 \\",
    r"Standard-Attention \cite{vaswani2017attention} & 40,450 & 24.80 & 1.37 & 2.90 \\"
)

# 11. Section VI-C text (C02)
old_vic_topo = r"""Topographic mapping of learned cross-modal attention reveals distinct cortical networks across paradigms without manual channel pre-selection (Fig.~\ref{fig:diagnostics}e). In mental arithmetic, cross-modal attention weights concentrate selectively over the prefrontal cortex (PFC: Fp1, AFz, Fp2 $\leftrightarrow$ Ch01--Ch08). During continuous calculation, frontal midline theta event-related synchronization ($\theta$ ERS, 4--8\,Hz) reflects working memory load and executive maintenance mediated by the anterior cingulate cortex and dorsolateral prefrontal cortex (dlPFC) \cite{gevins1997high}. Concurrently, elevated metabolic oxygen consumption triggers local astrocytic and pericyte signaling, driving delayed capillary hyperemia characterized by pronounced $\Delta[\mathrm{HbO}]$ elevation and $\Delta[\mathrm{HbR}]$ washout \cite{attwell2010glial, iadecola2004neurovascular}. The learned attention mechanism captures this temporal-topographic contingency, coupling the sustained prefrontal electrical oscillation with downstream vascular hyperoxygenation.

In contrast, during kinesthetic motor imagery, cross-modal attention automatically shifts bilaterally to the sensorimotor cortex (SMC: C3, C4 $\leftrightarrow$ Ch17--Ch36). Unilateral hand movement imagination suppresses idling rhythms in the contralateral primary motor cortex (M1) and primary somatosensory cortex (S1), producing focal sensorimotor $\mu$ (8--12\,Hz) and $\beta$ (13--30\,Hz) event-related desynchronization (ERD) \cite{pfurtscheller1999event, mcfarland2000mu}. This neuronal activation increases local oxygen extraction, producing localized capillary hyperoxygenation over the contralateral motor strip alongside relative ipsilateral deoxygenation."""

new_vic_topo = r"""Functional mapping of neurovascular coupling illustrates distinct regional circuits across paradigms without manual channel pre-selection (Fig.~\ref{fig:diagnostics}e). In mental arithmetic, biophysical coupling aligns over the prefrontal cortex (PFC: AFp1, AFp2, AFF1h, AFF2h $\leftrightarrow$ Ch01--Ch08). During continuous calculation, frontal midline theta event-related synchronization ($\theta$ ERS, 4--8\,Hz) reflects working memory load and executive maintenance mediated by the anterior cingulate cortex and dorsolateral prefrontal cortex (dlPFC) \cite{gevins1997high}. Concurrently, elevated metabolic oxygen consumption triggers local astrocytic and pericyte signaling, driving delayed capillary hyperemia characterized by pronounced $\Delta[\mathrm{HbO}]$ elevation and $\Delta[\mathrm{HbR}]$ washout \cite{attwell2010glial, iadecola2004neurovascular}. The temporal fusion mechanism captures this physiological contingency, coupling sustained prefrontal electrical oscillations with downstream vascular hyperoxygenation.

In contrast, during kinesthetic motor imagery, physiological coupling shifts bilaterally to the sensorimotor cortex (SMC: FCC3h, CCP3h, FCC4h, CCP4h $\leftrightarrow$ Ch17--Ch36). Unilateral hand movement imagination suppresses idling rhythms in the contralateral primary motor cortex (M1) and primary somatosensory cortex (S1), producing focal sensorimotor $\mu$ (8--12\,Hz) and $\beta$ (13--30\,Hz) event-related desynchronization (ERD) \cite{pfurtscheller1999event, mcfarland2000mu}. This neuronal activation increases local oxygen extraction, producing localized capillary hyperoxygenation over the contralateral motor strip alongside relative ipsilateral deoxygenation."""

text = text.replace(old_vic_topo, new_vic_topo)

# 12. Bibliography spacing: replace -4.2pt with 0pt (C08)
text = text.replace(
    r"\def\IEEEbibitemsep{-4.2pt plus 0.5pt}",
    r"\def\IEEEbibitemsep{0pt plus 0.5pt}"
)

with open('manuscript/main.tex', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied paper fixes successfully.")
