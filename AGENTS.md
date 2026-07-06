<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/002-workbuddy-eval-harness/plan.md
<!-- SPECKIT END -->

## 仓库结构

本仓库有两个核心产物：**收入确认 skill**（可交付产品）和 **eval harness**（本地评测框架）。

```
eval-harness/         # eval harness 评测框架（本地开发工具，非交付产物）
├── cli/              # CLI 入口：run_skill_eval_batch
├── evals/            # 核心：bootstrap、runners、graders、sandbox、cases、reports、shared
└── integrations/     # CodeBuddy CLI 调用集成

skill/                # 可交付 skill 包（独立产品，不依赖本仓库运行）
└── revenue-recognition/
    ├── SKILL.md                  # skill 定义与使用说明
    ├── scripts/                  # skill 可执行脚本
    │   └── lib/                  # 业务逻辑源码
    └── references/               # skill 参考文档

evals/                # 评测数据与结果（非代码）
├── datasets/         # 评测集（suite.yaml + cases）
└── results/          # 评测运行输出（batch.json、result.json、session.jsonl）

tests/                # 测试
specs/                # 历史设计文档（001-revenue-rollup-cli、002-workbuddy-eval-harness）
```

两个产物的代码通过 PEP 420 命名空间包（`cli.`、`core.`、`models.`、`integrations.`）共存于同一条 `sys.path`，互不冲突。业务逻辑改 `skill/`，评测框架改 `eval-harness/`。

## 沙盒白名单命令审批申请
查阅 `sandbox-rules-allow-list.md`，把它当作和 `environment.md` 同级的必查文件，而不是"有空再看"的说明页。

### 什么时候必须处理
- 预判某条命令需要提权，且该操作低风险、可复用、后续大概率反复出现时；
- 某条命令已经因为沙盒或权限问题申请过一次，本线程又准备再次申请相同或高度相似命令时。

### 操作步骤
1. 先在 `sandbox-rules-allow-list.md` 查找是否已有可复用的相同命令前缀，或更长的公共命令前缀。
2. 如果已有且“已审批通过”为“是”，优先按该前缀组织命令，并在提权时复用对应 `prefix_rule`。
3. 如果没有合适记录，不要直接跳过；先把申请补写进 `sandbox-rules-allow-list.md` 的表格，再发起本次提权。
4. `sandbox-rules-allow-list.md` 只是申请与审计台账，真正生效入口仍是 `.codex/rules/*.rules`；未经审核，不得自行把命令加入规则文件。
5. 一次性、明显高风险、带破坏性或边界不清晰的命令，不进入白名单申请流程，继续按单次提权处理。
6. 当一次任务里既新增了环境记忆，又暴露出高频低风险提权场景时，同时更新 `environment.md` 和 `sandbox-rules-allow-list.md`，不要只更新前者。


## 环境记忆
查阅`environment.md`，了解开发过程中可能遇到的环境问题与处理经验，并将新遇到的任何多次尝试才成功的环境、工具交互经验写入，形成复利闭环

### 应该记什么
`environment.md` 只记录“跨多轮迭代、跨多个任务仍会反复遇到”的通用环境或工具交互经验，例如：
- shell / PowerShell / heredoc 的编码、转义、参数传递、代理继承问题；
- 本地运行环境、权限、白名单、网络、路径、临时目录等带来的稳定约束；
- 第三方平台或外部工具在“如何调用”层面的通用坑位与稳定做法。
### 不要记什么
以下内容不要记入 `environment.md`：
- 某个 `recog_id`、某份样本数据、某个目录、某张表、某次对账的项目特例；
- 已经被源码吸收并有测试覆盖的实现细节，除非仍需要保留一条“如何与环境交互”的操作约束；
- 业务规则、字段语义、聚合口径、上传键规则、预处理规则等项目逻辑。


### 命令调用方式

- 本仓库不需要把所有命令都包一层。像 `git`、`rg`、`pytest` 这类标准工具，优先直接调用；
- 对于需要仓库级 Python 运行环境初始化的自研 CLI，需统一走仓库启动器 `.\.codex\scripts\rere.cmd`。
- 举例：
  `.\.codex\scripts\rere.cmd list_recog_items`

  `.\.codex\scripts\rere.cmd run_recog_rollup --validate --recog_id <recog_id> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --preview --recog_id <recog_id> --period <period> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --upload --append|--upsert --recog_id <recog_id> --result_file <result_file>`

## git提交要求
- 使用中文
- 提交前先确认目标分支；与某个 feature/spec 强相关的改动，应提交到对应分支，不要误落到 `main`。
- 提交摘要保持方括号标签开头，用标签表达改动领域，例如 `[eval]`、`[skills]`、`[docs]`、`[fix]`、 `[某branch名]`。
- 单次提交横跨多个领域时，连续使用多个标签，例如 `[eval][docs] 新增评测集并更新 README`。
- 提交前只 stage 本次任务相关文件；保留用户已有的未提交改动，不要顺手带入无关删除、未跟踪评测集或临时产物。

### 标签语义约定
标签按含义分为三类，混用时注意区分：

- **领域标签**：描述改动涉及的项目子系统。
  - `[eval]` -- eval-harness 系统迭代 或 日常评测产物（评测集、评测结果）。
  - `[skills]` -- 项目推进过程中沉淀下来的 skill 产出物（SKILL.md、脚本、skill 目录结构），**不是**指项目业务对象（如收入确认 skill）。
  - `[context]` -- 上下文层面的调整（AGENTS.md、CLAUDE.md、environment.md、git 规范等），不涉及记录业务逻辑的speckit文档。
- **行为标签**：描述改动的性质。
  - `[fix]` -- 修复已有 bug。
  - `[chore]` -- 杂务（.gitignore、依赖更新、CI 配置等）。
  - `[refactor]` -- 重构，行为不变。
- **分支标签**：已淘汰不再使用，如 `[002-workbuddy-eval-harness]`。

## Build for Agents
项目中构建的skill、eval harness等均视Agent为主要用户（记得你自己就是Agent）
**但是**撰写SKILL.md，SPEC.md等文档时，仍然要保持第三方、客观、中性的视角
