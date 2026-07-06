# Data Model: WorkBuddy / CodeBuddy Eval Harness

## EvalSuiteManifest

评测集入口，来自 `suite.yaml`。

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `suite_id` | string | 是 | 评测集 ID。 |
| `model` | object | 否 | suite 级模型选择。首版一个 suite 只指定一个模型。 |
| `model.id` | string | `model` 存在时必填 | CodeBuddy 模型 ID。 |
| `model.config_file` | string | 否 | CodeBuddy `models.json` 路径。声明后必须包含 `model.id`，并会被复制到每条 case 的隔离 CodeBuddy 配置目录。 |
| `graders` | list[string] | 是 | 本批评测要运行的 grader ID。 |
| `cases` | list[string] | 是 | case 文件夹名列表。 |
| `input` | string | 否 | suite 级共享输入目录。支持绝对路径或相对于 suite.yaml 的相对路径。case 级 `input/` 为空时自动回退。 |
| `skills` | string | 否 | suite 级共享 skill 目录。支持绝对路径或相对于 suite.yaml 的相对路径。case 级 `skills/` 为空时自动回退。 |

示例（最小）：

```yaml
suite_id: revenue-recognition-real-smoke
graders:
  - preview_file_exists
cases:
  - revenue-recognition-dine-in-202605
```

示例（指定自定义模型配置）：

```yaml
suite_id: revenue-recognition-real-smoke
model:
  id: glm-5
  config_file: ${EVAL_MODELS_JSON}
graders:
  - preview_file_exists
cases:
  - revenue-recognition-dine-in-202605
```

示例（带 suite 级共享资源）：

```yaml
suite_id: Rollup_Core_20260630
graders:
  - preview_file_exists
  - preview_matches_baseline
input: d:/AI/rere-agent/202605-source-excel
skills: d:/AI/rere-agent/skill/revenue-recognition
cases:
  - dine_in_revenue_202605
```

## EvalCaseFolder

单条 case 的源材料目录。

```text
cases/<case_id>/
├── instruction.md
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
└── input/
```

| 路径 | 必填 | 含义 |
|---|---|---|
| `instruction.md` | 是 | 本 case 的用户任务、边界和必要提示。运行时作为 `<user_query>`，不复制进 workspace。 |
| `skills/` | 目录必须存在 | 本 case 提供给 Agent 的 skill 包。为空且 suite 级有 `skills` 声明时，自动回退到 suite 级共享路径。 |
| `input/` | 目录必须存在 | 本 case 允许 Agent 读取的输入文件。为空且 suite 级有 `input` 声明时，自动回退到 suite 级共享路径。 |

`case_id` 来自文件夹名，必须稳定，不能包含路径分隔符或路径穿越。

## CaseSandbox

运行时为单条 case 创建的一次性 sandbox workspace。它不是结果文件，运行结束后销毁。

```text
<sandbox>/
├── input/
├── output/
└── .workbuddy/
    └── skills/
        └── <skill-name>/
            ├── SKILL.md
            ├── references/
            └── scripts/
```

| 路径 | 含义 |
|---|---|
| `input/` | 从 case 源目录复制，Agent 可读。 |
| `output/` | Agent 唯一业务产物输出目录。 |
| `.workbuddy/skills/<skill-name>/` | 按 WorkBuddy 风格 materialize 后的 skill。 |

明确不在 sandbox 中生成：

- `instruction.md`
- `EVAL_CASE_CONTEXT.md`
- `.bin/`
- `.runtime/`

约束：

- 不挂载原始代码仓库。
- 不挂载用户主目录。
- 不把宿主机 `.codebuddy` 或 `.workbuddy` 整体暴露给 Agent。
- CodeBuddy 运行状态写入独立内部 `codebuddy-state/` 目录，不进入 case workspace。
- 运行结束后复制 `output/` 到结果目录，再销毁 sandbox。

## WorkBuddyStartupContext

发给 CodeBuddy 的首条用户消息，由 WorkBuddy 风格 `system-reminder` 和 `<user_query>` 组成。

| 部分 | 含义 |
|---|---|
| `user_info` | OS、shell、主题和 workspace 边界提示。 |
| `identity_context` | 默认 WorkBuddy 身份模板。 |
| `product_identity` | WorkBuddy 产品身份声明。 |
| `project_context` | 当前 sandbox workspace 文件结构。 |
| `additional_data` | 固定评测时间和 connector status。 |
| `connector-status` | 全部 connector 默认为 `disconnected`。 |
| `memory_and_skills_reminder` | 可见 WorkBuddy 提醒，但仍受 sandbox 边界限制。 |
| `manually_attached_skills` | 仅当 `instruction.md` 中出现 `/<skill-name>` 时注入。 |
| `user_query` | `instruction.md` 原文。 |

## TargetConfig

CodeBuddy 运行目标。

