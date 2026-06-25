# Data Model: 收入确认 WorkBuddy 自动化评测底座

## Overview

这个 feature 的核心不是单条命令，而是一套“稳定 case -> 独立 trial -> 证据包 ->
评分卡 -> 基线快照 -> 回归视图”的评测数据链。数据模型需要同时服务三类对象：

- 批量执行器：知道该跑哪些 case、如何发起、如何归档。
- 评分与回归系统：知道每条 case 的预期、得分、差异和失败归因。
- 人与 Agent 调用方：都能读懂同一套结果，不需要双份格式。

## Entities

### EvalCase

表示一条可重复执行的评测样本。

| Field | Type | Description |
|---|---|---|
| `case_id` | string | 稳定且可复用的 case 主键 |
| `title` | string | 人可读标题 |
| `stage` | string | 所属业务阶段，首版固定为 `rollup` |
| `prompt` | string | 发给被测 skill 的任务说明 |
| `inputs` | list[`CaseInputRef`] | 该 case 需要的输入材料 |
| `expectation_type` | enum | `success`、`correct_stop`、`environment_failure` |
| `scoring_focus` | list[string] | 本 case 重点关注的评分维度 |
| `safety_profile` | object | 是否允许写操作、是否要求安全环境 |
| `tags` | list[string] | 方便筛选的标签 |
| `enabled` | boolean | 当前是否参与批量运行 |
| `case_version` | string | case 自身版本号，用于兼容比较 |

补充约束：

- `case_id` 一旦进入基线，不应因文案小改动而修改。
- 若 case 行为定义发生实质变化，应提升 `case_version`，而不是偷改历史基线含义。

### CaseInputRef

表示一项输入材料引用。

| Field | Type | Description |
|---|---|---|
| `kind` | enum | `file`、`directory`、`inline_text`、`reference_doc`、`env_check` |
| `path_or_value` | string | 路径、文本或检查值 |
| `required` | boolean | 是否为必需输入 |
| `materialize_mode` | enum | `copy`、`link`、`reference` |
| `description` | string | 该输入在业务上的作用 |

### EvalBatch

表示一次批量评测运行。

| Field | Type | Description |
|---|---|---|
| `batch_id` | string | 本轮批次唯一标识 |
| `suite_id` | string | 使用的 case 集主键 |
| `runner` | enum | 首版固定为 `codebuddy_headless` |
| `target_skill` | string | 被测 skill 名称 |
| `started_at` | datetime | 批次开始时间 |
| `finished_at` | datetime? | 批次结束时间 |
| `case_ids` | list[string] | 本轮实际执行的 case 列表 |
| `baseline_ref` | string? | 用于比较的 baseline 标识 |
| `settings_profile_ref` | string | 本轮使用的默认/扩展设置 |
| `overall_status` | enum | `passed`、`regressed`、`environment_blocked`、`harness_error` |

### TrialRun

表示某条 case 在某一轮中的实际运行。

| Field | Type | Description |
|---|---|---|
| `run_id` | string | trial 唯一标识 |
| `batch_id` | string | 所属批次 |
| `case_id` | string | 所属 case |
| `session_id` | string? | CodeBuddy / WorkBuddy 会话 ID |
| `command_line` | string | 实际调用命令 |
| `permission_mode` | string | 本次运行的权限模式 |
| `output_format` | enum | `json` 或 `stream-json` |
| `status` | enum | `queued`、`running`、`completed`、`failed`、`inconclusive` |
| `outcome_class` | enum | `pass`、`correct_stop`、`environment_failure`、`skill_failure`、`harness_failure`、`evidence_missing` |
| `failure_source` | enum? | `skill_behavior`、`wrapped_tool`、`runtime_environment`、`harness_system` |
| `exit_code` | integer? | 运行进程退出码 |
| `started_at` | datetime | 开始时间 |
| `finished_at` | datetime? | 结束时间 |

### EvidenceBundle

表示与单条 trial 绑定的证据集合。

| Field | Type | Description |
|---|---|---|
| `evidence_id` | string | 证据包标识 |
| `run_id` | string | 所属 trial |
| `summary_path` | path | 面向人的摘要文件 |
| `stdout_path` | path | 标准输出落盘 |
| `stderr_path` | path | 标准错误落盘 |
| `final_json_path` | path | CLI `json` 结果文件 |
| `transcript_path` | path? | `stream-json` transcript 文件 |
| `telemetry_ref` | string? | 外部 OTel trace 标识或查询入口 |
| `missing_items` | list[string] | 缺失的证据项 |
| `collection_status` | enum | `complete`、`partial`、`failed` |
| `score_impact` | enum | `none`、`warning`、`blocking` |

