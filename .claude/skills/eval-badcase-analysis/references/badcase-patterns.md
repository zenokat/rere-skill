# Badcase 分析模式参考

本文档记录具体的 badcase 分析案例，作为未来分析同类问题的参考。每个案例提炼出通用的分析模式。

---

## 模式 A：Agent 偏离 skill 路径

### 典型表现

- preview_file_exists grader 通过（产物存在），但 preview_matches_baseline grader 失败（产物格式不符预期）
- Agent 生成的产物缺少标准字段或 sheet
- session trace 中 Agent 读了 skill 文件但判定"为空"后自己写了替代逻辑

### 分析要点

1. **还原 Agent 的决策路径**：逐行读 session.jsonl，找到 Agent 在哪个关键节点放弃了 skill 路径。看它的 reasoning 是什么——是"skill 文件为空"还是"找不到对应命令"还是其他原因。

2. **检查 sandbox 环境配置**：看 harness 的 sandbox 构建逻辑（如 `_copy_tree`、`_effective_skills_dir`）是否正确地将 skill 文件复制到了 Agent 可访问的位置。重点检查：
   - SKILL.md 是否在 Agent 能 cat/read 到的路径
   - skill 目录结构是否被拆散（如子目录被当成独立 skill 复制）
   - 隐藏文件（如 `.env`）是否被排除

3. **做同类对比**：找到同批次中通过了的 case，看它们的 Agent 面对相同的 sandbox 缺陷走了什么不同路径。如果同一模型在相同条件下行为不一致，说明根因在环境配置而非模型能力。

4. **改进方向落到 harness 配置或 skill 文件结构**：这不是 Agent 的问题，是环境或 skill 交付方式的问题。

### 案例：Rollup_Core_20260630 eleme_delivery_revenue

harness 的 `_copy_tree` 遍历 skill 目录的子目录作为独立 skill 复制，导致 SKILL.md 遗留在父层。Agent 读不到 SKILL.md 后判定"skill files are empty"，自行用 openpyxl 写了一套汇总逻辑，产物不含 grader 期望的 `results` sheet。

同一模型的 dine_in_revenue Agent 面对相同的 sandbox 缺陷，选择了继续读 references/ 下的文档，成功走标准路径。

---

## 模式 B：脚本/工具执行卡死

### 典型表现

- outputs 为空
- Agent 最终回复说"校验仍在运行"或"停止轮询"
- 或 CodeBuddy 报 timeout（session.jsonl 缺失）

### 分析要点

1. **确认 Agent 是否走了正确的路径**：先区分"Agent 行为问题"和"工具执行问题"。如果 Agent 选了正确的命令、正确的参数、正确的路径，问题在工具执行而非 Agent 行为。

2. **读产品代码的执行链路**：找到脚本/工具的入口点，逐层追踪调用链。标注出每个网络调用、文件 I/O 操作和计算步骤。记录：
   - 共有多少次网络调用（特别是分页场景下的多次 API 请求）
   - 是否存在重复调用（同一数据被请求了多次）
   - 每次调用的 timeout 设置
   - stdout/stderr 的输出行为（是否有中间进度标记）

3. **检查 stdout/stderr 输出行为**：这是工具可观测性的核心问题。如果脚本从启动到结束只有一次输出（最终结果），Agent 无法区分"正在运行"和"挂了"。检查：
   - 脚本是否使用 `print()` / `typer.echo()` / `sys.stderr.write()` 输出中间进度
   - Python 在非 TTY 环境（Docker 容器）中默认块缓冲，是否影响输出可见性
   - Agent 是否自行添加了 `| tail` / `| head` pipe（会缓冲输出）

4. **否定假设的系统性方法**：
   - 假设"pipe 导致失败" -> 检查通过 case 是否也有 pipe
   - 假设"大文件导致慢" -> 检查通过 case 的文件大小
   - 假设"目录导致慢" -> 检查通过 case 是否也传了目录
   - 假设"飞书 API 限流" -> 画执行时间线，看失败 case 是否连续出现

5. **改进方向落到产品代码**：
   - 核心修复：增加 stderr 进度输出（`[stage_name]` 前缀标记）
   - 配合修复：消除重复的 API 调用
   - 辅助修复：在 SKILL.md 中告知 Agent 脚本执行时间和 pipe 禁令

### 案例：Rollup_Core_20260630 eleme_delivery_settlement / jingdong_delivery_revenue

Agent 正确走了 list -> validate 路径，但 `run_recog_rollup.py --validate` 执行超过 6 分钟无任何输出。根因是脚本零进度输出（代码级确认：`formatters.py` 只在最后输出一次 JSON）加上 Windows Docker 环境下飞书 API 的间歇性网络延迟叠加。通过对比否定了 pipe 假设（alipay 用了同样 pipe 在 22 秒内完成）和限流假设（失败 case 不是连续执行的）。

---

## 模式 C：源文件/配置给错（Agent 行为正确）

### 典型表现

- outputs 为空
- Agent 最终回复明确说"已阻断在 validate 阶段"或类似表述
- grader 判 fail（因为产物为空）

### 分析要点

1. **结合 suite 的评测目的判断**：先搞清楚这个评测集想测什么。如果评测目的是"在完美条件下 Agent 能否顺利完成任务"，那源文件不符合条件属于 case 数据问题，不是 Agent 问题。

2. **验证 Agent 的阻断是否正确**：读 trace，看 Agent 阻断的原因是否与 skill 规则一致。如果 Agent 正确识别了源文件不符合要求并按规则阻断，这是正确行为。

3. **区分三类情况**：
   - Agent 正确阻断 + case 数据给错 -> 修正 case 数据
   - Agent 正确阻断 + grader 设计不支持"合规阻断" -> 评估是否需要新增 grader 维度
   - Agent 错误阻断（源文件实际符合规则但 Agent 判定不符合）-> 这是 Agent/skill 的问题，需要进一步分析

4. **改进方向**：
   - 如果是 case 数据问题：修正 input 文件
   - 如果是 grader 设计问题：评估是否需要新增 grader 或修改 case 的 expected outcome
   - 不要把 Agent 的正确阻断当作 bug 来修

### 案例：Rollup_Core_20260630 meituan_voucher_settlement

Agent 正确识别到源文件缺少规则要求的 `收益明细` sheet，在 validate 阶段按规则阻断。评测集的目的是验证"完美条件下 Agent 能否顺利完成"，因此应修正 case 的 input 文件。

---

## 分析中的常见陷阱

### 1. 不看产品代码就下结论

假设"脚本执行慢是因为大文件"，但不去读脚本的实现确认它到底做了什么。正确的做法：先读代码，确认调用链，再判断瓶颈在哪。

### 2. 只验证支持假设的证据，不找否定证据

假设"pipe 导致失败"，找到了失败 case 有 pipe 就下结论。正确做法：也检查通过 case 是否有 pipe——如果有，假设被否定。

### 3. 把 Agent 的正确行为当作 bug

Agent 按规则阻断了不符合要求的源文件，但 grader 判 fail。不要急着修改 Agent 行为或新增 grader，先结合评测目的判断这是不是 case 数据的问题。

### 4. 泛泛的改进方向

"优化脚本性能"不是改进方向。"在 `validate_stage.py` 的 `run()` 方法中添加 stderr 进度输出，使用 `[validate]` 前缀标记每个步骤"才是。改进方向必须具体到代码位置。

### 5. 过早停止分析

看到"脚本卡死"就停了，不去深挖为什么卡、卡在哪里、是确定性问题还是间歇性问题。正确做法：一直挖到底，直到能给出具体的、有代码根据的改进方向。
