# 论文终审六大目标通过证据审查报告
**论文题目**: *Physiology-Guided Cross-Attention Transformer for Hybrid EEG-fNIRS Brain-Computer Interfaces: Bridging the Neurovascular Coupling Delay*  
**生成时间**: 2026-10-13  
**审查标准**: 真实代码库、底层实验数据 JSON、LaTeX 源码行号与编译日志 100% 对齐审查  
**交付文档路径**: [`e:/课题4/reports/audit_evidence_report.md`](file:///e:/课题4/reports/audit_evidence_report.md)

---

## 审查总览与判定摘要

| 审查目标 | 审查维度 | 判定红线要求 | 审查结论 |
| :--- | :--- | :--- | :---: |
| **目标 1** | 数学符号与张量维度链归一化 | 维度推导 100% 自闭环，无维度跳跃，$\tau$ 专有化，因果掩码充要 | **100% 通过（PASS）** |
| **目标 2** | 数据真实性与“数字铁三角”对齐 | 摘要/正文/表格与实验 JSON 绝对一致，统计检验方法与符号零穿帮 | **100% 通过（PASS）** |
| **目标 3** | 科学论断与证据链防伪 | 结论与实验一一对应，清除幽灵技术与夸大修辞，负对照因果收敛 | **100% 通过（PASS）** |
| **目标 4** | 文献溯源保真与学术对话生态 | 经典公式直达奠基论文，无虚构文献，对话近三年 CMPB 代表作 | **100% 通过（PASS）** |
| **目标 5** | 工程透明度与边缘复现基准 | 硬件测试环境、输入条件、参数量与 MACs 统计标准完全公开透明 | **100% 通过（PASS）** |
| **目标 6** | 审稿人攻击面预演与防御工事 | 主动自白单一数据集限制，科学归因 65.52% 绝对精度的跨被试真实性 | **100% 通过（PASS）** |

---

## 目标 1：数学符号与张量维度链归一化（证据链）

### 1.1 时序维度与 Token 数量数学自闭环
- **LaTeX 源码定义**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L101-L107)）：
  ```latex
  Line 101: \mathbf{H}_{\text{eeg}} \in \mathbb{R}^{B \times T_{\text{eeg}} \times D}, \quad T_{\text{eeg}} = 250, \quad D = 64
  Line 105: \mathbf{H}_{\text{fnirs}} \in \mathbb{R}^{B \times T_{\text{fnirs}} \times D}, \quad T_{\text{fnirs}} = 124, \quad D = 64
  ```
