"""
High-Performance Multi-Part Parallel Downloader for TU Berlin BBCI Datasets.
Uses concurrent HTTP Range requests to maximize bandwidth utilization across international routes.
"""

import os
import sys
import time
import ssl
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_file_size(url: str, ctx: ssl.SSLContext) -> int:
    """Query total content length via Range request."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        content_range = resp.headers.get('Content-Range')
        if content_range:
            # Format: 'bytes 0-0/797840805'
            return int(content_range.split('/')[-1])
        cl = resp.headers.get('Content-Length')
        if cl:
            return int(cl)
    raise ValueError(f"Unable to determine content length for {url}")


def download_chunk(
    url: str,
    part_path: Path,
    start_byte: int,
    end_byte: int,
    ctx: ssl.SSLContext,
    max_retries: int = 10
) -> bool:
    """Download a single byte range with resume support."""
    part_size = end_byte - start_byte + 1
    
    # Check if part already complete
    if part_path.exists():
        existing = part_path.stat().st_size
        if existing == part_size:
            return True
        elif existing > part_size:
            part_path.unlink()
            existing = 0
    else:
        existing = 0

    retries = 0
    while retries < max_retries:
        try:
            curr_start = start_byte + existing
            if curr_start > end_byte:
                return True
                
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Range': f'bytes={curr_start}-{end_byte}'
                }
            )
            
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp, open(part_path, 'ab' if existing > 0 else 'wb') as fp:
                while True:
                    buf = resp.read(256 * 1024)
                    if not buf:
                        break
                    fp.write(buf)
                    existing += len(buf)
                    
            if existing == part_size:
                return True
        except Exception as e:
            retries += 1
            time.sleep(min(2 ** min(retries, 4), 10))
            
    return part_path.exists() and part_path.stat().st_size == part_size


def download_file_parallel(
    url: str,
    target_file: Path,
    num_threads: int = 8
) -> bool:
    """Download a large file using concurrent HTTP Range workers."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    print(f"[*] Querying file size for {target_file.name}...")
    total_size = get_file_size(url, ctx)
    print(f"[*] Total file size: {total_size / 1e6:.2f} MB ({total_size} bytes)")
    
    if target_file.exists() and target_file.stat().st_size == total_size:
        print(f"[OK] {target_file.name} is already completely downloaded.")
        return True
        
    # Split into num_threads chunks
    chunk_size = total_size // num_threads
    ranges = []
    part_files = []
    
    for i in range(num_threads):
        start = i * chunk_size
        end = total_size - 1 if i == num_threads - 1 else (i + 1) * chunk_size - 1
        part_file = target_file.parent / f"{target_file.name}.part{i:02d}"
        ranges.append((start, end))
        part_files.append(part_file)

    print(f"[*] Starting parallel download with {num_threads} concurrent streams...")
    t0 = time.time()
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(download_chunk, url, p_file, r[0], r[1], ctx): i
            for i, (p_file, r) in enumerate(zip(part_files, ranges))
        }
        
        # Monitor aggregate progress
        while True:
            done_count = sum(1 for f in futures if f.done())
            downloaded = sum(p.stat().st_size for p in part_files if p.exists())
            elapsed = time.time() - t0
            speed = (downloaded / 1e6) / max(elapsed, 0.1)
            pct = (downloaded / total_size) * 100
            print(f"\rProgress: {downloaded / 1e6:.1f} / {total_size / 1e6:.1f} MB ({pct:.1f}%) | Speed: {speed:.2f} MB/s | Workers: {done_count}/{num_threads} done", end="", flush=True)
            
            if done_count == num_threads:
                break
            time.sleep(1.0)
            
    print()
    # Check all parts succeeded
    all_ok = all(f.result() for f in futures)
    if not all_ok:
        print("[FAIL] Some parts failed to download.")
        return False
        
    print(f"[*] All {num_threads} parts downloaded. Assembling final file: {target_file.name}...")
    with open(target_file, "wb") as outfile:
        for p_file in part_files:
            with open(p_file, "rb") as infile:
                while True:
                    buf = infile.read(4 * 1024 * 1024)
                    if not buf:
                        break
                    outfile.write(buf)
            p_file.unlink()
            
    final_size = target_file.stat().st_size
    assert final_size == total_size, f"Size mismatch: {final_size} != {total_size}"
    total_time = time.time() - t0
    avg_speed = (total_size / 1e6) / max(total_time, 0.1)
    print(f"[OK] Successfully assembled {target_file.name} ({total_size / 1e6:.1f} MB in {total_time:.1f}s, avg {avg_speed:.2f} MB/s)!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python multipart_downloader.py <url> <target_file> [threads]")
        sys.exit(1)
    url = sys.argv[1]
    target = Path(sys.argv[2])
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    download_file_parallel(url, target, num_threads=threads)
