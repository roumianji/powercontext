# 任务列表规格 v1

## 已有行为：修改后必须保持

- KEEP-001：不提供 status 时返回全部任务，保持插入顺序；提供 q 时仍执行原有标题筛选。
- KEEP-002：q 去除首尾空白，匹配标题时忽略大小写。空 q 不限制结果。
- KEEP-003：创建任务时去除标题首尾空白，空标题抛出 ValueError；新任务状态为 todo。
- KEEP-004：任务状态更新和删除保持原有行为；有效状态为 todo、doing、done。
- KEEP-005：查询返回副本，外部修改结果不得改动内部任务数据。

## 本次新增行为

- STATUS-001：query 包含 status 时，按精确状态筛选；todo、doing、done 均受支持，保持原有顺序。
- STATUS-002：status 和 q 同时提供时，两项条件必须同时满足。
- STATUS-003：status 的值不在有效状态中时抛出 ValueError。HTTP 接口将其转为 400。
- STATUS-004：没有匹配任务时返回空列表。

## 必要来源

- 规格：本文件中的 KEEP-001 至 KEEP-005、STATUS-001 至 STATUS-004。
- 需修改的代码：demo_app/service.py 的 TaskBoard.list_tasks。
- 调用上下文：demo_app/__main__.py 中 GET /tasks 对查询参数的处理。
- 功能测试：tests/test_target.py 的 StatusFilterTests。
- 回归测试：tests/test_regression.py 的 ExistingBehaviorTests。
- 初始数据：data/tasks.json。

## 初始版本说明

原版 list_tasks 只处理 q，尚未处理 status；HTTP 接口允许传入查询参数。
目标测试在原版上会因为未按状态筛选而失败，不是依赖缺失或程序无法启动。
后续使用 MiniMax 修改业务实现；两次验证使用同一份测试文件，不改断言或预期。
