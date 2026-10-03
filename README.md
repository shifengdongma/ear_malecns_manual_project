# 声源到 MaleCNS 神经活动 · 完整链路工作台

打开 **http://127.0.0.1:8765**，或运行 `./start_signal_workbench.ps1`。支持修改刺激后真正重新仿真、逐连接检查延迟与膜电压、真实 OpenEar 几何、265 个真实 SWC、刺激/拓扑条件比较和已有 FEM HDF5 导入。

[操作与本轮实测结果](docs/SIGNAL_WORKBENCH_GUIDE.md) · [离线完整链路报告](outputs/workbench/index.html) · [界面预览](outputs/workbench/workbench_overview.png) · [神经元事件预览](outputs/workbench/workbench_neural_events.png)。默认人耳响应为明确标注的参考传递函数演示；OpenEar 几何已复用，真实求解响应从已有模型导入。全部输出存储在 H 盘。

当前参考案例采用外部声源→共享标定 encoder 的输入，包含 250/150 Hz、三个 IPI、静默、权重打乱和 w0=2 mV。下面保留先前固定感觉输入实验记录，其数值对应不同的输入方案。

## 项目维护与文档

[工作日志](docs/work-log.md) · [工作总结](docs/work-summary.md) · [系统架构](docs/system-architecture.md) · [用户手册](docs/user-manual.md)。后续每次修改更新有关文档，代码上传须逐次询问用户；规则入口为 [AGENTS.md](AGENTS.md) 和 [.codex/project-rules.md](.codex/project-rules.md)。

GitHub 仅保存源码、配置、测试、依赖声明与文档。数据、原始模型、SWC、环境包、生成报告及缓存保留在 H 盘，因此仓库中的本机产物链接须恢复数据并运行后才可打开。首次使用参见用户手册。


---

# MaleCNS 果蝇连接组模型 · 本机运行版

本轮按用户要求重点放在果蝇模型。主链路已用真实数据运行：MaleCNS v1.0 官方文件 → JO-A/B 候选注释审计 → subclass=auditory 的 65 个输入细胞 → 265 节点／6,535 边的 1–2 hop 子图 → 固定感觉输入 → Brian2 LIF → 活动、latency、SWC 与拓扑对照。人耳部分保留 HDF5 和 encoder 接口，等待接入已有有限元模型。

**打开 [果蝇模型互动报告](outputs/visualizations/malecns_brain_explorer/index.html)**：播放活动、旋转真实形态、切换拓扑、点选神经元。也可查看 [动态预览](outputs/visualizations/malecns_brain_explorer/brain_activity.gif)、[概览图](outputs/visualizations/malecns_brain_explorer/brain_overview.png) 和 [运行报告](docs/BRAIN_RUN_REPORT_20261003.md)。报告可离线打开，无外部 JS/CDN。

上轮关于“真实文件缺失”的判断已被本轮逐项检查纠正：三份官方数据及历史快照在 H 盘可用。已对官方 MD5 和本地 SHA-256 重新核验，并从原始文件重新提取 auditory-only 子图。Google 2026-09-03 的发布说明与本项目选用的 MaleCNS 一致：[Google 官方说明](https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/)。数据署名依照 MaleCNS / FlyEM、HHMI Janelia、Cambridge、MRC LMB 和 Google Research 官方记录。

默认原图激活 65/65 输入细胞、4/100 第一跳、0/100 第二跳；重连图下游为 0，权重打乱图激活 6 个第一跳细胞。完整保留 15 个增益场景和 2 个未知递质符号场景，不能凭一次仿真声称真实拓扑优势。真实连接结构与形态不等于实测动力学，当前仍是听觉子图模型，不是完整 CNS 仿真。

## 运行

在本项目目录运行；入口也支持从其他工作目录启动。源码所在目录自动成为项目根目录，无需建立目录联接。Windows 必须在 H 盘；WSL 必须在已挂载的 `/mnt/h`。数据、缓存、临时文件和输出均在项目内，环境保留原位置。

```powershell
$pythonExe = 'C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe'
& $pythonExe scripts/10_run_pipeline.py --controls
& $pythonExe -m pytest tests -q --basetemp=downloads/pytest-check
& $pythonExe scripts/00_selftest.py
& $pythonExe scripts/06_stage1.py --mode offline
```

