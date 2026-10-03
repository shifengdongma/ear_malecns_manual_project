# 外部声场—人耳有限元—MaleCNS v1.0—SNN 初版技术操作路线手册

> 版本：v0.1（个人开发 / 可复现实验优先）  
> 目标：让计算机专业学生从一台普通工作站开始，在不依赖湿实验和全 CNS 仿真的前提下，搭建一个可以运行、检查、替换模块和继续扩展的最小闭环。

---

## 0. 先把研究问题说准确

### 0.1 本项目不是“人耳把声音送给果蝇大脑”

**必须固定的科学边界：**

```text
外部声场
  ↓
人耳有限元模型
  ↓
人耳机械响应
  ↓
提取物种相对通用的时频/时间结构特征
  ↓
显式的人工 cross-species encoder
  ↓
等效 JON-compatible drive（rate / spike / current）
  ↓
MaleCNS v1.0 中重建的 JO sensory axons / central projections
  ↓
MaleCNS 真实连接拓扑约束的神经动力学模型
  ↓
模拟活动传播与可视化
```

**不能写成：**

- “MaleCNS 直接接收鼓膜位移”；
- “果蝇大脑接收到人类耳蜗电信号”；
- “Google/Janelia 开源了可以运行的果蝇数字大脑”；
- “彩色 3D 动画是真实电流在脑中传播”。

**建议论文表述：**

> 基于人耳有限元机械表征与 MaleCNS v1.0 连接组约束神经网络的跨物种声学—神经计算框架。

### 0.2 什么信息优先保留

第一版只保留以下信息：

```text
frequency / spectrum
relative amplitude
amplitude envelope
onset / offset
pulse timing
IPI (inter-pulse interval)
modulation rate
```

这些比 TM 绝对位移、stapes 绝对速度或 BM 的人类 tonotopic 坐标更适合作为跨物种接口变量。

| 人耳/声学量 | 第一版是否传递 | 做法 |
|---|---:|---|
| 频率 | 是 | 公共频带先保持真实 Hz |
| envelope | 是 | Hilbert + 平滑 |
| onset/offset | 是 | 保留时间位置 |
| IPI / pulse structure | 强烈建议 | 不做时间压缩 |
| modulation | 是 | 保留 |
| relative intensity | 是 | 数据集级归一化后映射 |
| 绝对 Pa | 不直接 | 仅作为外部声学输入/标定量 |
| TM 绝对位移 | 不直接 | 用于 FEM 验证或特征提取 |
| stapes 绝对速度 | 不直接 | 可作为 encoder 原始波形 |
| BM 位置 | 不一一映射 | 转为频带能量/时频表示 |

---

# 1. 最小目标与阶段验收

## 1.1 第一阶段不要做全 CNS

建议规模：

| 版本 | 神经元目标 | 用途 |
|---|---:|---|
| Debug | 100–300 | 第一次闭环 |
| PoC | 500–1500 | 核心实验 |
| Extended | 1500–3000 | 网络统计/论文扩展 |
| Large | 3000–10000 | 后期性能/拓扑实验 |
| Whole CNS | 166k 量级 | 不作为个人项目 MVP |

第一阶段正式验收只要求：

```text
动态发现 JO-A / JO-B
  ↓
提取 1–2 hop MaleCNS 子图
  ↓
100–300 neuron LIF
  ↓
固定 sensory spike input
  ↓
raster + latency + graph
```

第二阶段再加入：

```text
250 Hz / pulse stimulus
  ↓
JON-compatible encoder
  ↓
MaleCNS
```

第三阶段才加入：

```text
Human-ear FEM
  ↓
encoder
  ↓
MaleCNS
```

---

# 2. 硬件资源

## 2.1 推荐个人工作站

**最低可开始：**

```text
CPU: 6–8 cores
RAM: 16 GB
SSD: 500 GB
GPU: 不要求
```

**推荐配置：**

```text
CPU: 8–12 cores
RAM: 32 GB
SSD: 1 TB NVMe
GPU: 可无；有 NVIDIA GPU 只对后期 ML/UQ/渲染更有帮助
```

这套配置足以完成：

- neuPrint 查询；
- 100–3000 neuron 子图；
- Brian2 LIF；
- 数十至数百条 SWC；
- Python 图分析；
- HDF5 接口；
- 基础参数扫描。

## 2.2 如果做真实 3D 人耳 FEM

真实 FEM 往往比 300 neuron SNN 更耗资源。

建议：

