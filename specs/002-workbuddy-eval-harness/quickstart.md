# Quickstart: 收入确认 WorkBuddy 自动化评测底座验证指南

## Purpose

这份 quickstart 的目标不是讲“评测是什么”，而是约定实现完成后，如何最小成本验证这套
harness 已经具备批量运行、证据采集、自动评分和基线比较四个主能力。

首版默认只覆盖收入确认 SOP 第 3 步“汇总”的 rollup case，不默认覆盖 upload。

## Prerequisites

- 本仓库 Python 3.13 环境可用
- CodeBuddy CLI 已安装，并且 `codebuddy -p "hello"` 能正常执行
- 被测收入确认 skill 已能在 WorkBuddy / CodeBuddy 同核环境中被发现
- 本地已准备好至少 3 条代表性 case 对应的输入材料
- 若需 trace，已准备可用的 OTLP Collector

补充约定：

- 本仓库内自研 CLI 应统一通过 `.\.codex\scripts\rere.cmd` 启动
- 首版默认只评 `list_recog_items`、`validate`、`preview` 与边界/环境类 case
- upload 相关 case 只有在显式安全环境中才运行

## Scenario 1: 跑通 3 条代表性 smoke batch

目标：验证批量运行、独立结果记录和主摘要已经打通。

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml `
  --output_root .tmp/evals/smoke `
  --result_format json
```

预期检查点：

- 生成一个新的 `<batch_id>` 目录
- stdout 返回批次级 JSON 摘要
- 每条 case 都有独立 `run.json`
- 三条 case 至少分别覆盖：
  - 成功 preview
  - 正确止步
  - 环境失败

## Scenario 2: 打开 transcript 留痕

目标：验证深度证据不是只停留在最终 JSON，而是可以保存过程 transcript。

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml `
  --output_root .tmp/evals/smoke-transcript `
  --capture_transcript `
  --result_format json
```

预期检查点：

- `cases/<case_id>/transcript.jsonl` 存在
- `evidence.md` 中能跳到 transcript
- 若 transcript 采集失败，`run.json` 和 `scorecard.json` 会明确标记证据缺口

## Scenario 3: 打开可选 OTel trace

目标：验证 harness 能把 trace 当作增强观测面接入，而不是改写主结果契约。

```powershell
$env:CODEBUDDY_CODE_ENABLE_TELEMETRY = "1"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml `
  --output_root .tmp/evals/smoke-otel `
  --enable_otel `
  --result_format json
```

预期检查点：

- 主结果目录结构不变
- `run.json` / `evidence.md` 中出现 `telemetry_ref`
- 即使 OTel 不可用，主 batch 仍可根据配置降级，而不是直接把所有 case 混成 skill 失败

## Scenario 4: 保存首份 baseline

目标：验证评测结果可以沉淀成后续可复用基线。

```powershell
.\.codex\scripts\rere.cmd save_skill_eval_baseline `
  --run_dir .tmp/evals/smoke/<batch_id> `
  --baseline_name rollup-smoke-v1
```

预期检查点：

- 生成 `baseline.json`
- 基线中保留 case 版本、skill/prompt/environment 指纹和评分器版本
- 新基线默认先是 `draft` 或等价待复核状态

## Scenario 5: 重跑并做 baseline diff

目标：验证后续重跑能直接输出逐 case、逐维度差异。

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml `
  --output_root .tmp/evals/smoke-rerun `
  --baseline .tmp/evals/baselines/rollup-smoke-v1/baseline.json `
  --result_format json
```

预期检查点：

- 自动生成 `compare/diff.json` 和 `compare/diff.md`
- 差异状态至少区分 `unchanged`、`fixed`、`regressed`、`not_comparable`
- 批次摘要能回答“下一轮更应先改哪里”

## Smoke Suite Composition

首版 smoke suite 建议固定包含以下三类：

1. `rollup-preview-success`
   验证能正确识别项目、执行 validate / preview，并输出 preview 产物。
2. `rollup-correct-stop-downstream`
   验证当任务要求越过 rollup 边界时，skill 会正确止步。
3. `rollup-missing-cli-env-failure`
   验证当 WorkBuddy / CodeBuddy 环境只装了 skill 包装层、未装底层 CLI 时，会被归类为环境失败。

## Done Criteria

当以下条件都满足时，可认为首版评测底座主闭环已经成立：

- 至少 3 条代表性 case 可被同一批次自动发起
- 每条 case 都有独立结果记录和证据入口
- 自动评分能区分通过、正确止步、环境失败
- 结果可保存为 baseline，并能与后续运行直接比较
