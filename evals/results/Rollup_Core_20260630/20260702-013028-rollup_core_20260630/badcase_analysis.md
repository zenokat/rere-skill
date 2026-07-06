# Rollup_Core_20260630 Badcase 分析

运行信息：batch_id=20260702-013028-rollup_core_20260630，共 14 case，9 pass / 5 fail，总耗时 90min，总 token 753,919。

## 失败总览

5 个失败 case 归为 3 种类型：

| 类型 | Case 数 | 简述 |
|---|---|---|
| A. Agent 偏离 skill 路径 | 1 | Agent 自己写了一套汇总逻辑，产物格式不符合 grader 预期 |
| B. 脚本执行卡死 | 3 | validate/preview 执行时间过长，Agent 放弃轮询或 CodeBuddy 超时 |
| C. 源文件给错 | 1 | case 的源文件不符合 skill 规则，Agent 正确阻断但被判 fail |

---

## 类型 A：Agent 偏离 skill 路径

### 涉及 case

| Case | outputs | 最终回复 | 耗时 |
|---|---|---|---|
| eleme_delivery_revenue_202605 | 有文件 | 自行生成汇总 Excel | 8m05s |

### 根因

**harness 的 skill 目录复制逻辑将 SKILL.md 遗漏在父层，Agent 读不到 SKILL.md 后判定"skill 为空"，自行写了一套 Python 汇总逻辑，产物不含 grader 期望的 `results` sheet。**

同一模型（glm-5.2）面对相同的 sandbox 结构缺陷，行为不一致——有些 Agent 能绕过 SKILL.md 缺失去读 references/ 下的文档继续走 skill 路径，eleme Agent 则直接放弃。

### 改进方向

**P0：修复 skill 目录复制 bug**

当前 `suite.yaml` 的 `skills` 指向 `revenue-recognition/` 目录，harness 的 `_copy_tree` 逻辑（case_sandbox.py L77-81）遍历其**子目录**作为独立 skill 复制，导致 SKILL.md 遗漏在父层。修复后所有 case 的 Agent 都能读到 SKILL.md，获得完整的 skill 路径指引。

两种修复方式：
1. `suite.yaml` 改为 `skills: d:/AI/rere-agent/skill`（指向 skill 父目录），harness 会把 `revenue-recognition/` 作为一个完整 skill 复制
2. harness 的 `_copy_tree` 逻辑增加：如果源目录本身包含 SKILL.md，将其整体视为一个 skill 而非遍历子目录

### 证据链

#### 1. sandbox skill 结构有问题（所有 case 共有）

```
skill/revenue-recognition/     <- suite.yaml 指向这里
├── SKILL.md                    <- 被留在这一层，未复制
├── references/                 <- 被当成独立 skill 复制
│   ├── rollup.md
│   └── workflow.md
└── scripts/                    <- 被当成独立 skill 复制
    ├── list_recog_items.py
    ├── run_recog_rollup.py
    └── lib/
```

复制到 sandbox 后：

```
.workbuddy/skills/
├── references/     <- SKILL.md 不在这里
│   ├── rollup.md
│   └── workflow.md
└── scripts/        <- SKILL.md 也不在这里
    ├── list_recog_items.py
    └── run_recog_rollup.py
```

正确的结构应该是 `.workbuddy/skills/revenue-recognition/SKILL.md`。

#### 2. eleme Agent 的决策路径

| 步骤 | 行为 | reasoning |
|---|---|---|
| L4-7 | ls input/ 和 workspace/ | 了解环境 |
| L8-9 | ls `.workbuddy/skills/` | 看到两个子目录 references/ 和 scripts/ |
| L12 | `cat references/SKILL.md` 和 `cat scripts/SKILL.md` | **两个路径都返回空（exit code 1）** |
| L14 reasoning | "The skill files are empty" | **判定 skill 为空，放弃使用** |
| L15 起 | 自己用 openpyxl 逐个探索 Excel | 开始手动处理 |
| L42-44 | 创建 Task 计划（Analyze/Compute/Generate） | 完全偏离 skill 路径 |
| L71 | 写 build_summary.py 并运行 | 自行生成产物 |

