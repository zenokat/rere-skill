# Iteration Progress

## Purpose

本文件只承担两件事：

1. 追踪迭代循环进度，确保一个项目未对账通过前，不跳到下一个项目；遇到需要业
务确认的问题时，明确停下，避免反复撞墙。
2. 记录每轮迭代的增量改动，沉淀开发历程，帮助后续项目复用已验证的修复和经验。

## Usage

- 总表只看当前推进状态，用来决定“下一个该做哪个项目，当前项目该不该继续”
- 每个项目保留一个简短历史表，用来记录每轮关键结论和增量改动
- 如果最近一轮结论是 `业务TBD` 或 `blocked`，在问题解决前不要继续该项目
- 只有 `status=matched` 的项目，才可以纳入稳定回归集合

## Project Status

| recog_id | recog_name | status | last_round | next_action | latest_delta |
|---|---|---|---|---|---|
| dine_in_revenue | 堂食收入 | matched | 1 | 保持在稳定回归集合中，后续规则改动后持续回归 | 修复测试侧字段解包、期间筛选、负数 `last_row` 边界与联合键归一化 |
| eleme_delivery_settlement | 饿了么回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现期间或联合键问题，优先回归该项目 | 修复大账单流式读取、只读模式维度误判、忽略 `~$` 临时文件；补强联合键归一化与字段类型规范化 |

`status` 只使用以下几种值：

- `working`：还在继续工程迭代
- `matched`：已与 baseline 对账一致
- `业务TBD`：需要业务确认，当前停止
- `blocked`：遇到外部硬阻碍，当前停止

## Template

为新项目建记录时，复制以下模板：

```md
### <recog_id> / <recog_name>

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | YYYY-MM-DD | validate通过，preview/baseline不一致，继续迭代 | 本轮新增修改 | 本轮关键结论、阻断或下一步 |
```

字段说明：

- `result`：只写本轮最重要的结果，足以判断是否继续、是否换项目、是否应停下等业务确认
- `delta`：只写本轮新增代码、规则、文档、环境处理等增量改动
- `notes`：补充关键背景，例如条数、耗时、阻断原因、下一步动作

## Active Projects

### dine_in_revenue / 堂食收入

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-12 | `validate` 与 `preview` 通过，`preview` 287 条、baseline 287 条，对账一致 | 修复测试侧字段解包、期间筛选、负数 `last_row` 边界与联合键归一化；补强 baseline helper | 已纳入稳定回归集合 |

### eleme_delivery_settlement / 饿了么回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-12 | `validate` 与 `preview` 通过，最新 `preview` 232 条，与 baseline 对账一致 | 修复大账单流式读取、只读模式维度误判、忽略 `~$` 临时文件；补强联合键归一化与字段类型规范化 | 已纳入稳定回归集合 |

## Update Rule

每轮结束后只做两件事：

1. 更新 `Project Status` 中该项目的 `status`、`last_round`、`next_action`、`latest_delta`
2. 在该项目的小表里追加一行，记录本轮 `result`、`delta`、`notes`

如果本轮结论是 `业务TBD` 或 `blocked`，必须把停止原因直接写进 `result` 或 `notes`，
让下一位接手的人不用重新撞一次墙。
