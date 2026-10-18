# 阶段 5 软件与复现包验收

日期：2026-10-14。审查独立包、实际 CLI、原实验实现的一致性及交付文档。本轮未修改模块、训练入口、原实验记录或稿件，也未重跑实验训练。

## 结论

独立 Python 包已具备可调用、可打包及外部安装能力；联合读出和潜在读出与原实现数值一致。完整论文复现入口仍需三组局部修正：训练入口及协议、Direct-Only 门控语义、发布文档与元数据。已有实验数据无需重跑。

## 通过项

- 复跑 tests/test_temporal_fusion.py 与 tests/test_compliance.py：14 passed，5.63 秒。
- reproduce_benchmark.py --verify 运行成功，确认 92,293 参数、29 个处理数据目录、四种窗口前向形状和首查询行未来访问屏蔽。
- --benchmark 实际运行成功，能够读取阶段 1、3、4 JSON 并打印锁定结果。
- pip wheel --no-deps --no-build-isolation 构建成功，生成 temporal_fusion-1.0.0 wheel。
- 将 wheel 安装到独立临时目录，并在项目外通过 Python -I 调用。独立导入和 3 秒输入前向成功，不依赖 src 包。
- 用原实现权重映射加载新实现，联合读出和 Latent-Only 的 logits、attention、reconstruction 最大差值均为零。
- 三份 PDF 均为 8 页，SHA-256 同为 634a18492792e8bad88adcc13e2ba13b2fe733317315e895b9265a8e307005dc；日志无 Overfull、undefined 或 Warning。

--verify 当前是模块和环境自检，不会实际启动 pytest，也不校验每个数据文件的内容。数据目录数与真正的内容完整性应在说明中分别标注。--benchmark 是结果展示入口；真正的训练复现由训练命令承担。

## 修正组 1：训练命令与实验协议

实际执行 python reproduce_benchmark.py --train-fold 5，在进入训练前报 ImportError：run_phase1_suite 不存在。原模块导出的是 run_phase1_experiments。

删除错误导入后，还应复用原实验的单折训练流程，而不是继续使用当前另写的简化循环。当前单折入口与论文协议的差异包括：

- 未设置 seed=42+subject；
- 验证集固定取 pool 前五人，而非原实验的循环位置规则；
- 每 epoch 只进行一次全训练集更新，而非 batch=256 随机打乱；
- 缺少原 warm-up/cosine 调度与 gradient clipping；
- 检查点选择未使用原验证损失的平局规则。

建议从现有实验脚本提取共享 train_one_fold，CLI 与全折实验共同调用，输入/输出均保存可核对的配置和结果。这样修复一次即可保持一致性。

## 修正组 2：Direct-Only 保持已实测定义

阶段 1 的 Direct-Only 将重建器潜在输入置零，但保留由光学代理重建产生的门控。新包的 DualPathJointReadout 在 cut_gate_latent=True 时跳过整个重建门控，改为直接使用归一化特征。

在相同权重和输入下实测：attention 与 reconstruction 最大差值均为零，Direct-Only logits 最大差值为 0.1214585。差异来自门控绕过，不是数值精度。

应让 cut_gate_latent 仅在重建器输入端切断潜在连接，保留代理门控；如另需“完全取消门控”，使用独立开关。补充权重映射后的三种读出数值一致性检查即可覆盖此处，已有 14 个单元测试未检查新旧等价性。

## 修正组 3：发布文档与元数据一致

- README 的表格应由原结果 JSON 生成。例：Seed 100 Subject-SD 应为 12.53，当前为 11.83；Seed 2024 应为 11.54，当前为 12.24。Seed 42 Macro F1 SD 应为 11.76，当前为 12.16。共享编码器基线的 SD、F1、p、q 也存在与原记录不同的手填值。
- 补上 README 链接所指向的 LICENSE 文件，许可证元数据已经声明 MIT，但根目录尚无该文件。
- 添加数据获得及预处理命令，以及与实际实验版本一致的环境快照。requirements.txt 当前是版本范围，并非 README 所称的 pinned dependencies。
- README 的论文标题与数据 DOI 应和主稿保持一致；该同步可以随表格自动生成完成。

这些是复现包发布内容的局部对齐，不改变研究结果。

## 成果定位

阶段 5 已将论文核心计算变成能够单独安装和调用的软件实现。补齐上述入口与一致性后，软件贡献可以具体表述为“独立时间融合模块、与实验一致的训练复现入口、锁定结果展示和自动化数值验证”。