Agent 生成的 Excel 包含 3 个中文 sheet（`收入总览`、`门店收入明细`、`数据来源说明`），而 grader 期望 `results` sheet。

#### 3. 对比：通过的 dine_in_revenue 面对同样问题走了不同路径

dine_in_revenue 的 Agent 同样看不到 SKILL.md（sandbox 结构相同），但选择了继续探索 references/ 下的文档：

| 步骤 | reasoning |
|---|---|
| L14 ls skills/ | "Let me look at the skills directory to understand what tools are available." |
| L19-20 Read references/workflow.md | "There's a skills directory with reference files. Let me read them to understand the workflow." |
| L24-25 Read scripts/*.py | "Now I understand the workflow. This is a rollup task. I need to: 1. Find recog_id 2. Validate 3. Preview" |
| L42 | `uv run scripts/list_recog_items.py` | **成功调用 skill 脚本** |
| L59 | `uv run scripts/run_recog_rollup.py --preview` | 生成标准产物 |

两个 Agent（同一模型 glm-5.2）面对完全相同的 sandbox 结构问题，一个判定"skill 为空"放弃，另一个判定"有 reference 文件可以读"继续探索。

---

## 类型 B：脚本执行卡死

### 涉及 case

| Case | outputs | 最终回复 | 耗时 |
|---|---|---|---|
| eleme_delivery_settlement_202605 | 空 | "后台校验仍在进行，我停止轮询" | 7m38s |
| jingdong_delivery_revenue_202605 | 空 | "校验仍在运行（已约 5.5 分钟），我将停止轮询" | 7m43s |
| meituan_delivery_settlement_202605 | 有文件（内容正确） | "CodeBuddy run timed out" | 19m02s |

### 根因

**skill 脚本（`run_recog_rollup.py --validate`）从启动到结束只有最终 JSON 一次输出，中间零进度。当执行时间因飞书 API 网络延迟叠加而超过 Agent 的前台命令 timeout 时，Agent 无法区分"脚本在正常运行"和"脚本挂了"，合理放弃轮询。**

这不是 Agent 行为问题——Agent 走了正确的 skill 路径，选了正确的 recog_id，传入了合理的 source_file。问题在 skill 脚本的可观测性设计。

加剧因素：
- `get_project()` 被重复调用两次（`run_recog_rollup_service.py:122` 和 `validate_stage.py:77`），多出 4 次冗余飞书 API 调用（共 7 次，可减到 5 次）
- Windows Docker 环境下 `open.feishu.cn` 的 DNS/TCP 延迟间歇性叠加（timeout=30s，7 次串行最多 210 秒）
- Agent 自行添加 `| tail` pipe 加剧了输出缓冲问题（但 pipe 不是根因——alipay 用了同样 pipe 在 22 秒内完成）

meituan_delivery_settlement 的失败原因不同：session.jsonl 缺失（CodeBuddy 超时），但产物已生成且与 baseline 完全匹配（237 行 0 差异）。Agent 行为正确，preview 阶段处理 436M input 目录耗时超过 15 分钟 timeout 上限。

### 改进方向

#### P2a：skill 脚本增加 stderr 进度输出（核心修复）

`run_recog_rollup.py` 需要在执行过程中输出进度标记。使用 **stderr** 输出（stderr 不被 `| tail` 截断，也不污染最终 JSON stdout）。

**改动位置：`validate_stage.py` 的 `run()` 方法（L69-117）和 `run_recog_rollup_service.py` 的 `run_validate()` 方法。**

```python
# validate_stage.py, run() 方法内
import sys

print("[validate] Loading project configuration...", file=sys.stderr, flush=True)
# _require_project() 调用后
print("[validate] Project loaded. Discovering source files...", file=sys.stderr, flush=True)
# discover_source_files() 后
print(f"[validate] Found {len(source_files)} source file(s). Sampling for validation...", file=sys.stderr, flush=True)
# choose_validation_sample() 后
print(f"[validate] Sampling: {sampled_file}", file=sys.stderr, flush=True)
# load_rule_bundle() 前后
print("[validate] Loading rule bundle from Feishu (2 API calls)...", file=sys.stderr, flush=True)
print(f"[validate] Rule bundle loaded ({len(rules)} rules, {len(specs)} source specs)", file=sys.stderr, flush=True)
# build_sheet_dataset() 前后
print(f"[validate] Opening source file: {sampled_file}...", file=sys.stderr, flush=True)
# _validate_target_fields() 前后
print("[validate] Fetching target table fields from Feishu...", file=sys.stderr, flush=True)
print("[validate] Validation complete.", file=sys.stderr, flush=True)
```

好处：
- Agent 能从 stderr 看到进度（`2>&1` 合并 stderr 到 stdout，即使 stdout 被 `| tail` 截断，stderr 仍然实时可见）
- 开发者手动运行时也能看到进度
- 不改变 stdout 的 JSON 输出格式，不影响 grader 或下游消费者

#### P2b：消除 `get_project()` 的重复调用

当前 `get_project()` 在两处各调用一次：
- `run_recog_rollup_service.py:122`（`_require_project()` 内）
- `validate_stage.py:77`（`run()` 内）

每次触发 `list_projects()` + `list_tables()` 两个 API 调用，共 4 次冗余。修复方式：在 `run_validate()` 中将 project 对象作为参数传递给 `validation_stage.run()`，避免重复查询。7 次网络调用减少到 5 次，延迟暴露面降低约 30%。

#### P2c：SKILL.md 补充等待指导

在 SKILL.md 中明确告知 Agent：
1. 脚本执行包含飞书 API 网络调用和 `uv run` 依赖安装，总耗时可能在 30 秒到 2 分钟之间
2. 不要在命令中添加 `| tail`、`| head` 等 pipe 命令——这会缓冲输出导致看不到进度
3. 如果脚本执行超过 2 分钟没有输出，检查 stderr 是否有进度标记（`[validate]` 前缀）

#### P2d（可选）：harness timeout 调整

meituan_delivery_settlement 的 19 分钟超时说明某些 case 的 preview 阶段处理大 input 目录（436M）需要超过 15 分钟。可以考虑给 preview 阶段单独设置更宽的 timeout，或在 `suite.yaml` 中支持 per-case timeout 覆盖。这不是优先事项，P2a + P2b 修复后大部分 case 的执行时间应在可接受范围内。

### 证据链

#### 1. Agent 走了正确的 skill 路径

eleme_delivery_settlement 的 Agent 成功执行了 list_recog_items -> validate 的标准流程：

| 步骤 | 行为 | 结果 |
|---|---|---|
| L14 | `find .workbuddy -name SKILL.md` | 找不到 SKILL.md |
| L27-28 | Read `scripts/list_recog_items.py` 和 `scripts/run_recog_rollup.py` | 读到了脚本 |
| L36 | TaskCreate | 计划走 list -> validate -> preview |
| L44 | `uv run list_recog_items.py` | **成功**，找到 `eleme_delivery_settlement` |
| L52 | `uv run run_recog_rollup.py --validate --recog_id eleme_delivery_settlement --source_file "input/饿了么回款/" 2>&1 \| tail -60` | **被自动后台化**（foreground timeout），6 分钟无输出 |
| L55-83 | Agent 反复 TaskOutput 轮询 6 次 | 每次 "running, no output"，最终放弃 |

#### 2. pipe 不是根因

通过 case 中 alipay_settlement 也用了 `| tail -80` pipe，但 validate 在 22 秒内正常完成，直接进入 preview。pipe 只是加剧了判断困难，不是区分通过/失败的因素。

#### 3. 飞书 API 全局限流不是原因

14 个 case 串行执行，3 个失败 case 不是连续出现的：

```
01:30 dine_in_revenue          PASS   173s
01:33 eleme_delivery_revenue   FAIL   485s  (类型A)
01:41 eleme_delivery_settlement FAIL   458s  (类型B)
01:49 member_collection         PASS   190s    <-- 飞书 API 正常
01:52 wechat_pay_settlement     PASS   248s    <-- 飞书 API 正常
01:56 alipay_settlement         PASS   187s    <-- 飞书 API 正常
01:59 shouqianba_settlement     PASS   254s    <-- 飞书 API 正常
02:04 douyin_voucher_settlement PASS   397s    <-- 飞书 API 正常
02:10 jingdong_delivery_revenue FAIL   463s  (类型B)
02:18 jingdong_delivery_settlement PASS 626s    <-- 同平台，飞书 API 正常
02:29 amap_voucher_settlement   PASS   208s    <-- 飞书 API 正常
02:32 meituan_voucher_settlement FAIL  298s  (类型C)
02:37 meituan_delivery_revenue  PASS   237s    <-- 飞书 API 正常
02:?? meituan_delivery_settlement FAIL 1142s (类型B, CodeBuddy timeout)
```

eleme 在 01:41 卡死后，紧接着 01:49-01:59 四个 case 都正常调用了飞书 API。jingdong_delivery_revenue 在 02:10 卡死后，02:18 的 jingdong_delivery_settlement（同平台、类似数据量）正常通过。

#### 4. validate 执行链路中有 7 次串行飞书 API 调用

从 skill 脚本实现角度，`--validate` 的完整调用链：

```
run_recog_rollup.py (entry)
  -> build_service()                         # 加载配置，初始化飞书客户端
  -> service.run_validate()
     -> _require_project()                    # API CALL 1+2: list_projects, list_tables
     -> validation_stage.run()
        -> discover_source_files()              # 目录遍历 rglob("*")，收集文件路径（不读内容）
        -> choose_validation_sample()          # random.Random(seed).choice(files)
        -> rule_repository.load_rule_bundle()  # API CALL 3+4: list_records(source_spec), list_records(rollup_rule)
        -> catalog_repository.get_project()     # API CALL 5+6: 重复调用 (!)
        -> _validate_source_sheet_specs()
           -> build_sheet_dataset()             # openpyxl 打开一个采样文件
              -> <10MB: load_workbook(read_only=False)
              -> >=10MB: load_workbook(read_only=True) (流式)
        -> _validate_target_fields()
           -> client.list_fields()              # API CALL 7
```

其中 API CALL 5+6 与 1+2 完全重复，代码位置：`run_recog_rollup_service.py:122` 和 `validate_stage.py:77`。

#### 5. stdout 零输出的代码级证据

整个 validate 阶段的所有输出都通过 `formatters.py` 的 `exit_with_json()` 在最后一次性输出。中间没有任何 `print()`、`typer.echo()` 或 `sys.stderr.write()` 调用。

在 Docker 容器中（非 TTY 环境），Python 默认使用块缓冲（4KB/8KB），加上 `| tail` pipe 会进一步缓冲 stdout。Agent（和 harness）在整个执行过程中看到的输出永远是 "no output"。

---

## 类型 C：源文件给错

### 涉及 case

| Case | outputs | 最终回复 | 耗时 |
|---|---|---|---|
| meituan_voucher_settlement_202605 | 空 | "已阻断在 validate 阶段" | 4m59s |

### 根因

**Agent 的行为是正确的**——源文件不符合 skill 规则，Agent 按规则在 validate 阶段阻断，不生成产物。这是 case 的源文件给错了。

Rollup_Core_20260630 的评测目的是验证"当信息和源文件都完善的情况下 Agent 能否顺利调用工具完成汇总"，因此应该提供符合规则的源文件。

### 改进方向

**P1：修正 meituan_voucher_settlement 的 input 文件**

替换为包含 `收益明细` sheet 的交易明细级文件。不需要新增 grader 或修改 Agent 行为。

### 证据链

Agent 读取了 `input/美团团购/收益列表/` 下的 6 个 xlsx 文件，发现只有聚合报表 sheet（`按门店`、`按日期`、`按项目`、`按账户`），缺少规则要求的 `收益明细` 交易明细级 sheet。Agent 成功走了标准 skill 路径（list_recog_items -> validate），在 validate 阶段正确阻断并报告了原因。

---

## 迭代方向总结

按优先级排序：

### P0：修复 skill 目录复制 bug

**影响范围**：所有 14 个 case（SKILL.md 全部缺失）

当前 `suite.yaml` 的 `skills` 指向 `revenue-recognition/` 目录，harness 遍历其子目录作为独立 skill 复制，导致 SKILL.md 遗漏。这是一个确定性的 bug，修复后所有 case 的 Agent 都能读到 SKILL.md。

两种修复方式：
1. `suite.yaml` 改为 `skills: d:/AI/rere-agent/skill`（指向 skill 父目录），harness 会把 `revenue-recognition/` 作为一个完整 skill 复制
2. harness 的 `_copy_tree` 逻辑增加：如果源目录本身包含 SKILL.md，将其整体视为一个 skill 而非遍历子目录

### P1：修正 meituan_voucher_settlement 的 input 文件

**影响范围**：1 个 case

源文件缺少 `收益明细` sheet，需要替换为交易明细级文件。

### P2：skill 脚本可观测性修复

**影响范围**：所有 case 的 validate/preview 执行

| 子项 | 改动 | 说明 |
|---|---|---|
| P2a | `validate_stage.py` 添加 stderr 进度输出（`[validate]` 前缀标记） | 核心修复 |
| P2b | 消除 `get_project()` 重复调用（7 次 API 减到 5 次） | 配合修复 |
| P2c | SKILL.md 补充等待指导和 pipe 禁令 | 配合修复 |

代码级证据：`formatters.py` 只在最后通过 `exit_with_json()` 输出一次结果，中间没有任何进度标记。`get_project()` 在 `run_recog_rollup_service.py:122` 和 `validate_stage.py:77` 各调用一次，共 4 次冗余 API 调用。

### P3：评估 CodeBuddy timeout 配置

**影响范围**：meituan_delivery_settlement（436M input，preview 需要 >15 分钟）

当前默认 900 秒（15 分钟），对于大 input 目录的 case 可能不够。需要评估是否调宽上限，或者优化 preview 阶段的性能。

### P4：根因排查（可选）

在 Docker 容器内单独运行 `run_recog_rollup.py --validate --recog_id eleme_delivery_settlement --source_file <目录>`，附加 `PYTHONUNBUFFERED=1` 和 `PYTHONDONTWRITEBYTECODE=1`，看是否能稳定复现挂死以及卡在哪个步骤。

### 不需要做的事

- 不需要新增 grader（现有两个 grader 的判定逻辑是对的）
- 不需要修改 Agent 的"等待策略"（脚本挂起时 Agent 放弃是合理行为，根源在脚本可观测性）
- 不需要为"合规阻断"新增判定维度（类型 C 是 case input 给错的问题）
- 不需要修改飞书 API 的 timeout 配置（30 秒已经是合理值，超时会抛异常而非静默挂死）
- 不需要修改 `choose_validation_sample` 的随机选择策略（validate 只打开一个文件做结构检查，不是性能瓶颈）

### 修复后的预期效果

- 类型 A 的 eleme_delivery_revenue：Agent 能读到 SKILL.md，走标准 skill 路径，产物格式由脚本保证，grader 通过。
- 类型 B（eleme_delivery_settlement + jingdong_delivery_revenue）：
  - P0 不影响这两个 case（它们已经走了正确的 skill 路径）
  - P2a（stderr 进度输出）让 Agent 能看到脚本在运行，不会因为"无输出"而放弃轮询
  - P2b（消除重复 API 调用）减少约 30% 的网络延迟暴露面
  - P2c（SKILL.md 等待指导）减少 Agent 自行加 `| tail` pipe 的概率
- 类型 C：不受影响，仍然需要 P1 修正 input。

**P0 + P1 + P2a + P2b 修复后，预期通过率从 9/14（64%）提升到 13/14（93%）**。剩余 1 个失败（meituan_delivery_settlement 的 CodeBuddy timeout）需要 P3（timeout 调整）解决。
