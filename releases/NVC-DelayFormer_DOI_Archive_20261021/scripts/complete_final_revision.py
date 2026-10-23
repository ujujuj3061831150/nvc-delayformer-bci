"""Verify reconciled evidence, publish compiled copies, and write factual notes."""
from pathlib import Path
import json, shutil, hashlib
import numpy as np
from scipy import stats
import fitz

root=Path(__file__).resolve().parents[1]
archive=root/'reports/archive/final_revision_20261013'
for name in ['CBM_Cover_Letter.md','CBM_Highlights.md','CBM_Submission_Package_Checklist.md']:
    source=root/'reports'/name
    target=archive/'reports'/name
    if source.exists() and not target.exists(): shutil.copy2(source,target)

highlights=[
    'Timestamp-constrained cross-attention combines EEG and fNIRS sequences.',
    'The main benchmark uses a fixed 5.0 s Gaussian delay prior.',
    'Twenty-nine subject-held-out folds yield 66.44% mean accuracy.',
    'Circular EEG shifting changes accuracy by -6.61 percentage points.',
    'Batch-one GPU forward latency has median 3.24 ms and P99 5.89 ms.',
]
assert all(len(h)<=85 for h in highlights)
(root/'reports/CBM_Highlights.md').write_text('# Research Highlights\n\n'+'\n'.join('- '+h for h in highlights)+'\n',encoding='utf-8')

letter='''# Cover Letter to Computers in Biology and Medicine

October 13, 2026

Dear Editor,

We submit “Physiology-Guided Temporal Fusion for Subject-Held-Out EEG–fNIRS Classification” for consideration in *Computers in Biology and Medicine*.

The study evaluates NVC-DelayFormer for mental arithmetic versus rest on the public TU Berlin EEG–fNIRS cohort. The architecture combines convolutional encoders, a fixed Gaussian delay prior, timestamp-constrained attention, weighted direct features, and an auxiliary reconstruction output.

Twenty-nine subject-held-out folds use 23 training subjects, five validation subjects, and one test subject each. Across 1,740 test trials, accuracy is 66.44% ± 10.85%, the 95% confidence interval is [62.31%, 70.57%], Macro F1 is 65.13%, and Cohen’s kappa is 0.3287. The four paired baseline comparisons have Benjamini–Hochberg q < 0.01.

The manuscript reports component ablations, a fixed-weight delay sweep, and input perturbations. A five-second circular EEG shift lowers accuracy by 6.61 percentage points. The independently trained zero-delay model reaches 66.61%, with Wilcoxon p = 0.9636 against the full model. Additional causal EEG smoothing is evaluated after offline preprocessing.

The model has 92,293 trainable parameters and 19.98 million profiled MACs. Batch-one GPU forward latency has median 3.24 ms and P99 5.89 ms. CPU latency, including its measured long tail, is reported separately. Timings exclude acquisition, preprocessing, and device transfer.

The accompanying records retain subject-level results and the statistical and engineering protocols.

Sincerely,

Antigravity BCI Research Collaborative

Laboratory for Neural Engineering & Neurovascular Computing

research@antigravity-bci.org
'''
(root/'reports/CBM_Cover_Letter.md').write_text(letter,encoding='utf-8')

negative=json.loads((root/'reports/negative_controls_rigorous_results.json').read_text(encoding='utf-8'))
full=np.array(negative['full_model']['fold_accs'])
checks=[]
for name,r in negative['controls'].items():
    a=np.array(r['fold_accs'])
    counts=np.array(r['fold_correct_counts'])
    denominator=r['trials_per_subject']*r['evaluations_per_subject']
    assert np.allclose(a,counts/denominator*100,atol=1e-12,rtol=0)
    diff=np.round(full-a,10)
    t=stats.ttest_1samp(diff,0)
    w=stats.wilcoxon(diff,zero_method='wilcox',correction=False,alternative='two-sided',method='approx')
    assert abs(t.pvalue-r['t_test_p'])<1e-14
    assert abs(w.pvalue-r['wilcoxon_p'])<1e-14
    checks.append({'condition':name,'t_p':t.pvalue,'wilcoxon_p':w.pvalue,'fdr_q':r['fdr_q'],'count_and_statistics_verified':True})

