# Cover Letter to Computer Methods and Programs in Biomedicine

October 13, 2026

Dear Editor,

We submit “Physiology-guided temporal fusion for cross-subject EEG–fNIRS classification” for consideration in *Computer Methods and Programs in Biomedicine*.

The study evaluates NVC-DelayFormer for mental arithmetic versus rest on the public TU Berlin EEG–fNIRS cohort. The architecture combines convolutional encoders, a fixed Gaussian delay prior, timestamp-constrained attention, weighted direct features, and an auxiliary reconstruction output.

Twenty-nine subject-held-out folds use 23 training subjects, five validation subjects, and one test subject each. Across 1,740 test trials, accuracy is 66.44% ± 10.85%, the 95% confidence interval is [62.31%, 70.57%], Macro F1 is 65.13%, and Cohen’s kappa is 0.3287. The four paired baseline comparisons have Benjamini–Hochberg q < 0.01.

The manuscript reports component ablations, a fixed-weight delay sweep, and input perturbations. A five-second circular EEG shift lowers accuracy by 6.61 percentage points. The independently trained zero-delay model reaches 66.61%, with Wilcoxon p = 0.9636 against the full model. Additional causal EEG smoothing is evaluated after offline preprocessing.

The model has 92,293 trainable parameters and 19.98 million profiled MACs. Batch-one GPU forward latency has median 3.24 ms and P99 5.89 ms. CPU latency, including its measured long tail, is reported separately. Timings exclude acquisition, preprocessing, and device transfer.

The accompanying records retain subject-level results and the statistical and engineering protocols.

Sincerely,

Antigravity BCI Research Collaborative

Laboratory for Neural Engineering & Neurovascular Computing

research@antigravity-bci.org
