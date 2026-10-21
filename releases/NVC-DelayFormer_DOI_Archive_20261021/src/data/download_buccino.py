"""
Resilient Downloader & Extractor for Buccino et al. 2016 Hybrid EEG-fNIRS Dataset.
Fetches public Figshare archives:
- S1-S8:  https://ndownloader.figshare.com/files/2601537 (~206 MB)
- S9-S15: https://ndownloader.figshare.com/files/2601481 (~190 MB)

Reference:
Buccino et al., "Hybrid EEG-fNIRS Asynchronous Brain-Computer Interface for Multiple Motor Tasks",
PLOS ONE, 2016. DOI: 10.1371/journal.pone.0146610.
"""

import os
import sys
import time
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List

BUCCINO_FILES: List[Dict[str, str]] = [
    {
        "name": "EEG-fNIRS_hybrid_SMR_BCI_data_S1-S8.zip",
        "url": "https://ndownloader.figshare.com/files/2601537",
        "expected_size": 206487810,
        "subjects": "S1-S8",
    },
    {
        "name": "EEG-fNIRS_hybrid_SMR_BCI_data_S9-S15.zip",
        "url": "https://ndownloader.figshare.com/files/2601481",
        "expected_size": 189852513,
        "subjects": "S9-S15",
    },
]


def download_file_with_resume(url: str, target_path: Path, expected_size: int, max_retries: int = 5) -> bool:
    """Download a file with HTTP Range support, progress display, and exponential retry."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".download")

    for attempt in range(1, max_retries + 1):
        try:
            initial_bytes = temp_path.stat().st_size if temp_path.exists() else 0
            if initial_bytes == expected_size:
                temp_path.replace(target_path)
                return True

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            if initial_bytes > 0:
                headers["Range"] = f"bytes={initial_bytes}-"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                mode = "ab" if initial_bytes > 0 and status == 206 else "wb"
                if mode == "wb":
                    initial_bytes = 0

                chunk_size = 1024 * 1024  # 1 MB chunks
                downloaded = initial_bytes
                start_time = time.time()

                with open(temp_path, mode) as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = (downloaded - initial_bytes) / (elapsed + 1e-6) / (1024 * 1024)
                        pct = (downloaded / expected_size) * 100 if expected_size > 0 else 0
                        print(
                            f"\r[*] Downloading {target_path.name}: {downloaded / 1024 / 1024:.1f}/{expected_size / 1024 / 1024:.1f} MB "
                            f"({pct:.1f}%) @ {speed:.2f} MB/s",
                            end="",
                            flush=True,
                        )

            print()
            if target_path.exists():
                target_path.unlink()
            temp_path.replace(target_path)
            print(f"[+] Successfully downloaded {target_path.name}")
            return True

        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as err:
            wait_sec = 2 ** attempt
            print(f"\n[!] Network exception on attempt {attempt}/{max_retries}: {err}. Retrying in {wait_sec}s...")
            time.sleep(wait_sec)

    return False


def extract_archive(zip_path: Path, extract_dir: Path) -> None:
    """Extract zip archive into destination directory."""
    print(f"[*] Extracting {zip_path.name} to {extract_dir}...")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    print(f"[+] Finished extracting {zip_path.name}")


def download_and_extract_buccino_dataset(data_root: str = "data/raw/buccino") -> Path:
    """Download both Figshare archives and extract them into data_root."""
    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)
    extracted_dir = root / "extracted"

    print("=" * 80)
    print("BUCCINO ET AL. 2016 HYBRID EEG-fNIRS DATASET DOWNLOADER")
    print(f"Target Directory: {root.resolve()}")
    print("=" * 80)

    for item in BUCCINO_FILES:
        target_zip = root / item["name"]
        if target_zip.exists() and target_zip.stat().st_size == item["expected_size"]:
            print(f"[+] Archive {item['name']} already exists and size matches ({item['expected_size']} bytes).")
        else:
            success = download_file_with_resume(item["url"], target_zip, item["expected_size"])
            if not success:
                raise RuntimeError(f"Failed to download {item['name']} after maximum retries.")

        extract_archive(target_zip, extracted_dir)

    print("=" * 80)
    print("[+] All Buccino et al. 2016 archives are downloaded and extracted successfully!")
    print(f"[+] Location: {extracted_dir.resolve()}")
    print("=" * 80)
    return extracted_dir


if __name__ == "__main__":
    download_and_extract_buccino_dataset()
