# 项目程序启动与使用手册（2026-10-07）

## 本机一键启动

PowerShell 中执行：

```powershell
Set-Location -LiteralPath 'H:/基于人耳有限元机械响应与果蝇听觉连接组的跨物种机械感觉编码联合仿真框架/ear_malecns_manual_project'
./start_signal_workbench.ps1
```

打开 http://127.0.0.1:8765 。数据、缓存、浏览器独立配置和产物全部保存在 H 盘，复用现有 Python 环境。直接打开科研报告：

```powershell
./start_signal_workbench.ps1 -Research
```

升级源码后，在确认没有正在执行的任务时显式重启：

```powershell
./start_signal_workbench.ps1 -Restart -Research
```

其他环境可指定 `-PythonExecutable '你的 python.exe 路径'`；其他端口用 `-Port 8865`，只开服务用 `-NoBrowser`。重启只检查并停止 server.json 指向、命令匹配本项目入口的进程，不结束其他程序。

## 十分钟完整演示

1. 选择 250 Hz tone，讲述 A–F：声压、机械适配、包络和 65 通道编码。
2. 选择第一跳细胞及入边，点击“定位到事件”，1 ms/秒慢放，讲述放电→延迟→ΔV→阈值。查看膜电压和红/橙事件标记。
3. 在 SWC 视图拖动旋转/滚轮缩放，说明真实形态与模型状态的区别。
4. 选择 pulse IPI 36 ms，勾选“等 RMS 声压控制”，目标 0.5 Pa，点击重新仿真。界面显示实际有效幅度；勾选时峰值幅度字段禁用，避免将 RMS 控制与峰值幅度混用；导入已有 FEM 时不能单独缩放声源而保持机械响应不变。
5. 打开“科研对照与术语解释”的科研报告入口；切换结构/时序、等 RMS、增益组别及指标。蓝点为每次运行，橙点和竖线为均值和探索性区间。
6. 打开原始试次表、导出 CSV；解释为什么图中有差异仍不等于真实生理结论。

JON 是触角机械感觉细胞，AMMC/WED 是听觉处理脑区；IPI 是脉冲起始间隔；RMS 是有效幅度；LIF 是漏电积分发放；SWC 是分支形态。界面内有可展开中文解释，更完整的模型/论文依据见 `RESEARCH_PROTOCOL.md`。

## 重新生成科研实验

在上述项目目录中：

```powershell
$pythonExecutable = 'C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe'
& $pythonExecutable scripts/23_run_research.py
```

默认协议为 `configs/research_pilot.json`，5 种子 × 13 条件 = 65 次，串行运行 Brian2。也可复制协议再指定 `--protocol configs/自定义协议.json`，至少两个互异种子；建议先小样本验证，再增加种子数。

进度逐次输出，每次创建新的 `outputs/research/research_*`，不覆盖历史。`latest.json` 指向最新完成结果。若中途失败，已完成试次与 trials.csv 保留，但不会更新 latest 为失败批次。批量模式只保存 spikes 与统计，不记录全电压；单连接电压解释用工作台。

协议固定 1 秒、200–800 ms 分析窗口。内置报告的三组图依赖现有 condition 名称；修改/删除条件或增加其他研究设计时须同步修改报告图组和验证规则，不要把当前生成器当作任意协议通用解析器。

## 产物如何使用

|文件|用途|
|---|---|
|`index.html`|自包含交互科研报告，直接双击离线打开|
|`research_summary.png/.svg`|论文图；SVG 可编辑、放大|
|`trials.csv`|每种子原始试次与输入哈希|
|`summary.csv`|均值、标准差、区间|
|`paired_effects.csv`|逐种子配对差值及区间|
|`protocol.json`、`calibration.json`|精确协议与固定参考标定|
|`stimuli/*.h5`|本批次实际声源和演示机械输出|
|`trials/*/input.npz`、`spikes.parquet`|可追溯输入和模型响应|
|`controls/*`、`manifest.json`|对照图、校验和、代码/依赖证据|

离线主工作台为 `outputs/workbench/index.html`，科研报告路径见 `outputs/research/latest.json`。已有 FEM 导入格式和数据恢复步骤见 `user-manual.md`。Git 仓库不含这些原始模型/结果；重新克隆须恢复 H 盘真实数据。