| 字段 | 类型 | 含义 |
|---|---|---|
| `skill_names` | list[string] | sandbox 内可见 skill 名称。 |
| `skill_entries` | list[string] | sandbox 相对 `SKILL.md` 降级路径。 |
| `codebuddy_executable` | string | CLI 可执行文件名，默认 `codebuddy`。 |
| `model` | string/null | 可选 CodeBuddy 模型 ID；为空时使用 CodeBuddy 默认模型。 |
| `use_container_sandbox` | boolean | 是否启用 Docker/OCI 容器隔离；默认启用。 |
| `env` | object | CodeBuddy 进程的最小环境变量覆盖，不得包含仓库 tool-root 或隐藏运行时。 |

当 suite 声明了 `model.config_file`，runner 会在每条 case 启动前把该文件复制到隔离的 `CODEBUDDY_CONFIG_DIR/models.json`，并设置 `CODEBUDDY_DISABLE_BUILTIN_MODELS=1`，降低误走内置模型的风险。公开结果只记录配置指纹，不记录路径、文件内容或 API key。

## BatchResult

整批评测结果，写入 `<output_root>/<batch_id>/batch.json`。

| 字段 | 类型 | 含义 |
|---|---|---|
| `batch_id` | string | 本次运行 ID。 |
| `suite_id` | string | 评测集 ID。 |
| `model` | object | 本批请求的模型信息，`requested` 为空表示使用 CodeBuddy 默认模型；使用 `model.config_file` 时包含 `config.source` 和 `config.fingerprint`。 |
| `status` | enum | `passed` 或 `failed`。 |
| `case_counts` | object | 总数、完成数、通过数、失败数。 |
| `metrics` | object | 批次耗时、token、成本。 |

`batch.json` 不包含 case 数组。

## CaseResult

单条 case 结果，写入 `cases/<case_id>/result.json`。

| 字段 | 类型 | 含义 |
|---|---|---|
| `case_id` | string | case ID。 |
| `status` | enum | `completed`、`failed` 或 `blocked`。 |
| `verdict` | enum | `pass` 或 `fail`。 |
| `score` | integer | `1` 或 `0`。 |
| `final_response` | string | Agent 最终回答。 |
| `model` | object | `requested` 为本次请求的模型，`observed` 为 session/stdout 实际采到的模型；使用 `model.config_file` 时包含不泄密的配置证据。 |
| `metrics` | object | 单 case 耗时、token、成本。 |
| `graders` | list[`GraderResult`] | 评分器结果列表。 |
| `evidence` | object | session、outputs 和缺失证据。 |

`evidence` 固定包含：

| 字段 | 类型 | 含义 |
|---|---|---|
| `session_path` | string | `session.jsonl`。 |
| `outputs_path` | string | `outputs/`。 |
| `missing` | list[string] | 缺失证据列表。 |

## SessionRecord

`session.jsonl` 是 CodeBuddy / WorkBuddy 原始 session 的逐行原文，作为 Agent 轨迹的唯一事实源。harness 直接复制 CodeBuddy 写出的 session 文件，不做归一化、不屏蔽路径、不丢弃字段。

事件类型与字段以 CodeBuddy 原始为准，常见包括 `message`（user/assistant，含完整 `content`）、`function_call`（含完整 `arguments`）、`function_call_result`（含完整 `output`/stdout/stderr/exit code）、`reasoning`，以及 `providerData`（模型、token 用量）、`sessionId`、时间戳等原始元数据。没有 harness 自定义的事件类型映射。

`SessionRecord` 没有额外清洗层，因此可能包含环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`。评测结果包应按敏感证据管理，不应公开分享；如果真实凭据被采入 session，应先轮换凭据。

在 Windows 上，CodeBuddy 原始 session 文件可能位于超过 260 字符的 `codebuddy-state/<case>/projects/<cwd-id>/*.jsonl` 路径下。采集实现必须能读取这类长路径，但 `CaseResult.evidence.session_path` 仍保持为结果包内的普通相对路径 `session.jsonl`。

## CaseOutputs

单条 case 业务产物目录，写入 `cases/<case_id>/outputs/`。

规则：

- 来源是 sandbox 内的 `output/`。
- 目录必须存在，可以为空。
- grader 引用产物时使用 `outputs/...` 相对路径。
- harness 不为 outputs 额外生成索引文件。

## GraderResult

单个评分器结果，写入 `result.json.graders[]`。

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | string | grader ID。 |
| `type` | enum | `code` 或 `model`。 |
| `score` | integer | `1` 或 `0`。 |
| `summary` | string | 为什么给这个分数。 |
| `evidence` | object | 评分证据摘要。 |

约束：

- 所有 grader 都是二元判断。
- `verdict` 固定按“全 1 为 pass，有 0 为 fail”生成。
- grader 可以读取 `result.json`、`session.jsonl`、`outputs/` 或受控远端结果。
- grader 不新增额外结果文件。
