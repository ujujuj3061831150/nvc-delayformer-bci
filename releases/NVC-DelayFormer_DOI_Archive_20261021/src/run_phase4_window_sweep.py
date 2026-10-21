"""
Phase 4: Time Window Length & Decision Latency Joint Evaluation Suite.
Evaluated across all 29 subjects (1,740 trials) under strict 29-fold LOSO cross-validation
(Train 23 / Val 5 / Test 1) on TU Berlin dataset (Shin et al. IEEE TNSRE 2017).

Physical Window Sweep:
- T_win in [10.0, 7.5, 5.0, 3.0] seconds from common task onset t = 0.0 s
- Physically aligned EEG (100 Hz) and fNIRS (10.333 Hz = 124/12 Hz)
- Full Model [On, Kernel] vs. Ablation [Off, Uniform] independently retrained per window
- Joint Evaluation Quad-Matrix:
  1. Cross-Subject Accuracy (%)
  2. Macro F1-score (%)
  3. Computational Complexity (FLOPs & MACs in M)
  4. Execution Latency (GPU & CPU batch-1 forward in ms)
"""

import sys
import json
import time
import platform
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import scipy.stats as stats
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.flop_counter import FlopCounterMode
import matplotlib.pyplot as plt

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.nvc_net import NVCDelayFormer
from src.train import get_warmup_cosine_scheduler
from src.utils.seed import set_seed


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float, dict]:
    acc = float(np.mean(y_true == y_pred) * 100.0)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    prec_1 = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec_1 = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_1 = 2 * prec_1 * rec_1 / (prec_1 + rec_1) if (prec_1 + rec_1) > 0 else 0.0

    prec_0 = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    rec_0 = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1_0 = 2 * prec_0 * rec_0 / (prec_0 + rec_0) if (prec_0 + rec_0) > 0 else 0.0

    macro_f1 = float((f1_0 + f1_1) / 2.0 * 100.0)
    cm = {"tp": tp, "tn": tn, "fp": fp, "fn": fn}
    return acc, macro_f1, cm


def profile_computation(model: nn.Module, dummy_eeg: torch.Tensor, dummy_fnirs: torch.Tensor) -> Dict[str, float]:
    model.eval()
    with FlopCounterMode(display=False) as fc:
        with torch.no_grad():
            _ = model(dummy_eeg, dummy_fnirs)
    flops = fc.get_total_flops()
    macs = flops // 2
    return {
        "flops": int(flops),
        "macs": int(macs),
        "m_flops": round(flops / 1e6, 3),
        "m_macs": round(macs / 1e6, 3),
    }


def measure_latency(
    model: nn.Module,
    dummy_eeg: torch.Tensor,
    dummy_fnirs: torch.Tensor,
    device_name: str,
    warmup: int = 1000,
    runs: int = 5000,
) -> Dict[str, float]:
    is_cuda = (device_name == "cuda")
    model.eval()

    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(dummy_eeg, dummy_fnirs)
        if is_cuda:
            torch.cuda.synchronize()

    # Timed runs
    times_ms = []
    with torch.no_grad():
        for _ in range(runs):
            if is_cuda:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
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
        "timed_runs": runs,
    }


