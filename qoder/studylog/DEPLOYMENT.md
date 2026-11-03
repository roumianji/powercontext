# 部署指南：公网访问架构

## 概述

由于 Qoder Sites 平台限制（仅支持 Deno/JavaScript Functions 和 Supabase 数据库），无法直接部署 Python + seekdb 后端。需要采用**前后端分离架构**：

- **前端**：Qoder Sites（静态 HTML/CSS/JS）
- **后端**：独立云服务器（Flask + seekdb）

## 架构图

```
┌──────────────────────────────────────────────────────────┐
│                    用户浏览器                              │
│              https://studylog-xxx.qoder.zone              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ HTTPS
                     │
┌────────────────────▼─────────────────────────────────────┐
│              Qoder Sites (前端)                           │
│  - 静态 HTML/CSS/JS                                       │
│  - 调用后端 API                                           │
│  - 自动 HTTPS + CDN                                       │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ HTTPS (跨域)
                     │
┌────────────────────▼─────────────────────────────────────┐
│              云服务器 (后端)                               │
│  - Nginx 反向代理                                         │
│  - Flask 应用                                             │
│  - seekdb 数据库                                          │
│  - https://api.yourdomain.com                             │
└──────────────────────────────────────────────────────────┘
```

## 第一步：准备云服务器

### 推荐配置

- **云服务商**：阿里云 ECS / 腾讯云 CVM / 华为云 ECS
- **操作系统**：Ubuntu 22.04 LTS / CentOS 8+
- **配置**：2 核 4GB 内存（最低 1 核 2GB）
- **带宽**：1-5 Mbps
- **磁盘**：40GB+ SSD

### 安全组配置

开放以下端口：
- `22` (SSH)
- `80` (HTTP)
- `443` (HTTPS)

## 第二步：服务器环境配置

### 1. 连接服务器

```bash
ssh root@your-server-ip
```

### 2. 更新系统

```bash
apt update && apt upgrade -y  # Ubuntu/Debian
# 或
yum update -y  # CentOS/RHEL
```

### 3. 安装 Python 3.10+

**Ubuntu 22.04:**
```bash
apt install python3 python3-pip python3-venv -y
python3 --version  # 应该 >= 3.10
```

**CentOS 8+:**
```bash
dnf install python3 python3-pip -y
```

### 4. 安装 Nginx

```bash
apt install nginx -y  # Ubuntu/Debian
# 或
dnf install nginx -y  # CentOS/RHEL

systemctl enable nginx
systemctl start nginx
```

### 5. 安装 Git

```bash
apt install git -y  # Ubuntu/Debian
# 或
dnf install git -y  # CentOS/RHEL
```

## 第三步：部署后端应用

### 1. 克隆代码

```bash
cd /opt
git clone https://github.com/roumianji/powercontext.git
cd powercontext/qoder/studylog
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python seed_data.py
```

### 4. 测试运行

```bash
python app.py
```

访问 `http://your-server-ip:5100/health` 应该返回：
```json
{
  "status": "healthy",
  "database": {...},
  "record_count": 7,
  "timestamp": "..."
}
```

按 `Ctrl+C` 停止。

### 5. 使用 Gunicorn（生产环境）

```bash
pip install gunicorn
```

测试 Gunicorn：
```bash
gunicorn -w 4 -b 127.0.0.1:5100 app:app
```

### 6. 配置 systemd 服务

创建服务文件：
```bash
nano /etc/systemd/system/studylog.service
```

内容：
```ini
[Unit]
Description=StudyLog Flask Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/powercontext/qoder/studylog
Environment="PATH=/opt/powercontext/qoder/studylog/.venv/bin"
ExecStart=/opt/powercontext/qoder/studylog/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5100 app:app

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
systemctl daemon-reload
systemctl enable studylog
systemctl start studylog
systemctl status studylog
```

## 第四步：配置域名和 HTTPS

### 方案 A：使用自有域名

1. **购买域名**（阿里云 / 腾讯云 / Cloudflare）

2. **添加 DNS 解析**
   ```
   类型: A
   主机记录: api
   记录值: your-server-ip
   ```

3. **申请 SSL 证书**（Let's Encrypt）
   ```bash
   apt install certbot python3-certbot-nginx -y
   certbot --nginx -d api.yourdomain.com
   ```

### 方案 B：使用云服务器 IP（测试用）

跳过域名配置，直接使用 IP 访问。

## 第五步：配置 Nginx 反向代理

编辑 Nginx 配置：
```bash
nano /etc/nginx/sites-available/studylog
```

内容（使用域名）：
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

或（使用 IP）：
```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

启用配置：
```bash
ln -s /etc/nginx/sites-available/studylog /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

## 第六步：配置 CORS

