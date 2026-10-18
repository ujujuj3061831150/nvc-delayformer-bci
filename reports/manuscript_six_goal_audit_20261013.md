# CBM 手稿六目标审查报告

审查日期：2026-10-13（Asia/Shanghai）。

审查对象：`E:/课题4/reports/manuscript_CBM_submission.pdf`，11 个物理页，正文页码 1–10；对应 `latex_cbm/main_cbm.tex`、`latex_cbm/references.bib`、当前模型与数据解析代码、29 人实验 JSON、负对照 JSON、作图代码和已保存检查点。

**结论：六项目标均未达到要求；不建议按当前版本投稿。最优先问题是输入 EEG 通道错误，其次是方法与实际代码不一致、消融混杂和图表/统计错配。现有数字不能通过统一替换成审查清单中的数字而修复。**

本次为审查，没有修改原手稿、参考文献或实验代码，也没有重跑训练。生成了本报告、复算证据 JSON 和全 29 人输入检查 JSON。材料中的既往“PASS”报告仅作为待核验材料，未当作验证结论。

## 0. 范围与版本识别

当前 PDF 的章节实际为：3 Biophysical Modeling；4 Architecture；5 Experimental Setup；6 Results；7 Ablation；8 Negative Controls；9 Interpretability；10 Discussion；11 Conclusion。当前只有 Table 1、Table 2，没有 Table 3。审查清单中的章节号与目标数字不完全适用此版本。

| 目标 | 判定 | 关键问题 |
|---|---|---|
| 1 数学与维度 | 不通过 | 250/124 长度正确；多头定义、缩放、广播、输出路径、输入物理含义均不闭环 |
| 2 数字与统计 | 不通过 | 目标数值版本不符；Figure 3 与图注冲突；SE 被写为 CI；t/Wilcoxon 错配；q 值错误 |
| 3 论断与证据 | 不通过 | 固定延迟被称为可学习；显式正则被称为自主发现；消融并非单因素 |
| 4 文献 | 不通过 | Delpy 引用存在但缺 DOI；至少数条题名、作者、卷号或文章号错误；一条疑似拼接条目 |
| 5 工程复现 | 不通过 | 参数量和 MACs 不匹配；延迟硬件/预热协议与代码不对应 |
| 6 审稿防御 | 不通过 | 局限性已有段落，但含未证实的最大规模、统计功效和他人泄漏断言 |

## 1. 最高优先级：输入真实性与预处理

### A01：全 29 人 EEG 输入有 18 个重复通道【投稿阻断】

位置：`src/data/parse_real_tuberlin.py:23`（EEG_TARGET_28）、`:91`（匹配与回退）；证据：`reports/manuscript_CBM_input_audit_20261013.json`。

原始 Sub-01 MA 会话实际 EEG 通道为 F7、AFF5h、F3、AFp1、AFp2、AFF6h、F4、F8、AFF1h、AFF2h、Cz、Pz、FCC5h、FCC3h、CCP5h、CCP3h、T7、P7、P3、PPO1h、POO1、POO2、PPO2h、P4、FCC4h、FCC6h、CCP4h、CCP6h、P8、T8，以及两个 EOG 通道；文件采样率 200 Hz。

目标列表中的 Fp1、AFz、F1、FC5、FC1、C3、CP5、CP1、Oz、Fp2、F2、FC2、FC6、C4、CP2、CP6、O1、O2 共 18 个名称不存在。代码执行 `matches[0] if matches else 0`，把这些通道全部替换为实际第一个通道 F7，却保留目标名称。

**检查全 29 个 `ma_epochs.pt`：每人上述 18 个位置均与通道 0 逐元素相等。** 每人的形状确实为 EEG `(60,28,1000)`、fNIRS `(60,72,124)`，两类均 30 个试次，但形状正确不等于 28 个独立真实 EEG 通道。

影响：当前精度仅对应该错误输入管线；空间滤波、额中线 theta、Fp1/AFz/Fp2 拓扑解释不可按所标电极成立；任何修复后的性能都必须重新计算，不能承诺继续得到 65.52%。

修复：使用原始文件真实通道并明确选择规则；未匹配通道立即报错；保存源索引、真实名称、montage、被试/会话来源与预处理哈希。修复后重建全部输入并重跑 LOSO、基线、消融及相关图表。

### A02：fNIRS 处理顺序与采样时间需重新验证【高】

