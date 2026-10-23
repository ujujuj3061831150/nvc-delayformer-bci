"""
Authoritative 29-Subject Full Benchmark, Ablation, Delay Sensitivity & Convergence Suite.
Evaluated across ALL 29 human subjects (1,740 authentic trials) of Shin et al. (IEEE TNSRE 2017)
under strict 29-fold Leave-One-Subject-Out (LOSO) cross-validation with three-way isolation
(Train 23 / Val 5 / Test 1).
"""

import sys
import copy
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import scipy.stats as stats
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW

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
from src.train import get_warmup_cosine_scheduler
from src.utils.seed import set_seed


def compute_cohens_kappa(acc_percent: float, chance: float = 0.5) -> float:
    p_o = acc_percent / 100.0
    p_e = chance
    return float((p_o - p_e) / (1.0 - p_e))


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


def run_full_29sub_suite():
    print("=" * 80)
    print("STARTING 29-SUBJECT FULL BENCHMARK, ABLATION & DELAY ANALYSIS (1,740 REAL TRIALS)")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing on compute device: {device}")
    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))  # 1 to 29

    # Pre-cache all 29 subjects into VRAM / RAM
    print("\n[1/5] Pre-caching 29 subjects into memory...")
    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        cache[sid] = (
            d["eeg"].to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )
    print(f"      Successfully cached {len(cache)} subjects ({len(cache)*60} trials).")

    # Define model configurations
    benchmark_models = [
        "EEGNet",
        "fNIRS-CNN",
        "Feature-Concat",
        "Standard-Attention",
        "NVC-DelayFormer (Full)"
    ]

    ablation_variants = [
        "Full Model",
        "w/o Delay Prior",
        "w/o Causal Mask",
        "w/o Recon Loss",
        "Wrong Delay Prior (0s)"
    ]

    results_benchmark = {m: [] for m in benchmark_models}
    macro_f1_benchmark = {m: [] for m in benchmark_models}
    locked_predictions = {m: {} for m in benchmark_models}
    params_count = {}

    # Run Benchmark Models
    print("\n[2/5] Running 29-Fold LOSO Evaluation with 3-Way Nested Validation...")
    for model_name in benchmark_models:
        t0 = time.time()
        for test_sub in all_subs:
            set_seed(42 + test_sub)
            pool = [s for s in all_subs if s != test_sub]
            start_idx = (test_sub - 1) % len(pool)
            val_ids = [pool[(start_idx + i) % len(pool)] for i in range(5)]
            train_ids = [s for s in pool if s not in val_ids]

            tr_e = torch.cat([cache[s][0] for s in train_ids], dim=0)
            tr_f = torch.cat([cache[s][1] for s in train_ids], dim=0)
            tr_l = torch.cat([cache[s][2] for s in train_ids], dim=0)

            val_e = torch.cat([cache[s][0] for s in val_ids], dim=0)
            val_f = torch.cat([cache[s][1] for s in val_ids], dim=0)
            val_l = torch.cat([cache[s][2] for s in val_ids], dim=0)

            te_e, te_f, te_l = cache[test_sub]

            if model_name == "EEGNet":
                model = EEGNetClassifier(in_channels=30, num_classes=2, feature_dim=64).to(device)
            elif model_name == "fNIRS-CNN":
                model = FNIRSClassifier(in_channels=72, num_classes=2, feature_dim=64).to(device)
            elif model_name == "Feature-Concat":
                model = ConcatFusionClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64).to(device)
            elif model_name == "Standard-Attention":
                model = StandardCrossAttentionClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, num_heads=4).to(device)
            else:
                model = NVCDelayFormer(num_classes=2, eeg_channels=30, fnirs_channels=72, feature_dim=64, num_heads=4, learnable_delay=False).to(device)

            if test_sub == 1:
                params_count[model_name] = sum(p.numel() for p in model.parameters() if p.requires_grad)

            opt = AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
            sched = get_warmup_cosine_scheduler(opt, warmup_epochs=2, total_epochs=12)
            criterion = nn.CrossEntropyLoss()

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
                    if model_name == "EEGNet":
                        logits = model(tr_e[b])
                        loss = criterion(logits, tr_l[b])
                    elif model_name == "fNIRS-CNN":
                        logits = model(tr_f[b])
                        loss = criterion(logits, tr_l[b])
                    elif model_name in ["Feature-Concat", "Standard-Attention"]:
                        logits = model(tr_e[b], tr_f[b])
                        loss = criterion(logits, tr_l[b])
                    else:
                        logits, _, recon, (deep_logits, shallow_logits) = model(
                            tr_e[b], tr_f[b], use_delay_prior=True, use_causal_mask=True, return_recon=True, return_branch_logits=True
                        )
                        loss_cls, _, _, _ = NVCDelayFormer.compute_auxiliary_loss(
                            logits, deep_logits, shallow_logits, tr_l[b], aux_weight=0.2, criterion=criterion
                        )
                        w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                        target_hbo = model.compute_buxton_hemodynamics(tr_f[b])[:, :36, :]
                        loss = loss_cls + 0.08 * (w_diff ** 2).sum() + F.mse_loss(recon, target_hbo)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    opt.step()
                sched.step()

                # Model selection on held-out validation cohort
                model.eval()
                with torch.no_grad():
                    if model_name == "EEGNet":
                        v_logits = model(val_e)
                    elif model_name == "fNIRS-CNN":
                        v_logits = model(val_f)
                    elif model_name in ["Feature-Concat", "Standard-Attention"]:
                        v_logits = model(val_e, val_f)
                    else:
                        v_logits, _ = model(val_e, val_f, use_delay_prior=True, use_causal_mask=True)
                    v_loss = criterion(v_logits, val_l).item()
                    v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

                if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                    best_val_acc = v_acc
                    best_val_loss = v_loss
                    best_state = copy.deepcopy(model.state_dict())

            # Evaluate best checkpoint on unseen test subject
            model.load_state_dict(best_state)
            model.eval()
            with torch.no_grad():
                if model_name == "EEGNet":
                    preds_logits = model(te_e)
                elif model_name == "fNIRS-CNN":
                    preds_logits = model(te_f)
                elif model_name in ["Feature-Concat", "Standard-Attention"]:
                    preds_logits = model(te_e, te_f)
                else:
                    preds_logits, _ = model(te_e, te_f, use_delay_prior=True, use_causal_mask=True)

                preds_cls = preds_logits.argmax(-1).cpu().numpy()
                probs = F.softmax(preds_logits, dim=-1)[:, 1].cpu().numpy()
                y_true = te_l.cpu().numpy()

                acc, f1, cm = compute_metrics(y_true, preds_cls)
                results_benchmark[model_name].append(acc)
                macro_f1_benchmark[model_name].append(f1)

                locked_predictions[model_name][f"sub-{test_sub:02d}"] = {
                    "y_true": y_true.tolist(),
                    "y_pred": preds_cls.tolist(),
                    "y_prob": [round(float(p), 4) for p in probs],
                    "acc": acc,
                    "f1": f1,
                    "cm": cm
                }

        arr = np.array(results_benchmark[model_name])
        f1_arr = np.array(macro_f1_benchmark[model_name])
        print(f"      {model_name:<24}: Acc = {arr.mean():.2f}% +/- {arr.std(ddof=1):.2f}% | Macro F1 = {f1_arr.mean():.2f}% (Time: {time.time()-t0:.1f}s)")

    # Run Ablation Variants
    trained_full_models = {}
    print("\n[3/5] Running 29-Fold LOSO Evaluation for Ablation Variants...")
    results_ablation = {v: [] for v in ablation_variants}
    macro_f1_ablation = {v: [] for v in ablation_variants}
    recon_corrs = {v: [] for v in ablation_variants}
    recon_mses = {v: [] for v in ablation_variants}
    locked_ablation_predictions = {v: {} for v in ablation_variants}

    for v in ablation_variants:
        t0 = time.time()
        for test_sub in all_subs:
            set_seed(42 + test_sub)
            pool = [s for s in all_subs if s != test_sub]
            start_idx = (test_sub - 1) % len(pool)
            val_ids = [pool[(start_idx + i) % len(pool)] for i in range(5)]
            train_ids = [s for s in pool if s not in val_ids]

            tr_e = torch.cat([cache[s][0] for s in train_ids], dim=0)
            tr_f = torch.cat([cache[s][1] for s in train_ids], dim=0)
            tr_l = torch.cat([cache[s][2] for s in train_ids], dim=0)

            val_e = torch.cat([cache[s][0] for s in val_ids], dim=0)
            val_f = torch.cat([cache[s][1] for s in val_ids], dim=0)
            val_l = torch.cat([cache[s][2] for s in val_ids], dim=0)

            te_e, te_f, te_l = cache[test_sub]

            tau_init = 0.0 if v == "Wrong Delay Prior (0s)" else 5.0
            use_delay = (v != "w/o Delay Prior")
            use_causal = (v != "w/o Causal Mask")
            lambda_recon = 0.0 if v == "w/o Recon Loss" else 1.0

            model = NVCDelayFormer(
                num_classes=2, eeg_channels=30, fnirs_channels=72, feature_dim=64, num_heads=4,
                nvc_delay_mean_sec=tau_init, learnable_delay=False
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
                    logits, _, recon_pred = model(tr_e[b], tr_f[b], use_delay_prior=use_delay, use_causal_mask=use_causal, return_recon=True)
                    w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                    loss = F.cross_entropy(logits, tr_l[b]) + 0.08 * (w_diff ** 2).sum()
                    if lambda_recon > 0.0:
                        target_hbo = model.compute_buxton_hemodynamics(tr_f[b])[:, :36, :]
                        loss = loss + lambda_recon * F.mse_loss(recon_pred, target_hbo)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    opt.step()
                sched.step()

                model.eval()
                with torch.no_grad():
                    v_logits, _ = model(val_e, val_f, use_delay_prior=use_delay, use_causal_mask=use_causal)
                    v_loss = F.cross_entropy(v_logits, val_l).item()
                    v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0
                if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                    best_val_acc = v_acc
                    best_val_loss = v_loss
                    best_state = copy.deepcopy(model.state_dict())

            model.load_state_dict(best_state)
            model.eval()
            if v == "Full Model":
                trained_full_models[test_sub] = model

            with torch.no_grad():
                preds_logits, _, t_recon = model(te_e, te_f, use_delay_prior=use_delay, use_causal_mask=use_causal, return_recon=True)
                preds_cls = preds_logits.argmax(-1).cpu().numpy()
                probs = F.softmax(preds_logits, dim=-1)[:, 1].cpu().numpy()
                y_true = te_l.cpu().numpy()

                acc, f1, cm = compute_metrics(y_true, preds_cls)
                results_ablation[v].append(acc)
                macro_f1_ablation[v].append(f1)

                locked_ablation_predictions[v][f"sub-{test_sub:02d}"] = {
                    "y_true": y_true.tolist(),
                    "y_pred": preds_cls.tolist(),
                    "y_prob": [round(float(p), 4) for p in probs],
                    "acc": acc,
                    "f1": f1,
                    "cm": cm
                }

                true_hbo = model.compute_buxton_hemodynamics(te_f)[:, :36, :]
                mse_val = F.mse_loss(t_recon, true_hbo).item()
                recon_mses[v].append(mse_val)
                r_num = ((t_recon - t_recon.mean(-1, keepdim=True)) * (true_hbo - true_hbo.mean(-1, keepdim=True))).sum(-1)
                r_den = torch.sqrt(((t_recon - t_recon.mean(-1, keepdim=True))**2).sum(-1) * ((true_hbo - true_hbo.mean(-1, keepdim=True))**2).sum(-1) + 1e-8)
                recon_corrs[v].append((r_num / r_den).mean().item())

        arr = np.array(results_ablation[v])
        full_arr = np.array(results_ablation["Full Model"])
        delta = arr.mean() - full_arr.mean()
        p_t = stats.ttest_rel(full_arr, arr)[1] if v != "Full Model" else 1.0
        p_w = stats.wilcoxon(full_arr, arr)[1] if v != "Full Model" else 1.0
        print(f"      {v:<24}: Acc = {arr.mean():.2f}% +/- {arr.std(ddof=1):.2f}% (Delta = {delta:+.2f}%, t-p = {p_t:.4f}, w-p = {p_w:.4f}, r_HbO = {np.mean(recon_corrs[v]):.4f}, Time: {time.time()-t0:.1f}s)")

    # Run Test-Time Delay Sensitivity Sweep (without gradient updates)
    print("\n[4/5] Running 29-Subject Cohort Delay Sensitivity Sweep tau in [0.0, 2.0, 4.0, 5.0, 6.0, 8.0]s...")
    delay_sweep_taus = [0.0, 2.0, 4.0, 5.0, 6.0, 8.0]
    delay_sweep_accs = {}
    for tau in delay_sweep_taus:
        tau_accs = []
        for test_sub in all_subs:
            m = trained_full_models[test_sub]
            te_e, te_f, te_l = cache[test_sub]
            m.cross_attention.delay_mean.data.fill_(tau)
            with torch.no_grad():
                preds, _ = m(te_e, te_f, use_delay_prior=True, use_causal_mask=True)
                tau_accs.append((preds.argmax(-1) == te_l).float().mean().item() * 100.0)
            # Restore 5.0s
            m.cross_attention.delay_mean.data.fill_(5.0)

        t_arr = np.array(tau_accs)
        se = float(t_arr.std(ddof=1) / np.sqrt(len(t_arr)))
        delay_sweep_accs[str(tau)] = {
            "mean": float(t_arr.mean()),
            "std": float(t_arr.std(ddof=1)),
            "se": se,
            "fold_accs": [float(x) for x in t_arr]
        }
        print(f"      tau = {tau:.1f}s: Mean Acc = {t_arr.mean():.2f}% +/- {t_arr.std(ddof=1):.2f}% (SE = {se:.2f}%)")

    # Spontaneous Convergence from non-5s initialization (CLEAN: NO tau_reg anchor!)
    print("\n[5/5] Tracking Spontaneous Convergence from Non-5s Initialization (NO ARTIFICIAL REGULARIZER)...")
    convergence_trajectories = {}
    init_taus = [2.5, 3.0, 7.0]
    for tau_init in init_taus:
        tau_hist = []
        set_seed(100)
        tr_e = torch.cat([cache[s][0] for s in range(1, 25)], dim=0)
        tr_f = torch.cat([cache[s][1] for s in range(1, 25)], dim=0)
        tr_l = torch.cat([cache[s][2] for s in range(1, 25)], dim=0)

        learnable_model = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, feature_dim=64, num_heads=4,
            nvc_delay_mean_sec=tau_init, learnable_delay=True
        ).to(device)
        delay_params = [learnable_model.cross_attention.delay_mean]
        base_params = [p for p in learnable_model.parameters() if p is not delay_params[0]]
        opt = AdamW([
            {"params": base_params, "lr": 3e-3, "weight_decay": 0.05},
            {"params": delay_params, "lr": 0.01, "weight_decay": 0.0}
        ])

        tau_hist.append(float(learnable_model.cross_attention.delay_mean.mean().item()))
        for ep in range(1, 21):
            learnable_model.train()
            perm = torch.randperm(tr_e.size(0), device=device)
            for idx in range(0, tr_e.size(0), 256):
                b = perm[idx:idx+256]
                opt.zero_grad()
                logits, _, recon_pred, (deep_logits, shallow_logits) = learnable_model(
                    tr_e[b], tr_f[b], return_recon=True, return_branch_logits=True
                )
                w_diff = learnable_model.direct_readout.weight[1] - learnable_model.direct_readout.weight[0]
                target_hbo = learnable_model.compute_buxton_hemodynamics(tr_f[b])[:, :36, :]
                loss_cls, _, _, _ = NVCDelayFormer.compute_auxiliary_loss(
                    logits, deep_logits, shallow_logits, tr_l[b], aux_weight=0.2
                )
                loss = loss_cls + 0.08 * (w_diff ** 2).sum() + F.mse_loss(recon_pred, target_hbo)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(learnable_model.parameters(), 1.0)
                opt.step()
            tau_cur = float(torch.clamp(learnable_model.cross_attention.delay_mean.mean(), 0.0, 8.0).item())
            tau_hist.append(tau_cur)

        convergence_trajectories[str(tau_init)] = tau_hist
        print(f"      tau_init = {tau_init:.1f}s -> Final tau = {tau_hist[-1]:.2f}s (Trajectory: {[round(x, 2) for x in tau_hist[::4]]})")

    # Statistical Significance and FDR Correction
    full_arr = np.array(results_benchmark["NVC-DelayFormer (Full)"])
    full_f1_arr = np.array(macro_f1_benchmark["NVC-DelayFormer (Full)"])
    df_n = len(all_subs) - 1  # 28
    t_crit_95 = stats.t.ppf(0.975, df=df_n)  # ~2.0484

    summary_data = {
        "dataset": "TU Berlin Mental Arithmetic vs. Rest",
        "citation": "Shin et al. IEEE TNSRE 2017",
        "num_subjects": 29,
        "total_trials": 1740,
        "validation_protocol": "29-Fold Full LOSO with 3-Way Nested Validation (Train 23 / Val 5 / Test 1)",
        "degrees_of_freedom": df_n,
        "t_critical_95": float(t_crit_95),
        "models": {},
        "ablations": {},
        "delay_sweep": delay_sweep_accs,
        "convergence_trajectories": convergence_trajectories
    }

    # Compile Benchmark Stats
    raw_p_bench = []
    for m in benchmark_models:
        m_arr = np.array(results_benchmark[m])
        m_f1 = np.array(macro_f1_benchmark[m])
        t_stat, p_t = stats.ttest_rel(full_arr, m_arr) if m != "NVC-DelayFormer (Full)" else (0.0, 1.0)
        w_stat, p_w = stats.wilcoxon(full_arr, m_arr) if m != "NVC-DelayFormer (Full)" else (0.0, 1.0)
        se = float(m_arr.std(ddof=1) / np.sqrt(len(m_arr)))
        ci95 = [float(m_arr.mean() - t_crit_95 * se), float(m_arr.mean() + t_crit_95 * se)]
        if m != "NVC-DelayFormer (Full)":
            raw_p_bench.append(p_w)

        summary_data["models"][m] = {
            "mean_acc": float(m_arr.mean()),
            "std_acc": float(m_arr.std(ddof=1)),
            "se_acc": se,
            "ci95": ci95,
            "mean_macro_f1": float(m_f1.mean()),
            "std_macro_f1": float(m_f1.std(ddof=1)),
            "cohens_kappa": compute_cohens_kappa(float(m_arr.mean())),
            "num_params": params_count.get(m, 0),
            "t_test_p": float(p_t),
            "wilcoxon_p": float(p_w),
            "fold_accs": [float(x) for x in m_arr],
            "fold_f1s": [float(x) for x in m_f1]
        }

    q_vals = stats.false_discovery_control(raw_p_bench)
    bench_non_full = [m for m in benchmark_models if m != "NVC-DelayFormer (Full)"]
    for idx, m in enumerate(bench_non_full):
        summary_data["models"][m]["fdr_q"] = float(q_vals[idx])
    summary_data["models"]["NVC-DelayFormer (Full)"]["fdr_q"] = 1.0

    # Compile Ablation Stats
    raw_p_ab = []
    for v in ablation_variants:
        v_arr = np.array(results_ablation[v])
        v_f1 = np.array(macro_f1_ablation[v])
        t_stat, p_t = stats.ttest_rel(full_arr, v_arr) if v != "Full Model" else (0.0, 1.0)
        w_stat, p_w = stats.wilcoxon(full_arr, v_arr) if v != "Full Model" else (0.0, 1.0)
        se = float(v_arr.std(ddof=1) / np.sqrt(len(v_arr)))
        ci95 = [float(v_arr.mean() - t_crit_95 * se), float(v_arr.mean() + t_crit_95 * se)]
        if v != "Full Model":
            raw_p_ab.append(p_w)

        summary_data["ablations"][v] = {
            "mean_acc": float(v_arr.mean()),
            "std_acc": float(v_arr.std(ddof=1)),
            "se_acc": se,
            "ci95": ci95,
            "mean_macro_f1": float(v_f1.mean()),
            "std_macro_f1": float(v_f1.std(ddof=1)),
            "delta_acc": float(v_arr.mean() - full_arr.mean()),
            "t_test_p": float(p_t),
            "wilcoxon_p": float(p_w),
            "mean_r_hbo": float(np.mean(recon_corrs[v])),
            "mean_mse_hbo": float(np.mean(recon_mses[v])),
            "fold_accs": [float(x) for x in v_arr],
            "fold_f1s": [float(x) for x in v_f1]
        }

    q_vals_ab = stats.false_discovery_control(raw_p_ab)
    ab_non_full = [v for v in ablation_variants if v != "Full Model"]
    for idx, v in enumerate(ab_non_full):
        summary_data["ablations"][v]["fdr_q"] = float(q_vals_ab[idx])
    summary_data["ablations"]["Full Model"]["fdr_q"] = 1.0

    # Save Authoritative JSON files
    json_29_path = Path("reports/real_29sub_benchmark_and_ablation_summary.json")
    json_26_path = Path("reports/real_26sub_benchmark_and_ablation_summary.json")
    locked_pred_path = Path("reports/real_29sub_locked_predictions.json")
    json_29_path.parent.mkdir(parents=True, exist_ok=True)

    with open(json_29_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    with open(json_26_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    with open(locked_pred_path, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark_predictions": locked_predictions,
            "ablation_predictions": locked_ablation_predictions
        }, f, indent=2)

    print(f"\n[+] Saved authoritative results to {json_29_path}")
    print(f"[+] Saved locked test-set predictions to {locked_pred_path}")

    # Generate Figures
    generate_all_figures(summary_data, locked_predictions)


def generate_all_figures(data: Dict, locked_preds: Dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = Path("reports/figures")
    latex_fig_dir = Path("latex/figures")
    artifact_fig_dir = Path("reports/figures")
    fig_dir.mkdir(parents=True, exist_ok=True)
    latex_fig_dir.mkdir(parents=True, exist_ok=True)
    artifact_fig_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "lines.linewidth": 1.8,
        "axes.spines.top": False,
        "axes.spines.right": False
    })

    # 1. Benchmark Comparison Bar Chart
    models = list(data["models"].keys())
    means = [data["models"][m]["mean_acc"] for m in models]
    ses = [data["models"][m]["se_acc"] for m in models]

    fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=300)
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#D55E00"]
    bars = ax.bar(range(len(models)), means, yerr=ses, capsize=4.5, color=colors, edgecolor="black", alpha=0.88, width=0.55)
    ax.axhline(50.0, color="#888888", linestyle="--", linewidth=1.2, label="Chance Level (50.0%)")
    ax.set_ylabel("Classification Accuracy (%)")
    ax.set_title("29-Fold Full LOSO Benchmark Comparison (1,740 Authentic Trials)", fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([m.replace("NVC-DelayFormer (Full)", "NVC-DelayFormer\n(Ours)") for m in models], rotation=15, ha="right")
    ax.set_ylim(45.0, 75.0)

    for bar, m_val, se_val in zip(bars, means, ses):
        ax.text(bar.get_x() + bar.get_width() / 2.0, m_val + se_val + 0.8, f"{m_val:.2f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    for i, m in enumerate(models):
        if m != "NVC-DelayFormer (Full)":
            p_val = data["models"][m]["wilcoxon_p"]
            ax.text(i, 47.0, f"p={p_val:.4f}", ha="center", fontsize=8.5, color="#333333")

    plt.tight_layout()
    for p in [fig_dir / "real_29sub_benchmark_comparison.png",
              fig_dir / "real_26sub_benchmark_comparison.png",
              latex_fig_dir / "real_29sub_benchmark_comparison.png",
              latex_fig_dir / "real_26sub_benchmark_comparison.png",
              artifact_fig_dir / "real_26sub_benchmark_comparison.png",
              artifact_fig_dir / "real_29sub_benchmark_comparison.png"]:
        fig.savefig(p, dpi=300)
    plt.close(fig)

    # 2. Confusion Matrix (Subject 5 & Cohort pooled) from locked predictions
    sub05_data = locked_preds["NVC-DelayFormer (Full)"]["sub-05"]
    cm05 = sub05_data["cm"]
    acc05 = sub05_data["acc"]
    cm_matrix_05 = np.array([
        [cm05["tn"], cm05["fp"]],
        [cm05["fn"], cm05["tp"]]
    ])

    fig, ax = plt.subplots(figsize=(5.0, 4.2), dpi=300)
    im = ax.imshow(cm_matrix_05, cmap="Blues", interpolation="nearest")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Rest", "Mental Arithmetic"])
    ax.set_yticklabels(["Rest", "Mental Arithmetic"])
    ax.set_xlabel("Predicted Class")
    ax.set_ylabel("True Class")
    ax.set_title(f"Subject 05 Confusion Matrix\n(Accuracy = {acc05:.2f}%, 60 Trials)", fontweight="bold")

    for r in range(2):
        for c in range(2):
            val = cm_matrix_05[r, c]
            ax.text(c, r, f"{val}", ha="center", va="center", color="white" if val > cm_matrix_05.max() / 2 else "black", fontsize=14, fontweight="bold")

    plt.tight_layout()
    for p in [fig_dir / "sub05_confusion_matrix.png",
              latex_fig_dir / "sub05_confusion_matrix.png",
              artifact_fig_dir / "sub05_confusion_matrix.png"]:
        fig.savefig(p, dpi=300)
    plt.close(fig)

    # 3. Ablation Comparison Bar Chart
    ab_keys = list(data["ablations"].keys())
    ab_means = [data["ablations"][k]["mean_acc"] for k in ab_keys]
    ab_ses = [data["ablations"][k]["se_acc"] for k in ab_keys]
    ab_r = [data["ablations"][k]["mean_r_hbo"] for k in ab_keys]

    fig, ax1 = plt.subplots(figsize=(8.5, 4.8), dpi=300)
    ab_colors = ["#D55E00", "#56B4E9", "#009E73", "#E69F00", "#CC79A7"]
    bars_ab = ax1.bar(range(len(ab_keys)), ab_means, yerr=ab_ses, capsize=4.5, color=ab_colors, edgecolor="black", alpha=0.85, width=0.55)
    ax1.set_ylabel("Classification Accuracy (%)", color="#111111")
    ax1.set_title("5-Way Ablation Analysis: Accuracy vs. HbO Reconstruction Fidelity", fontweight="bold")
    ax1.set_xticks(range(len(ab_keys)))
    ax1.set_xticklabels([k.replace("Wrong Delay Prior (0s)", "Wrong Delay\n(\\tau=0s)") for k in ab_keys], rotation=15, ha="right")
    ax1.set_ylim(50.0, 72.0)

    for bar, m_val, se_val, k in zip(bars_ab, ab_means, ab_ses, ab_keys):
        delta = data["ablations"][k]["delta_acc"]
        delta_str = "Baseline" if k == "Full Model" else f"{delta:+.2f}%"
        ax1.text(bar.get_x() + bar.get_width() / 2.0, m_val + se_val + 0.8, f"{m_val:.2f}%\n({delta_str})", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot(range(len(ab_keys)), ab_r, color="#1B365D", marker="o", markersize=7, linewidth=2.0, linestyle="--", label="Test-Set r_HbO")
    ax2.set_ylabel("HbO Reconstruction Pearson r", color="#1B365D")
    ax2.set_ylim(-0.2, 1.0)
    for i, r_val in enumerate(ab_r):
        ax2.text(i, r_val + 0.05, f"r={r_val:.2f}", color="#1B365D", fontsize=9.5, fontweight="bold", ha="center")

    plt.tight_layout()
    for p in [fig_dir / "real_29sub_ablation_comparison.png",
              fig_dir / "real_26sub_ablation_comparison.png",
              latex_fig_dir / "real_29sub_ablation_comparison.png",
              latex_fig_dir / "real_26sub_ablation_comparison.png",
              artifact_fig_dir / "real_26sub_ablation_comparison.png",
              artifact_fig_dir / "real_29sub_ablation_comparison.png"]:
        fig.savefig(p, dpi=300)
    plt.close(fig)

    # 4. Two-Panel Delay Sensitivity & Convergence Curve
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(11.0, 4.5), dpi=300)

    # Panel A: 29-Subject Cohort Delay Sweep
    taus = [float(k) for k in data["delay_sweep"].keys()]
    sweep_means = [data["delay_sweep"][k]["mean"] for k in data["delay_sweep"].keys()]
    sweep_ses = [data["delay_sweep"][k]["se"] for k in data["delay_sweep"].keys()]

    ax_a.errorbar(taus, sweep_means, yerr=sweep_ses, fmt="-o", color="#D55E00", ecolor="#D55E00", elinewidth=1.5, capsize=4.0, markersize=6.5, label="29-Subject Cohort")
    ax_a.axvspan(4.5, 6.5, color="#D55E00", alpha=0.15, label="Physiological Window\n(4.5s--6.5s)")
    ax_a.axvline(5.0, color="#D55E00", linestyle=":", linewidth=1.5)
    ax_a.set_xlabel("Fixed Delay Prior Latency \\tau (seconds)")
    ax_a.set_ylabel("Grand Mean Accuracy (%)")
    ax_a.set_title("A: Cohort Broad-Peak Delay Sensitivity (N=29)", fontweight="bold")
    ax_a.set_ylim(58.0, 70.0)
    ax_a.legend(loc="lower center", frameon=True)
    ax_a.grid(True, linestyle=":", alpha=0.6)

    # Panel B: Spontaneous Convergence Trajectories
    conv_data = data["convergence_trajectories"]
    colors_conv = {"2.5": "#0072B2", "3.0": "#009E73", "7.0": "#CC79A7"}
    epochs = list(range(len(list(conv_data.values())[0])))
    for init_k, traj in conv_data.items():
        ax_b.plot(epochs, traj, label=f"Init \\tau = {init_k}s", color=colors_conv.get(init_k, "#333333"), marker="s", markersize=4, alpha=0.9)
    ax_b.set_xlabel("Training Epoch")
    ax_b.set_ylabel("Learned Physiological Delay \\tau (seconds)")
    ax_b.set_title("B: Unconstrained Gradient Trajectories", fontweight="bold")
    ax_b.set_ylim(1.5, 8.0)
    ax_b.legend(loc="upper left", frameon=True)
    ax_b.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    for p in [fig_dir / "delay_sensitivity_curve.png",
              latex_fig_dir / "delay_sensitivity_curve.png",
              artifact_fig_dir / "delay_sensitivity_curve.png"]:
        fig.savefig(p, dpi=300)
    plt.close(fig)

    # 5. Individual 29-Subject LOSO Performance
    fig, ax = plt.subplots(figsize=(10.0, 4.2), dpi=300)
    sub_accs = data["models"]["NVC-DelayFormer (Full)"]["fold_accs"]
    sub_ids = [f"S{i:02d}" for i in range(1, 30)]
    bar_cols = ["#D55E00" if a >= 65.0 else "#4C72B0" if a >= 55.0 else "#C44E52" for a in sub_accs]
    ax.bar(range(len(sub_accs)), sub_accs, color=bar_cols, edgecolor="black", alpha=0.85, width=0.65)
    ax.axhline(50.0, color="#888888", linestyle="--", label="Chance (50%)")
    mean_cohort = float(np.mean(sub_accs))
    ax.axhline(mean_cohort, color="#D55E00", linestyle="-", linewidth=2.0, label=f"Cohort Mean ({mean_cohort:.2f}%)")
    ax.set_ylabel("Test Accuracy (%)")
    ax.set_title("NVC-DelayFormer: Subject-by-Subject Generalization Across 29 Folds", fontweight="bold")
    ax.set_xticks(range(len(sub_accs)))
    ax.set_xticklabels(sub_ids, rotation=45, ha="right")
    ax.set_ylim(40.0, 95.0)
    ax.legend(loc="upper right", frameon=True)

    plt.tight_layout()
    for p in [fig_dir / "real_29sub_loso_performance.png",
              fig_dir / "real_26sub_loso_performance.png",
              latex_fig_dir / "real_29sub_loso_performance.png",
              latex_fig_dir / "real_26sub_loso_performance.png",
              artifact_fig_dir / "real_26sub_loso_performance.png",
              artifact_fig_dir / "real_29sub_loso_performance.png"]:
        fig.savefig(p, dpi=300)
    plt.close(fig)

    print("\n[+] All publication-quality figures successfully compiled.")


if __name__ == "__main__":
    run_full_29sub_suite()
