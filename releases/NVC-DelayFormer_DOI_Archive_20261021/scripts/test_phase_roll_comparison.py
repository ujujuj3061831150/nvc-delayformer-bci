"""
Compare Phase Roll (+/- 5.0s) across EEGNet, Standard-Attention, and NVC-DelayFormer
Also tests Delay Prior Tau Compensation (shifting tau to match the rolled lag).
Evaluated across all 29 subjects under 29-Fold LOSO.
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import scipy.stats as stats
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.nvc_net import NVCDelayFormer
from src.models.baselines import EEGNetClassifier, StandardCrossAttentionClassifier
from src.train import get_warmup_cosine_scheduler
from src.utils.seed import set_seed

def run_phase_roll_suite():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))

    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        cache[sid] = (
            d["eeg"].to(device),
            d["fnirs"].to(device),
            d["labels"].to(device)
        )

    print("=" * 80)
    print("TESTING PHASE ROLL (+/- 5s) & DELAY COMPENSATION ACROSS MODELS (29 SUBJECTS)")
    print("=" * 80)

    # 1. Train models across 29 folds
    eegnet_acc_norm, eegnet_acc_roll = [], []
    stdattn_acc_norm, stdattn_acc_roll = [], []
    nvc_acc_norm, nvc_acc_roll, nvc_acc_comp = [], [], []

    shift = 500 # 5.0s at 100Hz

    for test_sub in all_subs:
        set_seed(42 + test_sub)
        pool = [s for s in all_subs if s != test_sub]
        start_idx = (test_sub - 1) % len(pool)
        val_ids = [pool[(start_idx + i) % len(pool)] for i in range(5)]
        train_ids = [s for s in pool if s not in val_ids]

        tr_e = torch.cat([cache[s][0] for s in train_ids], dim=0)
        tr_f = torch.cat([cache[s][1] for s in train_ids], dim=0)
        tr_l = torch.cat([cache[s][2] for s in train_ids], dim=0)
        te_e, te_f, te_l = cache[test_sub]
        n_tr = tr_e.size(0)

        # Roll test EEG
        te_e_roll = torch.roll(te_e, shifts=shift, dims=-1)

        # --- A. EEGNet ---
        m_eeg = EEGNetClassifier(in_channels=28, num_classes=2, feature_dim=64).to(device)
        opt_eeg = AdamW(m_eeg.parameters(), lr=3e-3, weight_decay=0.05)
        sched_eeg = get_warmup_cosine_scheduler(opt_eeg, 2, 10)
        for ep in range(1, 11):
            m_eeg.train()
            perm = torch.randperm(n_tr, device=device)
            for idx in range(0, n_tr, 256):
                b = perm[idx:idx+256]
                opt_eeg.zero_grad()
                out = m_eeg(tr_e[b])
                loss = F.cross_entropy(out, tr_l[b])
                loss.backward()
                opt_eeg.step()
            sched_eeg.step()
        m_eeg.eval()
        with torch.no_grad():
            acc_norm = (m_eeg(te_e).argmax(-1) == te_l).float().mean().item() * 100.0
            acc_roll = (m_eeg(te_e_roll).argmax(-1) == te_l).float().mean().item() * 100.0
            eegnet_acc_norm.append(acc_norm)
            eegnet_acc_roll.append(acc_roll)

        # --- B. Standard-Attention ---
        m_std = StandardCrossAttentionClassifier(num_classes=2, eeg_channels=28, fnirs_channels=72, feature_dim=64, num_heads=4).to(device)
        opt_std = AdamW(m_std.parameters(), lr=3e-3, weight_decay=0.05)
        sched_std = get_warmup_cosine_scheduler(opt_std, 2, 10)
        for ep in range(1, 11):
            m_std.train()
            perm = torch.randperm(n_tr, device=device)
            for idx in range(0, n_tr, 256):
                b = perm[idx:idx+256]
                opt_std.zero_grad()
                out = m_std(tr_e[b], tr_f[b])
                loss = F.cross_entropy(out, tr_l[b])
                loss.backward()
                opt_std.step()
            sched_std.step()
        m_std.eval()
        with torch.no_grad():
            acc_norm = (m_std(te_e, te_f).argmax(-1) == te_l).float().mean().item() * 100.0
            acc_roll = (m_std(te_e_roll, te_f).argmax(-1) == te_l).float().mean().item() * 100.0
            stdattn_acc_norm.append(acc_norm)
            stdattn_acc_roll.append(acc_roll)

        # --- C. NVC-DelayFormer ---
        m_nvc = NVCDelayFormer(num_classes=2, eeg_channels=28, fnirs_channels=72, feature_dim=64, num_heads=4, nvc_delay_mean_sec=5.0, learnable_delay=False).to(device)
        opt_nvc = AdamW(m_nvc.parameters(), lr=3e-3, weight_decay=0.05)
        sched_nvc = get_warmup_cosine_scheduler(opt_nvc, 2, 10)
        for ep in range(1, 11):
            m_nvc.train()
            perm = torch.randperm(n_tr, device=device)
            for idx in range(0, n_tr, 256):
                b = perm[idx:idx+256]
                opt_nvc.zero_grad()
                logits, _, recon_pred = m_nvc(tr_e[b], tr_f[b], use_delay_prior=True, use_causal_mask=True, return_recon=True)
                w_diff = m_nvc.direct_readout.weight[1] - m_nvc.direct_readout.weight[0]
                target_hbo = m_nvc.compute_buxton_hemodynamics(tr_f[b], True, True)[:, :36, :]
                loss = F.cross_entropy(logits, tr_l[b]) + 0.08 * (w_diff ** 2).sum() + 1.0 * F.mse_loss(recon_pred, target_hbo)
                loss.backward()
                opt_nvc.step()
            sched_nvc.step()
        m_nvc.eval()
        with torch.no_grad():
            acc_norm, _ = m_nvc(te_e, te_f, use_delay_prior=True, use_causal_mask=True)
            acc_norm = (acc_norm.argmax(-1) == te_l).float().mean().item() * 100.0

            acc_roll, _ = m_nvc(te_e_roll, te_f, use_delay_prior=True, use_causal_mask=True)
            acc_roll = (acc_roll.argmax(-1) == te_l).float().mean().item() * 100.0

            # Tau Compensation: test with compensated delay prior
            # Rolling forward by +500 samples (+5.0s) means EEG events appear 5.0s later in time.
            # Thus the lag between fNIRS (peaking at ~5s) and EEG burst changes from 5s to 0s.
            m_nvc.cross_attention.delay_mean.data.fill_(0.0)
            acc_comp, _ = m_nvc(te_e_roll, te_f, use_delay_prior=True, use_causal_mask=False)
            acc_comp = (acc_comp.argmax(-1) == te_l).float().mean().item() * 100.0
            m_nvc.cross_attention.delay_mean.data.fill_(5.0)

            nvc_acc_norm.append(acc_norm)
            nvc_acc_roll.append(acc_roll)
            nvc_acc_comp.append(acc_comp)

    # Output stats
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY ACROSS 29 SUBJECTS (N=29, df=28):")
    print("=" * 80)

    for name, norm_list, roll_list in [
        ("EEGNet (Unimodal)", eegnet_acc_norm, eegnet_acc_roll),
        ("Standard-Attention", stdattn_acc_norm, stdattn_acc_roll),
        ("NVC-DelayFormer", nvc_acc_norm, nvc_acc_roll)
    ]:
        n_arr = np.array(norm_list)
        r_arr = np.array(roll_list)
        drop = n_arr - r_arr
        t_val, p_val = stats.ttest_rel(n_arr, r_arr)
        print(f"{name:<22}: Normal={n_arr.mean():.2f}% +/- {n_arr.std(ddof=1):.2f}% | Rolled={r_arr.mean():.2f}% +/- {r_arr.std(ddof=1):.2f}% | Drop={drop.mean():+.2f}% | t(28)={t_val:.3f}, p={p_val:.4e}")

    comp_arr = np.array(nvc_acc_comp)
    roll_arr = np.array(nvc_acc_roll)
    recov = comp_arr - roll_arr
    t_c, p_c = stats.ttest_rel(comp_arr, roll_arr)
    print(f"NVC Tau Compensated   : Rolled={roll_arr.mean():.2f}% -> Compensated={comp_arr.mean():.2f}% | Recovery={recov.mean():+.2f}% | t(28)={t_c:.3f}, p={p_c:.4e}")

if __name__ == "__main__":
    run_phase_roll_suite()
