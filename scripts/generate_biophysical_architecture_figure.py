"""
Generate Publication-Grade Multi-Scale Biophysical & Architecture Schematic
Figure: Bridging Neurovascular Coupling Biology to Cross-Attention Transformers
Targeting IEEE TBME / Nature-family publication standards.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path

def draw_architecture_schematic(output_png: Path, output_pdf: Path):
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "axes.edgecolor": "#2c3e50",
        "axes.linewidth": 1.2,
        "figure.dpi": 300
    })

    fig = plt.figure(figsize=(15, 8.5), facecolor="#ffffff")
    
    # 3 Major Horizontal Panels
    ax_bio = fig.add_axes([0.05, 0.52, 0.40, 0.42])
    ax_sens = fig.add_axes([0.05, 0.08, 0.40, 0.38])
    ax_net = fig.add_axes([0.50, 0.08, 0.47, 0.86])

    # -------------------------------------------------------------------------
    # PANEL A: BIOPHYSICAL NVC CASCADE
    # -------------------------------------------------------------------------
    ax_bio.set_xlim(0, 10)
    ax_bio.set_ylim(0, 10)
    ax_bio.axis("off")
    ax_bio.set_title("A | Biophysical Neurovascular Coupling (NVC) Cascade", 
                     fontsize=12, fontweight="bold", loc="left", color="#1a252f", pad=10)

    # Box 1: Neural Activity
    b1 = patches.FancyBboxPatch((0.5, 5.2), 2.5, 4.0, boxstyle="round,pad=0.2", 
                                facecolor="#ebf5fb", edgecolor="#2980b9", linewidth=1.5)
    ax_bio.add_patch(b1)
    ax_bio.text(1.75, 8.4, "1. Synaptic Firing", fontsize=10, fontweight="bold", ha="center", color="#1b4f72")
    ax_bio.text(1.75, 7.2, "Pyramidal Neurons\nGlutamate Release\nTemporal: ~10 ms", 
                fontsize=8.5, ha="center", color="#2c3e50")
    # Action potential spike
    t_spk = np.linspace(0.8, 2.7, 50)
    spk = 5.8 + 0.6 * np.exp(-((t_spk - 1.75)/0.15)**2) * np.sin(20*(t_spk - 1.75))
    ax_bio.plot(t_spk, spk, color="#e74c3c", lw=1.5)

    # Arrow 1 -> 2
    ax_bio.annotate("", xy=(3.8, 7.2), xytext=(3.1, 7.2),
                    arrowprops=dict(arrowstyle="->", color="#34495e", lw=2))

    # Box 2: Astrocytic Signaling
    b2 = patches.FancyBboxPatch((3.8, 5.2), 2.5, 4.0, boxstyle="round,pad=0.2", 
                                facecolor="#fef9e7", edgecolor="#f39c12", linewidth=1.5)
    ax_bio.add_patch(b2)
    ax_bio.text(5.05, 8.4, "2. Astrocytic Relay", fontsize=10, fontweight="bold", ha="center", color="#7d6608")
    ax_bio.text(5.05, 7.1, "Astrocytic Endfeet\nCa2+ Elevation\nVasodilator Synthesis", 
                fontsize=8.5, ha="center", color="#2c3e50")
    ax_bio.text(5.05, 5.8, "EETs / NO / PGE2", fontsize=8, ha="center", style="italic", color="#d35400")

    # Arrow 2 -> 3
    ax_bio.annotate("", xy=(7.1, 7.2), xytext=(6.4, 7.2),
                    arrowprops=dict(arrowstyle="->", color="#34495e", lw=2))

    # Box 3: Hemodynamic Response
    b3 = patches.FancyBboxPatch((7.1, 5.2), 2.6, 4.0, boxstyle="round,pad=0.2", 
                                facecolor="#fdedec", edgecolor="#e74c3c", linewidth=1.5)
    ax_bio.add_patch(b3)
    ax_bio.text(8.4, 8.4, "3. Vascular Dilation", fontsize=10, fontweight="bold", ha="center", color="#78281f")
    ax_bio.text(8.4, 7.1, "Arteriolar Smooth Muscle\nDelta[HbO] Up, Delta[HbR] Down\nCanonical Delay: ~5.0 s", 
                fontsize=8.5, ha="center", color="#2c3e50")
    # HRF curve
    t_hrf = np.linspace(7.3, 9.5, 50)
    hrf = 5.6 + 0.8 * (((t_hrf - 7.3)/1.0)**4) * np.exp(-(t_hrf - 7.3)/0.35)
    ax_bio.plot(t_hrf, hrf, color="#c0392b", lw=2)

    # Biological bridge label across bottom of Panel A
    ax_bio.text(5.0, 3.8, "<--- Biophysical Hemodynamic Delay Axis (tau ~ 5.16-5.25 s, Mean 5.18 s) --->", 
                fontsize=9.0, ha="center", color="#8e44ad", fontweight="bold",
                bbox=dict(boxstyle="square,pad=0.3", fc="#f4ecf7", ec="#9b59b6", lw=1))

    # -------------------------------------------------------------------------
    # PANEL B: MULTIMODAL SENSORS & SIGNAL PROCESSING
    # -------------------------------------------------------------------------
    ax_sens.set_xlim(0, 10)
    ax_sens.set_ylim(0, 10)
    ax_sens.axis("off")
    ax_sens.set_title("B | Multimodal Dual-Stream Acquisition & MBLL Inversion", 
                      fontsize=12, fontweight="bold", loc="left", color="#1a252f", pad=10)

    # EEG Stream
    eeg_box = patches.FancyBboxPatch((0.5, 5.2), 9.0, 3.8, boxstyle="round,pad=0.2", 
                                     facecolor="#f4f6f7", edgecolor="#7f8c8d", linewidth=1.2)
    ax_sens.add_patch(eeg_box)
    ax_sens.text(1.2, 8.0, "Scalp EEG Stream", fontsize=10, fontweight="bold", color="#2c3e50")
    ax_sens.text(1.2, 6.2, "28 Electrodes (10-20 Standard Layout)\nSampling: 100 Hz | Common Average Reference (CAR)\nBandpass: 0.5 - 45.0 Hz (Zero-Phase SOS)", 
                 fontsize=8.5, color="#34495e")
    # Mini EEG wave
    t_eeg = np.linspace(6.5, 9.2, 100)
    eeg_sig = 7.0 + 0.4 * np.sin(10*t_eeg) + 0.2 * np.cos(25*t_eeg)
    ax_sens.plot(t_eeg, eeg_sig, color="#2980b9", lw=1.2)

    # fNIRS Stream
    fnirs_box = patches.FancyBboxPatch((0.5, 0.5), 9.0, 4.2, boxstyle="round,pad=0.2", 
                                       facecolor="#fdf2e9", edgecolor="#d35400", linewidth=1.2)
    ax_sens.add_patch(fnirs_box)
    ax_sens.text(1.2, 3.8, "Prefrontal fNIRS & MBLL Inversion", fontsize=10, fontweight="bold", color="#935116")
    ax_sens.text(1.2, 1.8, "36 Optode Pairs (Dual-Wavelength: 760 nm & 850 nm)\nMBLL: Extinction Inversion Matrix Condition Number kappa = 3.64 < 15.0\nBandpass: 0.01 - 0.10 Hz (Mayer Wave & Cardiac Rejection)", 
                 fontsize=8.5, color="#5d6d7e")
    # Mini fNIRS wave
    t_fn = np.linspace(6.8, 9.2, 80)
    fn_sig = 2.4 + 0.5 * (1.0 / (1.0 + np.exp(-3*(t_fn - 8.0))))
    ax_sens.plot(t_fn, fn_sig, color="#e67e22", lw=2)

    # -------------------------------------------------------------------------
    # PANEL C: NVC-DELAYFORMER NEURAL ARCHITECTURE
    # -------------------------------------------------------------------------
    ax_net.set_xlim(0, 10)
    ax_net.set_ylim(0, 10)
    ax_net.axis("off")
    ax_net.set_title("C | NVC-DelayFormer Cross-Attention & Multi-Task Engine", 
                     fontsize=12, fontweight="bold", loc="left", color="#1a252f", pad=10)

    # EEG Encoder
    ax_net.add_patch(patches.FancyBboxPatch((0.5, 7.2), 3.8, 2.0, boxstyle="round,pad=0.2", 
                                           facecolor="#ebf5fb", edgecolor="#2980b9", lw=1.5))
    ax_net.text(2.4, 8.4, "EEG Spatiotemporal Encoder", fontsize=9.5, fontweight="bold", ha="center", color="#1b4f72")
    ax_net.text(2.4, 7.6, "1D Conv -> BatchNorm -> GELU\nKeys & Values: K, V in R^(T_eeg x D)", 
                fontsize=8, ha="center", color="#34495e")

    # fNIRS Encoder
    ax_net.add_patch(patches.FancyBboxPatch((5.7, 7.2), 3.8, 2.0, boxstyle="round,pad=0.2", 
                                           facecolor="#fef5e7", edgecolor="#d35400", lw=1.5))
    ax_net.text(7.6, 8.4, "fNIRS Convolutional Encoder", fontsize=9.5, fontweight="bold", ha="center", color="#784212")
    ax_net.text(7.6, 7.6, "1D Conv -> Spatial BatchNorm -> GELU\nQueries: Q in R^(T_fnirs x D)", 
                fontsize=8, ha="center", color="#34495e")

    # Central Core: Cross-Attention with Causal Delay Prior
    core_box = patches.FancyBboxPatch((0.5, 3.3), 9.0, 3.3, boxstyle="round,pad=0.25", 
                                      facecolor="#f9ebea", edgecolor="#c0392b", lw=2.0)
    ax_net.add_patch(core_box)
    ax_net.text(5.0, 6.0, "Physiology-Guided Causal Cross-Attention Core", fontsize=11, fontweight="bold", ha="center", color="#922b21")
    
    # Formula in Core Box
    core_desc = (
        "Attention Logits S_(i,j) = (Q_i * K_j^T) / sqrt(d_k) + gamma * P_(i,j) + M_(i,j)\n\n"
        "Gaussian Delay Prior: P_(i,j) = - ((t_i - t_j) - tau)^2 / (2 * sigma^2)\n"
        "[Learned: tau -> 5.18 s (5.16-5.25 s),  sigma -> 1.50 s,  gamma = 0.25]\n\n"
        "Upper-Triangular Causal Mask: M_(i,j) = 0 if (t_i - t_j >= 0) else -inf"
    )
    ax_net.text(5.0, 4.3, core_desc, fontsize=9.0, ha="center", color="#2c3e50")

    # Arrows from Encoders into Core
    ax_net.annotate("", xy=(2.4, 6.6), xytext=(2.4, 7.2), arrowprops=dict(arrowstyle="->", color="#2980b9", lw=2))
    ax_net.annotate("", xy=(7.6, 6.6), xytext=(7.6, 7.2), arrowprops=dict(arrowstyle="->", color="#d35400", lw=2))

    # Arrow from Core to Output Heads
    ax_net.annotate("", xy=(5.0, 2.5), xytext=(5.0, 3.3), arrowprops=dict(arrowstyle="->", color="#c0392b", lw=2))

    # Multi-Task Heads
    # Head 1: Classification
    ax_net.add_patch(patches.FancyBboxPatch((0.5, 0.4), 4.2, 2.0, boxstyle="round,pad=0.2", 
                                           facecolor="#d5f5e3", edgecolor="#27ae60", lw=1.5))
    ax_net.text(2.6, 1.8, "Task 1: Cognitive Classification", fontsize=9.5, fontweight="bold", ha="center", color="#196f3d")
    ax_net.text(2.6, 0.9, "Linear Head -> y in {MA, Rest}\nLoss: Cross-Entropy L_ce\nAccuracy: 65.52% +- 10.58% (N=29)", 
                fontsize=8.5, ha="center", color="#145a32")

    # Head 2: Reconstruction
    ax_net.add_patch(patches.FancyBboxPatch((5.3, 0.4), 4.2, 2.0, boxstyle="round,pad=0.2", 
                                           facecolor="#e8f8f5", edgecolor="#16a085", lw=1.5))
    ax_net.text(7.4, 1.8, "Task 2: Auxiliary Delta[HbO] Decoder", fontsize=9.5, fontweight="bold", ha="center", color="#0e6251")
    ax_net.text(7.4, 0.9, "1D Conv Reconstructor -> Y_HbO\nLoss: MSE L_recon (r_HbO = 0.77)\nOrthogonal Gradients (cos theta = +0.0089)", 
                fontsize=8.5, ha="center", color="#0b5345")

    # Global Multi-Task Bracket
    ax_net.text(5.0, 2.7, "Total Multi-Task Objective:  L_total = L_ce + 0.08 * ||w_diff||^2 + L_recon", 
                fontsize=9.5, ha="center", color="#8e44ad", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#f4ecf7", ec="#8e44ad", lw=1))

    # Save outputs
    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.savefig(output_pdf, bbox_inches="tight")
    for extra_dir in [Path("latex/figures"), Path("C:/Users/ikunccc/.gemini/antigravity/brain/dced5340-cb2c-4d72-a2e2-7006b0c89469/figures")]:
        extra_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(extra_dir / output_png.name, dpi=300, bbox_inches="tight")
        plt.savefig(extra_dir / output_pdf.name, bbox_inches="tight")
    plt.close()
    print(f"[+] Multi-scale schematic saved to: {output_png} and {output_pdf}")

if __name__ == "__main__":
    png_path = Path("reports/figures/nvc_delayformer_architecture_schematic.png")
    pdf_path = Path("reports/figures/nvc_delayformer_architecture_schematic.pdf")
    draw_architecture_schematic(png_path, pdf_path)
    draw_architecture_schematic(png_path, pdf_path)
