# 汇总阶段指南

## 用途

当任务属于收入确认 SOP 第 3 步“汇总”时，使用本参考文件。汇总阶段消费已经完成预处理的干净单文件或干净目录，先做结构检验，再生成试算预览结果，并在明确授权时把门店级基础事实字段上传到业务数据库。

汇总产物是下游收入回款确认的字段原材料，不是最终收入确认结果。

## 意图识别

当用户请求包含以下目标时，判断为“汇总阶段”任务：

- 列出可用收入确认项目，或查找应该使用的 `recog_id`。
- 检查某个源文件或目录能否被某个确认项目消费。
- 对平台流水数据做预览、试算、聚合、汇总，尤其是按门店生成基础事实字段。
- 生成可供人工复核或后续上传使用的 `result_file`。
- 将已经生成的汇总结果文件上传到配置好的业务表。
- 评测是否能端到端跑通汇总阶段。

当用户请求符合以下情况时，不要当作汇总阶段继续执行：

- 输入仍是原始下载压缩包、未解压文件，或混放多类业务文件的平台导出目录。此时路由到“文件预处理”。
- 用户询问折后收入、实际回款、平台服务费、税费、配送费或其他最终确认字段如何计算。此时属于下游“收入回款确认”，若没有专门参考文件，说明边界并停止。
- 用户要求入账、验算、分发、调整或封版。此时属于更后面的 SOP 阶段，若没有专门参考文件，说明边界并停止。

如果同一个请求同时包含汇总和下游确认，只完成汇总阶段，并明确说明后续交接点。

## 必要输入

运行工具前，先确认以下输入是否具备：

| 输入 | 含义 | 适用模式 |
|---|---|---|
| 确认项目线索 | 用户提供的项目名称、平台、业务描述，用于选择 `recog_id`。 | 所有模式 |
| `recog_id` | 机器可读的确认项目主键。不知道时先用 `list_recog_items` 查询。 | validate、preview、upload |
| `period` | 会计期间，格式为 `YYYYMM`。 | preview、完整流程 |
| `source_file` | 已完成预处理的干净源文件或干净目录。 | validate、preview、完整流程 |
| `result_file` | preview 阶段生成、准备上传的结果文件。 | upload |

`source_file` 必须已经干净。它可以是单个文件，也可以是目录，但不能是原始下载目录，也不能是仍混放多种业务文件的目录。

## 工具前提

一个完整的 skill 产品包应提供以下执行路径之一：

1. 系统 `PATH` 上已经能直接调用 `list_recog_items` 和 `run_recog_rollup`。
2. 当前 Python 环境可以以模块方式调用汇总工具包。
3. 使用 skill 随包脚本 `scripts/list_recog_items.py` 和 `scripts/run_recog_rollup.py`，并通过显式参数或环境变量提供工具路径。

不要要求用户一定拥有原始开发仓库的启动器。在开发仓库内，`.codex/scripts/rere.cmd` 可以作为本地验证便利入口，但它不是 skill 产品契约的一部分。

汇总工具会从环境变量或本地环境文件读取飞书凭证、配置表和结果表信息。若配置缺失，把问题归类为“环境失败”，而不是“skill 能力失败”。

## 推荐流程

### 1. 识别项目

如果用户没有提供准确的 `recog_id`，先列出可用项目：

```bash
list_recog_items
```

只有当返回的项目清单能明确匹配用户的业务线索时，才选择某个项目继续执行。若多个项目都可能匹配，先向用户澄清，不要猜测。

### 2. 校验干净输入

preview 前先执行结构检验：

```bash
run_recog_rollup --validate --recog_id <recog_id> --source_file <干净单文件或目录>
```

如果校验失败，停止，不进入 preview。总结时说明失败阶段、源文件或 sheet 信息，以及下一步更可能归属的责任方：预处理、配置、汇总工具或业务确认。

### 3. 生成试算预览

校验通过后执行 preview：

```bash
run_recog_rollup --preview --recog_id <recog_id> --period <YYYYMM> --source_file <干净单文件或目录>
```

记录返回的 `result_file`、行数、字段数、警告和工具提示。`result_file` 是交给人工复核或受控上传的正式交接产物。

### 4. 仅在明确授权时上传

上传是单独的受控动作，不要默认执行。

```bash
run_recog_rollup --upload --recog_id <recog_id> --result_file <preview结果文件>
run_recog_rollup --upload --append --recog_id <recog_id> --result_file <preview结果文件>
run_recog_rollup --upload --upsert --recog_id <recog_id> --result_file <preview结果文件>
```

上传前必须确认目标环境安全，并且用户明确要求上传。首版评测基线优先覆盖 validate 和 preview；除非 case 明确说明上传环境安全，否则不要把上传作为默认评测动作。

## 随包脚本

随包脚本保持两个入口，名称与汇总工具契约一致：

```bash
python scripts/list_recog_items.py
python scripts/run_recog_rollup.py --validate --recog_id <recog_id> --source_file <path>
python scripts/run_recog_rollup.py --preview --recog_id <recog_id> --period <YYYYMM> --source_file <path>
python scripts/run_recog_rollup.py --upload --recog_id <recog_id> --result_file <path>
```

这两个脚本只是包装器，不实现任何业务规则。它们应委托给已安装的汇总命令、随包运行时，或用户通过环境变量显式提供的命令路径。

## 失败处理

继续行动前，先把失败分到正确类型：

| 失败类型 | 典型信号 | 正确处理 |
|---|---|---|
| 输入缺失 | 没有期间、没有源文件、没有项目线索，或项目不唯一。 | 向用户补问缺失信息。 |
| 预处理问题 | 输入仍是压缩包、混合目录、缺少预期文件、sheet 不对。 | 停止并路由到文件预处理。 |
| 环境问题 | 缺少凭证、缺少 CLI 命令、权限或网络配置异常。 | 报告环境失败和需要补齐的配置。 |
| 汇总工具问题 | validate、preview 或 upload 阶段返回技术性错误。 | 报告阶段和错误细节，不要自行绕过。 |
| 业务边界问题 | 不支持的规则、业务含义不清、baseline 差异无法解释。 | 停止并请求业务或开发确认。 |
| 下游请求 | 用户要求最终确认字段或入账动作。 | 说明汇总交接物，不要计算下游字段。 |

## 结果总结模板

每次执行后，用以下结构总结：

```text
结论：<成功 / 已阻断 / 需要澄清 / 环境失败>
阶段：<list / validate / preview / upload>
项目：<recog_id 和可读名称，如已知>
期间：<YYYYMM，如适用>
输入：<source_file 或 result_file>
产物：<result_file、row_count、field_count，如适用>
风险或下一步：<需要人工确认、预处理修正、环境补齐或可进入下游确认>
```

## 本地开发说明

仅在原始开发仓库内部，维护者可以使用：

```powershell
.\.codex\scripts\rere.cmd list_recog_items
.\.codex\scripts\rere.cmd run_recog_rollup --validate --recog_id <recog_id> --source_file <path>
.\.codex\scripts\rere.cmd run_recog_rollup --preview --recog_id <recog_id> --period <YYYYMM> --source_file <path>
```

这只是为了本地开发和沙盒白名单更方便，不应成为 skill 产品的依赖链路。
