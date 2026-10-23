# IEEE TBME 投稿文件包清单与投稿风险自查对照表

**目标期刊：** *IEEE Transactions on Biomedical Engineering* (TBME)  
**稿件类型：** Regular Paper（双栏排版，严格 8 页满版预算，无超页费）  
**论文标题：** Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces  
**通讯作者：** 段芳（Fang Duan, nkfetsh@gmail.com）  
**第一作者：** 陈宏杰（Hongjie Chen, chenhj976@gmail.com）  
**作者单位：** 华侨大学信息科学与工程学院（College of Information Science and Engineering, Huaqiao University）  
**开源代码库：** https://github.com/ujujuj3061831150/nvc-delayformer-bci  

---

## 一、投稿文件资产索引

1. **主手稿 PDF**：`reports/manuscript_IEEEtran_submission.pdf`（与 `manuscript/main.pdf`、`reports/manuscript_submission.pdf` 保持完全一致的 SHA-256 校验和）
   - 源工程：`manuscript/main.tex`、`manuscript/references.bib`、`manuscript/figures/`
2. **投稿信（Cover Letter）**：`reports/Cover_Letter.md`
   - 致 IEEE TBME 主编，涵盖背景意义、核心贡献、伦理声明、无利益冲突、8 页预算保证及开源数据/代码声明。
3. **论文亮点（Highlights）**：`reports/Highlights.md` 与 `reports/Highlights.txt`
   - 包含 5 条核心量化贡献，单条字符严格控制在期刊要求范围内。
4. **DOI 归档包与可重现资产**：`releases/NVC-DelayFormer_DOI_Archive_20261021.zip` 及 `.zip.sha256`
   - 包含完整的模型源码、测试套件、微型权重和跨平台复现脚本。
5. **核心实验验证记录（JSON）**：
   - 逐试次锁死预测记录：`reports/real_29sub_locked_predictions.json`
   - 主基准与消融实验汇总：`reports/real_29sub_benchmark_and_ablation_summary.json`
   - 多随机种子汇总：`reports/multiseed_grand_benchmark_summary.json`
   - 在线流式对齐评测（CrEA）：`reports/crea_streaming_evaluation_results.json`
   - 外部任务（Shin 2018 工作记忆）：`reports/phase6_external_dataset_shin2018_nback_results.json`
   - 外部任务（Shin 2017 运动想象）：`reports/phase6_external_dataset_shin2017_mi_results.json`
   - 工程参数与 GPU 延迟基准：`reports/engineering_benchmarks_round3.json`
   - 窗口截断敏度测试：`reports/window_sweep_round3.json`

---

## 二、投稿四大核心自查对照表（审稿人免卡自查）

### 核心一：研究缺口真实性（对比近年顶刊/顶会找真实空白）
- [x] **前人成果梳理透彻**：系统回顾了从经典特征拼接（Fazli 2012, Buccino 2016）、协方差对齐（He 2020）到现代深度学习（EEGNet 2018, ATCNet 2023, Conformer 2022, fNIRSNet 2024, FGANet 2022, EFMLNet 2025, MBC-ATT 2025）的发展脉络。
- [x] **现存真实缺陷定位精准**：指出多模态时间尺度失配（毫秒级电生理 vs. 多秒级神经血管耦合）在零校准留一跨受试者（LOSO）场景下的致命痛点——无约束交叉注意力允许反因果对齐（$\delta_{ij} < 0$，血流超前于神经冲动），诱发跨人泛化过拟合。
- [x] **本文具体解决点明确**：提出生理时延先验高斯核（$\tau_h \in [3.5, 6.5]$\,s）与物理因果时序硬遮罩（$t_{\mathrm{nirs}} \ge t_{\mathrm{eeg}}$），从生物力学本质约束注意力搜索空间。

### 核心二：核心结果多条件充分验证（经得起变动与质疑）
- [x] **严格跨受试者划分**：29 折独立 LOSO 交叉验证，每折严格划分 23 人训练、5 人选模、1 人盲测，杜绝数据泄露。
- [x] **多随机种子复现性**：跨 Seed 42, 100, 2024 达到 78.22% ± 1.00% 极小批间波动，主种子 79.37% ± 7.73%。
- [x] **因子分解全面**：$2 \times 2$ 全因子分解分离连续时延先验（+4.31 pp）与因果遮罩（+0.63 pp）边际增益，双先验协同带来 +4.94 pp 纯净提升。
- [x] **扰动压力测试**：通过类内/跨类置换、循环时移（5.0s）及因果低通滤波，确证模型强依赖于高频振荡成分（$\theta, \alpha, \beta$）且对相位抖动具有弹性。
- [x] **跨范式泛化支撑**：在涵盖工作记忆（26人，1,872试次）和运动想象（29人，1,740试次）共 3,612 独立外部试次上，全模型与时延流分别取得 73.24%/73.61% 和 66.32%/66.09% 准确率。

### 核心三：前置自查解释所有疑点（坦诚、严谨、不隐瞒）
- [x] **时延扫描平台期疑点**：针对扫描在 8.0s 仍处于高位平台期（80.46%）的现象，主动解释：冲激 HRF 峰值在 3.5~6.5s，但由于任务采用持续 10.0s 认知块设计，冲激响应与方波信号连续卷积必然产生延长的微血管高充血平台。
- [x] **外部模型优势坦白说明**：在运动想象任务上，明确说明并报告 FGANet 在该任务取得 70.40%（较本文高 4.08 pp），指出两模型在共享编码器前提下注意力融合策略的差异，不隐匿、不防御。
- [x] **全遮罩极端边界防御**：对首行或所有 Key 均处于未来的极端边缘情况，因果注意力层严格输出零权重（$0.0$）并利用后置残差与层归一化保障数值稳定，杜绝 NaN 扩散。
- [x] **流式与离线性能折损透明公开**：在线流式评测使用 CrEA 递推对齐，在完全无未来会话统计量的前提下取得 71.21% ± 11.44%，恢复离线批对齐（75.06%）的 94.9% 水平，客观报告试次递推收敛曲线。

### 核心四：明确阐述实际工程与临床增量（拒绝空喊意义）
- [x] **极简边缘计算负担**：参数量仅 63,932 个（较 ATCNet 少 1.8 倍，较 Conformer 少 17.5 倍），单步运算 24.79 M MACs。
- [x] **实时闭环延迟保证**：笔记本端消费级 GPU 测得中位数推理延迟 2.22 ms，P99 延迟 4.48 ms，吞吐量达 1,691 trials/s，远低于人类感知及 100Hz 采样周期（10 ms）。
- [x] **床旁即插即用落地路径**：在线 CrEA 在 5~8 个试次内将协方差相对误差从 45.15% 快速收敛至 29.38%（稳态 3.60%），摆脱传统欧氏对齐对整段会话转导统计的依赖。