## 验证、停止与常见问题

```powershell
& $pythonExecutable -m pytest tests -q --basetemp=downloads/pytest-research
```

科研先导迭代 47 项 Python 检查、9 项原工作台浏览器检查、5 项科研交互检查通过，批次内同输入哈希与零事件稳定性检查通过。浏览器测试需单独启动本机 Edge 调试端口 9226，测试用配置也放 H 盘。

服务日志为 `outputs/workbench/server.stdout.log` 与 `server.stderr.log`；页面不存在科研结果时先运行 23 入口。修改代码后仍见旧页面，用 `-Restart` 并刷新。关闭浏览器不停止服务，前台运行可 Ctrl+C；后台停止须核对 server.json 的 pid 及对应本项目命令。

等 RMS 无法应用到静默声源，也不可独立改变已导入机械响应的声源；不同 IPI 仍可能产生不同编码事件数。置信区间基于计算试次而非果蝇个体，不能将每个神经元当成独立样本。

## 链路定位与协同响应操作（2026-10-07）

升级后执行 `./start_signal_workbench.ps1 -Restart -Research`，打开 http://127.0.0.1:8765/research 。点击 A 声源、B–C 机械层、D 特征、E–F 编码、G–H 结构或 I 突触：报告展开工作台并定位对应面板；直接在工作台改参数/选细胞，报告顶部也标出相应环节。点击“统计与对照”回到批量统计。“打开独立工作台窗口”适合大屏演示。

1. 修改声源/刺激参数，链路高亮显示当前位置和受影响层，“参数待运行”提示说明当前响应还是旧实验。点击“重新仿真”，成功后所有视图切换到新的冻结实验。服务不提供细分进度，因此计算中不会动画伪造 A→K 执行步骤。
2. 点击 J–K 或“从刺激起点联动播放”，同时观察局部声压/包络/编码、20 ms 感觉与逐跳事件数、10 ms 逐跳放电率、真实拓扑亮线和 SWC 整细胞闪光。原图中第二跳可能无放电，应如实解释。无声时可有预设背景感觉输入。
3. 点击总览拓扑中的细胞，选中状态、SWC、入边、膜电压和增量说明共同切换。总览 SWC 可拖动旋转/滚轮缩放，与详细视图共用视角；“形态范围”仍在详细 SWC 面板。
4. 点击“导览活跃突触事件”，自动选择刺激期真实模型边并慢放；四格依次说明前突触放电、延迟排程、目标到达 ΔV 与随后 8 ms 内的目标 spike。导览锁定同一事件，避免播放中跳换解释对象。没有合适活动时直接提示，不生成假事件。
5. 拖动统一时间滑块会暂停并刷新全部视图，raster / heatmap 游标也随之移动。“定位到事件”和表格行定位可用于手动检查，之后点击播放。速度为 50 / 1 / 10 ms 模拟时间每秒，结束自动停播；模拟时间不是现实声播放的时间。
6. 导出离线报告后，无需服务即可联动回放；参数重算/参考案例切换禁用。在线单次新结果不自动加入旧 65 次统计；要增加批量研究需另跑研究协议。

JO 是感觉输入细胞，hop 是结构边层数；spike 是模型放电，ΔV 是突触事件在模型中施加的电压增量。颜色和形态中心闪光用于展示整细胞状态，不能当作实测电流、胞体位置或 SWC 空间传导。所有入边累计增量不能直接等同于目标净电压，单边到达与随后放电也不是单边因果证据。

HTTP 科研报告使用当前模板和原冻结统计；历史批次 index.html 保留生成时的版本。当前界面离线副本为 `outputs/research/interactive-current.html`，文件方式只能导航说明和统计；单次活动离线回放在 `outputs/workbench/index.html`。本轮检查证据为 `outputs/workbench/sync_browser_qa.json` 和 `sync_overview_preview.png`，全部留在 H 盘。

本次链路协同升级通过 49 项 Python 检查和 14 项联动浏览器检查，包含 720 px 窄屏和离线科研报告边界检查。联动浏览器脚本为 `scripts/25_sync_browser_qa.cjs`，需独立 headless Edge CDP 端口 9227；仅供开发验收，日常启动不需浏览器调试端口。
