# Rollup_Core_Large_20260704 Badcase 分析

## 1. 概述

本次最新运行目录为：

`evals/results/Rollup_Core_Large_20260704/20260704-143657-_rollup_perftest_20260704`

批次结果显示 5 个 case 中 3 个通过、2 个失败。结论先行：

- `eleme_delivery_revenue_202605` 不是收入确认产品失败，而是评测器没有识别 `uv run --script ...` 这种合法脚本调用方式。该 case 已生成产物，且产物与 baseline 完全一致。
- `eleme_delivery_settlement_202605` 是真实执行未完成：Agent 已调用正确脚本，但 preview 仍在后台运行时就给出了最终回复，eval harness 随即复制 `output/`，导致产物缺失。
- 当前打开的 `suite.yaml` 声明了 `case_max_duration:600`，但本批次 `result.json` 中未实际启用该 grader；因此本报告按本批次实际评分口径分析，同时把性能阈值作为额外风险单列。

## 2. 批次概览

| 项目 | 值 |
| --- | --- |
| batch_id | `20260704-143657-_rollup_perftest_20260704` |
| batch.json suite_id | `_Rollup_PerfTest_20260704` |
| 当前数据集目录 | `Rollup_Core_Large_20260704` |
| 模型 | `deepseek-v4-pro` |
| 总 case 数 | 5 |
| 通过 | 3 |
| 失败 | 2 |
| 总耗时 | 3,376,287 ms |
| 总 token | 326,705 |

| case | 结果 | 耗时 | 是否有产物 | 主要失败点 | 分析判定 |
| --- | --- | ---: | --- | --- | --- |
| `eleme_delivery_revenue_202605` | fail | 683.2s | 有 | 脚本调用 grader 全部为 0 | 评测器漏判 |
| `eleme_delivery_settlement_202605` | fail | 778.9s | 无 | `preview_file_exists=0`、`preview_matches_baseline=0` | preview 未完成即结束 |
| `jingdong_delivery_revenue_202605` | pass | 560.0s | 有 | 无 | 正常 |
| `jingdong_delivery_settlement_202605` | pass | 604.1s | 有 | 无 | 正常，但超过 600s 性能阈值 |
| `meituan_delivery_settlement_202605` | pass | 731.1s | 有 | 无 | 正常，但超过 600s 性能阈值 |

## 3. 失败类型一：评测器漏识别 `uv run --script`

### 涉及 case

- `eleme_delivery_revenue_202605`

### 现象

该 case 的 `result.json` 中：

- `preview_file_exists=1`
- `preview_matches_baseline=1`
- `skill_script_called:list_recog_items=0`
- `skill_script_called:run_recog_rollup=0`
- `skill_script_args:run_recog_rollup:--validate=0`
- `skill_script_args:run_recog_rollup:--preview=0`

这组结果表面上看像是 Agent 没有调用收入确认 skill 脚本，但 session trace 显示 Agent 实际执行了脚本：

```powershell
uv run --script ".workbuddy/skills/revenue-recognition/scripts/list_recog_items.py"
uv run --script ".workbuddy/skills/revenue-recognition/scripts/run_recog_rollup.py" --validate --recog_id eleme_delivery_revenue --source_file "input/饿了么收入"
uv run --script ".workbuddy/skills/revenue-recognition/scripts/run_recog_rollup.py" --preview --recog_id eleme_delivery_revenue --period 202605 --source_file "input/饿了么收入"
```

preview 也已完成，输出文件为：

`outputs/202605_eleme_delivery_revenue_20260704-151239.xlsx`

baseline 对比结果为 232 行、11 个字段、`diff_count=0`。

### 根因

根因在 eval harness 的脚本调用识别逻辑，而不是收入确认 skill。

`eval-harness/evals/graders/skill_script_called.py` 的 `_matches_script_path_invocation()` 当前匹配的是：

- `uv run scripts/<script>.py`
- `python scripts/<script>.py`
- `py scripts/<script>.py`
- 或进入 `scripts/` 后直接调用脚本

但它不支持：

```powershell
uv run --script path/to/scripts/<script>.py
```

`eval-harness/evals/graders/skill_script_args.py` 又依赖 `skill_script_called` 中的 `_find_script_calls()` 先找到脚本调用，再检查 `--validate`、`--preview` 参数。因此一旦脚本调用被漏识别，参数 grader 也会连带失败。

### 排除项

- 不是 Agent 没读 skill：trace 中可见它读取了 `.workbuddy/skills/revenue-recognition/SKILL.md` 和 `references/rollup.md`。
- 不是没有调用脚本：trace 中有 `list_recog_items.py` 和 `run_recog_rollup.py` 的实际命令。
- 不是产物错误：preview 产物存在，且 baseline 完全一致。