原始 Sub-01 NIRS 标注信号 `NIRS (low wavelength, high wavelength)`，单位 V，采样率 10 Hz，波长 760/850 nm。解析器先对强度做 0.01–0.1 Hz 带通，再对带通结果截断至 `>=1e-4` 并取强度比的负对数。正文却描述为先有 optical densities，再带通，再 MBLL。这两条管线不等价。对带通强度的符号截断可能引入明显非线性失真；需从正的原始强度/有效光学基线形成 OD 后再按经验证的流程滤波，核查饱和、负值和低强度处理。

12 秒原始 10 Hz 信号经过重采样成为 124 点；按等长重采样解释，输出有效速率应为 `124/12=10.333333… Hz`，模型与数据元数据却使用 10.4 Hz。PDF 图注/预处理写 10.33 Hz，架构正文写 10.4 Hz。应将实际采样时间轴保存为数据元信息，并让先验使用该时间轴；不能仅改正文。

单位链亦未闭环：正文 epsilon 用 `mM^-1 cm^-1` 和 d=3 cm；代码注释用 `mm^-1 (mol/L)^-1` 和 d=30 mm，随后还有输入幅度依赖的缩放。需要核实系数表的真正单位与 ln/log10 约定，统一浓度单位、长度单位和图表单位。条件数不能证明单位正确。

## 2. 目标 1：数学、符号与维度

### 已通过的有限检查

- EEG 1000 点经 k=4、s=4、无 padding 的池化得到 250 点；k=15、p=7、s=1 保长。
- fNIRS 124 点经 k=5、p=2、s=1 保长。
- 实际前向输出：logits `(1,2)`，attention `(1,4,124,250)`，reconstruction `(1,36,124)`。已运行当前固定延迟模型验证。
- 相关正文未发现把 66/62 当作当前 token 长度的残留；普通精度、CI 中出现这些数字并不构成错误。
- 未发现 tau 被同时用于 Softmax 温度或衰减系数。但仍有其他符号复用。

### M01：多头维度与缩放缺失【高】

PDF 正文第 4 页 / Eq. 9；`latex_cbm/main_cbm.tex:137–158`。

正文定义 Q/K/V 为三维张量，d_k=64；接着 W 被定义为四维 `(B,H,124,250)`，最后又直接写 Z=WV 为三维 `(B,124,64)`。未定义分头、转置、head 合并与广播，不能视为完整推导。

当前代码 D=64、H=4、每头 d_h=16，以 `sqrt(16)` 缩放而非正文的 `sqrt(64)`。应写清：

```text
E: (B,250,64), F: (B,124,64)
Qh: (B,4,124,16)
Kh,Vh: (B,4,250,16)
S = Qh @ Kh.transpose(-2,-1) / sqrt(16): (B,4,124,250)
P,M: (124,250), broadcast to (1,1,124,250)
A = softmax(S + prior + M, dim=-1): (B,4,124,250)
Ch = A @ Vh: (B,4,124,16)
merge_heads(Ch): (B,124,64)
```

还需补齐实际输出投影、门控、LayerNorm、时间包络加权；这些运算都存在于代码。

### M02：Gaussian prior 的实际公式不匹配【高】

正文写 `gamma=0.25`、`log(P+1e-6)`，代码是 `-0.35 * abs(prior_scale) * (dt-clamp(tau,0,8))^2 / (2*clamp(sigma,0.5,4)^2+1e-8)`，其中 prior_scale 可学习。两者系数、参数化和尾部截断均不同。Figure 1 又展示与正文/代码不完全相同的 prior 表达。不能互称等价。

### M03：因果边界应由 dt=0 定义，不能擅改为 dt=tau【高】

当前定义 `dt=t_nirs[i]-t_eeg[j]`；Eq. 8 允许 dt>=0、屏蔽 dt<0，等时点允许。代码实际上屏蔽 `dt<-1e-4`，存在 0.1 ms 容差。建议显式定义 epsilon_t 的单位与作用，使用完整互补分段。

`0<=dt<tau` 是因果的、偏离 prior 中心的连接，当前实现允许它；tau 是软先验中心，不是硬屏蔽阈值。若新增 dt>=tau 的硬条件，会改变方法，还可能导致最早若干 query 全部被屏蔽，须说明空行处理并重新实验。

由于 Q/K 对应不同速率的矩形矩阵 124x250，掩码不是通常索引意义的“upper-triangular”；应称按物理时间定义的跨模态掩码。

### M04：“严格因果”不能由 attention mask 保证【高】

EEG temporal conv 使用对称 padding 7；fNIRS conv 使用对称 padding 2；EEG pooling token j 的原始支撑是 4j…4j+3，若以中心标记应有 1.5/100 秒偏移。若以左端标记 j/25，则其特征包含该时标之后的信息。

