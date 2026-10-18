"""
Phase 6: Independent External Dataset Cross-Subject Validation.
Evaluates NVC-DelayFormer and comparison baselines on the completely independent
Buccino et al. 2016 multimodal dataset (15 healthy human subjects, 3,000 trials).

Protocol:
- 15-fold Leave-One-Subject-Out (LOSO) cross-validation.
- For held-out test subject s in {1..15}:
  - 2 validation subjects: (s-1) % 14 and s % 14 among the remaining 14 subjects.
  - 12 training subjects.
  - Seed: 42 + s.
- Models:
  1. NVC-DelayFormer (Full Model: Joint Readout + Gaussian Delay Prior + Kernel Weighting)
  2. Factorial [Off, Uniform] Ablation (Uniform 1/T weighting + unconstrained cross-attention)
  3. Direct-Only (Biophysical direct features with optical proxy gating)
  4. Latent-Only (Token-level cross-attention MLP readout)
  5. Authentic 2D-EEGNet (Lawhern et al. 2018; 21 channels)
  6. Handcrafted Multimodal Shrinkage-LDA (Ledoit-Wolf analytical shrinkage)
  7. Handcrafted Multimodal RBF-SVM (Validation-tuned C parameter)
"""

import sys
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
from torch.utils.data import TensorDataset, DataLoader

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


def extract_handcrafted_features(
    eeg: np.ndarray, fnirs: np.ndarray, fs_eeg: float = 100.0, fs_fnirs: float = 10.42
) -> np.ndarray:
    """
    Extract frequency and statistical features from EEG and fNIRS windows.
    - EEG (21 channels): Welch PSD in theta (4-8Hz), alpha (8-13Hz), beta (13-30Hz) -> 63 features.
    - fNIRS (68 channels): mean, peak amplitude, and linear slope -> 204 features.
    Total: 267 features per trial.
    """
    N, C_eeg, T_eeg = eeg.shape
    _, C_fnirs, T_fnirs = fnirs.shape
    features = []

    for i in range(N):
        trial_feats = []
        # 1. EEG Bandpower
        trial_eeg = eeg[i]  # (21, T)
        freqs, psd = signal.welch(trial_eeg, fs=fs_eeg, nperseg=min(256, T_eeg), axis=-1)
        theta_idx = np.logical_and(freqs >= 4.0, freqs < 8.0)
        alpha_idx = np.logical_and(freqs >= 8.0, freqs < 13.0)
        beta_idx = np.logical_and(freqs >= 13.0, freqs <= 30.0)

        trial_feats.extend(np.mean(psd[:, theta_idx], axis=-1))
        trial_feats.extend(np.mean(psd[:, alpha_idx], axis=-1))
        trial_feats.extend(np.mean(psd[:, beta_idx], axis=-1))

        # 2. fNIRS statistics (mean, peak, slope)
        trial_fnirs = fnirs[i]  # (68, T)
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


def load_all_buccino_data(data_dir: str = "data/processed_buccino") -> Dict[int, Dict[str, torch.Tensor]]:
    """Load preprocessed epochs for all 15 Buccino subjects."""
    root = Path(data_dir)
    subjects_data = {}
    for sub_id in range(1, 16):
        pt_file = root / f"sub-{sub_id:02d}" / "smr_epochs.pt"
        if not pt_file.exists():
            raise FileNotFoundError(f"Missing preprocessed data for sub-{sub_id:02d}: {pt_file}")
        data = torch.load(str(pt_file), weights_only=False)
        subjects_data[sub_id] = {
            "eeg": data["eeg"],
            "fnirs": data["fnirs"],
            "labels": data["labels"],
        }
    return subjects_data