### 改进建议

优先级 P0：

1. 修改 `eval-harness/evals/graders/skill_script_called.py::_matches_script_path_invocation()`，支持 `uv run --script <script_path>`。
2. 在 `tests/` 中为 `skill_script_called` 和 `skill_script_args` 补充覆盖：
   - `uv run --script .workbuddy/skills/revenue-recognition/scripts/list_recog_items.py`
   - `uv run --script .workbuddy/skills/revenue-recognition/scripts/run_recog_rollup.py --validate ...`
   - `uv run --script .workbuddy/skills/revenue-recognition/scripts/run_recog_rollup.py --preview ...`

优先级 P1：

1. 在 `skill/revenue-recognition/references/rollup.md` 中继续强化推荐命令形态，例如统一写成：

```powershell
cd .workbuddy/skills/revenue-recognition
uv run scripts/list_recog_items.py
uv run scripts/run_recog_rollup.py --validate ...
uv run scripts/run_recog_rollup.py --preview ...
```

这能降低 Agent 命令形态分叉，但不能替代 P0 的评测器修复，因为 `uv run --script` 本身也是合理命令。

## 4. 失败类型二：后台 preview 未完成即被当作最终结果

### 涉及 case

- `eleme_delivery_settlement_202605`

### 现象

该 case 的 `result.json` 中：

- `skill_script_called:list_recog_items=1`
- `skill_script_called:run_recog_rollup=1`
- `skill_script_args:run_recog_rollup:--validate=1`
- `skill_script_args:run_recog_rollup:--preview=1`
- `preview_file_exists=0`
- `preview_matches_baseline=0`

这说明 Agent 已经按要求调用脚本，但最终没有可评分产物。

最终回复也直接说明 preview 没完成：

```text
Preview 仍在进行中。第 12/14 个文件「蔡林记」（约 130MB）数据量较大，已处理 250,000 行，正在等待后续数据。进程仍在运行中，继续等待完成通知。
```

session trace 中，preview 进入后台任务后仍在运行：

- 任务状态：`Status: running`
- 运行时长：约 10m55s
- 当前进度：第 12/14 个文件，已处理 250,000 行
- rule bundle：26 条规则、5 个 source specs

harness 随后复制 sandbox 的 `output/`，由于产物还没有写出，结果目录中 `outputs/` 为空。cleanup 阶段还出现了文件占用错误，进一步说明当时仍存在未释放的运行过程或文件句柄。

### 根因

这是一个“长耗时任务管理”问题，由 Agent 行为和 eval harness 回收机制共同触发。

从产品脚本看，`skill/revenue-recognition/scripts/lib/core/preview/preview_stage.py` 的 preview 逻辑会：

1. 加载 rule bundle。
2. 遍历每个源文件。
3. 对每个源文件再遍历 `source_sheets`。
4. 调用 `build_sheet_dataset(..., stream_to_end=True)` 流式读取大 Excel。
5. 对每一行计算分组字段、条件表达式和求和规则。
6. 全部聚合完成后才写出 preview 产物。

这意味着耗时大致受以下因素叠加影响：

- 文件数量
- 大文件行数
- source specs 数量
- rollup rules 数量
- 条件表达式复杂度

`eleme_delivery_settlement_202605` 的组合明显更重：26 条规则、5 个 source specs，并且存在约 130MB 的大 Excel。相比之下：

- `eleme_delivery_revenue_202605`：10 条规则、1 个 source spec，preview 完成。
- `jingdong_delivery_settlement_202605`：15 条规则、1 个 source spec，后台任务完成后通过。

因此，后台运行本身不是问题。问题在于本 case 中后台任务还没完成，Agent 就把“仍在进行中”作为最终回答提交，harness 又没有二次识别“仍有后台 Bash 任务在运行”，于是提前进入评分。

### 排除项

- 不是源文件或配置错误：validate 阶段通过。
- 不是 Agent 没调用脚本：脚本调用和参数 grader 全部通过。
- 不是脚本没有进度输出：trace 中能看到每 50,000 行的 preview 进度。
- 不是后台任务必然失败：`jingdong_delivery_settlement_202605` 同样进入后台，最终等到 completed 后产物生成并通过。

### 改进建议

优先级 P0，eval harness 层：

1. 在 `eval-harness/integrations/codebuddy_cli/headless_runner.py` 或 `eval-harness/evals/runners/batch_runner.py` 增加“后台任务未完成”检测。
2. 如果 session 中最后一个相关 `TaskOutput` 仍是 `Status: running`，或最终回复包含“仍在进行中”“等待完成通知”等明确未完成信号，应进入以下两种状态之一：
   - 继续等待后台任务完成，再复制 `output/`；
   - 达到明确上限后标记为 `tool_timeout` 或 `background_task_timeout`，不要把它混同为普通产物缺失。
