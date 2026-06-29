# Feature Specification: WorkBuddy / CodeBuddy Eval Harness

**Feature Branch**: `002-workbuddy-eval-harness`
**Created**: 2026-06-25
**Updated**: 2026-06-28
**Status**: Implementation alignment in progress

## User Need

评测执行者需要安全、真实地运行 WorkBuddy / CodeBuddy eval case，并拿到足够判断结果的最小证据：

- 整批是否跑完。
- 每条 case 是否完成。
- Agent 最终回答是什么。
- grader 为什么给 `1` 或 `0`。
- Agent 可见轨迹能否复盘。
- case 业务产物是否真的生成。

当前目标不是给 Agent 一个完整宿主机环境，而是给它一个只属于本 case 的 workspace。CodeBuddy 不应读写原始代码仓库或用户主目录；业务产物只能写入 sandbox 的 `output/`，再由 harness 复制到结果目录。

## Scope

首版必须支持：

- 用 suite YAML 定义 `suite_id`、case 列表和 graders。
- 用 case 文件夹定义 `instruction.md`、`skills/` 和 `input/`。
- 每条 case 在公开结果包之外的一次性 sandbox workspace 中运行。
- sandbox 内 skill 加载结构尽量还原 WorkBuddy 的 `.workbuddy/skills/<skill-name>/`。
- 启动上下文尽量还原 WorkBuddy session 中观察到的 `system-reminder` 形态。
- 基于 CodeBuddy CLI 无头模式运行真实模型。
- 默认使用 Docker/OCI 容器作为强隔离执行边界；CodeBuddy 权限参数只作为辅助护栏和取证信号。
- 自动评分，grader 只返回 `0` 或 `1`。
- 生成 `batch.json`、`cases/<case_id>/result.json`、`cases/<case_id>/session.jsonl` 和 `cases/<case_id>/outputs/`。

首版不支持：

- 仅依赖 CodeBuddy 权限体系作为主要隔离边界。
- baseline 保存与比较。
- Markdown 报告。
- 多套 profile。
- fake runner 作为评测执行者路径。
- upload 或真实外部写入评测。
- 直接在原始代码仓库 cwd 中裸跑 Agent。
- 在 workspace 中生成 `.bin/`、`.runtime/`、`EVAL_CASE_CONTEXT.md` 等隐藏辅助运行时。

## User Stories

### US1: 组织可搬走的 case 文件夹

作为评测执行者，我希望每条 case 是一个文件夹，里面包含任务说明、skill 和输入文件，这样 case 不依赖原始代码仓库路径，也更容易审查 Agent 到底能看到什么。

**Independent Test**: 给定包含 `instruction.md`、`skills/` 和 `input/` 的 case 文件夹，harness 能把 `input/` 和 `skills/` materialize 到 sandbox workspace；`instruction.md` 不作为文件复制进 workspace，而是进入首条用户消息。

### US2: 控制本批评分器

作为评测执行者，我希望在 suite YAML 中声明本批评测使用哪些 grader，这样评分口径是评测集契约的一部分，而不是藏在代码默认值里。

**Independent Test**: 给定 `graders: [preview_file_exists]`，harness 只运行该 grader，并把结果写入 `result.json.graders[]`。

### US3: 在受控 workspace 中运行真实 CodeBuddy

作为评测执行者，我希望每条 case 在一次性 sandbox workspace 里运行，这样 Agent 不能读写代码仓库或用户主目录，也不能把产物写到不受控位置。

**Independent Test**: 运行单条 case 时，CodeBuddy 的 cwd 位于 sandbox；sandbox 只包含 `input/`、`output/` 和 `.workbuddy/skills/<skill-name>/`；不包含 `instruction.md`、`EVAL_CASE_CONTEXT.md`、`.bin/` 或 `.runtime/`；运行结束后 sandbox 被销毁。

### US4: 尽量还原 WorkBuddy 上下文

作为评测执行者，我希望评测环境尽量接近 WorkBuddy 生产环境，这样 CodeBuddy CLI 评测结果不会因为上下文差异而失真。