预处理用双向零相位滤波，代码 `compute_buxton_hemodynamics` 使用中心差分，均读取未来样本。故 dt>=0 只约束 token 间访问，不证明全管线的流式因果性、无未来样本访问或验证数据隔离。需要区分三者，真实在线验证须采用因果滤波、因果卷积/明确缓冲和单侧导数。

### M05：符号复用、参数未定义与 HRF 峰值错误【中/高】

- M 在 MBLL 表示 2x2 反演矩阵，又在 attention 表示 124x250 mask；D 在 MBLL 表示 DPF 对角矩阵，而模型维度应另用 d_model。
- 正文把 `mathbf{P}_{i,j}`、`mathbf{M}_{i,j}` 等矩阵元素写成粗体；矩阵粗体、标量元素斜体/普通数学字体应统一。
- 重建损失 C/T 未说明为 C_HbO=36、T_NIRS=124；Softmax 所沿维度、广播、头合并未定义。
- Eq. 5 的 A1/A2/alpha1/alpha2/beta1/beta2 没有完整参数/单位定义。单项 `t^alpha exp(-t/beta)` 的峰值为 alpha*beta，tau 出现在常数因子里并不自动使峰值等于 tau。若称 tau 为峰时，须给出约束 alpha1*beta1=tau 等，并说明第二项对总峰值的影响；最好使用有可靠来源且明确参数的 canonical HRF。
- “最高 mutual information 必然在 tau”不是给定卷积式能推出的物理不变量；必须改为建模假设/待检验经验规律。

## 3. 目标 2：数字、统计与 LOSO

### D01：用户清单的数值不是当前实验数值【高】

| 指标 | 审查清单 | 当前 PDF | 当前 29 人 JSON/复算 |
|---|---:|---:|---:|
| 主模型均值 | 65.52% | 65.52% | 65.51724498% |
| 主模型 Std | 8.71% | 10.58% | ddof=0:10.57814813%；ddof=1:10.76538653% |
| Macro F1 | 65.18% | 未报告 | 无逐试次预测，不能重建 |
| EEGNet | 60.32% | 57.93% | 57.93103761% |
| 单 fNIRS | 51.90% | 54.31% | 54.31034699% |
| 标准 attention | 61.72% | 58.16% | 58.16092296% |
| 对 EEGNet 提升 | 5.20 | 7.59 | 7.58620737 个百分点 |
| 对 fNIRS 提升 | 13.62 | 11.21 | 11.20689799 个百分点 |
| 对标准 attention 提升 | 3.80 | 7.36 | 7.35632202 个百分点 |

Abstract、Table 1、Section 6 和 Conclusion 的主均值/Std 当前彼此一致。清单中的三项提升算术上成立，但缺少对应实验记录，不能用于替换。精度差应写 percentage points/pp，避免与相对百分比提升混淆。

### D02：样本 SD、CI 和误差棒口径混杂【高】

当前主实验 JSON 用 np.std() 即 ddof=0；负对照 JSON 用 ddof=1。推荐把受试者间 SD 统一为样本 SD=10.77%，并明确报告单位。

由当前 29 个 fold 复算的受试者均值 t 区间为 `[61.4223%,69.6122%]`，即 `[61.42%,69.61%]`。PDF `[61.50%,69.54%]` 是基于 ddof=0 SD 和 2.048 左右临界值；JSON benchmark 另用 1.96 得到 `[61.6672%,69.3673%]`。不应混用并全部标记为同一 CI。

Figure 2 图注写 95% CI，但 `src/run_29sub_full_benchmark.py:446` 传入 `yerr=ses`；视觉上误差棒约 2 个百分点也支持它是 SE。Figure 4 的 delay 曲线同样使用 SE，应显式标注。

### D03：Figure 3 混淆矩阵与文本严重矛盾【投稿阻断】

PDF 正文第 5 页图中对角线 96.7%、70.0%，两类支持数均为 30 时，正确数约 29+21=50，accuracy 和 balanced accuracy 均为 83.33%。图注和 Section 6.3 却写 76.67%，且称两类都为 76.67%。当前 29 人 JSON 中第五个 fold 的主模型 accuracy 又为 68.33%。这至少涉及三组不同实验或错误标注，不能靠改一个数字闭环。

作图来源 `src/train.py:222–248` 每个 epoch 在 test_loader 评估并据此选 best checkpoint。若 Figure 3 来自这条训练路径，就存在测试集模型选择泄漏；这不等于主 29-fold benchmark 存在该泄漏，但该图不能继续称 blind test，须从主实验锁定模型的逐试次预测重新生成。

