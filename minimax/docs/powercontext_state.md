# PowerContext 任务状态：第三阶段

## 安装与验证

将本包解压到已有 minimax/ 目录，再执行：

```bash
python -m pip install -r requirements-powercontext.txt
python -m task_state checkpoint
python -m task_state resume
```

后两条命令分别启动一个 Python 进程。checkpoint 核对实际工程上下文和 before 测试日志后，
使用 PowerContext 1.4.1 的 Builtin Runtime / Atomic Memory 接口保存任务摘要。
resume 在新进程中打开相同的 PowerContext 数据库，经其接口发现并精确读取保存的修订，
再根据读出的任务去 seekdb 查询工程资料，将完成项、待办和测试结果加入新的开发上下文。

数据库分工：seekdb 存工程资料；PowerContext 使用其 SQLite 持久化后端存任务状态。
本阶段没有配置生成或嵌入模型，不需要额外模型 API 凭据。

## 明确输入与输出

- checkpoint 输入：当前 .runtime/context.json、对应的真实数据库查询记录、before/after 测试日志和初始测试快照。
- checkpoint 输出：PowerContext 中的 Atomic Memory，以及 evidence/powercontext/ 中的写入结果与真实引用。
- resume 输入：PowerContext 持久化数据库及任务 ID；任务正文与进度从 PowerContext 获取，不从本地摘要文件读取。
- resume 输出：.runtime/context_with_state.json，包含工程资料、task_progress 和 next_action。
- 完整的恢复后上下文也会归档到 evidence/context/；PowerContext 读出和使用记录保存在 evidence/powercontext/。

关键状态位置为 .runtime/powercontext.sqlite3，调度侧文件为 .runtime/powercontext.scheduler.sqlite3。
它们由运行步骤在干净环境中创建，不需要交付自己的本地数据库文件。
checkpoint 与 resume 使用 SDK 返回的真实 Scope ID，不把 Scope 标题当 ID。

## 状态真实性与复用

保存前检查目标测试和回归测试对应同一代码版本，并核对源码/测试哈希。
before 目标测试必须是断言失败，不能是依赖缺失或启动错误；回归测试须成功。
tests/ 必须与初始快照保持一致。只将验证结果的摘要、日志来源和哈希写入任务状态，完整日志仍在 evidence/。

首次 checkpoint 输出“此前同任务状态数量：0”，表明从该任务的空状态开始。
resume 显示保存和读取进程的 PID，并把恢复的 pending[0] 用作后续 next_action。
因此状态参与后续处理，而不是仅读出来打印。

多次 checkpoint 会追加不可变记录；resume 为指定任务选择最近一次保存的状态，再精确读取其引用。
默认任务 ID 是 status-filter-v1，可用全局 --task-id 参数指定其他 ID。
后续修改完成并保存 after 测试、重新导入和查询当前工程后，可执行：

```bash
python -m task_state checkpoint --phase after
python -m task_state resume
```

状态中的“目标测试通过”不能单独证明 MiniMax 实际参与；模型使用记录仍需在后续真实调用中补齐。

## 版本与来源

可选的模块验证命令为 `python -m unittest -v checks.test_powercontext_state`。
其中跨进程检查使用真实 PowerContext SDK 和临时 SQLite 数据库，状态正文为明确的单元测试样例；
这些临时样例不作为课程作品的真实测试结果或 seekdb 操作记录。

- PowerContext：1.4.1，使用 powercontext[builtin]。
- requirements-powercontext.lock 锁定本阶段验证时解析出的运行依赖，面向 Python 3.12 / Linux。
- 原有业务代码、固定测试、修改前快照和日志不包含在这个追加包中。
- 参考：https://github.com/oceanbase/powercontext ，接口以 PyPI 1.4.1 包源码为准。
- 本适配代码由 ChatGPT 辅助编写；不把适配模块开发记作 MiniMax 的代码修改。
