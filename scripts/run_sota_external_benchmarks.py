"""
Benchmark recent deep learning EEG-fNIRS SOTA models across both external validation cohorts:
1. Shin et al. (2018) Cognitive n-back Working Memory (0-back vs 2-back, 26 subjects, 1,872 trials)
2. Shin et al. (2017) Kinesthetic Motor Imagery (Left Hand vs Right Hand, 29 subjects, 1,740 trials)

Models evaluated:
- FGANet (Kwak et al., IEEE TNSRE 2022)
- EFMLNet (Sun et al., IEEE TNSRE 2023)
- MBC-ATT (Li et al., Front. Hum. Neurosci. 2024/2025)

Protocols:
- Strict participant-isolated Leave-One-Subject-Out (LOSO) cross-validation.
- Unsupervised Euclidean Alignment (EA) applied per subject on EEG.
- Checkpoint selection on held-out validation cohort.
- Two-sided paired Wilcoxon signed-rank test against NVC-DelayFormer Full Model.
- Benjamini-Hochberg FDR q-value multiple testing correction.
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


def evaluate_task(
    task_name: str,
    data_dir: Path,
    epoch_file: str,
    all_subs: List[int],
    n_val_subs: int,
    nvc_accs: List[float],
    device: torch.device
) -> Dict:
    print("\n" + "=" * 70)
    print(f"BENCHMARKING TASK: {task_name}")
    print(f"Subjects: {len(all_subs)}, Val Subjects per fold: {n_val_subs}")
    print("=" * 70)

    # 1. Load and cache with EA
    print(f"[*] Pre-caching and applying EA across {len(all_subs)} subjects...")
    cache = {}
    for sid in all_subs:
        d = torch.load(data_dir / f"sub-{sid:02d}" / epoch_file, weights_only=True)
        eeg_ea = align_subject_eeg(d["eeg"])
        cache[sid] = (
            eeg_ea.to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )
    print(f"    Loaded {len(cache)} subjects successfully.")

    model_factories = {
        "FGANet": lambda: FGANetClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, dropout=0.25),
        "EFMLNet": lambda: EFMLNetClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, dropout=0.25),
        "MBC-ATT": lambda: MBCATTClassifier(eeg_channels=30, fnirs_channels=72, num_classes=2, feature_dim=64, num_heads=4, dropout=0.25)
    }

    task_results = {}

    for model_name, factory in model_factories.items():
        print(f"\n--- Running {model_name} on {task_name} ---")
        t_start = time.time()
        fold_accs = []
        fold_f1s = []

        for test_sub in all_subs:
            set_seed(42 + test_sub)
            pool = [s for s in all_subs if s != test_sub]
            val_subs = [pool[(test_sub + i) % len(pool)] for i in range(n_val_subs)]
            train_subs = [s for s in pool if s not in val_subs]

            tr_e = torch.cat([cache[s][0] for s in train_subs], dim=0)
            tr_f = torch.cat([cache[s][1] for s in train_subs], dim=0)
            tr_l = torch.cat([cache[s][2] for s in train_subs], dim=0)

            val_e = torch.cat([cache[s][0] for s in val_subs], dim=0)
            val_f = torch.cat([cache[s][1] for s in val_subs], dim=0)
            val_l = torch.cat([cache[s][2] for s in val_subs], dim=0)

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

                # Validation
                model.eval()
                with torch.no_grad():
                    v_logits = model(val_e, val_f)
                    v_loss = criterion(v_logits, val_l).item()
                    v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

                if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                    best_val_acc = v_acc
                    best_val_loss = v_loss
                    best_state = copy.deepcopy(model.state_dict())

            # Test evaluation
            model.load_state_dict(best_state)
            model.eval()
            with torch.no_grad():
                te_logits = model(te_e, te_f)
                preds = te_logits.argmax(dim=-1).cpu().numpy()
                truth = te_l.cpu().numpy()
                acc, f1, _ = compute_metrics(truth, preds)
                fold_accs.append(acc)
                fold_f1s.append(f1)

            print(f"    Sub {test_sub:02d}: Acc = {acc:.2f}%, F1 = {f1:.2f}% (val = {best_val_acc:.2f}%)")

        mean_acc = float(np.mean(fold_accs))
        std_acc = float(np.std(fold_accs, ddof=1))
        macro_f1 = float(np.mean(fold_f1s))
        std_f1 = float(np.std(fold_f1s, ddof=1))
        ci_low, ci_high = compute_ci95(fold_accs)
        w_stat, p_val = stats.wilcoxon(nvc_accs, fold_accs, alternative="two-sided")

        elapsed = time.time() - t_start
        print(f"\n>>> {model_name} on {task_name} in {elapsed:.1f}s:")
        print(f"    Mean Acc: {mean_acc:.2f}% ± {std_acc:.2f}%")
        print(f"    Macro F1: {macro_f1:.2f}% ± {std_f1:.2f}%")
        print(f"    95% CI: [{ci_low:.2f}, {ci_high:.2f}]%")
        print(f"    Wilcoxon p vs NVC-DelayFormer: {p_val:.4e} (w_stat={w_stat})")

        task_results[model_name] = {
            "mean_acc": mean_acc,
            "std_acc": std_acc,
            "macro_f1": macro_f1,
            "std_f1": std_f1,
            "ci95": [ci_low, ci_high],
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p": float(p_val),
            "fold_accs": fold_accs,
            "fold_f1s": fold_f1s,
            "elapsed_sec": float(elapsed)
        }

    # Benjamini-Hochberg FDR correction
    model_names = list(task_results.keys())
    p_vals = [task_results[m]["wilcoxon_p"] for m in model_names]
    sorted_idx = np.argsort(p_vals)
    q_vals = [0.0] * len(p_vals)
    m_tests = len(p_vals)
    min_q = float("inf")
    for r in reversed(range(m_tests)):
        orig_i = sorted_idx[r]
        rank = r + 1
        q = p_vals[orig_i] * m_tests / rank
        min_q = min(min_q, q)
        q_vals[orig_i] = min(min_q, 1.0)

    for i, m in enumerate(model_names):
        task_results[m]["bh_q"] = float(q_vals[i])
        print(f"    {m}: p = {task_results[m]['wilcoxon_p']:.4e}, BH q = {task_results[m]['bh_q']:.4e}")

    return task_results


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting External Cohorts SOTA Benchmarks on device: {device}")
    t_grand_start = time.time()

    # Load baseline NVC-DelayFormer accuracies
    # 1. n-back
    nback_json = project_root / "reports" / "phase6_external_dataset_shin2018_nback_results.json"
    with open(nback_json, "r", encoding="utf-8") as f:
        nback_data = json.load(f)
    nvc_nback_accs = nback_data["models"]["NVC-DelayFormer (Full Model)"]["per_subject_acc"]

    # 2. MI
    mi_json = project_root / "reports" / "phase6_external_dataset_shin2017_mi_results.json"
    with open(mi_json, "r", encoding="utf-8") as f:
        mi_data = json.load(f)
    nvc_mi_accs = mi_data["models"]["NVC-DelayFormer (Full Model)"]["per_subject_acc"]

    grand_results = {}

    # Run n-back Working Memory
    nback_dir = project_root / "data" / "processed_shin2018_nback"
    grand_results["Working Memory (n-back)"] = evaluate_task(
        task_name="Working Memory (0-back vs 2-back)",
        data_dir=nback_dir,
        epoch_file="nback_epochs.pt",
        all_subs=list(range(1, 27)),
        n_val_subs=4,
        nvc_accs=nvc_nback_accs,
        device=device
    )

    # Run Motor Imagery
    mi_dir = project_root / "data" / "processed_shin2017_mi"
    grand_results["Motor Imagery"] = evaluate_task(
        task_name="Motor Imagery (Left vs Right Hand)",
        data_dir=mi_dir,
        epoch_file="mi_epochs.pt",
        all_subs=list(range(1, 30)),
        n_val_subs=5,
        nvc_accs=nvc_mi_accs,
        device=device
    )

    out_file = project_root / "reports" / "sota_external_benchmarks_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(grand_results, f, indent=2)
    print(f"\n[+] All external SOTA benchmarks saved to: {out_file}")
    print(f"Total Grand Elapsed Time: {time.time() - t_grand_start:.1f}s")


if __name__ == "__main__":
    main()