果蝇模型不需要人耳模型即可复跑（从本项目根目录）：

```powershell
$snapshot = 'data/processed/malecns_snapshots/real_public_fixed_20261003'
& $pythonExe scripts/16_run_connectome.py --snapshot $snapshot --controls
# 查看已生成报告
Start-Process 'outputs/visualizations/malecns_brain_explorer/index.html'
# 校验本轮交付文件
& $pythonExe scripts/17_verify_delivery.py
```

`16_run_connectome.py` 接受 `--input PATH.npz`：要求 `body_ids` 与 snapshot seed 顺序一致，以及一维 `channels`、`times_s`，时间在仿真范围内且每通道每仿真格不重复。已实测该入口与原 encoder 链路复用同一输入时 spike 表完全一致。未来 FEM 接入不用修改果蝇模型核心。

真实数据重新下载／重提取：

```powershell
& $pythonExe scripts/08_download_public.py
& $pythonExe scripts/06_stage1.py --mode public --config configs/stage1_auditory_only.yaml
```

可视化重建：

```powershell
& $pythonExe scripts/12_build_brain_report.py --run outputs/runs/malecns_brain_focus_20261003 --sweep outputs/parameter_sweeps/gains_20261003T091801_100456Z --skeleton-dir skeletons/male-cns-v1.0/activity_representative --report-id YOUR_NEW_REPORT
```

已有报告可加 `--refresh` 重新生成；刷新仅允许同一源运行的派生报告，不覆盖冻结实验数据。

其他机器使用主 `environment.yml` 建环境、`pip install -e .` 后以 `python` 运行。完整链路需要 SciPy/h5py，第一阶段最小环境不含这些依赖。默认配置 `configs/pipeline.yaml`，seed=42，dataset=`male-cns:v1.0`。自动生成唯一 run ID，也可指定 `--run-id`，已有目录拒绝覆盖。

本轮实际依赖版本保存在 `requirements-runtime-lock.txt`（Windows Python 3.12），机器与缓存路径记录在 `outputs/environment_actual.json`。果蝇主入口默认使用 `configs/stage1_auditory_only.yaml`；`pipeline_real_demo.yaml` 是单独的工程增益演示，不替代主配置。

## 接真实数据

已有 01–09 阶段脚本保持可用。真实快照先通过 `06_stage1.py --mode public`（需官方下载文件）或 `--mode live`（需 neuPrint token）生成，JO seed 动态发现并保留注释审计。token 只在本机环境变量中设置。

```powershell
& $pythonExe scripts/10_run_pipeline.py --snapshot data/processed/malecns_snapshots/YOUR_SNAPSHOT --controls
& $pythonExe scripts/10_run_pipeline.py --snapshot data/processed/malecns_snapshots/YOUR_SNAPSHOT --fem fem/hdf5/test.h5 --calibrate-fem fem/hdf5/train1.h5 fem/hdf5/train2.h5 --controls
# 后续测试复用已冻结的标定
& $pythonExe scripts/10_run_pipeline.py --snapshot data/processed/malecns_snapshots/YOUR_SNAPSHOT --fem fem/hdf5/test2.h5 --calibration outputs/runs/YOUR_RUN/calibration.json --controls
```

外部 FEM 必须提供训练集或已有 calibration。配置总时长和刺激起止时间需匹配数据。FEM 数值契约及研究边界见 [链路说明](docs/PIPELINE_IMPLEMENTATION.md)。

## 产物

父运行保存 `encoder.npz`、`calibration.json`、`comparison.csv`、配置和 manifest；original、rewired、weight_shuffled 各有独立运行目录，保存图快照、固定输入、spikes、latency、raster、graph 和指标。固定输入 SHA-256 必须一致。源码哈希、种子和依赖版本记录在 manifest 中。

离线软件夹具验证目录仍为 `outputs/runs/initial_pipeline_verified`；本轮真实结构实验为 `outputs/runs/malecns_brain_focus_20261003`，可视化在 `outputs/visualizations/malecns_brain_explorer`。synthetic transfer 与负数 ID 图只验证软件；encoder 尚未生理拟合。`real_malecns_acceptance` 保持 false，等待注释功能复核和动力学标定。