补充检查：保存的 `checkpoints/best_nvc_delayformer_sub05.pt` 的 epoch=11、val_acc=0.8333333、metrics accuracy=0.8333333、MacroF1=0.8303167，与图中83.33%相符。其state_dict不含当前模型的direct_readout与当前形状的hrf_reconstructor权重，说明它还属于不同架构版本；不能与当前92,225参数主实验混用。

### D04：p 值方法错配、effect size 错误、q 值错误【高】

Wrong Delay 的真实情况：tau=0 秒、不是反向 -tau；paired t-test p=0.0450651；Wilcoxon p=0.0690179。Table 2 和对应正文对这两者的标注目前正确；**审查清单中 Wilcoxon=0.0451 / t=0.0690 的对应关系是反的。** Table 2 却把 Wrong Delay q 写为 0.0684，JSON 的正确 q 为 0.0690179（0.0690）。按 Wilcoxon 或对应 FDR，没有显著证据；不能择取未经校正 t p 强称机制确认。

主基线统计复算如下：

| 比较对象 | t(28) 复算 | t-test p | Wilcoxon p | dz 复算 | PDF 问题 |
|---|---:|---:|---:|---:|---|
| EEGNet | 3.2722 | 0.0028345 | 0.0029923 | 0.6076 | Section 6.1 把 0.0030 写成 paired t p；t=3.242 也不符 |
| fNIRS-CNN | 4.6177 | 0.00007884 | 0.00023076 | 0.8575 | 文中 t=4.148、p=0.0002、dz=0.77 均未按同一组 fold 计算 |
| Feature-Concat | 2.9293 | 0.0066862 | 0.0050619 | 0.5440 | dz=0.58 不符 |
| Standard-Attention | 3.3698 | 0.0022075 | 0.0015414 | 0.6258 | t p 写0.0021、dz=0.65 不符 |

Table 1/2 使用 *, **, ***，但未提供显著性图例；需要注明阈值、双侧/单侧、主检验、零差与 ties 处理、BH 的检验家族。星号应固定绑定一个预先选定的方法，而不是每行挑较小 p。w/o Recon 的 Wilcoxon p=0.0513、q=0.0684，不支持校正后显著。

所有主基线 Wilcoxon BH q 当前小于 0.01，但其中 Feature-Concat p=0.0050619，因此“所有对比 p<0.005”不成立。Shapiro-Wilk 必须说明测试哪组 paired differences，不能一组结果覆盖所有比较。LOSO 各 fold 训练集合重叠，应说明统计依赖限制。

### D05：LOSO 隔离存在；宣称的验证/训练协议不存在【高】

`src/run_29sub_full_benchmark.py:87–97` 确实每 fold 划分 23 train / 5 val / 1 test，test subject 不在训练内，29 人各一次 test。训练中的随机打乱是训练集 minibatch shuffle，不是 within-subject random split。

但 val_ids 只被排除，没有验证前向、早停或 best validation checkpoint 选择。代码训练固定 10 epochs，AdamW lr=3e-3、weight_decay=0.05、batch=256；正文写 early stopping patience=12、lr=1e-3、weight_decay=1e-4、batch=32。需据真实实验改正文，或按声明协议重新训练。

两份 26sub/29sub benchmark JSON 的 SHA256 完全相同，且均包含 29 个 fold。这不证明造假，但证明文件命名/版本溯源失效。建议保存实验运行 ID、配置、代码 commit/hash、数据 hash、每 fold subject IDs、prediction 与 checkpoint，并清除历史文件误用。

### D06：随机水平检验算术正确但独立性假设过强【中/高】

1140/1740 对应 65.5172%，exact one-sided binomial p=4.24185e-39，公式数值正确。但同被试试次、时间连续性及 LOSO 训练集合共享，使“1740 独立试次”假设未经论证。应以受试者为统计单位或采用保持被试/会话结构的 permutation/bootstrap。

当前 fold accuracy 对 50% 的探索性双侧单样本 t-test p=1.8662e-8；这是本次复算结果，不能冒充原实验预注册检验，且不能消除输入和模型选择问题。

## 4. 目标 3：方法与证据链

### C01：主基准根本没有学习 tau【投稿阻断】

`src/run_29sub_full_benchmark.py:108,207` 明确 `learnable_delay=False`；tau 和 sigma 注册为 buffer，主实验固定 tau=5、sigma=1.5。正文、摘要、标题相关论述与 Conclusion 却强调 learnable/adaptive、自主发现。学习率 eta_tau=0.1 也未在主训练 optimizer 中实现。

### C02：“自主收敛”被显式目标正则驱动【投稿阻断】

`src/run_29sub_full_benchmark.py:312–313` 加入 `0.04*(delay_mean-5.18)**2`。该实验还聚合了多被试训练数据，而非独立留一 test 机制证据。不能称 unconstrained backpropagation、spontaneous discovery、without manual hyperparameter tuning，Figure 4B 的“Spontaneous Convergence Proof”不成立。

