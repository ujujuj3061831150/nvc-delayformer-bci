# Data availability and preparation

Participant EEG/fNIRS recordings (both raw files and processed tensor caches) are not included.
Acquire them from their original providers under the original access and reuse terms.

- Shin et al. (2017), Open Access Dataset for EEG+NIRS Single-Trial Classification:
  https://doi.org/10.1109/TNSRE.2016.2628057
  Mental arithmetic and motor imagery are tasks from this dataset.
- Shin et al. (2018), Simultaneous acquisition of EEG and NIRS during cognitive tasks:
  https://doi.org/10.1038/sdata.2018.3

The archive preserves dataset acquisition and parsing source in `src/data/`.
Inspect provider paths and parser requirements before running download jobs:

```bash
python -m src.data.download_real_tuberlin
python -m src.data.batch_parse_real 29
```

The MA training entry point expects `data/processed/sub-XX/ma_epochs.pt`.
The external parsers are `parse_shin2017_mi.py` and `parse_shin2018_nback.py`.
Do not replace recordings with synthetic demos when reporting benchmark results.
The example checkpoint requires matching processed data for evaluation.
