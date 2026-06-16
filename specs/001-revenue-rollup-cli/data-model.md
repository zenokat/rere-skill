# Data Model: 收入确认 Skill 第 3 步汇总工具

## Overview

这个功能的核心是一个由确认项目目录驱动的汇总引擎。它只覆盖收入确认 Skill 十步
SOP 中的第 3 步“汇总”。确认项目目录负责注册可处理的业务项目，预处理后源文件
集合负责提供干净输入，sheet 结构定义负责描述如何读取源 Excel，规则集合负责
定义如何汇总生成字段，结果文件则作为试算与上传之间的边界产物，并作为下游收
入回款确认继续计算的原材料。

## Entities

### RecognitionProject

表示一个已注册的阶段一汇总项目。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | `run_recog_rollup` 使用的稳定业务主键 |
| `recog_name` | string | 供 Agent 理解的可读项目名称 |
| `bitable_table_id` | string | 阶段一上传目标的 Bitable 数据表 |
| `bitable_table_exists` | boolean | 当前目标表是否可访问 |

### PreprocessedSourceInput

表示一个已经完成文件预处理、可被 `source_file` 接受的输入集合。

| Field | Type | Description |
|---|---|---|
| `path` | path | 传给 `run_recog_rollup` 的单文件路径或目录路径 |
| `kind` | enum | `file` 或 `directory` |
| `preprocessed` | boolean | 是否已完成解压、识别和按确认项目分拣 |
| `contains_only_target_files` | boolean | 是否只包含当前确认项目所需的那类业务文件 |

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

补充约束：
- 同一 `recog_id` 下，每个 `SUM` 类型的 `bitable_field` 只能在规则表中出现一次。
- 如果源目录同时存在多种 schema，应将它们分别映射为不同的基础事实字段，再由下游收入回款确认步骤做字段间运算。

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

补充说明：

- `PreviewArtifact` 代表门店级基础事实字段集合，可供下游收入回款确认继续做字段间运算，
  但不等同于最终确认收入或最终回款结果。

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

表示一个用于校准的 202605 历史记录。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 所属项目 |
| `period` | string | 基线期间 |
| `fields` | map | 归一化后的阶段一字段值 |

### IterationProjectSummary

用于概括某个项目在 Ralph 循环中的当前状态，对应 `iteration-progress.md` 中的总表。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 项目主键 |
| `recog_name` | string | 项目名称 |
| `status` | string | 当前推进状态，仅使用 `working`、`matched`、`业务TBD`、`blocked` |
| `last_round` | integer | 当前项目最近一轮编号 |
| `next_action` | string | 下一步动作，或为什么应停止 |
| `latest_delta` | string | 最近一轮新增改动摘要 |

### IterationRecord

用于记录某个项目的单轮迭代证据，对应 `iteration-progress.md` 中的项目小表。

| Field | Type | Description |
|---|---|---|
| `recog_id` | string | 所属项目 |
| `round` | integer | 当前项目内的轮次编号 |
| `date` | date | 本轮记录日期 |
| `result` | string | 本轮最关键的结果，用于判断是否继续当前项目、是否需要业务确认、是否可进入回归 |
| `delta` | string | 本轮新增规则、代码补丁、文档调整或环境处理摘要 |
| `notes` | string | 补充条数、耗时、阻断原因、下一步动作等关键信息 |

## Relationships

- 一个 `RecognitionProject` 会关联多条 `SourceSheetSpec`
- 一个 `RecognitionProject` 会关联多条 `RollupRule`
- 一次 preview 运行会产生一个 `PreviewArtifact` 和零到多条 `PreviewIssue`
- 一次 upload 运行会通过 `UploadRequest` 消费一个 `PreviewArtifact`
- 一条 `IterationProjectSummary` 用来概括一个 `RecognitionProject` 当前的校准状态
- 一个 `RecognitionProject` 会关联多条 `IterationRecord`

## State Flow

```text
Listed
  -> Validated
  -> Previewed
  -> Baseline Matched
  -> Regression Eligible

Any stage can move to:
  -> Code Iteration
  -> Business TBD
  -> Blocked (requires external dependency or manual decision)
```
