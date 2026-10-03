# 用户手册

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

四个数组必须等长、有限、一维；响应限制 20 MB、0.4–2 秒。标定含 `q_low`、`q_high`、`envelope_tau_ms: 5`，来自同物理量与单位的共享训练/参考集。合成演示的 `calibration_demo.json` 不可直接当真实 FEM 标定。

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