另有架构层面 `clamp(tau,0,8)`；负 tau 输入被钳为 0，因此当前代码不能直接用于 -tau 反向延迟实验。本次前向验证 tau=-5 与 tau=0 的 prior00/屏蔽边界一致。

修复：删除自主发现的结论；若要保留，必须移除目标值正则、分开训练/验证/test，在多初值多随机种子下报告轨迹和不收敛情况，并给出真正方向反转实验。

### C03：正文分类式遗漏主要分支【投稿阻断】

正文 logits=MLP(GAP(Z_cross))，当前实际为：

```text
deep_logits = MLP(concat(mean(fused),mean(EEG_encoded)))
direct_features = normalized, temporally weighted fNIRS derivatives and EEG log energy
logits = 0.02 * deep_logits + 0.98 * direct_readout(direct_features)
```

0.98 是 logit 的线性系数，不能直接当作98%性能贡献，但足以说明正文没有描述真正输出路径。

还遗漏：Gaussian kernel marginal 时间权重、固定宽度1.1、EEG onset exponential、task_gate sigmoid、基于幅度的 unit_scale、reconstruction detach混合、g_recon、沿通道 roll(18) 和 BatchNorm 等。对架构/因果归因/复杂度均有影响。

### C04：重建目标不是正文声称的原始 HbO【高】

重建器输入是 `(B,100,124)`：64维融合特征和36维 fNIRS 派生信号拼接；不是只从 Z_cross 预测。目标为 `compute_buxton_hemodynamics(fnirs)[:,:36,:]`，即导数加0.15*信号再乘幅度缩放，不是 MBLL 得到的原始 baseline-subtracted HbO。

因此 r_HbO/MSE_HbO 的物理标签和“从 EEG/fused latents 恢复真实血流”的解释不成立。该一阶算子也不能直接等同完整 Balloon Model，需给出推导或改称经验线性 hemodynamic proxy。高重建相关性可能包含目标自输入的 shortcut，必须增加 target-excluded reconstruction 控制。

### C05：消融混杂，无法单独证明 mask/prior 机制【投稿阻断】

`compute_nvc_temporal_envelopes` 的分支不只切换 mask：移除 prior 改为均匀时间权重；移除 mask 改为人为 anti-causal kernel（NIRS约1.5秒、EEG约6秒）。`compute_buxton_hemodynamics` 在任何 prior/mask 关闭时又删除导数项。重建 target 也因此改变。

因此 w/o Causal Mask 的 -9.02 pp 不只是 attention mask 的效应；w/o Delay 同样混杂。应固定全部其他算子，仅独立切换 attention logit bias 或 mask，重新训练/评估，并补充容量匹配基线。

### C06：负对照不能收敛到已证实的生理因果方向【高】

- Wrong Delay 是 tau=0，不是 -tau，且 Wilcoxon/FDR 未显著。
- Phase-roll comparative script 的补偿同时设置 tau=0 并关闭 mask，不是单独调 prior；由此还触发前述时间包络/导数的多重变化，无法叫 affirmative causal confirmation。
- 对长度1000的 EEG，+500 与-500 circular roll 完全相同；“±5s”不是两个独立方向的 perturbation。wrap seam 对不同模型影响不同，EEGNet不显著不能排除 seam 对 NVC 的影响。
- “一个模型显著、另一个不显著”不等于模型间下降量差异显著；需要受试者级 interaction/差值之差或等效性检验。p>=0.25 也不证明 unaffected/insensitive。
- 当前负对照 JSON 的 roll 是 65.52→58.39、下降7.13 pp、p=8.122e-8；正文 comparative experiment 却是66.09→59.20、下降6.90 pp、p=7.05e-8。二者可能来自不同重新训练，但后者没有持久化逐fold输出，本次不能复算，须标明实验来源并补充原始结果。
- within-class permutation 不显著最多说明类条件配对破坏未检出下降；不能证明模型使用 genuine NVC。across-class permutation 改变类别相容性，本身不能隔离时延机制。

可接受论断：现有结果支持“在该实现和数据上，对特定时间扰动存在模型相关的性能变化”。生理方向性需要无混杂正/零/负 delay控制、匹配参数、固定读出/滤波与边界处理，再进行预定义对比。

### C07：Ghost descriptions 与过度表述【高】

当前 PDF 未发现 Label Smoothing、自监督分支，亦未发现清单列出的 completely eliminates/perfectly solves/guarantees optimal 三个精确短语。真正残留的是不存在于主训练的 learned delay、early stopping、tau学习率，以及未被控制实验证实的 Mayer-wave suppression、生理因果确认、无计算开销和立即部署。