```text
16–32 CPU cores
64–128 GB RAM
1–2 TB NVMe
```

如果学校有 COMSOL/ANSYS/HPC，优先使用现有条件，不要为了“全开源”重新实现成熟的人耳模型。

---

# 3. 软件栈与为什么这样选

| 层 | 软件 | 作用 |
|---|---|---|
| OS | Windows 11 + WSL2 Ubuntu / 原生 Ubuntu | Linux 科研生态最稳定 |
| 环境 | Conda/Miniconda | 隔离 Python 依赖 |
| MaleCNS | neuPrint + neuprint-python | 查询真实连接组 |
| 数据 | pandas + pyarrow | Feather/Parquet |
| 图 | NetworkX | 100–3000 node PoC 足够 |
| 神经 | Brian2 | 方程透明、Python 友好 |
| 信号 | NumPy + SciPy | waveform / filter / Hilbert |
| 数据接口 | HDF5/h5py | FEM → encoder 标准接口 |
| 3D | navis + PyVista | SWC / morphology |
| FEM 快速路线 | COMSOL/ANSYS/已有模型 | 实际人耳模型 |
| FEM 开源路线 | 3D Slicer + Gmsh + FEniCSx | 后期可复现扩展 |

**为什么不把 FlyBrainLab 当主实现？**  
本项目的数据核心是 2026 MaleCNS v1.0。最透明、最容易调试的第一版是：

```text
neuPrint → pandas → NetworkX → Brian2 → navis/PyVista
```

---

# 4. Windows 11 + WSL2 从零搭环境

> 如果你已经有可用 Ubuntu，可直接跳到 4.3。

## 4.1 Windows 管理员 PowerShell

检查：

```powershell
wsl --status
wsl --list --verbose
```

若没有 WSL：

```powershell
wsl --install
```

安装一个 Ubuntu 发行版后重启 Windows，再运行：

```powershell
wsl --list --verbose
```

确认目标发行版的 VERSION 为 2。

## 4.2 进入 Ubuntu

```powershell
wsl
```

Linux 中：

```bash
cat /etc/os-release
uname -a
```

## 4.3 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  git \
  curl \
  wget \
  ca-certificates \
  pkg-config \
  libgl1 \
  libglu1-mesa \
  libxrender1 \
  libxext6 \
  libsm6
