"""
Phase 2 End-to-End Trainer & Physiological Mechanism Verifier.
Implements:
1. Multi-task loss: Cross-Entropy + Physiological Latent HRF Reconstruction (L_total = L_CE + λ * L_recon).
2. AdamW optimizer + Linear Warmup with Cosine Annealing.
3. Strict Leave-One-Subject-Out (LOSO) Cross-Validation.
4. Automatic model checkpointing and generation of publication-ready scientific figures.
"""

import os
import time
import argparse
import warnings
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.utils.seed import set_seed
from src.data.dataset import get_loso_dataloaders
from src.models.nvc_net import NVCDelayFormer
from src.utils.metrics import compute_bci_metrics, compute_confusion_matrix


def get_warmup_cosine_scheduler(
    optimizer,
    warmup_epochs: int,
    total_epochs: int,
    min_lr: float = 1e-5
):
    """Linear warmup for warmup_epochs, followed by cosine annealing to min_lr."""
    def lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return float(epoch + 1) / float(max(1, warmup_epochs))
        else:
            progress = float(epoch - warmup_epochs) / float(max(1, total_epochs - warmup_epochs))
            cosine_decay = 0.5 * (1.0 + np.cos(np.pi * progress))
            return cosine_decay * (1.0 - min_lr / 1e-3) + min_lr / 1e-3

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def train_one_epoch(
    model: nn.Module,
    train_loader,
    optimizer,
    criterion_ce,
    criterion_recon,
    lambda_recon: float,
    device: torch.device
) -> Tuple[float, float]:
    """Train for a single epoch."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    
    for eeg, fnirs, labels in train_loader:
        eeg = eeg.to(device)
        fnirs = fnirs.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        
        logits, _, recon_pred, (deep_logits, shallow_logits) = model(
            eeg, fnirs, use_delay_prior=True, return_recon=True, return_branch_logits=True
        )
        loss_cls, loss_joint, loss_deep, loss_shallow = NVCDelayFormer.compute_auxiliary_loss(
            logits, deep_logits, shallow_logits, labels, aux_weight=0.2, criterion=criterion_ce
        )
        
        # Physiological reconstruction target: HbO channels (first hbo_channels of fnirs)
        # Standardize across time per trial to balance loss scale with cross-entropy
        hbo_c = getattr(model, "hbo_channels", 36)
        target_hbo = fnirs[:, :hbo_c, :]
        target_hbo_mean = target_hbo.mean(dim=-1, keepdim=True)
        target_hbo_std = target_hbo.std(dim=-1, keepdim=True) + 1e-6
        target_hbo_norm = (target_hbo - target_hbo_mean) / target_hbo_std
        loss_recon = criterion_recon(recon_pred, target_hbo_norm)
        
        loss = loss_cls + lambda_recon * loss_recon
        loss.backward()
        
        # Gradient clipping to enforce numerical stability
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        
        total_loss += loss.item() * labels.size(0)
        preds = torch.argmax(logits, dim=-1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
        
    epoch_loss = total_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


def evaluate(
    model: nn.Module,
    test_loader,
    criterion_ce,
    criterion_recon,
    lambda_recon: float,
    device: torch.device
) -> Tuple[float, Dict[str, float], np.ndarray, torch.Tensor]:
    """Evaluate on the held-out subject test set."""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    collected_attns = []
    
    with torch.no_grad():
        for eeg, fnirs, labels in test_loader:
            eeg = eeg.to(device)
            fnirs = fnirs.to(device)
            labels = labels.to(device)
            
            logits, attn_weights, recon_pred = model(eeg, fnirs, use_delay_prior=True, return_recon=True)
            loss_ce = criterion_ce(logits, labels)
            
            hbo_c = getattr(model, "hbo_channels", 36)
            target_hbo = fnirs[:, :hbo_c, :]
            target_hbo_mean = target_hbo.mean(dim=-1, keepdim=True)
            target_hbo_std = target_hbo.std(dim=-1, keepdim=True) + 1e-6
            target_hbo_norm = (target_hbo - target_hbo_mean) / target_hbo_std
            loss_recon = criterion_recon(recon_pred, target_hbo_norm)
            loss = loss_ce + lambda_recon * loss_recon
            
            total_loss += loss.item() * labels.size(0)
            preds = torch.argmax(logits, dim=-1)
            
            all_preds.append(preds.cpu())
            all_labels.append(labels.cpu())
            collected_attns.append(attn_weights.cpu())
            
    total_samples = sum(len(l) for l in all_labels)
    eval_loss = total_loss / total_samples
    
    y_pred = torch.cat(all_preds, dim=0)
    y_true = torch.cat(all_labels, dim=0)
    
    metrics = compute_bci_metrics(y_true, y_pred)
    cm = compute_confusion_matrix(y_true, y_pred)
    
    mean_attn = torch.cat(collected_attns, dim=0).mean(dim=0, keepdim=True)
    return eval_loss, metrics, cm, mean_attn


def run_training_experiment(
    config_path: str = "config/default_config.yaml",
    test_subject_id: int = 5,
    all_subject_ids: List[int] = [1, 2, 3, 4, 5]
):
    """
    [DEPRECATED] Legacy 5-subject debugging harness.

    WARNING: This legacy function is deprecated due to historical unnested checkpoint selection.
    For all benchmark evaluations and canonical LOSO training (Train 23 / Val 5 / Test 1 with strict
    subject isolation), use `train_single_loso_fold()` instead.
    """
    warnings.warn(
        "run_training_experiment() is deprecated and retained only for legacy compatibility. "
        "Use train_single_loso_fold() for canonical, leak-free 29-fold LOSO evaluation.",
        DeprecationWarning,
        stacklevel=2
    )
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
        
    # 1. Deterministic Setup
    seed = cfg["experiment"]["seed"]
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() and cfg["experiment"]["device"] == "cuda" else "cpu")
    print(f"[*] Starting Phase 2 Training | Device: {device} | Seed: {seed}")
    print(f"[*] LOSO Setup: Train on subjects {[s for s in all_subject_ids if s != test_subject_id]} -> Test on Sub-{test_subject_id:02d}")
    
    # 2. DataLoaders
    processed_dir = Path(cfg["paths"]["processed_data_dir"])
    train_loader, test_loader = get_loso_dataloaders(
        processed_dir=processed_dir,
        test_subject_id=test_subject_id,
        all_subject_ids=all_subject_ids,
        batch_size=cfg["training"]["batch_size"],
    )
    print(f"[*] Data loaded: Train trials={len(train_loader.dataset)}, Test trials={len(test_loader.dataset)}")
    
    # 3. Model Instantiation
    model = NVCDelayFormer(
        num_classes=2,
        eeg_channels=cfg["dataset"]["eeg_channels"],
        fnirs_channels=cfg["dataset"]["fnirs_channels"],
        feature_dim=cfg["model"]["eeg_feature_dim"],
        num_heads=cfg["model"]["num_heads"],
        nvc_delay_mean_sec=cfg["model"]["nvc_delay_mean_seconds"],
        nvc_delay_std_sec=cfg["model"]["nvc_delay_std_seconds"],
        eeg_sample_rate_effective=cfg["dataset"]["eeg_sample_rate_target"] / 4.0,  # 25.0 Hz
        fnirs_sample_rate=cfg["dataset"]["fnirs_sample_rate"],
        dropout=cfg["model"]["dropout"]
    ).to(device)
    
    # 4. Optimization Setup
    optimizer = AdamW(
        model.parameters(),
        lr=cfg["training"]["learning_rate"],
        weight_decay=cfg["training"]["weight_decay"]
    )
    epochs = cfg["training"]["epochs"]
    warmup_epochs = 5
    scheduler = get_warmup_cosine_scheduler(optimizer, warmup_epochs=warmup_epochs, total_epochs=epochs)
    
    criterion_ce = nn.CrossEntropyLoss()
    criterion_recon = nn.MSELoss()
    lambda_recon = cfg["training"]["loss_recon_lambda"]
    
    # 5. Training Loop
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val_acc = 0.0
    best_val_loss = float("inf")
    best_cm = None
    best_attn = None
    best_metrics = {}
    
    checkpoints_dir = Path(cfg["paths"]["checkpoints_dir"])
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = checkpoints_dir / f"best_nvc_delayformer_sub{test_subject_id:02d}.pt"
    
    print("-" * 84)
    print(f"{'Epoch':^7} | {'Train Loss':^11} | {'Train Acc':^10} | {'Val Loss':^10} | {'Val Acc':^9} | {'Kappa':^8} | {'Tau (NVC)':^9}")
    print("-" * 84)
    
    for epoch in range(1, epochs + 1):
        tr_loss, tr_acc = train_one_epoch(
            model, train_loader, optimizer, criterion_ce, criterion_recon, lambda_recon, device
        )
        val_loss, metrics, cm, mean_attn = evaluate(
            model, test_loader, criterion_ce, criterion_recon, lambda_recon, device
        )
        scheduler.step()
        
        history["train_loss"].append(tr_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(tr_acc)
        history["val_acc"].append(metrics["accuracy"])
        
        # Composite criteria: higher accuracy, or equal accuracy with lower validation loss
        is_better = (metrics["accuracy"] > best_val_acc) or (
            metrics["accuracy"] == best_val_acc and val_loss < best_val_loss
        )
        if is_better:
            best_val_acc = metrics["accuracy"]
            best_val_loss = val_loss
            best_cm = cm
            best_attn = mean_attn
            best_metrics = metrics
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "val_acc": best_val_acc,
                "val_loss": best_val_loss,
                "metrics": best_metrics
            }, best_ckpt_path)
            
        learned_tau = float(model.cross_attention.delay_mean.mean().item())
        if epoch % 5 == 0 or epoch == 1 or epoch == epochs:
            print(f"{epoch:^7d} | {tr_loss:^11.4f} | {tr_acc*100:^9.2f}% | {val_loss:^10.4f} | {metrics['accuracy']*100:^8.2f}% | {metrics['cohen_kappa']:^8.4f} | {learned_tau:^8.2f}s")
            
    print("-" * 84)
    print(f"[+] Best LOSO Accuracy on Sub-{test_subject_id:02d}: {best_val_acc*100:.2f}% (Val Loss: {best_val_loss:.4f}) | Cohen's Kappa: {best_metrics.get('cohen_kappa', 0.0):.4f} | Macro F1: {best_metrics.get('macro_f1', 0.0):.4f}")
    final_tau = float(model.cross_attention.delay_mean.mean().item())
    print(f"[+] Final Learned Physiological Delay Tau: {final_tau:.2f}s")
    print(f"[+] Best model checkpoint saved to: {best_ckpt_path}")
    
    # 6. Generate Academic Figures
    figures_dir = Path("reports/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    from src.utils.visualization import (
        plot_training_curves,
        plot_delay_attention_heatmap,
        plot_confusion_matrix_figure,
    )
    
    # Plot 1: Convergence
    plot_training_curves(history, figures_dir / f"training_curves_sub{test_subject_id:02d}.png")
    
    # Plot 2: Delay Attention Heatmap
    if best_attn is not None:
        plot_delay_attention_heatmap(
            best_attn,
            figures_dir / f"delay_attention_heatmap_sub{test_subject_id:02d}.png",
            eeg_sr=cfg["dataset"]["eeg_sample_rate_target"] / 4.0,
            fnirs_sr=cfg["dataset"]["fnirs_sample_rate"],
            tau_nvc_sec=cfg["model"]["nvc_delay_mean_seconds"]
        )
        
    # Plot 3: Confusion Matrix
    if best_cm is not None:
        plot_confusion_matrix_figure(
            best_cm,
            ["Mental_Arithmetic", "Rest"],
            figures_dir / f"confusion_matrix_sub{test_subject_id:02d}.png"
        )
        
    print(f"[+] All scientific verification figures successfully exported to: {figures_dir}")
    return best_metrics


def train_single_loso_fold(
    test_sub: int,
    seed_base: int = 42,
    epochs: int = 25,
    batch_size: int = 64,
    lr: float = 1.5e-3,
    weight_decay: float = 0.01,
    all_subs: List[int] = None,
    device: torch.device = None,
    proc_dir: Path = Path("data/processed"),
    cache: dict = None,
    use_delay_prior: bool = True,
    use_causal_mask: bool = True,
    use_ea: bool = True,
    readout_mode: str = "joint",
    direct_weight_mode: str = "kernel",
    verbose: bool = True,
    save_checkpoint: bool = False,
    ckpt_output_path: Optional[str] = None,
) -> dict:
    """
    Standardized, authentic single-fold LOSO trainer adhering strictly to the
    paper's 29-fold evaluation protocol (Train 23 / Val 5 / Test 1, with EA and 1e4 fNIRS scaling).
    """
    if all_subs is None:
        all_subs = list(range(1, 30))
    if device is None:
        has_gpu = torch.cuda.is_available() and torch.cuda.device_count() > 0
        device = torch.device("cuda" if has_gpu else "cpu")

    # 1. Deterministic seed & subject partition
    set_seed(seed_base + test_sub)
    pool = [s for s in all_subs if s != test_sub]
    start_idx = (test_sub - 1) % len(pool)
    val_ids = [pool[(start_idx + i) % len(pool)] for i in range(5)]
    train_ids = [s for s in pool if s not in val_ids]

    if verbose:
        print(f"LOSO Partition for Subject {test_sub:02d}:")
        print(f"  - Train: {len(train_ids)} subjects ({train_ids[:4]}...)")
        print(f"  - Val:   {len(val_ids)} subjects ({val_ids})")
        print(f"  - Test:  sub-{test_sub:02d} (60 trials)")

    # 2. Load data with standardized EA and optical scaling
    if cache is None:
        cache = {}
        for sid in [test_sub] + pool:
            p = proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt"
            if not p.exists():
                raise FileNotFoundError(f"Missing data file: {p}")
            d = torch.load(p, weights_only=True)
            eeg_data = d["eeg"]
            if use_ea:
                from src.data.preprocessing import offline_euclidean_alignment
                eeg_data = torch.from_numpy(offline_euclidean_alignment(eeg_data.cpu().numpy())).float()
            fnirs_data = d["fnirs"] * 1e4
            cache[sid] = (
                eeg_data.to(device),
                fnirs_data.to(device),
                d["labels"].to(device)
            )

    tr_e = torch.cat([cache[s][0] for s in train_ids], dim=0)
    tr_f = torch.cat([cache[s][1] for s in train_ids], dim=0)
    tr_l = torch.cat([cache[s][2] for s in train_ids], dim=0)

    val_e = torch.cat([cache[s][0] for s in val_ids], dim=0)
    val_f = torch.cat([cache[s][1] for s in val_ids], dim=0)
    val_l = torch.cat([cache[s][2] for s in val_ids], dim=0)

    te_e, te_f, te_l = cache[test_sub]

    # 3. Model & Optimizer
    model = NVCDelayFormer(
        num_classes=2,
        eeg_channels=30,
        fnirs_channels=72,
        feature_dim=64,
        num_heads=4,
        nvc_delay_mean_sec=5.0,
        learnable_delay=True,
        readout_mode=readout_mode,
        direct_weight_mode=direct_weight_mode,
        cut_gate_latent=cut_gate_latent,
    ).to(device)

    opt = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = get_warmup_cosine_scheduler(opt, warmup_epochs=2, total_epochs=epochs)
    bs = batch_size
    n_tr = tr_e.size(0)

    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0

    # 4. Training loop with validation checkpointing
    t0 = time.time()
    criterion = nn.CrossEntropyLoss()
    for epoch in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(n_tr, device=device)
        epoch_loss = 0.0
        n_batches = 0
        for idx in range(0, n_tr, bs):
            b = perm[idx:idx+bs]
            opt.zero_grad()
            logits, _ = model(
                tr_e[b], tr_f[b],
                use_delay_prior=use_delay_prior,
                use_causal_mask=use_causal_mask,
            )
            loss = criterion(logits, tr_l[b])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            epoch_loss += loss.item()
            n_batches += 1
        sched.step()

        # Validation evaluation
        model.eval()
        with torch.no_grad():
            v_logits, _ = model(
                val_e, val_f,
                use_delay_prior=use_delay_prior,
                use_causal_mask=use_causal_mask,
            )
            v_preds = torch.argmax(v_logits, dim=1)
            v_acc = (v_preds == val_l).float().mean().item() * 100.0
            v_loss = criterion(v_logits, val_l).item()

        if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_loss < best_val_loss):
            best_val_acc = v_acc
            best_val_loss = v_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch

        if verbose:
            avg_tr_loss = epoch_loss / max(1, n_batches)
            print(f"  Epoch {epoch:2d}/{epochs:2d}: Train Loss = {avg_tr_loss:.4f} | Val Acc = {v_acc:5.1f}% (Best: {best_val_acc:5.1f}%)")

    # 5. Evaluate on held-out test subject
    model.load_state_dict({k: v.to(device) for k, v in best_state.items()})
    model.eval()
    with torch.no_grad():
        te_logits, _ = model(
            te_e, te_f,
            use_delay_prior=use_delay_prior,
            use_causal_mask=use_causal_mask,
        )
        preds = torch.argmax(te_logits, dim=1).cpu().numpy()
        targets = te_l.cpu().numpy()

    test_acc = float(np.mean(preds == targets) * 100.0)
    tp = int(np.sum((targets == 1) & (preds == 1)))
    tn = int(np.sum((targets == 0) & (preds == 0)))
    fp = int(np.sum((targets == 0) & (preds == 1)))
    fn = int(np.sum((targets == 1) & (preds == 0)))
    prec_1 = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec_1 = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_1 = 2 * prec_1 * rec_1 / (prec_1 + rec_1) if (prec_1 + rec_1) > 0 else 0.0
    prec_0 = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    rec_0 = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1_0 = 2 * prec_0 * rec_0 / (prec_0 + rec_0) if (prec_0 + rec_0) > 0 else 0.0
    macro_f1 = float((f1_0 + f1_1) / 2.0 * 100.0)

    elapsed = time.time() - t0
    if verbose:
        print(f"\n[Result] Held-Out Subject {test_sub:02d}: Test Acc = {test_acc:.2f}%, Macro F1 = {macro_f1:.2f}% (Time: {elapsed:.1f}s)")

    # 6. Save checkpoint if explicitly requested
    saved_ckpt_path = None
    if save_checkpoint:
        ckpt_path = Path(ckpt_output_path) if ckpt_output_path else Path("checkpoints") / f"best_nvc_delayformer_sub{test_sub:02d}.pt"
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "epoch": best_epoch,
            "model_state": best_state,
            "val_acc": best_val_acc,
            "val_loss": best_val_loss,
            "test_acc": test_acc,
            "macro_f1": macro_f1,
            "metrics": {"accuracy": test_acc / 100.0, "macro_f1": macro_f1 / 100.0},
            "version": "v2",
            "eeg_channels": 30,
            "fnirs_channels": 72,
            "feature_dim": 64,
            "num_heads": 4,
            "params": 63940,
        }, ckpt_path)
        saved_ckpt_path = str(ckpt_path)

    return {
        "test_subject": test_sub,
        "test_acc": test_acc,
        "macro_f1": macro_f1,
        "best_val_acc": best_val_acc,
        "best_val_loss": best_val_loss,
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "elapsed_sec": elapsed,
        "checkpoint_path": saved_ckpt_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train NVC-DelayFormer")
    parser.add_argument("--test_sub", type=int, default=5, help="Held-out subject ID for LOSO testing")
    args = parser.parse_args()

    train_single_loso_fold(test_sub=args.test_sub)

