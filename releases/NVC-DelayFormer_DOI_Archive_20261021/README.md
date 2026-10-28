# NVC-DelayFormer research archive

Companion software and saved research artifacts for:
**Physiology-Guided Temporal Fusion for Cross-Subject EEG-fNIRS Brain-Computer Interfaces**.

Release-series date: 2026-10-21. Snapshot built at: 2026-10-28T13:05:01+00:00. Software version in project metadata: 1.0.0.
This is a snapshot of the current working files, including uncommitted changes.
It is prepared for a DOI repository deposit; no DOI has been assigned by this ZIP.

## Contents

- `temporal_fusion/`: installable model package.
- `src/`: research models, training, preprocessing and dataset acquisition code.
- `reproduce_benchmark.py`: command-line verification, demo, profiling and training entry point.
- `tests/`, `config/`: tests and configuration files.
- `scripts/`: current analysis and figure scripts, including historical utility scripts.
- `reports/`: saved JSON records as present in the workspace. Some records describe earlier experiments;
  filenames and timestamps identify their provenance. Their inclusion is not a new scientific validation.
- `checkpoints/`: available example checkpoint; not a complete collection of all LOSO-fold weights.
- `manuscript/`: latest main PDF, LaTeX, bibliography and figures referenced by that LaTeX file.
- `CITATION.cff`, `.zenodo.json`: citation and deposit metadata copied from current project identity.
- `ARCHIVE_METADATA.json`, `VALIDATION.json`, `MANIFEST.sha256`: snapshot provenance, checks and file hashes.

## Installation and basic checks

Run commands from this extracted archive directory. Python 3.11 is the packaging test environment.

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest tests -q -k "not test_loso_three_split_isolation"
python reproduce_benchmark.py --demo
```

`requirements-lock.txt` is the existing full environment snapshot, not a minimal portable dependency list.
`environment/requirements-tested-core.txt` records relevant package versions present during archive checks;
CUDA availability and GPU timing depend on the receiving machine.

`--benchmark` displays saved records; it does not retrain all models.
`--train-fold`, `--train-all`, checkpoint evaluation and dataset-dependent analyses require separately
acquired/preprocessed data. Consult `DATA_AVAILABILITY.md` before those commands.
Small unit tests or synthetic demonstrations do not revalidate every manuscript result.
The excluded LOSO-loader test requires participant tensor files. After preparing data,
run `python -m pytest tests -q` to include it. See `VALIDATION.json` for the current source-workspace and archive-only test results.

## DOI deposit

Upload the ZIP to your chosen research repository as a software/research-artifact deposit.
Use the included metadata as a starting point and confirm creator names, affiliations, license scope,
and the desired release version in the repository form. The creators are Hongjie Chen and Fang Duan, as recorded in the project citation metadata. Do not invent a publication DOI or mark the manuscript as accepted.
When the repository assigns a DOI, add that DOI to its citation record and future releases.

## License and integrity

The existing repository MIT license is included unchanged. Third-party datasets retain their original
terms and are not redistributed here. This archive omits raw/processed participant recordings,
Git history and configuration, credentials, caches, build outputs, audit conversations and older PDF copies.
Verify `MANIFEST.sha256` after extraction; the external `.zip.sha256` checks the ZIP itself.