def train_and_eval_nvc_variant(
    sub_id: int,
    subjects_data: Dict[int, Dict[str, torch.Tensor]],
    device: torch.device,
    variant_name: str = "Full Model",
    epochs: int = 12,
    batch_size: int = 128,
) -> Tuple[float, float, Dict[str, int]]:
    """Train and evaluate an NVC-DelayFormer variant on a single held-out fold."""
    set_seed(42 + sub_id)
    all_subs = list(range(1, 16))
    remaining = [s for s in all_subs if s != sub_id]  # 14 subjects

    # Cyclic 2-subject validation set
    val_idx_1 = (sub_id - 1) % 14
    val_idx_2 = sub_id % 14
    val_subs = [remaining[val_idx_1], remaining[val_idx_2]]
    train_subs = [s for s in remaining if s not in val_subs]

    # Assemble datasets
    train_eeg = torch.cat([subjects_data[s]["eeg"] for s in train_subs], dim=0)
    train_fnirs = torch.cat([subjects_data[s]["fnirs"] for s in train_subs], dim=0)
    train_y = torch.cat([subjects_data[s]["labels"] for s in train_subs], dim=0)

    val_eeg = torch.cat([subjects_data[s]["eeg"] for s in val_subs], dim=0)
    val_fnirs = torch.cat([subjects_data[s]["fnirs"] for s in val_subs], dim=0)
    val_y = torch.cat([subjects_data[s]["labels"] for s in val_subs], dim=0)

    test_eeg = subjects_data[sub_id]["eeg"]
    test_fnirs = subjects_data[sub_id]["fnirs"]
    test_y = subjects_data[sub_id]["labels"]

    train_loader = DataLoader(
        TensorDataset(train_eeg, train_fnirs, train_y),
        batch_size=batch_size,
        shuffle=True,
    )

    # Configure variant
    if variant_name == "Full Model":
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=21,
            fnirs_channels=68,
            hbo_channels=34,
            fnirs_sample_rate=10.42,
            readout_mode="joint",
            direct_weight_mode="kernel",
        ).to(device)
        use_prior = True
    elif variant_name == "Factorial [Off, Uniform]":
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=21,
            fnirs_channels=68,
            hbo_channels=34,
            fnirs_sample_rate=10.42,
            readout_mode="joint",
            direct_weight_mode="uniform",
        ).to(device)
        use_prior = False
    elif variant_name == "Direct-Only":
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=21,
            fnirs_channels=68,
            hbo_channels=34,
            fnirs_sample_rate=10.42,
            readout_mode="direct_only",
            cut_gate_latent=True,
        ).to(device)
        use_prior = True
    elif variant_name == "Latent-Only":
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=21,
            fnirs_channels=68,
            hbo_channels=34,
            fnirs_sample_rate=10.42,
            readout_mode="latent_only",
        ).to(device)
        use_prior = True
    else:
        raise ValueError(f"Unknown variant: {variant_name}")

    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
    warmup_epochs = 2
    cosine_epochs = epochs - warmup_epochs

    def lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return float(epoch + 1) / float(max(1, warmup_epochs))
        progress = float(epoch - warmup_epochs) / float(max(1, cosine_epochs))
        return 0.5 * (1.0 + np.cos(np.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_state = None

    val_eeg_dev = val_eeg.to(device)
    val_fnirs_dev = val_fnirs.to(device)
    val_y_dev = val_y.to(device)

    for epoch in range(1, epochs + 1):
        model.train()
        for batch_eeg, batch_fnirs, batch_y in train_loader:
            batch_eeg = batch_eeg.to(device)
            batch_fnirs = batch_fnirs.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            logits, _, recon_pred, (deep_logits, shallow_logits) = model(
                batch_eeg,
                batch_fnirs,
                use_delay_prior=use_prior,
                use_causal_mask=True,
                return_recon=True,
                return_branch_logits=True,
            )
            loss_joint = F.cross_entropy(logits, batch_y)
            loss_deep = F.cross_entropy(deep_logits, batch_y)
            loss_shallow = F.cross_entropy(shallow_logits, batch_y)
            loss = loss_joint + 0.2 * (loss_deep + loss_shallow)

            # Direct readout regularization
            if variant_name != "Latent-Only" and hasattr(model, "direct_readout") and hasattr(model.direct_readout, "weight"):
                w0 = model.direct_readout.weight[0]
                w1 = model.direct_readout.weight[1]
                loss = loss + 0.08 * torch.sum((w1 - w0) ** 2)

            # Auxiliary proxy reconstruction loss on target HbO channels (34 channels)
            target_hbo = model.compute_buxton_hemodynamics(batch_fnirs)[:, :model.hbo_channels, :]
            loss = loss + 1.0 * F.mse_loss(recon_pred, target_hbo)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        scheduler.step()

        # Validation evaluation
        model.eval()
        with torch.no_grad():
            v_logits, _ = model(val_eeg_dev, val_fnirs_dev, use_delay_prior=use_prior, use_causal_mask=True)
            v_loss = F.cross_entropy(v_logits, val_y_dev).item()
            v_preds = torch.argmax(v_logits, dim=-1).cpu().numpy()
            v_acc = accuracy_score(val_y.numpy(), v_preds)

            if (v_acc > best_val_acc) or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
                best_val_acc = v_acc
                best_val_loss = v_loss
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    # Held-out evaluation
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        t_logits, _ = model(test_eeg.to(device), test_fnirs.to(device), use_delay_prior=use_prior, use_causal_mask=True)
        t_preds = torch.argmax(t_logits, dim=-1).cpu().numpy()
        y_true = test_y.numpy()

    test_acc = accuracy_score(y_true, t_preds) * 100.0
    test_f1 = f1_score(y_true, t_preds, average="macro") * 100.0
    tn, fp, fn, tp = confusion_matrix(y_true, t_preds, labels=[0, 1]).ravel()
    cm_dict = {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)}

    return test_acc, test_f1, cm_dict, param_count


def train_and_eval_eegnet(
    sub_id: int,
    subjects_data: Dict[int, Dict[str, torch.Tensor]],
    device: torch.device,
    epochs: int = 12,
    batch_size: int = 128,
) -> Tuple[float, float, Dict[str, int]]:
    """Train and evaluate Authentic 2D-EEGNet on single held-out fold."""
    set_seed(42 + sub_id)
    all_subs = list(range(1, 16))
    remaining = [s for s in all_subs if s != sub_id]

    val_subs = [remaining[(sub_id - 1) % 14], remaining[sub_id % 14]]
    train_subs = [s for s in remaining if s not in val_subs]

    train_eeg = torch.cat([subjects_data[s]["eeg"] for s in train_subs], dim=0).unsqueeze(1)
    train_y = torch.cat([subjects_data[s]["labels"] for s in train_subs], dim=0)

    val_eeg = torch.cat([subjects_data[s]["eeg"] for s in val_subs], dim=0).unsqueeze(1)
    val_y = torch.cat([subjects_data[s]["labels"] for s in val_subs], dim=0)

    test_eeg = subjects_data[sub_id]["eeg"].unsqueeze(1)
    test_y = subjects_data[sub_id]["labels"]

    train_loader = DataLoader(TensorDataset(train_eeg, train_y), batch_size=batch_size, shuffle=True)
    model = AuthenticEEGNet2D(in_channels=21, time_points=600, num_classes=2).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = -1.0
    best_state = None
    val_eeg_dev = val_eeg.to(device)
    val_y_dev = val_y.to(device)

    for epoch in range(1, epochs + 1):
        model.train()
        for b_x, b_y in train_loader:
            b_x, b_y = b_x.to(device), b_y.to(device)
            optimizer.zero_grad()
            logits = model(b_x)
            loss = F.cross_entropy(logits, b_y)
            loss.backward()
            optimizer.step()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            v_logits = model(val_eeg_dev)
            v_preds = torch.argmax(v_logits, dim=-1).cpu().numpy()
            v_acc = accuracy_score(val_y.numpy(), v_preds)
            if v_acc > best_val_acc:
                best_val_acc = v_acc
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        t_logits = model(test_eeg.to(device))
        t_preds = torch.argmax(t_logits, dim=-1).cpu().numpy()
        y_true = test_y.numpy()

    test_acc = accuracy_score(y_true, t_preds) * 100.0
    test_f1 = f1_score(y_true, t_preds, average="macro") * 100.0
    tn, fp, fn, tp = confusion_matrix(y_true, t_preds, labels=[0, 1]).ravel()
    cm_dict = {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)}
    p_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return test_acc, test_f1, cm_dict, p_count


