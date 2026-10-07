# 声源 → MaleCNS 全链路实验工作台

本机入口：http://127.0.0.1:8765 。在项目目录运行 `./start_signal_workbench.ps1` 可启动服务并打开 Edge。使用已有 Python 环境 `C:/Users/liyang/.virtualenvs/ear-malecns/Scripts/python.exe`；数据、缓存、浏览器独立配置、导入文件、日志和实验结果均位于 H 盘本项目。服务只监听本机回环地址。

## 先进行一次操作

1. 在“已有可复现实验”选择 250 Hz tone、Pulse IPI 36 ms，或 Assumed w0=2 mV。切换会加载对应真实运行结果并加入本次比较表。
2. 在神经元菜单选择下游细胞，再从“查看入边”选择连接。“定位到事件”会定位到前突触发放之前，进入 0.1 ms/帧慢放。上方拓扑箭头标记显示模型延迟排程，下方同时显示前/后突触膜电压和到达时间。
3. 修改声压、IPI、载频、延迟或网络增益，点击“重新仿真”。按钮会实际调用 Brian2，并新建不可覆盖的实验目录。选择 WAV 时导入前一秒的音频，转单声道和 10 kHz；声压字段是 PCM→Pa 的明确比例。
4. 切换膜电压/发放亮度，拖动 SWC 旋转，滚轮缩放。全部 265 个 SWC 已取得；显示使用每个最多 300 条抽稀线段，原始 SWC 保留完整。
5. “导出离线报告”保存包含数据、真实形态与代码的单文件 HTML，无需网络即可回放；重新计算需本地服务。“保存参数”和“导出比较 CSV”支持记录实验。浏览器关闭后服务继续运行。

第一次打开不需要等待下载或重新计算：预计算条件已经保存在 H 盘。独立离线入口为 `outputs/workbench/index.html`。

## 完整链路及证据边界

|环节|实现|当前边界|
|---|---|---|
|A 声源|tone / pulse / AM / chirp / noise / WAV，载频、幅度、IPI 可调|单点 p(t)，没有三维声场求解|
|B–C 人耳|复用 OpenEar ZETA 真实几何：TM、malleus、incus、stapes 可旋转；全部 13 份 PLY 保存于 fem/geometry|OpenEar 提供几何，不提供本项目已经求解、验证的 FEM 响应。默认机械曲线使用明确标注的参考传递函数替身；已有 FEM 通过 HDF5 导入。几何不冒充 FE 变形|
|D 特征|频谱主频、包络、onset、pulse/IPI、相对幅度|仅包络/适应 M1 驱动编码，载频特征没有被人为变成 JO subtype 生理调谐|
|E–F 编码|固定共享参考集 Q5/Q95，5 ms 包络平滑、10 ms 适应，等效速度与率、65 独立随机事件通道|参考标定和映射为工程假设；测试刺激不单独拟合分位数。默认自发感觉驱动 5 Hz|
|G–H 连接组|MaleCNS v1.0，65 auditory JO-A/B 输入，265 细胞，6,535 定向边，1–2 hop|当前冻结子图；没有声称运行全部 CNS 或第三跳|
|I 电信号|Brian2 单室 LIF，真实结构计数转有符号 ΔV，固定可调延迟；全部 265 细胞记录膜电压|递质为预测，动力学、权重变换和符号先验为假设；没有实测电流、电导模型、多室电缆或 AdEx|
|J–K 展示|全部膜电压、raster、10 ms firing-rate heatmap、首次发放 latency、逐跳活跃、事件表及 265 SWC 同步|SWC 上颜色是模型状态；没有虚构电流沿分支传播。突触到达由真实监测的前突触 spike + 模型延迟导出，不证明某条边单独导致目标放电|
|L / M 约束|界面和运行配置明确区分真实结构、预测递质及假设参数|JON/AMMC 生理拟合、人耳实验验证留待后续接入|

膜方程 `dV/dt = (-60 - V)/tau_m`；达到 −50 mV 后放电并复位 −60 mV，不应期 2 ms。突触事件 `Vpost += w`；`w = sign(NT) × w0 × log1p(structural_count) / median(log1p(count))`。当前 ACh 取正、GABA 取负，未知/其他递质采用配置先验；受体上下文可能改变实际作用。膜电压每 0.2 ms 在仿真步骤结束记录，运行步长 0.1 ms，所以波形不一定保留复位前的阈值尖峰，单独的 spike 标记来自 SpikeMonitor。