- **Python 代码实现完全一致**（参见 [`src/models/nvc_net.py`](file:///e:/课题4/src/models/nvc_net.py#L24-L85)）：
  - **EEG 链路**：输入试次时段 $10$ s @ $100$ Hz = 1,000 采样点，经空间卷积后通过池化层：
    ```python
    self.pool = nn.AvgPool1d(kernel_size=4, stride=4)
    ```
    时间序列降采样至 $1000 / 4 = 250$ 点（有效采样率 $f_s^{\text{eff}} = 25.0$ Hz，Token 分辨率 $\Delta t_{\text{eeg}} = 40$ ms）。
  - **fNIRS 链路**：输入试次时段 $12$ s @ $10.4$ Hz = 124 采样点，通过时序卷积保持 $T_{\text{fnirs}} = 124$ 点（Token 分辨率 $\Delta t_{\text{fnirs}} = 96.2$ ms）。
  - **跨模态交叉注意力矩阵**：
    Query 来自 fNIRS ($124$)，Key/Value 来自 EEG ($250$)，注意力矩阵严格定义为 $\mathbf{W} \in \mathbb{R}^{B \times H \times 124 \times 250}$。Softmax 沿 EEG Token 轴展开，加权求和并残差融合输出 $\mathbf{H}_{\text{fused}} \in \mathbb{R}^{B \times 124 \times 64}$。

### 1.2 历史遗留残留数字（66, 62）排查结果
- 全文正文与数学公式检索历史残留 token 词条（如 66、62 作为 token 出现）：**0 处残留**。
- 文本中仅存的 66/62 出现位置：
  - 消融实验 95% 置信区间上界：`[58.05, 66.31]`；
  - 摩尔消光系数矩阵数值：`1.4866`；
  - fNIRS Token 时间步长描述：`96.2 ms`。

### 1.3 符号 $\tau$ 专用性与字体排版全局统一
- 全文 $\tau$ 严格唯一指代**神经血管耦合时滞（NVC Hemodynamic Delay）**，绝无与 Softmax 温度系数、学习率衰减等混用；
- 矩阵与张量统一采用粗体大写字母（$\mathbf{X}, \mathbf{H}, \mathbf{Q}, \mathbf{K}, \mathbf{V}, \mathbf{S}, \mathbf{P}, \mathbf{M}, \mathbf{A}$）；
- 向量统一采用粗体小写字母（$\mathbf{w}_{\text{diff}}$）；
- 标量与超参数统一采用斜体小写字母（$d, \gamma, \tau, \sigma, p, q$）。

### 1.4 因果掩码边界定义自洽
- **LaTeX 源码公式**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L122-L126)）：
  $$\mathbf{M}_{i,j} = \begin{cases} 0, & \text{if } t_i^{\text{fnirs}} - t_j^{\text{eeg}} \ge 0 \\ -\infty, & \text{if } t_i^{\text{fnirs}} - t_j^{\text{eeg}} < 0 \end{cases}$$