应删除/降级：resolves、catastrophic collapse、confirms、ruled out、immediate feasibility、without computational overhead、unaffected。不能机械替换为 significantly attenuates/superior adaptability，因为这些词仍需相应统计实验。

### C08：可解释性图/描述不对应【高】

Figure 5 图中 validation loss 上升且 validation accuracy下降，图注却称单调降低和持续改善；它是60 epoch路径，不是主10 epoch实验。需要注明探索性来源或重绘主实验。

Figure 6 的 topomap 数值范围与正文1.95/+0.88不一致，单位还需解决。`src/utils/topomap.py` 把空间滤波权重乘积的 ranking 线性映射到0.72–0.96，且可回退至手工 canonical pairs；这些不是原始 cross-attention 概率。时间 attention 的250个 key并非28个电极，不能直接视为电极之间的连接。正文 w>0.88/真实 cortical flow需撤回或重做有明确定义的 attribution。

Figure 7 实际可见高值集中于接近起点，5秒线只是理论覆盖线；不能仅靠红色理论线说明已经观察到 learned 5秒band。熵4.58、erank13.33、Fisher2.1288缺少与锁定主模型/真实数据直接绑定的导出记录，应标明样本、归一化定义、数据来源；不得用随机模型审计替代实验证据。

## 5. 目标 4：参考文献

### B01：结构核查

`.bib` 共33条，正文引用28个不同key；没有未定义cite key。5个未引用key：benjamini1995controlling、shapiro1965analysis、shin2018simultaneous、cope1991system、lotte2018review。若正文使用BH/Shapiro，宜真正引用相应来源。

23条缺 DOI（包括非期刊会议/学位条目）；已存在的10个 DOI 均符合基本 `10.…/…` 结构。不是所有会议/学位文献必有 DOI，不能编造补齐。当前 `.bib` 未发现明显裸 & 导致的 LaTeX 编译问题；标题大小写保护不等于元数据真实性。

已尝试逐条 Crossref DOI/题名检索；部分返回 HTTP 429，有些无DOI题名检索返回了错误候选。**完整的“33条均真实且无错误”未获验证；证据JSON中已保留失败和候选状态，不能把题名搜索首条自动当作对应文献。**

### B02：已确认/高度可疑的条目

| key | 当前问题 | 可靠核查/处理 |
|---|---|---|
| delpy1988estimation | 原始Delpy1988已在正文与重建目标处引用；缺DOI | 补 `10.1088/0031-9155/33/12/008`；不是需要从二次综述“替换回原典” |
| scholkmann2014review | 作者/卷页对应的是另一完整题名，现题名错误 | 正确题名为 A review on continuous wave functional near-infrared spectroscopy and imaging instrumentation and methodology；NeuroImage85(Part1):6–27 |
| hong2017future | 给定DOI对应文章题名与bib题名不同 | DOI真实题名 Hybrid Brain–Computer Interface Techniques for Improved Classification Accuracy and Increased Number of Commands: A Review |
| salim2023lightweight | `Salim, Rukhsar` 把given/family颠倒，正文错误地称Salim | Crossref/作者arXiv：given Salim，family Rukhsar；应Rukhsar and Tiwari |
| perez2024unraveling | volume244错，4名作者表错，包含非该论文作者Gómez并漏3人 | volume246；6作者 Pérez-Velasco, Marcos-Martínez, Santamaría-Vázquez, Martínez-Cagigal, Moreno-Calderón, Hornero；108048 |
| keles2016increasing | 精确题名未找到支持；JNE13(5):056004实际属于另一篇论文 | 该卷/文章号对应Moses等 Neural speech recognition: Continuous phoneme decoding using spatiotemporal representations of human cortical activity；现条目疑似拼接，须从作者原始论文核实或移除，不可保留 |
| lotte2018review（未引用） | pages021005/issue2不符；作者Chouvatut需校核 | 正确文章号031005、issue3、DOI10.1088/1741-2552/aab2f2；需按作者原文名单修复 |

