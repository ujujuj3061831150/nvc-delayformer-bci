"""
Benchmark recent deep learning EEG-fNIRS SOTA models on the TU Berlin Mental Arithmetic dataset:
1. FGANet (Kwak et al., IEEE TNSRE 2022)
2. EFMLNet (Sun et al., IEEE TNSRE 2023)
3. MBC-ATT (Li et al., Front. Hum. Neurosci. 2024/2025)

Protocol:
- Strict 29-subject Leave-One-Subject-Out (LOSO) cross-validation (1,740 trials, 60 trials/subject).
- Nested validation: Train 23 subjects, Validation 5 subjects, Test 1 subject.
- Unsupervised Euclidean Alignment (EA) applied per subject on EEG.
- Seed: 42 (matching Table I Primary Seed).
- Comparison: Two-sided paired Wilcoxon signed-rank test against NVC-DelayFormer (79.37% ± 7.73%),
  followed by Benjamini-Hochberg FDR q-value correction.
"""

import sys
import copy
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import scipy.linalg
import scipy.stats as stats
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.baselines import (
    FGANetClassifier,
    EFMLNetClassifier,
    MBCATTClassifier
)
from src.train import get_warmup_cosine_scheduler
from src.utils.seed import set_seed


def align_subject_eeg(eeg_tensor: torch.Tensor) -> torch.Tensor:
    """
    Apply unsupervised Euclidean Alignment to a single subject's EEG trials.
    eeg_tensor: (N, C, T)
    """
    N, C, T = eeg_tensor.shape
    X = eeg_tensor.cpu().numpy()
    covs = [np.dot(X[i], X[i].T) / float(T) for i in range(N)]
    mean_cov = np.mean(covs, axis=0) + 1e-5 * np.eye(C)

    vals, vecs = scipy.linalg.eigh(mean_cov)
    vals = np.maximum(vals, 1e-6)
    r_inv_sqrt = np.dot(vecs, np.dot(np.diag(1.0 / np.sqrt(vals)), vecs.T))

    X_aligned = np.matmul(r_inv_sqrt[None, :, :], X)
    return torch.from_numpy(X_aligned).float()


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


def compute_ci95(data: List[float]) -> Tuple[float, float]:
    arr = np.array(data, dtype=np.float64)
    n = len(arr)
    m = np.mean(arr)
    se = stats.sem(arr)
    h = se * stats.t.ppf(0.975, df=n - 1)
    return float(m - h), float(m + h)