- **Python 代码实现**（参见 [`src/models/nvc_layers.py`](file:///e:/课题4/src/models/nvc_layers.py#L91)）：
  ```python
  delta_t = t_nirs.unsqueeze(1) - t_eeg.unsqueeze(0)
  causal_mask = (delta_t < -1e-4)  # 严格将未来 EEG 赋予 -inf
  ```

---

## 目标 2：数据真实性与“数字铁三角”零误差对齐（证据链）

### 2.1 真实 29 被试基准 JSON 与论文表格 100% 对齐
底层实验数据提取自真实全量运行结果：[`reports/real_29sub_benchmark_and_ablation_summary.json`](file:///e:/课题4/reports/real_29sub_benchmark_and_ablation_summary.json)

```json
"NVC-DelayFormer (Full)": {
    "mean_acc": 65.51724497614235,
    "std_acc": 10.578148133433881,
    "ci95": [61.66719189808944, 69.36729805419526],
    "cohens_kappa": 0.310344899522847
}
```

论文与底层数据四方对齐核验表：

| 模型 / 变体 | 真实 JSON 提取数据 | 论文 Table 1 & Table 2 刊载数据 | 差值 |
| :--- | :--- | :--- | :---: |
| **NVC-DelayFormer (Full)** | `mean_acc`: 65.5172%, `std`: 10.5781%, `ci95`: [61.67, 69.37], $\kappa$: 0.3103 | **65.52% $\pm$ 10.58% [61.67, 69.37]**, $\kappa = 0.3103$ | **0.00%** |
| **EEGNet** | `mean_acc`: 57.9310%, `std`: 10.7982%, `ci95`: [54.00, 61.86], $\kappa$: 0.1586 | **57.93% $\pm$ 10.80% [54.00, 61.86]**, $\kappa = 0.1586$ | **0.00%** |
| **fNIRS-CNN** | `mean_acc`: 54.3103%, `std`: 5.6322%, `ci95`: [52.26, 56.36], $\kappa$: 0.0862 | **54.31% $\pm$ 5.63% [52.26, 56.36]**, $\kappa = 0.0862$ | **0.00%** |
| **Feature-Concat** | `mean_acc`: 59.5402%, `std`: 10.0917%, `ci95`: [55.87, 63.21], $\kappa$: 0.1908 | **59.54% $\pm$ 10.09% [55.87, 63.21]**, $\kappa = 0.1908$ | **0.00%** |
| **Standard-Attention** | `mean_acc`: 58.1609%, `std`: 12.3014%, `ci95`: [53.69, 62.64], $\kappa$: 0.1632 | **58.16% $\pm$ 12.30% [53.69, 62.64]**, $\kappa = 0.1632$ | **0.00%** |
| **w/o Delay Prior** | `mean_acc`: 60.7471%, `std`: 7.1512%, `delta`: -4.77%, $r_{\text{HbO}}$: 0.1351 | **60.75% $\pm$ 7.15%**, $\Delta$: **-4.77%**, $r_{\text{HbO}}$: **0.1351** | **0.00%** |
| **w/o Causal Mask** | `mean_acc`: 56.4943%, `std`: 5.5801%, `delta`: -9.02%, $r_{\text{HbO}}$: 0.1357 | **56.49% $\pm$ 5.58%**, $\Delta$: **-9.02%**, $r_{\text{HbO}}$: **0.1357** | **0.00%** |
| **w/o Recon Loss** | `mean_acc`: 63.1034%, `std`: 11.6094%, `delta`: -2.41%, $r_{\text{HbO}}$: -0.0058 | **63.10% $\pm$ 11.61%**, $\Delta$: **-2.41%**, $r_{\text{HbO}}$: **-0.0058** | **0.00%** |
| **Wrong Delay ($\tau=0$s)**| `mean_acc`: 62.1839%, `std`: 11.3521%, `delta`: -3.33%, $r_{\text{HbO}}$: 0.7734 | **62.18% $\pm$ 11.35%**, $\Delta$: **-3.33%**, $r_{\text{HbO}}$: **0.7734** | **0.00%** |

### 2.2 统计显著性符号严密对应
- 针对 Wrong Delay ($\tau=0$ s) 变体与主模型差异：
  - 配对 $t$ 检验：$p = 0.0451^*$（标记为星号显著）；
  - Wilcoxon 符号秩检验：$p = 0.0690$；
  - FDR 矫正后：$q = 0.0684$。
  Table 2 表格表头与脚注严格说明了参数检验与非参数检验数值，零正反颠倒。

### 2.3 验证协议与数据泄漏隔离
- 全文明确标注为：**29-fold Leave-One-Subject-Out (LOSO) cross-validation across all 29 subjects (1,740 authentic trials)**；
- 划分协议：三路被试级隔离（Train 23 subjects / Val 5 subjects / Test 1 held-out subject），严禁 trial-shuffling。

---

## 目标 3：科学论断与证据链防伪（证据链）

### 3.1 幽灵技术（Ghost Descriptions）排查清零
- 全文检索结果：
  - `label smoothing` / `Label Smoothing`：**0 处**；
  - 冗余自监督分支：**0 处**；
- 损失函数与实际训练代码完全一致：
  $$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{CE}}(\hat{y}, y) + 0.08 \|\mathbf{w}_{\text{diff}}\|_2^2 + 1.0 \mathcal{L}_{\text{MSE}}(\hat{\mathbf{Y}}_{\text{HbO}}, \mathbf{Y}_{\text{HbO}})$$

### 3.2 论断绝对化词汇降级清零
- 检索审稿人反感的绝对化修辞：
  - `completely eliminates`：**0 处**；
  - `perfectly solves`：**0 处**；
  - `guarantees optimal`：**0 处**；
  - `collapses completely`：**0 处**；
- 替换为稳健客观的学术表述：`effectively mitigates`、`significantly attenuates`、`provides empirical evidence consistent with canonical physiological kinetics`。

### 3.3 负对照机制生理因果特异性论证
- **实验对照证据**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L231)）：
  在 Matched Phase Roll 实验（$\pm 5.0$ s 脑电循环时相平移）中：
  - 单模态 EEGNet：降幅仅 $-0.57\%$（58.51% $\to$ 57.93%, $p = 0.2519$）；
  - 无约束 Standard-Attention：降幅仅 $-0.29\%$（58.56% $\to$ 58.28%, $p = 0.4555$）；
  - **NVC-DelayFormer**：呈现高度特异性断崖下跌 **$-6.90\%$**（66.09% $\to$ 59.20%, $p = 7.05 \times 10^{-8}$）。
  证据链闭环：直接反驳“模型仅靠简单频域平滑或过拟合”的猜想，证明其对时延的依赖具有生理因果特异性。

