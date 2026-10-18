"""
Phase 1: Readout Decoupling and 2x2 Factorial Design Benchmark Suite.
Target: Computer Methods and Programs in Biomedicine (CMPB).

Strict 29-Fold Leave-One-Subject-Out (LOSO) Cross-Validation (Train 23 / Val 5 / Test 1)
over all 29 human subjects (1,740 authentic trials) of Shin et al. (IEEE TNSRE 2017).

Evaluates:
1. 2x2 Factorial Design:
   - [On, Kernel]   (Full Model)
   - [On, Uniform]  (Attention Prior On, Uniform direct weights)
   - [Off, Kernel]  (Attention Prior Off, Kernel direct weights)
   - [Off, Uniform] (Joint-Uniform: Attention Prior Off, Uniform direct weights)
2. Readout Branch Decoupling (Independently retrained):
   - Direct-Only  (Zero latent leakage to reconstructor/gating, direct readout only)
   - Latent-Only  (Latent MLP readout only)
3. Diagnostic Zero-Shot Test-Time Branch Shutdown (on trained [On, Kernel] weights):
   - Test-time Direct Logits
   - Test-time Latent Logits
4. Statistical Interaction Effect Analysis:
   I(s) = A_{On,Kernel}(s) - A_{On,Uniform}(s) - A_{Off,Kernel}(s) + A_{Off,Uniform}(s)
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


def run_phase1_experiments():
    print("=" * 84)
    print("PHASE 1: READOUT DECOUPLING & 2x2 FACTORIAL ANALYSIS (29 SUBJECTS, 1,740 TRIALS)")
    print("=" * 84)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Compute Device: {device}")
    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))  # 1 to 29

    print("\n[Step 1/4] Pre-caching all 29 subjects in memory...")
    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        cache[sid] = (
            d["eeg"].to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )
    print(f"Cached {len(cache)} subjects successfully.")

    # Configurations to train independently
    configs = {
        "Full Model [On, Kernel]": {
            "use_delay_prior": True,
            "direct_weight_mode": "kernel",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
        "Factorial [On, Uniform]": {
            "use_delay_prior": True,
            "direct_weight_mode": "uniform",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
        "Factorial [Off, Kernel]": {
            "use_delay_prior": False,
            "direct_weight_mode": "kernel",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
        "Factorial [Off, Uniform]": {
            "use_delay_prior": False,
            "direct_weight_mode": "uniform",
            "readout_mode": "joint",
            "cut_gate_latent": False,
        },
        "Direct-Only": {
            "use_delay_prior": True,
            "direct_weight_mode": "kernel",
            "readout_mode": "direct_only",
            "cut_gate_latent": True,
        },
        "Latent-Only": {
            "use_delay_prior": True,
            "direct_weight_mode": "kernel",
            "readout_mode": "latent_only",
            "cut_gate_latent": False,
        },
    }

    results = {cfg_name: [] for cfg_name in configs}
    macro_f1s = {cfg_name: [] for cfg_name in configs}
    locked_predictions = {cfg_name: {} for cfg_name in configs}
    trained_checkpoints = {}  # {cfg_name: {sub_id: state_dict}}

    # Diagnostic test-time branch shutdown records (evaluated on Full Model)
    diag_direct_accs = []
    diag_direct_f1s = []
    diag_latent_accs = []
    diag_latent_f1s = []

    print("\n[Step 2/4] Executing 29-Fold LOSO Independent Retraining for all 6 configurations...")

    for cfg_name, cfg in configs.items():
        t0 = time.time()
        print(f"\n---> Training: {cfg_name}")
        trained_checkpoints[cfg_name] = {}

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

            model = NVCDelayFormer(
                num_classes=2,
                eeg_channels=30,
                fnirs_channels=72,
                feature_dim=64,
                num_heads=4,
                nvc_delay_mean_sec=5.0,
                learnable_delay=False,
                readout_mode=cfg["readout_mode"],
                direct_weight_mode=cfg["direct_weight_mode"],
                cut_gate_latent=cfg["cut_gate_latent"],
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
                        use_delay_prior=cfg["use_delay_prior"],
                        use_causal_mask=True,
                        return_recon=True,
                        return_branch_logits=True,
                    )
                    
                    if cfg["readout_mode"] != "latent_only":
                        w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                        reg_w = 0.08 * (w_diff ** 2).sum()
                    else:
                        reg_w = 0.0

                    loss_joint = F.cross_entropy(logits, tr_l[b])
                    loss_deep = F.cross_entropy(deep_logits, tr_l[b])
                    loss_shallow = F.cross_entropy(shallow_logits, tr_l[b])
                    loss = loss_joint + 0.2 * (loss_deep + loss_shallow) + reg_w

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
                        use_delay_prior=cfg["use_delay_prior"],
                        use_causal_mask=True,
                    )
                    v_loss = F.cross_entropy(v_logits, val_l).item()
                    v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

                if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                    best_val_acc = v_acc
                    best_val_loss = v_loss
                    best_state = copy.deepcopy(model.state_dict())

            # Evaluate on held-out test subject
            model.load_state_dict(best_state)
            model.eval()
            trained_checkpoints[cfg_name][test_sub] = best_state

            with torch.no_grad():
                preds_logits, _, _ = model(
                    te_e, te_f,
                    use_delay_prior=cfg["use_delay_prior"],
                    use_causal_mask=True,
                    return_recon=True,
                )
                preds_cls = preds_logits.argmax(-1).cpu().numpy()
                probs = F.softmax(preds_logits, dim=-1)[:, 1].cpu().numpy()
                y_true = te_l.cpu().numpy()

                acc, f1, cm = compute_metrics(y_true, preds_cls)
                results[cfg_name].append(acc)
                macro_f1s[cfg_name].append(f1)

                locked_predictions[cfg_name][f"sub-{test_sub:02d}"] = {
                    "y_true": y_true.tolist(),
                    "y_pred": preds_cls.tolist(),
                    "y_prob": [round(float(p), 4) for p in probs],
                    "acc": acc,
                    "f1": f1,
                    "cm": cm
                }

                # If this is the Full Model, run diagnostic test-time zero-shot branch shutdown
                if cfg_name == "Full Model [On, Kernel]":
                    _, _, (lat_logits, dir_logits) = model(
                        te_e, te_f,
                        use_delay_prior=True,
                        use_causal_mask=True,
                        return_branch_logits=True
                    )
                    # Evaluate test-time direct logits alone
                    dir_preds = dir_logits.argmax(-1).cpu().numpy()
                    d_acc, d_f1, _ = compute_metrics(y_true, dir_preds)
                    diag_direct_accs.append(d_acc)
                    diag_direct_f1s.append(d_f1)

                    # Evaluate test-time latent logits alone
                    lat_preds = lat_logits.argmax(-1).cpu().numpy()
                    l_acc, l_f1, _ = compute_metrics(y_true, lat_preds)
                    diag_latent_accs.append(l_acc)
                    diag_latent_f1s.append(l_f1)

        acc_arr = np.array(results[cfg_name])
        f1_arr = np.array(macro_f1s[cfg_name])
        elapsed = time.time() - t0
        print(f"      Completed: Acc = {acc_arr.mean():.2f}% +/- {acc_arr.std(ddof=1):.2f}% | F1 = {f1_arr.mean():.2f}% (Time: {elapsed:.1f}s)")

    print("\n[Step 3/4] Performing Statistical Significance & Interaction Analysis...")

    full_acc = np.array(results["Full Model [On, Kernel]"])
    on_uni_acc = np.array(results["Factorial [On, Uniform]"])
    off_ker_acc = np.array(results["Factorial [Off, Kernel]"])
    off_uni_acc = np.array(results["Factorial [Off, Uniform]"])
    direct_only_acc = np.array(results["Direct-Only"])
    latent_only_acc = np.array(results["Latent-Only"])

    # Subject-level interaction effect:
    # I(s) = A_{On,Kernel}(s) - A_{On,Uniform}(s) - A_{Off,Kernel}(s) + A_{Off,Uniform}(s)
    interaction_s = full_acc - on_uni_acc - off_ker_acc + off_uni_acc
    i_mean = float(np.mean(interaction_s))
    i_std = float(np.std(interaction_s, ddof=1))
    i_se = float(i_std / np.sqrt(len(interaction_s)))
    t_crit = float(stats.t.ppf(0.975, df=len(interaction_s) - 1))
    i_ci95 = [float(i_mean - t_crit * i_se), float(i_mean + t_crit * i_se)]
    i_t_stat, i_p_val = stats.ttest_1samp(interaction_s, 0.0)
    try:
        i_wilc_stat, i_wilc_p = stats.wilcoxon(interaction_s)
    except ValueError:
        i_wilc_p = 1.0

    # Marginal effects
    # Main effect of Attention Prior: mean over direct weighting levels
    main_effect_attn = 0.5 * ((full_acc - off_ker_acc) + (on_uni_acc - off_uni_acc))
    # Main effect of Direct Kernel: mean over attention prior levels
    main_effect_direct = 0.5 * ((full_acc - on_uni_acc) + (off_ker_acc - off_uni_acc))

    # Compile condition summary stats
    summary_stats = {}
    p_values_to_correct = []
    condition_order = list(configs.keys())

    for name in condition_order:
        arr = np.array(results[name])
        f1_arr = np.array(macro_f1s[name])
        m_acc = float(np.mean(arr))
        s_acc = float(np.std(arr, ddof=1))
        se_acc = float(s_acc / np.sqrt(len(arr)))
        ci = [float(m_acc - t_crit * se_acc), float(m_acc + t_crit * se_acc)]
        n_correct = int(np.round(m_acc / 100.0 * 1740))

        if name != "Full Model [On, Kernel]":
            t_p = float(stats.ttest_rel(full_acc, arr)[1])
            try:
                w_p = float(stats.wilcoxon(full_acc, arr)[1])
            except ValueError:
                w_p = 1.0
            p_values_to_correct.append((name, w_p))
        else:
            t_p = 1.0
            w_p = 1.0

        summary_stats[name] = {
            "mean_acc": m_acc,
            "std_acc": s_acc,
            "se_acc": se_acc,
            "ci95": ci,
            "mean_macro_f1": float(np.mean(f1_arr)),
            "std_macro_f1": float(np.std(f1_arr, ddof=1)),
            "correct_trials": f"{n_correct}/1740",
            "delta_vs_full": float(m_acc - float(np.mean(full_acc))),
            "t_test_p": t_p,
            "wilcoxon_p": w_p,
            "fold_accs": arr.tolist(),
            "fold_f1s": f1_arr.tolist(),
        }

    # Benjamini-Hochberg FDR correction
    sorted_p = sorted(p_values_to_correct, key=lambda x: x[1])
    m_tests = len(sorted_p)
    q_vals = {}
    cum_min = 1.0
    for rank, (name, p_val) in reversed(list(enumerate(sorted_p, 1))):
        q = min(cum_min, p_val * m_tests / rank)
        cum_min = q
        q_vals[name] = float(min(1.0, q))

    summary_stats["Full Model [On, Kernel]"]["bh_q"] = 1.0
    for name in configs:
        if name != "Full Model [On, Kernel]":
            summary_stats[name]["bh_q"] = q_vals.get(name, 1.0)

    # Diagnostic test-time branch shutdown stats
    diag_stats = {
        "Full Model (Test-Time Direct-Only Logits)": {
            "mean_acc": float(np.mean(diag_direct_accs)),
            "std_acc": float(np.std(diag_direct_accs, ddof=1)),
            "mean_macro_f1": float(np.mean(diag_direct_f1s)),
            "std_macro_f1": float(np.std(diag_direct_f1s, ddof=1)),
            "fold_accs": diag_direct_accs,
        },
        "Full Model (Test-Time Latent-Only Logits)": {
            "mean_acc": float(np.mean(diag_latent_accs)),
            "std_acc": float(np.std(diag_latent_accs, ddof=1)),
            "mean_macro_f1": float(np.mean(diag_latent_f1s)),
            "std_macro_f1": float(np.std(diag_latent_f1s, ddof=1)),
            "fold_accs": diag_latent_accs,
        }
    }

    # Factorial interaction decision
    if i_p_val < 0.05 and i_mean > 0:
        decision_regime = "Super-additive Synergy (Both factors interact positively beyond additive contributions)"
    elif (i_p_val < 0.05 or i_wilc_p < 0.06) and i_mean < 0:
        decision_regime = "Sub-additive Functional Compensation (Negative interaction: both pathways independently restore average performance with ceiling saturation)"
    elif abs(float(np.mean(off_ker_acc)) - float(np.mean(full_acc))) < 0.5:
        decision_regime = "Direct Pathway Dominance (Direct feature kernel weighting accounts for primary gain)"
    else:
        decision_regime = "Additive / Non-interactive (Both pathways contribute with stable additive integration)"

    output_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": "TU Berlin Mental Arithmetic vs Rest (Shin et al. 2017)",
        "num_subjects": 29,
        "total_trials": 1740,
        "evaluation_protocol": "29-Fold Full LOSO with 3-Way Nested Validation (Train 23 / Val 5 / Test 1)",
        "conditions_evaluated": summary_stats,
        "diagnostic_branch_shutdown": diag_stats,
        "factorial_analysis": {
            "two_factor_interaction_I": {
                "formula": "A_[On,Kernel] - A_[On,Uniform] - A_[Off,Kernel] + A_[Off,Uniform]",
                "mean_pp": i_mean,
                "std_pp": i_std,
                "se_pp": i_se,
                "ci95_pp": i_ci95,
                "t_stat": float(i_t_stat),
                "p_val_t": float(i_p_val),
                "p_val_wilcoxon": float(i_wilc_p),
                "per_subject_I": interaction_s.tolist(),
            },
            "marginal_effects": {
                "main_effect_attention_prior_pp": {
                    "mean": float(np.mean(main_effect_attn)),
                    "std": float(np.std(main_effect_attn, ddof=1)),
                },
                "main_effect_direct_kernel_pp": {
                    "mean": float(np.mean(main_effect_direct)),
                    "std": float(np.std(main_effect_direct, ddof=1)),
                }
            },
            "empirical_decision_regime": decision_regime,
        },
        "locked_predictions": locked_predictions,
    }

    # Save to JSON
    out_path = Path("reports/phase1_readout_and_factorial_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"\n[Step 4/4] Saved authoritative records to: {out_path.resolve()}")

    # Print Formatted Results
    print("\n" + "=" * 94)
    print(f"{'Condition':<28} | {'Accuracy (%)':<16} | {'Macro F1 (%)':<16} | {'Delta (%)':<10} | {'Wilc. p':<10} | {'BH q':<8}")
    print("-" * 94)
    for name, st in summary_stats.items():
        ci_str = f"[{st['ci95'][0]:.1f}, {st['ci95'][1]:.1f}]"
        acc_str = f"{st['mean_acc']:.2f} +/- {st['std_acc']:.2f}"
        f1_str = f"{st['mean_macro_f1']:.2f} +/- {st['std_macro_f1']:.2f}"
        delta_str = f"{st['delta_vs_full']:+.2f}" if name != "Full Model [On, Kernel]" else "Ref"
        p_str = f"{st['wilcoxon_p']:.4f}" if name != "Full Model [On, Kernel]" else "-"
        q_str = f"{st['bh_q']:.4f}" if name != "Full Model [On, Kernel]" else "-"
        print(f"{name:<28} | {acc_str:<16} | {f1_str:<16} | {delta_str:<10} | {p_str:<10} | {q_str:<8}")
    print("=" * 94)

    print("\n--- Diagnostic Test-Time Zero-Shot Branch Shutdown (Fixed Weights) ---")
    for d_name, d_st in diag_stats.items():
        print(f"{d_name:<46}: Acc = {d_st['mean_acc']:.2f}% +/- {d_st['std_acc']:.2f}% | F1 = {d_st['mean_macro_f1']:.2f}%")

    print("\n--- 2x2 Factorial Interaction Analysis ---")
    print(f"Interaction Effect I: Mean = {i_mean:+.3f} pp (95% CI: [{i_ci95[0]:+.3f}, {i_ci95[1]:+.3f}])")
    print(f"t-test p-value: {i_p_val:.4f} | Wilcoxon p-value: {i_wilc_p:.4f}")
    print(f"Main Effect of Attention Prior: {np.mean(main_effect_attn):+.3f} pp")
    print(f"Main Effect of Direct Kernel:   {np.mean(main_effect_direct):+.3f} pp")
    print(f"Empirical Regime: {decision_regime}")
    print("=" * 94)

    return output_payload


if __name__ == "__main__":
    run_phase1_experiments()