原典链接：[Delpy1988](https://doi.org/10.1088/0031-9155/33/12/008)；[Scholkmann2014出版方](https://www.sciencedirect.com/science/article/pii/S1053811913004941)；[Hong2017出版方](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2017.00035/full)；[Rukhsar作者预印本](https://arxiv.org/abs/2305.04325)；[Pérez-Velasco机构记录](https://portaldelaciencia.uva.es/documentos/65d1e700824cc36763f8d264?lang=en_US)；[056004作者手稿](https://escholarship.org/content/qt7mp0q4mj/qt7mp0q4mj_noSplash_f2f348296a139f692315b9385a8f058a.pdf)。

### B03：近年生态与实质对话

当前有3篇2022–2025 CMPB文献在正文引用：2023轻量seizure、2024 MI解释性、2025 EEGConvNeXt dementia。数量达到“至少3”的下限，但没有同期EEG-fNIRS融合代表作；seizure/dementia不能替代跨模态融合和MI解码对话。

可补充且已核对出版方的两篇：

1. **fNIRSNET: A multi-view spatio-temporal convolutional neural network fusion for functional near-infrared spectroscopy-based auditory event classification**，EAAI137(PartB)，109256，2024，DOI `10.1016/j.engappai.2024.109256`。直接讨论HbO/HbR视图与EEG-fNIRS融合；需指出它是听觉任务，不可直接把准确率与本MA-LOSO比较。[出版方](https://www.sciencedirect.com/science/article/abs/pii/S0952197624014143)。
2. **A multiscale feature fusion network based on attention mechanism for motor imagery EEG decoding**，ASOC151，111129，2024，DOI `10.1016/j.asoc.2023.111129`。可讨论多尺度时间编码与本跨模态生理先验的区别。[出版方](https://www.sciencedirect.com/science/article/pii/S156849462301147X)。

当前目标投稿期刊是 Computers in Biology and Medicine（CBM），不是 Computer Methods and Programs in Biomedicine（CMPB）。如“目标期刊近期文献”确指CBM，还要另做CBM直接相关检索；不能把CMPB当作CBM。

## 6. 目标 5：工程复现

### E01：参数量实际不一致【高】

本次实例化当前代码并精确数参数；fixed指主实验模式：

| 模型 | PDF Table1 | 29人JSON | 当前代码 |
|---|---:|---:|---:|
| EEGNet | 7,986 | 36,226 | 36,226 |
| fNIRS-CNN | 17,154 | 17,154 | 17,154 |
| Feature-Concat | 24,818 | 53,058 | 53,058 |
| Standard-Attention | 41,586 | 69,826 | 69,826 |
| NVC fixed | 76,257 | 92,225 | 92,225 |
| NVC learnable | 未区分 | 未区分 | 92,227 |

清单43.8k没有当前证据；PDF76,257也不符。参数增加影响Discussion的容量竞争解释，不能只改单个参数值。

### E02：14.2M MACs未闭环【高】

对 batch1、EEG(1,28,1000)、fNIRS(1,72,124)运行前向，按Conv1d/Linear稠密MACs计算并加两次attention矩阵乘法，得到 **19,911,688 MACs ≈19.91M**。其中QK/AV为3.968M；模型即使不请求return_recon仍执行重建器，因此不能随意排除它。

此计数未含BN、激活、Softmax、exp、导数与元素运算，是明示口径下的部分算子MAC统计，不能称完整硬件FLOPs。若每MAC计2FLOPs，对这些算子约39.82M FLOPs。论文14.2M未找到匹配统计脚本/排除规则，须统一工具版本、输入形状、precision、batch、算子范围及MAC/FLOP约定。

### E03：延迟协议“写了”，但不可复现【高】

PDF Section10.2披露i7-12700H CPU @2.30GHz及RTX4060、batch1、1000 warmup+5000 timed、1.61±0.12ms、P993.06ms、568.1 trials/s。披露表面完整，但没有明确该值来自CPU还是GPU，也没有保存匹配原始latency samples。

主benchmark代码自动选择CUDA/CPU，10 warmup+100 timed，JSON NVC平均3.41518ms；当前白盒审计脚本为TorchScript、50 warmup+100 timed，报告Mean1.37ms、P992.75ms，吞吐2928.6来自batch4。均不支持上述1000/5000协议。清单中的硬件“例如”不能当作已实测硬件。

需要分别给出CPU/GPU型号、线程数、PyTorch/CUDA/cuDNN版本、eval/no_grad、精度、同步、输入驻留/传输范围、eager/JIT、warmup/test次数、每次耗时样本、统计SD或SE定义、测试checkpoint以及是否包含前处理。不要把此次检查环境当作原实验机器。

1.61ms的直接倒数约621.1 trials/s；568.1可以来自不同开销/协议，但须说明，两者不能被写成同一测量的严格换算。

### E04：嵌入式和在线结论超出证据【高】

消费级CPU/GPU测试不能证明立即适用于可穿戴microcontroller；<250MB VRAM也不是微控制器资源证据。需降为“supports further evaluation on resource-constrained platforms”，并补目标硬件、RAM/功耗/量化和端到端延迟实测。

论文64.83±10.42% causal filtering emulation未在当前负对照JSON中找到对应结果；脚本虽然开头描述streaming control，实际当前输出只包含3种permutation/roll控制，未实现该流式过滤结果。此数字应移除或补可复算真实实验。10–12秒输入缓冲与算法前向毫秒数必须继续分开。

## 7. 目标 6：防御段落是否科学成立

Discussion已有single-cohort、解剖异质性和跨被试/被试内区分段落；临床delay标志被明确写为exploratory hypothesis，这点合理。但以下必须修正：

1. 本研究实际是 Mental Arithmetic vs Rest，不是双手MI；原始基准另含MI，不能据此称本实验为双手运动解码。原始数据说明：[TU Berlin](https://doc.ml.tu-berlin.de/hBCI/contactthanks.html)。
2. “one of the largest”“全球极少数严格校准”“通常10–15人”“far exceeds”缺系统比较或来源；保留客观N=29、同时记录和公开可获取即可，勿堆叠规模宣传。
3. p<0.005不等于证明高统计功效，且不能用统计显著性“最小化小样本偏差”。需给效应/CI和外部泛化局限，不用p替代power分析。
4. 跨被试任务与被试内任务确实不同，但within-subject训练测试不天然构成泄漏。无指向性审计证据不能指责所有85%以上报告“artificially inflated/overfitting leakage”。应说明协议不可直接比较。
5. 65.52%对50%和54.31%的差异应分别绑定对应统计检验；清单51.90%不是当前baseline。不得把一个p<0.005同时作为多个论断的泛指证据。
6. 当前测试集用于epoch选择的单被试图路径，必须主动区分并重做；不能用“absolute zero-leakage”笼统覆盖所有结果。

可用的审慎局限段（须在重跑修复实验后代入结果）：

> This study evaluated mental arithmetic versus rest on one public EEG–fNIRS cohort of 29 participants. Subject-held-out evaluation addresses a different generalization question from within-subject evaluation, so accuracies from these protocols are not directly comparable. The present findings do not establish generalization to motor imagery, clinical populations, other recording systems, or microcontroller deployment. The temporal perturbation results are consistent with model-dependent use of temporal structure; establishing physiological directionality requires matched controls that isolate the delay prior from other processing components.

## 8. 修复顺序与复核标准

1. **先修输入**：真实通道mapping、fNIRS OD/MBLL单位和顺序、采样时间轴；数据快照、哈希、每fold划分锁定。
2. **锁定真实方法**：决定保留完整代码模型还是改为正文所述模型；公开直接读出、包络、导数、重建target；固定/可学习tau分别定义。
3. **修消融与验证**：单因素对照，独立验证集模型选择，test一次性锁定；删除拉向5.18的正则后才能检验自主学习。保存逐试次预测、fold指标和checkpoint。
4. **重跑统计与图表**：统一SD/CI/test/BH家族；重算MacroF1；所有图表从同一版本预测自动生成；phase roll及compensation保存fold结果，并检验模型间effect差异。
5. **文献修复**：更正已确认条目，隔离疑似拼接Keles文献，完成未验证条目；加入真正相关2022–2025融合/MI文献的实质对话。
6. **重新测工程**：同一模型/输入的参数、MACs、CPU/GPU延迟、P99及目标平台测试；删除无法复算的streaming数字。
7. **最后改论断与编译PDF**：正文/摘要/表/图四方自动对齐；逐页核验，避免通过扩大措辞让证据“看起来满足要求”。

通过标准：每个核心数字能追到同一run的逐fold/逐trial结果；每条方法能追到实际执行代码；每个消融只改变声称的因素；每个硬件指标有原始协议与样本；每条文献有可核对原始来源。当前结果尚不满足这些标准。

## 9. 本次可复查证据与限制

- `reports/manuscript_CBM_audit_evidence_20261013.json`：统计复算、当前参数量、前向维度、MAC分项、mask边界、Bib结构及Crossref逐项成功/失败。
- `reports/manuscript_CBM_input_audit_20261013.json`：全29人形状、类计数和重复通道位置；Sub-01原始NIRS采样率、单位与波长。
- `tmp/pdfs/audit_checks.py`：本次只读验证脚本（写入证据文件）；运行使用当前代码，不重新训练。

PDF已提取全文并目视检查公式/架构/表格/图2–7及Discussion/References页面。参考文献存在限流和题名候选歧义，未把未验证条目标为真实；没有完整的phase-roll comparative fold输出、原始latency样本或主实验逐trial预测，相关结论明确标为未验证。原始数据详细montage只抽查Sub-01，但已对全部29人的保存输入验证18个重复通道；此错误的跨被试普遍性已直接证实。
