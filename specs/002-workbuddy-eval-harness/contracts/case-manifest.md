# Contract: Suite And Case Folder

## suite.yaml

评测集文件告诉 harness：本批评测叫什么、跑哪些 case、使用哪些 grader。

```yaml
suite_id: revenue-recognition-real-smoke
model:
  id: glm-5
  config_file: ${EVAL_MODELS_JSON}
graders:
  - preview_file_exists
  - preview_matches_baseline
cases:
  - revenue-recognition-dine-in-202605
```

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `suite_id` | string | 是 | 评测集 ID。 |
| `model` | object | 否 | suite 级模型选择。用于固定本评测集使用的 CodeBuddy 模型。 |
| `model.id` | string | `model` 存在时必填 | CodeBuddy 模型 ID，会传给 `codebuddy --model`。 |
| `model.config_file` | string | 否 | CodeBuddy `models.json` 路径。支持绝对路径、相对 suite.yaml 的相对路径，以及 `${ENV_VAR}`。声明后 harness 会复制到每条 case 的隔离 CodeBuddy 配置目录。 |
| `graders` | list[string] | 是 | 本批评测要运行的 grader ID。 |
| `cases` | list[string] | 是 | case 文件夹名列表。 |
| `input` | string | 否 | suite 级共享输入目录。支持绝对路径或相对于 suite.yaml 的相对路径。case 级 `input/` 为空时自动回退。 |
| `skills` | string | 否 | suite 级共享 skill 目录。支持绝对路径或相对于 suite.yaml 的相对路径。case 级 `skills/` 为空时自动回退。 |

规则：

- `cases[]` 必须是稳定目录名，不能包含路径分隔符或路径穿越。
- `model` 是 suite 级配置；首版一个 suite 只指定一个模型。要比较多个模型，应创建多个 suite 分别运行。
- 如果声明了 `model.config_file`，其中必须定义 `model.id`，否则 manifest 加载失败，避免静默回退到 CodeBuddy 内置模型。
- `model.config_file` 只能引用本机私有配置文件，不应把 API key 写进仓库内的 suite.yaml。
- suite YAML 不再声明 `skill.path`、`skill.name` 或 `prompt`。
- 评分规则由 `graders` 控制，不存在隐藏默认 grader。

## Case Folder

每条 case 必须位于 `cases/<case_id>/`：

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
| `instruction.md` | 是 | Agent 要完成的任务、边界和必要提示。运行时作为 `<user_query>`，不作为文件复制进 workspace。 |
| `skills/` | 目录必须存在 | 本 case 提供给 Agent 的 skill 包。为空且 suite 级有 `skills` 声明时，自动回退到 suite 级共享路径。 |
| `input/` | 目录必须存在 | 本 case 允许 Agent 读取的输入文件。为空且 suite 级有 `input` 声明时，自动回退到 suite 级共享路径。 |

规则：

- `instruction.md` 不写标准答案。
- 如果 `instruction.md` 中出现 `/<skill-name>`，harness 视为用户通过斜杠指令手动调用该 skill，并注入 `manually_attached_skills`。
- `input/` 中只放本 case 可见数据。
- `skills/` 中的 skill 应是可搬走的产品包，不依赖原始开发仓库绝对路径。
- skill 附带脚本应放在 `skills/<skill-name>/scripts/`，并由 `SKILL.md` 或 `references/` 说明运行前提。
- 运行时 harness 会把 `skills/<skill-name>/` 放到 sandbox 的 `.workbuddy/skills/<skill-name>/`。
- harness 不会额外生成 `.bin/`、`.runtime/` 或 `EVAL_CASE_CONTEXT.md` 来补运行能力。
