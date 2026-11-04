# MiniMax × OceanBase：SDD 上下文管理系统

## 一、项目简介

本项目是 OceanBase 2026 课程竞赛 MiniMax 赛题的实现。

开发任务：为任务列表增加 status 筛选，保持已有功能。

使用三项核心技术：

- MiniMax：实际生成业务代码修改
- seekdb：存储和检索规格、代码、测试及数据
- PowerContext：保存和跨进程恢复开发任务状态

## 二、运行环境

- Python 3.12
- Linux / WSL2
- pylibseekdb==1.4.0.post2
- PyMySQL==1.2.0
- powercontext[builtin]==1.4.1
- python-dotenv==1.2.4

完整依赖和约束见 requirements-*.txt 及
requirements-powercontext.lock。

## 三、从零初始化

在仓库 minimax/ 目录执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-minimax.txt
.venv/bin/python -m context_module ingest
```

程序将六份工程资料导入 seekdb。

## 四、构造开发上下文

```bash
.venv/bin/python -m context_module context \
  --task "给任务列表增加 status 筛选，保持原有功能"
```

输出包括：
- 适用规格 KEEP-001～005、STATUS-001～004
- 相关业务代码 demo_app/service.py
- 接口代码 demo_app/__main__.py
- 目标测试 tests/test_target.py
- 回归测试 tests/test_regression.py
- 初始数据 data/tasks.json

上下文来自 seekdb 实际查询结果。

## 五、运行验证测试

```bash
.venv/bin/python tools/run_tests.py target --label after
.venv/bin/python tools/run_tests.py regression --label after
```

预期结果：
- 目标测试：6/6 通过
- 回归测试：10/10 通过

修改前测试结果保存在 evidence/before/。
修改前代码保存在 snapshots/before/。
修改后代码为 demo_app/service.py。

修改前目标测试因缺少 status 功能而失败，
原有回归测试通过。修改前后使用相同测试文件。

## 六、PowerContext 状态保存和恢复

完成上下文初始化与测试后：

```bash
.venv/bin/python -m task_state checkpoint --phase after
```

再启动一个新进程执行：

```bash
.venv/bin/python -m task_state resume
```

恢复的任务进度会用于后续上下文。

## 七、MiniMax 实际代码修改

模型：MiniMax-M3.1-Flash

调用方式：Anthropic-compatible Messages HTTP API

完整证据位于 evidence/minimax/，包括：
- input_context.json：实际提供的上下文
- request_body.json：请求内容
- response_text.txt：模型公开文本响应
- code.diff：代码修改差异
- before/ 和 after/：修改前后源码
- record.json：模型调用与验证记录

核对已有记录不需要重新调用模型。

如需再次生成代码，可在初始化环境并配置有效
MiniMax API Key 后运行：

```bash
.venv/bin/python -m coding_assistant configure
.venv/bin/python -m coding_assistant run
```

重新调用可能产生 API 费用，并修改业务代码。
正常复现已有结果不需要执行这两条命令。

## 八、规格更新验证

修改 specs/task_list.md 中的规格内容，然后执行：

```bash
.venv/bin/python -m context_module ingest
.venv/bin/python -m context_module context \
  --task "给任务列表增加 status 筛选，保持原有功能"
```

本次实验已验证 STATUS-001 增加状态值区分大小写
的说明后，重新检索可以获取更新后的内容。

查询及导入证据保存在 evidence/database/
和 evidence/context/。

## 九、重置及运行说明

本地运行状态保存在 .runtime/，不会提交至 Git。

如需从空状态重新初始化：

```bash
rm -rf .runtime/
.venv/bin/python -m context_module ingest
```

然后重新运行上下文检索、测试、checkpoint 和 resume。

业务演示程序可通过以下命令启动：

```bash
.venv/bin/python -m demo_app --port 8088
```

访问 http://localhost:8088/tasks 。

## 十、已知限制

- 当前依赖 Linux 兼容运行环境和 Python 3.12。
- seekdb 使用 pylibseekdb 本地运行时。
- PowerContext 使用 SQLite 持久化后端。
- MiniMax 实际代码生成需要网络和有效 API Key。
- 不提交真实密钥、本地数据库和虚拟环境。

## 十一、技术说明

详见 docs/technical_report.md。

源码、实验结果和技术使用记录均在 minimax/ 目录中。