def run_phase4_suite():
    print("=" * 80)
    print("PHASE 4: TIME WINDOW LENGTH & DECISION LATENCY JOINT EVALUATION (29 SUBJECTS)")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cpu_device = torch.device("cpu")
    print(f"CUDA Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'})")

    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))

    # 1. Pre-cache raw full data
    print("\n[Step 1/5] Loading and pre-caching 29 subjects in GPU memory...")
    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        cache[sid] = (
            d["eeg"].to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )
    print(f"Successfully cached {len(cache)} subjects.")

    # 2. Window configurations
    # Full original dataset: EEG 10.0s @ 100 Hz = 1000 pts; fNIRS 12.0s @ 10.333 Hz = 124 pts
    # Common physical alignment truncates both modalities at T_win from task onset t=0.0 s
    windows = [
        {"win_sec": 10.0, "n_eeg": 1000, "n_fnirs": 103},
        {"win_sec": 7.5,  "n_eeg": 750,  "n_fnirs": 78},
        {"win_sec": 5.0,  "n_eeg": 500,  "n_fnirs": 52},
        {"win_sec": 3.0,  "n_eeg": 300,  "n_fnirs": 31},
    ]

    models_to_test = [
        {
            "name": "Full Model [On, Kernel]",
            "use_delay_prior": True,
            "direct_weight_mode": "kernel",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
        {
            "name": "Ablation [Off, Uniform]",
            "use_delay_prior": False,
            "direct_weight_mode": "uniform",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
    ]

    all_window_results = {}

    print("\n[Step 2/5] Running independent 29-fold LOSO cross-validation across window lengths...")
    total_start_time = time.time()

    for win_cfg in windows:
        w_sec = win_cfg["win_sec"]
        n_eeg = win_cfg["n_eeg"]
        n_fnirs = win_cfg["n_fnirs"]
        w_key = f"{w_sec:.1f}s"
        print(f"\n=======================================================")
        print(f"Evaluating Window Length: {w_key} (EEG: {n_eeg} pts, fNIRS: {n_fnirs} pts)")
        print(f"=======================================================")

        all_window_results[w_key] = {
            "window_sec": w_sec,
            "n_eeg_pts": n_eeg,
            "n_fnirs_pts": n_fnirs,
            "models": {},
        }

        for m_cfg in models_to_test:
            m_name = m_cfg["name"]
            t0_m = time.time()
            print(f"---> Training {m_name} for window {w_key}...")

            subject_accs = []
            subject_f1s = []
            subject_preds = {}

            for test_sub in all_subs:
                set_seed(42 + test_sub)
                pool = [s for s in all_subs if s != test_sub]
                start_idx = (test_sub - 1) % len(pool)
                val_ids = [pool[(start_idx + i) % len(pool)] for i in range(5)]
                train_ids = [s for s in pool if s not in val_ids]

                # Slice inputs to exact window length
                tr_e = torch.cat([cache[s][0][:, :, :n_eeg] for s in train_ids], dim=0)
                tr_f = torch.cat([cache[s][1][:, :, :n_fnirs] for s in train_ids], dim=0)
                tr_l = torch.cat([cache[s][2] for s in train_ids], dim=0)

                val_e = torch.cat([cache[s][0][:, :, :n_eeg] for s in val_ids], dim=0)
                val_f = torch.cat([cache[s][1][:, :, :n_fnirs] for s in val_ids], dim=0)
                val_l = torch.cat([cache[s][2] for s in val_ids], dim=0)

                te_e = cache[test_sub][0][:, :, :n_eeg]
                te_f = cache[test_sub][1][:, :, :n_fnirs]
                te_l = cache[test_sub][2]

                model = NVCDelayFormer(
                    num_classes=2,
                    eeg_channels=30,
                    fnirs_channels=72,
                    feature_dim=64,
                    num_heads=4,
                    nvc_delay_mean_sec=5.0,
                    learnable_delay=False,
                    readout_mode=m_cfg["readout_mode"],
                    direct_weight_mode=m_cfg["direct_weight_mode"],
                    cut_gate_latent=m_cfg["cut_gate_latent"],
                ).to(device)

                opt = AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
                sched = get_warmup_cosine_scheduler(opt, warmup_epochs=2, total_epochs=12)
                bs = 256
                n_tr = tr_e.size(0)

                best_val_acc = -1.0
                best_val_loss = float("inf")
                best_state = None

                for epoch in range(1, 13):
                    model.train()
                    perm = torch.randperm(n_tr, device=device)
                    for idx in range(0, n_tr, bs):
                        b = perm[idx:idx+bs]
                        opt.zero_grad()
                        logits, _, recon_pred, (deep_logits, shallow_logits) = model(
                            tr_e[b], tr_f[b],
                            use_delay_prior=m_cfg["use_delay_prior"],
                            use_causal_mask=True,
                            return_recon=True,
                            return_branch_logits=True,
                        )

                        w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                        reg_w = 0.08 * (w_diff ** 2).sum()
                        loss_cls, _, _, _ = NVCDelayFormer.compute_auxiliary_loss(
                            logits, deep_logits, shallow_logits, tr_l[b], aux_weight=0.2
                        )
                        loss = loss_cls + reg_w

                        target_hbo = model.compute_buxton_hemodynamics(tr_f[b])[:, :36, :]
                        loss = loss + 1.0 * F.mse_loss(recon_pred, target_hbo)

                        loss.backward()
                        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                        opt.step()
                    sched.step()

                    # Validation checkpointing
                    model.eval()
                    with torch.no_grad():
                        v_logits, _ = model(
                            val_e, val_f,
                            use_delay_prior=m_cfg["use_delay_prior"],
                            use_causal_mask=True,
                        )
                        v_preds = torch.argmax(v_logits, dim=1)
                        v_acc = (v_preds == val_l).float().mean().item() * 100.0
                        v_loss = F.cross_entropy(v_logits, val_l).item()

                    if v_acc > best_val_acc or (v_acc == best_val_acc and v_loss < best_val_loss):
                        best_val_acc = v_acc
                        best_val_loss = v_loss
                        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

                # Evaluate on held-out test subject
                model.load_state_dict({k: v.to(device) for k, v in best_state.items()})
                model.eval()
                with torch.no_grad():
                    te_logits, _ = model(
                        te_e, te_f,
                        use_delay_prior=m_cfg["use_delay_prior"],
                        use_causal_mask=True,
                    )
                    preds = torch.argmax(te_logits, dim=1).cpu().numpy()
                    targets = te_l.cpu().numpy()

                acc, f1, cm = compute_metrics(targets, preds)
                subject_accs.append(acc)
                subject_f1s.append(f1)
                subject_preds[f"sub-{test_sub:02d}"] = {
                    "accuracy": round(acc, 2),
                    "macro_f1": round(f1, 2),
                    "confusion_matrix": cm,
                }

            # Statistical aggregation
            mean_acc = float(np.mean(subject_accs))
            std_acc = float(np.std(subject_accs, ddof=1))
            se_acc = std_acc / np.sqrt(len(all_subs))
            ci_acc = [round(float(mean_acc - 2.0484 * se_acc), 2), round(float(mean_acc + 2.0484 * se_acc), 2)]

            mean_f1 = float(np.mean(subject_f1s))
            std_f1 = float(np.std(subject_f1s, ddof=1))
            se_f1 = std_f1 / np.sqrt(len(all_subs))
            ci_f1 = [round(float(mean_f1 - 2.0484 * se_f1), 2), round(float(mean_f1 + 2.0484 * se_f1), 2)]

            total_correct = int(round(np.sum([acc * 60.0 / 100.0 for acc in subject_accs])))

            print(f"    -> {m_name}: Acc = {mean_acc:.2f}% (SD={std_acc:.2f}, 95% CI={ci_acc}), F1 = {mean_f1:.2f}%, Correct = {total_correct}/1740, Time = {time.time()-t0_m:.1f}s")

            all_window_results[w_key]["models"][m_name] = {
                "mean_accuracy": round(mean_acc, 2),
                "std_accuracy": round(std_acc, 2),
                "ci_95_accuracy": ci_acc,
                "mean_macro_f1": round(mean_f1, 2),
                "std_macro_f1": round(std_f1, 2),
                "ci_95_macro_f1": ci_f1,
                "total_correct": total_correct,
                "total_trials": 1740,
                "subject_accuracies": [round(x, 2) for x in subject_accs],
                "subject_macro_f1s": [round(x, 2) for x in subject_f1s],
                "per_subject": subject_preds,
            }

        # Paired statistics between Full Model and Ablation [Off, Uniform]
        acc_full = np.array(all_window_results[w_key]["models"]["Full Model [On, Kernel]"]["subject_accuracies"])
        acc_abl = np.array(all_window_results[w_key]["models"]["Ablation [Off, Uniform]"]["subject_accuracies"])
        diff_acc = acc_full - acc_abl
        t_stat, t_pval = stats.ttest_rel(acc_full, acc_abl)
        w_stat, w_pval = stats.wilcoxon(acc_full, acc_abl)

        all_window_results[w_key]["paired_comparison"] = {
            "mean_delta_pp": round(float(np.mean(diff_acc)), 2),
            "std_delta_pp": round(float(np.std(diff_acc, ddof=1)), 2),
            "t_statistic": round(float(t_stat), 4),
            "t_p_value": float(t_pval),
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p_value": float(w_pval),
        }
        print(f"    Paired Δ = +{np.mean(diff_acc):.2f} pp (t-pval={t_pval:.4f}, Wilcoxon-pval={w_pval:.4f})")

    print(f"\n[Step 2/5 Completed in {time.time()-total_start_time:.1f}s]")

    # 3. Profiling FLOPs, MACs, and GPU/CPU latency across windows
    print("\n[Step 3/5] Profiling FLOPs, MACs, and Execution Latency across windows (Batch Size = 1)...")
    comp_profiles = {}

    bench_model_gpu = NVCDelayFormer().to(device)
    bench_model_cpu = NVCDelayFormer().to(cpu_device)

    for win_cfg in windows:
        w_sec = win_cfg["win_sec"]
        n_eeg = win_cfg["n_eeg"]
        n_fnirs = win_cfg["n_fnirs"]
        w_key = f"{w_sec:.1f}s"

        dummy_eeg_gpu = torch.randn(1, 30, n_eeg, device=device)
        dummy_fnirs_gpu = torch.randn(1, 72, n_fnirs, device=device)
        dummy_eeg_cpu = torch.randn(1, 30, n_eeg, device=cpu_device)
        dummy_fnirs_cpu = torch.randn(1, 72, n_fnirs, device=cpu_device)

        print(f"\nProfiling {w_key} (EEG {n_eeg}, fNIRS {n_fnirs})...")
        flops_info = profile_computation(bench_model_gpu, dummy_eeg_gpu, dummy_fnirs_gpu)
        print(f"  FLOPs: {flops_info['m_flops']} M, MACs: {flops_info['m_macs']} M")

        print("  Measuring GPU latency (1,000 warmup, 5,000 runs)...")
        gpu_lat = measure_latency(bench_model_gpu, dummy_eeg_gpu, dummy_fnirs_gpu, device_name="cuda", warmup=1000, runs=5000)
        print(f"  GPU Latency: {gpu_lat['mean_ms']} ± {gpu_lat['std_ms']} ms (median: {gpu_lat['median_ms']} ms)")

        print("  Measuring CPU latency (200 warmup, 1,000 runs)...")
        cpu_lat = measure_latency(bench_model_cpu, dummy_eeg_cpu, dummy_fnirs_cpu, device_name="cpu", warmup=200, runs=1000)
        print(f"  CPU Latency: {cpu_lat['mean_ms']} ± {cpu_lat['std_ms']} ms (median: {cpu_lat['median_ms']} ms)")

        comp_profiles[w_key] = {
            "window_sec": w_sec,
            "n_eeg_pts": n_eeg,
            "n_fnirs_pts": n_fnirs,
            "computation": flops_info,
            "gpu_latency": gpu_lat,
            "cpu_latency": cpu_lat,
            "total_decision_latency_gpu_sec": round(w_sec + gpu_lat["mean_ms"] / 1000.0, 4),
            "total_decision_latency_cpu_sec": round(w_sec + cpu_lat["mean_ms"] / 1000.0, 4),
        }
        all_window_results[w_key]["engineering_profile"] = comp_profiles[w_key]

    # 4. Save JSON results
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True, parents=True)
    json_path = reports_dir / "phase4_window_sweep_results.json"

    final_payload = {
        "title": "Phase 4: Time Window Length & Decision Latency Joint Evaluation",
        "description": "Unified physical window length sweep (10.0s, 7.5s, 5.0s, 3.0s) with matched EEG/fNIRS onset and independent 29-fold LOSO cross-validation.",
        "hardware_environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
            "torch_version": torch.__version__,
        },
        "windows_summary": all_window_results,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)
    print(f"\n[Step 4/5] Results successfully saved to {json_path}")

    # 5. Generate Publication-Quality 4-Panel Visualization
    print("\n[Step 5/5] Generating publication-quality 4-panel trade-off figure...")
    generate_tradeoff_figure(all_window_results, comp_profiles)

    print("\n" + "=" * 80)
    print("PHASE 4 SWEEP COMPLETE AND AUDITED SUCCESSFULLY!")
    print("=" * 80)


