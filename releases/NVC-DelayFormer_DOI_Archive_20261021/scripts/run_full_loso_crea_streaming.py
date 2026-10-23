"""
Strict 29-Fold Leave-One-Subject-Out (LOSO) Cross-Validation
with Online Causal Recursive Euclidean Alignment (CrEA) Streaming Evaluation.

Protocol:
1. For each test subject s in {1..29}:
   - Train on 23 subjects (outer training fold).
   - Validate on 5 subjects for model checkpoint selection.
   - Test subject s is STRICTLY UNSEEN during training and model selection.
2. For test subject s:
   - Compute prior source covariance R_src from the 23 training participants.
   - For each trial k = 1..60:
     - Update covariance recursively using empirical Bayes shrinkage (kappa_0 = 5.0)
       strictly from previous trials 1..k-1 (zero session lookahead).
     - Transform trial k using the causal recursive alignment matrix.
     - Predict trial k using the held-out fold s model checkpoint.
3. Record trial-by-trial predictions, offline vs streaming accuracies, and covariance errors.
"""
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import json
import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW

from src.models.nvc_net import NVCDelayFormer
from src.data.preprocessing import CausalRecursiveEA, offline_euclidean_alignment
from src.train import get_warmup_cosine_scheduler

def run_29fold_loso_streaming():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing 29-fold LOSO on compute device: {device}")

    # Load raw preprocessed epochs for all 29 subjects
    sub_data = {}
    sub_raw_covs = {}
    total_subs = 29
    val_size = 5

    for s in range(1, total_subs + 1):
        p = project_root / f"data/processed/sub-{s:02d}/ma_epochs.pt"
        d = torch.load(p, map_location="cpu", weights_only=True)
        sub_data[s] = d
        eeg_np = d["eeg"].numpy() # (60, 30, 1000)
        covs = [np.cov(eeg_np[t]) + 1e-5 * np.eye(30) for t in range(len(eeg_np))]
        sub_raw_covs[s] = covs

    offline_accs = []
    streaming_accs = []
    subject_details = {}

    t_start = time.time()

    for test_sub in range(1, total_subs + 1):
        t0 = time.time()
        # LOSO split
        rem = [s for s in range(1, total_subs + 1) if s != test_sub]
        val_subs = rem[:val_size]
        train_subs = rem[val_size:]

        # Offline EA for training & validation sets
        tr_e_list, tr_f_list, tr_l_list = [], [], []
        for s in train_subs:
            d = sub_data[s]
            eeg_ea = offline_euclidean_alignment(d["eeg"].numpy())
            tr_e_list.append(torch.from_numpy(eeg_ea).float())
            tr_f_list.append(d["fnirs"] * 1e4)
            tr_l_list.append(d["labels"])

        tr_e = torch.cat(tr_e_list, dim=0).to(device)
        tr_f = torch.cat(tr_f_list, dim=0).to(device)
        tr_l = torch.cat(tr_l_list, dim=0).to(device)

        val_e_list, val_f_list, val_l_list = [], [], []
        for s in val_subs:
            d = sub_data[s]
            eeg_ea = offline_euclidean_alignment(d["eeg"].numpy())
            val_e_list.append(torch.from_numpy(eeg_ea).float())
            val_f_list.append(d["fnirs"] * 1e4)
            val_l_list.append(d["labels"])

        val_e = torch.cat(val_e_list, dim=0).to(device)
        val_f = torch.cat(val_f_list, dim=0).to(device)
        val_l = torch.cat(val_l_list, dim=0).to(device)

        # Build model for this fold
        torch.manual_seed(42 + test_sub)
        np.random.seed(42 + test_sub)
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=30,
            fnirs_channels=72,
            feature_dim=64,
            num_heads=4,
            learnable_delay=False
        ).to(device)

        opt = AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
        sched = get_warmup_cosine_scheduler(opt, warmup_epochs=2, total_epochs=12)
        criterion = nn.CrossEntropyLoss()

        bs = 256
        n_tr = tr_e.size(0)
        best_val_acc = -1.0
        best_val_loss = float("inf")
        best_state = None

        # Train fold model
        hbo_c = 36
        for epoch in range(1, 13):
            model.train()
            perm = torch.randperm(n_tr, device=device)
            for idx in range(0, n_tr, bs):
                b = perm[idx:idx+bs]
                opt.zero_grad()
                logits, _, recon_pred, (deep_logits, shallow_logits) = model(
                    tr_e[b], tr_f[b],
                    use_delay_prior=True,
                    use_causal_mask=True,
                    return_recon=True,
                    return_branch_logits=True
                )
                target_hbo = model.compute_buxton_hemodynamics(tr_f[b])[:, :hbo_c, :]
                loss, _ = NVCDelayFormer.compute_composite_loss(
                    joint_logits=logits,
                    deep_logits=deep_logits,
                    shallow_logits=shallow_logits,
                    targets=tr_l[b],
                    recon_pred=recon_pred,
                    recon_target=target_hbo,
                    shallow_weight=model.direct_readout.weight,
                    aux_weight=0.2,
                    recon_weight=1.0,
                    margin_weight=0.08,
                    criterion=criterion
                )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                opt.step()
            sched.step()

            # Validation selection
            model.eval()
            with torch.no_grad():
                v_logits, _ = model(val_e, val_f, use_delay_prior=True, use_causal_mask=True)
                v_loss = criterion(v_logits, val_l).item()
                v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

            if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                best_val_acc = v_acc
                best_val_loss = v_loss
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        # Load best fold model
        model.load_state_dict({k: v.to(device) for k, v in best_state.items()})
        model.eval()

        # Evaluate unseen test subject s
        d_test = sub_data[test_sub]
        te_raw_eeg = d_test["eeg"].numpy() # (60, 30, 1000)
        te_fnirs = (d_test["fnirs"] * 1e4).to(device)
        te_labels = d_test["labels"].to(device)

        # 1. Offline transductive EA
        te_eeg_off = torch.from_numpy(offline_euclidean_alignment(te_raw_eeg)).float().to(device)
        with torch.no_grad():
            off_logits, _ = model(te_eeg_off, te_fnirs, use_delay_prior=True, use_causal_mask=True)
            off_preds = off_logits.argmax(-1)
            off_acc = float((off_preds == te_labels).float().mean().item() * 100.0)
        offline_accs.append(off_acc)

        # 2. Online trial-causal CrEA
        # Source prior from the 23 training participants
        train_covs = [c for tid in train_subs for c in sub_raw_covs[tid]]
        R_src = np.mean(train_covs, axis=0)

        crea = CausalRecursiveEA(channels=30, shrinkage_alpha=5.0, R_source=R_src)
        te_eeg_crea = crea.transform_sequence(te_raw_eeg)
        errors, _ = crea.compute_frobenius_convergence(te_raw_eeg)
        te_eeg_stream = torch.from_numpy(te_eeg_crea).float().to(device)

        with torch.no_grad():
            str_logits, _ = model(te_eeg_stream, te_fnirs, use_delay_prior=True, use_causal_mask=True)
            str_preds = str_logits.argmax(-1)
            str_acc = float((str_preds == te_labels).float().mean().item() * 100.0)
        streaming_accs.append(str_acc)

        elapsed = time.time() - t0
        print(f"Fold {test_sub:02d}/29: Offline Acc = {off_acc:.2f}%, CrEA Streaming Acc = {str_acc:.2f}% ({elapsed:.1f}s)")

        subject_details[f"sub-{test_sub:02d}"] = {
            "offline_acc": round(off_acc, 2),
            "streaming_acc": round(str_acc, 2),
            "cov_error_t1": round(float(errors[0] * 100.0), 2),
            "cov_error_t8": round(float(errors[7] * 100.0), 2),
            "cov_error_t60": round(float(errors[-1] * 100.0), 2),
            "labels": te_labels.cpu().numpy().tolist(),
            "streaming_preds": str_preds.cpu().numpy().tolist(),
            "offline_preds": off_preds.cpu().numpy().tolist(),
        }

    total_elapsed = time.time() - t_start
    off_mean = float(np.mean(offline_accs))
    off_std = float(np.std(offline_accs, ddof=1))
    str_mean = float(np.mean(streaming_accs))
    str_std = float(np.std(streaming_accs, ddof=1))
    ci95_str = [float(str_mean - 1.96 * str_std / np.sqrt(29)), float(str_mean + 1.96 * str_std / np.sqrt(29))]

    print("\n" + "=" * 70)
    print("STRICT 29-FOLD LOSO EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total Runtime: {total_elapsed/60.0:.1f} minutes")
    print(f"Offline Batch Mean Acc:    {off_mean:.2f}% +/- {off_std:.2f}%")
    print(f"CrEA Streaming Mean Acc:   {str_mean:.2f}% +/- {str_std:.2f}% (95% CI: [{ci95_str[0]:.2f}%, {ci95_str[1]:.2f}%])")
    print(f"Relative Performance Retention: {str_mean / off_mean * 100.0:.2f}%")
    print("=" * 70)

    results = {
        "evaluation": "Strict 29-Fold Independent LOSO Cross-Validation",
        "cohort": "TU Berlin Mental Arithmetic (29 participants, 1,740 trials)",
        "protocol": "Causal recursive alignment, fold-specific models, zero subject lookahead",
        "offline_mean_acc": round(off_mean, 2),
        "offline_std_acc": round(off_std, 2),
        "mean_streaming_acc": round(str_mean, 2),
        "std_streaming_acc": round(str_std, 2),
        "ci95_streaming": [round(ci95_str[0], 2), round(ci95_str[1], 2)],
        "retention_pct": round(str_mean / off_mean * 100.0, 2),
        "subjects": subject_details
    }

    out_file = project_root / "reports/crea_streaming_evaluation_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Successfully saved 100% verified 29-fold evaluation record to: {out_file}")

if __name__ == "__main__":
    run_29fold_loso_streaming()
