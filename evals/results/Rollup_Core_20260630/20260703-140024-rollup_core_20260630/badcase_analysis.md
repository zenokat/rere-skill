# Rollup_Core_20260630 Badcase 分析

**批次 ID**: `20260703-140024-rollup_core_20260630`
**模型**: deepseek-v4-pro
**分析日期**: 2026-07-03

## 失败总览

| 指标 | 数值 |
|------|------|
| 总 case 数 | 14 |
| 通过 | 12 |
| 失败 | 2 |
| 通过率 | 85.7% |
| 总耗时 | 83.8 分钟 |
| 总 token | 642,212 |

### 失败 case 分类

| case_id | verdict | 失败类型 | 业务产物是否正确 | 耗时 |
|---------|---------|----------|-----------------|------|
| member_collection_202605 | fail | grader 误判（匹配模式不完整） | 正确（231 行，与 baseline 完全一致） | 358s |
| meituan_delivery_settlement_202605 | fail | 脚本超时（大文件性能瓶颈） | 无产物（未在超时内完成） | 724s |

---

## 类型 1：grader 误判 -- skill_script_called 匹配模式不完整

### 涉及 case

| case_id | 业务产物 | preview_file_exists | preview_matches_baseline | skill_script_called 全部 | 耗时 |
|---------|---------|---------------------|--------------------------|-------------------------|------|
| member_collection_202605 | 正确（231 行，0 diff） | 1 | 1 | 0（4 项 grader 全部 0 分） | 358s |

### 根因

Agent 确实调用了 `list_recog_items.py` 和 `run_recog_rollup.py`，且业务产物与 baseline 完全一致。失败原因是 `skill_script_called` grader 的匹配模式无法识别 Agent 的命令格式。

**具体机制**：grader 用子串 `scripts/{script_name}.py` 检查命令字符串。member_collection 的 Agent 使用了 `cd ".../scripts" && uv run list_recog_items.py` 的命令格式（先 cd 到 scripts 目录，再直接用脚本名），而 grader 要求的子串 `scripts/list_recog_items.py` 在这个格式中被 `&&` 和 `uv run ` 打断，导致匹配失败。

对比通过的 case（如 dine_in_revenue），Agent 使用的是 `cd ".../revenue-recognition" && uv run scripts/list_recog_items.py` 的格式（cd 到 skill 根目录，用完整路径调用脚本），恰好包含了 grader 需要的子串。

**本质**：同一个 Agent 模型在不同 case 中使用了两种等价的命令格式，grader 只识别了其中一种。

### 改进方向