def run_sota_benchmark():
    print("=" * 80)
    print("BENCHMARKING RECENT MULTIMODAL DEEP LEARNING SOTA (2022-2024)")
    print("Models: FGANet (2022), EFMLNet (2023), MBC-ATT (2024)")
    print("Dataset: TU Berlin 29 Subjects (1,740 Real Trials) under LOSO Cross-Validation")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing on device: {device}")

    proc_dir = project_root / "data" / "processed"
    all_subs = list(range(1, 30))

    # Load and cache with EA
    print("\n[1/3] Pre-caching and applying Euclidean Alignment across 29 subjects...")
    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        eeg_ea = align_subject_eeg(d["eeg"])
        cache[sid] = (
            eeg_ea.to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )
    print(f"      Successfully cached {len(cache)} subjects ({len(cache)*60} trials).")

    # Authoritative NVC-DelayFormer Seed 42 benchmark per-subject accuracies
    summary_path = project_root / "reports" / "real_29sub_benchmark_and_ablation_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        auth_summary = json.load(f)
    nvc_accs = auth_summary["models"]["NVC-DelayFormer"]["fold_accs"]
    nvc_mean = auth_summary["models"]["NVC-DelayFormer"]["mean_acc"]
    print(f"\nTarget NVC-DelayFormer (Full Model) Baseline: {nvc_mean:.2f}% across 29 subjects.")

    model_factories = {
        "FGANet": lambda: FGANetClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, dropout=0.25),
        "EFMLNet": lambda: EFMLNetClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, dropout=0.25),
        "MBC-ATT": lambda: MBCATTClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, num_heads=4, dropout=0.25)
    }

    results = {}
    total_t0 = time.time()

    print("\n[2/3] Executing 29-Fold LOSO Training & Evaluation...")
    for model_name, factory in model_factories.items():
        print(f"\n--- Training {model_name} ---")
        dummy_model = factory()
        n_params = sum(p.numel() for p in dummy_model.parameters() if p.requires_grad)
        print(f"    Trainable parameters: {n_params:,}")

        fold_accs = []
        fold_f1s = []
        t_model_start = time.time()

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

            model = factory().to(device)
            opt = AdamW(model.parameters(), lr=1.5e-3, weight_decay=0.01)
            total_epochs = 15
            sched = get_warmup_cosine_scheduler(opt, warmup_epochs=2, total_epochs=total_epochs)
            criterion = nn.CrossEntropyLoss()

            bs = 64
            n_tr = tr_e.size(0)

            best_val_acc = -1.0
            best_val_loss = float("inf")
            best_state = None

            for epoch in range(1, total_epochs + 1):
                model.train()
                perm = torch.randperm(n_tr, device=device)
                for idx in range(0, n_tr, bs):
                    b = perm[idx:idx + bs]
                    opt.zero_grad()
                    logits = model(tr_e[b], tr_f[b])
                    loss = criterion(logits, tr_l[b])
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    opt.step()
                sched.step()

                # Validation selection
                model.eval()
                with torch.no_grad():
                    v_logits = model(val_e, val_f)
                    v_loss = criterion(v_logits, val_l).item()
                    v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

                if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                    best_val_acc = v_acc
                    best_val_loss = v_loss
                    best_state = copy.deepcopy(model.state_dict())

            # Evaluate on held-out test participant
            model.load_state_dict(best_state)
            model.eval()
            with torch.no_grad():
                te_logits = model(te_e, te_f)
                preds = te_logits.argmax(dim=-1).cpu().numpy()
                truth = te_l.cpu().numpy()
                acc, f1, _ = compute_metrics(truth, preds)
                fold_accs.append(acc)
                fold_f1s.append(f1)

            print(f"    Sub {test_sub:02d}/29: Acc = {acc:.2f}%, F1 = {f1:.2f}% (val_acc = {best_val_acc:.2f}%)")

        mean_acc = float(np.mean(fold_accs))
        std_acc = float(np.std(fold_accs, ddof=1))
        macro_f1 = float(np.mean(fold_f1s))
        ci_low, ci_high = compute_ci95(fold_accs)
        w_stat, p_val = stats.wilcoxon(nvc_accs, fold_accs, alternative="two-sided")

        elapsed = time.time() - t_model_start
        print(f"\n>>> {model_name} Completed in {elapsed:.1f}s:")
        print(f"    Mean Acc: {mean_acc:.2f}% ± {std_acc:.2f}%")
        print(f"    Macro F1: {macro_f1:.2f}%")
        print(f"    95% CI: [{ci_low:.2f}, {ci_high:.2f}]%")
        print(f"    Wilcoxon p vs NVC-DelayFormer: {p_val:.4e} (w_stat={w_stat})")

        results[model_name] = {
            "parameters": n_params,
            "mean_acc": mean_acc,
            "std_acc": std_acc,
            "macro_f1": macro_f1,
            "ci95": [ci_low, ci_high],
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p": float(p_val),
            "fold_accs": fold_accs,
            "fold_f1s": fold_f1s,
            "elapsed_sec": float(elapsed)
        }

    # Multiple testing correction (Benjamini-Hochberg FDR)
    print("\n[3/3] Computing Benjamini-Hochberg FDR q-values...")
    model_names = list(results.keys())
    p_vals = [results[m]["wilcoxon_p"] for m in model_names]

    # Rank p-values
    sorted_indices = np.argsort(p_vals)
    q_vals = [0.0] * len(p_vals)
    m_tests = len(p_vals)

    min_q = float("inf")
    for rank_idx in reversed(range(m_tests)):
        orig_idx = sorted_indices[rank_idx]
        rank = rank_idx + 1
        q = p_vals[orig_idx] * m_tests / rank
        min_q = min(min_q, q)
        q_vals[orig_idx] = min(min_q, 1.0)

    for i, m in enumerate(model_names):
        results[m]["bh_q"] = float(q_vals[i])
        print(f"    {m}: p = {results[m]['wilcoxon_p']:.4e}, BH q = {results[m]['bh_q']:.4e}")

    output_path = project_root / "reports" / "sota_benchmarks_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Full benchmark metrics saved to: {output_path}")
    print(f"Total time elapsed: {time.time() - total_t0:.1f}s")


if __name__ == "__main__":
    run_sota_benchmark()
