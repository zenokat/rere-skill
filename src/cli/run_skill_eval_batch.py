"""`run_skill_eval_batch` CLI 入口。

该命令是首版 eval harness 的唯一用户入口：读取最小 YAML，调用真实
CodeBuddy CLI，写出 `batch.json`、`result.json`、`session.jsonl` 和 `outputs/`。
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from evals.bootstrap import build_eval_harness
from evals.reports.serializers import dumps_json
from evals.shared.env import load_repo_dotenv

app = typer.Typer(add_completion=False, help="运行 WorkBuddy / CodeBuddy eval batch。")


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="评测集 YAML 路径。"),
    output_root: Path = typer.Option(..., "--output_root", help="评测结果输出根目录。"),
    case: list[str] | None = typer.Option(None, "--case", help="仅运行指定 case，可重复传入。"),
    model: str | None = typer.Option(None, "--model", help="临时覆盖 suite.yaml 的 model.id；为空时使用 suite 配置或 CodeBuddy 默认模型。"),
) -> None:
    """执行一批 skill 评测 case。

    Args:
        suite: 评测集 YAML 路径。
        output_root: 输出根目录。
        case: 可选 case 白名单。
        model: 可选模型 ID 覆盖值。正式评测应优先写在 suite.yaml 的
            `model.id` 中。

    Returns:
        None。
    """

    try:
        load_repo_dotenv()
        harness = build_eval_harness()
        batch_payload = harness.run_batch(
            suite_path=suite,
            output_root=output_root,
            selected_case_ids=case,
            model=model,
        )
        typer.echo(_stdout_summary(batch_payload, output_root))
        raise typer.Exit(0 if batch_payload["status"] == "passed" else 2)
    except typer.Exit:
        raise
    except Exception as exc:
        payload = {
            "status": "error",
            "stage": "eval_harness",
            "message": str(exc),
            "retryable": False,
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        raise typer.Exit(1)


def _stdout_summary(batch_payload: dict[str, object], output_root: Path) -> str:
    """生成 CLI stdout 的最小 JSON 摘要。

    Args:
        batch_payload: `batch.json` 内容。
        output_root: 输出根目录。

    Returns:
        str: stdout JSON 文本。
    """

    batch_id = str(batch_payload["batch_id"])
    payload = {
        "batch_id": batch_id,
        "status": batch_payload["status"],
        "case_counts": batch_payload["case_counts"],
        "batch_json": str(output_root / batch_id / "batch.json"),
    }
    return dumps_json(payload)


def main() -> None:
    """命令行入口函数。"""

    app()


if __name__ == "__main__":
    main()
