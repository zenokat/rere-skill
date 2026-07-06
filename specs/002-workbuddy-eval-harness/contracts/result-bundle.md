# Contract: Result Bundle

## Directory

一次运行只暴露以下结果：

```text
<output_root>/<batch_id>/
├── batch.json
└── cases/
    └── <case_id>/
        ├── result.json
        ├── session.jsonl
        └── outputs/
```

不生成 Markdown 报告、artifact index、agent-result、final、scorecard、baseline 或 diff 文件。

## batch.json

```json
{
  "batch_id": "20260627-130214-revenue-recognition-real-smoke",
  "suite_id": "revenue-recognition-real-smoke",
  "model": {
    "requested": "glm-5",
    "config": {
      "source": "suite_config_file",
      "fingerprint": "sha256:9d3f0c9a2c4b7e11"
    }
  },
  "status": "passed",
  "case_counts": {
    "total": 1,
    "completed": 1,
    "passed": 1,
    "failed": 0
  },
  "metrics": {
    "duration_ms": 48231,
    "tokens": {
      "input": null,
      "output": null,
      "total": null
    },
    "cost": {
      "amount": null,
      "currency": null
    }
  }
}
```

`batch.json` 只表达批次总体情况，不包含 case 数组。`model.requested` 记录本批请求的 CodeBuddy 模型 ID；来源可以是 suite.yaml 的 `model.id`，也可以是 CLI `--model` 临时覆盖。如果没有指定模型，值为 `null`，表示使用 CodeBuddy 默认模型。声明 suite `model.config_file` 时，`model.config` 会记录配置来源和指纹，但不会记录本机路径、文件内容或 API key。每条 case 的细节固定写在 `cases/<case_id>/result.json`。

## result.json

```json
{
  "case_id": "revenue-recognition-dine-in-202605",
  "status": "completed",
  "verdict": "pass",
  "score": 1,
  "final_response": "Preview generated under output/preview.xlsx; upload was not run.",
  "model": {
    "requested": "glm-5",
    "observed": "glm-5",
    "config": {
      "source": "suite_config_file",
      "fingerprint": "sha256:9d3f0c9a2c4b7e11"
    }
  },
  "metrics": {
    "duration_ms": 48231,
    "tokens": {
      "input": null,
      "output": null,
      "total": null
    },
    "cost": {
      "amount": null,
      "currency": null
    }
  },
  "graders": [
    {
      "id": "preview_file_exists",
      "type": "code",
      "score": 1,
      "summary": "Found a preview artifact under outputs/.",
      "evidence": {
        "file": "outputs/202605_dine_in_revenue.xlsx",
        "size_bytes": 18642,
        "sha256": "..."
      }
    },
    {
      "id": "preview_matches_baseline",
      "type": "code",
      "score": 1,
      "summary": "All preview rows match baseline records.",
      "evidence": {
        "recog_id": "dine_in_revenue",
        "period": "202605",
        "preview_count": 1,
        "baseline_count": 1,
        "difference_count": 0
      }
    }
  ],
  "evidence": {
    "session_path": "session.jsonl",
    "outputs_path": "outputs/",
    "missing": []
  }
}
```

`score` 只能是 `1` 或 `0`。`verdict` 固定由 graders 计算：全 1 为 `pass`，有 0 为 `fail`。`model.requested` 是本次请求的模型，`model.observed` 是 CodeBuddy session 或 stdout 中实际采到的模型；采不到时为 `null`。`model.config` 只在使用 suite `model.config_file` 时出现，用于证明本次运行复制了哪一份自定义模型配置，不包含 API key。

## session.jsonl

`session.jsonl` 是 CodeBuddy / WorkBuddy 原始 session 的逐行原文，作为 Agent 轨迹的唯一事实源。harness 直接复制 CodeBuddy 写出的 session 文件，不做归一化、不屏蔽路径、不丢弃字段。事件类型与字段以 CodeBuddy 原始为准，常见包括 `message`（user/assistant）、`function_call`、`function_call_result`、`reasoning`，并保留 `providerData`、`sessionId`、时间戳等原始元数据。

由于它是原始证据，`session.jsonl` 可能包含工具输出中的环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`。结果包应按敏感材料处理：默认只用于本地复盘和受控归档，不公开分享；如果真实凭据被采集进 session，应先轮换凭据。

```jsonl
{"type":"message","role":"user","content":[{"type":"input_text","text":"<system-reminder data-role=\"user-context\">...</system-reminder>"}],"sessionId":"..."}
{"type":"function_call","name":"Bash","callId":"call_001","arguments":"uv run scripts/run_recog_rollup.py --preview ...","sessionId":"..."}
{"type":"function_call_result","name":"Bash","callId":"call_001","status":"completed","output":{"type":"text","text":"result_file=output/202605_dine_in_revenue.xlsx"},"sessionId":"..."}
{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Preview generated under output/202605_dine_in_revenue.xlsx; upload was not run."}],"sessionId":"..."}
```

如果 case 未捕获到 session，`session.jsonl` 不生成，`result.json` 的 `evidence.missing` 记为 `codebuddy_session_jsonl`。

## outputs/

`outputs/` 是从 sandbox `output/` 复制出来的业务产物目录。

规则：

- 目录必须存在，可以为空。
- 不额外生成 outputs 索引。
- grader 证据引用使用 `outputs/...` 相对路径。
- preview Excel 等业务产物直接保存在该目录中。
