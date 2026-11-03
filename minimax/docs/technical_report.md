# MiniMax × PowerContext 课程作业技术说明

## 1. 任务目标

在已有任务列表程序中增加 status 筛选功能，同时保持原有功能不变。

支持 todo、doing、done 三种状态，并允许与标题关键词 q 组合筛选。

## 2. 技术方案

本项目使用：

- seekdb：存储并检索工程资料
- PowerContext：保存与恢复开发任务状态
- MiniMax-M3.1-Flash：根据工程上下文生成代码修改
- Python unittest：执行功能和回归测试

## 3. 实施过程

1. 将 6 份工程资料导入 seekdb。
2. 检索相关代码、规格、测试和初始数据。
3. 执行修改前测试，记录基线。
4. 使用 PowerContext 保存并恢复任务状态。
5. 调用 MiniMax API 生成 status 筛选代码。
6. 校验代码修改范围并应用修改。
7. 执行修改后目标测试与回归测试。
8. 更新工程资料和规格文档，重新导入 seekdb。
9. 保存并恢复修改后的 PowerContext 状态。

## 4. 实验结果

| 项目 | 修改前 | 修改后 |
| --- | --- | --- |
| 目标测试 | 0/6 | 6/6 |
| 回归测试 | 10/10 | 10/10 |

MiniMax 实际调用：
- 模型：MiniMax-M3.1-Flash
- 输入 Token：5334
- 输出 Token：537
- 响应耗时：14.132 秒
- 自动重试：0 次

实际修改文件：demo_app/service.py

## 5. 证据

- MiniMax 调用记录：evidence/minimax/
- 修改前后测试：evidence/before/、evidence/after/
- seekdb 数据操作：evidence/database/
- 上下文检索：evidence/context/
- PowerContext 状态记录：evidence/powercontext/

## 6. 结论

本次实验验证了基于 seekdb 工程上下文、
PowerContext 任务状态管理与 MiniMax 代码生成的开发流程。

目标功能实现成功，全部固定测试通过，
并完成修改后工程资料的更新与任务状态恢复。
