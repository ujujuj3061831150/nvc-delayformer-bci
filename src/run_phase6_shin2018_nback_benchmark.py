"""
Phase 6 (Cohort 2): Independent External Dataset Cross-Subject Validation on Shin et al. (2018) n-back Working Memory.
Evaluates NVC-DelayFormer and baseline architectures on the independent 26-subject
TU Berlin Cognitive n-back Working Memory dataset (Shin et al., Scientific Data 2018, 5:180003; 26 healthy subjects, 1,872 trials).

Task: 0-back (low cognitive workload) vs. 2-back (high cognitive workload).
Protocol:
- 26-fold Leave-One-Subject-Out (LOSO) cross-validation.
- For held-out test subject s in {1..26}:
  - 4 validation subjects: pool[(s + i) % 25] for i in 0..3 among the remaining 25 subjects.
  - 21 training subjects (exclusively used for backpropagation / covariance estimation).
  - 1 held-out test subject (evaluated strictly ONCE using best validation checkpoint).
  - Seed: 42 + s.
- Models Evaluated (Matching Table 5 in CMPB manuscript):
  1. NVC-DelayFormer (Full Model: Joint Readout + Gaussian Delay Prior + Kernel Weighting)
  2. Handcrafted Shrinkage-LDA (Ledoit-Wolf analytical shrinkage)
  3. Handcrafted Multimodal SVM (Validation-tuned C parameter)
  4. Latent-Only (Deep token-level cross-attention MLP readout)
  5. Direct-Only (Shallow biophysical direct features with optical proxy gating)
  6. Authentic EEGNet-2D (Lawhern et al. 2018, 30 channels)
"""

import sys
import copy
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import scipy.signal as signal
from scipy.stats import wilcoxon, t as student_t
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score

import torch
import torch.nn as nn
import torch.nn.functional as F

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from temporal_fusion import NVCDelayFormer
from src.models.baselines import AuthenticEEGNet2D
from src.run_phase6_shin2018_benchmark import (
    set_seed,
    euclidean_alignment,
    extract_handcrafted_features,
    get_warmup_cosine_scheduler,
    train_nvc_variant,
    train_eegnet
)


def bh_fdr(p_values: List[float]) -> List[float]:
    p_values = np.asarray(p_values)
    n = len(p_values)
    order = np.argsort(p_values)
    ranked_p = p_values[order]
    q_values = np.zeros(n)
    curr_min = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        q = min(curr_min, ranked_p[i] * n / rank)
        curr_min = q
        q_values[order[i]] = q
    return [float(x) for x in q_values]