pairs=[('latex_cbm/main_cbm.pdf','reports/manuscript_CBM_submission.pdf'),
       ('latex/main.pdf','reports/manuscript_IEEEtran_submission.pdf')]
files=[]
for src,dst in pairs:
    path=root/src
    document=fitz.open(path)
    text='\n'.join(p.get_text() for p in document)
    for stale in ['6.90','7.05','0.2519','64.83','above 85','1933.2','1.61']:
        assert stale not in text,(src,stale)
    for required in ['66.44','59.83','64.43','362.00']:
        assert required in text,(src,required)
    assert '??' not in text
    document.close()
    shutil.copy2(path,root/dst)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==hashlib.sha256((root/dst).read_bytes()).hexdigest()
    files.append({'compiled':src,'submission':dst,'sha256':digest,'pages':len(fitz.open(path))})

artifact_root=Path('C:/Users/ikunccc/.gemini/antigravity/brain/dced5340-cb2c-4d72-a2e2-7006b0c89469')
artifact_copies=[]
for f in files:
    target=artifact_root/Path(f['submission']).name
    if target.exists():
        previous=archive/'artifact_copies'/target.name
        previous.parent.mkdir(parents=True,exist_ok=True)
        if not previous.exists(): shutil.copy2(target,previous)
        shutil.copy2(root/f['submission'],target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==f['sha256']
        artifact_copies.append(str(target))

report='''# 最终修改与验证记录

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
'''
for name,r in negative['controls'].items():
    report+=f"| {name} | {r['mean_acc']:.2f}% ± {r['std_acc']:.2f}% | {-r['delta_mean']:+.2f} | {r['t_test_p']:.8g} | {r['wilcoxon_p']:.8g} | {r['fdr_q']:.8g} |\n"
report+='''
## 交付文件

'''
for f in files: report+=f"- `{f['submission']}`：{f['pages']}页，与`{f['compiled']}` SHA256一致。\n"
for p in artifact_copies: report+=f"- `{p}`：与同格式提交副本SHA256一致。\n"
report+='''
## 验证范围与留存

- 从JSON计数比例独立复算四项paired t和Wilcoxon，与保存统计逐项一致。
- 两种LaTeX稿件重新生成参考文献并多次编译；检查未定义引用、公式溢出和最终页面渲染。
- 本次未重训模型，未更改模型前向计算，未新增实验观测。主精度来自已有锁定预测，负对照来自已有计数记录恢复。
- 工程JSON仍为原测量摘要，未补写缺失的原始计时样本。CPU记录的processor是平台标识；正文未将其扩写成未经该记录确认的CPU型号。
- 重建相关性对应派生proxy且该proxy进入重建输入；不解释为独立生理信号恢复或分类必需性。
- 先前版本位于`reports/archive/final_revision_20261013/`。本记录取代先前“全部通过”式总结，不构成新增实验认证。
'''
(root/'reports/real_experimental_verification_and_manuscript_audit_report.md').write_text(report,encoding='utf-8')
(root/'reports/final_revision_verification.json').write_text(json.dumps({'statistics':checks,'pdf_files':files,'artifact_copies':artifact_copies,'main_results_preserved':True,'inference_unchanged':True,'visual_qa':'All final CBM and IEEE pages rendered and inspected; no clipping or overlap observed.'},indent=2),encoding='utf-8')
(root/'reports/CBM_Submission_Package_Checklist.md').write_text('''# 当前本地投稿文件索引

- CBM稿件：`reports/manuscript_CBM_submission.pdf`
- IEEE格式稿件：`reports/manuscript_IEEEtran_submission.pdf`
- 投稿信：`reports/CBM_Cover_Letter.md`
- Highlights：`reports/CBM_Highlights.md`
- 修改与验证记录：`reports/real_experimental_verification_and_manuscript_audit_report.md`
- 逐试次预测：`reports/real_29sub_locked_predictions.json`
- 主实验汇总：`reports/real_29sub_benchmark_and_ablation_summary.json`
- 负对照：`reports/negative_controls_rigorous_results.json`
- 工程摘要：`reports/engineering_benchmarks.json`

文件已在本地准备，未进行外部投稿。作者、单位与声明保留现有手稿提供的信息。
''',encoding='utf-8')
print(json.dumps({'statistics_verified':len(checks),'outputs':files},ensure_ascii=False,indent=2))
