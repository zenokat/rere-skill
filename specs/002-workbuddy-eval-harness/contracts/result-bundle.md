# Contract: 结果包与证据包

## Purpose

结果包是本 feature 的统一输出契约。它需要同时满足：

- Agent 稳定读取
- 人工快速复盘
- 后续保存为 baseline
- 后续做 regression diff

## Canonical Files

### `batch.json`

批次级结构化总结果。

至少包含：

| Field | Type | Description |
|---|---|---|
| `batch_id` | string | 批次标识 |
| `suite_id` | string | case 集标识 |
| `overall_status` | string | `passed`、`regressed`、`environment_blocked`、`harness_error` |
| `started_at` | datetime | 开始时间 |
| `finished_at` | datetime | 结束时间 |
| `target` | object | 被测 skill、runner、版本信息 |
| `case_results` | list[object] | 每条 case 的摘要 |
| `summary_counts` | object | 聚合计数 |
| `artifacts` | object | 相关产物引用 |

### `summary.md`

批次级面向人的摘要。

至少回答三件事：

1. 这轮评测覆盖了什么
2. 主要问题集中在哪
3. 下一轮更应该先改 skill、工具、环境还是 harness

### `cases/<case_id>/run.json`

单 case 的主结果文件。

至少包含：

| Field | Type | Description |
|---|---|---|
| `case_id` | string | case 标识 |
| `run_id` | string | 本次运行标识 |
| `session_id` | string? | 会话 ID |
| `workspace_dir` | string | 本次 case 独立工作目录 |
| `cleanup_status` | string | 工作目录清理状态 |
| `status` | string | 运行状态 |
| `outcome_class` | string | 结果分类 |
| `failure_source` | string? | 失败归因 |
| `final_message` | string | 最终结论摘要 |
| `evidence` | object | 证据文件引用 |
| `scorecard_ref` | path | 评分卡路径 |

### `cases/<case_id>/scorecard.json`

单 case 的维度化评分结果。

至少包含：

| Field | Type | Description |
|---|---|---|
| `total_score` | number | 总分 |
| `final_verdict` | string | 最终结论 |
| `grader_outputs` | list[object] | 评分器原始输出 |
| `dimensions` | list[object] | 逐维度分数、理由、grader 类型 |
| `evidence_gaps` | list[string] | 影响评分的证据缺口 |

### `cases/<case_id>/evidence.md`

面向人的证据导航页。

至少列出：

- CLI 调用摘要
- `session_id`
- transcript / trace / stdout / stderr / final JSON 的路径
- 哪些证据缺失、会不会影响评分

## Evidence Completeness

结果包必须显式区分三种情况：

- `complete`: 证据齐全
- `partial`: 证据部分缺失，但还能形成有限评分
- `failed`: 证据采集失败，无法可靠评分

不要把 `partial` 默默伪装成完整成功。

## Grader Compatibility Rule

结果包必须允许同时容纳默认评分器和扩展评分器：

- 默认评分器输出要稳定可比较
- 扩展评分器输出可以增量增加，但必须带 `grader_id` 和 `version`
- baseline compare 发现评分器集合或版本发生变化时，必须把该差异纳入可比性判断

## Human + Agent Dual Consumption Rule

同一轮评测不得维护两套完全不同的主结果格式。

稳定主格式应是：

- 机器主入口：`batch.json`、`run.json`、`scorecard.json`
- 人工主入口：`summary.md`、`evidence.md`

Markdown 只能作为阅读增强，不能替代 JSON 主契约。
