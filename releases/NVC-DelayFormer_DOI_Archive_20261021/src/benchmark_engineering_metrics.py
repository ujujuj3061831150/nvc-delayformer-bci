"""
Engineering Reproducibility Benchmark: Parameter Counts, MACs, and Latency.
Protocol:
- Batch Size: 1 (single-trial real-time streaming)
- EEG input: (1, 30, 1000) (30 scalp channels, 10.0s @ 100 Hz)
- fNIRS input: (1, 72, 124) (36 HbO + 36 HbR channels, 12.0s @ 10.333 Hz)
- Latency measurement: 1,000 warm-up iterations, 5,000 timed evaluations
- CPU & GPU tested independently with torch.cuda.synchronize() and time.perf_counter()
- FLOPs / MACs profiled via PyTorch FlopCounterMode
"""

import sys
import json
import time
import platform
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.flop_counter import FlopCounterMode

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.nvc_net import NVCDelayFormer
from src.models.baselines import (
    EEGNetClassifier,
    FNIRSClassifier,
    ConcatFusionClassifier,
    StandardCrossAttentionClassifier
)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def profile_flops(model: nn.Module, dummy_eeg: torch.Tensor, dummy_fnirs: torch.Tensor, model_name: str) -> dict:
    model.eval()
    with FlopCounterMode(display=False) as flop_counter:
        with torch.no_grad():
            if model_name == "EEGNet":
                _ = model(dummy_eeg)
            elif model_name == "fNIRS-CNN":
                _ = model(dummy_fnirs)
            else:
                _ = model(dummy_eeg, dummy_fnirs)
    total_flops = flop_counter.get_total_flops()
    macs = total_flops // 2
    return {
        "flops": int(total_flops),
        "macs": int(macs),
        "m_flops": round(total_flops / 1e6, 2),
        "m_macs": round(macs / 1e6, 2)
    }


def measure_latency(model: nn.Module, dummy_eeg: torch.Tensor, dummy_fnirs: torch.Tensor, model_name: str, device_name: str, warmup: int = 1000, runs: int = 5000) -> dict:
    is_cuda = (device_name == "cuda")
    model.eval()
    
    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            if model_name == "EEGNet":
                _ = model(dummy_eeg)
            elif model_name == "fNIRS-CNN":
                _ = model(dummy_fnirs)
            else:
                _ = model(dummy_eeg, dummy_fnirs)
        if is_cuda:
            torch.cuda.synchronize()

    # Timed evaluations
    times_ms = []
    with torch.no_grad():
        for _ in range(runs):
            if is_cuda:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            if model_name == "EEGNet":
                _ = model(dummy_eeg)
            elif model_name == "fNIRS-CNN":
                _ = model(dummy_fnirs)
            else:
                _ = model(dummy_eeg, dummy_fnirs)
            if is_cuda:
                torch.cuda.synchronize()
            t1 = time.perf_counter()
            times_ms.append((t1 - t0) * 1000.0)

    arr = np.array(times_ms)
    return {
        "mean_ms": round(float(np.mean(arr)), 3),
        "std_ms": round(float(np.std(arr)), 3),
        "median_ms": round(float(np.median(arr)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
        "min_ms": round(float(np.min(arr)), 3),
        "max_ms": round(float(np.max(arr)), 3),
        "warmup_runs": warmup,
        "timed_runs": runs
    }


def run_engineering_benchmarks():
    print("=" * 80)
    print("STARTING ENGINEERING BENCHMARKS (PARAMETERS, FLOPs/MACs, CPU/GPU LATENCY)")
    print("=" * 80)

    cpu_device = torch.device("cpu")
    gpu_available = torch.cuda.is_available()
    gpu_device = torch.device("cuda" if gpu_available else "cpu")

    hardware_info = {
        "os": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else "None",
        "cpu_count": platform.uname().node
    }

    models_dict = {
        "EEGNet": lambda: EEGNetClassifier(in_channels=30, num_classes=2, feature_dim=64),
        "fNIRS-CNN": lambda: FNIRSClassifier(in_channels=72, num_classes=2, feature_dim=64),
        "Feature-Concat": lambda: ConcatFusionClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64),
        "Standard-Attention": lambda: StandardCrossAttentionClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, num_heads=4),
        "NVC-DelayFormer": lambda: NVCDelayFormer(num_classes=2, eeg_channels=30, fnirs_channels=72, feature_dim=64, num_heads=4, learnable_delay=False)
    }

    results = {
        "hardware_info": hardware_info,
        "protocol": {
            "batch_size": 1,
            "eeg_shape": [1, 30, 1000],
            "fnirs_shape": [1, 72, 124],
            "warmup_runs": 1000,
            "timed_runs": 5000
        },
        "models": {}
    }

    dummy_eeg_cpu = torch.randn(1, 30, 1000, device=cpu_device)
    dummy_fnirs_cpu = torch.randn(1, 72, 124, device=cpu_device)
    dummy_eeg_gpu = torch.randn(1, 30, 1000, device=gpu_device) if gpu_available else None
    dummy_fnirs_gpu = torch.randn(1, 72, 124, device=gpu_device) if gpu_available else None

    for name, init_fn in models_dict.items():
        print(f"\nEvaluating {name}...")
        model_cpu = init_fn().to(cpu_device)
        params = count_parameters(model_cpu)
        flops_info = profile_flops(model_cpu, dummy_eeg_cpu, dummy_fnirs_cpu, name)

        print(f"  Params: {params:,} | MACs: {flops_info['macs']:,} ({flops_info['m_macs']} M) | FLOPs: {flops_info['flops']:,} ({flops_info['m_flops']} M)")

        print("  Measuring CPU Latency (1,000 warmup + 5,000 runs)...")
        cpu_lat = measure_latency(model_cpu, dummy_eeg_cpu, dummy_fnirs_cpu, name, "cpu", warmup=1000, runs=5000)
        print(f"    CPU Mean: {cpu_lat['mean_ms']:.3f} ms +/- {cpu_lat['std_ms']:.3f} ms (P50: {cpu_lat['median_ms']:.3f} ms, P99: {cpu_lat['p99_ms']:.3f} ms)")

        gpu_lat = None
        if gpu_available:
            print("  Measuring GPU Latency (1,000 warmup + 5,000 runs)...")
            model_gpu = init_fn().to(gpu_device)
            gpu_lat = measure_latency(model_gpu, dummy_eeg_gpu, dummy_fnirs_gpu, name, "cuda", warmup=1000, runs=5000)
            print(f"    GPU Mean: {gpu_lat['mean_ms']:.3f} ms +/- {gpu_lat['std_ms']:.3f} ms (P50: {gpu_lat['median_ms']:.3f} ms, P99: {gpu_lat['p99_ms']:.3f} ms)")

        results["models"][name] = {
            "num_params": params,
            "macs": flops_info["macs"],
            "m_macs": flops_info["m_macs"],
            "flops": flops_info["flops"],
            "m_flops": flops_info["m_flops"],
            "cpu_latency": cpu_lat,
            "gpu_latency": gpu_lat
        }

    out_file = Path("reports/engineering_benchmarks.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[+] Successfully saved engineering benchmarks to {out_file}")


if __name__ == "__main__":
    run_engineering_benchmarks()
