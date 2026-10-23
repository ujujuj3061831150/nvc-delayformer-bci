"""
Export 100% empirical diagnostics for Figure 2:
1. Real CrEA Frobenius relative error convergence averaged across all 29 subjects
   (comparing empirical Bayes shrinkage prior R_src vs cold-start identity R_0 = I).
2. Real gate activations across MA, MI, and n-back from the model checkpoint.
3. Authentic (124, 250) cross-modal attention matrix from sub-05 evaluation.
"""
import json
import sys
import torch
import numpy as np
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.data.preprocessing import offline_euclidean_alignment
from src.models.nvc_net import NVCDelayFormer

device = torch.device('cpu')

# 1. Real CrEA Convergence (29 subjects of TU Berlin MA)
all_sub_covs = []
for s in range(1, 30):
    p = f'data/processed/sub-{s:02d}/ma_epochs.pt'
    ds = torch.load(p, map_location=device, weights_only=True)
    es = ds['eeg'].numpy()
    covs = [np.cov(es[t]) + 1e-5 * np.eye(30) for t in range(len(es))]
    all_sub_covs.append(covs)

errs_shrinkage_all = []
errs_naive_all = []

for s in range(29):
    covs_s = all_sub_covs[s]
    R_off = np.mean(covs_s, axis=0)
    norm_off = np.linalg.norm(R_off, 'fro')

    rem = [i for i in range(29) if i != s]
    train_ids = rem[5:]  # 23 training-fold participants
    train_covs = [c for tr in train_ids for c in all_sub_covs[tr]]
    R_src = np.mean(train_covs, axis=0)

    # Scale R_src to match this subject's initial trial trace
    scale = np.trace(covs_s[0]) / np.trace(R_src)
    R_src_sc = R_src * scale

    # Trace-matched Identity for cold-start identity baseline
    tr_C1 = np.trace(covs_s[0]) / 30.0
    R_I_sc = np.eye(30) * tr_C1

    e_s = []
    e_I = []

    acc_s = 5.0 * R_src_sc
    w_s = 5.0

    acc_I = 5.0 * R_I_sc
    w_I = 5.0

    for t in range(60):
        acc_s += covs_s[t]
        w_s += 1.0
        e_s.append(float(np.linalg.norm(acc_s / w_s - R_off, 'fro') / norm_off))

        acc_I += covs_s[t]
        w_I += 1.0
        e_I.append(float(np.linalg.norm(acc_I / w_I - R_off, 'fro') / norm_off))

    errs_shrinkage_all.append(e_s)
    errs_naive_all.append(e_I)

mean_err_s = (np.mean(errs_shrinkage_all, axis=0) * 100.0).tolist()
mean_err_n = (np.mean(errs_naive_all, axis=0) * 100.0).tolist()

print(f"CrEA calculated. Trial 1: Shrinkage={mean_err_s[0]:.2f}%, Cold-Start I={mean_err_n[0]:.2f}%")
print(f"Trial 5: Shrinkage={mean_err_s[4]:.2f}%, Cold-Start I={mean_err_n[4]:.2f}%")
print(f"Trial 8: Shrinkage={mean_err_s[7]:.2f}%, Cold-Start I={mean_err_n[7]:.2f}%")
print(f"Trial 60: Shrinkage={mean_err_s[59]:.2f}%, Cold-Start I={mean_err_n[59]:.2f}%")

# 2. Real Gate distributions & Real (124, 250) Attention Matrix
ckpt = torch.load('checkpoints/best_nvc_delayformer_sub05.pt', map_location=device, weights_only=False)
model = NVCDelayFormer(eeg_channels=30, fnirs_channels=72).to(device)
model.load_state_dict(ckpt['model_state'])
model.eval()

def get_real_gates(data_path):
    d = torch.load(data_path, map_location=device, weights_only=True)
    eeg = torch.from_numpy(offline_euclidean_alignment(d['eeg'].cpu().numpy())).float().to(device)
    fnirs = (d['fnirs'] * 1e4).to(device)
    with torch.no_grad():
        _, _, g = model(eeg, fnirs, return_gate=True)
        # g: (N, 64) -> average across feature channels per trial
        trial_means = g.mean(dim=-1).cpu().numpy().tolist()
        all_channels = g.cpu().numpy().flatten().tolist()
    return trial_means, all_channels

ma_trial_gates, ma_all_gates = get_real_gates('data/processed/sub-05/ma_epochs.pt')
mi_trial_gates, mi_all_gates = get_real_gates('data/processed_shin2017_mi/sub-05/mi_epochs.pt')
nb_trial_gates, nb_all_gates = get_real_gates('data/processed_shin2018_nback/sub-05/nback_epochs.pt')

# Extract real 124x250 attention matrix from Sub-05 MA trials
d5 = torch.load('data/processed/sub-05/ma_epochs.pt', map_location=device, weights_only=True)
eeg5 = torch.from_numpy(offline_euclidean_alignment(d5['eeg'].cpu().numpy())).float().to(device)
fnirs5 = (d5['fnirs'] * 1e4).to(device)
with torch.no_grad():
    _, attn5 = model(eeg5, fnirs5)
# Average across trials and attention heads -> (124, 250)
mean_attn = attn5.mean(dim=(0, 1)).cpu().numpy()
print(f"Real attention matrix extracted. Shape: {mean_attn.shape}, Min: {mean_attn.min():.6f}, Max: {mean_attn.max():.6f}")

output_data = {
    'crea_trials': list(range(1, 61)),
    'crea_error_shrinkage': [round(x, 4) for x in mean_err_s],
    'crea_error_naive': [round(x, 4) for x in mean_err_n],
    'ma_gate_trial_means': [round(x, 4) for x in ma_trial_gates],
    'mi_gate_trial_means': [round(x, 4) for x in mi_trial_gates],
    'nback_gate_trial_means': [round(x, 4) for x in nb_trial_gates],
    'ma_gate_channels': [round(x, 4) for x in ma_all_gates[:256]],
    'mi_gate_channels': [round(x, 4) for x in mi_all_gates[:256]],
    'nback_gate_channels': [round(x, 4) for x in nb_all_gates[:256]],
    'attention_matrix': [[round(float(v), 6) for v in row] for row in mean_attn],
}

out_path = Path('reports/real_diagnostics_data.json')
out_path.write_text(json.dumps(output_data, indent=2), encoding='utf-8')
print(f"Successfully exported 100% real empirical diagnostics to {out_path}")