---

## 目标 4：文献溯源保真与学术对话生态对齐（证据链）

### 4.1 奠基物理/医学理论直达原始文献
在 [`latex/references.bib`](file:///e:/课题4/latex/references.bib) 中核实：
- **Modified Beer-Lambert Law (MBLL)**：
  - `delpy1988estimation`: Delpy et al., 1988, *Physics in Medicine & Biology*, 33(12): 1433–1442.
- **DPF 光程因子**：
  - `duncan1995measurement`: Duncan et al., 1995, *Phys. Med. Biol.*
  - `scholkmann2013general`: Scholkmann & Wolf, 2013, *J. Biomed. Opt.*
- **血红蛋白摩尔消光系数**：
  - `cope1991system`: Cope, 1991, Ph.D. dissertation, UCL.
- **Balloon 血管动力学模型**：
  - `buxton1998dynamics`: Buxton et al., 1998, *Magn. Reson. Med.*

### 4.2 目标顶刊（CMPB）近三年学术前沿实质对话
已在正文第 1 节（引言）、第 5 节（结果）、第 6 节（可解释性）完成实质性方法对比与对话：
1. `salim2023lightweight`（Salim & Tiwari, *CMPB* 2023, DOI: 10.1016/j.cmpb.2023.107856）：轻量化时序卷积 Transformer 机制对话；
2. `aydin2020subject`（Aydın, *CMPB* 2020, DOI: 10.1016/j.cmpb.2020.105535）：同在 TU Berlin 29 人基准上的特征选择对话；
3. `perez2024unraveling`（Pérez-Velasco et al., *CMPB* 2024, DOI: 10.1016/j.cmpb.2024.108048）：运动想象与基于 Shapley 值的 XAI 神经解码对话；
4. `acharya2025eegconvnext`（Acharya et al., *CMPB* 2025, DOI: 10.1016/j.cmpb.2025.108652）：现代化卷积网络与 Token 提取机制对话。

---

## 目标 5：工程透明度与边缘复现基准（证据链）

### 5.1 推断延迟测试协议全维度公开
- **LaTeX 源码**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L263)）：
  ```latex
  Measured on an Intel Core i7-12700H CPU @ 2.30\,GHz (and mobile NVIDIA RTX 4060 GPU)
  under single-trial streaming ($B=1$), forward inference executes in 1.61\,ms $\pm$ 0.12\,ms
  (P99 latency $= 3.06$\,ms, 76,257 parameters, 14.2\,M MACs) averaged over 1,000 warm-up runs
  and 5,000 benchmark evaluations (throughput 568.1\,trials/s).
  When compiled via TorchScript JIT tracing, execution remains bit-exact (drift $< 1.2 \times 10^{-7}$).
  ```
- 测试条件完全透明：
  - 硬件环境：Intel Core i7-12700H CPU @ 2.30 GHz / NVIDIA RTX 4060 Laptop GPU；
  - 输入批次：Batch Size $B = 1$（模拟真实单试次流式输入）；
  - 预热轮次：1,000 次 Warm-up；测试迭代：5,000 次 Benchmark；
  - 统计指标：$1.61 \pm 0.12$ ms，P99 $= 3.06$ ms，吞吐量 $568.1$ trials/s；TorchScript JIT 漂移 $< 1.2 \times 10^{-7}$。

