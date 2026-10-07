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
2. 选择第一跳细胞及入边，点击“定位到事件”，0.1 ms/帧慢放，讲述放电→延迟→ΔV→阈值。查看膜电压和红/橙事件标记。
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

本轮 47 项 Python 检查、9 项原工作台浏览器检查、5 项科研交互检查通过，批次内同输入哈希与零事件稳定性检查通过。浏览器测试需单独启动本机 Edge 调试端口 9226，测试用配置也放 H 盘。

服务日志为 `outputs/workbench/server.stdout.log` 与 `server.stderr.log`；页面不存在科研结果时先运行 23 入口。修改代码后仍见旧页面，用 `-Restart` 并刷新。关闭浏览器不停止服务，前台运行可 Ctrl+C；后台停止须核对 server.json 的 pid 及对应本项目命令。

等 RMS 无法应用到静默声源，也不可独立改变已导入机械响应的声源；不同 IPI 仍可能产生不同编码事件数。置信区间基于计算试次而非果蝇个体，不能将每个神经元当成独立样本。