```

说明：

- `build-essential`：Brian2 C++ standalone 后期需要编译器；
- OpenGL 相关库：PyVista/navis 某些渲染环境可能需要；
- `git/curl/wget`：获取代码和数据。

## 4.4 安装 Miniconda

可从官方 Miniconda 页面下载 Linux x86_64 安装器，然后：

```bash
bash Miniconda3-latest-Linux-x86_64.sh
```

按提示执行 `conda init`，重新打开 shell：

```bash
conda --version
python --version
```

---

# 5. 建立项目

假设目录：

```bash
mkdir -p ~/research
cd ~/research
```

把本交付包解压后：

```bash
cd ear_malecns_manual_project
```

检查：

```bash
find . -maxdepth 2 -type f | sort
```

推荐初始化 Git：

```bash
git init
git add .
git commit -m "Initial ear-MaleCNS research scaffold"
```

---

# 6. Python 环境

## 6.1 推荐：environment.yml

```bash
conda env create -f environment.yml
conda activate ear-malecns
```

开发模式安装本项目：

```bash
pip install -e .
```

验证：

```bash
python -c "import numpy, pandas, scipy, networkx, brian2; print('base packages OK')"
python -c "import neuprint; print('neuprint OK')"
```

## 6.2 跑本地测试

先安装 pytest：

```bash
pip install pytest
pytest -q
```

这些测试完全不访问 MaleCNS，目的是先确认：

```text
stimulus
→ synthetic transfer
→ feature
→ rate
→ spikes
```

的数组长度、范围、数值接口没有低级错误。

---

# 7. 第一次离线跑通：无需 neuPrint、无需真实 FEM

执行：

```bash
python scripts/00_selftest.py
```

预期输出类似：

```text
Self-test FEM: .../selftest_fem.h5
Encoder spikes: ...
PASS: stimulus -> synthetic transfer -> encoder
```

## 7.1 这里的 synthetic transfer 是什么

`synthetic_transfer_response()` 使用一个阻尼二阶传递函数作为**程序自检替身**。

它不是：

- OpenEar；
- COMSOL 人耳；
- 生理真实中耳；
- 可以发表的人耳结果。

它只解决一个软件工程问题：

> 在真正 FEM 还没准备好时，后面的 HDF5、encoder、SNN 是否可以独立开发？

这样能把复杂系统拆开调试。

---

# 8. neuPrint 账号与 token

## 8.1 注册并获取 token

访问 MaleCNS/neuPrint 官方站点，登录后获取 API token。

不要把 token 写进 Git。

Linux/WSL 当前 shell：

```bash
export NEUPRINT_APPLICATION_CREDENTIALS="YOUR_TOKEN"
```

检查：

```bash
python -c "import os; print(bool(os.getenv('NEUPRINT_APPLICATION_CREDENTIALS')))"
```

Windows PowerShell（如果原生 Windows Python）：

```powershell
$env:NEUPRINT_APPLICATION_CREDENTIALS="YOUR_TOKEN"
```

## 8.2 第一次连接 MaleCNS

```bash
python scripts/01_connect_neuprint.py
```

本工程固定：

```text
server = https://neuprint.janelia.org
dataset = male-cns:v1.0
```

成功标准：Client 创建成功，并能向该 dataset 发请求。

---

# 9. 动态发现 auditory JON，而不是写死 body ID

执行：

```bash
python scripts/02_discover_jons.py
```

输出：

```text
data/processed/auditory_input_cells.csv
```

## 9.1 理论解释

Johnston's organ 是触角中的 mechanosensory organ。MaleCNS 是 CNS EM volume，所以这里的 JON 更准确理解为：

> 已被追踪进入 CNS 的 sensory axons / central projections。

不是“完整触角外周器官都在 MaleCNS 里”。

## 9.2 为什么用 regex

初版候选：

```regex
^JO-(A[1-4]|B[1-4])(?:_[abc])?$
```

目的：

- 运行时从当前 `male-cns:v1.0` 得到 body ID；
- 不复制别的数据集旧 ID；
- 生成 CSV 后进行**版本冻结**。

必须人工检查：

```bash
head -n 20 data/processed/auditory_input_cells.csv
```

论文方法中保存这个 CSV。

---

# 10. 提取 1–2 hop auditory subgraph

执行：

```bash
python scripts/03_extract_subgraph.py
```

默认配置：

```yaml
hops: 2
min_weight: 5
max_new_nodes_per_hop: 150
```

输出：

```text
data/processed/auditory_subgraph_v1/
├── nodes.parquet
├── edges.parquet
└── auditory_subgraph.graphml
```

## 10.1 `min_weight=5` 的正确解释

它只是**计算裁剪起点**，不是生理阈值。

错误：

> “少于 5 个突触没有功能。”

正确：

> “为控制 PoC 子图规模，第一版以连接突触数阈值 5 做结构筛选，并在后续对阈值做敏感性分析。”

## 10.2 `local_input_fraction` 的限制

代码会给探索性结果计算：

\[
q_{ij}^{local}=\frac{n_{ij}}{\sum_{k\in subgraph} n_{kj}}
\]

但这不是论文级完整 input-normalized strength。

论文版分母应是 B 神经元的**全局总输入**：

\[
q_{ij}=\frac{n_{ij}}{\sum_{k\in MaleCNS}n_{kj}}
\]

因此代码把字段明确命名为 `local_input_fraction`，防止误读。

---

# 11. MaleCNS 拓扑如何变成 SNN

## 11.1 MaleCNS 不提供完整动力学

结构连接组只提供强大的结构先验：

```text
谁连谁
连接数量
位置/ROI
部分神经递质预测
形态
```

不会自动提供每个细胞的：

- 膜电容；
- 阈值；
- 离子通道；
- receptor subtype；
- release probability；
- 精确 conduction delay。

因此第一版 LIF 是**一阶计算近似**。

## 11.2 LIF 方程

\[
\tau_m\frac{dV}{dt}=E_L-V
\]

达到阈值：

\[
V\ge V_{th}
\]

触发 spike，再 reset。

默认工程先验：

```text
tau_m = 20 ms
E_L = -60 mV
V_th = -50 mV
V_reset = -60 mV
refractory = 2 ms
delay = 1.5 ms
```

这些参数**不是 MaleCNS 逐细胞实测值**，必须归类为 `assumed`，并做扫描。

## 11.3 synapse count 不是 mV/nS

本工程默认：

\[
w_{ij}=s_{ij} w_0
\frac{\log(1+n_{ij})}
{median_E[\log(1+n)]}
\]

原因：

- `n_ij` 是 EM 结构连接数；
- 直接线性放大容易使强边支配全网；
- log 仅是工程映射；
- `w0` 是必须扫描/拟合的 gain。

## 11.4 neurotransmitter sign

当前代码仅把：

```text
GABA -> inhibitory prior
ACh -> excitatory prior
其他/未知 -> uncertain prior
```

这不是“受体上下文已确定”。论文版应做至少两个 uncertain-sign 情景。

---

# 12. 第一次 SNN 运行

前置条件：

```bash
python scripts/00_selftest.py
python scripts/02_discover_jons.py
python scripts/03_extract_subgraph.py
```

然后：

```bash
python scripts/04_run_snn.py
```

输出：

```text
outputs/run_001/
├── spikes.parquet
├── raster.png
└── latency.csv
```

## 12.1 成功标准

不是“越多 spike 越好”。

必须同时满足：

1. 无输入时不应无限自激；
2. 刺激期至少能激活输入/部分 downstream；
3. 不能 1–2 ms 内整个网络全部饱和；
4. 停止刺激后活动应合理衰减；
5. 参数变化不能轻易把结论完全翻转。

## 12.2 如果完全不发放

优先检查：

```yaml
snn:
  input_weight_mv: 2.0
  w0_mv: 0.5
