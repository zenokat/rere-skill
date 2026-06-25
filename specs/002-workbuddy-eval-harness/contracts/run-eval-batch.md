# Contract: 批量运行入口

## Purpose

该契约定义 harness 的主入口如何被人和 Agent 调用，用于一次性发起一批 case、收集证据、
执行评分并输出可比较结果。

## Proposed Command

在仓库本地开发环境中，首版建议统一通过仓库启动器暴露：

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch
```

说明：

- 这是仓库级开发入口，不代表未来 skill 产品包的唯一入口。
- 选择 `rere.cmd` 是为了复用本仓库对 Python 环境初始化的统一约束。

## Required Arguments

| Argument | Type | Description |
|---|---|---|
| `--suite` | path | case manifest 路径 |
| `--output_root` | path | 本轮运行输出目录 |

## Optional Arguments

| Argument | Type | Description |
|---|---|---|
| `--case` | string, repeatable | 仅运行指定 case |
| `--baseline` | path | 指定对比基线 |
| `--settings_profile` | string | 覆盖 manifest 中默认设置 |
| `--runner` | string | 默认 `codebuddy_headless` |
| `--result_format` | string | `text` 或 `json`，默认 `json` |
| `--capture_transcript` | flag | 是否保存 `stream-json` transcript |
| `--enable_otel` | flag | 是否开启 OTel trace 导出 |
| `--promote_baseline` | string | 运行成功后直接生成基线名称 |
| `--workspace_root` | path | case 独立工作目录根路径 |
| `--cleanup_workspaces` | flag | 运行结束后清理临时工作目录 |
| `--write_policy` | string | `read_only`、`safe_only`、`approved_write` |

## Runner Behavior

执行器必须保证：

1. 每条 case 生成独立 `run_id` 和输出目录。
2. 无头执行默认通过 CodeBuddy CLI `-p` 发起。
3. 若任务涉及授权动作，runner 必须只在受信场景下为底层 CLI 注入 `-y`。
4. 即使单个 case 失败，整批运行也要尽量完成其余 case，并在批次摘要中给出完整状态。
5. 每条 case 还必须生成独立 `workspace_dir`，不得复用其他 case 的运行目录。
6. 当 `write_policy=read_only` 时，runner 必须阻断 upload 或真实外部写动作。
7. 当 case 声明需要安全写环境时，runner 必须先校验环境，再决定是否放行。

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | 批次完成，且没有 unexpected regression |
| `1` | 用法错误或 harness 内部错误 |
| `2` | 批次完成，但存在 unexpected failure / regression |
| `3` | 运行环境阻断到无法形成可靠评测结果 |
| `4` | 安全策略阻断了被禁止的写操作 |

## Stdout Contract

当 `--result_format json` 时，stdout 至少返回以下结构：

```json
{
  "batch_id": "20260625-101530-rollup-smoke",
  "suite_id": "rollup-smoke",
  "overall_status": "regressed",
  "case_counts": {
    "total": 3,
    "passed": 1,
    "correct_stop": 1,
    "environment_failure": 1,
    "regressed": 0
  },
  "artifacts": {
    "batch_json": ".tmp/evals/20260625-101530-rollup-smoke/batch.json",
    "summary_md": ".tmp/evals/20260625-101530-rollup-smoke/summary.md"
  }
}
```

## Batch Directory Layout

```text
<output_root>/<batch_id>/
├── batch.json
├── summary.md
├── compare/
│   ├── diff.json
│   └── diff.md
└── cases/
    └── <case_id>/
        ├── run.json
        ├── stdout.txt
        ├── stderr.txt
        ├── final.json
        ├── transcript.jsonl        # 可选
        ├── workspace/              # 独立运行工作目录或其引用
        ├── evidence.md
        └── scorecard.json
```

## Isolation And Safety Rules

首版批量运行入口必须遵守以下规则：

- 不同 case 之间不得共享工作目录
- 评分只读取本次 `run_id` 目录中的证据
- 未声明安全环境的 case，默认视为只读评测
- 若被测 Agent 试图触发 upload 或真实外部写操作，且当前不满足 `approved_write` 条件，应直接阻断并记录为安全策略阻断

## Failure Classification Rules

首版必须固定输出以下归因枚举之一：

- `skill_behavior`
- `wrapped_tool`
- `runtime_environment`
- `harness_system`

不可出现“失败了，但不知道为什么”的空白归因。