## 本轮实际运行结果

|条件|总 spikes|输入活跃 / 65|第一跳活跃 / 100|第二跳活跃 / 100|
|---|---:|---:|---:|---:|
|250 Hz tone|1364|65|29|0|
|150 Hz tone|1384|65|33|1|
|Pulse IPI 15 ms|1243|65|30|0|
|Pulse IPI 36 ms|1097|65|27|0|
|Pulse IPI 72 ms|749|65|29|0|
|Silence + 5 Hz spontaneous sensory drive|15|7|0|0|
|Weight shuffled|1405|65|32|1|
|Assumed w0=2 mV|2024|65|61|22|

所有条件为 1 秒工程仿真，种子 42。较强增益 w0=2 mV 可用于观察两跳活动，但这不是生理拟合，也不是“更正确”的结果。权重打乱和增益实验使用与默认 tone 完全相同的感觉输入 SHA-256。默认第二跳静默是保留的实际结果。模型输出支持软件机制演示，不能据此单独推断听觉生理或真实拓扑优势。

## 接入已有有限元输出

左侧选择“导入已有 FEM HDF5”，上传响应及固定训练/参考集的 `calibration.json`，点击导入，再运行。文件内声源和机械响应会固定，控制面板的声源字段会禁用；可继续调整 encoder 与网络。请求文件上限 20 MB，均匀采样时长 大于 0.4 且不超过 2 秒。

HDF5 必须包含等长有限一维数组：

- `stimulus/time_s`，从 0 开始，秒；
- `stimulus/pressure_Pa`，Pa；
- `fem/tm_displacement_m`，m；
- `fem/stapes_velocity_m_s`，m/s；
- `metadata` 组属性 `sample_rate_hz` 和非空 `fem_version`。

`calibration.json` 需要 `q_low`、`q_high`（有序、有限）、`envelope_tau_ms: 5`，分位数来自同一物理量和单位的共享训练集 log-envelope，不能在每个测试片段上重拟合。可附 `source`、单位、数据版本和训练条件。`outputs/workbench/calibration_demo.json` 仅针对合成参考传递函数，不可直接视为真实 FEM 的标定。导入成功只证明格式/时轴可读，不证明模型材料、边界条件或物理真实性。本轮导入一致性检查使用有明确合成标记的测试文件，未冒充真实 FEM。

若已有频域 FEM，可在外部先用 H(f) 与声源频谱计算对应响应，再导出本格式；不需重建本项目的人耳几何。OpenEar 来源：https://zenodo.org/records/1473724 。MaleCNS 来源：https://male-cns.janelia.org/download/ 。本地下载清单保留远端校验和及 SHA-256。

## 文件与复现

- `scripts/18_signal_workbench.py`：服务及参考案例准备入口；`--prepare` 会产生新一组六条件参考案例并更新列表。
- `src/ear_malecns/signal_workbench.py`：声源、共享标定、真实图 SNN、全电压及事件导出。
- `src/ear_malecns/workbench_server.py`、`workbench_template.html`：本地交互服务和独立报告。
- `scripts/20_fetch_subgraph_skeletons.py`：真实子图全部 SWC 下载/校验。
- `scripts/21_workbench_browser_qa.cjs`：本机 Edge CDP 浏览器检查；调试端口 9226，仅用于测试。
- `scripts/22_verify_workbench_http.py`：导入一致性、同输入权重对照和增益实验。
- `outputs/workbench/experiments/signal_*`：每次运行的 HDF5、固定输入、spikes、逐细胞/逐跳指标、latency、全电压 NPZ、突触到达 parquet、配置、JSON 和 manifest。
- `skeletons/male-cns-v1.0/all_auditory`：265 份真实原始 SWC 与官方校验记录。
- `outputs/workbench/reference_comparison.csv`、`browser_qa.json`、`http_qa.json`：参考比较及实际检查记录。

运行 `python -m pytest tests -q --basetemp=downloads/pytest-workbench` 进行检查。现有环境无需安装新依赖。需要停止本项目服务时，根据 `outputs/workbench/server.json` 的 pid 检查对应进程确为 `18_signal_workbench.py`，再停止该进程；不要结束其他占用端口的程序。
