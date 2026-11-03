#!/usr/bin/env python3
"""强化测试套件：验证数据库初始化、持久化、重启恢复和异常处理。"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from datetime import date, datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import open_store, Store, DB_PATH


class TestReport:
    """测试报告生成器。"""
    
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add(self, name, passed, message=""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        if passed:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}: {message}")
    
    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"测试总结: {self.passed}/{total} 通过, {self.failed} 失败")
        print("=" * 70)
        return self.failed == 0


def test_database_initialization(report):
    """测试 1: 数据库首次初始化。"""
    print("\n[测试组 1] 数据库初始化")
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test.seekdb"
        
        try:
            # 首次打开，应该自动创建表和结构
            with open_store(test_db) as store:
                info = store.get_db_info()
                report.add(
                    "首次初始化创建数据库",
                    "engine" in info and info["engine"] == "seekdb",
                    f"db_info={info}"
                )
                
                # 验证表结构
                tables = store.execute(
                    "SHOW TABLES LIKE 'study_logs'"
                )
                report.add(
                    "study_logs 表已创建",
                    len(tables) > 0,
                    f"tables={tables}"
                )
                
                # 验证可以插入数据
                new_id = store.add_log(
                    log_date="2026-01-01",
                    project="测试项目",
                    completed="测试事项",
                    problems="",
                    next_plan=""
                )
                report.add(
                    "可以插入数据",
                    new_id > 0,
                    f"new_id={new_id}"
                )
                
        except Exception as e:
            report.add("数据库初始化", False, str(e))


def test_data_persistence(report):
    """测试 2: 数据持久化（写入后重启仍可读取）。"""
    print("\n[测试组 2] 数据持久化")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "persist.seekdb"
        test_data = {
            "log_date": "2026-02-15",
            "project": "持久化测试",
            "completed": "测试数据持久化功能",
            "problems": "无",
            "next_plan": "继续测试"
        }
        
        try:
            # 第一次连接：写入数据
            with open_store(test_db) as store:
                new_id = store.add_log(**test_data)
                report.add(
                    f"写入记录 #{new_id}",
                    new_id > 0,
                    f"id={new_id}"
                )
            
            # 第二次连接：读取数据（模拟重启）
            with open_store(test_db) as store:
                logs = store.query_logs(project="持久化测试")
                found = any(
                    log["log_date"].isoformat() == test_data["log_date"] and
                    log["completed"] == test_data["completed"]
                    for log in logs
                )
                report.add(
                    "重启后数据仍存在",
                    found and len(logs) > 0,
                    f"found={found}, count={len(logs)}"
                )
                
        except Exception as e:
            report.add("数据持久化", False, str(e))


def test_multiple_restarts(report):
    """测试 3: 多次重启不丢失数据。"""
    print("\n[测试组 3] 多次重启")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "restart.seekdb"
        
        try:
            # 连续启动 5 次，每次写入一条记录
            for i in range(5):
                with open_store(test_db) as store:
                    store.add_log(
                        log_date=f"2026-03-0{i+1}",
                        project="重启测试",
                        completed=f"第 {i+1} 次启动",
                        problems="",
                        next_plan=""
                    )
            
            # 最后一次启动，验证所有记录
            with open_store(test_db) as store:
                logs = store.query_logs(project="重启测试")
                report.add(
                    "5 次重启后所有记录完整",
                    len(logs) == 5,
                    f"expected=5, actual={len(logs)}"
                )
                
        except Exception as e:
            report.add("多次重启", False, str(e))


def test_query_filters(report):
    """测试 4: 查询筛选功能。"""
    print("\n[测试组 4] 查询筛选")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "query.seekdb"
        
        try:
            with open_store(test_db) as store:
                # 准备测试数据
                test_records = [
                    ("2026-04-01", "项目A", "完成任务1", "问题1", "计划1"),
                    ("2026-04-02", "项目A", "完成任务2", "问题2", "计划2"),
                    ("2026-04-03", "项目B", "完成任务3", "问题3", "计划3"),
                    ("2026-04-04", "项目B", "seekdb 测试", "问题4", "计划4"),
                ]
                
                for rec in test_records:
                    store.add_log(*rec)
                
                # 测试 1: 按项目筛选
                logs_a = store.query_logs(project="项目A")
                report.add(
                    "按项目筛选（项目A）",
                    len(logs_a) == 2,
                    f"expected=2, actual={len(logs_a)}"
                )
                
                # 测试 2: 按日期范围筛选
                logs_date = store.query_logs(
                    date_from="2026-04-02",
                    date_to="2026-04-03"
                )
                report.add(
                    "按日期范围筛选",
                    len(logs_date) == 2,
                    f"expected=2, actual={len(logs_date)}"
                )
                
                # 测试 3: 按关键词筛选
                logs_kw = store.query_logs(keyword="seekdb")
                report.add(
                    "按关键词筛选",
                    len(logs_kw) == 1 and "seekdb" in logs_kw[0]["completed"],
                    f"found={len(logs_kw)}"
                )
                
                # 测试 4: 组合筛选
                logs_combo = store.query_logs(
                    project="项目B",
                    keyword="seekdb"
                )
                report.add(
                    "组合筛选（项目+关键词）",
                    len(logs_combo) == 1,
                    f"expected=1, actual={len(logs_combo)}"
                )
                
        except Exception as e:
            report.add("查询筛选", False, str(e))


def test_weekly_report_generation(report):
    """测试 5: 周报生成与数据库一致性。"""
    print("\n[测试组 5] 周报生成")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "report.seekdb"
        
        try:
            with open_store(test_db) as store:
                # 准备一周的数据
                store.add_log("2026-05-01", "项目X", "完成任务A", "问题A", "计划A")
                store.add_log("2026-05-02", "项目X", "完成任务B", "问题B", "计划B")
                store.add_log("2026-05-03", "项目Y", "完成任务C", "问题C", "计划C")
                
                # 查询周报数据
                logs = store.query_logs(
                    date_from="2026-05-01",
                    date_to="2026-05-03"
                )
                
                # 按项目分组
                grouped = {}
                for log in logs:
                    proj = log["project"]
                    if proj not in grouped:
                        grouped[proj] = []
                    grouped[proj].append(log)
                
                report.add(
                    "周报数据查询完整",
                    len(logs) == 3,
                    f"expected=3, actual={len(logs)}"
                )
                
                report.add(
                    "按项目分组正确",
                    len(grouped) == 2 and "项目X" in grouped and "项目Y" in grouped,
                    f"projects={list(grouped.keys())}"
                )
                
                # 验证每个项目的记录数
                x_count = len(grouped.get("项目X", []))
                y_count = len(grouped.get("项目Y", []))
                report.add(
                    "项目记录数正确",
                    x_count == 2 and y_count == 1,
                    f"项目X={x_count}, 项目Y={y_count}"
                )
                
        except Exception as e:
            report.add("周报生成", False, str(e))


def test_error_handling(report):
    """测试 6: 异常处理。"""
    print("\n[测试组 6] 异常处理")
    
    # 测试 1: 空数据库查询
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "empty.seekdb"
        
        try:
            with open_store(test_db) as store:
                logs = store.query_logs()
                report.add(
                    "空数据库查询不报错",
                    isinstance(logs, list) and len(logs) == 0,
                    f"logs={logs}"
                )
        except Exception as e:
            report.add("空数据库查询", False, str(e))
    
    # 测试 2: 无效日期格式（应该被数据库拒绝或正确处理）
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "invalid.seekdb"
        
        try:
            with open_store(test_db) as store:
                # 尝试插入无效日期
                try:
                    store.add_log("invalid-date", "测试", "事项", "", "")
                    report.add("无效日期处理", False, "应该抛出异常但未抛出")
                except Exception:
                    report.add("无效日期被正确拒绝", True, "抛出异常")
        except Exception as e:
            report.add("无效日期测试", False, str(e))
    
    # 测试 3: 空字符串字段
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "empty_fields.seekdb"
        
        try:
            with open_store(test_db) as store:
                new_id = store.add_log(
                    "2026-06-01",
                    "测试",
                    "完成事项",
                    "",  # 空问题
                    ""   # 空计划
                )
                log = store.get_log_by_id(new_id)
                report.add(
                    "空字符串字段可正常存储",
                    log is not None and log["problems"] == "" and log["next_plan"] == "",
                    f"log={log}"
                )
        except Exception as e:
            report.add("空字符串字段", False, str(e))


def test_concurrent_access(report):
    """测试 7: 并发访问（顺序快速开关）。"""
    print("\n[测试组 7] 并发访问")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "concurrent.seekdb"
        
        try:
            # 快速连续打开和关闭
            for i in range(10):
                with open_store(test_db) as store:
                    store.add_log(
                        f"2026-07-{i+1:02d}",
                        "并发测试",
                        f"事项{i}",
                        "",
                        ""
                    )
            
            # 验证所有记录
            with open_store(test_db) as store:
                logs = store.query_logs(project="并发测试")
                report.add(
                    "10 次快速开关后数据完整",
                    len(logs) == 10,
                    f"expected=10, actual={len(logs)}"
                )
        except Exception as e:
            report.add("并发访问", False, str(e))


def test_production_database(report):
    """测试 8: 生产数据库验证。"""
    print("\n[测试组 8] 生产数据库")
    
    try:
        if not DB_PATH.exists():
            report.add("生产数据库存在", False, f"{DB_PATH} 不存在")
            return
        
        with open_store() as store:
            # 验证数据库信息
            info = store.get_db_info()
            report.add(
                "生产数据库引擎正确",
                info.get("engine") == "seekdb",
                f"info={info}"
            )
            
            # 验证有数据
            logs = store.query_logs()
            report.add(
                f"生产数据库有记录 ({len(logs)} 条)",
                len(logs) > 0,
                f"count={len(logs)}"
            )
            
            # 验证可以新增
            new_id = store.add_log(
                date.today().isoformat(),
                "测试项目",
                "自动化测试写入",
                "",
                ""
            )
            report.add(
                f"生产数据库可写入 (id={new_id})",
                new_id > 0,
                f"new_id={new_id}"
            )
            
            # 验证可以查询到新增记录
            log = store.get_log_by_id(new_id)
            report.add(
                "新增记录可查询",
                log is not None and log["completed"] == "自动化测试写入",
                f"log={log}"
            )
            
    except Exception as e:
        report.add("生产数据库测试", False, str(e))


def main():
    print("=" * 70)
    print("研习周记 — 强化测试套件")
    print("=" * 70)
    
    report = TestReport()
    
    # 运行所有测试组
    test_database_initialization(report)
    test_data_persistence(report)
    test_multiple_restarts(report)
    test_query_filters(report)
    test_weekly_report_generation(report)
    test_error_handling(report)
    test_concurrent_access(report)
    test_production_database(report)
    
    # 生成报告
    success = report.summary()
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