3. `copy_outputs_to_result()` 前增加保护：若检测到关键 preview 任务仍在运行，不应立即复制空目录并评分。

优先级 P0，收入确认 skill 层：

1. 优化 `eleme_delivery_settlement` 的大文件处理路径，重点减少对同一大型 workbook 的重复打开和重复扫描。
2. 如果多个 source spec 指向同一物理 sheet，可考虑合并为一次扫描，在同一行数据上同时执行多个 source spec 对应的规则。
3. 对超大文件增加更密集或更可解释的进度信息，例如包含当前文件、当前 source spec、已处理行数和预计剩余阶段。当前 50,000 行一个进度点能证明脚本还活着，但不足以帮助 Agent 判断是否应该继续等待多久。

优先级 P1，skill 文档层：

1. 在 `skill/revenue-recognition/SKILL.md` 的等待规则中补充：只要后台任务仍是 `running`，Agent 不能把“继续等待完成通知”作为最终交付结果。
2. 文档中明确：只有出现 `Preview complete` 且产物路径已生成，才能总结产物；否则应继续等待或明确报告环境超时。

## 5. 评测口径风险：`case_max_duration:600` 未锁定

当前打开的：

`evals/datasets/Rollup_Core_Large_20260704/suite.yaml`

声明了 `case_max_duration:600`。但本批次：

- `batch.json` 的 `suite_id` 是 `_Rollup_PerfTest_20260704`
- 各 case 的 `result.json.graders` 中没有 `case_max_duration:600`

这说明本次实际运行口径与当前工作区中的 `suite.yaml` 不完全一致，或者 suite 在运行后被修改过。

这个差异会显著影响结论解释。按本批次实际 grader，3 个 case 通过；但如果 600 秒上限生效，则以下 case 也会被性能阈值影响：

- `eleme_delivery_revenue_202605`：683.2s，虽然产物正确。
- `jingdong_delivery_settlement_202605`：604.1s，当前通过。
- `meituan_delivery_settlement_202605`：731.1s，当前通过。

### 改进建议

优先级 P0：

1. 在每次 batch 结果目录保存当次运行使用的 suite manifest 快照。
2. 在 `batch.json` 中记录 suite 文件路径、suite fingerprint、实际 grader 列表。
3. 确保结果目录名、`suite_id`、源 suite 文件保持可追溯关系。

优先级 P1：

1. 对性能评测明确两套口径：
   - 功能正确性：是否调用脚本、是否生成产物、是否匹配 baseline。
   - 性能稳定性：是否在目标时间内完成。
2. 如果 `case_max_duration:600` 是核心指标，应把它纳入正式 summary；如果只是观察指标，应避免它影响功能正确性的 pass/fail。

## 6. 迭代方向总结

### P0：修复脚本调用 grader

修复 `uv run --script` 识别后，`eleme_delivery_revenue_202605` 应从失败转为通过。

按当前六个实际 grader 口径，这一项可将通过率从 3/5 提升到 4/5。

### P0：处理后台任务未完成的评分时机

当前 `eleme_delivery_settlement_202605` 的失败不是“脚本没跑”，而是“脚本还没跑完就评分”。harness 需要在复制产物和评分前确认后台任务是否真正完成。

修复后会得到更准确的结果：

- 如果 preview 最终完成并产物匹配 baseline，则该 case 应通过。
- 如果 preview 超过运行上限，则应明确标记为性能超时，而不是产物缺失。

### P1：优化大文件 preview 性能

`eleme_delivery_settlement_202605` 暴露出大文件、多 source specs、多规则组合下的耗时风险。建议优先优化同一 workbook / sheet 的重复读取与重复扫描。

目标不是单纯“让这次 case 通过”，而是让大文件场景具备可预测的完成时间和更清晰的进度反馈。

### P1：固化评测 manifest

本次结果与当前 `suite.yaml` 在 `case_max_duration:600` 上存在口径差异。建议后续每个 batch 都保存运行时 manifest 快照，避免复盘时无法判断当时到底用了哪些 grader。

## 7. 修复后的预期效果

按本批次实际评分口径：

- 修复 `uv run --script` 漏判后，最低预期通过率为 4/5。
- 再修复后台任务等待与回收机制后，如果 `eleme_delivery_settlement_202605` 最终产物正确，预期通过率可到 5/5。

如果启用 `case_max_duration:600`：

- 当前多个正确产物 case 会受性能阈值影响。
- 在启用该阈值前，建议先完成大文件 preview 性能优化，或把性能分与功能正确性分开展示。