def run_shin2018_nback_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data_dir = Path("data/processed_shin2018_nback")
    
    all_subs = sorted([int(p.name.split("-")[1]) for p in data_dir.glob("sub-*") if (p / "nback_epochs.pt").exists()])
    n_subjects = len(all_subs)
    assert n_subjects == 26, f"Expected 26 subjects, found {n_subjects}"

    print("=" * 86)
    print(f"26-FOLD LOSO BENCHMARK ON SHIN ET AL. (2018) N-BACK WORKING MEMORY ({n_subjects} SUBJECTS)")
    print(f"Device: {device} | 1,872 total trials (72 per subject: 36 0-back / 36 2-back)")
    print("=" * 86)

    # 1. Load, align and cache all subjects
    print("\n[Step 1/2] Pre-processing, Euclidean Alignment, and Caching all 26 subjects...")
    t0 = time.time()
    cache_eeg = {}
    cache_fnirs = {}
    cache_labels = {}
    cache_feats = {}

    for sid in all_subs:
        pt_path = data_dir / f"sub-{sid:02d}" / "nback_epochs.pt"
        loaded = torch.load(pt_path, map_location="cpu", weights_only=False)
        eeg_raw = loaded["eeg"].numpy()      # (72, 30, 1000)
        fnirs_raw = loaded["fnirs"].numpy()  # (72, 72, 124)
        labels = loaded["labels"].numpy()    # (72,)

        # Unsupervised Euclidean Alignment per subject
        eeg_ea = euclidean_alignment(eeg_raw)

        # Handcrafted multimodal features (306 dims)
        feats = extract_handcrafted_features(eeg_raw, fnirs_raw)

        cache_eeg[sid] = torch.from_numpy(eeg_ea).float().to(device)
        cache_fnirs[sid] = torch.from_numpy(fnirs_raw).float().to(device)
        cache_labels[sid] = torch.from_numpy(labels).long().to(device)
        cache_feats[sid] = feats

    print(f"Done caching in {time.time() - t0:.2f}s.")

    # 2. Models to evaluate
    model_names = [
        "NVC-DelayFormer (Full Model)",
        "Handcrafted Shrinkage-LDA",
        "Handcrafted Multimodal SVM",
        "Latent-Only (Deep)",
        "Direct-Only (Shallow)",
        "Authentic EEGNet-2D"
    ]

    fold_accuracies = {m: [] for m in model_names}
    fold_f1s = {m: [] for m in model_names}

    print("\n[Step 2/2] Running 26-Fold LOSO Cross-Validation...")
    total_start = time.time()

    for fold_idx, test_sub in enumerate(all_subs):
        f_start = time.time()
        other_subs = [s for s in all_subs if s != test_sub]
        
        # 4 Validation subjects, remaining 21 are training
        val_subs = [other_subs[(fold_idx + i) % len(other_subs)] for i in range(4)]
        train_subs = [s for s in other_subs if s not in val_subs]

        # Tensors
        tr_e = torch.cat([cache_eeg[s] for s in train_subs], dim=0)
        tr_f = torch.cat([cache_fnirs[s] for s in train_subs], dim=0)
        tr_y = torch.cat([cache_labels[s] for s in train_subs], dim=0)

        va_e = torch.cat([cache_eeg[s] for s in val_subs], dim=0)
        va_f = torch.cat([cache_fnirs[s] for s in val_subs], dim=0)
        va_y = torch.cat([cache_labels[s] for s in val_subs], dim=0)

        te_e = cache_eeg[test_sub]
        te_f = cache_fnirs[test_sub]
        te_y = cache_labels[test_sub]

        # Features
        tr_feats = np.concatenate([cache_feats[s] for s in train_subs], axis=0)
        tr_feats_y = tr_y.cpu().numpy()
        va_feats = np.concatenate([cache_feats[s] for s in val_subs], axis=0)
        va_feats_y = va_y.cpu().numpy()
        te_feats = cache_feats[test_sub]
        te_feats_y = te_y.cpu().numpy()

        scaler = StandardScaler()
        tr_feats_sc = scaler.fit_transform(tr_feats)
        va_feats_sc = scaler.transform(va_feats)
        te_feats_sc = scaler.transform(te_feats)

        # A. Handcrafted Shrinkage-LDA
        lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        lda.fit(tr_feats_sc, tr_feats_y)
        lda_preds = lda.predict(te_feats_sc)
        fold_accuracies["Handcrafted Shrinkage-LDA"].append(float(accuracy_score(te_feats_y, lda_preds)) * 100.0)
        fold_f1s["Handcrafted Shrinkage-LDA"].append(float(f1_score(te_feats_y, lda_preds, average="macro")) * 100.0)

        # B. Handcrafted Multimodal SVM (validation-tuned C)
        best_svm = None
        best_va_score = -1.0
        for C_val in [0.01, 0.1, 1.0, 10.0]:
            svm = SVC(C=C_val, kernel="rbf", gamma="scale", random_state=42 + test_sub)
            svm.fit(tr_feats_sc, tr_feats_y)
            va_acc = accuracy_score(va_feats_y, svm.predict(va_feats_sc))
            if va_acc > best_va_score:
                best_va_score = va_acc
                best_svm = svm
        svm_preds = best_svm.predict(te_feats_sc)
        fold_accuracies["Handcrafted Multimodal SVM"].append(float(accuracy_score(te_feats_y, svm_preds)) * 100.0)
        fold_f1s["Handcrafted Multimodal SVM"].append(float(f1_score(te_feats_y, svm_preds, average="macro")) * 100.0)

        # C. NVC-DelayFormer (Full Model)
        set_seed(42 + test_sub)
        nvc_full = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, hbo_channels=36,
            feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0,
            learnable_delay=False, readout_mode="joint", direct_weight_mode="kernel", cut_gate_latent=False
        ).to(device)
        acc_full, f1_full = train_nvc_variant(
            nvc_full, use_prior=True, readout_mode="joint",
            tr_e=tr_e, tr_f=tr_f, tr_y=tr_y,
            va_e=va_e, va_f=va_f, va_y=va_y,
            te_e=te_e, te_f=te_f, te_y=te_y,
            device=device, epochs=15, batch_size=128
        )
        fold_accuracies["NVC-DelayFormer (Full Model)"].append(acc_full)
        fold_f1s["NVC-DelayFormer (Full Model)"].append(f1_full)

        # D. Latent-Only (Deep)
        set_seed(42 + test_sub)
        lat_model = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, hbo_channels=36,
            feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0,
            learnable_delay=False, readout_mode="latent_only", direct_weight_mode="kernel", cut_gate_latent=False
        ).to(device)
        acc_lat, f1_lat = train_nvc_variant(
            lat_model, use_prior=True, readout_mode="latent_only",
            tr_e=tr_e, tr_f=tr_f, tr_y=tr_y,
            va_e=va_e, va_f=va_f, va_y=va_y,
            te_e=te_e, te_f=te_f, te_y=te_y,
            device=device, epochs=15, batch_size=128
        )
        fold_accuracies["Latent-Only (Deep)"].append(acc_lat)
        fold_f1s["Latent-Only (Deep)"].append(f1_lat)

        # E. Direct-Only (Shallow)
        set_seed(42 + test_sub)
        dir_model = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, hbo_channels=36,
            feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0,
            learnable_delay=False, readout_mode="direct_only", direct_weight_mode="kernel", cut_gate_latent=True
        ).to(device)
        acc_dir, f1_dir = train_nvc_variant(
            dir_model, use_prior=True, readout_mode="direct_only",
            tr_e=tr_e, tr_f=tr_f, tr_y=tr_y,
            va_e=va_e, va_f=va_f, va_y=va_y,
            te_e=te_e, te_f=te_f, te_y=te_y,
            device=device, epochs=15, batch_size=128
        )
        fold_accuracies["Direct-Only (Shallow)"].append(acc_dir)
        fold_f1s["Direct-Only (Shallow)"].append(f1_dir)

        # F. Authentic EEGNet-2D
        set_seed(42 + test_sub)
        eegnet = AuthenticEEGNet2D(in_channels=30, num_classes=2, kernel_len=64, dropout=0.25).to(device)
        acc_eegnet, f1_eegnet = train_eegnet(
            eegnet,
            tr_e=tr_e, tr_y=tr_y,
            va_e=va_e, va_y=va_y,
            te_e=te_e, te_y=te_y,
            device=device, epochs=15, batch_size=128
        )
        fold_accuracies["Authentic EEGNet-2D"].append(acc_eegnet)
        fold_f1s["Authentic EEGNet-2D"].append(f1_eegnet)

        print(
            f"Fold {fold_idx + 1:02d}/26 (VP{test_sub:03d}) | "
            f"Full: {acc_full:.2f}% | LDA: {fold_accuracies['Handcrafted Shrinkage-LDA'][-1]:.2f}% | "
            f"EEGNet: {acc_eegnet:.2f}% | SVM: {fold_accuracies['Handcrafted Multimodal SVM'][-1]:.2f}% | "
            f"Latent: {acc_lat:.2f}% | Direct: {acc_dir:.2f}% ({time.time() - f_start:.1f}s)"
        )

    print(f"\nAll 26 folds finished in {time.time() - total_start:.2f}s.")

    # 3. Aggregate statistics and significance tests
    summary = {
        "metadata": {
            "dataset": "Shin et al. (2018) Scientific Data (DOI: 10.1038/sdata.2018.3)",
            "task": "n-back Working Memory (0-back vs. 2-back)",
            "num_subjects": 26,
            "total_trials": 1872,
            "trials_per_sub": 72,
            "evaluation": "26-fold Leave-One-Subject-Out (LOSO)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "models": {}
    }

    full_accs = np.array(fold_accuracies["NVC-DelayFormer (Full Model)"])
    model_keys_for_stats = [m for m in model_names if m != "NVC-DelayFormer (Full Model)"]

    p_values_dict = {}
    for m in model_keys_for_stats:
        m_accs = np.array(fold_accuracies[m])
        # Two-sided paired Wilcoxon signed-rank test
        try:
            stat, p_val = wilcoxon(full_accs, m_accs)
        except Exception:
            p_val = 1.0
        p_values_dict[m] = float(p_val)

    # BH FDR Correction across all comparisons against full model
    q_vals = bh_fdr([p_values_dict[m] for m in model_keys_for_stats])
    q_values_dict = {m: q for m, q in zip(model_keys_for_stats, q_vals)}

    print("\n" + "=" * 86)
    print("FINAL 26-FOLD LOSO GRAND SUMMARY TABLE: SHIN ET AL. (2018) N-BACK (0-back vs. 2-back)")
    print("=" * 86)
    print(f"{'Model Architecture':<32} | {'Accuracy (%)':<18} | {'95% CI (%)':<16} | {'Macro F1 (%)':<18} | {'Wilcoxon p':<12} | {'BH q':<10}")
    print("-" * 115)

    for m in model_names:
        accs = np.array(fold_accuracies[m])
        f1s = np.array(fold_f1s[m])
        mean_acc = float(accs.mean())
        std_acc = float(accs.std(ddof=1))
        se_acc = std_acc / np.sqrt(len(accs))
        # df = 25 -> critical t = 2.060
        ci_95 = [float(mean_acc - 2.060 * se_acc), float(mean_acc + 2.060 * se_acc)]

        mean_f1 = float(f1s.mean())
        std_f1 = float(f1s.std(ddof=1))

        p_str = f"{p_values_dict[m]:.4f}" if m in p_values_dict else "--"
        q_str = f"{q_values_dict[m]:.4f}" if m in q_values_dict else "--"

        summary["models"][m] = {
            "per_subject_acc": [round(float(x), 2) for x in accs],
            "per_subject_f1": [round(float(x), 2) for x in f1s],
            "mean_acc": round(mean_acc, 2),
            "std_acc": round(std_acc, 2),
            "ci_95": [round(ci_95[0], 2), round(ci_95[1], 2)],
            "mean_f1": round(mean_f1, 2),
            "std_f1": round(std_f1, 2),
            "wilcoxon_p": p_values_dict.get(m, None),
            "bh_q": q_values_dict.get(m, None)
        }

        print(
            f"{m:<32} | {mean_acc:6.2f} +/- {std_acc:5.2f}% | "
            f"[{ci_95[0]:5.2f}, {ci_95[1]:5.2f}] | {mean_f1:6.2f} +/- {std_f1:5.2f}% | "
            f"{p_str:<12} | {q_str:<10}"
        )
    print("=" * 115)

    out_json = Path("reports/phase6_external_dataset_shin2018_nback_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved grand benchmark summary to: {out_json}")


if __name__ == "__main__":
    run_shin2018_nback_benchmark()
