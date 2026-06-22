# Validate Output Contract

## Purpose

本文档补充说明 `run_recog_rollup --validate` 在 condition 超出首版能力边界时，
必须对 Agent 暴露的结构化返回契约。

这里约束的是“工具应该如何报边界”，不是“工具替 Agent 做最终用户沟通”。

## Scope

本契约仅覆盖以下场景：

- condition 仍是占位符，尚未补成真实表达式
- condition 使用了首版 AST 白名单外的语法节点
- condition 调用了首版未开放的 helper
- condition 通过 `F("字段名")` 或自由标识符引用了无法解析的字段

这些都属于“当前框架表达能力边界”，而不是普通的数据脏值问题。

## Required Behavior

当 `run_recog_rollup --validate` 命中上述场景时，系统 MUST：

1. 以 `status=error` 结束本次 validate
2. 返回 `stage=validate`
3. 在失败检查项中给出稳定错误码，至少包括：
   - `condition_placeholder_detected`
   - `condition_parse_failed`
   - `condition_ast_not_allowed`
   - `condition_function_not_allowed`
   - `condition_invalid_f_call`
   - `condition_identifier_unresolved`
   - `condition_runtime_error`
4. 在 `message` 或 `details` 中明确这是当前首版 condition 的能力边界
5. 在 `message` 或 `details` 中明确提示 Agent 不应自行发明 helper 或绕过框架
6. 在 `message` 或 `details` 中明确提示应联系开发者扩展 condition 能力或新增内置 helper

## Agent Interpretation Contract

工具层与 Agent 层的职责边界如下：

- 工具负责：准确识别边界、输出结构化错误码、暴露可机读提示
- Agent 负责：据此向用户说明“当前需求超出首版能力边界，需要联系开发者扩展”

因此，validate 不要求直接输出完整面向终端用户的话术，但必须输出足够稳定的机读信息，
让 Agent 能安全停止，并把结论正确转达给用户。

## Example Failure Shape

```json
{
  "status": "error",
  "stage": "validate",
  "mode": "validate",
  "recog_id": "demo_recog",
  "message": "Validation failed.",
  "details": [
    {
      "sampled_source_file": "D:/AI/rere-agent/tests/_pytest_tmp/demo/source.csv",
      "checks": [
        {
          "check_name": "condition_valid",
          "scope": "rule:已结算金额",
          "passed": false,
          "message": "condition 使用了不被允许的函数。",
          "details": [
            {
              "code": "condition_function_not_allowed",
              "agent_action": "contact_developer_for_condition_extension",
              "guidance": "当前 condition 超出首版能力边界，请联系开发者扩展内置 helper 或 condition 能力。"
            }
          ]
        }
      ]
    }
  ]
}
```

## Non-Goals

- 不要求 validate 自动修复规则
- 不要求 Agent 自动生成新 helper
- 不要求在首版中开放自定义 helper 注册机制
