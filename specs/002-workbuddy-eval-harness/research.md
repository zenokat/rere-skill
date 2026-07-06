# Research: WorkBuddy / CodeBuddy Eval Harness

## R1: 评测输入形式

- **Decision**: 评测集由 suite YAML + case 文件夹组成。suite YAML 包含 `suite_id`、`graders`、`cases`，并允许 suite 级 `model` 与共享 `input`/`skills`；每条 case 的任务、skill 和输入文件放在 case 文件夹中。
- **Rationale**: 评测者需要清楚控制 Agent 能看到什么。把 prompt、skill 路径和 input 都塞进 YAML 会让 case 难以审查，也容易泄露开发仓库路径。
- **Implication**: 旧的 `skill.path`、`skill.name`、`cases[].prompt` 从用户契约中移除。

## R2: 环境隔离

- **Decision**: 每条 case 必须在一次性 sandbox workspace 中运行。默认要求 Docker/OCI 强隔离：本地仍 materialize 一次性 sandbox workspace，但 CodeBuddy 在容器内执行，容器只挂载当前 case workspace。
- **Rationale**: 用户当前目标是稳定阻止评测 Agent 读写原始代码仓库和本机其它目录。真实冒烟已证明 CodeBuddy 权限提示、Bash/PowerShell approval 和非交互模式会影响 case 成败，因此隔离边界应前移到 Docker，由容器挂载范围决定 Agent 可见文件。
- **Implication**: harness 不允许在隔离失败时退回宿主机裸跑；如果 Docker、容器内 CodeBuddy 登录态或必要运行时不可用，case 应记为环境失败。CodeBuddy 权限事件会保留在原始 `session.jsonl` 中，但不再承担主要安全边界。

## R3: WorkBuddy skill 加载形态

- **Decision**: case 源目录中使用 `skills/<skill-name>/`，运行时 materialize 到 sandbox 的 `.workbuddy/skills/<skill-name>/`。
- **Observed Source**: 本地 WorkBuddy session 中，Skill 工具返回的 skill 基目录类似 `C:\ProgramData\WorkBuddy\users\<user_id>\.workbuddy\skills\revenue-recognition`，并从该目录加载 `SKILL.md`。
- **Rationale**: 评测者维护 case 时需要简单直观的结构；运行时则应尽量接近 WorkBuddy 生产路径。
- **Implication**: 实现时不把 skill 放在 workspace 根目录。至少要保证 `.workbuddy/skills/<skill-name>/SKILL.md` 存在。

## R4: WorkBuddy 启动上下文

- **Decision**: harness 应生成 WorkBuddy 风格的 `system-reminder` 用户上下文，而不是伪造额外 `role=system`。
- **Observed Source**: 本地 WorkBuddy session 中未观察到独立 `role=system` 消息。第一条 `role=user` 消息包含 `<system-reminder ...>` 块，其中包括 `user_info`、`identity_context`、`product_identity`、`project_context`、`additional_data`、`memory_and_skills_reminder`、`manually_attached_skills` 和 `user_query`。
- **Rationale**: CodeBuddy CLI 可能有自己的内置 system prompt。再注入一套 system prompt 容易产生优先级和语义冲突；把 WorkBuddy 上下文作为普通输入更接近已观察 session，也更可控。
- **Implication**: 首版注入默认 identity 模板、全部 disconnected 的 connector status、sandbox project context 和原始用户请求。不注入真实个人记忆或用户主目录内容。

## R5: `manually_attached_skills` 判定

- **Decision**: 不新增 case 配置项控制手动挂载 skill。harness 根据 `instruction.md` 中是否出现 `/<skill-name>` 判断。
- **Rationale**: 真实 WorkBuddy 交互中，用户用斜杠指令调用 skill。把这个动作写在用户请求里，比额外配置更贴近真实交互，也减少评测执行者要维护的字段。
- **Implication**: 例如 `instruction.md` 包含 `/revenue-recognition` 时，启动上下文注入 `manually_attached_skills`；没有斜杠指令时，skill 仍在 workspace 中，但不声明为本轮手动挂载。

## R6: `instruction.md` 的运行时位置

- **Decision**: `instruction.md` 是 case 源材料，运行时作为 `<user_query>` 注入首条用户消息，不复制进 CodeBuddy workspace。
- **Rationale**: 真实 WorkBuddy 中用户请求是消息，不是 workspace 文件。把 instruction 同时作为文件和消息会制造额外上下文，影响评测真实性。
- **Implication**: sandbox 中不应出现 `instruction.md`。如果 Agent 需要复盘任务，应从首条消息中读取。

## R7: Skill 脚本运行边界

- **Decision**: skill 附带脚本应放在 skill 自己的 `scripts/` 下，并由 `SKILL.md` 或 `references/` 说明运行前提。harness 不生成 `.bin/` 或 `.runtime/`。
- **Rationale**: 根据 agent skill 的脚本使用习惯，脚本应是 skill 产品包的一部分，能通过相对路径、`--help`、非交互参数和结构化输出被 Agent 使用。由 harness 临时注入仓库 CLI wrapper 会把评测变成“依赖本仓库的特殊环境”，不再是可搬走的 case。
- **Implication**: 如果某个 skill 的 `scripts/` 离开原始仓库后无法运行，应判为 skill 打包或环境失败，而不是由 harness 补一套隐藏运行时。

## R8: 结果文件最小化

- **Decision**: 每次运行只暴露 `batch.json`、`cases/<case_id>/result.json`、`cases/<case_id>/session.jsonl` 和 `cases/<case_id>/outputs/`。
- **Rationale**: 评测者真正要看的是总体运行情况、单 case 指标、Agent 轨迹和业务产物。其它报告文件会增加阅读成本和口径漂移风险。
- **Implication**: Markdown 报告、artifact index、agent-result、final、scorecard、baseline 和 diff 都不进入首版结果包。

## R9: Grader 契约

- **Decision**: suite YAML 必须声明本批 graders。grader 只输出 0/1 二元判断，扩展后仍写回 `result.json.graders[]`。
- **Rationale**: 评分口径是评测集的一部分，不能只藏在代码默认值里。二元输出让 `verdict` 简单稳定：全 1 为 pass，有 0 为 fail。
- **Implication**: 当前堂食收入 case 使用 `preview_file_exists`，该 grader 检查 `outputs/` 中是否存在 preview 文件。

## R10: Session 来源

- **Decision**: `session.jsonl` 不由 harness 猜测生成，也不再归一化；它是 CodeBuddy / WorkBuddy 原始 session JSONL 的原样副本。
- **Observed Source**: CodeBuddy / WorkBuddy session 中已观察到 `message`、`function_call`、`function_call_result`、`reasoning` 和 `file-history-snapshot`。
- **Rationale**: 当前最重要的是保留真实证据，避免归一化时丢字段、改事件名或错误屏蔽路径。原始 session 虽然更大、更敏感，但它是复盘 Agent 真实行为的唯一事实源。
- **Implication**: 原始 `reasoning`、`providerData`、工具参数、工具输出和绝对路径都会保留。结果包必须按敏感证据管理；如果 session JSONL 缺失，不生成假轨迹，只在 `result.json.evidence.missing` 记录 `codebuddy_session_jsonl`。

## R11: 外部写入边界

- **Decision**: 首版普通 case 不评测真实 upload 或其它外部写入。
- **Rationale**: 隔离环境优先验证 Agent 能否读 skill、消费 input、生成 output 和遵守边界。外部写入需要额外凭证、审计和回滚方案。
- **Implication**: 如果 instruction 要求 upload，harness 应阻断或判为不支持的 case，而不是放宽隔离。
