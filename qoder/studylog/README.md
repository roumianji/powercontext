# 研习周记

基于 Flask + OceanBase seekdb 的学习与科研记录工具。

## 项目简介

研习周记解决学习与科研记录分散、查询困难、
手工整理周报耗时的问题。

核心功能：
1. 新增学习/科研记录
2. 按项目、日期和关键词筛选记录
3. 自动生成 Markdown 周报
4. 通过 seekdb 持久化存储和查询数据

项目主要开发、调试和测试工作通过 Qoder CLI 完成。

## 项目地址

Qoder Sites 公开展示页：
https://studylog-86sb51dc8lq.qoder.zone

GitHub：
https://github.com/roumianji/powercontext

分支：2026-competition-ecosystem

## 运行环境

- Python 3.12（已验证）
- Flask 3.1.1
- pylibseekdb 1.4.0.post2
- PyMySQL 1.2.0
- Linux / WSL2 Ubuntu（已验证）

## 快速启动

克隆项目：

```bash
git clone -b 2026-competition-ecosystem \
  https://github.com/roumianji/powercontext.git

cd ob2026-powercontext/qoder/studylog
```

安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

使用独立的演示数据库：

```bash
mkdir -p data
export STUDYLOG_DB_PATH="$PWD/data/review_demo.seekdb"
export STUDYLOG_DEMO_MODE=1
unset STUDYLOG_API_KEY
```

启动本地服务：

```bash
.venv/bin/python -m flask --app app run \
  --host 127.0.0.1 --port 5100 --no-reload
```

访问：

- http://127.0.0.1:5100/
- http://127.0.0.1:5100/app
- http://127.0.0.1:5100/health

以上是本地复现方式，不需要购买云服务器。

## 最小功能验证

另开一个终端，执行：

### 1. 检查数据库

```bash
curl http://127.0.0.1:5100/health
```

预期：status 为 healthy，数据库引擎为 seekdb。

### 2. 写入一条演示记录

```bash
curl -X POST http://127.0.0.1:5100/api/demo/logs \
  -H "Content-Type: application/json" \
  -d '{
    "log_date":"2026-11-04",
    "completed":"完成 seekdb 功能验证",
    "problems":"",
    "next_plan":"生成周报"
  }'
```

预期：返回 ok=true 和新记录 ID。

### 3. 查询刚才写入的数据

```bash
curl -G http://127.0.0.1:5100/api/logs \
  --data-urlencode "keyword=完成 seekdb 功能验证"
```

预期：返回刚才写入的记录。

### 4. 生成周报

```bash
curl -G http://127.0.0.1:5100/api/report \
  --data-urlencode "date_from=2026-11-04" \
  --data-urlencode "date_to=2026-11-04"
```

预期：返回包含对应记录的 Markdown 周报。

### 5. 数据持久化

停止 Flask，使用相同的
STUDYLOG_DB_PATH 重新启动。

再次查询记录，预期原始记录仍然存在。

## 技术结合说明

本项目使用真实的 OceanBase seekdb 作为业务数据库。

- 新增记录：写入 seekdb
- 查询筛选：从 seekdb 查询记录
- 周报生成：读取 seekdb 数据并按项目汇总
- 持久化：程序重启后数据仍然保留

数据库操作由 database.py 实现。

项目不使用 SQLite、JSON 文件或浏览器本地存储
替代 seekdb 业务数据库。

## 自动化验证

项目包含：

- verify.py：基础验证脚本
- test_comprehensive.py：综合测试脚本

开发环境中综合测试曾完成 21/21 项验证。
这些测试可能写入数据，应在独立测试数据库中运行。

## 部署说明

Qoder Sites 主要承担作品展示和评审入口。

Flask + seekdb 可以按以上说明在本地运行。

项目还实现了前后端分离版本和公网演示方案。
目前独立公网演示依赖运行中的 WSL 主机，
不保证全天候在线。

详细部署说明见 DEPLOYMENT.md。
该文件包含早期云服务器部署方案，
不是本地基础验收的前置要求。

## Qoder 开发记录

项目由 Qoder CLI 参与需求拆解、代码生成、
测试、API 开发及安全改进。

开发过程截图与会话记录作为赛事材料另行提交。