def eval_handcrafted_baselines(
    subjects_data: Dict[int, Dict[str, torch.Tensor]]
) -> Dict[str, Dict[str, Any]]:
    """Evaluate Multimodal Shrinkage-LDA and RBF-SVM across 15-fold LOSO."""
    print("[*] Extracting handcrafted multimodal features (PSD + Hemodynamic stats)...")
    sub_features = {}
    sub_labels = {}

    for sub_id in range(1, 16):
        eeg_np = subjects_data[sub_id]["eeg"].numpy()
        fnirs_np = subjects_data[sub_id]["fnirs"].numpy()
        feats = extract_handcrafted_features(eeg_np, fnirs_np)
        sub_features[sub_id] = feats
        sub_labels[sub_id] = subjects_data[sub_id]["labels"].numpy()

    lda_accs, lda_f1s = [], []
    svm_accs, svm_f1s = [], []

    for sub_id in range(1, 16):
        all_subs = list(range(1, 16))
        remaining = [s for s in all_subs if s != sub_id]
        val_subs = [remaining[(sub_id - 1) % 14], remaining[sub_id % 14]]
        train_subs = [s for s in remaining if s not in val_subs]

        x_train = np.concatenate([sub_features[s] for s in train_subs], axis=0)
        y_train = np.concatenate([sub_labels[s] for s in train_subs], axis=0)
        x_val = np.concatenate([sub_features[s] for s in val_subs], axis=0)
        y_val = np.concatenate([sub_labels[s] for s in val_subs], axis=0)
        x_test = sub_features[sub_id]
        y_test = sub_labels[sub_id]

        scaler = StandardScaler()
        x_train_sc = scaler.fit_transform(x_train)
        x_val_sc = scaler.transform(x_val)
        x_test_sc = scaler.transform(x_test)

        # 1. Shrinkage LDA
        lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        lda.fit(x_train_sc, y_train)
        lda_preds = lda.predict(x_test_sc)
        lda_accs.append(accuracy_score(y_test, lda_preds) * 100.0)
        lda_f1s.append(f1_score(y_test, lda_preds, average="macro") * 100.0)

        # 2. RBF-SVM with validation C tuning
        best_c = 1.0
        best_val_acc = -1.0
        for c in [0.01, 0.1, 1.0, 10.0]:
            svm = SVC(kernel="rbf", C=c)
            svm.fit(x_train_sc, y_train)
            v_acc = accuracy_score(y_val, svm.predict(x_val_sc))
            if v_acc > best_val_acc:
                best_val_acc = v_acc
                best_c = c

        best_svm = SVC(kernel="rbf", C=best_c)
        best_svm.fit(x_train_sc, y_train)
        svm_preds = best_svm.predict(x_test_sc)
        svm_accs.append(accuracy_score(y_test, svm_preds) * 100.0)
        svm_f1s.append(f1_score(y_test, svm_preds, average="macro") * 100.0)

    return {
        "Handcrafted Multimodal Shrinkage-LDA": {
            "per_subject_acc": lda_accs,
            "per_subject_f1": lda_f1s,
            "mean_acc": float(np.mean(lda_accs)),
            "std_acc": float(np.std(lda_accs, ddof=1)),
            "mean_f1": float(np.mean(lda_f1s)),
            "std_f1": float(np.std(lda_f1s, ddof=1)),
            "params": None,
        },
        "Handcrafted Multimodal RBF-SVM": {
            "per_subject_acc": svm_accs,
            "per_subject_f1": svm_f1s,
            "mean_acc": float(np.mean(svm_accs)),
            "std_acc": float(np.std(svm_accs, ddof=1)),
            "mean_f1": float(np.mean(svm_f1s)),
            "std_f1": float(np.std(svm_f1s, ddof=1)),
            "params": None,
        },
    }


