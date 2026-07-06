"""Tests for eval result secret redaction."""

from __future__ import annotations

import json

from evals.privacy.redaction import RedactionReport, SecretRedactor, collect_sensitive_values


def test_redacts_known_values_in_session_text() -> None:
    """Known evaluator secrets should be removed from nested session text.

    Args:
        None.

    Returns:
        None. Assertions verify that command output text is safe to commit.
    """

    report = RedactionReport()
    redactor = SecretRedactor({"RERE_FEISHU_APP_SECRET": "feishu-secret-value"})
    event = {
        "type": "function_call_result",
        "output": {
            "type": "text",
            "text": "RERE_FEISHU_APP_SECRET=feishu-secret-value",
        },
    }

    redacted = redactor.redact_jsonl_text(json.dumps(event, ensure_ascii=False) + "\n", report)

    assert "feishu-secret-value" not in redacted
    assert "<redacted:rere_feishu_app_secret>" in redacted
    assert report.replacement_count >= 1
    assert "rere_feishu_app_secret" in report.labels


def test_redacts_sensitive_json_fields_and_bearer_tokens() -> None:
    """Sensitive JSON keys and bearer tokens should be replaced.

    Args:
        None.

    Returns:
        None. Assertions verify both structured and plain-text rules.
    """

    report = RedactionReport()
    redactor = SecretRedactor()
    payload = {
        "apiKey": "sk-example-hidden",
        "headers": {"Authorization": "Bearer abcdef1234567890"},
        "message": 'Authorization: Bearer zyxwv987654321; apiKey=sk-inline-hidden; "apiKey": "sk-json-hidden"',
    }

    redacted = redactor.redact_jsonable(payload, report)

    assert redacted["apiKey"] == "<redacted:apikey>"
    assert redacted["headers"]["Authorization"] == "<redacted:authorization>"
    assert "zyxwv987654321" not in redacted["message"]
    assert "sk-inline-hidden" not in redacted["message"]
    assert "sk-json-hidden" not in redacted["message"]
    assert "bearer_token" in report.labels
    assert "apikey" in report.labels


def test_collect_sensitive_values_from_model_config() -> None:
    """Model config secrets should be discoverable before the run starts.

    Args:
        None.

    Returns:
        None. Assertions verify that suite ``models.json`` values can seed the
        redactor even if the agent later prints the file as plain text.
    """

    values = collect_sensitive_values(
        {
            "models": [
                {
                    "id": "glm-5",
                    "apiKey": "model-config-secret",
                    "url": "https://example.test/v1/chat/completions",
                }
            ]
        },
        prefix="model_config",
    )

    assert values == {"model_config_models_0_apikey": "model-config-secret"}
