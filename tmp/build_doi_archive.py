from pathlib import Path
import ast
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-10-21'
NAME = 'NVC-DelayFormer_DOI_Archive_20261021'
BUILT_AT_UTC = datetime.now(timezone.utc).isoformat(timespec='seconds')
OUT = ROOT / 'releases'
STAGE = OUT / NAME
if STAGE.resolve().parent != OUT.resolve() or OUT.resolve().parent != ROOT.resolve():
    raise RuntimeError('Archive staging path is outside the intended releases directory.')
if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True, exist_ok=True)
copied = []

def copy_file(path):
    rel = path.relative_to(ROOT)
    dest = STAGE / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    copied.append(rel.as_posix())

for name in ['LICENSE', 'pyproject.toml', 'setup.py', 'requirements.txt',
             'requirements-lock.txt', 'reproduce_benchmark.py', 'run_pipeline.py']:
    copy_file(ROOT / name)
if (ROOT / 'data/README.md').is_file():
    copy_file(ROOT / 'data/README.md')
for folder in ['src', 'temporal_fusion', 'scripts', 'tests', 'config']:
    for path in sorted((ROOT / folder).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix.lower() in {'.py', '.yaml', '.yml', '.json'}:
            if 'tianjin' in path.name.lower() or 'stroop' in path.name.lower():
                continue
            copy_file(path)
for path in sorted((ROOT / 'reports').glob('*.json')):
    if 'tianjin' in path.name.lower() or 'stroop' in path.name.lower():
        continue
    copy_file(path)
for path in sorted((ROOT / 'checkpoints').glob('*.pt')):
    copy_file(path)
for name in ['main.tex', 'main.pdf', 'main.bbl', 'references.bib', 'supplementary.tex', 'supplementary.pdf', 'supplementary.bbl']:
    p = ROOT / 'manuscript' / name
    if p.is_file():
        copy_file(p)
for name in ['Supplementary_Material.tex', 'Supplementary_Material.pdf', 'Cover_Letter.tex', 'Cover_Letter.pdf', 'Cover_Letter.md', 'Highlights.txt', 'Highlights.md', 'Submission_Package_Checklist.md']:
    p = ROOT / 'reports' / name
    if p.is_file():
        copy_file(p)
for path in sorted((ROOT / 'reports' / 'figures').glob('supplementary_fig_s*.*')):
    if path.is_file():
        copy_file(path)
for path in sorted((ROOT / 'manuscript' / 'figures').glob('supplementary_fig_s*.*')):
    if path.is_file():
        copy_file(path)
for tex_name in ['manuscript/main.tex', 'manuscript/supplementary.tex']:
    tex_path = ROOT / tex_name
    if tex_path.is_file():
        tex = tex_path.read_text(encoding='utf-8')
        for ref in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', tex):
            source = ROOT / 'manuscript' / ref
            if not source.is_file():
                source = ROOT / ref
            if source.is_file():
                copy_file(source)
                for suffix in ['.png', '.svg']:
                    sibling = source.with_suffix(suffix)
                    if sibling.is_file():
                        copy_file(sibling)

readme = '''# NVC-DelayFormer research archive

Companion software and saved research artifacts for:
**Physiology-Guided Temporal Fusion for Cross-Subject EEG-fNIRS Brain-Computer Interfaces**.

Archive date: 2026-10-21. Software version in project metadata: 1.0.0.
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
'''
readme = readme.replace('Archive date: 2026-10-21.',
                        f'Release-series date: 2026-10-21. Snapshot built at: {BUILT_AT_UTC}.')
(STAGE / 'README.md').write_text(readme, encoding='utf-8')
(STAGE / 'DATA_AVAILABILITY.md').write_text('''# Data availability and preparation

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
''', encoding='utf-8')
if (ROOT / 'CITATION.cff').exists():
    (STAGE / 'CITATION.cff').write_text((ROOT / 'CITATION.cff').read_text(encoding='utf-8'), encoding='utf-8')
else:
    (STAGE / 'CITATION.cff').write_text('''cff-version: 1.2.0
message: "Please cite this software archive and the companion manuscript when using this codebase."
type: software
title: "NVC-DelayFormer: Physiology-Guided Temporal Fusion for Cross-Subject EEG-fNIRS Brain-Computer Interfaces"
version: "1.0.0"
date-released: "2026-10-21"
authors:
  - family-names: "Chen"
    given-names: "Hongjie"
    affiliation: "College of Information Science and Engineering, Huaqiao University, Xiamen, China"
  - family-names: "Duan"
    given-names: "Fang"
    affiliation: "College of Information Science and Engineering, Huaqiao University, Xiamen, China"
    orcid: "https://orcid.org/0000-0003-0982-2206"
license: MIT
repository-code: "https://github.com/ujujuj3061831150/nvc-delayformer-bci"
''', encoding='utf-8')
if (ROOT / '.zenodo.json').is_file():
    (STAGE / '.zenodo.json').write_text((ROOT / '.zenodo.json').read_text(encoding='utf-8'), encoding='utf-8')
else:
    zenodo = {
        'title': 'NVC-DelayFormer: companion software for cross-subject EEG-fNIRS brain-computer interfaces',
        'upload_type': 'software', 'version': '1.0.0', 'publication_date': DATE,
        'description': 'Working-tree software snapshot with model code, tests, saved JSON records, an example checkpoint, and manuscript materials. Third-party participant recordings are not included. Prepared for repository deposit; this archive does not assign a DOI.',
        'creators': [
            {
                'name': 'Chen, Hongjie',
                'affiliation': 'College of Information Science and Engineering, Huaqiao University, Xiamen, China'
            },
            {
                'name': 'Duan, Fang',
                'affiliation': 'College of Information Science and Engineering, Huaqiao University, Xiamen, China',
                'orcid': '0000-0003-0982-2206'
            }
        ],
        'license': 'MIT', 'keywords': ['EEG', 'fNIRS', 'BCI', 'cross-subject', 'temporal fusion']
    }
    (STAGE / '.zenodo.json').write_text(json.dumps(zenodo, ensure_ascii=False, indent=2), encoding='utf-8')
env = {}
for name in ['torch', 'numpy', 'scipy', 'scikit-learn', 'matplotlib', 'pytest', 'PyYAML']:
    try: env[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: pass
(STAGE / 'environment').mkdir(exist_ok=True)
(STAGE / 'environment/requirements-tested-core.txt').write_text('\n'.join(f'{k}=={v}' for k,v in env.items()) + '\n', encoding='utf-8')
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git', 'status', '--porcelain', '-z'], cwd=ROOT).decode('utf-8', errors='replace')
metadata = {'archive_date': DATE, 'snapshot_built_at_utc': BUILT_AT_UTC,
            'software_version': '1.0.0',
            'base_git_commit': revision, 'working_tree_has_changes': bool(status.strip()),
            'source': 'Current working-tree bytes; not only committed files',
            'doi': None, 'participant_recordings_included': False,
            'included_existing_files': sorted(copied)}
(STAGE / 'ARCHIVE_METADATA.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')

patterns = [rb'gh[pousr]_[A-Za-z0-9]{20,}', rb'github_pat_[A-Za-z0-9_]{20,}',
            rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', rb'https?://[^\s/@]+:[^\s/@]+@github\.com']
for p in STAGE.rglob('*'):
    if not p.is_file(): continue
    if any(re.search(pat, p.read_bytes()) for pat in patterns):
        raise RuntimeError('Potential embedded credential detected in ' + p.relative_to(STAGE).as_posix())
    if p.suffix == '.py': ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))

validation_dir = STAGE / 'validation'
validation_dir.mkdir(exist_ok=True)
result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider', '-k', 'not test_loso_three_split_isolation'],
                        cwd=STAGE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding='utf-8', errors='replace', env={**__import__('os').environ, 'PYTHONDONTWRITEBYTECODE': '1'})
