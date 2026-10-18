"""
Full 26-Fold Leave-One-Subject-Out (LOSO) Three-Split Evaluation for NVC-DelayFormer
on Real Human TU Berlin Hybrid EEG-fNIRS Dataset (1,560 Trials Total).

Validation Architecture (Zero Test Leakage):
- Each Fold:
  * 20 Training Subjects (1,200 trials): exclusively used for backprop.
  * 5 Validation Subjects (300 trials): exclusively used for Early Stopping & checkpointing.
  * 1 Held-Out Test Subject (60 trials): evaluated strictly ONCE using the best checkpoint.
"""

import sys
import copy
import time
import json
from pathlib import Path
from typing import Dict, List
import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
import matplotlib.pyplot as plt

from src.models.nvc_net import NVCDelayFormer
from src.data.dataset import get_loso_three_split_dataloaders
from src.train import get_warmup_cosine_scheduler, compute_bci_metrics
from src.utils.seed import set_seed


def run_26sub_loso_pipeline(
    processed_dir: str = "data/processed",
    num_subjects: int = 26,
    epochs_per_fold: int = 25,
    batch_size: int = 32,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    lambda_recon: float = 0.1,
    seed: int = 42
) -> Dict:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    proc_path = Path(processed_dir)
    all_subject_ids = list(range(1, num_subjects + 1))
    
    print("=" * 86)
    print("26-FOLD LOSO THREE-SPLIT BENCHMARK: NVC-DELAYFORMER ON REAL TU BERLIN DATASET")
    print(f"Device: {device} | Folds: {num_subjects} | Epochs/Fold: {epochs_per_fold} | Batch: {batch_size}")
    print(f"Split Structure: 20 Train (1,200 trials) / 5 Val (300 trials) / 1 Test (60 trials)")
    print("=" * 86)
    
    fold_results = []
    start_total_time = time.time()
    
    for fold_idx, test_sub_id in enumerate(all_subject_ids, 1):
        fold_start = time.time()
        
        # 1. Generate 3-way Split Loaders
        train_loader, val_loader, test_loader, train_ids, val_ids = get_loso_three_split_dataloaders(
            processed_dir=proc_path,
            test_subject_id=test_sub_id,
            all_subject_ids=all_subject_ids,
            val_subjects_count=5,
            batch_size=batch_size,
            num_workers=0
        )
        
        # 2. Instantiate Fresh Model
        model = NVCDelayFormer(
            num_classes=2,
            eeg_channels=28,
            fnirs_channels=72,
            feature_dim=64,
            num_heads=4,
            nvc_delay_mean_sec=5.0,
            nvc_delay_std_sec=2.0,
            eeg_sample_rate_effective=25.0,
            fnirs_sample_rate=10.4,
            dropout=0.25
        ).to(device)
        
        optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
        scheduler = get_warmup_cosine_scheduler(optimizer, warmup_epochs=4, total_epochs=epochs_per_fold)
        criterion_ce = nn.CrossEntropyLoss()
        criterion_recon = nn.MSELoss()
        
        best_score = -float("inf")
        best_val_acc = 0.0
        best_state_dict = None
        
        # 3. Training Loop with Validation Checkpoint Selection
        for epoch in range(1, epochs_per_fold + 1):
            model.train()
            for eeg, fnirs, labels in train_loader:
                eeg, fnirs, labels = eeg.to(device), fnirs.to(device), labels.to(device)
                optimizer.zero_grad()
                logits, _, recon_pred, (deep_logits, shallow_logits) = model(
                    eeg, fnirs, use_delay_prior=True, return_recon=True, return_branch_logits=True
                )
                loss_joint = criterion_ce(logits, labels)
                loss_deep = criterion_ce(deep_logits, labels)
                loss_shallow = criterion_ce(shallow_logits, labels)
                loss_cls = loss_joint + 0.2 * (loss_deep + loss_shallow)
                
                target_hbo = fnirs[:, :36, :]
                norm_hbo = (target_hbo - target_hbo.mean(dim=-1, keepdim=True)) / (target_hbo.std(dim=-1, keepdim=True) + 1e-6)
                loss_recon = criterion_recon(recon_pred, norm_hbo)
                loss = loss_cls + lambda_recon * loss_recon
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                
            scheduler.step()
            
            # Validation Evaluation
            model.eval()
            val_preds, val_trues = [], []
            val_loss_total = 0.0
            with torch.no_grad():
                for eeg, fnirs, labels in val_loader:
                    eeg, fnirs, labels = eeg.to(device), fnirs.to(device), labels.to(device)
                    logits, _ = model(eeg, fnirs, use_delay_prior=True)
                    loss_v = criterion_ce(logits, labels)
                    val_loss_total += loss_v.item() * labels.size(0)
                    val_preds.append(torch.argmax(logits, dim=-1).cpu())
                    val_trues.append(labels.cpu())
                    
            val_metrics = compute_bci_metrics(torch.cat(val_trues), torch.cat(val_preds))
            val_loss = val_loss_total / len(val_loader.dataset)
            score = val_metrics["accuracy"] * 10.0 - val_loss
            
            if score > best_score:
                best_score = score
                best_val_acc = val_metrics["accuracy"]
                best_state_dict = copy.deepcopy(model.state_dict())
                
        # 4. Final Blind Evaluation on Unseen Test Subject
        if best_state_dict is not None:
            model.load_state_dict(best_state_dict)
            
        model.eval()
        test_preds, test_trues = [], []
        with torch.no_grad():
            for eeg, fnirs, labels in test_loader:
                eeg, fnirs, labels = eeg.to(device), fnirs.to(device), labels.to(device)
                logits, _ = model(eeg, fnirs, use_delay_prior=True)
                test_preds.append(torch.argmax(logits, dim=-1).cpu())
                test_trues.append(labels.cpu())
                
        test_metrics = compute_bci_metrics(torch.cat(test_trues), torch.cat(test_preds))
        learned_tau = float(model.cross_attention.delay_mean.mean().item()) if hasattr(model.cross_attention, "delay_mean") else 5.0
        fold_time = time.time() - fold_start
        
        result_item = {
            "fold": fold_idx,
            "test_subject": test_sub_id,
            "val_acc": round(best_val_acc * 100, 2),
            "test_acc": round(test_metrics["accuracy"] * 100, 2),
            "cohen_kappa": round(test_metrics["cohen_kappa"], 4),
            "macro_f1": round(test_metrics["macro_f1"], 4),
            "learned_tau": round(learned_tau, 2),
            "fold_time_sec": round(fold_time, 2)
        }
        fold_results.append(result_item)
        
        print(f"Fold {fold_idx:02d}/{num_subjects:02d} (Sub-{test_sub_id:02d}) | "
              f"Val: {result_item['val_acc']:5.2f}% | "
              f"Test: {result_item['test_acc']:5.2f}% | "
              f"Kappa: {result_item['cohen_kappa']:6.4f} | "
              f"Tau: {result_item['learned_tau']:4.2f}s | "
              f"Time: {result_item['fold_time_sec']:4.1f}s")
        
        # Explicit garbage collection and GPU cache cleanup across LOSO folds
        del model, optimizer, scheduler, train_loader, val_loader, test_loader
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    total_elapsed = time.time() - start_total_time
    test_accs = [r["test_acc"] for r in fold_results]
    kappas = [r["cohen_kappa"] for r in fold_results]
    f1s = [r["macro_f1"] for r in fold_results]
    taus = [r["learned_tau"] for r in fold_results]
    
    mean_acc = float(np.mean(test_accs))
    std_acc = float(np.std(test_accs))
    mean_kappa = float(np.mean(kappas))
    mean_tau = float(np.mean(taus))
    
    print("\n" + "=" * 86)
    print("26-FOLD LOSO FINAL BENCHMARK SUMMARY (NVC-DELAYFORMER ON REAL DATA):")
    print(f"Mean Test Accuracy : {mean_acc:.2f}% ± {std_acc:.2f}% (Chance level: 50.0%)")
    print(f"Mean Cohen's Kappa  : {mean_kappa:.4f}")
    print(f"Mean Learned Tau    : {mean_tau:.2f}s (Biological hemodynamic delay window)")
    print(f"Total Benchmark Time: {total_elapsed / 60:.2f} minutes")
    print("=" * 86)
    
    summary_data = {
        "num_subjects": num_subjects,
        "mean_accuracy": round(mean_acc, 2),
        "std_accuracy": round(std_acc, 2),
        "mean_kappa": round(mean_kappa, 4),
        "mean_learned_tau": round(mean_tau, 2),
        "total_time_seconds": round(total_elapsed, 1),
        "fold_results": fold_results
    }
    
    # Save Summary JSON
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "real_26sub_nvc_delayformer_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fp:
        json.dump(summary_data, fp, indent=2)
    print(f"[+] Summary report saved to: {summary_path}")
    
    # Generate 26-Subject Performance Distribution Plot
    fig_path = reports_dir / "figures" / "real_26sub_loso_performance.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plot_26sub_performance(fold_results, mean_acc, std_acc, fig_path)
    print(f"[+] Performance figure saved to: {fig_path}")
    
    return summary_data


