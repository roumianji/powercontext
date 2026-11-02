"""向 seekdb 写入示例数据，用于验证。"""

from database import open_store

SAMPLE_DATA = [
    {
        "log_date": "2026-10-27",
        "project": "OceanBase 竞赛",
        "completed": "搭建项目框架，完成 seekdb 接入调研",
        "problems": "pylibseekdb 文档较少，需要参考 minimax 示例",
        "next_plan": "实现数据库层 CRUD 接口",
    },
    {
        "log_date": "2026-10-28",
        "project": "OceanBase 竞赛",
        "completed": "完成 database.py，实现 add/query/report 三个核心方法",
        "problems": "seekdb 的 LOCATE 函数与 SQLite 不兼容，需直接用 pymysql",
        "next_plan": "开发 Flask Web 界面",
    },
    {
        "log_date": "2026-10-29",
        "project": "OceanBase 竞赛",
        "completed": "Flask 前端三个页面完成：查询、新增、周报",
        "problems": "",
        "next_plan": "编写示例数据和验证脚本",
    },
    {
        "log_date": "2026-10-27",
        "project": "论文阅读",
        "completed": "阅读 Retrieval-Augmented Generation 综述论文",
        "problems": "论文中公式较多，需要额外查阅背景知识",
        "next_plan": "整理 RAG 相关笔记，准备组会汇报",
    },
    {
        "log_date": "2026-10-28",
        "project": "论文阅读",
        "completed": "完成 RAG 论文笔记，制作组会 PPT",
        "problems": "",
        "next_plan": "开始阅读 Vector Database 性能对比论文",
    },
    {
        "log_date": "2026-10-30",
        "project": "论文阅读",
        "completed": "阅读 Milvus vs Pinecone 性能评测论文",
        "problems": "部分实验数据难以复现",
        "next_plan": "总结向量数据库选型建议",
    },
    {
        "log_date": "2026-10-31",
        "project": "课程作业",
        "completed": "完成操作系统实验三：内存管理模拟器",
        "problems": "页面置换算法 LRU 实现有 bug",
        "next_plan": "调试并完善实验报告",
    },
]


def seed():
    with open_store() as store:
        existing = store.query_logs()
        if existing:
            print(f"数据库已有 {len(existing)} 条记录，跳过写入示例数据。")
            return

        for item in SAMPLE_DATA:
            new_id = store.add_log(**item)
            print(f"  写入 #{new_id}: {item['log_date']} [{item['project']}]")

        total = len(store.query_logs())
        print(f"\n共写入 {total} 条示例记录。")


if __name__ == "__main__":
    seed()
