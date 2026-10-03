# 初版链路落实记录（2026-10-03）

手册作为技术参考，本次未执行系统安装、环境迁移和全 CNS 仿真命令。在用户指定项目目录中完善代码，复用阶段一图快照、LIF 和分析实现。

链路：`stimulus → fem_io → pipeline.calibrate / encode_events → stage1.run_stage1 → snn → analysis`。

## FEM HDF5 契约

| 路径 | 要求 |
|---|---|
| stimulus/time_s | 秒，1D，从 0 开始，均匀采样 |
| stimulus/pressure_Pa | Pa，有限、与时间等长 |
| fem/tm_displacement_m | m，有限、与时间等长 |
| fem/stapes_velocity_m_s | m/s，有限、与时间等长 |
| metadata 属性 sample_rate_hz | 有限正数，与时间间隔一致 |
| metadata 属性 fem_version | 非空来源／版本字符串 |

格式校验不证明物理正确。真实 FEM 仍需几何、材料、边界条件、网格收敛及实验验证。合成版本固定为 `SYNTHETIC_SELFTEST_NOT_FEM`。

## 编码

训练集平滑 Hilbert envelope 后池化 log-envelope，冻结 Q5/Q95。测试集复用相同分位数和时间常数。默认自身标定仅用于 selftest。旧 `encode_fem_file` 接口新增可选 calibration，同时给旧默认归一化明确打标。

适应后 drive 改用 `1-exp(-gain*drive)`：零特征返回设定基线，修正旧 sigmoid 在静默时高于基线的问题。历史输入需要重新生成。该模型仍是未经过生理拟合的人工跨物种桥接，只使用 envelope，不保证载频或相位保留。

rate 在仿真时间格上积分，各通道独立按 `1-exp(-integrated_rate)` 采样是否有事件，每格最多一次。它是离散 Poisson 占用近似，高率时无法表达同格多个事件。固定事件只生成一次，随后用于全部拓扑对照。

## 拓扑对照

保度重连保持有向入度／出度和权重多重集，拒绝新增自环／重复边，记录请求、尝试和成功交换次数。成功次数为零不能声称有效随机化。权重打乱保持原拓扑。原 discovery hop 沿用于对照分组，不代表重连后的新最短路径。

合成夹具全部权重相同，因此权重打乱结果与原图相同属于预期。不能从合成图对照声称 MaleCNS 拓扑优势；正式研究需真实数据、多刺激和多个重连种子。

## 验证与后续

本次离线验收：120 节点，三个图条件，原图／重连／权重打乱各输出完整产物，固定输入文件哈希一致。验收入口产物为 `outputs/runs/initial_pipeline_verified`；相邻带拓扑后缀的目录保存具体仿真。失败的早期配置调试目录保留以便审计，不作为验收数据。

测试覆盖原阶段和新增幅度标定、固定采样复现、时间格无冲突、静默基线、无效 FEM 时间、重连 degree。优先取得真实 JO seed 并审查 annotation，然后接冻结图、训练刺激标定、经验证的人耳 FEM。在线认证、真实图结果、FEM 求解、生理拟合、正式 UQ 与动态形态动画尚未验收。

最终验证：`26 passed in 9.57s`；测试有一个来自异常路径测试的 Brian2 未加入网络对象告警，不影响通过。原图 789 spikes，重连 520 spikes，权重打乱 789 spikes；三组软件检查均通过。以上数值仅属于合成夹具，不作为生物学结论。
