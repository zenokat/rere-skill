---
name: eval-grader-build
description: Build or improve eval harness graders for this repository. Use when Codex needs to add a new grader, extend grader dispatch in the eval harness, compare generated artifacts with baselines, write grader tests, run a real smoke case, analyze badcases, or turn grader-building experience into repeatable workflow.
---

# Eval Grader Build

## Core Goal

Use this skill to build eval harness graders that are trustworthy in real runs, not only correct in isolated tests.

A grader is done only when it has:

- a small implementation that follows existing grader patterns;
- runner dispatch wiring when the grader is referenced from `suite.yaml`;
- focused unit or contract tests;
- at least one realistic smoke run when the grader depends on generated artifacts, remote data, or CodeBuddy behavior;
- evidence that a future reader can use to understand failures quickly.

## Read First

Before editing, read the current local patterns:

- `src/evals/graders/preview_file_exists.py` for the simplest grader shape;
- the newest similar grader, if present, for richer evidence and edge-case handling;
- `src/evals/runners/batch_runner.py` for grader dispatch and verdict aggregation;
- `tests/unit/eval_harness/` for testing style;
- `specs/002-workbuddy-eval-harness/plan.md` for harness boundaries;
- `environment.md` when the work touches Feishu, CodeBuddy, PowerShell encoding, Windows paths, temp dirs, or real smoke runs.

If the grader depends on revenue rollup semantics or preview Excel structure, also skim:

- `specs/001-revenue-rollup-cli/quickstart.md`;
- `skill/revenue-recognition/references/rollup.md`.

## Build Workflow

1. Define the score contract first.

   State what earns `score=1`, what earns `score=0`, and what evidence must be included for debugging. Keep the score binary unless the harness contract has explicitly changed.

2. Keep the grader read-only by default.

   Graders may read `result.json`, `session.jsonl`, `outputs/`, case metadata, and controlled remote baselines. They should not mutate business outputs, upload data, or create extra report files unless the suite contract explicitly requires it.

3. Implement the smallest useful grader.

   Put the grader under `src/evals/graders/`. Return a `GraderResult` consistent with existing graders. Prefer deterministic helpers over ad hoc parsing. Include enough evidence to answer: which artifact was checked, which baseline or rule was used, how many records were compared, and what failed.

4. Wire dispatch deliberately.

   Add the new grader id in `BatchRunner` only where existing grader ids are dispatched. Unknown grader ids should continue to fail clearly rather than silently pass.

5. Test behavior, not internals.

   Unit tests should cover the pass path, the important fail path, and missing or malformed inputs. If the grader uses remote systems, inject a fake source in tests instead of calling the remote system.

6. Run a real smoke when unit tests are not enough.

   For graders that validate generated files, remote baselines, or CodeBuddy session behavior, run at least one realistic case through `run_skill_eval_batch`. Use a minimal temporary suite if the production suite is still being edited by someone else.

## Baseline Comparison Graders

When a grader compares a generated preview artifact with a remote or shadow baseline:

- identify the generated artifact from the result bundle, usually `cases/<case_id>/outputs/`;
- read metadata from the artifact when available instead of hardcoding `recog_id`, `period`, field names, or key fields;
- compare on stable business keys, not row order;
- normalize values only where the business representation is known to be equivalent, such as numeric strings versus numbers or blank numeric placeholders that the existing workflow treats as zero;
- report differences in bounded samples so `result.json` stays readable;
- include counts and ids in evidence: preview count, baseline count, key fields, compared fields, target table id if relevant, diff type, diff count, and sample differences.

For Feishu Bitable baselines:

- keep reads controlled by existing `RERE_*` environment variables;
- default to `trust_env=False` unless `RERE_TRUST_ENV_PROXIES=true`;
- pass `page_token` as a query parameter for `records/search`, not in the POST body;
- avoid hardcoded Chinese field names in shell one-liners; read them from files or config to avoid encoding damage.

## Smoke Workflow

Use a real smoke to prove the grader works in the same path users care about:

```powershell
.\.codex\scripts\rere.cmd run_skill_eval_batch --suite <suite.yaml> --output_root <output-root> --case <case_id>
```

For a temporary smoke suite:

- keep it under `.tmp/evals/` unless the user explicitly asks to modify a real suite;
- copy only the needed input files and skill package;
- include only the grader under test and any simple prerequisite grader, such as `preview_file_exists`;
- make the instruction explicit about boundaries such as `validate` only, `preview` only, no upload, source directory, and output directory.

After the run, inspect:

- `batch.json` for batch status and case counts;
- `cases/<case_id>/result.json` for verdict, score, grader evidence, and final response;
- `cases/<case_id>/outputs/` for the artifact the grader evaluated;
- `session.jsonl` only when the failure looks like an Agent behavior issue rather than a grader issue.

Use Python with UTF-8 to inspect JSON that contains Chinese text on Windows. PowerShell pipelines can corrupt display or parsing when the terminal encoding is not aligned.

## Badcase Loop

When a case fails, classify it before changing code:

- grader bug: evidence is wrong, parser cannot read valid output, baseline paging is wrong, or the comparison is too strict;
- harness bug: result bundle paths, copied outputs, sandbox cleanup, session capture, or dispatch are wrong;
- Agent behavior issue: the model did not follow the task, skipped validation, wrote outside `output/`, or uploaded when prohibited;
- case data issue: source files are mixed, missing, stale, or not the intended period;
- environment issue: credentials, network, CodeBuddy login, Docker sandbox, Windows path length, or encoding.

Fix the smallest layer that owns the failure. Do not loosen a grader to hide a real Agent or case problem.

## Done Criteria

Before reporting completion:

- run targeted pytest for the new grader and dispatch tests;
- run broader eval harness tests when the change touches shared runner behavior;
- run `python -m compileall` on changed Python packages when practical;
- run at least one real smoke for artifact or remote-baseline graders;
- state whether tests passed, whether smoke passed, which case was used, and where the evidence lives.

If the smoke reveals a non-blocking harness issue, such as runtime cleanup residue, report it separately from grader correctness and decide whether it belongs in the same change.