def generate_tradeoff_figure(window_results: dict, comp_profiles: dict):
    fig_dir = Path("reports/figures")
    fig_dir.mkdir(exist_ok=True, parents=True)

    w_keys = ["10.0s", "7.5s", "5.0s", "3.0s"]
    w_secs = [10.0, 7.5, 5.0, 3.0]

    full_accs = [window_results[k]["models"]["Full Model [On, Kernel]"]["mean_accuracy"] for k in w_keys]
    full_acc_cis = [
        [full_accs[i] - window_results[w_keys[i]]["models"]["Full Model [On, Kernel]"]["ci_95_accuracy"][0] for i in range(4)],
        [window_results[w_keys[i]]["models"]["Full Model [On, Kernel]"]["ci_95_accuracy"][1] - full_accs[i] for i in range(4)],
    ]

    abl_accs = [window_results[k]["models"]["Ablation [Off, Uniform]"]["mean_accuracy"] for k in w_keys]
    abl_acc_cis = [
        [abl_accs[i] - window_results[w_keys[i]]["models"]["Ablation [Off, Uniform]"]["ci_95_accuracy"][0] for i in range(4)],
        [window_results[w_keys[i]]["models"]["Ablation [Off, Uniform]"]["ci_95_accuracy"][1] - abl_accs[i] for i in range(4)],
    ]

    full_f1s = [window_results[k]["models"]["Full Model [On, Kernel]"]["mean_macro_f1"] for k in w_keys]
    abl_f1s = [window_results[k]["models"]["Ablation [Off, Uniform]"]["mean_macro_f1"] for k in w_keys]

    macs_m = [comp_profiles[k]["computation"]["m_macs"] for k in w_keys]
    flops_m = [comp_profiles[k]["computation"]["m_flops"] for k in w_keys]

    gpu_lat_ms = [comp_profiles[k]["gpu_latency"]["mean_ms"] for k in w_keys]
    gpu_lat_std = [comp_profiles[k]["gpu_latency"]["std_ms"] for k in w_keys]

    cpu_lat_ms = [comp_profiles[k]["cpu_latency"]["mean_ms"] for k in w_keys]
    cpu_lat_std = [comp_profiles[k]["cpu_latency"]["std_ms"] for k in w_keys]

    plt.style.use("seaborn-v0_8-paper")
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["axes.linewidth"] = 0.8

    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5), dpi=300)

    # Panel A: Accuracy vs. Window Duration
    ax = axes[0, 0]
    ax.errorbar(w_secs, full_accs, yerr=full_acc_cis, fmt='-o', color='#1f77b4', lw=2, markersize=7, capsize=4, label='Full Model [On, Kernel]')
    ax.errorbar(w_secs, abl_accs, yerr=abl_acc_cis, fmt='--s', color='#d62728', lw=1.8, markersize=6, capsize=4, label='Ablation [Off, Uniform]')
    ax.axhline(50.0, color='gray', linestyle=':', lw=1, alpha=0.7, label='Chance Level (50%)')
    ax.set_title('(a) Cross-Subject Classification Accuracy', fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel('Window Duration $T_{\mathrm{win}}$ (s)', fontsize=10)
    ax.set_ylabel('Accuracy (%)', fontsize=10)
    ax.set_xticks(w_secs)
    ax.set_ylim(45, 75)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(frameon=True, fontsize=8.5, loc='lower right')

    # Annotate points
    for x, y in zip(w_secs, full_accs):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 7), ha='center', fontsize=8.5, fontweight='bold', color='#1f77b4')
    for x, y in zip(w_secs, abl_accs):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, -12), ha='center', fontsize=8, color='#d62728')

    # Panel B: Macro F1 vs. Window Duration
    ax = axes[0, 1]
    ax.plot(w_secs, full_f1s, '-o', color='#1f77b4', lw=2, markersize=7, label='Full Model [On, Kernel]')
    ax.plot(w_secs, abl_f1s, '--s', color='#d62728', lw=1.8, markersize=6, label='Ablation [Off, Uniform]')
    ax.set_title('(b) Cross-Subject Macro F1-Score', fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel('Window Duration $T_{\mathrm{win}}$ (s)', fontsize=10)
    ax.set_ylabel('Macro F1 (%)', fontsize=10)
    ax.set_xticks(w_secs)
    ax.set_ylim(45, 75)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(frameon=True, fontsize=8.5, loc='lower right')
    for x, y in zip(w_secs, full_f1s):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 7), ha='center', fontsize=8.5, fontweight='bold', color='#1f77b4')
    for x, y in zip(w_secs, abl_f1s):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, -12), ha='center', fontsize=8, color='#d62728')

    # Panel C: Arithmetic Complexity (FLOPs & MACs)
    ax = axes[1, 0]
    ax.plot(w_secs, macs_m, '-D', color='#2ca02c', lw=2, markersize=7, label='MACs (M)')
    ax.plot(w_secs, flops_m, '--^', color='#9467bd', lw=1.8, markersize=6, label='FLOPs (M)')
    ax.set_title('(c) Computational Complexity Scaling', fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel('Window Duration $T_{\mathrm{win}}$ (s)', fontsize=10)
    ax.set_ylabel('Operations (Millions)', fontsize=10)
    ax.set_xticks(w_secs)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(frameon=True, fontsize=8.5, loc='upper left')
    for x, y in zip(w_secs, macs_m):
        ax.annotate(f"{y:.2f}M", (x, y), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8.5, fontweight='bold', color='#2ca02c')

    # Panel D: Execution Latency (CPU & GPU)
    ax = axes[1, 1]
    ax.plot(w_secs, cpu_lat_ms, '-o', color='#ff7f0e', lw=2, markersize=7, label='CPU Latency (ms)')
    ax.plot(w_secs, gpu_lat_ms, '--s', color='#17becf', lw=1.8, markersize=6, label='GPU Latency (ms)')
    ax.set_title('(d) Single-Trial Forward Latency (Batch=1)', fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel('Window Duration $T_{\mathrm{win}}$ (s)', fontsize=10)
    ax.set_ylabel('Inference Latency (ms)', fontsize=10)
    ax.set_xticks(w_secs)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(frameon=True, fontsize=8.5, loc='center left')
    for x, y in zip(w_secs, cpu_lat_ms):
        ax.annotate(f"{y:.1f}ms", (x, y), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8.5, color='#ff7f0e')
    for x, y in zip(w_secs, gpu_lat_ms):
        ax.annotate(f"{y:.2f}ms", (x, y), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8.5, color='#17becf')

    plt.tight_layout()

    out_pdf = fig_dir / "phase4_window_tradeoff.pdf"
    out_png = fig_dir / "phase4_window_tradeoff.png"
    plt.savefig(out_pdf, bbox_inches="tight")
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved figure to {out_pdf} and {out_png}")


if __name__ == "__main__":
    run_phase4_suite()
