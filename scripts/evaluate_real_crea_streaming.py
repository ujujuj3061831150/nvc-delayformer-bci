import sys
sys.path.insert(0, ".")

import torch
import numpy as np
from pathlib import Path
import json

from src.models.nvc_net import NVCDelayFormer
from src.data.preprocessing import CausalRecursiveEA

def evaluate_streaming_crea():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    proc_dir = Path("data/processed")
    all_subs = list(range(1, 30))
    
    print("Loading datasets for 29 subjects...")
    sub_data = {}
    sub_raw_covs = {}
    for s in all_subs:
        d = torch.load(proc_dir / f"sub-{s:02d}" / "ma_epochs.pt", map_location="cpu", weights_only=True)
        eeg = d["eeg"].numpy() # (60, 30, 1000)
        covs = [np.cov(eeg[t]) + 1e-5 * np.eye(30) for t in range(len(eeg))]
        sub_data[s] = d
        sub_raw_covs[s] = covs

    # Load trained model checkpoint
    ckpt_path = Path("checkpoints/best_nvc_delayformer_sub05.pt")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    state = ckpt["model_state"] if isinstance(ckpt, dict) and "model_state" in ckpt else ckpt

    e_ch = 30
    f_ch = 72
    if "eeg_encoder.conv_spatial.weight" in state:
        e_ch = state["eeg_encoder.conv_spatial.weight"].shape[2]
    if "fnirs_encoder.conv_spatial.weight" in state:
        f_ch = state["fnirs_encoder.conv_spatial.weight"].shape[1]

    model = NVCDelayFormer(eeg_channels=e_ch, fnirs_channels=f_ch).to(device)
    model.load_state_dict(state)
    model.eval()

    # Load locked offline predictions for comparison
    with open("reports/real_29sub_locked_predictions.json", "r") as f:
        locked = json.load(f)

    print("Evaluating CrEA streaming alignment trial-by-trial for 29 subjects...")
    streaming_accs = []
    subject_details = {}

    for s in all_subs:
        # 23-subject training fold source prior (leave out test subject s and 5 cyclic val subjects)
        val_start = (s * 5) % 28
        val_ids = [(val_start + i) % 28 + 1 for i in range(5)]
        val_ids = [v if v < s else v + 1 for v in val_ids]
        train_ids = [x for x in all_subs if x != s and x not in val_ids]

        train_covs = [c for tid in train_ids for c in sub_raw_covs[tid]]
        R_src = np.mean(train_covs, axis=0)

        d = sub_data[s]
        eeg_raw = d["eeg"].numpy() # (60, 30, 1000)
        fnirs = (d["fnirs"] * 1e4).to(device)
        labels = d["labels"].to(device)

        # CrEA recursive transformation with training-fold prior
        crea = CausalRecursiveEA(channels=30, shrinkage_alpha=5.0, R_source=R_src)
        eeg_aligned = crea.transform_sequence(eeg_raw)
        errors, conds = crea.compute_frobenius_convergence(eeg_raw)

        eeg_aligned_t = torch.from_numpy(eeg_aligned).float().to(device)

        with torch.no_grad():
            logits, _ = model(eeg_aligned_t, fnirs, use_delay_prior=True, use_causal_mask=True)
            preds = logits.argmax(-1)
            correct = (preds == labels).sum().item()
            acc = float(correct / labels.numel() * 100.0)

        streaming_accs.append(acc)
        subject_details[f"sub-{s:02d}"] = {
            "streaming_acc": round(acc, 2),
            "offline_locked_acc": round(locked["NVC-DelayFormer"][str(s)], 2) if "NVC-DelayFormer" in locked else None,
            "cov_error_t1": round(float(errors[0] * 100.0), 2),
            "cov_error_t8": round(float(errors[7] * 100.0), 2),
            "cov_error_t60": round(float(errors[-1] * 100.0), 2),
            "labels": labels.cpu().numpy().tolist(),
            "preds": preds.cpu().numpy().tolist()
        }

    s_acc = np.array(streaming_accs)
    mean_acc = float(s_acc.mean())
    std_acc = float(s_acc.std(ddof=1))
    ci95 = [float(mean_acc - 1.96 * std_acc / np.sqrt(29)), float(mean_acc + 1.96 * std_acc / np.sqrt(29))]

    print("\n" + "=" * 60)
    print("CrEA STREAMING EVALUATION RESULTS (29 SUBJECTS)")
    print("=" * 60)
    print(f"Mean Streaming Accuracy: {mean_acc:.2f}% +/- {std_acc:.2f}%")
    print(f"95% CI: [{ci95[0]:.2f}%, {ci95[1]:.2f}%]")

    output = {
        "evaluation": "CrEA Trial-by-Trial Streaming Evaluation",
        "cohort": "TU Berlin Mental Arithmetic (29 participants, 1,740 trials)",
        "protocol": "Strict causal recursive alignment, zero session lookahead",
        "mean_streaming_acc": round(mean_acc, 2),
        "std_streaming_acc": round(std_acc, 2),
        "ci95": [round(ci95[0], 2), round(ci95[1], 2)],
        "subjects": subject_details
    }

    out_file = Path("reports/crea_streaming_evaluation_results.json")
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Saved complete streaming evaluation record to {out_file}")

if __name__ == "__main__":
    evaluate_streaming_crea()
