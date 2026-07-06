"""收入确认 WorkBuddy 自动化评测底座包。

本包提供一条可复用的评测链路：
1. 读取最小 case manifest。
2. 为每个 case 创建一次性 sandbox。
3. 调用真实 CodeBuddy CLI 无头模式。
4. 保留 CodeBuddy 原始 session JSONL 作为 Agent 轨迹事实源。
5. 生成 `batch.json`、`result.json`、`session.jsonl` 和 `outputs/`。

这些能力面向评测执行者和 Agent 共同使用，因此 JSON 契约是唯一结果入口。
"""
