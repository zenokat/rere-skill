# Tasks: 隔离版 WorkBuddy / CodeBuddy Eval Harness

## Phase 1: 文档与契约对齐

- [X] T001 将 README 改为 suite + case 文件夹 + graders + 隔离运行契约。
- [X] T002 将 spec.md 改为隔离版需求。
- [X] T003 将 plan.md 改为一次性 workspace + Docker/OCI 容器边界方案。
- [X] T004 将 data-model.md 改为 EvalCaseFolder、CaseSandbox、CaseOutputs 和 SessionRecord。
- [X] T005 将 research.md 写入 WorkBuddy session 调研结论：上下文以 `system-reminder` 出现在第一条 user message 中，不是独立 system prompt。
- [X] T006 更新 contracts 和 quickstart。
- [X] T007 将 examples 改为 `revenue-recognition-real-smoke/suite.yaml` + case 文件夹结构。

## Phase 2: Manifest 与 case 加载

- [X] T008 更新 manifest 模型，只接受 `suite_id`、可选 `model`、`graders`、`cases[]`、可选 suite 级共享 `input`/`skills`。
- [X] T009 删除旧 `skill.name`、`skill.path`、`cases[].prompt` 用户契约。
- [X] T010 实现 case 文件夹校验：必须存在 `instruction.md`、`skills/`、`input/`。
- [X] T011 校验 `cases[]` 只能引用 suite 目录下的 case 文件夹，禁止路径穿越。
- [X] T012 更新示例解析测试，验证新目录结构可被加载。

## Phase 3: Sandbox 隔离

- [X] T013 新增 CaseSandbox 创建器，为每条 case 创建一次性运行目录。
- [X] T014 将 `input/` 和 `skills/` materialize 到 sandbox；`instruction.md` 只进入首条用户消息。
- [X] T015 将 `skills/<skill-name>/` materialize 到 `.workbuddy/skills/<skill-name>/`。
- [X] T016 在 sandbox 内创建 `output/`。
- [X] T017 确保 sandbox 不包含原始代码仓库路径和用户主目录挂载。
- [X] T018 运行结束后复制 `output/` 到 `cases/<case_id>/outputs/`。
- [X] T019 运行结束后销毁 sandbox；销毁失败时不影响已写出的证据，但必须在 `result.json.evidence.missing` 或状态中体现。

## Phase 4: CodeBuddy / WorkBuddy 上下文

- [X] T020 生成 WorkBuddy 风格 `system-reminder` 启动上下文。
- [X] T021 启动上下文包含 user_info、默认 identity_context、product_identity、project_context、additional_data、connector-status、按斜杠指令推断的 manually_attached_skills 和 `instruction.md` 用户请求。
- [X] T022 不注入第二套 `role=system`；不覆盖 CodeBuddy CLI 自带 system prompt。
- [X] T023 如果 Skill 工具无法加载 sandbox skill，prompt 中提供 `.workbuddy/skills/<skill-name>/SKILL.md` 降级路径。
- [X] T024 更新 session 采集契约，保留 CodeBuddy 原始事件和 `system-reminder` 可见 prompt。

## Phase 5: 隔离运行

- [X] T025 新增隔离 runner，使用一次性 sandbox 运行 CodeBuddy CLI。
- [X] T026 runner 只挂载当前 case sandbox 和必要的临时 CLI 配置。
- [X] T027 禁止挂载原始代码仓库和用户主目录。
- [X] T028 sandbox 或 CLI 环境缺失时，case 记为环境失败，不退回宿主机裸跑。
- [X] T029 回收 stdout、stderr、退出码、session JSONL、最终响应、模型和 token usage。

## Phase 6: 结果包

- [X] T030 将轨迹文件从归一化轨迹改为原始 `session.jsonl`。
- [X] T031 每条 case 输出 `result.json`、`session.jsonl` 和 `outputs/`。
- [X] T032 `batch.json` 保持不包含 case 数组。
- [X] T033 删除旧结果文件路径：`agent-result.json`、`artifact-index.json`、`final.json`、`scorecard.json`、Markdown 报告和 baseline 相关文件。
- [X] T034 更新 result schema，写入 `evidence.session_path` 和 `evidence.outputs_path`。

## Phase 7: Grader

- [X] T035 suite YAML 中声明 graders；运行时只执行声明的 graders。
- [X] T036 更新 `preview_file_exists`，只检查 `cases/<case_id>/outputs/`。
- [X] T037 grader 证据路径必须使用 `outputs/...` 相对路径。
- [X] T038 保持 `score` 二元化：`1` 或 `0`。
- [X] T039 保持 verdict 规则：全 1 为 pass，有 0 为 fail。

## Phase 8: 测试与验收

- [X] T040 更新单元测试，覆盖新 manifest、case 文件夹校验、sandbox materialize。
- [X] T041 更新契约测试，校验结果目录只包含 `batch.json`、`result.json`、`session.jsonl` 和 `outputs/`。
- [X] T042 更新 session 测试，覆盖 WorkBuddy `system-reminder` prompt 和 CodeBuddy 原始 session 复制。
- [X] T043 增加隔离测试，证明 Agent 运行环境不包含原始代码仓库和用户主目录。
- [X] T044 用真实 CodeBuddy CLI 跑隔离版堂食收入 case，确认得到模型响应、preview output、`preview_file_exists` grader 和原始 session。
- [X] T045 跑完整 pytest。

## 验收清单

- [X] README 中的最小示例能作为评测者入口。
- [X] 每条 case 都在一次性 sandbox 中运行，结束后销毁。
- [X] sandbox 内 skill 加载结构接近 WorkBuddy `.workbuddy/skills/<skill-name>/`。
- [X] 启动上下文还原 WorkBuddy `system-reminder` 形态，包含默认 identity/additional_data，并且不覆盖 CodeBuddy system prompt。
- [X] Agent 不能直接看到原始代码仓库和用户主目录。
- [X] `outputs/` 保存 case 业务产物。
- [X] `batch.json` 能看总数、完成数、通过数、失败数和整体状态，且不包含 case 数组。
- [X] `result.json` 能看运行状态、最终回答、0/1 grader 结果、耗时、token、成本和证据缺口。
- [X] `session.jsonl` 能复盘 Agent 原始行为轨迹，并保留 CodeBuddy 原始字段。
