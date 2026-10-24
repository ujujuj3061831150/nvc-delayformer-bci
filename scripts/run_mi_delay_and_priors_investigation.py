"""
Investigation Suite for Motor Imagery (Shin et al. 2017) Neurovascular Dynamics.

Experiment 1: Fixed-Weight Candidate Delay Sweep (tau in [0.0, 8.0]s) across 29 LOSO folds.
Experiment 2: 2x2 Factorial Retraining Decomposition of Delay Prior (P) and Causal Mask (M) on MI:
              - Full Model (P_on, M_on)
              - Delay Only (P_on, M_off)
              - Causal Mask Only (P_off, M_on)
              - Both Priors Off (P_off, M_off) [Unconstrained Attention]
"""

import sys
import copy
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
from scipy import stats
from sklearn.metrics import accuracy_score, f1_score

import torch
import torch.nn as nn
import torch.nn.functional as F

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.nvc_net import NVCDelayFormer
from src.run_phase6_shin2018_benchmark import (
    set_seed,
    euclidean_alignment,
    get_warmup_cosine_scheduler
)


def train_eval_variant(
    model: nn.Module,
    use_prior: bool,
    use_causal_mask: bool,
    readout_mode: str,
    tr_e: torch.Tensor, tr_f: torch.Tensor, tr_y: torch.Tensor,
    va_e: torch.Tensor, va_f: torch.Tensor, va_y: torch.Tensor,
    te_e: torch.Tensor, te_f: torch.Tensor, te_y: torch.Tensor,
    device: torch.device,
    epochs: int = 15,
    batch_size: int = 128,
    lr: float = 3e-3,
    weight_decay: float = 0.05
) -> Tuple[float, float, nn.Module]:
    """Train NVCDelayFormer variant and return test accuracy, macro F1, and best model."""
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = get_warmup_cosine_scheduler(optimizer, warmup_epochs=2, total_epochs=epochs)
    
    n_tr = tr_e.size(0)
    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_state = None

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n_tr, device=device)
        for idx in range(0, n_tr, batch_size):
            b = perm[idx:idx + batch_size]
            bx_e, bx_f, by = tr_e[b], tr_f[b], tr_y[b]
            
            optimizer.zero_grad()
            logits, _, recon_pred, (deep_logits, shallow_logits) = model(
                bx_e, bx_f,
                use_delay_prior=use_prior,
                use_causal_mask=use_causal_mask,
                return_recon=True,
                return_branch_logits=True
            )
            loss_joint = F.cross_entropy(logits, by)
            loss_deep = F.cross_entropy(deep_logits, by)
            loss_shallow = F.cross_entropy(shallow_logits, by)
            loss = loss_joint + 0.2 * (loss_deep + loss_shallow)
            
            if readout_mode != "latent_only" and hasattr(model, "direct_readout") and hasattr(model.direct_readout, "weight"):
                w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                loss = loss + 0.08 * (w_diff ** 2).sum()

            if recon_pred is not None:
                target_hbo = bx_f[:, :36, :]
                loss = loss + 1.0 * F.mse_loss(recon_pred, target_hbo)
                
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
        scheduler.step()

        # Validation check
        model.eval()
        with torch.no_grad():
            v_logits, _ = model(va_e, va_f, use_delay_prior=use_prior, use_causal_mask=use_causal_mask)
            v_loss = F.cross_entropy(v_logits, va_y).item()
            v_preds = torch.argmax(v_logits, dim=-1)
            v_acc = float((v_preds == va_y).float().mean().item()) * 100.0

        if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
            best_val_acc = v_acc
            best_val_loss = v_loss
            best_state = copy.deepcopy(model.state_dict())

    # Evaluate test set
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        t_logits, _ = model(te_e, te_f, use_delay_prior=use_prior, use_causal_mask=use_causal_mask)
        t_preds = torch.argmax(t_logits, dim=-1).cpu().numpy()
        y_true = te_y.cpu().numpy()

    acc = float(accuracy_score(y_true, t_preds)) * 100.0
    f1 = float(f1_score(y_true, t_preds, average="macro")) * 100.0
    return acc, f1, model


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running on device: {device}")
    
    data_dir = Path("data/processed_shin2017_mi")
    all_subs = sorted([int(p.name.split("-")[1]) for p in data_dir.glob("sub-*") if (p / "mi_epochs.pt").exists()])
    n_subjects = len(all_subs)
    assert n_subjects == 29

    print("Loading and pre-caching 29 subjects...")
    cache_eeg = {}
    cache_fnirs = {}
    cache_labels = {}

    for sid in all_subs:
        pt_path = data_dir / f"sub-{sid:02d}" / "mi_epochs.pt"
        loaded = torch.load(pt_path, map_location="cpu", weights_only=False)
        eeg_raw = loaded["eeg"].numpy()
        fnirs_raw = loaded["fnirs"].numpy()
        labels = loaded["labels"].numpy()

        eeg_ea = euclidean_alignment(eeg_raw)
        cache_eeg[sid] = torch.from_numpy(eeg_ea).float().to(device)
        cache_fnirs[sid] = torch.from_numpy(fnirs_raw).float().to(device)
        cache_labels[sid] = torch.from_numpy(labels).long().to(device)

    print(f"Cached {len(cache_eeg)} subjects.")

    # We will test 4 conditions:
    # 1. Full Model (P_on, M_on)
    # 2. Both Priors Off (P_off, M_off) -> unconstrained cross-attention
    # 3. Delay Only (P_on, M_off)
    # 4. Mask Only (P_off, M_on)
    conditions = [
        {"name": "Full Model (P_on, M_on)", "prior": True, "mask": True},
        {"name": "Both Priors Off (P_off, M_off)", "prior": False, "mask": False},
        {"name": "Delay Only (P_on, M_off)", "prior": True, "mask": False},
        {"name": "Mask Only (P_off, M_on)", "prior": False, "mask": True},
    ]

    cond_results = {c["name"]: {"accs": [], "f1s": []} for c in conditions}
    full_trained_models = {}

    print("\n" + "=" * 80)
    print("STEP 1: 29-FOLD LOSO EVALUATION ACROSS FACTORIAL PRIOR CONDITIONS ON MOTOR IMAGERY")
    print("=" * 80)

    t0_all = time.time()
    for fold_idx, test_sub in enumerate(all_subs):
        other_subs = [s for s in all_subs if s != test_sub]
        val_subs = [other_subs[(fold_idx + i) % len(other_subs)] for i in range(5)]
        train_subs = [s for s in other_subs if s not in val_subs]

        tr_e = torch.cat([cache_eeg[s] for s in train_subs], dim=0)
        tr_f = torch.cat([cache_fnirs[s] for s in train_subs], dim=0)
        tr_y = torch.cat([cache_labels[s] for s in train_subs], dim=0)

        va_e = torch.cat([cache_eeg[s] for s in val_subs], dim=0)
        va_f = torch.cat([cache_fnirs[s] for s in val_subs], dim=0)
        va_y = torch.cat([cache_labels[s] for s in val_subs], dim=0)

        te_e = cache_eeg[test_sub]
        te_f = cache_fnirs[test_sub]
        te_y = cache_labels[test_sub]

        fold_str = f"Fold {fold_idx+1:02d}/29 (Sub-{test_sub:02d})"

        for cond in conditions:
            set_seed(42 + test_sub)
            model = NVCDelayFormer(
                num_classes=2, eeg_channels=30, fnirs_channels=72, hbo_channels=36,
                feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0,
                learnable_delay=False, readout_mode="joint", direct_weight_mode="kernel", cut_gate_latent=False
            ).to(device)

            acc, f1, trained_m = train_eval_variant(
                model=model,
                use_prior=cond["prior"],
                use_causal_mask=cond["mask"],
                readout_mode="joint",
                tr_e=tr_e, tr_f=tr_f, tr_y=tr_y,
                va_e=va_e, va_f=va_f, va_y=va_y,
                te_e=te_e, te_f=te_f, te_y=te_y,
                device=device,
                epochs=15, batch_size=128
            )
            cond_results[cond["name"]]["accs"].append(acc)
            cond_results[cond["name"]]["f1s"].append(f1)

            if cond["name"] == "Full Model (P_on, M_on)":
                full_trained_models[test_sub] = trained_m

        print(f"{fold_str} | Full: {cond_results['Full Model (P_on, M_on)']['accs'][-1]:.2f}% | "
              f"Both Off: {cond_results['Both Priors Off (P_off, M_off)']['accs'][-1]:.2f}% | "
              f"Delay Only: {cond_results['Delay Only (P_on, M_off)']['accs'][-1]:.2f}% | "
              f"Mask Only: {cond_results['Mask Only (P_off, M_on)']['accs'][-1]:.2f}%")

    print(f"\nAll 29 folds completed in {time.time() - t0_all:.1f}s.")

    print("\n" + "=" * 80)
    print("STEP 2: FIXED-WEIGHT CANDIDATE DELAY SWEEP ON MOTOR IMAGERY (tau in [0.0..8.0]s)")
    print("=" * 80)

    tau_sweep = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    delay_sweep_results = {tau: [] for tau in tau_sweep}

    for tau in tau_sweep:
        for test_sub in all_subs:
            m = full_trained_models[test_sub]
            m.eval()
            te_e = cache_eeg[test_sub]
            te_f = cache_fnirs[test_sub]
            te_y = cache_labels[test_sub]

            # Set tau parameter
            m.cross_attention.tau.data.fill_(tau)
            with torch.no_grad():
                logits, _ = m(te_e, te_f, use_delay_prior=True, use_causal_mask=True)
                preds = logits.argmax(dim=-1).cpu().numpy()
                y_true = te_y.cpu().numpy()
                acc = float(accuracy_score(y_true, preds)) * 100.0
                delay_sweep_results[tau].append(acc)
            # Restore 5.0s
            m.cross_attention.tau.data.fill_(5.0)

    # Print Summary Tables
    print("\n" + "=" * 80)
    print("EXPERIMENT 1: MOTOR IMAGERY DELAY SENSITIVITY SWEEP SUMMARY (N=29 FOLDS)")
    print("=" * 80)
    sweep_summary = {}
    for tau in tau_sweep:
        accs = np.array(delay_sweep_results[tau])
        ci = stats.t.ppf(0.975, len(accs) - 1) * accs.std(ddof=1) / np.sqrt(len(accs))
        sweep_summary[tau] = {
            "mean": float(accs.mean()),
            "std": float(accs.std(ddof=1)),
            "ci95": float(ci),
            "raw_accs": accs.tolist()
        }
        print(f"  Delay tau = {tau:3.1f}s : Acc = {accs.mean():.2f}% +/- {accs.std(ddof=1):.2f}% (95% CI: [{accs.mean()-ci:.2f}, {accs.mean()+ci:.2f}])")

    print("\n" + "=" * 80)
    print("EXPERIMENT 2: MOTOR IMAGERY FACTORIAL PRIOR RETRAINING ABLATION (N=29 FOLDS)")
    print("=" * 80)
    factorial_summary = {}
    full_accs = np.array(cond_results["Full Model (P_on, M_on)"]["accs"])
    for cond in conditions:
        name = cond["name"]
        accs = np.array(cond_results[name]["accs"])
        f1s = np.array(cond_results[name]["f1s"])
        delta = float(accs.mean() - full_accs.mean())
        if name != "Full Model (P_on, M_on)":
            p_val = float(stats.wilcoxon(full_accs, accs)[1])
        else:
            p_val = 1.0

        factorial_summary[name] = {
            "mean_acc": float(accs.mean()),
            "std_acc": float(accs.std(ddof=1)),
            "mean_f1": float(f1s.mean()),
            "std_f1": float(f1s.std(ddof=1)),
            "delta_vs_full": delta,
            "wilcoxon_p": p_val,
            "raw_accs": accs.tolist()
        }
        print(f"  {name:<34} : Acc = {accs.mean():.2f}% +/- {accs.std(ddof=1):.2f}% | F1 = {f1s.mean():.2f}% | Delta = {delta:+.2f}pp (p = {p_val:.4f})")

    # Save to JSON
    out_file = Path("reports/mi_delay_and_priors_investigation_results.json")
    out_data = {
        "metadata": {
            "dataset": "Shin et al. (2017) Motor Imagery (29 subjects, 1740 trials)",
            "purpose": "Verify delay prior and causal mask dynamics on sensorimotor vs prefrontal paradigms",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "experiment1_delay_sweep": sweep_summary,
        "experiment2_factorial_priors": factorial_summary
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"\nResults successfully written to: {out_file}")


if __name__ == "__main__":
    main()
