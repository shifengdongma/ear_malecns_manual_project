# 第一阶段数据与软件来源

核查与下载：2026 年 9 月 25 日（北京时间）。

- [MaleCNS 官方下载页](https://male-cns.janelia.org/download/)：v1.0 数据、SWC 单位及 CC-BY 授权。引用数据时应署名 MaleCNS / FlyEM（HHMI Janelia）、Cambridge、MRC LMB、Google Research 等项目合作者，具体论文引文按官方发布记录。
- [神经元注释](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather)：bodyId、type、subclass、status、entryNerve 等。
- [神经递质预测](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-neurotransmitters-male-cns-v1.0.feather)：body 映射为 bodyId；consensus_nt 映射为 consensusNt。预测不等于确定的受体效应，glutamate 保留为 uncertain prior。
- [分段连接数量](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather)：body_pre / body_post / weight。本机读取到 151,856,684 行，属于完整 segment 图，不能混同于论文中 proofread neuron 图边数。
- [neuprint-python 查询文档](https://connectome-neuprint.github.io/neuprint-python/docs/queries.html)：omit_rois=True 获得神经元对总连接数量，不把 ROI 分行取最大值充当总量。
- [Brian2 运行文档](https://brian2.readthedocs.io/en/stable/user/running.html)：显式 Network、固定时间步长及独立重复模拟。

每个原始文件旁记录 URL、字节数、ETag、官方 MD5 和 SHA-256。公共文件路线和 neuPrint API 路线分开标记，公共文件下载不代表完成 API 认证。

科学边界：连接组是结构重建；LIF 电压、脉冲和活动图是模型计算结果。声学刺激、机械响应、人工 JON-compatible drive、突触电压增量不是同一个物理量。
