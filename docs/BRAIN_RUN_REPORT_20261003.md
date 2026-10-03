# MaleCNS 果蝇模型运行记录（2026-10-03，北京时间）

## 本轮目标与数据依据

按用户最新要求，重点为果蝇神经元模型，人耳部分保留后续接口。已核查 [Google Research 2026-09-03 发布说明](https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/) 和 [MaleCNS 官方下载页](https://male-cns.janelia.org/download/)，本项目固定使用 `male-cns:v1.0`。

三份官方原始文件共 1,109,008,094 bytes，均已复核 provider MD5、本地 SHA-256 和大小：神经元注释、神经递质预测、segment-to-segment 连接数。上轮只凭文件列表判断数据缺失不准确；本轮已逐项核验并从原始数据重新提取。原文件、下载来源和哈希位于 `data/raw/malecns/`，新快照位于 `data/processed/malecns_snapshots/real_public_fixed_20261003/`。

名称候选包含 auditory 和 wind_gravity 等不同注释，本轮筛选 auditory。得到 65 seeds、265 节点、6,535 条有向边。递质预测：178 acetylcholine、84 gaba、3 glutamate。预测符号只是工程先验；glutamate 保留未知符号情景，不把预测标签当作受体功能测量。

## 本机环境和 H 盘存储

Windows 11，16 个逻辑 CPU；Python 3.12.7 位于既有 `C:/Users/liyang/.virtualenvs/ear-malecns/`。Brian2 2.10.1、NumPy 2.5.3、pandas 3.0.6、SciPy 1.18.1、h5py 3.16.0、PyArrow 25.0.1、NetworkX 3.7 和 Matplotlib 3.11.2 均可用。未重装环境。

所有新增数据、SWC、OpenEar 几何、输出、下载／测试／绘图缓存和浏览器独立配置在 H 盘项目目录。环境本体保留原位置。完整机器记录位于 `outputs/environment_actual.json`。

初次 WSL 检查被沙箱拒绝；经授权只读检查后确认 Ubuntu-22.04 和 docker-desktop 均已注册为 WSL2、处于 stopped 状态。未测试启动，不能由初次沙箱错误推断 WSL 损坏。本项目已在 Windows 原生 Python 成功运行，不依赖 WSL。

## 果蝇实验结果

主入口 `scripts/16_run_connectome.py` 不依赖人耳，接受真实图快照和固定感觉输入。seed=42，dt=0.1 ms，duration=1000 ms；65 独立通道，20 → 100 → 20 Hz，刺激窗 200–800 ms，共 4,519 冻结事件。

| 拓扑 | 总发放数 | 输入活跃 | 第一跳活跃 | 第二跳活跃 |
|---|---:|---:|---:|---:|
| 真实原图 | 1575 | 65/65 | 4/100 | 0/100 |
| 保度重连 | 1548 | 65/65 | 0/100 | 0/100 |
| 权重打乱 | 1596 | 65/65 | 6/100 | 0/100 |

原图与权重打乱通过当前阶段软件验收；重连条件的 downstream_response=false 原样保存，退出码 2 表示该检查未通过，并非运行崩溃。没有为了美观改变这个条件的参数。零输入对照为 0 spikes，未触发近不应期上限的检查。

三个固定输入文件 SHA-256 一致：`2f11b5ad5f7afadd0f2d08990db65c4784abc7a4ebc77e6d4dc9fbbcdaa52c95`。以 `outputs/delivery_verification.json` 中完整哈希为权威，本段便于查阅。保度重连完成 32,675 次交换（56,530 次尝试），入度／出度及权重多重集均验证保持；权重打乱保持拓扑和权重多重集。原 discovery hop 沿用作分组，不代表重连后的路径距离。

主运行在 `outputs/runs/malecns_brain_focus_20261003/`，三个带拓扑后缀的相邻目录保存 graph_snapshot、spikes、latency、neuron/hop metrics、raster、config 和 manifest。

## 参数依赖与形态

保存 15 个固定输入增益场景，位于 `outputs/parameter_sweeps/gains_20261003T091801_100456Z/`。下游活跃比例在不同场景为 0%–54.5%，说明目前响应明显依赖假设参数。默认 w0=0.5 mV、input gain=6 mV，不把演示增益当成生理拟合。

另有两个未知递质符号情景，位于 `gains_20261003T091811_403915Z/`，本次总发放均为 1575、下游活跃均为 2%。这只说明当前刺激与模型下该情景没有改变指标。

24 个代表性 SWC 按原图响应排序、每 hop 8 个细胞，保存在 `skeletons/male-cns-v1.0/activity_representative/`。另保留种子样本和按 ID 排序的代表样本。全部来自官方公共存储，逐文件检查官方 MD5 和本地 SHA-256。原 SWC 全量保留，浏览器每个细胞最多显示 1600 条抽稀线段；抽样细胞不用于估计总体活跃比例。官方 8 nm 坐标转换为微米。

## 可视化与验证

`outputs/visualizations/malecns_brain_explorer/index.html` 是自包含报告：活动播放、时间滑块、原图／重连／权重打乱切换、神经元点选、SWC 旋转／缩放、raster 和敏感性网格。无需网络或外部 JS。另生成 `brain_activity.gif`、`brain_overview.png` 和 `brain_overview.pdf`。

浏览器亮度是模拟 spike 的 τ=20 ms 指数衰减。单细胞整体着色，没有模拟枝条内的电缆传播。图布局是拓扑排列，SWC 才是解剖坐标；图仅画最强 900 条边，但仿真使用全部边。

26 个 pytest 通过；9 个 Edge 页面交互自检通过（时间滑块、活动变化、拓扑切换、指标、结构颜色、点选、旋转、完整网格及三组条件）。`scripts/17_verify_delivery.py` 完成原始数据、固定输入一致性、图对照不变量、SWC、报告 manifest 和附属几何校验，全部通过。

## 留给人耳模型的接口

已用 `16_run_connectome.py --input encoder.npz` 复用既有人工编码输入，`malecns_interface_replay_20261003_original` 与 `real_public_demo_20261003_original` 的 spike 表完全一致（1332 spikes）。外部 NPZ 需要按快照 seed 顺序提供 body_ids、channels、times_s，时间格无冲突。后续真实 FEM → HDF5 → 显式 encoder → 固定事件可接入同一网络，不用修改神经模型核心。

已补下载 [OpenEar ZETA](https://zenodo.org/records/1473724) 的 13 个解剖几何，139,662,639 bytes，存储于 `fem/geometry/openear_zeta/`。用 HTTP ranges 从官方 ZIP 提取几何，实际传输 68,558,630 bytes；逐成员 CRC32 加本地 SHA-256，未声称完成整包 MD5。原始影像未下载，几何未参与果蝇主实验，也不是 FEM 力学响应。

当前成果是真实结构约束下的听觉子图 LIF 平台。全 CNS 扩展、神经动力学生理标定、多刺激多种子统计和真实 FEM 尚未完成；`real_malecns_acceptance=false` 保留科学边界。
