# 研习周记

基于 seekdb (OceanBase 嵌入式引擎) 的个人学习/科研记录工具。

## 功能

1. **新增记录** — 日期、项目、完成事项、遇到的问题、下一步计划
2. **查询记录** — 按日期范围、项目、关键词筛选
3. **生成周报** — 按项目汇总，支持复制/下载 Markdown

## 快速启动

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

## 技术栈

- **后端**: Python + Flask
- **数据库**: seekdb (pylibseekdb + PyMySQL)
- **前端**: 原生 HTML/CSS，无 JS 框架

## 验证步骤

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 新增记录 | 访问 /add，填写表单提交 | 跳转首页，显示"记录 #N 已保存" |
| 查询筛选 | 首页选择项目/日期/关键词 | 只显示匹配记录 |
| 数据持久化 | 停止并重启 app.py | 之前写入的记录仍然存在 |
| 生成周报 | 访问 /report，选择日期范围 | 按项目汇总显示，可复制/下载 Markdown |
| seekdb 引擎 | 查看首页底部 | 显示 `seekdb` 引擎和版本号 |

## 目录结构

```
qoder/studylog/
├── app.py              # Flask 主应用
├── database.py         # seekdb 连接与 CRUD
├── seed_data.py        # 示例数据写入脚本
├── requirements.txt    # Python 依赖
├── templates/          # HTML 模板
│   ├── base.html
│   ├── index.html      # 查询页
│   ├── add.html        # 新增页
│   └── report.html     # 周报页
└── data/               # seekdb 数据文件（gitignore）
```
