# Contract: 基线快照与比较

## Purpose

baseline 不是“把某次结果存下来”这么简单，而是把后续可以重复比较所需的上下文一起冻结。

## Baseline Snapshot Schema

建议文件名：

```text
baselines/<baseline_id>/baseline.json
```

至少包含：

| Field | Type | Description |
|---|---|---|
| `baseline_id` | string | 基线标识 |
| `suite_id` | string | 所属 case 集 |
| `created_from_batch_id` | string | 来源批次 |
| `created_at` | datetime | 创建时间 |
| `skill_version` | string? | skill 版本 |
| `prompt_version` | string? | prompt / 打包版本 |
| `environment_fingerprint` | object | 运行环境指纹 |
| `scorer_versions` | object | scorer 版本 |
| `settings_profile_id` | string | 运行所用评测设置 |
| `case_results` | list[object] | 逐 case 结果 |
| `approval_status` | string | `draft`、`reviewed`、`promoted` |

## Case-Level Baseline Record

每条 case 至少保存：

| Field | Type | Description |
|---|---|---|
| `case_id` | string | case 标识 |
| `case_version` | string | case 版本 |
| `expected_outcome_class` | string | 预期结果分类 |
| `scorecard` | object | 冻结后的主评分结果 |
| `failure_source` | string? | 若失败或正确止步，保留归因 |
| `evidence_refs` | object | 关键证据引用 |
| `workspace_policy` | object | 当时的环境隔离与写策略摘要 |

## Promotion Rule

首版建议：

- 新批次运行结束后先形成 `draft` baseline
- 只有在人工复核通过后，才把状态提升为 `promoted`

原因：

- baseline 会决定后续回归方向，不能完全自动晋升
- 特别是 Rubric 评分和正确止步 case，首版需要人工校准

## Baseline Compare Contract

建议提供独立命令：

```powershell
.\.codex\scripts\rere.cmd compare_skill_eval_baseline --run_dir <run_dir> --baseline <baseline_path>
```

比较结果至少区分：

| Status | Meaning |
|---|---|
| `unchanged` | 无实质变化 |
| `fixed` | 旧失败/低分，本轮修复 |
| `regressed` | 新增失败或评分下降 |
| `new_issue` | 基线中不存在的问题 |
| `not_comparable` | 版本或证据缺口导致不可比 |

## Regression Gating Rule

首版建议：

- `regressed` 视为 CI / 评审阻断信号
- `not_comparable` 不应被静默忽略，必须在摘要里单独列出原因
- `fixed` 和 `unchanged` 都应统计并进入聚合摘要
- 当评分器版本、设置 profile 或环境隔离策略发生变化时，应优先评估是否需要标记为 `not_comparable`
