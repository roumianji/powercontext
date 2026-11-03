# MiniMax SDD 课程作业：第一阶段初始工程

这是可运行的初始业务工程、规格和固定测试集。它不是完成版提交。
seekdb/OceanBase、MiniMax、PowerContext 的实际接入与使用记录将在后续阶段补齐。

## 环境

Python 3.12，当前阶段只使用 Python 标准库，没有第三方依赖。
将压缩包内容解压到比赛仓库的 minimax/ 目录；目录中应直接出现 demo_app/、tests/ 等。
虚拟环境继续使用已有的 .venv；此包不含虚拟环境，也不改 Git 远程地址。

## 修改前测试

```bash
python tools/run_tests.py regression --label before
python tools/run_tests.py target --label before
```

预期：原有功能 10 个测试通过，退出码 0；新功能 6 个测试以断言失败结束，退出码 1，无环境错误。
每次运行的命令、退出码、Python 版本、Git 提交和全部源码/测试文件哈希写入 evidence/before/。
将后续实际运行结果作为证据；此包不包含助手机器上的测试日志。

## 运行业务程序

```bash
python -m demo_app --port 8088
```

浏览器访问 http://localhost:8088/tasks，或 http://localhost:8088/tasks?q=论文。
初始版本访问 /tasks?status=done 仍返回全部任务，正是本次需要修改的行为。
按 Ctrl+C 停止。示例数据来自 data/tasks.json，内存数据在重启时重新载入。

## 后续任务

1. 将必要规格、代码、测试导入 seekdb/OceanBase，并通过真实查询组装上下文。
2. 将实际查询得到的上下文提供给 MiniMax，仅修改业务实现并记录过程。
3. 用相同的目标测试和回归测试运行 after 验证，保存代码差异和修改后快照。
4. 用 PowerContext 保存任务记录，另一个进程重启后读取并用于后续上下文。
5. 演示规格更新和重新导入，核对输出确实使用新内容。
6. 整理依赖锁定、初始化/重置方法、技术使用记录和一页技术说明。

## 代码来源

此示例由 ChatGPT 辅助为本课程作业新建，不是第三方业务项目的复刻。
初始版本未使用 MiniMax 生成；MiniMax 实际代码修改记录须在后续真实运行中产生。
官方比赛模板：https://github.com/oceanbase/powercontext/tree/2026-competition-ecosystem。
使用其同名分支作为 Git 基线；本包仅提供 minimax/ 内的文件，不含 Git 历史。

## 修改前快照

snapshots/before/ 保存原始业务代码、规格、测试和数据。后续恢复业务代码时使用此目录，
保持 tests/ 不变。before_manifest.json 提供每个快照文件的 SHA-256。
