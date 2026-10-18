> 2026-10-13 CMPB 全文优化更新：当前主稿已完成方法重排、公式/维度补全、统计复核和客观讨论改写；EEGNet 历史基线在发表文本中纠正为 EEG-CNN，零时延变体纠正为 Zero-delay prior。完整模型验证链成立，独立生理机制归因和 MBLL 物理单位来源仍不能判定通过。详见 [最终修改与论证闭环评估](CMPB_final_polishing_and_story_assessment.md)。下文保留历史验收记录。

# 最终修改与验证记录

日期：2026-10-13。修改依据为当前30通道实验记录、逐试次锁定预测、负对照记录及工程JSON。

## 修改内容

- 两种稿件的摘要、引言、结果和结论统一报告66.44% ± 10.85%、Macro F1 65.13%，时移变化为-6.61个百分点。
- 移除旧版EEGNet/Standard-Attention时移比较及生理方向性确认；主基准固定tau=5 s，零延迟消融为66.61%、Wilcoxon p=0.9636。
- 将“流式因果滤波验证”改为“追加因果EEG平滑”：在离线预处理的EEG上递推平滑，alpha=0.85，fNIRS不变。准确率64.43%。
- 改用明确的负对照统计口径，保存全精度计数比例、分母、检验参数和BH检验家族。
- 删除预设审稿质疑、对其他研究泄漏的泛指断言、CPU长尾原因推测和未经绑定新版模型的历史空间图/潜空间数字。
- 方法正文补齐4头/16维缩放、广播、时间掩码容差、直接读出、时间权重、重建输入/目标与输出链。重绘实际计算图与结果图。
- 讨论只报告观测结果、测试条件和评价范围。GPU/CPU分别报告中位数、均值、SD及P99；未重新测量延迟。
- 投稿信与Highlights同步最新数字及题目。
- 两种稿件保留2023轻量EEG、2024运动想象解释性、2025卷积表示文献，并补充2024 fNIRSNET多视图融合对话。新增条目按作者手稿与出版方记录核对；未将不同任务的准确率作直接比较。

## 负对照记录恢复与统计

原JSON的逐被试精度曾被舍入为两位小数。本次用明确的试次数约束恢复计数比例：单次条件每人60次；10次置换条件合计600次。所有原舍入值均能唯一对应其整数正确次数，恢复值与原值误差不超过0.005个百分点。未恢复或编造单次置换预测。

配对差值采用full减control，保留至10位小数以消除等价有理数运算的浮点秩差异。双侧Wilcoxon采用normal approximation、zero_method=wilcox、ties校正、无连续性校正；四项Wilcoxon采用BH校正。主基准与消融原始汇总未改动。

| 条件 | Mean ± sample SD | control-full (pp) | paired t p | Wilcoxon p | BH q |
|---|---:|---:|---:|---:|---:|
| Within-Class Permutation | 66.57% ± 9.84% | +0.13 | 0.81475659 | 0.59683955 | 0.59683955 |
| Across-Class Permutation | 56.84% ± 5.78% | -9.60 | 3.7184815e-05 | 0.00016811776 | 0.00033623551 |
| Temporal Phase Roll (±5s) | 59.83% ± 10.12% | -6.61 | 9.4706317e-06 | 7.1310695e-05 | 0.00028524278 |
| Additional Causal EEG Smoothing | 64.43% ± 11.08% | -2.01 | 0.02950144 | 0.032176108 | 0.042901477 |

## 交付文件

- `reports/manuscript_CBM_submission.pdf`：9页，与`latex_cbm/main_cbm.pdf` SHA256一致。
- `reports/manuscript_IEEEtran_submission.pdf`：5页，与`latex/main.pdf` SHA256一致。
- `C:\Users\ikunccc\.gemini\antigravity\brain\dced5340-cb2c-4d72-a2e2-7006b0c89469\manuscript_CBM_submission.pdf`：与同格式提交副本SHA256一致。
- `C:\Users\ikunccc\.gemini\antigravity\brain\dced5340-cb2c-4d72-a2e2-7006b0c89469\manuscript_IEEEtran_submission.pdf`：与同格式提交副本SHA256一致。

## 验证范围与留存

- 从JSON计数比例独立复算四项paired t和Wilcoxon，与保存统计逐项一致。
- 两种LaTeX稿件重新生成参考文献并多次编译；检查未定义引用、公式溢出和最终页面渲染。
- 本次未重训模型，未更改模型前向计算，未新增实验观测。主精度来自已有锁定预测，负对照来自已有计数记录恢复。
- 工程JSON仍为原测量摘要，未补写缺失的原始计时样本。CPU记录的processor是平台标识；正文未将其扩写成未经该记录确认的CPU型号。
- 重建相关性对应派生proxy且该proxy进入重建输入；不解释为独立生理信号恢复或分类必需性。
- 先前版本位于`reports/archive/final_revision_20261013/`。本记录取代先前“全部通过”式总结，不构成新增实验认证。
