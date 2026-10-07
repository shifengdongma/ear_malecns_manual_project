# 用户手册

2026-10-07 更新：[程序启动与使用手册](STARTUP_AND_USAGE.md) · [科研协议与论文设计](RESEARCH_PROTOCOL.md) · [更新链路图](research-pipeline.svg)。新增等 RMS 控件、65 次配对先导实验与中文术语解释，启动脚本支持 `-Research`、`-Restart`、`-PythonExecutable`。

## 本机使用

项目目录为 `H:/基于人耳有限元机械响应与果蝇听觉连接组的跨物种机械感觉编码联合仿真框架/ear_malecns_manual_project`。现有环境为 `C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe`，当前已安装运行依赖；无需为启动再次安装环境。

在项目目录 PowerShell 运行：

```powershell
./start_signal_workbench.ps1
```

脚本复用已运行的本项目服务或启动服务，并打开 Edge。入口 **http://127.0.0.1:8765**。日志、缓存、浏览器独立配置和结果都保存在 H 盘。需要手动前台启动可执行：

```powershell
$pythonExecutable = 'C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe'
& $pythonExecutable scripts/18_signal_workbench.py --port 8765
```

## 一次完整观察

1. 选择预计算 250 Hz tone，观察声压、频谱、OpenEar 几何、机械响应及编码率。
2. 选择下游细胞，从“查看入边”选择连接，点击“定位到事件”。
3. 点击播放，以 0.1 ms/帧观察前突触发放、延迟到达、目标膜电压变化；红线是实际模型 spike，橙色标记是选中边到达。
4. 切换“膜电压状态/发放亮度”，拖动 SWC 旋转，滚轮缩放；形态范围可选全部、输入+第一跳、选中及入边来源。
5. 切换 Pulse IPI 15/36/72 ms 或修改声源后“重新仿真”。参数不是只改变动画，按钮会实际运行 Brian2 并创建新实验目录。
6. 观察底部条件比较；使用 Weight shuffled 查看结构权重对照，Assumed w0=2 mV 查看假设增益下的两跳活动。比较前核对感觉输入哈希。

控制范围：载频 50–500 Hz，声压 0–4 Pa，IPI 10–100 ms，延迟 0.1–5 ms，w0 0–2 mV，膜时间常数 5–40 ms。当前不同刺激共享固定参考标定。静默条件仍有默认 5 Hz 自发感觉驱动，所以不要求网络绝对零放电。

选择 WAV 时上传音频，系统取前一秒，转单声道并重采样 10 kHz；短文件补零。声压幅度是 PCM→Pa 比例，试听仅调整音量，不改变计算输入。参数和映射都是工程假设，不把试听音量当真实物理标定。

## 导入已有 FEM

机械层选择“导入已有 FEM HDF5”，上传响应和共享 `calibration.json` 后点击导入，再运行。文件内声源与机械响应固定，可调整 encoder 和网络。HDF5 要包含：

|路径/属性|内容|
|---|---|
|`stimulus/time_s`|从 0 开始的均匀秒时间轴|
|`stimulus/pressure_Pa`|声压，Pa|
|`fem/tm_displacement_m`|鼓膜位移，m|
|`fem/stapes_velocity_m_s`|镫骨速度，m/s|
|`metadata` 属性 `sample_rate_hz`|正采样率|
|`metadata` 属性 `fem_version`|来源和版本|

四个数组必须等长、有限、一维；响应限制 20 MB、大于 0.4 且不超过 2 秒。标定含 `q_low`、`q_high`、`envelope_tau_ms: 5`，来自同物理量与单位的共享训练/参考集。合成演示的 `calibration_demo.json` 不可直接当真实 FEM 标定。

OpenEar 提供真实解剖几何；默认机械曲线是已打标的参考传递函数演示，并非求解后的 OpenEar FEM。格式导入成功也不代表物理验证。无需重建人耳研究，可直接接已有模型输出。

## 保存与复现

- “保存参数”：下载本次参数/config/来源/感觉输入哈希。
- “导出比较 CSV”：导出本次浏览加载的条件对比。
- “导出离线报告”：下载自包含 HTML，并在实验目录保存 `visual_report.html`；离线可回放，重算需启动服务。
- 本机已有离线入口：`outputs/workbench/index.html`。
- 每次真实运行产物：`outputs/workbench/experiments/signal_*`，含固定输入、全电压、spikes、突触到达、统计及校验清单。

关闭浏览器不会停止后台服务。停止前核对 `outputs/workbench/server.json` 中 pid 对应的命令确为本项目 `18_signal_workbench.py`，再停止该进程；前台运行可 Ctrl+C。

## 从 GitHub 恢复代码

仓库是代码与文档版本，不包含原始数据、OpenEar 模型、SWC、Python 环境和生成报告。克隆位置也应在 H 盘：

```powershell
git clone git@github.com:shifengdongma/ear_malecns_manual_project.git
```

在新环境按 `requirements.txt`/`pyproject.toml` 安装依赖；包下载缓存放 H 盘。启动脚本默认寻找已有 ear-malecns 环境，其他环境可用前台 Python 入口。真实数据可复用本机已校验目录，或重新运行以下入口：

```powershell
$pythonExecutable = 'C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe'
& $pythonExecutable scripts/08_download_public.py
& $pythonExecutable scripts/06_stage1.py --mode public --config configs/pipeline_real_demo.yaml --run-id real_public_fixed_20261003
& $pythonExecutable scripts/11_prepare_openear.py --download
& $pythonExecutable scripts/20_fetch_subgraph_skeletons.py
```

上述命令用于全新克隆：`06_stage1.py` 创建工作台要求的冻结目录并运行一次固定输入实验；已有同名快照时请直接复用，不再次创建。`20_fetch_subgraph_skeletons.py` 没有 `--help`，执行即下载/核验 SWC。先阅读 `SIGNAL_WORKBENCH_GUIDE.md`、`data_sources.md`，恢复真实冻结图与模型后再准备工作台案例。下载入口会产生较大的官方文件；环境包和这些文件均不纳入 Git。

```powershell
& $pythonExecutable scripts/18_signal_workbench.py --prepare
& $pythonExecutable -m pytest tests -q --basetemp=downloads/pytest-workbench
```

`--prepare` 更新六组基础参考案例列表；本机额外权重/增益条件的验收入口为 `scripts/22_verify_workbench_http.py`。没有真实图/SWC/OpenEar 时启动失败属于依赖数据未恢复，不能拿合成图冒充真实图。

## 常见问题与维护

- 页面无法访问：启动脚本，检查 `server.stdout.log`/`server.stderr.log` 与端口；不能为释放端口结束其他程序。
- 一次运行失败：错误显示在控制面板，读取日志并保留失败目录；不要覆盖成功实验。
- 第二跳没有活动：这是当前条件的可能结果；可查看膜电压及输入，勿把提高增益当成生理验证。
- 波形未显示阈值尖峰：电压每步结束记录、放电立即复位；红色 spike 标记来自独立监测。
- 选中边到达却不发放：膜电压受所有入边、衰减及不应期共同影响。

后续更新由四份核心文档共同维护：日志记录过程，总结反映现状，架构记录接口和实现，手册记录实际操作。后续代码变更完成后，助手需先提供可审查的结果，再询问是否上传 GitHub；没有明确同意不执行 push。本轮首次上传已经明确授权。

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
