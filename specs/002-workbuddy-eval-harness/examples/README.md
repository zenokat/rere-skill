# Examples

## revenue-recognition-real-smoke

这是首版面向评测者的示例评测集，用隔离 sandbox 跑当前收入确认 skill 的真实单 case。

运行命令：

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml `
  --output_root .tmp/evals/revenue-real-smoke
```

示例结构：

```text
revenue-recognition-real-smoke/
├── suite.yaml
└── cases/
    └── revenue-recognition-dine-in-202605/
        ├── instruction.md
        ├── skills/
        └── input/
```

> 对于多条 case 共用同一套 skill 和 input 的场景，可在 `suite.yaml` 中声明 suite 级 `input`/`skills` 共享路径，case 级目录留空即可，harness 会自动回退。详见 [README](../../README.md#suiteyaml)。

本 case 的目标是：只执行堂食收入 202605 的 validate 和 preview，不执行 upload。评分器为 `preview_file_exists`，检查 `outputs/` 中是否出现本次 preview 文件。

预期结果文件：

- `batch.json`
- `cases/revenue-recognition-dine-in-202605/result.json`
- `cases/revenue-recognition-dine-in-202605/session.jsonl`
- `cases/revenue-recognition-dine-in-202605/outputs/`
