# Elsevier *Computers in Biology and Medicine* (CBM) 投稿核对清单 (Submission Checklist)

### 一、核心投稿文件与本地路径对应表

| 投稿系统要求栏目 | 推荐上传文件 | 本地绝对路径 | 作用与要求说明 |
| :--- | :--- | :--- | :--- |
| **Manuscript File** (PDF / TeX) | `main_cbm.pdf` 或完整的 LaTeX 打包包 | [`e:/课题4/reports/manuscript_CBM_submission.pdf`](file:///e:/课题4/reports/manuscript_CBM_submission.pdf) | Elsevier 5p 双栏排版标准稿，10页长文，含全套图表与统计分析 |
| **Highlights** | `CBM_Highlights.md` | [`e:/课题4/reports/CBM_Highlights.md`](file:///e:/课题4/reports/CBM_Highlights.md) | 必选，5条核心结论，严格每条 $\le 85$ 字符（含空格） |
| **Cover Letter** | `CBM_Cover_Letter.md` | [`e:/课题4/reports/CBM_Cover_Letter.md`](file:///e:/课题4/reports/CBM_Cover_Letter.md) | 包含研究背景、双重分离核心突破、声明及通讯作者信息 |
| **Graphical Abstract** (可选推荐) | `nvc_multipanel_topomap_suite.png` | [`e:/课题4/reports/figures/nvc_multipanel_topomap_suite.png`](file:///e:/课题4/reports/figures/nvc_multipanel_topomap_suite.png) | 推荐使用图4（皮层地形三联图），直观呈现神经血管耦合时间桥 |
| **LaTeX 源码包** (若投源文件) | `latex_cbm/` 整个目录 | [`e:/课题4/latex_cbm`](file:///e:/课题4/latex_cbm) | 含 `main_cbm.tex`, `references.bib`, `figures/` |

---

### 二、Elsevier Editorial Manager 系统填报关键元数据

1. **Article Type**:
   * 选择 **Full Length Article** 或 **Regular Research Paper**。
2. **Title**:
   * `Physiology-Guided Causal Cross-Attention Resolves the Neurovascular Latency Mismatch in Hybrid EEG--fNIRS Brain--Computer Interfaces`
3. **Abstract**:
   * 直接复制手稿摘要（约 250 词，已完整涵盖 29-fold LOSO、65.52%、Cohen's dz、Phase Roll 双重分离 $p=7.05\times 10^{-8}$ 以及 1.61 ms 边缘时延）。
4. **Keywords**:
   * `Hybrid Brain-Computer Interface`
   * `Neurovascular Coupling`
   * `Electroencephalography`
   * `Functional Near-Infrared Spectroscopy`
   * `Causal Cross-Attention`
   * `Deep Learning`
5. **CRediT Author Statement**:
   * 已内置于正文：*Antigravity BCI Research Collaborative: Conceptualization, Methodology, Software, Formal analysis, Investigation, Data curation, Writing - original draft, Writing - review & editing, Visualization.*
6. **Conflict of Interest**:
   * 选择 *No conflict of interest exists*.
7. **Research Data**:
   * 选择 *Data will be made available on request / Data is publicly available (TU Berlin Benchmark)*.

---

### 三、建议推荐审稿人方向与回避策略
* **推荐审稿人专业画像 (Suggested Reviewers)**：
  1. **混合脑机接口与多模态神经工程专家**：熟悉 EEG 与 fNIRS 联合分析、CSP 滤波、运动想象或认知负荷解码的学者（如长期在 JNE / TBME / CBM 发表 hybrid BCI 的团队）。
  2. **生物医学时序深度学习与 Transformer 专家**：熟悉时间序列交叉注意力、生理先验嵌入及留一被试（LOSO）评估规范的学者。
* **主要回避对象 (Opposed Reviewers)**：
  * 无需特殊回避，可避开存在直接同类算法竞争的课题组。
