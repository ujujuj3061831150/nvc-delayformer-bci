"""
Resilient, Multi-Threaded Real TU Berlin Dataset Downloader & Extractor.
Fetches the official benchmark archives from TU Berlin:
- http://doc.ml.tu-berlin.de/hBCI/NIRS/NIRS_01-29.zip (~802 MB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_01-05.zip (~1.08 GB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_06-10.zip (~1.08 GB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_11-15.zip (~1.08 GB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_16-20.zip (~1.08 GB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_21-25.zip (~1.08 GB)
- http://doc.ml.tu-berlin.de/hBCI/EEG/EEG_26-29.zip (~0.82 GB)

Total size: ~7.0 GB across 7 archives.
Supports:
1. Resumable chunked downloading (HTTP Range requests).
2. Auto-retry with exponential backoff on network hiccups.
3. Concurrent download worker pool.
4. Auto-unzipping into data/raw/real_tuberlin/.
5. Real-time JSON progress tracking in data/downloads/download_status.json.
"""

import os
import sys
import time
import json
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://doc.ml.tu-berlin.de/hBCI"

ARCHIVES = [
    {"name": "NIRS_01-29.zip", "url": f"{BASE_URL}/NIRS/NIRS_01-29.zip", "subfolder": "NIRS", "size": 802171961},
    {"name": "EEG_01-05.zip", "url": f"{BASE_URL}/EEG/EEG_01-05.zip", "subfolder": "EEG", "size": 1083547146},
    {"name": "EEG_06-10.zip", "url": f"{BASE_URL}/EEG/EEG_06-10.zip", "subfolder": "EEG", "size": 1083500000},
    {"name": "EEG_11-15.zip", "url": f"{BASE_URL}/EEG/EEG_11-15.zip", "subfolder": "EEG", "size": 1083500000},
    {"name": "EEG_16-20.zip", "url": f"{BASE_URL}/EEG/EEG_16-20.zip", "subfolder": "EEG", "size": 1083500000},
    {"name": "EEG_21-25.zip", "url": f"{BASE_URL}/EEG/EEG_21-25.zip", "subfolder": "EEG", "size": 1083500000},
    {"name": "EEG_26-29.zip", "url": f"{BASE_URL}/EEG/EEG_26-29.zip", "subfolder": "EEG", "size": 820000000},
]


def update_status_file(status_file: Path, status_data: Dict):
    """Write current download progress to status JSON."""
    try:
        temp_file = status_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
        temp_file.replace(status_file)
    except Exception:
        pass


