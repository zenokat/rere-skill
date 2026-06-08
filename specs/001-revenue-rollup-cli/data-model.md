# Data Model: 收入确认阶段一汇总工具

## Overview

这个功能的核心是一个由项目目录驱动的汇总引擎。项目目录负责标识当前处理的
业务项目，sheet 结构定义负责描述如何读取源 Excel，规则集合负责定义如何汇
总生成字段，结果文件则作为试算与上传之间的边界产物。

## Entities

### RecognitionProject

表示一个已注册的阶段一汇总项目。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | `run_recog_rollup` 使用的稳定业务主键 |
| `recog_name` | string | 供 Agent 理解的可读项目名称 |
| `bitable_table_id` | string | 阶段一上传目标的 Bitable 数据表 |
| `bitable_table_exists` | boolean | 当前目标表是否可访问 |

### SourceSheetSpec

描述某个项目中一个源 sheet 应如何读取。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 所属项目 |
| `sheet` | string | 源工作簿中应存在的 sheet 名称；对 `csv` 或只有单个 sheet 的 `xlsx` 使用 `DEFAULT` |
| `category_row` | integer | 用于分类定位的行号 |
| `field_row` | integer | 用于字段定位的行号 |
| `last_row` | integer | 数据结束行，或相对末尾的偏移 |
| `optional` | boolean | 是否允许该 sheet 缺失 |

### RollupRule

定义一个输出字段应如何从源数据计算得到。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 所属项目 |
| `bitable_field` | string | 结果矩阵中的输出字段名 |
| `type` | enum | `GROUP` 或 `SUM` |
| `sheet` | string | 使用的源 sheet；对 `csv` 或只有单个 sheet 的 `xlsx` 使用 `DEFAULT` |
| `category` | string | 源字段的分类定位信息 |
| `field` | string | 源字段名 |
| `condition` | string? | 可选条件表达式 |
| `optional` | boolean | 是否允许源字段缺失 |

### ValidationCheckResult

表示一次结构或上传可行性检查结果。

| Field | Type | Description |
|---|---|---|
| `check_name` | string | 检查项标识，例如 `sheet_exists` |
| `scope` | string | 所属的 sheet、字段、规则或表范围 |
| `passed` | boolean | 检查是否通过 |
| `message` | string | 面向 Agent 的摘要信息 |
| `details` | object/list | 结构化细节，供 Agent 继续处理 |

补充说明：

- 当 `source_file` 传入目录时，`ValidationCheckResult.details` 中应包含本次被随机抽检
  的代表文件路径。

### PreviewArtifact

表示 `run_recog_rollup --preview` 的成功结果。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 项目主键 |
| `period` | string | `YYYYMM` 会计期间 |
| `result_file` | path | 生成的 Excel 结果文件 |
| `row_count` | integer | 输出记录数 |
| `field_count` | integer | 输出字段数 |
| `generated_at` | datetime | 用于命名文件的生成时间 |

### PreviewIssue

表示一次试算阶段的计算异常。

| Field | Type | Description |
|---|---|---|
| `source_file` | path | 出问题的工作簿 |
| `sheet` | string | 出问题的 sheet |
| `row` | integer? | 出问题的数据行 |
| `field` | string? | 出问题的字段 |
| `rule_ref` | string? | 关联规则标识 |
| `message` | string | 异常说明 |

### UploadRequest

表示一次上传调用请求。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 项目主键 |
| `result_file` | path | 待上传的 preview 结果文件 |
| `strategy` | enum | `default`、`append` 或 `upsert` |

### UploadOutcome

表示一次上传动作的结果。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 项目主键 |
| `result_file` | path | 已上传文件 |
| `strategy` | enum | 本次使用的上传策略 |
| `target_table_id` | string | 上传到的飞书数据表id |
| `row_count` | integer | 上传记录数 |
| `field_count` | integer | 上传字段数 |
| `status` | enum | `ok`、`conflict` 或 `error` |
| `message` | string | 上传结果摘要 |

### HistoricalBaselineRecord

表示一个用于校准的 202603 历史记录。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 所属项目 |
| `period` | string | 基线期间 |
| `fields` | map | 归一化后的阶段一字段值 |

### CoverageMatrixRow

用于追踪每个项目在 Ralph 循环中的推进状态。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 项目主键 |
| `recog_name` | string | 项目名称 |
| `source_ready` | boolean | 源文件是否已就绪 |
| `history_ready` | boolean | 历史记录是否已具备 |
| `validate_passed` | boolean | 当前结构检验是否通过 |
| `preview_matched` | boolean | 当前 preview 是否与基线一致 |
| `diff_type` | string | 差异分类 |
| `rule_delta` | string | 本轮新增规则或代码调整摘要 |
| `regression_status` | string | 当前回归状态 |

## Relationships

- 一个 `RecognitionProject` 会关联多条 `SourceSheetSpec`
- 一个 `RecognitionProject` 会关联多条 `RollupRule`
- 一次 preview 运行会产生一个 `PreviewArtifact` 和零到多条 `PreviewIssue`
- 一次 upload 运行会通过 `UploadRequest` 消费一个 `PreviewArtifact`
- 一条 `CoverageMatrixRow` 用来概括一个 `RecognitionProject` 当前的校准状态

## State Flow

```text
Listed
  -> Validated
  -> Previewed
  -> Baseline Matched
  -> Upload Eligible
  -> Uploaded

Any stage can move to:
  -> Blocked (requires rule, config, or code iteration)
```
