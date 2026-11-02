#!/usr/bin/env python3
"""自动化验证脚本：测试所有核心功能。"""

import sys
import time
import subprocess
import urllib.request
import urllib.parse

BASE_URL = "http://127.0.0.1:5100"


def fetch(path, method="GET", data=None):
    url = BASE_URL + path
    if data:
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_index():
    """测试首页加载和记录显示。"""
    status, body = fetch("/")
    assert status == 200, f"首页返回 {status}"
    assert "研习周记" in body, "页面标题缺失"
    count = body.count('class="tag"')
    print(f"  [PASS] 首页加载，显示 {count} 条记录")
    return count


def test_filter_project():
    """测试项目筛选。"""
    status, body = fetch("/?project=" + urllib.parse.quote("OceanBase 竞赛"))
    assert status == 200
    count = body.count('class="tag"')
    assert count >= 3, f"OceanBase 竞赛记录数不足: {count}"
    print(f"  [PASS] 项目筛选: OceanBase 竞赛 ({count} 条)")


def test_filter_date():
    """测试日期范围筛选。"""
    status, body = fetch("/?date_from=2026-10-28&date_to=2026-10-29")
    assert status == 200
    assert "2026-10-28" in body
    assert "2026-10-29" in body
    print(f"  [PASS] 日期范围筛选: 2026-10-28 ~ 2026-10-29")


def test_filter_keyword():
    """测试关键词搜索。"""
    status, body = fetch("/?keyword=seekdb")
    assert status == 200
    assert "seekdb" in body.lower()
    print(f"  [PASS] 关键词搜索: seekdb")


def test_add_record():
    """测试新增记录。"""
    status, body = fetch("/add", method="POST", data={
        "log_date": "2026-11-02",
        "project": "验证测试",
        "completed": "自动化验证脚本运行成功",
        "problems": "",
        "next_plan": "完成所有测试",
    })
    assert status in (200, 302), f"新增返回 {status}"
    print(f"  [PASS] 新增记录 (status={status})")


def test_report():
    """测试周报生成。"""
    status, body = fetch("/report?date_from=2026-10-27&date_to=2026-10-31")
    assert status == 200
    assert "周报预览" in body
    assert "OceanBase 竞赛" in body
    assert "论文阅读" in body
    print(f"  [PASS] 周报生成")


def test_report_download():
    """测试 Markdown 下载。"""
    status, body = fetch("/report/download?date_from=2026-10-27&date_to=2026-10-31")
    assert status == 200
    assert "# 研习周报" in body
    assert "## 项目：OceanBase 竞赛" in body
    print(f"  [PASS] Markdown 下载 ({len(body)} 字节)")


def main():
    print("=" * 60)
    print("研习周记 — 自动化验证")
    print("=" * 60)

    tests = [
        ("首页加载", test_index),
        ("项目筛选", test_filter_project),
        ("日期范围筛选", test_filter_date),
        ("关键词搜索", test_filter_keyword),
        ("新增记录", test_add_record),
        ("周报生成", test_report),
        ("Markdown 下载", test_report_download),
    ]

    passed = 0
    failed = 0

    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print("=" * 60)
    print(f"验证结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