def download_single_archive(
    item: Dict,
    download_dir: Path,
    extract_root: Path,
    status_file: Path,
    status_data: Dict,
    max_retries: int = 5
) -> bool:
    """Download a single zip archive with resume support and unpack."""
    filename = item["name"]
    url = item["url"]
    dest_zip = download_dir / filename
    extract_target = extract_root / item["subfolder"]
    extract_target.mkdir(parents=True, exist_ok=True)
    
    # Check if already extracted
    extracted_flag = download_dir / f".{filename}.extracted"
    if extracted_flag.exists():
        print(f"[*] {filename} is already downloaded and extracted.")
        status_data[filename] = {"status": "extracted", "progress_pct": 100.0}
        update_status_file(status_file, status_data)
        return True
        
    chunk_size = 1024 * 1024  # 1 MB chunk
    retries = 0
    
    while retries < max_retries:
        try:
            existing_size = dest_zip.stat().st_size if dest_zip.exists() else 0
            
            headers = {"User-Agent": "Mozilla/5.0 (TU Berlin BCI Downloader)"}
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"
                
            req = urllib.request.Request(url, headers=headers)
            
            try:
                resp = urllib.request.urlopen(req, timeout=30)
            except urllib.error.HTTPError as e:
                if e.code == 416:  # Range not satisfiable (already fully downloaded)
                    print(f"[*] {filename} already complete.")
                    break
                else:
                    raise e
                    
            total_size = existing_size + int(resp.headers.get("Content-Length", 0))
            print(f"[>] Downloading {filename} (Starting at {existing_size / 1e6:.1f} MB / {total_size / 1e6:.1f} MB)...")
            
            mode = "ab" if existing_size > 0 else "wb"
            with open(dest_zip, mode) as fp:
                downloaded = existing_size
                last_time = time.time()
                last_bytes = downloaded
                
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fp.write(chunk)
                    downloaded += len(chunk)
                    
                    now = time.time()
                    if now - last_time >= 5.0:
                        speed_mb = ((downloaded - last_bytes) / 1e6) / (now - last_time)
                        pct = (downloaded / total_size) * 100.0 if total_size > 0 else 0.0
                        print(f"[{filename}] {downloaded / 1e6:.1f} MB / {total_size / 1e6:.1f} MB ({pct:.1f}%) | {speed_mb:.2f} MB/s")
                        status_data[filename] = {
                            "status": "downloading",
                            "downloaded_mb": round(downloaded / 1e6, 2),
                            "total_mb": round(total_size / 1e6, 2),
                            "progress_pct": round(pct, 1),
                            "speed_mbs": round(speed_mb, 2),
                        }
                        update_status_file(status_file, status_data)
                        last_time = now
                        last_bytes = downloaded
                        
            print(f"[+] Download complete: {filename}")
            break
            
        except Exception as err:
            retries += 1
            wait_sec = min(2 ** retries, 30)
            print(f"[!] Error downloading {filename} ({err}). Retry {retries}/{max_retries} in {wait_sec}s...")
            time.sleep(wait_sec)
            
    if not dest_zip.exists():
        status_data[filename] = {"status": "failed"}
        update_status_file(status_file, status_data)
        return False
        
    # Unpack archive
    print(f"[*] Extracting {filename} to {extract_target}...")
    status_data[filename]["status"] = "extracting"
    update_status_file(status_file, status_data)
    try:
        with zipfile.ZipFile(dest_zip, "r") as zf:
            zf.extractall(extract_target)
        extracted_flag.touch()
        status_data[filename]["status"] = "extracted"
        status_data[filename]["progress_pct"] = 100.0
        update_status_file(status_file, status_data)
        print(f"[+] Extracted {filename} successfully.")
        return True
    except Exception as e:
        print(f"[!] Extraction failed for {filename}: {e}")
        status_data[filename]["status"] = "extract_failed"
        update_status_file(status_file, status_data)
        return False


def run_parallel_downloader(max_workers: int = 3):
    """Run concurrent download pipeline."""
    project_root = Path(__file__).resolve().parent.parent.parent
    download_dir = project_root / "data" / "downloads"
    extract_root = project_root / "data" / "raw" / "real_tuberlin"
    
    download_dir.mkdir(parents=True, exist_ok=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    
    status_file = download_dir / "download_status.json"
    status_data = {}
    
    print("=" * 80)
    print("TU BERLIN HYBRID EEG-fNIRS REAL DATASET DOWNLOADER")
    print(f"Target Directory: {extract_root}")
    print(f"Concurrent Workers: {max_workers}")
    print("Total Archives: 7 (~7.0 GB total)")
    print("=" * 80)
    
    # Prioritize NIRS archive first, then EEG archives
    sorted_archives = sorted(ARCHIVES, key=lambda x: 0 if x["subfolder"] == "NIRS" else 1)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_single_archive,
                item,
                download_dir,
                extract_root,
                status_file,
                status_data
            ): item["name"]
            for item in sorted_archives
        }
        
        for future in as_completed(futures):
            name = futures[future]
            try:
                success = future.result()
                if success:
                    print(f"[✔] Archive {name} finished processing.")
                else:
                    print(f"[✘] Archive {name} failed.")
            except Exception as e:
                print(f"[✘] Exception processing {name}: {e}")
                
    print("\n" + "=" * 80)
    print("All archives processed. Check status at:", status_file)
    print("=" * 80)


if __name__ == "__main__":
    workers = 3
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        workers = int(sys.argv[1])
    run_parallel_downloader(max_workers=workers)
