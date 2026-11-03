# MiniMax 实际代码修改：第四阶段

## 本机配置与运行

将本包解压到已有 minimax/ 目录，保持虚拟环境激活：

```bash
python -m pip install -r requirements-minimax.txt
python -m coding_assistant configure
python -m coding_assistant run
```

configure 使用终端隐藏输入读取订阅 Key，在本机保存到 .env（权限 600），补齐 .gitignore 中的
.env 与 .runtime/ 排除项。它不调用模型。已有配置时，Key 留空表示保留原值。
模型和 Base URL 可以交互修改；也可以通过对应的 MINIMAX_* 环境变量覆盖 .env。
示例文件仅使用占位值，不含真实凭据。使用套餐详情中的订阅 Key；普通按量计费 Key 属于另一种计费方式。

默认接入方式：Python 3.12 标准库 urllib，通过 Anthropic 兼容的 Messages HTTP 接口调用
https://api.minimax.cn/anthropic/v1/messages。默认模型 MiniMax-M3.1-Flash，思考深度 low，
输出上限 8192，超时 240 秒。输出上限包含模型的思考 token。
此默认值依据 2026-11-01 查阅的官方文档；账号可用模型及服务区域以套餐和官方当前说明为准。

## 实际流程

1. 通过 task_state resume 在新进程读取 PowerContext，并经 seekdb 查询当前工程资料。
2. 保存本次实际输入上下文和请求正文，向 MiniMax 发出一次生成请求，无自动重试。
3. 只提取模型的公开文本结果，不保存 thinking 私有推理内容。
4. 模型返回完整业务文件；校验修改仅限 TaskBoard.list_tasks 函数体，语法须有效，固定测试不可改变。
5. 保存本次修改前/后源码和 code.diff，应用模型返回的候选代码，运行同一套目标测试与回归测试。
6. 两组测试均通过后，重新导入/查询修改后的工程，并用 PowerContext 保存和复用 after 状态。

代码生成没有预设补丁或本地实现兜底，API 请求失败不会被当作 MiniMax 已完成修改。
目标测试/回归测试未全部通过时，保留失败候选和日志，自动恢复本次修改前的业务源码。
校验约束针对本作业的狭窄修改范围，不宣称是运行任意不可信 Python 的安全沙箱。

## 技术使用记录

每次实际运行建立 evidence/minimax/<运行ID>/，包含：

- input_context.json：真实输入，含 seekdb 工程资料及 PowerContext 恢复的进度与引用。
- request_body.json：实际发送的任务和上下文，不包含认证请求头。
- response_text.txt：MiniMax 返回的公开文本，不包含 thinking 块。
- before/demo_app/service.py 与 after/demo_app/service.py：对应本次修改的源码快照。
- code.diff：与候选代码对应的修改差异。
- record.json：模型、接口、请求/响应标识、用量、源码哈希、测试命令/退出码和状态收尾记录。

完整测试日志仍由 tools/run_tests.py 写入 evidence/after/，数据库记录和状态使用记录沿用各模块的 evidence 目录。
网络/模型错误不会自动反复发起收费请求。日志不保存认证头、真实 Key 或私有思维链。

## 收尾失败的恢复

如果代码与测试已经成功，但资料重导入或 after 状态保存失败，源码保持在已验证的修改后状态。
修复对应问题后执行：

```bash
python -m coding_assistant finalize
```

finalize 只为与当前源码匹配、且测试已通过的实际模型运行补做收尾，不重新调用 MiniMax。
如果生成或测试失败，则先查看本次记录，再决定是否手动重试 run。
运行成功后仍需演示规格更新、整理最终运行说明和一页技术说明，并提交到比赛分支。

## 参考与来源

可选检查命令：`python -m unittest -v checks.test_coding_assistant`。
其中 HTTP 响应由明确的模拟接口提供，代码候选仅是临时单元测试样例；它们不作为正式 MiniMax 使用记录。
正式业务代码不包含这些测试候选，也不会在 API 失败时使用它们代替模型生成。

- MiniMax 其他工具接入：https://platform.minimax.cn/docs/m-plan/other-tools
- Anthropic 兼容协议：https://platform.minimax.cn/docs/api-reference/text-anthropic-api
- 订阅 Key 获取：https://platform.minimax.cn/docs/m-plan/quickstart
- 本调用模块由 ChatGPT 辅助编写；只有实际 run 产生的 MiniMax 响应、代码差异和验证结果，才记为 MiniMax 的本次代码修改。
