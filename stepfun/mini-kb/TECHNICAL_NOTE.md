# 阶跃星辰：端侧知识库技术说明

实测日期：2026-11-06。代码位于大赛分支 `2026-competition-ecosystem` 的 `stepfun/mini-kb`。

## 实现与修复

浏览器 Web Worker 运行 Transformers.js 3.8.1 / ONNX Runtime Web，使用本机 ONNX 权重生成 384 维向量。WebGPU 优先，优化配置使用 FP16，WASM 优化配置使用 INT8；后端没有嵌入模型，不调用云端推理。

Node + seekdb 1.4.0 embedded 保存文档与向量，执行 HNSW、全文查询及数据库端 RRF。不同精度分别存储；导入使用确定性 SHA256 ID 与 upsert，每批刷新并验证索引。重新打开已有集合时显式设置 embeddingFunction:null，修复第二批导入意外尝试加载 default-embed 的问题。

Linux 延迟加载原生库的 static TLS 错误通过 API 子进程的 GLIBC_TUNABLES 修复，保留 65536 字节，未修改系统配置。启动日志写入 data/api-process.log，开发环境支持自动重载。数据库错误不会再把成功加载的前端模型误标为加载失败。

## 本轮环境与方法

- 浏览器：Windows Chromium 156（本应用浏览器）；逻辑线程数 16。
- WebGPU adapter：vendor=nvidia，architecture=ampere；驱动未提供具体设备名称。CPU 型号、驱动版本未采集。
- API：WSL Ubuntu 24.04，Linux x64，Node 22.23.4，seekdb 1.4.0 embedded。
- 模型：Xenova/all-MiniLM-L6-v2，revision 751bff37182d3f1213fa05d7196b954e230abad9。使用发布者预量化权重，不声称自行量化。权重字节数和 SHA256 见 public/model-manifest.json。
- 数据：项目自建英文合成集 60 文档 / 40 查询，20 个主题及近邻干扰文档；每文档一个 chunk。标注未经独立人工复核，不属于公开标准基准。
- batch=8；top-k=5；每组正式测量 3 轮，共 120 次；三组共 360 次。文档 batch 预热、查询预热 3 次，与正式查询分开记录。模型加载不混入热态延迟，本轮没有可靠冷缓存下载对照。
- 测评前核验全部 ID 和集合总数；语料和查询标注均保存 SHA256。正式记录见 evidence/benchmark-2026-11-06.json。

## 实测结果

| 配置 | 权重 MiB | 查询向量化 P50 / P95 ms | seekdb P50 / P95 ms | 端到端 P50 / P95 ms | Recall@5 | nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|
| webgpu / fp32 | 86.200 | 12.100 / 20.720 | 3.650 / 4.022 | 24.700 / 33.300 | 0.975 | 0.876 |
| webgpu / fp16 | 43.199 | 11.700 / 15.125 | 3.700 / 4.984 | 24.500 / 30.145 | 0.975 | 0.876 |
| wasm / q8 | 21.908 | 11.850 / 14.600 | 3.530 / 4.103 | 24.050 / 27.110 | 0.975 | 0.879 |

以上为最终配置下补齐的三组结果，360 次完整正式查询。此前还完成过一轮三组对照，合计 720 次完整查询。完整历史保留在 evidence/benchmark-all-2026-11-06.json，当前对照为 evidence/benchmark-2026-11-06.json。

FP16 权重约为 FP32 一半。最终查询向量化 P50 从 12.10 ms 降到 11.70 ms，降低约 3.3%；此前一轮为 12.55 ms 与 11.75 ms。两轮尾延迟的变化方向不同，说明收益有波动，不能宣称稳定加速或统计显著。FP32 / FP16 的本集检索质量一致；INT8 的相近质量仅适用于本轮英文自建语料。

三种配置均未召回 q012 的目标来源（优化 CPU 兜底的运行时与精度），保留这条失败查询，Recall@5 为 0.975。

本轮复验出现过一次浏览器 Failed to fetch，中断的查询批次没有被记为完成，之后独立补齐 FP16 和 INT8 的正式测评。原生运行时在热重载及调试线程初始化时也产生过线程警告/退出异常；最终恢复常规 SDK 加载、65536 字节 TLS 预留后完成了上述查询。长期运行与进程反复启停的稳定性仍需另行验证。

导入向量化吞吐（已预热文档 batch）：

- webgpu / fp32: 60 块，309.44 块/秒；embedding 193.90 ms，写入 1936.92 ms，刷新/验证 2902.49 ms。
- webgpu / fp16: 60 块，188.26 块/秒；embedding 318.70 ms，写入 1728.03 ms，刷新/验证 2515.72 ms。
- wasm / q8: 60 块，34.55 块/秒；embedding 1736.70 ms，写入 1902.12 ms，刷新/验证 2577.82 ms。

## 验证及范围

- 11 个 JavaScript 文件语法检查通过，3 项指标测试通过。
- 前端 Vite 6.4.5 生产构建通过（Windows Node 22.14.0 的隔离前端依赖目录）；没有把这一检查称为 WSL 原生 SDK 安装测试。
- WSL 实际完成三种配置的多批次导入、索引刷新、固定语料内容校验、数据库混合检索和逐次测量。
- 浏览器刷新后能恢复已保存的测评表与原始记录；API 重载后原集合仍存在。
- 仅 WASM 的 INT8 路径已执行完整流程。尚未对实际 GPU 失效或浏览器撤销 WebGPU 做故障注入，不能将显式 WASM 测试等同于自动故障降级测试。
- 原始日志与报告已保存。本轮没有执行大赛平台提交。

报告重建：`npm run report -- evidence/benchmark-2026-11-06.json --out evidence/report-2026-11-06.md`。

## 提交复现补充

新增 npm run models 下载入口及 dev/build/start 前置检查，固定完整 revision 和八文件 SHA256，采用流式下载、临时文件、校验后替换、失败重试和镜像兜底。实际通过八文件本地完整校验，并在空目录从 HF-Mirror 下载 config.json 校验成功。未宣称从公网重新下载全部 159 MB 权重完成全新 WSL 安装。
