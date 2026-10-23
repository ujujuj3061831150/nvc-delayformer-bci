# Benchmark Datasets and Data Provenance

This directory contains preprocessed multimodal EEG–fNIRS benchmark datasets accompanying the manuscript:  
**"Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces"** (*IEEE Transactions on Biomedical Engineering*).

---

## 1. Primary Benchmark: TU Berlin Mental Arithmetic Dataset

The primary benchmark evaluated across all 29 subjects in this repository is derived from the open-access simultaneous EEG–fNIRS dataset collected by Technische Universität Berlin:

- **Original Authors**: Jaeyoung Shin, Alexander von Lühmann, Benjamin Blankertz, Do-Won Kim, Jichai Jeong, Han-Jeong Hwang, and Klaus-Robert Müller.
- **Reference**:  
  J. Shin, A. von Lühmann, B. Blankertz, D.-W. Kim, J. Jeong, H.-J. Hwang, and K.-R. Müller,  
  *"Open Access Dataset for EEG+NIRS Single-Trial Classification,"*  
  **IEEE Transactions on Neural Systems and Rehabilitation Engineering**, vol. 25, no. 10, pp. 1735–1745, Oct. 2017.  
  DOI: [10.1109/TNSRE.2016.2628057](https://doi.org/10.1109/TNSRE.2016.2628057)
- **Official Data Portal**: [https://doc.ml.tu-berlin.de/hBCI/](https://doc.ml.tu-berlin.de/hBCI/)
- **Ethical Approval**: Approved by the Ethics Committee of the Institute of Psychology and Ergonomics, Technische Universität Berlin (Protocol SH_01_20150330).

---

## 2. Processed Data Specifications (`data/processed/`)

The repository includes preprocessed epochs for all 29 participants (`sub-01` through `sub-29`) under `data/processed/sub-XX/ma_epochs.pt`. Each file contains a serialized PyTorch dictionary with keys:

| Key | Tensor Shape | Sampling Rate | Description |
| :--- | :--- | :--- | :--- |
| `eeg` | `[60, 30, 1000]` (Float32) | 100 Hz | 30 scalp electrodes (10–5 montage), 10.0 s epochs ($t \in [0, 10]\,\text{s}$). Bandpass filtered at 0.5–45 Hz (zero-phase 4th-order Butterworth) and re-referenced via Common Average Reference (CAR). |
| `fnirs` | `[60, 72, 124]` (Float32) | 10.33 Hz | 36 optical channels $\times$ 2 chromophores (36 $\Delta[\text{HbO}]$ + 36 $\Delta[\text{HbR}]$), 12.0 s epochs ($t \in [0, 12]\,\text{s}$). Converted from raw optical density via Modified Beer-Lambert Law (MBLL, differential pathlength factor $\text{DPF} = 6.51\,(760\,\text{nm})\,/\,5.86\,(850\,\text{nm})$), bandpass filtered at 0.01–0.10 Hz. |
| `labels` | `[60]` (Long) | — | Binary ground-truth labels: `0` = Baseline / Rest, `1` = Mental Arithmetic. |

### Note on File Size Uniformity
Because all 29 files contain identical uncompressed 32-bit floating-point tensor dimensions ($60 \times 30 \times 1000$ EEG elements and $60 \times 72 \times 124$ fNIRS elements) serialized via `torch.save`, each `.pt` file has an identical byte size on disk ($9,346,355$ bytes). This is a mathematical property of uncompressed array serialization, and each subject's data reflects distinct, authentic physiological recordings with significant inter-subject variance (verified via `python reproduce_benchmark.py --verify-data`).

---

## 3. External Validation Datasets

To evaluate cross-paradigm generalizability (reported in Table V of the manuscript), two additional cohorts are analyzed:
1. **Motor Imagery (Shin 2017 MI)**: Same 29 participants, 60 trials/participant (left-hand vs. right-hand motor imagery), collected under identical hardware settings (DOI: [10.1109/TNSRE.2016.2628057](https://doi.org/10.1109/TNSRE.2016.2628057)).
2. **Working Memory / $n$-back (Shin et al. 2018)**: 26 participants, 72 block-derived 10.0 s epochs per participant (0-back vs. 2-back working memory load), DOI: [10.1038/sdata.2018.3](https://doi.org/10.1038/sdata.2018.3).

---

## 4. Licensing and Distribution Terms

- **Source Code, Architecture, and Reproduction Scripts**: Licensed under the **MIT License** (see [LICENSE](../LICENSE)).
- **Preprocessed Benchmark Datasets**: Provided strictly for academic verification and computational reproducibility. The underlying raw and processed benchmark data are governed by the **GNU General Public License (GNU GPL)** as published by the Free Software Foundation and stipulated by the original TU Berlin data distribution portal ([https://doc.ml.tu-berlin.de/hBCI/](https://doc.ml.tu-berlin.de/hBCI/)). Any redistribution or downstream scientific use must comply with GNU GPL terms and cite the original publication (Shin et al., 2017).
