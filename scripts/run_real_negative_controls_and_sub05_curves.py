"""
Authentic 30-Channel Negative Controls & Sub-05 Training Curves Generator.
Evaluates across all 29 human subjects (1,740 authentic trials):
1. Full Model test accuracy (30 channels, 10.33 Hz)
2. Within-Class Cross-Modal Permutation (preserves class labels, shuffles only pair sync)
3. Across-Class Cross-Modal Permutation (unconstrained trial shuffling)
4. Temporal Phase Roll (+/- 5.0s shift in EEG)
5. Additional Causal EEG Smoothing (exponential smoothing added to offline-preprocessed EEG; fNIRS unchanged)
6. Authentic Sub-05 epoch-by-epoch training history & Nature-grade training curve plot
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import scipy.stats as stats
import scipy.signal as signal
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.nvc_net import NVCDelayFormer
from src.train import get_warmup_cosine_scheduler
from src.utils.seed import set_seed
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt


def run():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[+] Running on device: {device}")
    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))

    # Pre-cache authentic 30-channel data
    print("[+] Loading authentic 30-channel data across all 29 subjects...")
    cache = {}
    for sid in all_subs:
        d = torch.load(proc_dir / f"sub-{sid:02d}" / "ma_epochs.pt", weights_only=True)
        eeg = d["eeg"].to(device)       # (60, 30, 1000)
        fnirs = d["fnirs"].to(device)   # (60, 72, 124)
        labels = d["labels"].to(device) # (60,)
        assert eeg.size(1) == 30, f"Expected 30 channels, got {eeg.size(1)}"
        cache[sid] = (eeg, fnirs, labels)

    print("\n[Step 1] Training 30-channel Full Model across all 29 LOSO folds...")
    trained_models = {}
    full_fold_accs = []
    sub05_history = {
        "epoch": [], "train_loss_total": [], "train_loss_ce": [],
        "train_loss_recon": [], "val_loss_ce": [], "val_acc": []
    }

    total_epochs = 12
    warmup_epochs = 2
    bs = 256

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
        n_tr = tr_e.size(0)

        model = NVCDelayFormer(
            num_classes=2, eeg_channels=30, fnirs_channels=72, feature_dim=64, num_heads=4,
            nvc_delay_mean_sec=5.0, learnable_delay=False
        ).to(device)

        opt = AdamW(model.parameters(), lr=3e-3, weight_decay=0.05)
        sched = get_warmup_cosine_scheduler(opt, warmup_epochs=warmup_epochs, total_epochs=total_epochs)

        best_val_acc = -1.0
        best_val_loss = float("inf")
        best_state = None

        for epoch in range(1, total_epochs + 1):
            model.train()
            perm = torch.randperm(n_tr, device=device)
            ep_ce = 0.0
            ep_recon = 0.0
            ep_tot = 0.0
            batches = 0

            for idx in range(0, n_tr, bs):
                b = perm[idx:idx+bs]
                opt.zero_grad()
                logits, _, recon_pred = model(tr_e[b], tr_f[b], use_delay_prior=True, use_causal_mask=True, return_recon=True)
                w_diff = model.direct_readout.weight[1] - model.direct_readout.weight[0]
                ce_loss = F.cross_entropy(logits, tr_l[b])
                target_hbo = model.compute_buxton_hemodynamics(tr_f[b])[:, :36, :]
                recon_loss = F.mse_loss(recon_pred, target_hbo)
                loss = ce_loss + 0.08 * (w_diff ** 2).sum() + 1.0 * recon_loss

                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                opt.step()

                ep_ce += ce_loss.item()
                ep_recon += recon_loss.item()
                ep_tot += loss.item()
                batches += 1

            sched.step()

            model.eval()
            with torch.no_grad():
                v_logits, _ = model(val_e, val_f, use_delay_prior=True, use_causal_mask=True)
                v_ce = F.cross_entropy(v_logits, val_l).item()
                v_acc = (v_logits.argmax(-1) == val_l).float().mean().item() * 100.0

            if test_sub == 5:
                sub05_history["epoch"].append(epoch)
                sub05_history["train_loss_total"].append(ep_tot / batches)
                sub05_history["train_loss_ce"].append(ep_ce / batches)
                sub05_history["train_loss_recon"].append(ep_recon / batches)
                sub05_history["val_loss_ce"].append(v_ce)
                sub05_history["val_acc"].append(v_acc)

            if v_acc > best_val_acc or (abs(v_acc - best_val_acc) < 1e-4 and v_ce < best_val_loss):
                best_val_acc = v_acc
                best_val_loss = v_ce
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        model.load_state_dict(best_state)
        model.eval()
        trained_models[test_sub] = model

        with torch.no_grad():
            preds, _ = model(te_e, te_f, use_delay_prior=True, use_causal_mask=True)
            acc = (preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()
            full_fold_accs.append(acc)

    full_arr = np.array(full_fold_accs)
    print(f"      Full Model (30-ch) Accuracy: {full_arr.mean():.2f}% +/- {full_arr.std(ddof=1):.2f}%")

    # Save and Plot authentic Sub-05 training curves
    print("\n[Step 2] Generating authentic Sub-05 training curves figure...")
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
        "font.size": 7.5
    })
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.5, 2.8), dpi=600)
    eps = sub05_history["epoch"]

    # Panel A: Classification Cross-Entropy Loss & Val Accuracy
    ax1.plot(eps, sub05_history["train_loss_ce"], label="Train CE Loss", color="#0F4D92", lw=1.5)
    ax1.plot(eps, sub05_history["val_loss_ce"], label="Val CE Loss", color="#C85A46", lw=1.5, linestyle="--")
    ax1.set_xlabel("Epoch", fontweight="bold")
    ax1.set_ylabel("Cross-Entropy Loss", fontweight="bold")
    ax1.set_ylim(0.0, 1.2)
    ax1.legend(loc="upper right", fontsize=6.8)
    ax1.text(-0.16, 1.08, "a", transform=ax1.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax1.set_title("Sub-05 Classification Optimization", loc="left", fontsize=7.8, fontweight="bold")

    # Panel B: Auxiliary Reconstruction MSE Loss & Validation Accuracy
    ax2.plot(eps, sub05_history["train_loss_recon"], label=r"Aux $\mathcal{L}_{\mathrm{recon}}$ (MSE)", color="#329688", lw=1.5)
    ax2_twin = ax2.twinx()
    ax2_twin.plot(eps, sub05_history["val_acc"], label="Val Acc (%)", color="#7884B4", lw=1.5, linestyle="-.")
    ax2.set_xlabel("Epoch", fontweight="bold")
    ax2.set_ylabel(r"Reconstruction MSE ($\Delta[\mathrm{HbO}]$)", fontweight="bold", color="#329688")
    ax2_twin.set_ylabel("Validation Accuracy (%)", fontweight="bold", color="#7884B4")
    ax2_twin.spines["top"].set_visible(False)
    ax2_twin.spines["right"].set_color("#7884B4")
    ax2.spines["left"].set_color("#329688")
    ax2.set_ylim(0.0, 0.005)
    ax2_twin.set_ylim(40.0, 85.0)
    ax2.text(-0.16, 1.08, "b", transform=ax2.transAxes, fontsize=9.0, fontweight="bold", va="top")
    ax2.set_title("Hemodynamic Reconstruction & Accuracy", loc="left", fontsize=7.8, fontweight="bold")

    plt.tight_layout()
    for d in [Path("reports/figures"), Path("latex/figures"), Path("latex_cbm/figures"), Path(r"C:\Users\ikunccc\.gemini\antigravity\brain\dced5340-cb2c-4d72-a2e2-7006b0c89469\figures")]:
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / "training_curves_sub05.png", dpi=600)
        fig.savefig(d / "training_curves_sub05.pdf")
    plt.close(fig)
    print("      [OK] Authentic Sub-05 training curves saved.")

    # Step 3: Within-Class Permutation Control
    print("\n[Step 3] Evaluating Control 1: Within-Class Permutation (Preserving MA/Rest labels)...")
    num_monte_carlo = 10
    within_perm_sub_means = []
    for test_sub in all_subs:
        m = trained_models[test_sub]
        te_e, te_f, te_l = cache[test_sub]
        ma_idx = (te_l == 1).nonzero(as_tuple=True)[0]
        rest_idx = (te_l == 0).nonzero(as_tuple=True)[0]

        sub_mc_accs = []
        for seed_offset in range(num_monte_carlo):
            torch.manual_seed(1000 + test_sub * 100 + seed_offset)
            ma_perm = ma_idx[torch.randperm(len(ma_idx), device=device)]
            rest_perm = rest_idx[torch.randperm(len(rest_idx), device=device)]

            perm_eeg = te_e.clone()
            perm_eeg[ma_idx] = te_e[ma_perm]
            perm_eeg[rest_idx] = te_e[rest_perm]

            with torch.no_grad():
                preds, _ = m(perm_eeg, te_f, use_delay_prior=True, use_causal_mask=True)
                acc = (preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()
                sub_mc_accs.append(acc)
        within_perm_sub_means.append(float(np.mean(sub_mc_accs)))
    within_arr = np.array(within_perm_sub_means)
    print(f"      Within-Class Permutation Acc: {within_arr.mean():.2f}% +/- {within_arr.std(ddof=1):.2f}%")

    # Step 4: Across-Class Permutation Control (Unconstrained)
    print("\n[Step 4] Evaluating Control 2: Across-Class Permutation (Unconstrained shuffle)...")
    across_perm_sub_means = []
    for test_sub in all_subs:
        m = trained_models[test_sub]
        te_e, te_f, te_l = cache[test_sub]
        n_trials = te_l.size(0)

        sub_mc_accs = []
        for seed_offset in range(num_monte_carlo):
            torch.manual_seed(2000 + test_sub * 100 + seed_offset)
            perm = torch.randperm(n_trials, device=device)
            perm_eeg = te_e[perm]

            with torch.no_grad():
                preds, _ = m(perm_eeg, te_f, use_delay_prior=True, use_causal_mask=True)
                acc = (preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()
                sub_mc_accs.append(acc)
        across_perm_sub_means.append(float(np.mean(sub_mc_accs)))
    across_arr = np.array(across_perm_sub_means)
    print(f"      Across-Class Permutation Acc: {across_arr.mean():.2f}% +/- {across_arr.std(ddof=1):.2f}%")

    # Step 5: Temporal Phase Roll (+/- 5.0s EEG Roll)
    print("\n[Step 5] Evaluating Control 3: Temporal Phase Shift (+/- 5.0s EEG Roll)...")
    roll_sub_means = []
    for test_sub in all_subs:
        m = trained_models[test_sub]
        te_e, te_f, te_l = cache[test_sub]

        sub_roll_accs = []
        for shift in [500]:  # +/-500 are identical for 1000-sample epochs
            rolled_eeg = torch.roll(te_e, shifts=shift, dims=-1)
            with torch.no_grad():
                preds, _ = m(rolled_eeg, te_f, use_delay_prior=True, use_causal_mask=True)
                acc = (preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()
                sub_roll_accs.append(acc)
        roll_sub_means.append(float(np.mean(sub_roll_accs)))
    roll_arr = np.array(roll_sub_means)
    print(f"      Phase Shift (+/-5s) Acc: {roll_arr.mean():.2f}% +/- {roll_arr.std(ddof=1):.2f}%")

    # Step 6: Additional Causal EEG Smoothing
    print("\n[Step 6] Evaluating Control 4: Additional Causal EEG Smoothing (Single-Pass Causal IIR)...")
    # Simulate single-pass causal IIR filter using a causal exponential moving-average / recursive IIR
    # to measure the group delay impact on the trained model
    causal_sub_accs = []
    for test_sub in all_subs:
        m = trained_models[test_sub]
        te_e, te_f, te_l = cache[test_sub]

        # Emulate causal IIR filtering: single-pass 1st-order causal low-pass filter smoothing
        # on offline-preprocessed test EEG only; fNIRS unchanged
        alpha_e = 0.85
        te_e_causal = te_e.clone()
        for t in range(1, te_e_causal.size(-1)):
            te_e_causal[..., t] = alpha_e * te_e_causal[..., t-1] + (1 - alpha_e) * te_e[..., t]

        with torch.no_grad():
            preds, _ = m(te_e_causal, te_f, use_delay_prior=True, use_causal_mask=True)
            acc = (preds.argmax(-1) == te_l).sum().item() * 100.0 / te_l.numel()
            causal_sub_accs.append(acc)
    causal_arr = np.array(causal_sub_accs)
    print(f"      Streaming Causal Emulation Acc: {causal_arr.mean():.2f}% +/- {causal_arr.std(ddof=1):.2f}%")

    # Step 7: Paired Subject-Level Statistics across all 29 subjects
    print("\n[Step 7] Computing Subject-Level Paired Statistics (N=29, df=28)...")
    controls = {
        "Within-Class Permutation": within_arr,
        "Across-Class Permutation": across_arr,
        "Temporal Phase Roll (±5s)": roll_arr,
        "Additional Causal EEG Smoothing": causal_arr
    }

    stats_results = {}
    for name, c_arr in controls.items():
        diff = np.round(full_arr - c_arr, 10)
        mean_diff = float(diff.mean())
        std_diff = float(diff.std(ddof=1))
        se_diff = float(std_diff / np.sqrt(29))
        t_stat, p_t = stats.ttest_1samp(diff, 0, alternative='two-sided')
        w_stat, p_w = stats.wilcoxon(diff, zero_method='wilcox', correction=False, alternative='two-sided', method='approx')

        evaluations = num_monte_carlo if 'Permutation' in name else 1
        stats_results[name] = {
            "mean_acc": float(c_arr.mean()),
            "std_acc": float(c_arr.std(ddof=1)),
            "se_acc": float(c_arr.std(ddof=1) / np.sqrt(29)),
            "delta_mean": mean_diff,
            "delta_std": std_diff,
            "delta_se": se_diff,
            "t_statistic": float(t_stat),
            "df": 28,
            "t_test_p": float(p_t),
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p": float(p_w),
            "fold_accs": [float(x) for x in c_arr],
            "trials_per_subject": 60,
            "evaluations_per_subject": evaluations,
            "fold_correct_counts": np.rint(c_arr * (60 * evaluations) / 100).astype(int).tolist()
        }
        print(f"\n      --- {name} ---")
        print(f"      Mean Acc: {c_arr.mean():.2f}% +/- {c_arr.std(ddof=1):.2f}% | Drop: {mean_diff:+.2f}%")
        print(f"      Paired t-test: t(28) = {t_stat:.4f}, p = {p_t:.4e}")
        print(f"      Wilcoxon signed-rank: W = {w_stat:.1f}, p = {p_w:.4e}")

    q_values = stats.false_discovery_control([r['wilcoxon_p'] for r in stats_results.values()], method='bh')
    for row, q_value in zip(stats_results.values(), q_values):
        row['fdr_q'] = float(q_value)

    output_data = {
        "description": "Authentic 30-Channel Negative Controls Benchmark (N=29 Subjects, 1,740 Real Trials)",
        "full_model": {
            "mean_acc": float(full_arr.mean()),
            "std_acc": float(full_arr.std(ddof=1)),
            "se_acc": float(full_arr.std(ddof=1) / np.sqrt(29)),
            "fold_accs": [float(x) for x in full_arr],
            "trials_per_subject": 60,
            "evaluations_per_subject": 1,
            "fold_correct_counts": np.rint(full_arr * 60 / 100).astype(int).tolist()
        },
        "controls": stats_results,
        "sub05_training_history": sub05_history,
        "statistics_protocol": {
            "unit": "subject", "subjects": 29, "standard_deviation_ddof": 1,
            "difference": "full minus control accuracy, percentage points",
            "difference_round_decimals": 10,
            "t_test": "two-sided one-sample t on paired differences",
            "wilcoxon": {"alternative": "two-sided", "zero_method": "wilcox", "method": "approx", "continuity_correction": False},
            "fdr": "Benjamini-Hochberg over four perturbation Wilcoxon tests"
        }
    }

    out_json = Path("reports/negative_controls_rigorous_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"\n[+] Saved authentic 30-channel results to {out_json}")

    # Save Markdown Table
    md_lines = [
        "# Authentic 30-Channel Fold-by-Fold Negative Controls (N=29 Subjects, 1,740 Trials)",
        "",
        "| Subject | Full Model Acc (%) | Within-Class Perm (%) | Across-Class Perm (%) | Phase Roll ±5s (%) | Streaming Causal (%) |",
        "| :---: | :---: | :---: | :---: | :---: | :---: |"
    ]
    for i in range(29):
        sid = f"Sub-{i+1:02d}"
        md_lines.append(f"| {sid} | {full_arr[i]:.2f}% | {within_arr[i]:.2f}% | {across_arr[i]:.2f}% | {roll_arr[i]:.2f}% | {causal_arr[i]:.2f}% |")

    md_lines.extend([
        "",
        "## Summary Statistics Across 29 Subjects (df=28)",
        "",
        f"- **Full Model**: {full_arr.mean():.2f}% ± {full_arr.std(ddof=1):.2f}%",
        f"- **Within-Class Permutation**: {within_arr.mean():.2f}% ± {within_arr.std(ddof=1):.2f}% (Drop: {full_arr.mean()-within_arr.mean():+.2f}%, p_t = {stats_results['Within-Class Permutation']['t_test_p']:.4e})",
        f"- **Across-Class Permutation**: {across_arr.mean():.2f}% ± {across_arr.std(ddof=1):.2f}% (Drop: {full_arr.mean()-across_arr.mean():+.2f}%, p_t = {stats_results['Across-Class Permutation']['t_test_p']:.4e})",
        f"- **Temporal Phase Roll (±5s)**: {roll_arr.mean():.2f}% ± {roll_arr.std(ddof=1):.2f}% (Drop: {full_arr.mean()-roll_arr.mean():+.2f}%, p_t = {stats_results['Temporal Phase Roll (±5s)']['t_test_p']:.4e})",
        f"- **Additional Causal EEG Smoothing**: {causal_arr.mean():.2f}% ± {causal_arr.std(ddof=1):.2f}% (Drop: {full_arr.mean()-causal_arr.mean():+.2f}%, p_t = {stats_results['Additional Causal EEG Smoothing']['t_test_p']:.4e})",
        ""
    ])

    out_md = Path("reports/negative_controls_fold_table.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"[+] Saved markdown table to {out_md}")


if __name__ == "__main__":
    run()
