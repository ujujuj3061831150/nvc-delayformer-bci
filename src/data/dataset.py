"""
PyTorch Dataset and Cross-Validation Data Loader for Hybrid EEG-fNIRS BCI.
Enforces strict Subject-Level Isolation (LOSO) with zero cross-subject data leakage.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import torch
from torch.utils.data import Dataset, DataLoader


class HybridEEGfNIRSDataset(Dataset):
    """
    Standard PyTorch Dataset for synchronized EEG-fNIRS trials.
    """
    def __init__(self, eeg: torch.Tensor, fnirs: torch.Tensor, labels: torch.Tensor):
        assert eeg.shape[0] == fnirs.shape[0] == labels.shape[0], "Trial counts mismatch."
        self.eeg = eeg
        self.fnirs = fnirs
        self.labels = labels

    def __len__(self) -> int:
        return self.labels.shape[0]

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.eeg[idx], self.fnirs[idx], self.labels[idx]


def load_subject_data(processed_dir: Path, subject_id: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Load cached preprocessed .pt file for a given subject."""
    sub_file = processed_dir / f"sub-{subject_id:02d}" / "ma_epochs.pt"
    assert sub_file.exists(), f"Processed file {sub_file} does not exist. Run preprocessing first."
    payload = torch.load(sub_file, weights_only=True)
    return payload["eeg"], payload["fnirs"], payload["labels"]


def get_loso_dataloaders(
    processed_dir: Path,
    test_subject_id: int,
    all_subject_ids: List[int],
    batch_size: int = 16,
    num_workers: int = 0
) -> Tuple[DataLoader, DataLoader]:
    """
    Generate Leave-One-Subject-Out (LOSO) DataLoaders.
    
    Args:
        processed_dir: Root directory of processed subject data.
        test_subject_id: Target unseen subject ID for testing.
        all_subject_ids: Full list of available subject IDs.
        batch_size: Mini-batch size.
        
    Returns:
        train_loader: Training set composed of all subjects except test_subject_id.
        test_loader: Evaluation set strictly composed of test_subject_id.
    """
    train_eeg_list, train_fnirs_list, train_label_list = [], [], []
    
    train_ids = [s for s in all_subject_ids if s != test_subject_id]
    assert len(train_ids) > 0, "No training subjects found."
    
    # 1. Pool training subjects
    for sub_id in train_ids:
        eeg, fnirs, labels = load_subject_data(processed_dir, sub_id)
        train_eeg_list.append(eeg)
        train_fnirs_list.append(fnirs)
        train_label_list.append(labels)
        
    train_eeg = torch.cat(train_eeg_list, dim=0)
    train_fnirs = torch.cat(train_fnirs_list, dim=0)
    train_labels = torch.cat(train_label_list, dim=0)
    
    # 2. Load held-out test subject
    test_eeg, test_fnirs, test_labels = load_subject_data(processed_dir, test_subject_id)
    
    train_dataset = HybridEEGfNIRSDataset(train_eeg, train_fnirs, train_labels)
    test_dataset = HybridEEGfNIRSDataset(test_eeg, test_fnirs, test_labels)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    
    return train_loader, test_loader


def get_loso_three_split_dataloaders(
    processed_dir: Path,
    test_subject_id: int,
    all_subject_ids: List[int],
    val_subjects_count: int = 5,
    batch_size: int = 16,
    num_workers: int = 0
) -> Tuple[DataLoader, DataLoader, DataLoader, List[int], List[int]]:
    """
    Generate strict 3-way Split DataLoaders for Leave-One-Subject-Out (LOSO)
    with a completely isolated Validation Subject Pool:
    - Test Set: strictly test_subject_id (1 subject, 100% held-out blind test).
    - Validation Set: val_subjects_count subjects deterministically isolated from training.
    - Training Set: remaining subjects used exclusively for gradient updates.

    Returns:
        train_loader: DataLoader for training subjects.
        val_loader: DataLoader for validation subjects (used for Early Stopping / checkpointing).
        test_loader: DataLoader for target unseen test subject (blind evaluation).
        train_ids: List of subject IDs in training set.
        val_ids: List of subject IDs in validation set.
    """
    pool_ids = sorted([s for s in all_subject_ids if s != test_subject_id])
    assert len(pool_ids) >= 2, f"Need at least 2 subjects in pool to form train and val splits, got {len(pool_ids)}"
    
    # Adaptive validation count: default 5 for 26 subjects, or 1 for small cohorts
    actual_val_count = min(val_subjects_count, max(1, len(pool_ids) // 5))
    
    # Deterministic circular assignment based on test_subject_id
    start_idx = (test_subject_id - 1) % len(pool_ids)
    val_ids = [pool_ids[(start_idx + i) % len(pool_ids)] for i in range(actual_val_count)]
    train_ids = [s for s in pool_ids if s not in val_ids]
    
    assert len(train_ids) > 0, "Training set cannot be empty."
    assert set(train_ids).isdisjoint(set(val_ids)), "Train and Val subjects must be mutually exclusive."
    assert test_subject_id not in train_ids and test_subject_id not in val_ids, "Test subject leaked into train/val!"
    
    # 1. Load Training Data
    tr_eeg, tr_fnirs, tr_lbl = [], [], []
    for sid in train_ids:
        eeg, fnirs, labels = load_subject_data(processed_dir, sid)
        tr_eeg.append(eeg)
        tr_fnirs.append(fnirs)
        tr_lbl.append(labels)
    train_dataset = HybridEEGfNIRSDataset(torch.cat(tr_eeg), torch.cat(tr_fnirs), torch.cat(tr_lbl))
    
    # 2. Load Validation Data
    val_eeg, val_fnirs, val_lbl = [], [], []
    for sid in val_ids:
        eeg, fnirs, labels = load_subject_data(processed_dir, sid)
        val_eeg.append(eeg)
        val_fnirs.append(fnirs)
        val_lbl.append(labels)
    val_dataset = HybridEEGfNIRSDataset(torch.cat(val_eeg), torch.cat(val_fnirs), torch.cat(val_lbl))
    
    # 3. Load Test Data
    t_eeg, t_fnirs, t_lbl = load_subject_data(processed_dir, test_subject_id)
    test_dataset = HybridEEGfNIRSDataset(t_eeg, t_fnirs, t_lbl)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    
    return train_loader, val_loader, test_loader, train_ids, val_ids