```

逐步增加，而不是直接改几十倍。

建议扫描：

```text
w0 × {0.25, 0.5, 1, 2, 4}
input weight × {0.5, 1, 2}
```

## 12.3 如果全网爆发

降低：

- `w0_mv`；
- `input_weight_mv`；
- encoder gain / r_max；

或增加：

- inhibition；
- threshold；
- refractory。

不要通过删除“不好看的”神经元来得到漂亮结果。

---

# 13. 外部声场输入

## 13.1 第一批刺激

建议：

```text
100, 150, 200, 250, 300, 350, 400 Hz
```

以及 pulse temporal structure：

```text
IPI = 15, 24, 36, 48, 72 ms
```

第一版不要从完整 20 Hz–20 kHz 开始。

## 13.2 生成 tone

工程代码：

```python
from ear_malecns.stimulus import gated_tone

t, p = gated_tone(
    frequency_hz=250,
    fs_hz=10000,
    duration_s=1.0,
    amplitude=1.0,       # 可解释为 1 Pa 的校准输入
    onset_s=0.2,
    offset_s=0.8,
)
```

## 13.3 生成 pulse-song-like stimulus

```python
from ear_malecns.stimulus import pulse_song_like

t, p = pulse_song_like(
    carrier_hz=275,
    ipi_ms=36,
    fs_hz=10000,
    duration_s=1.0,
)
```

注意：这是受文献启发的可控 stimulus，不等于完整天然 courtship song。

---

# 14. 真实人耳 FEM：推荐实现顺序

## 14.1 第一版建模边界

优先：

```text
ear canal
→ tympanic membrane
→ ossicles
→ stapes
```

有成熟模型再加：

```text
cochlear fluid
→ BM(x,f)
```

## 14.2 为什么频域优先

求传递函数：

\[
H_{TM}(f)=\frac{u_{TM}(f)}{p_{in}(f)}
\]

\[
H_{stapes}(f)=\frac{v_{stapes}(f)}{p_{in}(f)}
\]

有内耳时：

\[
H_{BM}(x,f)=\frac{u_{BM}(x,f)}{p_{in}(f)}
\]

对任意输入：

\[
Y(f)=H(f)X(f)
\]

再 IFFT 得到时域波形。

优点：一次昂贵 sweep 可复用到许多刺激，而不是每条音频重新做 transient FE。

---

# 15. FEM 路线 A：已有 COMSOL/ANSYS/其他 FE 模型

这是最推荐的现实路线。

## 15.1 至少导出

```text
time_s
input pressure_Pa
tm_displacement_m
stapes_velocity_m_s
sample_rate_hz / frequency grid
model version
```

不要把几百万网格节点直接交给 SNN。

## 15.2 标准 HDF5

```text
fem_output.h5
├── /stimulus/time_s
├── /stimulus/pressure_Pa
├── /fem/tm_displacement_m
├── /fem/stapes_velocity_m_s
└── /metadata
```

Python 写入接口已经在：

```text
src/ear_malecns/fem_io.py
```

如果 COMSOL/ANSYS 只能先导出 CSV，做一层转换即可。

## 15.3 CSV 转 HDF5 示例

```python
import pandas as pd
from ear_malecns.fem_io import write_fem_h5

