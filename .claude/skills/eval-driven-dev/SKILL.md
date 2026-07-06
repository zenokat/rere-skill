---
name: eval-driven-dev
description: Use when Codex needs to run an evaluation-driven development loop in this repository: collect or inspect eval results, perform badcase analysis, implement targeted fixes, rerun the relevant suite or cases for acceptance, preserve evidence, and write the standard daily-eval iteration commit summary. Typical triggers: eval-driven dev, 评测驱动迭代, 日常评测迭代, 获取评测结果后分析并修复, badcase 分析后重跑验收, eval iteration commit.
---

# Eval Driven Dev

## Core Goal

Run the standard daily eval loop end to end:

1. collect the latest eval result;
2. analyze badcases and classify root causes;
3. implement the smallest fix at the owning layer;
4. rerun the target suite or focused cases for acceptance;
5. preserve the evidence;
6. commit with the standard "daily eval -> iteration -> acceptance" summary format when requested.

Use this skill as the coordinator. When the work requires deeper analysis or grader work, also use the narrower skills:

- `eval-badcase-analysis` for detailed failure classification and a `badcase_analysis.md` report;
- `eval-grader-build` for grader or harness changes.

## Required Context

Before acting, read the repository-local context that affects eval execution:

- `AGENTS.md`
- `environment.md`
- `sandbox-rules-allow-list.md` when command approval or sandbox behavior is relevant
- target suite `suite.yaml`
- latest relevant `batch.json`
- failed cases' `result.json` and `session.jsonl`

Prefer `rg` / `rg --files` for discovery. Use UTF-8 aware readers for JSON or Markdown containing Chinese text.

## Workflow

### 1. Establish The Eval Baseline

Identify the exact suite and result batch before changing code.

- If the user says "latest run", choose the newest timestamped batch under the suite's result root.
- Record suite id, batch id, model, case counts, pass/fail counts, duration, and grader list.
- If the suite has changed after the batch was produced, call that out explicitly. Do not compare runs as the same口径 unless the grader list and suite intent match.

For each failed or suspicious case, inspect:

- `result.json`: verdict, failed graders, evidence, final response, duration;
- `session.jsonl`: actual Agent decisions, tool calls, background tasks, and final state;
- `outputs/`: whether expected artifacts exist and match the grader's evidence.

### 2. Analyze Badcases Before Fixing

Classify failures by owning layer before editing code:

- grader bug: valid behavior was scored incorrectly;
- harness bug: result bundle, output collection, session recovery, sandbox setup, timeout, or dispatch is wrong;
- Agent behavior issue: the Agent skipped required steps, ended early, wrote to the wrong place, or ignored skill instructions;
- product/skill issue: the shipped skill documentation or script behavior led the Agent to fail;
- case data issue: source files, periods, or fixtures are wrong;
- environment issue: credentials, model config, CodeBuddy login, Windows path, encoding, network, or permissions.

When there are multiple failures, group by root cause rather than walking cases one by one. Produce `badcase_analysis.md` in the batch directory when the user asks for analysis, when the run has multiple failures, or when the fix direction is not obvious.

### 3. Implement The Smallest Owning-Layer Fix

Fix the layer that owns the root cause.

- Grader/harness fixes belong under `eval-harness/`.
- Revenue-recognition product behavior belongs under `skill/revenue-recognition/`.
- Eval data or suite口径 changes belong under `evals/datasets/`.
- Environment learnings that will recur belong in `environment.md`.

Keep the diff surgical. Do not loosen graders to hide real Agent or product failures. Do not change suite thresholds just to make a failing run pass; if the threshold is wrong, explain the口径 decision and keep it separate from code fixes when practical.

### 4. Test Locally

Run targeted tests for the changed layer first, then broader eval-harness tests if runner, grader dispatch, or shared behavior changed.

Common commands:

```powershell
python -m pytest tests/unit/eval_harness
python -m pytest tests/contract/eval_harness
python -m compileall eval-harness/evals eval-harness/integrations skill/revenue-recognition/scripts/lib
```

If tests already failed before the change, state that clearly. If a test cannot be run, explain why and what evidence replaces it.

### 5. Rerun Acceptance Eval

Rerun the smallest eval that proves the fix:

- one case when the fix is case-specific;
- all affected historical failures when validating a badcase cluster;
- the whole suite when the request is a daily eval acceptance or the change touches shared harness behavior.

Use the repository launcher for self-authored eval CLI commands:

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch --suite <suite.yaml> --output_root <output-root>
```

Before running suites that use `model.config_file: ${EVAL_MODELS_JSON}`, ensure the repository `.env` / `.env.local` defines `EVAL_MODELS_JSON`, or that the current process environment does.

After the rerun, inspect `batch.json` and each affected `result.json`. Report case counts, failed graders, and evidence path. If acceptance fails, loop back to analysis rather than hand-waving.

### 6. Preserve Evidence

Keep evidence that future readers can audit:

- batch result directory with `batch.json`, case `result.json`, `session.jsonl`, and outputs;
- `badcase_analysis.md` when produced;
- tests that reproduce the harness/grader/product failure;
- environment notes for repeatable local setup issues.

When result artifacts are large, stage only the artifacts that are part of the intended eval evidence package.

## Standard Commit Summary

When the user asks to commit an eval-driven iteration, use the daily-eval iteration style:

```text
[recog][eval] <suite_id or eval name>: <迭代主题和验收结果>

P0: <最高优先级修复或根因闭环>

P1: <第二项修复>

P2: <第三项修复>

P3: <可选：文档、skill 指引、环境或验收增强>

补充回归测试覆盖 <关键测试范围>

验收结果：<suite_id> 最新运行 <passed>/<total> passed，<关键 grader 或剩余风险>
```

Guidelines:

- Use Chinese.
- Start with domain tags, usually `[recog][eval]`; add `[fix]`, `[context]`, or `[chore]` only when they clarify a cross-domain change.
- Use P0/P1/P2/P3 lines for the iteration story, not a file-by-file changelog.
- Include the acceptance result in the message body.
- Commit only staged files unless the user explicitly asks to stage more.
- Before committing, confirm the current branch and note any relevant unstaged changes left behind.

## Completion Report

Final response should be concise and conclusion-first:

- what changed and why;
- tests run and pass/fail status;
- acceptance eval result and path;
- commit hash if committed;
- any unstaged changes or residual risk.
