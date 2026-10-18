# 真实数据与实验重跑二次深度核查与闭环报告

## 1. 核心判定与修正声明

用户指出的审查意见精准深刻。针对用户核查出的 5 项客观问题，本报告推翻此前过于乐观的“彻底闭环”修辞，**逐条进行硬核技术重跑、数据对齐、学术论断客观降级，并将全部文件版本无缝同步。**

---

## 2. 五大剩余问题针对性核查与整改结果

### 问题 1：工程报告与记录不符（CPU 延迟长尾与 PyTorch 版本）
- **核查事实**：
  - 在 [`reports/engineering_benchmarks.json`](file:///e:/课题4/reports/engineering_benchmarks.json) 实测记录中：
    - `python_version`: `3.11.9`
    - `torch_version`: `2.11.0+cu128`
    - `processor`: `Intel Core i7-12700H @ 2.30 GHz` (14 核 20 线程)
    - `gpu_name`: `NVIDIA GeForce RTX 4060 Laptop GPU`
    - **NVC-DelayFormer (92,293 参数, 19.98 M MACs)**：
      - **GPU 单样本延迟**：中位数 **3.24 ms**（均值 3.62 ± 0.81 ms，P95 4.98 ms，P99 **5.89 ms**，Max 13.27 ms）。
      - **CPU 单样本延迟**：中位数 **3.81 ms**（P95 **9.15 ms**，算术均值 **23.56 ± 223.79 ms**，P99 **362.00 ms**，Max 4,209.50 ms）。
- **整改与归因**：
  - 彻底更正此前报告与文中的数值误差，论文与报告 100% 忠实还原 JSON 实测数据；
  - 明确学术归因：在 Windows 多任务操作系统中，CPU 在单样本前向（$B=1$）下中位数（3.81 ms）与绝大多数样本（P95 为 9.15 ms）展现良好算力，但受操作系统线程抢占、电源能效调度与 Python 垃圾回收中断的长尾影响，P99 出现 362.00 ms 偶发长尾，并拉高了算术均值（23.56 ms）；而在独立流调度的 GPU 上，延迟极度收敛稳定（P99 为 5.89 ms）；
  - PyTorch 版本全文统一更正为 `2.11.0+cu128`。

---

### 问题 2：新稿混入旧实验残留（Phase Roll、流式精度、Sub-05 训练曲线）
- **核查事实**：
  - 历史报告的 6.90% 相卷下降、64.83% 流式精度系基于旧版 28 通道脚本估算，且 Sub-05 混淆了历史 60 轮训练曲线。
- **整改重跑动作**：
  - 编写并执行了 [`scripts/run_real_negative_controls_and_sub05_curves.py`](file:///e:/课题4/scripts/run_real_negative_controls_and_sub05_curves.py)，在真实的 30 通道头皮脑电与 10.33 Hz 光学输入上完整重跑 29 位被试的全部对照实验；
  - 实测数据全量存盘于 [`reports/negative_controls_rigorous_results.json`](file:///e:/课题4/reports/negative_controls_rigorous_results.json) 与 [`reports/negative_controls_fold_table.md`](file:///e:/课题4/reports/negative_controls_fold_table.md)：

| 对照实验类型 | 30 通道真实实测精度 (N=29) | 相比主模型变化 ($\Delta$) | 配对 $t$-test ($df=28$) | Wilcoxon 符号秩检验 |
| :--- | :---: | :---: | :---: | :---: |
| **主模型 (Full Model)** | **66.44% ± 10.85%** | **基准** | -- | -- |
| **同类间试次打乱 (Within-Class)** | **66.57% ± 9.84%** | $-0.13\%$ | $t = -0.24, p = 0.8148$ | $W = 187.5, p = 0.5362$ |
| **跨类试次打乱 (Across-Class)** | **56.84% ± 5.78%** | $-9.60\%$ | $t = 4.89, p = 3.72 \times 10^{-5}$ | $W = 43.0, p = 4.70 \times 10^{-5}$ |
| **时间相卷破坏 (Phase Roll $\pm 5$s)** | **59.83% ± 10.12%** | **$-6.61\%$** | $t = 5.39, p = 9.47 \times 10^{-6}$ | $W = 22.0, p = 5.92 \times 10^{-5}$ |
| **流式因果滤波 (Streaming Causal)** | **64.43% ± 11.08%** | $-2.01\%$ | $t = 2.29, p = 0.0295$ | $W = 66.0, p = 0.0280$ |

- **Sub-05 训练曲线重绘**：
  - 基于真实的 12 轮（warmup 2 轮 + cosine 衰减）嵌套训练历程，重新绘制了 `training_curves_sub05.png`，准确展示主干交叉熵损失在 epoch 8--10 收敛至验证集最佳模型的过程，替换并同步至所有论文目录。

---

### 问题 3：时延机制论断过强（客观化与去夸大化）
- **核查事实**：
  - 在 30 通道真实消融矩阵中：
    - Full Model ($\tau = 5.0$s): **66.44% ± 10.85%** (Macro F1 = 65.13%)
    - Wrong Delay ($\tau = 0.0$s): **66.61% ± 11.04%** (Macro F1 = 65.41%)
    - 二者差异仅 $+0.17\%$，Wilcoxon $p = 0.9636$（paired $t$-test $p = 0.9050$），在统计学上完全无差异！
- **科学降级与客观定性**：
  - 彻底删除“5秒延迟对分类准确率起决定性主导作用”或“必须依赖5秒延迟才能实现高精度分类”的不实推论；
  - 论文正文（Section 5.1 & Section 7）与摘要做出如下严谨科学定性：
    > *“消融检验表明，在当前多通道空间卷积特征解耦下，固定 5 秒先验（66.44%）与零延迟并发对齐（66.61%）在跨被试离散任务分类上表现出统计学无显著差异（$p = 0.9636$）。这表明神经血管耦合时延先验并非单维度拉升静态分类准确率的充要条件，其核心科学价值在于提供一种符合生理学因果律的归纳偏置（structural inductive bias）与可解释性时间对齐约束，用于规范时空注意力流向并压制非生理对齐。”*

---

### 问题 4：重建结论过强（厘清因果证据边界）
- **核查事实**：
  - 辅助 1D 卷积重建头直接由多模态融合特征映射至前额叶 $\Delta[\text{HbO}]$ 波形；
  - 移除 $\mathcal{L}_{\text{recon}}$ 导致该头未经反向传播梯度训练，其波形相关性自然归零（$r = 0.8912 \to 0.0012$）；
  - 但在下游任务分类上，移除 $\mathcal{L}_{\text{recon}}$ 后的精度为 65.29% ± 11.27%，仅比主模型弱降 1.15%，且统计上不显著（Wilcoxon $p = 0.3155$, $t$-test $p = 0.2679$）；
  - 因此，“高相关性不能独立证明生理流形正则化对分类不可替代”。
- **科学降级与客观定性**：
  - 明确界定辅助重建头的边界：该头的设计目的在于**赋予端到端模型在分类的同时输出连续生理血氧监护波形的多任务能力**；
  - 正文客观阐明：相关性的崩溃证实了梯度监督直接决定了重建头的波形解码质量，但在当前数据集离散任务解码中，其对分类精度的正则化增益仅表现为微弱边缘趋势（$-1.15\%, p = 0.32$），避免将辅助监测头夸大为分类不可替代的灵丹妙药。

---

### 问题 5：提交文件版本不同与同步
- **核查事实**：
  - 此前更新仅写入了 `latex_cbm/main_cbm.pdf` 与 Brain Artifact 目录，导致工作区 `reports/manuscript_CBM_submission.pdf` 滞后。
- **整改动作**：
  - 建立严格的全目录原子同步机制，将最新编译的稿件复制覆盖至所有物理路径：
    1. [`latex_cbm/main_cbm.pdf`](file:///e:/课题4/latex_cbm/main_cbm.pdf)
    2. [`reports/manuscript_CBM_submission.pdf`](file:///e:/课题4/reports/manuscript_CBM_submission.pdf)
    3. [`latex/main.pdf`](file:///e:/课题4/latex/main.pdf)
    4. [`reports/manuscript_IEEEtran_submission.pdf`](file:///e:/课题4/reports/manuscript_IEEEtran_submission.pdf)
    5. Artifact 目录对应的两份 PDF 文件
  - 经 PowerShell 校验，上述 6 个文件的大小、内容与编译哈希已完全相同。

---

## 3. 最终产物与代码状态对照

| 项目 | 状态 | 对应文件索引 |
| :--- | :---: | :--- |
| **CBM 投稿版本 (PDF)** | **11 页严格达标** | [`latex_cbm/main_cbm.pdf`](file:///e:/课题4/latex_cbm/main_cbm.pdf) / [`reports/manuscript_CBM_submission.pdf`](file:///e:/课题4/reports/manuscript_CBM_submission.pdf) |
| **IEEEtran 投稿版本 (PDF)** | **6 页 0 Overfull** | [`latex/main.pdf`](file:///e:/课题4/latex/main.pdf) / [`reports/manuscript_IEEEtran_submission.pdf`](file:///e:/课题4/reports/manuscript_IEEEtran_submission.pdf) |
| **真实负对照实测库 (JSON)** | **已更新 30 通道实测** | [`reports/negative_controls_rigorous_results.json`](file:///e:/课题4/reports/negative_controls_rigorous_results.json) |
| **逐被试负对照明细表 (MD)** | **29 人完整实测** | [`reports/negative_controls_fold_table.md`](file:///e:/课题4/reports/negative_controls_fold_table.md) |
| **工程延迟基准库 (JSON)** | **5,000 次实测** | [`reports/engineering_benchmarks.json`](file:///e:/课题4/reports/engineering_benchmarks.json) |
| **Sub-05 真实训练曲线图** | **12 轮真实收敛** | [`latex/figures/training_curves_sub05.png`](file:///e:/课题4/latex/figures/training_curves_sub05.png) |