df = pd.read_csv("comsol_export.csv")
write_fem_h5(
    "data/processed/fem_output.h5",
    time_s=df["time_s"].to_numpy(),
    pressure_pa=df["pressure_Pa"].to_numpy(),
    tm_displacement_m=df["tm_displacement_m"].to_numpy(),
    stapes_velocity_m_s=df["stapes_velocity_m_s"].to_numpy(),
    sample_rate_hz=10000,
    fem_version="comsol_model_v1",
)
```

---

# 16. FEM 路线 B：完全开源

推荐链：

```text
OpenEar
→ 3D Slicer
→ geometry cleanup
→ Gmsh
→ FEniCSx/PETSc
→ HDF5
```

## 16.1 这里为什么不能给出“真实完整人耳 FEM 一键代码”

当前研究材料没有提供：

- 你最终选中的 OpenEar specimen；
- 清理后的几何；
- TM/韧带/关节实体或 shell 定义；
- 材料参数集；
- 耳蜗终端阻抗；
- 边界 tag；
- mesh convergence 结果。

因此任何声称“一段通用 Python 就是完整人耳 FEM”的代码都会是假精确。

本手册提供的是：

1. 可运行的全链软件骨架；
2. FEM 的严格输入/输出契约；
3. 开源 solver 的接入位置；
4. 真实模型建立后无需修改下游模块。

## 16.2 FEniCSx 建议独立环境

FEniCSx/PETSc 与主 Python 环境的 MPI/系统依赖较多，建议单独环境或 Docker，不要第一天和 Brian2/pyvista 混装后一起排错。

先把主链跑通，再建立：

```text
ear-fem
```

独立环境。

---

# 17. FEM → JON-compatible encoder

## 17.1 选择输入波形

第一版可选：

\[
y_h(t)=v_{stapes}(t)
\]

它只是 encoder 原始信号，**不是 JON 直接感受到的物理量**。

## 17.2 envelope

\[
e(t)=LPF(|\mathcal H[y_h(t)]|)
\]

其中 `Hilbert transform` 得到 analytic signal，模长用于 envelope。

## 17.3 robust normalization

\[
z(t)=clip\left(
\frac{\log(e+\epsilon)-Q_5}{Q_{95}-Q_5},0,1
\right)
\]

**论文实验必须：**

- 用训练/校准 stimulus set 统一计算 Q5/Q95；
- 测试刺激复用同一参数；
- 不能每条声音各自 min-max，否则会抹掉真实强弱差异。

## 17.4 JON surrogate

本工程实现了一个简单 adaptation surrogate：

\[
\tau_a \dot a=z-a
\]

再将适应后的 drive 映射为 firing rate。

默认：

```text
adaptation_tau = 10 ms
scan = 5–20 ms
```

只有将参数真正拟合到公开 JON physiology 后，才能称为 `physiology-fitted encoder`。

## 17.5 Poisson spikes

离散步长：

\[
P(spike)=r(t)\Delta t
\]

建议把生成的 spike times 保存：

```text
stim_250Hz_seed42.npz
```

之后所有网络参数实验重复使用同一 sensory input，防止 Poisson 随机差异干扰比较。

---

# 18. 为什么第一版应先固定 spike 输入

如果每次重跑网络都重新随机生成 spike：

```text
network parameter effect
+
input sampling noise
```

会混在一起。

因此正式实验流程：

```text
stimulus
→ encoder
→ 固定 spike file
→ real graph
→ rewired graph
→ 参数扫描
```

这样拓扑实验更公平。

---

# 19. Skeleton 与 3D 可视化

## 19.1 下载少量 skeleton

执行：

```bash
python scripts/05_fetch_skeletons.py
```

默认只取前 20 个，用于验证接口。

不要第一版同时渲染 3000 个完整 skeleton。

推荐：

```text
全部节点 -> graph/raster/heatmap
关键 50–200 cells -> 3D morphology
```

## 19.2 活动映射

定义模拟活动：

\[
a_i(t)=\sum_k \exp[-(t-t_{ik})/\tau_v] H(t-t_{ik})
\]

然后把 `a_i(t)` 映射到 body ID 对应 SWC 的颜色/透明度。

必须标注：

> simulation-derived activity over MaleCNS morphology

不能标注：

> measured electrical propagation

---

# 20. 完整运行顺序

## 20.1 第一次：纯离线

```bash
conda activate ear-malecns
pip install -e .
pytest -q
python scripts/00_selftest.py
```

验收：encoder `.npz` 生成。

## 20.2 第二次：接 MaleCNS

```bash
export NEUPRINT_APPLICATION_CREDENTIALS="YOUR_TOKEN"
python scripts/01_connect_neuprint.py
python scripts/02_discover_jons.py
python scripts/03_extract_subgraph.py
```

验收：

```text
auditory_input_cells.csv
nodes.parquet
edges.parquet
auditory_subgraph.graphml
```

## 20.3 第三次：SNN

```bash
python scripts/04_run_snn.py
```

验收：

```text
raster.png
spikes.parquet
latency.csv
```

## 20.4 第四次：3D 数据

```bash
python scripts/05_fetch_skeletons.py
```

验收：目标 body ID skeleton 保存成功。

## 20.5 第五次：替换真实 FEM

把：

```text
data/processed/selftest_fem.h5
```

替换为你真实模型导出的：

```text
data/processed/fem_output_real_v1.h5
```

调用：

```python
from ear_malecns.experiment import encode_fem_file
encode_fem_file(
    "data/processed/fem_output_real_v1.h5",
    "data/processed/real_encoder_seed42.npz",
    cfg,
)
```

后续 SNN 不需要更改核心接口。

---

# 21. 核心实验矩阵

## Experiment 0：软件/SNN 自检

**输入：**人工固定 spike rate，例如 baseline/stimulus/baseline。  
**目的：**只证明网络代码工作。  
**不能得出的结论：**听觉生理结论。

## Experiment 1：fly-compatible baseline

```text
synthetic acoustic stimulus
→ JON encoder
→ MaleCNS
```

变量：

- frequency；
- amplitude；
- pulse IPI；
- envelope。

## Experiment 2：时间结构

重点：尽量匹配总输入 spike 数，只改变 temporal pattern。

```text
IPI 15 ms
IPI 36 ms
IPI 72 ms
```

如果网络响应不同，才更能说明 topology/dynamics 在做额外计算，而不是 encoder 预先把答案编码进去。

## Experiment 3：real vs rewired

至少比较：

```text
MaleCNS real graph
degree-preserving rewired graph
weight-shuffled graph
```

指标：

- latency；
- response vector separability；
- active neuron fraction；
- cell-type response；
- simple classifier accuracy；
- recurrent persistence。

如果 real ≈ rewired，应如实报告“当前模型下没有观察到真实 topology 的额外优势”。

## Experiment 4：真实 Human-ear FEM

```text
same external stimulus
→ human-ear FEM
→ stapes/BM features
→ encoder
→ fixed JON spikes
→ MaleCNS
```

研究：信息在哪一级损失/改变，而不是“果蝇是否像人一样听见”。

---

# 22. 分析指标

## 22.1 First-spike latency

\[
L_i=t_i^{first}-t_{stimulus}
\]

## 22.2 Hop activation ratio

\[
A_h=\frac{N_{active,h}}{N_h}
\]

## 22.3 Group firing rate

\[
R_c=\frac1{|c|}\sum_{i\in c}r_i
\]

## 22.4 Population separation

例如 cosine distance：

\[
d(a,b)=1-\cos(\mathbf R_a,\mathbf R_b)
\]

## 22.5 分类

```text
network response -> 150/250/300 Hz
network response -> 15/36/72 ms IPI
```

必须 train/test split；不要在同一数据上训练并汇报准确率。

---

# 23. 参数来源必须分级

建立：

```text
configs/parameter_provenance.csv
```

建议列：

```text
parameter
value
unit
source_type
source_reference
confidence
scan_range
notes
```

`source_type` 只能选：

```text
measured
predicted
fitted
assumed
```

示例：

| 参数 | 类型 |
|---|---|
| MaleCNS edge weight/synapse count | measured/structural reconstruction |
| NT classification | predicted（除非有额外功能证据） |
| tau_m=20 ms | assumed |
| w0=0.5 mV | assumed/calibrated |
| JON adaptation range | literature-constrained |
| human→fly normalization | assumed/model design |

---

# 24. UQ / 敏感性分析

第一版扫描：

```text
encoder_gain = 0.25, 0.5, 1, 2, 4
tau_a = 5, 10, 20 ms
tau_m = 10, 20, 30 ms
w0 = baseline × {0.25,0.5,1,2,4}
delay = 0.5,1.5,3,5 ms
unknown_NT_sign = scenario A/B
```

后期再使用：

- Latin Hypercube；
- Morris；
- Sobol。

重点比较：

\[
Var(Y)=V_{FEM}+V_{encoder}+V_{SNN}+V_{topology}+V_{interaction}
\]

如果：

\[
V_{encoder} \gg V_{FEM}
\]

就不要继续用大量时间把 FEM 网格细化一倍；研究限制来自跨物种接口。

---

# 25. 常见错误排查

## 25.1 `NEUPRINT_APPLICATION_CREDENTIALS` missing

```bash
echo "$NEUPRINT_APPLICATION_CREDENTIALS"
```

为空就重新 export。

## 25.2 `ModuleNotFoundError: ear_malecns`

项目根目录：

```bash
pip install -e .
```

## 25.3 `navis`/PyVista 图形库报错

先证明数据链可运行：

```bash
python scripts/02_discover_jons.py
```

3D 是独立模块，不要让渲染问题阻塞连接组/SNN。

无 GUI Linux 环境可先关闭交互窗口，只保存离线图片。

## 25.4 neuPrint query 太大/太慢

先：

```yaml
hops: 1
max_new_nodes_per_hop: 50
```

确认工作后再扩展。

## 25.5 NetworkX 内存上涨

100–3000 nodes 继续用 NetworkX。到了百万 edge 量级才考虑：

- igraph；
- graph-tool；
- scipy sparse；
- Parquet 流式处理。

不要过早优化。

## 25.6 Brian2 太慢

PoC 先 runtime 模式。后期使用：

```python
from brian2 import set_device
set_device("cpp_standalone", directory="brian_build")
```

需要系统 C++ 编译器。

## 25.7 网络不稳定

不要只调一个参数到“看起来好看”。至少做：

```text
weight gain × delay × tau_m × encoder gain
```

小网格扫描。

---

# 26. 前两周操作表

| 天 | 操作 | 验收 |
|---:|---|---|
| 1 | WSL/Linux + Conda | `conda --version` |
| 2 | 创建环境 + pytest | tests PASS |
| 3 | neuPrint token + connection | Client PASS |
| 4 | JO regex query | 能列出 JO-* |
| 5 | 筛 JO-A/JO-B | CSV 固定 |
| 6 | 1-hop extraction | nodes/edges |
| 7 | GraphML + NetworkX QA | 图可打开 |
| 8 | 2-hop，小规模裁剪 | ≤300 nodes |
| 9 | synthetic FEM selftest | HDF5 |
| 10 | encoder | rate/spikes |
| 11 | LIF network | 无崩溃 |
| 12 | JON fixed spikes | downstream response |
| 13 | raster/latency | 图和 CSV |
| 14 | 20 skeleton +总结 | 最小 MaleCNS 闭环 |

**两周结束不要求真实人耳 FEM。**

---

# 27. 6–9 个月现实路线

## 阶段 A（第 1–4 周）MaleCNS 数据链

产物：

```text
auditory_input_cells.csv
auditory_subgraph_v1/
query scripts
20–50 skeletons
```

停止条件：如果无法稳定确认/查询 auditory JO seeds，则先解决 annotation 与 cell-type 验证，不进入 SNN 科研解释。

## 阶段 B（第 5–8 周）SNN baseline

产物：

- 100–300 neuron LIF；
- 参数扫描；
- fixed spike input；
- latency/raster。

继续条件：模型不自激、不饱和且可重复。

## 阶段 C（第 9–13 周）JON encoder

产物：

- tone/pulse/IPI stimulus；
- M0 encoder；
- adaptation M1 surrogate；
- physiology data comparison。

## 阶段 D（第 14–19 周）Human-ear FEM integration

产物：

- 频域 transfer functions；
- mesh convergence；
- real HDF5；
- FEM→encoder。

## 阶段 E（第 20–25 周）Topology controls

产物：

- real；
- degree-preserving rewire；
- weight shuffle；
- ablation；
- classification/separability。

## 阶段 F（第 26–36 周）UQ + 3D + writing

产物：

- parameter provenance；
- sensitivity；
- key skeleton animation；
- reproducibility package；
- thesis/paper figures。

---

# 28. 代码目录说明

```text
ear_malecns_manual_project/
├── TECHNICAL_MANUAL.md
├── environment.yml
├── requirements.txt
├── pyproject.toml
├── configs/
│   └── default.yaml
├── src/ear_malecns/
│   ├── config.py
│   ├── stimulus.py
│   ├── fem_io.py
│   ├── encoder.py
│   ├── malecns.py
│   ├── snn.py
│   ├── analysis.py
│   ├── visualize.py
│   ├── controls.py
│   └── experiment.py
├── scripts/
│   ├── 00_selftest.py
│   ├── 01_connect_neuprint.py
│   ├── 02_discover_jons.py
│   ├── 03_extract_subgraph.py
│   ├── 04_run_snn.py
│   └── 05_fetch_skeletons.py
├── tests/
│   └── test_local_pipeline.py
├── data/
└── outputs/
```

完整代码均在交付包内，不需要从聊天内容重新拼接。

---

# 29. 理论知识最小补充

## 29.1 声压与粒子速度

声压 `p` 是标量，而粒子速度 `u` 是矢量。果蝇近场机械听觉与触角运动/粒子速度的关系比“只看 Pa”更直接，所以本项目不能把人耳入口声压直接当 JON 感觉量。

## 29.2 Transfer function

在线性系统近似下：

\[
Y(f)=H(f)X(f)
\]

人耳 FEM 只需先求 `H(f)`，就能把大量不同 stimulus 复用到同一模型上。

## 29.3 Connectome graph

将 MaleCNS 写为：

\[
G=(V,E)
\]

节点是神经元，边是聚合后的有向连接。单边 `weight` 是结构性 synapse-count 信息，不等于生理 conductance。

## 29.4 SNN

Spike 是模型中的离散事件。当前项目研究的是：

> 在 MaleCNS 结构约束下，假设神经动力学产生的 simulation-derived activity propagation。

## 29.5 为什么 real-vs-rewired 很重要

如果所有特征选择性都由 encoder 产生，那么 MaleCNS 拓扑可能只是“装饰”。

只有通过保留规模/degree 等统计的对照图，才能检验真实拓扑是否带来额外时空计算。

---

# 30. 本初版没有假装完成的内容

为了保证研究可信度，以下内容需要真实数据/后续工作，当前代码不会伪造：

1. 不提供虚构的 MaleCNS JON body IDs；必须 API 动态查询。
2. 不声称 LIF 参数是 MaleCNS 全部神经元实测参数。
3. 不声称 NT prediction 等于确定 receptor effect。
4. 不提供一个伪装成“完整人耳”的通用 FEM 几何模型。
5. 不把 synthetic transfer function 当研究结果。
6. 不把 3D activity animation 叫真实 EM 电活动。
7. 不声称 100–350 Hz 是果蝇唯一可听频率；这里只作为初始共同频带和 song-related PoC。

---

# 31. 推荐官方入口

- MaleCNS Project: https://male-cns.janelia.org/
- MaleCNS Download: https://male-cns.janelia.org/download/
- neuPrint: https://neuprint.janelia.org/
- neuprint-python docs: https://connectome-neuprint.github.io/neuprint-python/docs/
- Brian2: https://brian2.readthedocs.io/
- FEniCSx: https://docs.fenicsproject.org/
- Gmsh: https://gmsh.info/
- OpenEar: https://zenodo.org/records/1473724

---

# 32. 最终初版验收清单

完成以下全部内容后，才算“初版完整链路”完成：

- [ ] 环境可从 `environment.yml` 重建；
- [ ] 本地 pytest 通过；
- [ ] neuPrint 能连接 `male-cns:v1.0`；
- [ ] JO-A/B body IDs 由程序查询，不硬编码；
- [ ] seed CSV 已版本冻结；
- [ ] auditory 1–2 hop 子图已导出；
- [ ] 100–300 neuron LIF 能稳定运行；
- [ ] sensory spike input 固定且可复现；
- [ ] raster / latency / graph 已输出；
- [ ] 至少 20 个 skeleton 可下载；
- [ ] synthetic transfer 仅用于软件自检；
- [ ] 真实 FEM 数据可按 HDF5 schema 读入；
- [ ] FEM → envelope/temporal feature → rate/spike 可运行；
- [ ] real graph 与 rewired control 使用相同输入；
- [ ] parameter provenance 区分 measured/predicted/fitted/assumed；
- [ ] 所有图明确标注 simulation-derived activity；
- [ ] README 固定 MaleCNS dataset version、随机种子、配置文件与实验 ID。

当以上条目完成，你拥有的不是“果蝇模拟人类听觉”，而是一套可复现、可替换模块、可做控制实验的 **human-ear physics → explicit cross-species encoding → MaleCNS connectome-constrained neural computation** 初版研究平台。
