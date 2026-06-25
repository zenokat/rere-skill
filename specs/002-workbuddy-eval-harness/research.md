# Research: 收入确认 WorkBuddy 自动化评测底座

## Decision 1: 首版自动化入口采用 CodeBuddy CLI 无头模式，而不是 WorkBuddy GUI

- **Decision**: 首版 runner 以 CodeBuddy CLI 官方无头模式作为自动化执行面，WorkBuddy GUI 仅视为同核的人类使用壳层。
- **Rationale**: Workbuddy官方文档明确给出了 `-p/--print`、`--resume`、`--continue`、`--output-format` 等自动化能力；这比围绕 GUI 做脆弱编排更稳定，也更适合后续 Agent 自主发起评测。
- **Alternatives considered**:
  - 直接自动操作 WorkBuddy GUI：更贴近终端用户界面，但自动化脆弱、状态不稳定、可复用性差。
  - 完全脱离官方 CLI，自己伪造 skill 调用：会偏离真实运行环境，评测价值不足。

## Decision 2: 标准结果使用 `json`，深度留痕补充 `stream-json`

- **Decision**: 每个 case 的标准机器结果以 CLI `--output-format json` 为主；需要更细过程留痕时，再补充 `stream-json` transcript。
- **Rationale**: `json` 结果更适合作为稳定主契约，方便批量汇总、评分和基线比较；`stream-json` 更适合复盘完整对话过程，但不应成为每次运行都必须依赖的主结果。
- **Alternatives considered**:
  - 只保留纯文本输出：人工可读，但机器解析与回归比较成本太高。
  - 默认所有运行都全量保存 `stream-json`：证据更丰富，但首版成本更高，且会放大存储与隐私管理压力。

## Decision 3: 每条 trial 默认新开会话，但保留 `session_id` 以便复盘与续跑

- **Decision**: 批量评测时，每条 case 默认使用独立新会话执行；同时保存 `session_id`，支持后续 `--resume` 或 `--continue` 做人工复查或补充问答。
- **Rationale**: Anthropic 的 eval 方法强调 trial 间要避免状态泄漏；独立会话更利于保证可比性。与此同时，保存会话 ID 又能降低复盘成本。
- **Alternatives considered**:
  - 一整批 case 共用一个长会话：容易互相污染上下文，导致分数失真。
  - 完全丢弃会话身份：可以减少管理复杂度，但复盘和人工追查成本过高。

## Decision 4: 将证据拆成“最小必备层”和“可选深度层”

- **Decision**: 首版把证据分为两层。最小必备层包含运行元数据、stdout/stderr、最终 JSON、`session_id` 和证据完整性标记；可选深度层再包含 transcript、OTel trace、更多工具细节。
- **Rationale**: 腾讯那篇实践强调 trace 是基础设施，但同时也提醒评测要先有闭环、再逐步完善。先锁定“每次一定能落下主结果”，再让深度留痕增量接入，风险更可控。
- **Alternatives considered**:
  - 一开始要求所有深度证据必须到齐：容易被环境能力或隐私顾虑卡死首版推进。
  - 只保留最终 pass/fail：复盘信号太弱，不满足本 feature 目标。

## Decision 5: OTel traces 作为可选证据通道，默认不开启敏感内容记录

- **Decision**: 采用 CodeBuddy CLI 官方 OTel trace 能力作为可选证据通道；默认只把 trace 当作附加观察面，prompt 内容、工具参数和工具全文都保持 opt-in。
- **Rationale**: 官方监控文档说明 traces 已对齐 Claude Code 约定，但 metrics/logs 还不在当前范围。对首版而言，把 OTel 当“增强可观测性”比当“唯一主证据”更稳妥。
- **Alternatives considered**:
  - 不接 OTel，只保留本地文件：实现更简单，但后续无法平滑接入企业观测平台。
  - 默认打开所有敏感内容上报：虽然方便排查，但不符合最小披露原则。

## Decision 6: 评分器采用 `确定性 > Rubric > 人工` 的三层结构

- **Decision**: 首版评分以确定性评分器为主，Rubric 评分器为辅，人工评分器只做校准、争议复核与基线晋升。
- **Rationale**: 这同时呼应了腾讯实践和 Anthropic 方法论。能用代码判断的，不交给模型；模型用于补足软指标；人工则用于校准和兜底。
- **Alternatives considered**:
  - 全部人工打分：最可靠，但无法支持高频回归。
  - 全部交给 LLM Judge：成本更低，但稳定性和可解释性不足。

## Decision 7: 评分看结果与关键守卫，不机械绑定完整路径

- **Decision**: 评分重点放在最终结论、边界遵守、关键动作和失败归因，不把“完整工具调用顺序必须一模一样”当作首版强约束。
- **Rationale**: Anthropic 特别提醒不要把评测写成“路径锁死”。只要结果正确、关键守卫满足，就不该因合理路径差异而扣分。
- **Alternatives considered**:
  - 严格按固定工具序列评分：实现简单，但会惩罚合理变化。
  - 完全不看过程信号：又会丢失对环境失败、越界行为和关键动作缺失的判断能力。

## Decision 8: “正确止步”必须成为一类独立通过类型

- **Decision**: case 预期类型中显式支持 `correct_stop`，并在评分与聚合报告中单列展示。
- **Rationale**: 本 feature 的多个需求都强调阻断、澄清和拒绝越界执行本身可以是正确结果。如果不把它做成一等公民，评测会天然鼓励“什么都继续做”的错误行为。
- **Alternatives considered**:
  - 统一把未继续执行视为失败：会直接违背边界遵守需求。
  - 只靠人工解释“这次停下也算对”：会让自动评分失去价值。

## Decision 9: 基线快照保存“可比较上下文”，而不只是保存一个总分

- **Decision**: baseline 需要同时保存 case 身份、评分结果、失败归因、证据引用、skill/prompt/environment 指纹和 scorer 版本。
- **Rationale**: 同一组 case 在不同版本重跑时，只有把“为什么这次和上次能比”一起存下来，回归结果才可信。否则一旦 prompt、skill 包或环境变了，就只剩表面分数，没有解释能力。
- **Alternatives considered**:
  - 只保存总分或通过率：太粗，无法定位回归位置。
  - 每次都重新人工比对原始日志：成本太高，无法长期维护。

## Decision 10: capability eval 通过后毕业为 regression suite

- **Decision**: 首版先把代表性真实 case 当 capability eval 跑通；当这些 case 稳定通过后，再晋升为固定 regression suite。
- **Rationale**: Anthropic 的“毕业机制”和腾讯的“通过后纳入回归”是一致的。这样既能用评测驱动迭代，又能让早期投入逐步沉淀成长期资产。
- **Alternatives considered**:
  - 一开始就按完整回归治理：前期成本过高，不利于快速起步。
  - 每轮都只做一次性人工验证：资产无法复利。

## Decision 11: 首版默认评测范围仅覆盖 rollup 的 validate / preview

- **Decision**: 首版默认 case 只覆盖 `list_recog_items`、`run_recog_rollup --validate`、`run_recog_rollup --preview` 以及正确止步/环境失败场景；upload 仅在 case 明确声明 `safe_environment` 时纳入。
- **Rationale**: 现有收入确认 skill 参考文档已经明确：首版评测基线优先覆盖 validate 和 preview，upload 需要受控环境和显式授权。
- **Alternatives considered**:
  - 默认把 upload 也纳入主评测：风险更高，也会增加环境噪声。
  - 只评 list / validate，不评 preview：无法覆盖真实业务核心链路。