补充说明：

- `collection_status=partial` 不等于 skill 失败；它首先是证据层状态。
- `score_impact` 用于说明证据缺失是否妨碍自动评分。

### ScoreDimension

表示一个评分维度定义。

| Field | Type | Description |
|---|---|---|
| `dimension_id` | string | 维度主键 |
| `name` | string | 维度名称 |
| `grader_type` | enum | `deterministic`、`rubric`、`human` |
| `weight` | number | 权重 |
| `required` | boolean | 是否为首版默认维度 |
| `version` | string | 维度规则版本 |

首版默认维度至少包括：

- `task_understanding`
- `tool_selection`
- `parameter_completeness`
- `result_interpretation`
- `failure_handling`
- `boundary_compliance`

### ScoreCard

表示某条 case 的评分结果。

| Field | Type | Description |
|---|---|---|
| `scorecard_id` | string | 评分卡标识 |
| `run_id` | string | 所属 trial |
| `dimension_scores` | list[object] | 各维度分数与理由 |
| `total_score` | number | 汇总分 |
| `final_verdict` | enum | `pass`、`pass_with_warning`、`fail`、`not_scorable` |
| `grader_versions` | map | 使用到的评分器版本 |
| `notes` | list[string] | 额外说明 |

### BaselineSnapshot

表示某一轮被正式保存的基线快照。

| Field | Type | Description |
|---|---|---|
| `baseline_id` | string | 基线主键 |
| `suite_id` | string | 所属 case 集 |
| `created_from_batch_id` | string | 来源批次 |
| `created_at` | datetime | 创建时间 |
| `case_versions` | map | 每条 case 对应的版本 |
| `skill_version` | string? | 被测 skill 版本 |
| `prompt_version` | string? | prompt / skill 包版本 |
| `environment_fingerprint` | object | 运行环境指纹 |
| `scorer_versions` | map | 评分器版本 |
| `case_results` | list[object] | 每条 case 的结论、分数、证据引用 |
| `approval_status` | enum | `draft`、`reviewed`、`promoted` |

### RegressionDiff

表示某轮结果与基线的比较产物。

| Field | Type | Description |
|---|---|---|
| `diff_id` | string | 对比标识 |
| `batch_id` | string | 当前批次 |
| `baseline_id` | string | 对比基线 |
| `case_diffs` | list[object] | 逐 case 差异 |
| `summary_counts` | map | 各类差异数量 |
| `regression_status` | enum | `clean`、`regressed`、`mixed`、`not_comparable` |

逐 case 差异至少区分：

- `unchanged`
- `fixed`
- `regressed`
- `new_issue`
- `not_comparable`

### EvalSettingsProfile

表示一套评测设置。

| Field | Type | Description |
|---|---|---|
| `profile_id` | string | 配置主键 |
| `base_profile` | string? | 继承自哪个默认配置 |
| `evidence_rules` | list[object] | 证据采集项定义 |
| `score_dimensions` | list[`ScoreDimension`] | 当前生效的评分维度 |
| `result_views` | list[string] | 需要产出的视图 |
| `profile_type` | enum | `default`、`extension` |
| `compatibility_note` | string? | 与历史基线可比性的说明 |

## Relationships

- 一个 `EvalBatch` 包含多条 `TrialRun`
- 一条 `TrialRun` 对应一个 `EvalCase`
- 一条 `TrialRun` 会产生一个 `EvidenceBundle`
- 一条 `TrialRun` 会产生一个 `ScoreCard`
- 一个 `BaselineSnapshot` 来自一个 `EvalBatch`
- 一个 `RegressionDiff` 对比一个 `EvalBatch` 与一个 `BaselineSnapshot`
- 一个 `EvalSettingsProfile` 可被多个 `EvalBatch` 复用

## State Flow

```text
Case Defined
  -> Batch Selected
  -> Trial Started
  -> Evidence Collected
  -> Scored
  -> Baseline Compared

Possible terminal classes:
  -> Pass
  -> Correct Stop
  -> Environment Failure
  -> Skill Failure
  -> Harness Failure
  -> Evidence Missing
```
