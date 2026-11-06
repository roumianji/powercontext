# seekdb × 阶跃星辰：端侧 AI 知识库

浏览器 Worker 通过 Transformers.js 3.8.1 / ONNX Runtime Web 本地生成 384 维向量，WebGPU 优先，WASM 兜底。Node API 只处理原文、元数据和已计算的向量；seekdb 1.4.0 embedded 完成 HNSW、全文检索与数据库端 RRF 融合。

## 启动

使用现有 `2026-competition-ecosystem` 分支、WSL Ubuntu 24.04 和 Node 20+，保留现有 pnpm-lock.yaml：

```bash
cd ~/coursework/ob2026-powercontext/stepfun/mini-kb
pnpm install --frozen-lockfile
npm run check
npm test
npm run models
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`；API 为 `127.0.0.1:8787`。服务只监听本机。原来的 `demo` 集合保留；固定测评使用语料内容哈希生成的独立 `eval_...` 知识库，每种精度独立集合。

生产演示：`npm run build`，再用 `NODE_ENV=production npm start`，访问 `http://127.0.0.1:8787`。原生库首次初始化可能需要等待，启动日志在 `data/api-process.log`。

## 本地模型

运行 `npm run models` 会从固定 revision 自动下载并校验全部模型文件；`dev`、`build`、`start` 也会先执行此检查。已有文件 SHA256 正确时不会重复下载。默认访问 Hugging Face，失败后尝试 HF-Mirror；可用 `HF_ENDPOINT=https://hf-mirror.com npm run models` 指定 HTTPS 镜像。

下载器以临时文件保存，校验大小和 SHA256 后原子替换；中断文件不会被当成有效模型。`npm run models:verify` 只校验，不下载。

Worker 已允许本地模型、禁止远程模型，从 `/models/` 加载权重。文件位于 `public/models/Xenova/all-MiniLM-L6-v2/`，保持目录结构：

```text
config.json
tokenizer.json
tokenizer_config.json
special_tokens_map.json
vocab.txt
onnx/model.onnx
onnx/model_fp16.onnx
onnx/model_quantized.onnx
```

来源：`Xenova/all-MiniLM-L6-v2`，revision `751bff37182d3f1213fa05d7196b954e230abad9`，Apache-2.0。使用发布方已有权重，没有自行执行量化。

`public/model-manifest.json` 记录本机文件实测字节数及 SHA256；可运行 `python3 scripts/model_sizes.py --write-manifest` 重新核对。权重、数据库和备份文件已忽略，不提交大文件。

| 配置 | ONNX 文件 | 字节数 | MiB |
|---|---|---:|---:|
| FP32 | model.onnx | 90387606 | 86.20 |
| FP16 | model_fp16.onnx | 45297825 | 43.20 |
| WASM INT8 / q8 | model_quantized.onnx | 22972370 | 21.91 |

## 操作与测评

普通使用：选择配置、加载模型、选择 txt/md 文件导入，再输入问题检索。原文与向量会写入本机 API，端侧推理不代表原文从不离开浏览器。

在“04 · 可复现性能测评”选择扩展集和 3 轮，点击“自动运行三组对照”。程序依次执行 FP32 自动后端、优化自动后端、仅 WASM 优化配置的加载、导入、预热及测评。实际精度和后端写入日志；GPU 不可用时自动配置会降级，不能把降级结果标为 GPU 成绩。

- 扩展集：`public/evaluation-suite.json`，60 份英文文档、40 条查询，20 个主题，包含近邻干扰文档。是项目自建合成回归集，相关性标注未经独立人工复核，不是公开标准基准，也不代表中文语义质量。
- 冒烟集：原来的 5 文档 / 5 查询。只用于检查流程，Recall@5 区分度很低。
- 导入前先对文档 batch 预热；查询正式测量前另有 3 次预热，记录在独立 warmup 事件中。
- 正式测量前，后端核验全部预期 chunk ID 和集合总数；缺失或混入额外文档时拒绝报告成绩。
- 每组默认 40 查询 × 3 轮 = 120 次正式测量，记录向量化、seekdb、端到端 P50 / P95，和 Recall@5、nDCG@5、MRR@5。不同轮次轮转查询起点。
- 以原始前五条 chunk 位置评估来源文档；同一来源的多个 chunk 不会重复计入相关性。
- 日志写入当前浏览器 localStorage，刷新后仍可导出；导出 JSON 含逐次结果、语料和查询 SHA256、模型 revision、实际后端、GPU 信息和模型权重指纹。请另存原始 JSON，浏览器存储不替代备份。

报告生成：

```bash
npm run report -- /path/to/stepfun-benchmark.json --out report.md
```

报告按同会话、同语料、同查询、同模型、同 batch、同轮数和同浏览器分组，只在同为 WebGPU 的 FP32 / FP16 间给出向量化耗时比值。WASM 与 WebGPU 的差异不能只归因于精度；加载时间也不能与热态查询延迟混为一谈。

仅 WASM 配置验证显式跳过 GPU 的完整路径；它不等于对浏览器撤销 GPU 或 GPU 初始化失败进行故障注入，自动降级仍需单独验证。

## seekdb 一致性与启动修复

每批 `upsert` 后刷新索引，核验 ID 可见并执行向量探测，成功才报告该批完成。`hybridSearch({ query, knn, rank: { rrf: {} } })` 在数据库端融合，不在前端拼接召回结果。向量索引显式 `embeddingFunction: null`，后端不执行模型。

Linux 原生库本机 ELF 的 TLS 段为 49456 字节。启动器为 API 子进程设置 65536 字节的 `glibc.rtld.optional_static_tls`，避免延迟加载时的 `cannot allocate memory in static TLS block`；不修改系统配置。过大的 TLS 预留曾引起线程创建问题，因此没有采用数 MiB 的通用设置。API 在独立进程运行，stdout/stderr 保存到 `data/api-process.log`，开发时监视 API 源码变化。

`npm run check` 检查 JavaScript 语法；`npm test` 验证指标的重复来源去重、漏召回、排序折损及分位数。前端构建和实际运行记录详见 TECHNICAL_NOTE.md。提交前保留原始实测 JSON，更新技术说明，不提交 node_modules、data 或模型大权重。