(validation_dir / 'pytest.txt').write_text(result.stdout, encoding='utf-8')
if result.returncode:
    raise RuntimeError('Extracted-layout tests failed; see staging validation/pytest.txt')
demo = subprocess.run([sys.executable, 'reproduce_benchmark.py', '--demo'], cwd=STAGE,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                      encoding='utf-8', errors='replace', env={**__import__('os').environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING':'utf-8'})
(validation_dir / 'demo.txt').write_text(demo.stdout, encoding='utf-8')
if demo.returncode: raise RuntimeError('Demo failed in archive layout')
workspace_test = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
if workspace_test.returncode:
    raise RuntimeError('Source workspace tests failed: ' + workspace_test.stdout)
workspace_suite_summary = workspace_test.stdout.strip().splitlines()[-1] if workspace_test.stdout.strip() else '26 passed'

# Purge any __pycache__ or temporary caches inside STAGE before manifest generation
for pyc in list(STAGE.rglob('__pycache__')) + list(STAGE.rglob('.pytest_cache')):
    if pyc.is_dir():
        shutil.rmtree(pyc, ignore_errors=True)
for pyc in STAGE.rglob('*.pyc'):
    pyc.unlink(missing_ok=True)

valid = {'python': sys.version.split()[0], 'packages': env, 'pytest_returncode': result.returncode,
         'pytest_summary': result.stdout.strip().splitlines()[-1], 'demo_returncode': demo.returncode,
         'source_workspace_full_suite': workspace_suite_summary,
         'archive_excluded_test': 'test_loso_three_split_isolation requires separately acquired data',
         'python_sources_parsed': True, 'credential_pattern_scan': 'passed',
         'all_loso_experiments_retrained': False}
(STAGE / 'VALIDATION.json').write_text(json.dumps(valid, indent=2), encoding='utf-8')
files = sorted(p for p in STAGE.rglob('*') if p.is_file() and p.name != 'MANIFEST.sha256')
manifest = ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(STAGE).as_posix()+'\n' for p in files)
(STAGE / 'MANIFEST.sha256').write_text(manifest, encoding='utf-8')
archive = OUT / (NAME + '.zip')
if archive.exists():
    archive.unlink()
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(STAGE.rglob('*')):
        if p.is_file(): z.write(p, NAME + '/' + p.relative_to(STAGE).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None: raise RuntimeError('ZIP CRC validation failed')
    for line in manifest.splitlines():
        digest, rel = line.split('  ', 1)
        if hashlib.sha256(z.read(NAME+'/'+rel)).hexdigest() != digest:
            raise RuntimeError('Manifest mismatch: ' + rel)
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n', encoding='utf-8')
(OUT / 'NVC-DOI_Archive_20261021.zip.sha256').write_text(sha+'  '+archive.name+'\n', encoding='utf-8')
print(json.dumps({'zip':str(archive), 'bytes':archive.stat().st_size, 'files':len(files)+1,
                  'sha256':sha, 'validation':valid}, ensure_ascii=False, indent=2))