def plot_26sub_performance(fold_results: List[Dict], mean_acc: float, std_acc: float, save_path: Path):
    sub_labels = [f"S{r['test_subject']:02d}" for r in fold_results]
    accs = [r["test_acc"] for r in fold_results]
    
    fig, ax = plt.subplots(figsize=(14, 5.5), dpi=300)
    bars = ax.bar(sub_labels, accs, color="#2ca02c", edgecolor="#1b611b", width=0.68, alpha=0.88, label="NVC-DelayFormer (Blind Test)")
    
    # Chance level & Mean line
    ax.axhline(50.0, color="#d62728", linestyle="--", lw=1.5, label="Chance Level (50.0%)")
    ax.axhline(mean_acc, color="#1f77b4", linestyle="-", lw=2.0, label=f"26-Fold Mean: {mean_acc:.2f}% (±{std_acc:.2f}%)")
    
    ax.set_ylabel("Blind Test Classification Accuracy (%)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Held-Out Test Subjects (26 Individual Human Participants)", fontsize=11, fontweight="bold")
    ax.set_title("NVC-DelayFormer: 26-Fold Full LOSO Blind Test Performance on Real TU Berlin Dataset", fontsize=12, pad=12)
    ax.set_ylim(40, 100)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", frameon=True, fontsize=10)
    
    # Value annotations on top of bars
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 1.0, f"{h:.1f}", ha="center", va="bottom", fontsize=7.5, rotation=0)
        
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    run_26sub_loso_pipeline(epochs_per_fold=25, batch_size=32)