def run_phase6_full_benchmark() -> None:
    """Run full 15-fold LOSO cross-validation benchmark on Buccino et al. 2016."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 80)
    print("PHASE 6: INDEPENDENT EXTERNAL DATASET EVALUATION (BUCCINO ET AL. 2016)")
    print(f"Device: {device} | 15 Subjects | 3,000 Trials (Movement vs. Rest)")
    print("=" * 80)

    subjects_data = load_all_buccino_data()
    models_to_evaluate = [
        "Full Model",
        "Factorial [Off, Uniform]",
        "Direct-Only",
        "Latent-Only",
    ]

    results: Dict[str, Any] = {
        "metadata": {
            "dataset": "Buccino et al. 2016 (PLOS ONE, DOI: 10.1371/journal.pone.0146610)",
            "task": "SMR BCI: Movement Execution vs. Baseline Rest (100 movement vs 100 rest)",
            "num_subjects": 15,
            "total_trials": 3000,
            "window_duration_sec": 6.0,
            "evaluation_scheme": "15-fold LOSO (Train 12 / Val 2 / Test 1)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "models": {},
    }

    # Evaluate deep models
    for model_name in models_to_evaluate:
        print(f"\n[*] Evaluating: {model_name}...")
        accs = []
        f1s = []
        cms = []
        model_p_count = None
        t0 = time.time()

        for sub_id in range(1, 16):
            acc, f1, cm, p_count = train_and_eval_nvc_variant(
                sub_id=sub_id,
                subjects_data=subjects_data,
                device=device,
                variant_name=model_name,
            )
            accs.append(acc)
            f1s.append(f1)
            cms.append(cm)
            model_p_count = p_count
            print(f"  Sub-{sub_id:02d}: Acc = {acc:.2f}%, F1 = {f1:.2f}%")

        elapsed = time.time() - t0
        mean_acc = float(np.mean(accs))
        std_acc = float(np.std(accs, ddof=1))
        se_acc = std_acc / np.sqrt(15)
        t_crit = student_t.ppf(0.975, df=14)
        ci_95 = [float(mean_acc - t_crit * se_acc), float(mean_acc + t_crit * se_acc)]

        results["models"][model_name] = {
            "per_subject_acc": [float(a) for a in accs],
            "per_subject_f1": [float(f) for f in f1s],
            "mean_acc": mean_acc,
            "std_acc": std_acc,
            "ci_95": ci_95,
            "mean_f1": float(np.mean(f1s)),
            "std_f1": float(np.std(f1s, ddof=1)),
            "params": model_p_count,
            "elapsed_sec": elapsed,
        }
        print(f"[+] {model_name} Grand Mean: {mean_acc:.2f}% +/- {std_acc:.2f}% | 95% CI: [{ci_95[0]:.2f}, {ci_95[1]:.2f}]% ({elapsed:.1f}s, {model_p_count} params)")

    # Evaluate EEGNet
    print("\n[*] Evaluating: Authentic 2D-EEGNet...")
    eegnet_accs, eegnet_f1s = [], []
    eegnet_p_count = None
    t0 = time.time()
    for sub_id in range(1, 16):
        acc, f1, _, p_count = train_and_eval_eegnet(sub_id, subjects_data, device)
        eegnet_accs.append(acc)
        eegnet_f1s.append(f1)
        eegnet_p_count = p_count
        print(f"  Sub-{sub_id:02d}: Acc = {acc:.2f}%, F1 = {f1:.2f}%")
    elapsed = time.time() - t0
    m_acc = float(np.mean(eegnet_accs))
    s_acc = float(np.std(eegnet_accs, ddof=1))
    results["models"]["Authentic EEGNet-2D"] = {
        "per_subject_acc": [float(a) for a in eegnet_accs],
        "per_subject_f1": [float(f) for f in eegnet_f1s],
        "mean_acc": m_acc,
        "std_acc": s_acc,
        "mean_f1": float(np.mean(eegnet_f1s)),
        "std_f1": float(np.std(eegnet_f1s, ddof=1)),
        "params": eegnet_p_count,
        "elapsed_sec": elapsed,
    }
    print(f"[+] Authentic EEGNet-2D Grand Mean: {m_acc:.2f}% +/- {s_acc:.2f}% ({elapsed:.1f}s, {eegnet_p_count} params)")

    # Evaluate Handcrafted Baselines
    print("\n[*] Evaluating Handcrafted Feature Baselines...")
    hc_results = eval_handcrafted_baselines(subjects_data)
    results["models"].update(hc_results)

    # Statistical significance comparisons vs. Full Model
    full_accs = np.array(results["models"]["Full Model"]["per_subject_acc"])
    print("\n" + "=" * 80)
    print("STATISTICAL COMPARISONS ON BUCCINO ET AL. 2016 (PAIRED WILCOXON vs. FULL MODEL)")
    print("=" * 80)

    comparison_names = [m for m in results["models"].keys() if m != "Full Model"]
    p_values = []
    diffs = []

    for name in comparison_names:
        m_accs = np.array(results["models"][name]["per_subject_acc"])
        diff = float(np.mean(full_accs - m_accs))
        diffs.append(diff)
        try:
            stat, p_val = wilcoxon(full_accs, m_accs)
        except Exception:
            p_val = 1.0
        p_values.append(float(p_val))
        results["models"][name]["diff_vs_full_pp"] = diff
        results["models"][name]["wilcoxon_p"] = float(p_val)

    # Benjamini-Hochberg FDR correction
    p_arr = np.array(p_values)
    order = np.argsort(p_arr)
    n_tests = len(p_arr)
    q_values = np.zeros(n_tests)
    cum_min = 1.0
    for rank in range(n_tests, 0, -1):
        idx = order[rank - 1]
        q_val = p_arr[idx] * n_tests / rank
        cum_min = min(cum_min, q_val)
        q_values[idx] = min(1.0, cum_min)

    for i, name in enumerate(comparison_names):
        results["models"][name]["bh_q"] = float(q_values[i])
        m = results["models"][name]
        print(
            f"{name:<35}: {m['mean_acc']:.2f}% +/- {m['std_acc']:.2f}% | "
            f"Diff: {m['diff_vs_full_pp']:+6.2f} pp | p = {m['wilcoxon_p']:.4f} | q = {m['bh_q']:.4f}"
        )

    # Pairwise comparison between Direct-Only and Latent-Only
    if "Direct-Only" in results["models"] and "Latent-Only" in results["models"]:
        dir_accs = np.array(results["models"]["Direct-Only"]["per_subject_acc"])
        lat_accs = np.array(results["models"]["Latent-Only"]["per_subject_acc"])
        dir_lat_diff = float(np.mean(dir_accs - lat_accs))
        try:
            _, dir_lat_p = wilcoxon(dir_accs, lat_accs)
        except Exception:
            dir_lat_p = 1.0
        results["readout_comparison_direct_vs_latent"] = {
            "mean_diff_pp": dir_lat_diff,
            "wilcoxon_p": float(dir_lat_p),
        }
        print("\n" + "=" * 80)
        print(f"DIRECT-ONLY VS. LATENT-ONLY: Diff = {dir_lat_diff:+6.2f} pp | Wilcoxon p = {dir_lat_p:.4f}")
        print("=" * 80)

    # Output JSON summary
    out_json = Path("reports/phase6_external_dataset_buccino_results.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[+] Phase 6 complete! Locked results saved to: {out_json.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    run_phase6_full_benchmark()