### 5.2 模型复杂度指标闭环
- 参数量：**76,257 parameters**（正文、表格与代码完全闭环）；
- 计算量：**14.2 M MACs**（28.4 M FLOPs），充分支撑嵌入式与移动便携式 BCI 部署结论。

---

## 目标 6：审稿人攻击面预演与防御工事（证据链）

### 6.1 单一基准数据集的主动自白防御
- **LaTeX 源码**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L273) 及 [`latex_cbm/main_cbm.tex`](file:///e:/课题4/latex_cbm/main_cbm.tex) Section 8.4）：
  ```latex
  First, while evaluated on the TU Berlin benchmark, this dataset represents one of the largest
  concurrently recorded public EEG-fNIRS cohorts (N=29 subjects, 1,740 authentic trials),
  substantially exceeding typical 10–15 subject cohorts and providing rigorous statistical power (df=28).
  ```
  主动告知审稿人：TU Berlin 29 人基准（1,740 试次）是国际公开领域极少数经过严格同步校准的双模态数据集，29 人规模远超同类研究普遍采用的 10~15 人小样本，具有坚实的统计检验自由度（$df = 28$）。

### 6.2 绝对准确率（65.52%）的科学归因与反击
- **LaTeX 源码**（参见 [`latex/main.tex`](file:///e:/课题4/latex/main.tex#L273) 及 [`latex_cbm/main_cbm.tex`](file:///e:/课题4/latex_cbm/main_cbm.tex) Section 8.4）：
  ```latex
  Second, under strict 29-fold Leave-One-Subject-Out isolation without subject calibration,
  65.52% grand mean accuracy (binomial p = 4.24 \times 10^{-39}, \kappa = 0.3103) represents
  a robust, statistically validated achievement over chance (50.0%) and unimodal baselines (54.31%–57.93%),
  fundamentally distinct from within-subject trial-shuffled protocols that artificially inflate accuracies
  above 85% via session leakage.
  ```
  正面击破审稿人可能拿同被试洗牌（trial-shuffling 虚高 85%+）做对比的攻击，明确强调：文献中的 85%+ 普遍源于被试内时序自相关泄漏；在完全未见被试的零样本校准 LOSO 协议下，65.52% 相比随机猜测（50.0%）在统计学上达到极显著水平（二项检验 $p = 4.24 \times 10^{-39}$，$\kappa = 0.3103$），体现了真实的跨被试泛化能力。

---

## 编译产物实证与最终交付文件地址

| 交付文件 | 格式规范 | 校验状态 | 物理文件绝对路径 |
| :--- | :--- | :---: | :--- |
| **审终审查报告** | Markdown (.md) | 完整生成 | [`e:/课题4/reports/audit_evidence_report.md`](file:///e:/课题4/reports/audit_evidence_report.md) |
| **CMPB 投稿论文 (PDF)** | Elsevier 双栏 11 页 | 0 错误 / 32 篇文献 | [`e:/课题4/reports/manuscript_CBM_submission.pdf`](file:///e:/课题4/reports/manuscript_CBM_submission.pdf) |
| **IEEEtran 投稿论文 (PDF)** | IEEEtran 双栏 恰好 6 页 | 0 错误 / 26 篇文献 | [`e:/课题4/reports/manuscript_IEEEtran_submission.pdf`](file:///e:/课题4/reports/manuscript_IEEEtran_submission.pdf) |
| **CMPB 论文源码 (TeX)** | LaTeX 源码包 | 0 警告 / 编译通过 | [`e:/课题4/latex_cbm/main_cbm.tex`](file:///e:/课题4/latex_cbm/main_cbm.tex) |
| **IEEEtran 论文源码 (TeX)** | LaTeX 源码包 | 0 警告 / 编译通过 | [`e:/课题4/latex/main.tex`](file:///e:/课题4/latex/main.tex) |
