"""研习周记 — Flask 主应用。"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, Response

from database import open_store, DB_PATH

app = Flask(__name__)
app.secret_key = "studylog-local-only"


def _store():
    return open_store()


# ── 首页 / 查询 ──────────────────────────────────────────────

@app.route("/")
def index():
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

    return render_template(
        "index.html",
        logs=logs,
        projects=projects,
        db_info=db_info,
        filters={"project": project, "keyword": keyword,
                 "date_from": date_from, "date_to": date_to},
    )


# ── 新增记录 ──────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        log_date = request.form.get("log_date", "").strip()
        project = request.form.get("project", "").strip()
        completed = request.form.get("completed", "").strip()
        problems = request.form.get("problems", "").strip()
        next_plan = request.form.get("next_plan", "").strip()

        if not log_date or not project or not completed:
            flash("日期、项目和完成事项为必填项", "error")
            return render_template("add.html", form=request.form, today=date.today().isoformat())

        with _store() as store:
            new_id = store.add_log(log_date, project, completed, problems, next_plan)

        flash(f"记录 #{new_id} 已保存", "success")
        return redirect(url_for("index"))

    return render_template("add.html", form={}, today=date.today().isoformat())


# ── 周报生成 ──────────────────────────────────────────────────

@app.route("/report", methods=["GET", "POST"])
def report():
    today = date.today()
    default_from = (today - timedelta(days=today.weekday())).isoformat()  # 本周一
    default_to = today.isoformat()

    if request.method == "POST":
        date_from = request.form.get("date_from", default_from).strip()
        date_to = request.form.get("date_to", default_to).strip()
    else:
        date_from = request.args.get("date_from", default_from)
        date_to = request.args.get("date_to", default_to)

    with _store() as store:
        logs = store.query_logs(date_from=date_from, date_to=date_to)

    # 按项目汇总
    grouped = {}
    for log in logs:
        proj = log["project"]
        if proj not in grouped:
            grouped[proj] = []
        grouped[proj].append(log)

    markdown = _build_markdown(date_from, date_to, grouped)

    return render_template(
        "report.html",
        logs=logs,
        grouped=grouped,
        markdown=markdown,
        date_from=date_from,
        date_to=date_to,
    )


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


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"数据库路径: {DB_PATH}")
    with _store() as store:
        info = store.get_db_info()
        print(f"数据库引擎: {info}")
    app.run(host="127.0.0.1", port=5100, debug=False)
