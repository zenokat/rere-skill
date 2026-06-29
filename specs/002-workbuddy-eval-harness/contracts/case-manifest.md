# Contract: Suite And Case Folder

## suite.yaml

评测集文件告诉 harness：本批评测叫什么、跑哪些 case、使用哪些 grader。

```yaml
suite_id: revenue-recognition-real-smoke
graders:
  - preview_file_exists
cases:
  - revenue-recognition-dine-in-202605
```

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `suite_id` | string | 是 | 评测集 ID。 |
| `graders` | list[string] | 是 | 本批评测要运行的 grader ID。 |
| `cases` | list[string] | 是 | case 文件夹名列表。 |

规则：

- `cases[]` 必须是稳定目录名，不能包含路径分隔符或路径穿越。
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
| `skills/` | 是 | 本 case 提供给 Agent 的 skill 包。 |
| `input/` | 是 | 本 case 允许 Agent 读取的输入文件。 |

规则：

- `instruction.md` 不写标准答案。
- 如果 `instruction.md` 中出现 `/<skill-name>`，harness 视为用户通过斜杠指令手动调用该 skill，并注入 `manually_attached_skills`。
- `input/` 中只放本 case 可见数据。
- `skills/` 中的 skill 应是可搬走的产品包，不依赖原始开发仓库绝对路径。
- skill 附带脚本应放在 `skills/<skill-name>/scripts/`，并由 `SKILL.md` 或 `references/` 说明运行前提。
- 运行时 harness 会把 `skills/<skill-name>/` 放到 sandbox 的 `.workbuddy/skills/<skill-name>/`。
- harness 不会额外生成 `.bin/`、`.runtime/` 或 `EVAL_CASE_CONTEXT.md` 来补运行能力。