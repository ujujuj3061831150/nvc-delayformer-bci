# Journal of Neural Engineering (JNE) 投稿文件包清单与投稿风险自查对照表

**目标期刊：** *Journal of Neural Engineering* (JNE), IOP Publishing  
**主编信息：** Prof. Warren M. Grill (Duke University, USA)  
**稿件类型：** Research Paper（Format-Free Initial Submission 初审自由格式）  
**论文标题：** Physiology-Guided Temporal Fusion for Cross-Subject EEG–fNIRS Brain–Computer Interfaces  
**通讯作者：** 段芳（Fang Duan, `nkfetsh@gmail.com`）  
**第一作者：** 陈宏杰（Hongjie Chen, `chenhj976@gmail.com`）  
**作者单位：** 华侨大学信息科学与工程学院（College of Information Science and Engineering, Huaqiao University）  
**开源代码库：** https://github.com/ujujuj3061831150/nvc-delayformer-bci  

---

## 一、 投稿系统直接上传核心文件资产

1. **主手稿 PDF**：`manuscript/main.pdf`（或 `reports/manuscript.pdf`，严格 8.0 页双栏）
   - 页眉：`JOURNAL OF NEURAL ENGINEERING, UNDER REVIEW, 2026`
   - File Type in Portal: **Main Document**
2. **补充材料 PDF**：`reports/Supplementary_Material.pdf`（4.0 页双栏）
   - 页眉：`JOURNAL OF NEURAL ENGINEERING, UNDER REVIEW, 2026`
   - 包含：Section S.I--S.IV 以及 **Section S.V & Table S3 (Buccino et al. 2016 独立外部数据集 15 折 LOSO 评测表，81.03%)**
   - File Type in Portal: **Supplementary File**
3. **投稿信 PDF**：`reports/Cover_Letter.pdf`（严格 1.0 页）
   - 致 JNE 主编 Prof. Warren M. Grill，涵盖核心突破、双中心验证、伦理声明与无利益冲突
   - File Type in Portal: **Cover Letter**
4. **源码归档包**：`reports/manuscript_latex_source.zip`
   - 包含干净的 `main.tex`, `main.bbl`, `references.bib`

---

## 二、 投稿四大核心自查对照表（审稿人视角免卡自查）

### 核心一：研究边界与无未证实首创（严格遵循学术边界约定）
- [x] **无不实首创宣称**：全面剔除未逐篇核实的 "first/novel/pioneering" 宽泛宣称。
- [x] **创新边界精准落地**：精确表述为“把以血流动力学响应时间为依据的多中心高斯时滞偏置（$\tau_h \in \{3.5, 4.5, 5.5, 6.5\}$ s）与排除未来 EEG token 的时间戳掩码共同写入 EEG–fNIRS 跨模态注意力，并在被试隔离的 LOSO 评估中用析因实验分别测量两者的作用”。

### 核心二：双中心跨硬件独立外部验证（解决单一数据集缺陷）
- [x] **主数据集（TU Berlin）**：29 名被试，三大任务（心算 79.37%、工作记忆 73.24%、运动想象 66.32%）。
- [x] **第二公开数据集（Buccino et al. 2016）**：15 名被试，3,000 试次，独立硬件（microEEG + NIRScout 8-16），取得 **81.03%** 跨被试识别率（Table S3）。
- [x] **消融规律跨队列 100% 复现**：`Direct-Only (80.43%) > Latent-Only (73.70%)`，证明生理双流先验的普适鲁棒性。

### 核心三：工程算力与实时在线可行性（闭环 BCI 证据）
- [x] **超轻量参数量**：全模型仅 **63,932** 参数与 **24.79 M MACs**，单试次 GPU 延迟仅 **2.22 ms**（P99: 4.48 ms）。
- [x] **CrEA 在线递推复杂度 $\mathcal{O}(C^2)$**：CPU 单试次更新耗时 $< 1.2$ ms，8 试次内相对误差收敛至 29.38%，全闭环延迟 $< 15$ ms。

### 核心四：代码复现与合规伦理
- [x] **单元测试全覆盖**：`pytest tests/` 26/26 项 100% 通过。
- [x] **全维度审计断言**：`tests/audit_codebase_soundness.py` 12 维度 48 项断言 100% 通过。
- [x] **开源透明度**：GitHub 仓库已完成 commit 与 push，开放完整代码。