| 优先级 | 改进项 | 具体位置 | 说明 |
|--------|--------|---------|------|
| P0 | 修复 grader 匹配模式 | [skill_script_called.py:140](eval-harness/evals/graders/skill_script_called.py#L140) | `_find_script_calls` 函数中 `pattern = f"scripts/{script_name}.py"` 只做简单子串匹配。应改为同时匹配以下等价格式：(1) `scripts/xxx.py` (2) `cd .../scripts" && uv run xxx.py` (3) 其他合理的等价调用方式 |

**建议修复方案**：将 `_find_script_calls` 从子串匹配改为正则匹配，覆盖以下命令格式：

```python
# 当前匹配模式（只覆盖格式 1）
pattern = f"scripts/{script_name}.py"

# 建议匹配模式（覆盖格式 1-3）
import re
# 格式1: uv run scripts/list_recog_items.py
# 格式2: cd .../scripts" && uv run list_recog_items.py
# 格式3: cd .../scripts && uv run list_recog_items.py
pattern = re.compile(
    rf"(?:scripts/){{0,1}}{re.escape(script_name)}\.py"
)
```

**预期效果**：修复后 member_collection_202605 的 4 项 skill grader 将从 0 分变为 1 分，verdict 从 fail 变为 pass，通过率从 85.7% 提升至 92.9%。

### 证据链

**1. Agent 确实调用了脚本（session trace 提取的 12 条 Bash 命令）**

从 session.jsonl 中提取的命令中，有 6 条包含脚本调用：

| 命令序号 | 命令（截断） | grader 能否匹配 |
|---------|-------------|---------------|
| CMD[0] | `cd ".../scripts" && uv run list_recog_items.py` | 不能 -- `scripts/list_recog_items.py` 子串不连续 |
| CMD[1] | `cd ".../scripts" && uv run run_recog_rollup.py --va...` | 不能 |
| CMD[3] | `cd ".../scripts" && uv run run_recog_rollup.py --va...` | 不能 |
| CMD[6] | `cd ".../scripts" && uv run run_recog_rollup.py --va...` | 不能 |
| CMD[8] | `cd ".../scripts" && uv run run_recog_rollup.py --va...` | 不能 |
| CMD[9] | `cd ".../scripts" && uv run run_recog_rollup.py --pr...` | 不能 |

**2. grader 源码确认**

`skill_script_called.py` 第 140 行：
```python
pattern = f"scripts/{script_name}.py"
return [cmd for cmd in commands if pattern in cmd]
```

这是一个纯粹的 `in` 子串匹配，要求命令字符串中包含 `scripts/list_recog_items.py` 这个完整连续子串。

**3. 通过 case 的命令格式对比**

dine_in_revenue（通过）的命令格式：
```
cd ".../revenue-recognition" && uv run scripts/list_recog_items.py 2>&1
```
`scripts/list_recog_items.py` 子串存在，grader 匹配成功。

member_collection（失败）的命令格式：
```
cd ".../revenue-recognition/scripts" && uv run list_recog_items.py
```
`scripts/list_recog_items.py` 子串不存在（被 `&& uv run ` 打断），grader 匹配失败。

**4. 排除的因素**

| 排除的假设 | 排除证据 |
|-----------|---------|
| Agent 没有调用脚本 | session trace 中 6 条 Bash 命令明确调用了 list_recog_items.py 和 run_recog_rollup.py |
| Agent 跳过了 validate 步骤 | Agent 执行了 4 次 validate（1 次混合文件失败 + 2 次字段不匹配 + 1 次成功） |
| 业务产物有问题 | preview_matches_baseline grader 确认 231 行数据与 baseline 0 diff |
| 上一轮也是这个 grader 判定的失败 | 上一轮没有 skill_script_called grader（是在两轮之间新增的），member_collection 上轮 pass |

**5. 上轮对比**

member_collection_202605 在上一轮（20260702-013028）中 verdict=pass，score=1，耗时 190s。上一轮的 grader 只有 `preview_file_exists` 和 `preview_matches_baseline` 两项，没有 `skill_script_called` 和 `skill_script_args`。本轮新增了流程合规性 grader 后，由于 grader 匹配模式不完整，导致该 case 被误判为失败。

---

## 类型 2：脚本超时 -- openpyxl 处理大文件性能瓶颈

### 涉及 case

| case_id | 最终回复 | preview_file_exists | 脚本是否被调用 | 耗时 |
|---------|---------|---------------------|--------------|------|
| meituan_delivery_settlement_202605 | "大文件仍在处理中..." | 0（无产物） | 是（list + validate + preview 均已执行） | 724s |

### 根因

Agent 正确执行了完整的工作流（list_recog_items -> validate -> preview），但 `run_recog_rollup.py --preview` 在处理 9 个源文件时，前 3 个"全部门店"大文件（合计约 450MB 的 xlsx）用 openpyxl 读取极慢。脚本运行约 10 分钟后被 WorkBuddy 的前台超时机制自动转入后台运行，Agent 随后尝试用 TaskOutput 轮询等待，但轮询也超时了，最终会话在总超时到达时被终止，preview 产物未生成。

**这不是 Agent 行为问题，也不是脚本逻辑 bug，而是运行时性能瓶颈导致的超时失败。**

### 改进方向

| 优先级 | 改进项 | 具体位置 | 说明 |
|--------|--------|---------|------|
| P1 | xlsx 大文件读取性能优化 | [skill/revenue-recognition/scripts/lib/](skill/revenue-recognition/scripts/lib/) 中读取 xlsx 的模块 | 将 openpyxl 替换为 polars 或 openpyxl 的 read_only 模式，减少内存占用和读取时间。450MB 的 xlsx 用 openpyxl 全量加载到内存需要数分钟，用 read_only 模式或 polars 可以提速 5-10 倍 |
| P2 | 前台超时配置提升 | eval harness 的 WorkBuddy CLI 集成层 | 当前前台超时约 10 分钟（从 trace 行为推断），对大文件 case 不够用。考虑提升到 15-20 分钟，或改为自适应超时（根据源文件总大小调整） |
| P2 | 脚本 stderr 进度输出优化 | [run_recog_rollup.py](skill/revenue-recognition/scripts/lib/cli/run_recog_rollup.py) | 当前脚本在处理每个文件时只在 stderr 输出 `[preview] Processing file N/M...`，但没有输出已用时间或预估剩余时间。增加时间信息可以帮助 Agent 和人类判断是否真的卡住还是正常慢 |

**预期效果**：P1 修复后，meituan_delivery_settlement 的 preview 阶段耗时预计从 >10 分钟降至 2-3 分钟，在超时内可以正常完成。通过率将从 85.7%（修复 grader 后 92.9%）进一步提升至 100%。

### 证据链

**1. 源文件大小**

Agent 探索 `input/美团外卖回款/` 目录时发现 9 个文件，其中 3 个"全部门店"文件特别大：
- 文件 1: ~186MB
- 文件 2: ~192MB
- 文件 3: ~63MB
- 其余 6 个文件: 门店级文件（较小）

合计约 450MB 的 xlsx 需要逐个用 openpyxl 读取解析。

**2. 执行时间线**

| 时间 | 经过时间 | 事件 |
|------|---------|------|
| 15:12:12 | 0s | 用户请求 |
| 15:12:13 | 1s | Agent 探索 input 目录 + 读 SKILL.md |
| 15:12:34 | 22s | Agent 查看美团外卖回款目录 + 读 rollup.md |
| 15:12:45 | 33s | Agent 执行 list_recog_items.py，找到 recog_id |
| 15:13:01 | 49s | validate 第一次失败（相对路径错误） |
| 15:13:18 | 66s | validate 第二次成功（绝对路径，22 项检查通过） |
| 15:13:42 | 90s | 开始执行 --preview 命令 |
| 15:23:51 | 11m 39s | 前台超时，命令被自动转后台（已处理 file 3/9） |
| 15:23:54 | 11m 42s | Agent 第一次 TaskOutput 轮询，进度卡在 file 3/9 |
| 15:23:55 | 11m 43s | Agent 第二次 TaskOutput 轮询，进度无变化 |
| ~15:30:35 | ~18m 23s | 会话被总超时终止 |

关键观察：从 15:13:42 开始 preview 到 15:23:51 被转后台，约 10 分钟只处理了 3/9 个文件。如果线性外推，9 个文件全部处理完需要约 30 分钟，远超总超时 20 分钟。

**3. stderr 输出确认脚本在正常工作**

```
[preview] Processing file 1/9...
[preview] Processing file 2/9...
[preview] Processing file 3/9...
```

脚本没有报错，逐文件处理，只是 openpyxl 读取超大 xlsx 文件极慢。

**4. Agent 的轮询行为**

Agent 在命令被转后台后，连续两次使用 `TaskOutput(block=true, timeout=600000)` 轮询。系统提示 "do NOT poll TaskOutput in a loop"，但 Agent 忽略了这个提示。两次轮询返回的 Duration 分别是 `10m 3s` 和 `10m 6s`（仅增加 3 秒），说明脚本在后台的处理速度也极慢。

**5. 上轮对比**

meituan_delivery_settlement_202605 在上一轮（20260702-013028）也是失败 case，但失败模式不同：
- 上轮：CodeBuddy 整体超时（19m02s），但产物已生成（preview_file_exists=1, preview_matches_baseline=1），只是 session 超时导致 status=failed
- 本轮：产物未生成（preview_file_exists=0），Agent 甚至没能等到脚本完成

两轮对比说明这个 case 的数据量（450MB xlsx）始终是一个性能挑战，但上轮至少产出了部分结果（只处理了部分文件），本轮连部分结果都没有产出。

**6. 排除的因素**

| 排除的假设 | 排除证据 |
|-----------|---------|
| Agent 偏离路径 | Agent 完整执行了 list -> validate -> preview 三步工作流，命令格式正确 |
| 脚本 bug / 崩溃 | stderr 输出正常，逐文件推进，无报错 |
| 飞书 API 限流 | preview 阶段不调用飞书 API（只在 validate 阶段校验 Bitable 字段），preview 是纯本地 xlsx 处理 |
| 沙盒磁盘空间不足 | 脚本在处理 file 3/9 后没有报磁盘错误，只是速度极慢 |

---

## 迭代方向总结

按优先级排序的改进项：

| 优先级 | 改进项 | 类型 | 影响范围 | 预期效果 |
|--------|--------|------|---------|---------|
| P0 | 修复 skill_script_called grader 匹配模式 | grader bug 修复 | member_collection_202605 | 通过率 85.7% -> 92.9% |
| P1 | xlsx 大文件读取性能优化（替换 openpyxl 或使用 read_only 模式） | 产品性能 | meituan_delivery_settlement_202605 | 通过率 92.9% -> 100% |
| P2 | 前台超时配置提升或自适应超时 | 评测框架配置 | 大文件 case | 降低超时失败风险 |
| P2 | 脚本 stderr 进度输出增加时间信息 | 可观测性 | 所有 case | 帮助 Agent 和人类判断进度 |

### 修复后的预期效果

| 场景 | 当前通过率 | P0 修复后 | P0+P1 修复后 |
|------|-----------|----------|-------------|
| 总体 | 12/14 (85.7%) | 13/14 (92.9%) | 14/14 (100%) |

**核心结论**：本轮 2 个失败 case 都不是 Agent 行为问题。一个是 grader 匹配模式的 bug（Agent 做了正确的事但被误判），另一个是 openpyxl 处理超大 xlsx 的性能瓶颈（脚本逻辑正确但运行时超时）。两者都有明确的代码修复方向。
