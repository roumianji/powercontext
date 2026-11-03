# 研习周记

基于 seekdb (OceanBase 嵌入式引擎) 的个人学习/科研记录工具。

## 功能特性

1. **新增记录** — 日期、项目、完成事项、遇到的问题、下一步计划
2. **查询记录** — 按日期范围、项目、关键词筛选
3. **生成周报** — 按项目汇总，支持复制/下载 Markdown
4. **JSON API** — 提供 RESTful API 接口，支持前后端分离部署

## 快速启动

### 本地运行

```bash
cd qoder/studylog

# 创建虚拟环境（首次）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 写入示例数据（首次）
.venv/bin/python seed_data.py

# 启动应用
.venv/bin/python app.py
```

浏览器打开 **http://127.0.0.1:5100**

### 公网部署（分离式架构）

由于 Qoder Sites 不支持 Python 后端，需要采用前后端分离部署：

```
┌─────────────────────────────────────┐
│  Qoder Sites (前端)                  │
│  https://studylog-xxx.qoder.zone    │
└──────────────┬──────────────────────┘
               │ HTTP API
               ▼
┌─────────────────────────────────────┐
│  云服务器 (后端)                      │
│  Flask + seekdb                      │
│  https://api.yourdomain.com         │
└─────────────────────────────────────┘
```

**部署步骤：**

1. **准备云服务器**（阿里云 ECS / 腾讯云 CVM / 自建服务器）
   - 安装 Python 3.10+
   - 开放 443 端口（HTTPS）

2. **部署后端**
   ```bash
   # 在服务器上
   git clone <your-repo>
   cd qoder/studylog
   
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python seed_data.py
   
   # 使用 systemd 或 supervisor 管理进程
   # 或使用 gunicorn
   .venv/bin/gunicorn -w 4 -b 0.0.0.0:5100 app:app
   ```

3. **配置 Nginx 反向代理 + HTTPS**
   ```nginx
   server {
       listen 443 ssl;
       server_name api.yourdomain.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://127.0.0.1:5100;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

4. **配置 CORS**（允许前端域名访问）
   
   在 `app.py` 中添加：
   ```python
   from flask_cors import CORS
   CORS(app, resources={r"/api/*": {"origins": "https://studylog-xxx.qoder.zone"}})
   ```

5. **修改前端调用远程 API**
   
   更新 `site/index.html` 中的 API 调用地址。

6. **重新发布 Qoder Sites**
   ```bash
   # 使用 sites CLI 重新发布
   ```

## API 文档

### 健康检查

```http
GET /health
```

响应：
```json
{
  "status": "healthy",
  "database": {"engine": "seekdb", "version": "5.7.25-OceanBase seekdb-v1.4.0.0"},
  "record_count": 12,
  "timestamp": "2026-11-03T10:30:00"
}
```

### 查询记录

```http
GET /api/logs?project=OceanBase竞赛&keyword=seekdb&date_from=2026-10-01&date_to=2026-10-31
```

响应：
```json
{
  "ok": true,
  "data": [...],
  "count": 5
}
```

### 新增记录

```http
POST /api/logs
Content-Type: application/json

{
  "log_date": "2026-11-03",
  "project": "OceanBase竞赛",
  "completed": "完成 API 开发",
  "problems": "",
  "next_plan": "部署到云服务器"
}
```

响应：
```json
{
  "ok": true,
  "id": 13,
  "message": "记录 #13 已保存"
}
```

### 获取项目列表

```http
GET /api/projects
```

响应：
```json
{
  "ok": true,
  "data": ["OceanBase竞赛", "论文阅读", "课程作业"]
}
```

## 技术栈

- **后端**: Python 3.10+ + Flask
- **数据库**: seekdb (pylibseekdb + PyMySQL)
- **前端**: 原生 HTML/CSS/JavaScript
- **部署**: Qoder Sites (前端) + 云服务器 (后端)

## 验证步骤

### 自动化测试

```bash
# 运行完整测试套件（21 项测试）
.venv/bin/python test_comprehensive.py

# 运行基础验证（7 项测试，需要应用运行）
.venv/bin/python verify.py
```

### 手动验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 新增记录 | 访问 /add，填写表单提交 | 跳转首页，显示"记录 #N 已保存" |
| 查询筛选 | 首页选择项目/日期/关键词 | 只显示匹配记录 |
| 数据持久化 | 停止并重启 app.py | 之前写入的记录仍然存在 |
| 生成周报 | 访问 /report，选择日期范围 | 按项目汇总显示，可复制/下载 Markdown |
| seekdb 引擎 | 查看首页底部 | 显示 `seekdb` 引擎和版本号 |
| 健康检查 | `curl http://127.0.0.1:5100/health` | 返回 JSON，status=healthy |
| API 查询 | `curl http://127.0.0.1:5100/api/logs` | 返回 JSON 记录列表 |

## 目录结构

```
qoder/studylog/
├── app.py                    # Flask 主应用（Web + API）
├── database.py               # seekdb 连接与 CRUD
├── seed_data.py              # 示例数据写入脚本
├── verify.py                 # 基础验证脚本（7 项）
├── test_comprehensive.py     # 完整测试套件（21 项）
├── requirements.txt          # Python 依赖
├── README.md                 # 本文档
├── TECHNICAL_ANALYSIS.md     # 技术分析与部署方案
├── .gitignore
├── templates/                # HTML 模板
│   ├── base.html
│   ├── index.html            # 查询页
│   ├── add.html              # 新增页
│   └── report.html           # 周报页
├── site/                     # Qoder Sites 前端（待改造）
│   └── index.html
└── data/                     # seekdb 数据文件（gitignore）
    └── studylog.seekdb
```

## 已知限制

1. **Qoder Sites 不支持 Python 后端**
   - Qoder Sites Functions 运行在 Deno (JavaScript/TypeScript) 环境
   - seekdb 是 Python 嵌入式数据库，无法在 Deno 中运行
   - 需要采用前后端分离架构，后端部署到独立服务器

2. **当前状态**
   - ✅ 本地 Flask + seekdb 应用完全可用
   - ✅ 所有核心功能已实现并验证
   - ✅ 提供 JSON API 接口
   - ⚠️ Qoder Sites 前端为静态展示页，未调用真实后端
   - ❌ 需要部署云服务器才能实现公网完整功能

## 故障排查

### 数据库连接失败

```
RuntimeError: Install requirements first: pip install -r requirements.txt
```

**解决：** 确保已安装 `pylibseekdb` 和 `pymysql`。

### 端口被占用

```
OSError: [Errno 98] Address already in use
```

**解决：** 修改 `app.py` 中的端口号，或停止占用端口的进程。

### 数据丢失

**检查：**
1. 确认 `data/studylog.seekdb` 文件存在
2. 检查文件权限
3. 查看日志中的错误信息

## 开发记录

- **2026-11-02**: 初始版本，完成 Flask + seekdb 后端开发
- **2026-11-03**: 加强测试套件（21 项测试全部通过）
- **2026-11-03**: 添加 JSON API 接口和健康检查端点
- **2026-11-03**: 完善错误处理和日志记录
- **2026-11-03**: 编写技术分析和部署文档

## 许可证

本项目为 OceanBase 2026 竞赛作品。

## 联系方式

如有问题或建议，请通过 GitHub Issues 反馈。
