# 收入确认汇总业务逻辑已迁移

收入确认汇总（结构检验、试算预览、受控上传、飞书 Bitable 调用、规则引擎等）的业务逻辑
**已从 `src/`（现已重命名为 `eval-harness/`）迁移到可交付的 skill 包**：

```
skill/revenue-recognition/scripts/lib/
```

`eval-harness/` 现在只承载本地评测工具，不再包含汇总业务逻辑：

- `eval-harness/cli/run_skill_eval_batch.py` —— eval-harness CLI 入口。
- `eval-harness/evals/` —— WorkBuddy / CodeBuddy eval harness 核心。
- `eval-harness/integrations/codebuddy_cli/` —— CodeBuddy CLI 调用集成。

## 测试如何引用业务逻辑

仓库内的业务回归测试（`tests/unit`、`tests/contract`、`tests/integration`、`tests/helpers`）
通过 `tests/conftest.py` 把 `skill/revenue-recognition/scripts/lib/` 注入 `sys.path`，
以 `cli.`/`core.`/`models.`/`utils.`/`integrations.feishu_bitable` 等包名直接 import skill
包内的业务代码。`cli` 与 `integrations` 是 PEP 420 命名空间包，可同时解析 eval-harness
与 skill lib（业务逻辑）两侧的子模块。

## 修改业务逻辑的正确入口

要改汇总/校验/上传逻辑，直接改 `skill/revenue-recognition/scripts/lib/` 下的代码。
不要在 `eval-harness/` 下重建汇总业务逻辑。
