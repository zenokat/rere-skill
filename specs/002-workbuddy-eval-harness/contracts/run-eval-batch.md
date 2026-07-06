# Contract: run_skill_eval_batch

## Command

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite <suite.yaml> `
  --output_root <output-dir> `
  [--model <model-id>]
```

## Arguments

| 参数 | 含义 |
|---|---|
| `--suite` | 评测集 YAML 路径。 |
| `--output_root` | 评测结果输出根目录。 |
| `--model` | 可选临时覆盖值。传入后覆盖 `suite.yaml` 的 `model.id`；不传时使用 suite 配置或 CodeBuddy 默认模型。 |

首版不提供 runner/profile/baseline/OTel/raw session 参数。

正式评测的模型应写在 suite YAML：

```yaml
model:
  id: glm-5
  config_file: ${EVAL_MODELS_JSON}
```

`config_file` 指向 CodeBuddy `models.json`。声明后，harness 会先校验该文件定义了 `model.id`，再把它复制到每条 case 的隔离 `CODEBUDDY_CONFIG_DIR/models.json`。复制后的配置文件不会进入公开结果包。

## Per Case Flow

每条 case 按以下顺序执行：

1. 读取 `cases/<case_id>/instruction.md`、`skills/` 和 `input/`；当 case 级 `skills/` 或 `input/` 为空时，回退到 suite 级共享路径（如有声明）。
2. 在公开结果包之外创建一次性 sandbox workspace。
3. 复制 `input/`（或 suite 级共享 input）到 sandbox。
4. 创建 sandbox `output/`。
5. 将 `skills/<skill-name>/`（或 suite 级共享 skills 中的子目录）materialize 为 `.workbuddy/skills/<skill-name>/`。
6. 生成 WorkBuddy 风格 `system-reminder` 启动上下文，把 `instruction.md` 原文放入 `<user_query>`。
7. 如果 `<user_query>` 中包含 `/<skill-name>`，注入对应 `manually_attached_skills`。
8. 解析 suite 级 `model`；如果声明了 `model.config_file`，校验其中包含本次请求的模型 ID，并复制到隔离 CodeBuddy 配置目录。
9. 以 sandbox workspace 为 cwd 运行 CodeBuddy CLI，并启用 Docker/OCI 容器隔离；如果 suite 或 CLI 指定了模型，同步传给 CodeBuddy。
10. 从 stdout 或 session JSONL 回收最终响应。
11. 把 CodeBuddy 原始 session JSONL 原样复制为 `session.jsonl`。
12. 复制 sandbox `output/` 到结果目录 `outputs/`。
13. 运行 suite YAML 声明的 graders。
14. 写入 `result.json`。
15. 销毁 sandbox。

如果 sandbox、Docker 或 CodeBuddy 容器运行能力不可用，case 失败并写入 `result.json`；不得退回宿主机裸跑。

## Sandbox Shape

运行时 CodeBuddy 面对的 workspace 固定为：

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

不包含：

- `instruction.md`
- `EVAL_CASE_CONTEXT.md`
- `.bin/`
- `.runtime/`
- 原始代码仓库
- 用户主目录

## Output

命令 stdout 只返回批次摘要：

```json
{
  "batch_id": "20260627-130214-revenue-recognition-real-smoke",
  "status": "passed",
  "case_counts": {
    "total": 1,
    "completed": 1,
    "passed": 1,
    "failed": 0
  },
  "batch_json": ".tmp/evals/revenue-real-smoke/20260627-130214-revenue-recognition-real-smoke/batch.json"
}
```

结果目录：

```text
<output_root>/<batch_id>/
├── batch.json
└── cases/
    └── <case_id>/
        ├── result.json
        ├── session.jsonl
        └── outputs/
```

## Session Capture

harness 把 CodeBuddy / WorkBuddy 写出的原始 session JSONL 原样复制为结果目录的 `session.jsonl`，作为 Agent 轨迹的唯一事实源。不做事件归一化、不重命名类型、不屏蔽路径、不丢弃字段（包括 `reasoning`、`providerData`、`sessionId` 等）。事件类型与字段以 CodeBuddy 原始为准。

Windows 上 CodeBuddy state 路径可能超过 260 字符。runner 查找和复制 session 时必须支持 Windows 扩展长路径，能读取 `codebuddy-state/<case>/projects/<cwd-id>/*.jsonl` 这类深层路径；写入结果包时仍使用普通相对路径 `session.jsonl`，不把扩展长路径前缀暴露给评测者。

`session.jsonl` 是原始敏感证据，可能包含工具输出中的环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`。结果包默认只用于本地复盘和受控归档；如采集到真实凭据，应先轮换凭据。

如果某条 case 未捕获到 session（环境失败或 CodeBuddy 未写出 session 文件），`session.jsonl` 不生成，`result.json` 的 `evidence.missing` 记为 `codebuddy_session_jsonl`。
