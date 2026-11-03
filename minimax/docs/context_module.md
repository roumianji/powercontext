# seekdb 上下文模块：第二阶段

## 安装与调用

将本包解压到已有 minimax/ 目录。本包只增加 context_module/、本说明和依赖文件，
不包含业务代码、原有 tests/、修改前快照、虚拟环境或验证日志。

在已激活的 Python 3.12 虚拟环境中运行：

```bash
python -m pip install -r requirements-seekdb.txt
python -m context_module ingest
python -m context_module context --task "给任务列表增加 status 筛选，保持原有功能"
```

模块基于 pylibseekdb 的本地运行接口和 PyMySQL 的参数化 SQL。数据库位于
.runtime/engineering.seekdb，每次命令运行时打开，命令结束后关闭连接与运行句柄。
默认使用 test 数据库中的 minimax_docs 和 minimax_meta 两张应用专用表。
ingest 以事务替换当前资料集合；只写这两张表。重复运行不累计旧资料，移除的源文件也不再参与查询。

如需其他项目根目录或数据库目录，全局参数应放在子命令之前：

```bash
python -m context_module --root /path/to/minimax --db .runtime/other.seekdb ingest
```

## 输入与输出

- ingest 输入：specs/**/*.md、demo_app/**/*.py、tests/**/test_*.py、data/**/*.json。
  __init__.py 不纳入。当前初始项目一共 6 个资料文件。
- context 输入：--task 自然语言任务。提取英文字段/符号、常见中文操作对应词，最多 12 个检索词。
- 数据库查询：对数据库中的正文与相对路径执行 LOCATE/LOWER 参数化关键词查询；不是向量检索。
- context 输出：.runtime/context.json；同时将完整上下文保存到 evidence/context/ 的独立文件。
- 来源信息：每份资料包含真实相对路径、内容哈希、代码/测试符号行号、规格条目及行号。
- 技术记录：每次命令的实际 SQL、参数、返回来源、资料版本、数据库版本和退出码写入 evidence/database/。

上下文的正文、符号和规格条目取自实际 SELECT 返回内容。
本地文件只用于检查资料是否已变化、来源是否仍存在；不会绕过数据库把文件正文塞入输出。

## 规格更新

修改 specs/task_list.md 后重新运行 ingest，再运行同一个 context 命令。
输出中的资料版本和规格内容将随实际文件变化。若资料改变却没有重新导入，context 会明确报错，
不会悄悄沿用旧规格。测试与业务代码变化同样要求重新导入。

验收时应在独立验证工作目录演示规格变更，保留原任务用于前后代码对比的测试与快照。

## 本样例必须查出的来源

1. specs/task_list.md：KEEP-001 至 KEEP-005、STATUS-001 至 STATUS-004。
2. demo_app/service.py：TaskBoard.list_tasks 及已有创建、更新、删除行为。
3. demo_app/__main__.py：HTTP 查询参数及错误响应处理。
4. tests/test_target.py：固定目标功能测试。
5. tests/test_regression.py：原有行为回归测试。
6. data/tasks.json：初始数据。

## 当前边界

本阶段实现工程资料入库、实际查询、来源定位和规格重新导入。
MiniMax 实际修改、PowerContext 状态写入/复用和修改后验证将在后续阶段完成。
本阶段不会把数据库连接检查或本地 JSON 文件冒充这些尚未完成的验收项。
检索采用小工程的关键词方案，不声称适用于大型仓库；每份资料上限 256 KiB。

## 模块逻辑检查

```bash
python -m unittest -v checks.test_context
```

这些检查用 SQLite 的 SQL 适配器验证来源选择、规格更新、过期检测、删除资料清理和事务回滚，
不冒充 seekdb 实际使用证据。seekdb 的真实启动、导入、查询应通过上述 ingest/context 命令在目标机器执行，
并以它们生成的 evidence/database/ 和 evidence/context/ 记录为准。

## 依赖与参考

- pylibseekdb 1.4.0.post2、PyMySQL 1.2.0。两者均为实际运行依赖。
- 官方本地接口：https://github.com/oceanbase/seekdb-bindings/blob/main/python/README.md
- 官方 seekdb 示例：https://github.com/oceanbase/seekdb#quick-start
- 上下文模块由 ChatGPT 辅助为本作业编写；未使用 MiniMax 编写本阶段模块。
