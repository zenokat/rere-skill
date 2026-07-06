# Quickstart: 运行一条真实 case

## 目标

用 CodeBuddy CLI 在一次性 sandbox workspace 中跑通一条真实 case，并拿到：

- `batch.json`
- `cases/<case_id>/result.json`
- `cases/<case_id>/session.jsonl`
- `cases/<case_id>/outputs/`

## 1. 准备 CodeBuddy CLI

```powershell
npm install -g @tencent-ai/codebuddy-code
codebuddy --version
codebuddy
codebuddy -p "hello" --output-format json
codebuddy -p "hello" --model <model-id> --output-format json
```

如果最小无头调用不能返回模型结果，先处理 CodeBuddy 安装、PATH、登录或权限问题。

## 2. 准备 Docker 隔离能力

每条 case 必须在一次性 sandbox workspace 中运行，并由 CodeBuddy CLI 启用 `--sandbox container --sandbox-new --sandbox-kill`。Docker/OCI 容器是默认安全边界：容器只能看到当前 case workspace，不能挂载原始代码仓库或用户主目录。

```powershell
docker --version
codebuddy -p "hello" --sandbox container --sandbox-new --sandbox-kill --permission-mode bypassPermissions --output-format json
```

如果 Docker、CodeBuddy 登录态、容器网络或容器内必要运行时不可用，case 应记为环境失败，不得退回宿主机裸跑。

## 3. 准备评测集

示例结构：

```text
specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/
├── suite.yaml
└── cases/
    └── revenue-recognition-dine-in-202605/
        ├── instruction.md
        ├── skills/
        │   └── revenue-recognition/
        │       ├── SKILL.md
        │       ├── references/
        │       └── scripts/
        └── input/
            └── 收银汇总表 202605.xlsx
```

`suite.yaml`：

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

> `model` 是可选字段。只指定 `model.id` 时使用 CodeBuddy 当前可用模型；同时指定 `model.config_file` 时，harness 会把该 `models.json` 复制到每条 case 的隔离 CodeBuddy 配置目录，并要求文件内必须定义该模型。`input` 和 `skills` 是可选字段，用于声明 suite 级共享路径。当 case 级目录为空时，harness 自动回退。详见 [README](./README.md#suiteyaml)。

如果使用 `${EVAL_MODELS_JSON}`，先在当前 PowerShell 会话设置：

```powershell
$env:EVAL_MODELS_JSON = "$env:USERPROFILE\.workbuddy\models.json"
```

`instruction.md` 写真实任务，例如：

```markdown
/revenue-recognition @input contains the source files for period 202605. Please process the dine-in revenue rollup.

Requirements:
- Run validate and preview only.
- Do not run upload.
- Treat input/ as the only source-data directory.
- Write the preview artifact under output/.
```

`/revenue-recognition` 表示用户在真实 WorkBuddy 交互里通过斜杠指令手动调用了该 skill。harness 会据此注入 `manually_attached_skills`。

## 4. 发起评测

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml `
  --output_root .tmp/evals/revenue-real-smoke
```

正式评测建议把模型写在 suite.yaml。`--model <model-id>` 只作为临时覆盖入口；如果 suite 同时声明了 `model.config_file`，覆盖后的模型 ID 也必须存在于该配置文件中。

## 5. 查看结果

先看批次：

```powershell
Get-Content .tmp/evals/revenue-real-smoke/<batch_id>/batch.json
```

再看单条 case：

```powershell
Get-Content .tmp/evals/revenue-real-smoke/<batch_id>/cases/revenue-recognition-dine-in-202605/result.json
Get-Content .tmp/evals/revenue-real-smoke/<batch_id>/cases/revenue-recognition-dine-in-202605/session.jsonl
Get-ChildItem .tmp/evals/revenue-real-smoke/<batch_id>/cases/revenue-recognition-dine-in-202605/outputs
```

## 验收点

- `batch.json.case_counts.total` 等于评测集 case 数。
- `batch.json.case_counts.completed` 等于已完成运行、取证和评分的 case 数。
- `batch.json.model.requested` 能看到本批请求的模型；没有指定时为 `null`。
- 如果使用 suite `model.config_file`，`batch.json.model.config.fingerprint` 能看到本次复制的配置文件指纹，但不会看到 API key。
- `result.json.score` 是 `1` 或 `0`。
- `result.json.model.observed` 能看到 session 或 stdout 里实际采到的模型；采不到时为 `null`。
- `result.json.graders[]` 能看到 0/1 评分原因。
- `session.jsonl` 能看到 Agent 可见行为轨迹。
- `session.jsonl` 是原始敏感证据，可能包含环境变量、凭据片段、绝对路径和 provider 细节；只在本地复盘或受控归档中使用。
- `outputs/` 中能看到本 case 产物。
- 运行结束后 sandbox 被销毁。
- sandbox 不包含 `instruction.md`、`EVAL_CASE_CONTEXT.md`、`.bin/` 或 `.runtime/`。