修改 `app.py`，添加 CORS 支持：

```bash
pip install flask-cors
```

在 `app.py` 中添加：
```python
from flask_cors import CORS

# 在 app = Flask(__name__) 后添加
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://studylog-86sb51dc8lq.qoder.zone",  # Qoder Sites 域名
            "http://localhost:5100",  # 本地开发
        ]
    }
})
```

重启服务：
```bash
systemctl restart studylog
```

## 第七步：测试后端 API

```bash
# 健康检查
curl https://api.yourdomain.com/health

# 查询记录
curl https://api.yourdomain.com/api/logs

# 新增记录
curl -X POST https://api.yourdomain.com/api/logs \
  -H "Content-Type: application/json" \
  -d '{"log_date":"2026-11-03","project":"测试","completed":"API 测试"}'
```

## 第八步：修改前端调用远程 API

更新 `site/index.html`，添加 API 调用逻辑：

```javascript
const API_BASE = 'https://api.yourdomain.com';

// 查询记录
async function loadLogs() {
  const response = await fetch(`${API_BASE}/api/logs`);
  const data = await response.json();
  if (data.ok) {
    renderLogs(data.data);
  }
}

// 新增记录
async function addLog(formData) {
  const response = await fetch(`${API_BASE}/api/logs`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(formData)
  });
  return await response.json();
}
```

## 第九步：重新发布 Qoder Sites

```bash
cd /home/research/coursework/ob2026-powercontext

# 使用 sites CLI 重新发布
/home/research/.qoder-cn/bin/qoderclicn/qoderclicn-1.1.81 sites \
  --session "cff17e6f-1a1d-48e6-bc1d-7ef813c611cf" \
  prepare_site --input-file qoder/studylog/prepare_input.json

# 发布
/home/research/.qoder-cn/bin/qoderclicn/qoderclicn-1.1.81 sites \
  --session "cff17e6f-1a1d-48e6-bc1d-7ef813c611cf" \
  publish_site --input '{"actionId":"<your-action-id>"}'
```

## 第十步：验证公网访问

1. 访问前端：`https://studylog-86sb51dc8lq.qoder.zone`
2. 测试新增记录
3. 测试查询筛选
4. 测试周报生成
5. 检查浏览器控制台是否有 CORS 错误

## 运维建议

### 日志查看

```bash
# 应用日志
journalctl -u studylog -f

# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 备份数据库

```bash
# 定期备份 seekdb 文件
cp /opt/powercontext/qoder/studylog/data/studylog.seekdb \
   /backup/studylog-$(date +%Y%m%d).seekdb
```

### 监控

使用 systemd 自动重启：
```bash
systemctl status studylog
```

配置 UptimeRobot 或类似服务监控 API 可用性。

### 性能优化

1. **Gunicorn worker 数量**：`CPU 核数 * 2 + 1`
2. **Nginx 缓存**：静态资源缓存
3. **数据库索引**：为常用查询字段添加索引

## 成本估算

| 项目 | 费用（月） |
|------|-----------|
| 云服务器（2核4G） | ¥100-200 |
| 域名（可选） | ¥50-100/年 |
| SSL 证书（Let's Encrypt） | 免费 |
| Qoder Sites | 免费 |
| **总计** | **¥100-200/月** |

## 故障排查

### 后端无法访问

1. 检查服务状态：`systemctl status studylog`
2. 检查端口监听：`netstat -tlnp | grep 5100`
3. 检查防火墙：`ufw status` 或 `firewall-cmd --list-all`
4. 查看日志：`journalctl -u studylog -n 50`

### CORS 错误

1. 确认 `flask-cors` 已安装
2. 检查 CORS 配置中的 origins 是否正确
3. 清除浏览器缓存

### 数据库连接失败

1. 检查 `data/studylog.seekdb` 文件权限
2. 确认 `pylibseekdb` 已正确安装
3. 查看应用日志

## 替代方案

如果不想维护云服务器，可以考虑：

1. **Serverless 平台**：阿里云函数计算 / 腾讯云云函数（需要适配 seekdb）
2. **PaaS 平台**：Heroku / Railway / Render（支持 Python）
3. **容器服务**：阿里云 ACK / 腾讯云 TKE（Docker 部署）

但这些方案可能需要调整 seekdb 的使用方式，因为 seekdb 是嵌入式数据库，需要本地文件系统访问。

## 总结

完成以上 10 个步骤后，你将拥有：

- ✅ 公网可访问的前端（Qoder Sites）
- ✅ 稳定运行的后端（云服务器）
- ✅ seekdb 数据持久化
- ✅ HTTPS 加密通信
- ✅ 完整的 CRUD 功能

**预计部署时间**：2-4 小时（首次）
