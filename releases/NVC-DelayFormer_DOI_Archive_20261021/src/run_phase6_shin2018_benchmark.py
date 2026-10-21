"""
Phase 6: Independent External Dataset Cross-Subject Validation on Shin et al. (2018) Cognitive Benchmark.
Evaluates NVC-DelayFormer and baseline architectures on the independent 26-subject
TU Berlin Cognitive Word Generation dataset (Shin et al., Scientific Data 2018, 5:180003; 26 healthy subjects, 1,560 trials).

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
  4. Direct-Only (Shallow biophysical direct features with optical proxy gating)
  5. Uniform ([Off, Uniform]: Uniform 1/T weighting + unconstrained cross-attention)
  6. Authentic EEGNet-2D (Lawhern et al. 2018, 30 channels)
  7. Latent-Only (Deep token-level cross-attention MLP readout)
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
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

import torch
import torch.nn as nn
import torch.nn.functional as F

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from temporal_fusion import NVCDelayFormer
from src.models.baselines import AuthenticEEGNet2D


def set_seed(seed: int) -> None:
    """Ensure strict deterministic execution for reproducibility."""
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def euclidean_alignment(X: np.ndarray) -> np.ndarray:
    """
    Euclidean Alignment (He & Wu, IEEE TBME 2020) for transfer learning across subjects.
    X: (N, C, T)
    """
    N, C, T = X.shape
    covs = np.zeros((N, C, C))
    for i in range(N):
        covs[i] = np.cov(X[i]) + 1e-5 * np.eye(C)
    R_bar = np.mean(covs, axis=0)
    
    # R_bar^(-1/2) via SVD
    u, s, vh = np.linalg.svd(R_bar)
    R_inv_sqrt = u @ np.diag(1.0 / np.sqrt(s + 1e-5)) @ vh
    
    X_aligned = np.zeros_like(X)
    for i in range(N):
        X_aligned[i] = R_inv_sqrt @ X[i]
    return X_aligned


def extract_handcrafted_features(
    eeg: np.ndarray, fnirs: np.ndarray, fs_eeg: float = 100.0, fs_fnirs: float = 10.33
) -> np.ndarray:
    """
    Extract frequency and statistical features from EEG and fNIRS windows.
    - EEG (30 channels): Welch PSD in theta (4-8Hz), alpha (8-13Hz), beta (13-30Hz) -> 90 features.
    - fNIRS (72 channels): mean, peak amplitude, and linear slope -> 216 features.
    Total: 306 features per trial.
    """
    N, C_eeg, T_eeg = eeg.shape
    _, C_fnirs, T_fnirs = fnirs.shape
    features = []

    for i in range(N):
        trial_feats = []
        # 1. EEG Bandpower
        trial_eeg = eeg[i]  # (30, T)
        freqs, psd = signal.welch(trial_eeg, fs=fs_eeg, nperseg=min(256, T_eeg), axis=-1)
        theta_idx = np.logical_and(freqs >= 4.0, freqs < 8.0)
        alpha_idx = np.logical_and(freqs >= 8.0, freqs < 13.0)
        beta_idx = np.logical_and(freqs >= 13.0, freqs <= 30.0)

        trial_feats.extend(np.mean(psd[:, theta_idx], axis=-1))
        trial_feats.extend(np.mean(psd[:, alpha_idx], axis=-1))
        trial_feats.extend(np.mean(psd[:, beta_idx], axis=-1))

        # 2. fNIRS statistics (mean, peak, slope)
        trial_fnirs = fnirs[i]  # (72, T)
        trial_feats.extend(np.mean(trial_fnirs, axis=-1))
        trial_feats.extend(np.max(trial_fnirs, axis=-1))

        time_vec = np.arange(T_fnirs) / fs_fnirs
        time_centered = time_vec - np.mean(time_vec)
        denom = np.sum(time_centered ** 2) + 1e-8
        centered_fnirs = trial_fnirs - np.mean(trial_fnirs, axis=-1, keepdims=True)
        slopes = np.sum(centered_fnirs * time_centered, axis=-1) / denom
        trial_feats.extend(slopes)

        features.append(trial_feats)

    return np.array(features, dtype=np.float32)


def get_warmup_cosine_scheduler(optimizer, warmup_epochs: int, total_epochs: int):
    def lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return float(epoch + 1) / float(max(1, warmup_epochs))
        progress = float(epoch - warmup_epochs) / float(max(1, total_epochs - warmup_epochs))
        return 0.5 * (1.0 + np.cos(np.pi * progress))
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def train_nvc_variant(
    model: nn.Module,
    use_prior: bool,
    readout_mode: str,
    tr_e: torch.Tensor, tr_f: torch.Tensor, tr_y: torch.Tensor,
    va_e: torch.Tensor, va_f: torch.Tensor, va_y: torch.Tensor,
    te_e: torch.Tensor, te_f: torch.Tensor, te_y: torch.Tensor,
    device: torch.device,
    epochs: int = 15,
    batch_size: int = 128,
    lr: float = 3e-3,
    weight_decay: float = 0.05
) -> Tuple[float, float]:
    """Train NVCDelayFormer variant and evaluate on test set."""
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
                use_causal_mask=True,
                return_recon=True,
                return_branch_logits=True,
            )
            loss_joint = F.cross_entropy(logits, by)
            loss_deep = F.cross_entropy(deep_logits, by)
            loss_shallow = F.cross_entropy(shallow_logits, by)
            loss = loss_joint + 0.2 * (loss_deep + loss_shallow)
            
            # Direct readout regularization
            if readout_mode != "latent_only" and hasattr(model, "direct_readout") and hasattr(model.direct_readout, "weight"):
                w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                loss = loss + 0.08 * (w_diff ** 2).sum()

            # Reconstruction loss on target HbO (first 36 channels)
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
            v_logits, _ = model(va_e, va_f, use_delay_prior=use_prior, use_causal_mask=True)
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
        t_logits, _ = model(te_e, te_f, use_delay_prior=use_prior, use_causal_mask=True)
        t_preds = torch.argmax(t_logits, dim=-1).cpu().numpy()
        y_true = te_y.cpu().numpy()

    acc = float(accuracy_score(y_true, t_preds)) * 100.0
    f1 = float(f1_score(y_true, t_preds, average="macro")) * 100.0
    return acc, f1


def train_eegnet(
    model: nn.Module,
    tr_e: torch.Tensor, tr_y: torch.Tensor,
    va_e: torch.Tensor, va_y: torch.Tensor,
    te_e: torch.Tensor, te_y: torch.Tensor,
    device: torch.device,
    epochs: int = 15,
    batch_size: int = 128,
    lr: float = 2e-3,
    weight_decay: float = 0.01
) -> Tuple[float, float]:
    """Train Authentic EEGNet-2D and evaluate on test set."""
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = get_warmup_cosine_scheduler(optimizer, warmup_epochs=2, total_epochs=epochs)
    
    n_tr = tr_e.size(0)
    best_val_acc = -1.0
    best_state = None

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n_tr, device=device)
        for idx in range(0, n_tr, batch_size):
            b = perm[idx:idx + batch_size]
            bx_e, by = tr_e[b], tr_y[b]
            
            optimizer.zero_grad()
            logits = model(bx_e)
            loss = F.cross_entropy(logits, by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
        scheduler.step()

        # Validation check
        model.eval()
        with torch.no_grad():
            v_logits = model(va_e)
            v_preds = torch.argmax(v_logits, dim=-1)
            v_acc = float((v_preds == va_y).float().mean().item()) * 100.0

        if v_acc > best_val_acc:
            best_val_acc = v_acc
            best_state = copy.deepcopy(model.state_dict())

    # Evaluate test set
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        t_logits = model(te_e)
        t_preds = torch.argmax(t_logits, dim=-1).cpu().numpy()
        y_true = te_y.cpu().numpy()

    acc = float(accuracy_score(y_true, t_preds)) * 100.0
    f1 = float(f1_score(y_true, t_preds, average="macro")) * 100.0
    return acc, f1


def run_shin2018_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data_dir = Path("data/processed_shin2018")
    
    all_subs = sorted([int(p.name.split("-")[1]) for p in data_dir.glob("sub-*") if (p / "wg_epochs.pt").exists()])
    n_subjects = len(all_subs)
    assert n_subjects == 26, f"Expected 26 subjects, found {n_subjects}"

    print("=" * 86)
    print(f"26-FOLD LOSO BENCHMARK ON SHIN ET AL. (2018) COGNITIVE DATASET ({n_subjects} SUBJECTS)")
    print(f"Device: {device} | 1,560 total trials (60 per subject, 30 WG / 30 Rest)")
    print("=" * 86)

    # 1. Load, align and cache all subjects
    print("\n[Step 1/2] Pre-processing, Euclidean Alignment, and Caching all 26 subjects...")
    t0 = time.time()
    cache_eeg = {}
    cache_fnirs = {}
    cache_labels = {}
    cache_feats = {}

    for sid in all_subs:
        pt_path = data_dir / f"sub-{sid:02d}" / "wg_epochs.pt"
        loaded = torch.load(pt_path, map_location="cpu", weights_only=False)
        eeg_raw = loaded["eeg"].numpy()      # (60, 30, 1000)
        fnirs_raw = loaded["fnirs"].numpy()  # (60, 72, 124)
        labels = loaded["labels"].numpy()    # (60,)

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
        "Direct-Only (Shallow)",
        "Uniform ([Off, Uniform])",
        "Authentic EEGNet-2D",
        "Latent-Only (Deep)"
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

        # D. Direct-Only (Shallow)
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

        # E. Uniform ([Off, Uniform])
        set_seed(42 + test_sub)
        uni_model = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, hbo_channels=36,
            feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0,
            learnable_delay=False, readout_mode="joint", direct_weight_mode="uniform", cut_gate_latent=False
        ).to(device)
        acc_uni, f1_uni = train_nvc_variant(
            uni_model, use_prior=False, readout_mode="joint",
            tr_e=tr_e, tr_f=tr_f, tr_y=tr_y,
            va_e=va_e, va_f=va_f, va_y=va_y,
            te_e=te_e, te_f=te_f, te_y=te_y,
            device=device, epochs=15, batch_size=128
        )
        fold_accuracies["Uniform ([Off, Uniform])"].append(acc_uni)
        fold_f1s["Uniform ([Off, Uniform])"].append(f1_uni)

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

        # G. Latent-Only (Deep)
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

        f_time = time.time() - f_start
        print(f"Fold {fold_idx+1:02d}/26 (Sub-{test_sub:02d}) [{f_time:.1f}s] | NVC: {acc_full:.2f}% | LDA: {fold_accuracies['Handcrafted Shrinkage-LDA'][-1]:.2f}% | SVM: {fold_accuracies['Handcrafted Multimodal SVM'][-1]:.2f}% | EEGNet: {acc_eegnet:.2f}% | Lat: {acc_lat:.2f}%")

    total_time = time.time() - total_start
    print("=" * 86)
    print(f"LOSO EVALUATION COMPLETED IN {total_time/60:.2f} MINUTES")
    print("=" * 86)

    # 3. Statistical Analysis & Report
    report = {
        "dataset": "Shin et al. (2018) Cognitive Word Generation",
        "citation": "Shin et al., Sci Data 5, 180003 (2018)",
        "num_subjects": n_subjects,
        "total_trials": n_subjects * 60,
        "models": {}
    }

    full_accs = np.array(fold_accuracies["NVC-DelayFormer (Full Model)"])
    raw_p_values = {}

    for m in model_names:
        accs = np.array(fold_accuracies[m])
        f1s = np.array(fold_f1s[m])

        mean_acc = float(np.mean(accs))
        std_acc = float(np.std(accs, ddof=1))
        mean_f1 = float(np.mean(f1s))
        std_f1 = float(np.std(f1s, ddof=1))

        se = std_acc / np.sqrt(n_subjects)
        t_crit = float(student_t.ppf(0.975, df=n_subjects - 1))
        ci_lower = float(mean_acc - t_crit * se)
        ci_upper = float(mean_acc + t_crit * se)

        if m == "NVC-DelayFormer (Full Model)":
            p_val = 1.0
        else:
            diff = full_accs - accs
            if np.all(diff == 0):
                p_val = 1.0
            else:
                stat, p_val = wilcoxon(full_accs, accs, alternative="two-sided")
                p_val = float(p_val)
        raw_p_values[m] = p_val

        report["models"][m] = {
            "mean_acc": round(mean_acc, 2),
            "std_acc": round(std_acc, 2),
            "mean_f1": round(mean_f1, 2),
            "std_f1": round(std_f1, 2),
            "ci_95": [round(ci_lower, 2), round(ci_upper, 2)],
            "wilcoxon_p": p_val,
            "fold_accuracies": [round(float(x), 2) for x in accs],
            "fold_f1s": [round(float(x), 2) for x in f1s]
        }

    # Benjamini-Hochberg FDR correction across non-reference models
    non_ref_models = [m for m in model_names if m != "NVC-DelayFormer (Full Model)"]
    raw_ps = [raw_p_values[m] for m in non_ref_models]
    sorted_indices = np.argsort(raw_ps)
    q_values = np.zeros(len(raw_ps))
    m_tests = len(raw_ps)
    for rank, idx in enumerate(sorted_indices, 1):
        q_values[idx] = min(raw_ps[idx] * m_tests / rank, 1.0)
    for i in range(len(sorted_indices) - 2, -1, -1):
        q_values[sorted_indices[i]] = min(q_values[sorted_indices[i]], q_values[sorted_indices[i+1]])

    for idx, m in enumerate(non_ref_models):
        report["models"][m]["fdr_q"] = float(q_values[idx])
    report["models"]["NVC-DelayFormer (Full Model)"]["fdr_q"] = 1.0

    print("\n" + "=" * 100)
    print("FINAL SUMMARY: SHIN ET AL. (2018) 26-SUBJECT COGNITIVE WORD GENERATION BENCHMARK")
    print(f"{'Model / Variant':<30} | {'Accuracy (%)':<18} | {'95% CI (%)':<18} | {'Macro F1 (%)':<14} | {'p-val':<8} | {'q-val':<8}")
    print("-" * 100)
    for m in model_names:
        stats = report["models"][m]
        p_str = "--" if m == "NVC-DelayFormer (Full Model)" else f"{stats['wilcoxon_p']:.4f}"
        q_str = "--" if m == "NVC-DelayFormer (Full Model)" else f"{stats['fdr_q']:.4f}"
        print(f"{m:<30} | {stats['mean_acc']:.2f} +/- {stats['std_acc']:.2f}% | [{stats['ci_95'][0]:.2f}, {stats['ci_95'][1]:.2f}] | {stats['mean_f1']:.2f} +/- {stats['std_f1']:.2f}% | {p_str:<8} | {q_str:<8}")
    print("=" * 100)

    out_json = Path("reports/phase6_external_dataset_shin2018_results.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Saved full benchmark report to {out_json}")
    return report


if __name__ == "__main__":
    run_shin2018_benchmark()
