"""研习周记 — Flask 主应用。"""

import json
import logging
import os
import secrets
import sys
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify

from database import open_store, DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("STUDYLOG_SECRET", "studylog-local-only")
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

SITE_DIR = Path(__file__).parent / "site"

API_KEY = os.environ.get("STUDYLOG_API_KEY", "")
CORS_ORIGINS = os.environ.get("STUDYLOG_CORS_ORIGINS", "").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]


@app.after_request
def add_cors_headers(response):
    if not CORS_ORIGINS:
        return response
    origin = request.headers.get("Origin", "")
    if origin in CORS_ORIGINS or "*" in CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["Access-Control-Max-Age"] = "3600"
    return response


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            return f(*args, **kwargs)
        provided = request.headers.get("X-API-Key", "")
        if not secrets.compare_digest(provided, API_KEY):
            logger.warning(f"API key 验证失败: ip={request.remote_addr}")
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def _store():
    """获取数据库连接，带错误处理。"""
    try:
        return open_store()
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "请求体过大"}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "not_found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"ok": False, "error": "method_not_allowed"}), 405


# ── 首页 / 查询 ──────────────────────────────────────────────

@app.route("/")
def index():
    try:
        project = request.args.get("project", "").strip()
        keyword = request.args.get("keyword", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        with _store() as store:
            logs = store.query_logs(
                date_from=date_from or None,
                date_to=date_to or None,
                project=project or None,
                keyword=keyword or None,
            )
            projects = store.list_projects()
            db_info = store.get_db_info()

        logger.info(f"查询记录: project={project}, keyword={keyword}, "
                   f"date_from={date_from}, date_to={date_to}, results={len(logs)}")

        return render_template(
            "index.html",
            logs=logs,
            projects=projects,
            db_info=db_info,
            filters={"project": project, "keyword": keyword,
                     "date_from": date_from, "date_to": date_to},
        )
    except Exception as e:
        logger.error(f"首页查询失败: {e}", exc_info=True)
        flash(f"查询失败: {str(e)}", "error")
        return render_template("index.html", logs=[], projects=[], db_info={},
                             filters={"project": "", "keyword": "", "date_from": "", "date_to": ""})


# ── 新增记录 ──────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
@require_api_key
def add():
    if request.method == "POST":
        try:
            log_date = request.form.get("log_date", "").strip()
            project = request.form.get("project", "").strip()
            completed = request.form.get("completed", "").strip()
            problems = request.form.get("problems", "").strip()
            next_plan = request.form.get("next_plan", "").strip()

            if not log_date or not project or not completed:
                flash("日期、项目和完成事项为必填项", "error")
                return render_template("add.html", form=request.form, today=date.today().isoformat())

            try:
                datetime.strptime(log_date, '%Y-%m-%d')
            except ValueError:
                flash("日期格式无效，请使用 YYYY-MM-DD", "error")
                return render_template("add.html", form=request.form, today=date.today().isoformat())

            with _store() as store:
                new_id = store.add_log(log_date, project, completed, problems, next_plan)

            logger.info(f"新增记录 #{new_id}: date={log_date}, project={project}")
            flash(f"记录 #{new_id} 已保存", "success")
            return redirect(url_for("index"))
        
        except Exception as e:
            logger.error(f"新增记录失败: {e}", exc_info=True)
            flash(f"保存失败: {str(e)}", "error")
            return render_template("add.html", form=request.form, today=date.today().isoformat())

    return render_template("add.html", form={}, today=date.today().isoformat())


# ── 周报生成 ──────────────────────────────────────────────────

@app.route("/report", methods=["GET", "POST"])
def report():
    try:
        today = date.today()
        default_from = (today - timedelta(days=today.weekday())).isoformat()
        default_to = today.isoformat()

        if request.method == "POST":
            date_from = request.form.get("date_from", default_from).strip()
            date_to = request.form.get("date_to", default_to).strip()
        else:
            date_from = request.args.get("date_from", default_from)
            date_to = request.args.get("date_to", default_to)

        with _store() as store:
            logs = store.query_logs(date_from=date_from, date_to=date_to)

        grouped = {}
        for log in logs:
            proj = log["project"]
            if proj not in grouped:
                grouped[proj] = []
            grouped[proj].append(log)

        markdown = _build_markdown(date_from, date_to, grouped)
        logger.info(f"生成周报: date_from={date_from}, date_to={date_to}, records={len(logs)}")

        return render_template(
            "report.html",
            logs=logs,
            grouped=grouped,
            markdown=markdown,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        logger.error(f"周报生成失败: {e}", exc_info=True)
        flash(f"生成周报失败: {str(e)}", "error")
        return render_template("report.html", logs=[], grouped={}, markdown="", 
                             date_from="", date_to="")


@app.route("/report/download")
def report_download():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    with _store() as store:
        logs = store.query_logs(date_from=date_from or None, date_to=date_to or None)

    grouped = {}
    for log in logs:
        proj = log["project"]
        if proj not in grouped:
            grouped[proj] = []
        grouped[proj].append(log)

    markdown = _build_markdown(date_from, date_to, grouped)

    return Response(
        markdown,
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=weekly_report_{date_from}_{date_to}.md"},
    )


def _build_markdown(date_from: str, date_to: str, grouped: dict) -> str:
    lines = [f"# 研习周报 ({date_from} ~ {date_to})", ""]
    if not grouped:
        lines.append("所选日期范围内无记录。")
        return "\n".join(lines)

    for proj, logs in grouped.items():
        lines.append(f"## 项目：{proj}")
        lines.append("")

        lines.append("### 完成事项")
        for log in logs:
            lines.append(f"- **{log['log_date']}**：{log['completed']}")
        lines.append("")

        problems = [log["problems"] for log in logs if log.get("problems")]
        if problems:
            lines.append("### 遇到的问题")
            for p in problems:
                lines.append(f"- {p}")
            lines.append("")

        plans = [log["next_plan"] for log in logs if log.get("next_plan")]
        if plans:
            lines.append("### 下一步计划")
            for p in plans:
                lines.append(f"- {p}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── 健康检查和 API ────────────────────────────────────────────

@app.route("/health")
def health():
    """健康检查端点，用于监控和负载均衡。"""
    try:
        with _store() as store:
            info = store.get_db_info()
            count = len(store.query_logs())
        return jsonify({
            "status": "healthy",
            "database": info,
            "record_count": count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": "server_error",
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route("/api/logs", methods=["GET"])
def api_list_logs():
    """JSON API: 查询记录列表。"""
    try:
        project = request.args.get("project", "").strip()
        keyword = request.args.get("keyword", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        with _store() as store:
            logs = store.query_logs(
                date_from=date_from or None,
                date_to=date_to or None,
                project=project or None,
                keyword=keyword or None,
            )
            # 转换日期对象为字符串
            for log in logs:
                if isinstance(log.get("log_date"), date):
                    log["log_date"] = log["log_date"].isoformat()
                if isinstance(log.get("created_at"), datetime):
                    log["created_at"] = log["created_at"].isoformat()

        return jsonify({"ok": True, "data": logs, "count": len(logs)})
    except Exception as e:
        logger.error(f"API 查询失败: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "server_error"}), 500


@app.route("/api/logs", methods=["POST", "OPTIONS"])
@require_api_key
def api_add_log():
    """JSON API: 新增记录。"""
    if request.method == "OPTIONS":
        return "", 204
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "请求体必须是 JSON"}), 400

        log_date = data.get("log_date", "").strip()
        project = data.get("project", "").strip()
        completed = data.get("completed", "").strip()
        problems = data.get("problems", "").strip()
        next_plan = data.get("next_plan", "").strip()

        if not log_date or not project or not completed:
            return jsonify({"ok": False, "error": "日期、项目和完成事项为必填项"}), 400

        try:
            datetime.strptime(log_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"ok": False, "error": "日期格式无效"}), 400

        if len(project) > 128:
            return jsonify({"ok": False, "error": "项目名过长"}), 400
        if len(completed) > 10000 or len(problems) > 10000 or len(next_plan) > 10000:
            return jsonify({"ok": False, "error": "内容过长"}), 400

        with _store() as store:
            new_id = store.add_log(log_date, project, completed, problems, next_plan)

        logger.info(f"API 新增记录 #{new_id}: date={log_date}, project={project}")
        return jsonify({"ok": True, "id": new_id, "message": f"记录 #{new_id} 已保存"})
    except Exception as e:
        logger.error(f"API 新增失败: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "server_error"}), 500


@app.route("/api/projects")
def api_list_projects():
    """JSON API: 获取所有项目列表。"""
    try:
        with _store() as store:
            projects = store.list_projects()
        return jsonify({"ok": True, "data": projects})
    except Exception as e:
        logger.error(f"API 获取项目列表失败: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "server_error"}), 500


@app.route("/api/report")
def api_report():
    """JSON API: 生成周报数据。"""
    try:
        today = date.today()
        default_from = (today - timedelta(days=today.weekday())).isoformat()
        default_to = today.isoformat()

        date_from = request.args.get("date_from", default_from).strip()
        date_to = request.args.get("date_to", default_to).strip()

        with _store() as store:
            logs = store.query_logs(date_from=date_from, date_to=date_to)
            for log in logs:
                if isinstance(log.get("log_date"), date):
                    log["log_date"] = log["log_date"].isoformat()
                if isinstance(log.get("created_at"), datetime):
                    log["created_at"] = log["created_at"].isoformat()

        grouped = {}
        for log in logs:
            proj = log["project"]
            if proj not in grouped:
                grouped[proj] = []
            grouped[proj].append(log)

        markdown = _build_markdown(date_from, date_to, grouped)
        logger.info(f"API 周报: {date_from}~{date_to}, {len(logs)} 条记录")

        return jsonify({
            "ok": True,
            "date_from": date_from,
            "date_to": date_to,
            "count": len(logs),
            "grouped": grouped,
            "markdown": markdown,
        })
    except Exception as e:
        logger.error(f"API 周报失败: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "server_error"}), 500


@app.route("/app")
@app.route("/app/")
def serve_site_app():
    """提供前端应用页面（本地测试用）。"""
    index_path = SITE_DIR / "index.html"
    if index_path.exists():
        return Response(index_path.read_bytes(), mimetype="text/html; charset=utf-8")
    return "site/index.html not found", 404


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("研习周记 — Flask 应用启动")
    logger.info("=" * 60)
    logger.info(f"数据库路径: {DB_PATH}")
    
    try:
        with _store() as store:
            info = store.get_db_info()
            count = len(store.query_logs())
            logger.info(f"数据库引擎: {info.get('engine')} v{info.get('version')}")
            logger.info(f"现有记录数: {count}")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("启动 Web 服务器: http://0.0.0.0:5100")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 60)
    
    app.run(host="0.0.0.0", port=5100, debug=False)