**Independent Test**: harness 生成的首条用户消息包含 WorkBuddy 风格的 `system-reminder` 上下文、默认 identity context、product identity、project context、additional data、connector status 和用户请求；如果 `instruction.md` 中出现 `/<skill-name>`，则注入 `manually_attached_skills`；同时不覆盖 CodeBuddy CLI 自带 system prompt。

### US5: 读取最小结果

作为评测执行者，我希望只看 `batch.json`、`result.json`、`session.jsonl` 和 `outputs/`，这样可以快速判断总体结果、单 case 评分、Agent 原始行为轨迹和业务产物。

**Independent Test**: 运行完成后，批次根目录生成 `batch.json`，每条 case 目录生成 `result.json`、`session.jsonl` 和 `outputs/`，且不生成 Markdown、归一化轨迹或重复 JSON 视图。

## Functional Requirements

- **FR-001**: 系统 MUST 支持从 suite YAML 读取 `suite_id`、`graders` 和 `cases`。
- **FR-002**: `cases` MUST 是 case 文件夹名列表。
- **FR-003**: 每条 case 文件夹 MUST 包含 `instruction.md`、`skills/` 和 `input/`。
- **FR-004**: 系统 MUST 不要求评测者在 case 中预设期望结果、关键词或分类。
- **FR-005**: 系统 MUST 为每条 case 创建一次性 sandbox workspace。
- **FR-006**: sandbox MUST 不挂载原始代码仓库和用户主目录。
- **FR-007**: sandbox MUST 只包含 `input/`、`output/` 和 `.workbuddy/skills/<skill-name>/` 这类 case workspace 内容。
- **FR-008**: sandbox MUST 不包含 `instruction.md`、`EVAL_CASE_CONTEXT.md`、`.bin/` 或 `.runtime/`。
- **FR-009**: 系统 MUST 按 WorkBuddy 的 skill 加载形态放置 skill；至少保证 `SKILL.md`、`references/` 和 `scripts/` 在 `.workbuddy/skills/<skill-name>/` 下可读。
- **FR-010**: 系统 MUST 生成 WorkBuddy 风格启动上下文，并把 `instruction.md` 原文作为 `<user_query>`。
- **FR-011**: 系统 MUST 不把 WorkBuddy 上下文注入为第二套 system prompt；CodeBuddy CLI 自带 system prompt 不应被覆盖。
- **FR-012**: 系统 MUST 在启动上下文中注入默认 identity context、product identity、project context、additional data 和全部 disconnected 的 connector status。
- **FR-013**: 系统 MUST 根据 `instruction.md` 中的 `/<skill-name>` 斜杠指令决定是否注入 `manually_attached_skills`。
- **FR-014**: 系统 MUST 使用 CodeBuddy CLI 无头模式运行真实评测。
- **FR-015**: 系统 MUST 默认通过 Docker/OCI 容器运行每条 case；容器是主要安全边界。
- **FR-016**: 系统 MUST 只把当前 case sandbox 挂载进容器，且不得挂载原始代码仓库或用户主目录；如果 Docker 或容器运行能力不可用，case MUST 记为环境失败。
- **FR-017**: 系统 MUST 回收模型最终回答；当 stdout 为空但 session JSONL 有 assistant 响应时，必须使用 session 响应补齐。
- **FR-018**: 系统 MUST 为每条成功捕获到 session 的 case 生成 `session.jsonl`，内容是 CodeBuddy / WorkBuddy 写出的原始 session JSONL 的原样副本。
- **FR-019**: 系统 MUST 为每条 case 生成 `result.json`。
- **FR-020**: 系统 MUST 为每条 case 保留 `outputs/`，并从 sandbox 的 `output/` 复制产物。
- **FR-021**: 系统 MUST 为每个批次生成 `batch.json`。
- **FR-022**: `batch.json` MUST 只包含总 case 数、完成数、通过数、失败数、批次状态和批次指标，不包含 case 数组。
- **FR-023**: `result.json` MUST 包含运行状态、最终回答、二元分数、grader 输出、耗时、token、成本、session 路径、outputs 路径和证据缺口。
- **FR-024**: token 和成本无法获取时，系统 MUST 写入 `null`，不得删除字段。
- **FR-025**: 系统 MUST 支持 suite YAML 中声明的 `preview_file_exists` grader，检查本 case 的 `outputs/` 中是否存在 preview 文件。
- **FR-026**: 系统 MUST 允许新增代码 grader 或模型 grader；grader 输出必须是 `score: 1` 或 `score: 0`，并写回 `result.json.graders[]`。
- **FR-027**: 系统 MUST 按固定规则生成 `verdict`：所有 grader 都为 `1` 时为 `pass`，任一 grader 为 `0` 时为 `fail`。
- **FR-028**: `session.jsonl` MUST 保留 CodeBuddy 原始事件与字段，包括 `message`、`function_call`、`function_call_result`、`reasoning`、`providerData`、`sessionId`、时间戳、工具参数和工具输出；不得归一化、重命名、屏蔽路径或丢弃字段。
- **FR-029**: 如果无法取得 CodeBuddy 原始 session JSONL，系统 MUST 不生成假的轨迹文件，并在 `result.json.evidence.missing` 记录 `codebuddy_session_jsonl`。
- **FR-030**: 系统 MUST 不生成 `summary.md`、`evidence.md`、`diff.md`、`agent-result.json`、`artifact-index.json`、`baseline.json`、`compare/diff.json`、`stdout.txt`、`stderr.txt`、`final.json`、`scorecard.json`。
- **FR-031**: 系统 MUST 把真实 upload 和外部写入排除在首版普通评测之外。
- **FR-032**: skill 随包脚本 MUST 位于 skill 自己的 `scripts/` 目录，并通过 skill 文档说明运行前提；harness 不得用 `.bin/` 或 `.runtime/` 临时补齐原始仓库运行时。
- **FR-033**: Windows 上 CodeBuddy 原始 session 路径可能超过 260 字符；系统 MUST 支持读取这类长路径，同时在结果包中只暴露普通相对路径 `session.jsonl`。
- **FR-034**: `session.jsonl` 是原始敏感证据，可能包含环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`；文档和结果契约 MUST 明确其不适合公开分享。

## Key Entities

- **EvalSuite**: 一个 suite YAML 和一组 case 文件夹。
- **EvalCaseFolder**: 单条 case 的源材料目录，包含 `instruction.md`、`skills/` 和 `input/`。
- **CaseSandbox**: 单条 case 的一次性 sandbox workspace。
- **WorkBuddyStartupContext**: 作为首条用户消息注入的 `system-reminder` 和 `<user_query>`。
- **BatchResult**: 整批评测结果，对应 `batch.json`。
- **CaseResult**: 单 case 结果，对应 `result.json`。
- **SessionRecord**: CodeBuddy / WorkBuddy 原始 session JSONL 的逐行事件，对应 `session.jsonl` 的一行。
- **CaseOutputs**: 单 case 从 sandbox `output/` 复制出来的业务产物目录。
- **GraderResult**: 评分器输出，写入 `result.json.graders[]`。

## Success Criteria

- **SC-001**: 评测者能按 README 的 suite + case 文件夹结构跑起真实 CodeBuddy 单 case。
- **SC-002**: 每条 case 在一次性 sandbox workspace 中运行，运行结束后 sandbox 被销毁。
- **SC-003**: Agent 不能直接读写原始代码仓库或用户主目录。
- **SC-004**: sandbox 内 skill 能按 WorkBuddy 风格路径被发现或被明确路径加载。
- **SC-005**: `batch.json` 能回答总数、完成数、通过数、失败数和整体状态。
- **SC-006**: `result.json` 能回答模型最终回答、0/1 grader 结果、耗时、token、成本和证据缺口。
- **SC-007**: `session.jsonl` 能复盘 Agent 原始行为轨迹，并保留 CodeBuddy 原始字段。
- **SC-008**: `outputs/` 保存 case 业务产物。
- **SC-009**: 真实 CodeBuddy CLI 堂食收入 case 冒烟测试在满足 Docker、CodeBuddy 登录态和 skill 运行前提后通过。
