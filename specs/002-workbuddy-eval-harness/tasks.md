# Tasks: 收入确认 WorkBuddy 自动化评测底座

**Input**: Design documents from `/specs/002-workbuddy-eval-harness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: `spec.md` 与 `plan.md` 已明确要求 contract、unit、integration、smoke 验证，因此本任务清单保留测试任务，并按“先写测试、后做实现”的顺序组织。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可以并行执行
- **[Story]**: 任务归属的用户故事，例如 `US1`、`US2`
- 每条任务都必须包含明确文件路径

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 先把评测底座的目录骨架、测试骨架和示例目录搭起来，避免后面实现时边写边补基础结构。

- [ ] T001 创建评测底座包结构文件 `src/evals/__init__.py`、`src/evals/cases/__init__.py`、`src/evals/runners/__init__.py`、`src/evals/evidence/__init__.py`、`src/evals/graders/__init__.py`、`src/evals/baselines/__init__.py`、`src/evals/reports/__init__.py`、`src/evals/profiles/__init__.py`、`src/evals/shared/__init__.py` 和 `src/integrations/codebuddy_cli/__init__.py`
- [ ] T002 创建评测底座测试包结构文件 `tests/contract/eval_harness/__init__.py`、`tests/integration/eval_harness/__init__.py` 和 `tests/unit/eval_harness/__init__.py`
- [ ] T003 [P] 创建示例 suite 骨架文件 `specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml` 和 `specs/002-workbuddy-eval-harness/examples/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 完成所有用户故事都会依赖的共享模型、装配、隔离和安全基座。

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] 实现共享评测枚举与标识生成辅助代码 `src/evals/shared/types.py` 和 `src/evals/shared/ids.py`
- [ ] T005 [P] 实现 case manifest 模型与加载器 `src/evals/cases/manifest_models.py` 和 `src/evals/cases/manifest_loader.py`
- [ ] T006 [P] 实现默认 settings profile 模型与加载器 `src/evals/profiles/models.py` 和 `src/evals/profiles/loader.py`
- [ ] T007 [P] 实现产物目录布局与单 case 工作区隔离能力 `src/evals/shared/output_layout.py` 和 `src/evals/shared/workspace_manager.py`
- [ ] T008 [P] 实现 CodeBuddy 命令构造与权限安全闸门 `src/integrations/codebuddy_cli/command_builder.py` 和 `src/integrations/codebuddy_cli/safety_guard.py`
- [ ] T009 [P] 实现共享 JSON 与 Markdown 序列化辅助代码 `src/evals/reports/serializers.py` 和 `src/evals/reports/markdown_helpers.py`
- [ ] T010 实现评测底座启动装配逻辑 `src/evals/bootstrap.py`

**Checkpoint**: 基础能力准备完成，可以进入用户故事实现。

---

## Phase 3: User Story 1 - 评测执行者能批量发起 WorkBuddy 评测 (Priority: P1) MVP

**Goal**: 让团队可以一次性发起一批稳定 case，并为每条 case 生成独立 trial、状态结论和批次摘要。

**Independent Test**: 准备至少 3 条代表性 case，执行一次 smoke batch，验证每条 case 都有独立 `run.json`、明确状态、稳定 `case_id` 和可追踪 `run_id`。

### Tests for User Story 1

- [ ] T011 [P] [US1] 编写 case manifest 契约测试 `tests/contract/eval_harness/test_case_manifest_contract.py`
- [ ] T012 [P] [US1] 编写批量运行 CLI 契约测试 `tests/contract/eval_harness/test_run_eval_batch_contract.py`
- [ ] T013 [P] [US1] 编写 3 条 case 的 smoke batch 集成测试 `tests/integration/eval_harness/test_rollup_smoke_batch.py`

### Implementation for User Story 1

- [ ] T014 [P] [US1] 实现 suite 仓储与 case 选择器 `src/evals/cases/suite_repository.py` 和 `src/evals/cases/case_selector.py`
- [ ] T015 [P] [US1] 实现无头 CodeBuddy 运行器适配层 `src/integrations/codebuddy_cli/headless_runner.py`
- [ ] T016 [US1] 实现单 case trial 生命周期编排 `src/evals/runners/batch_runner.py`
- [ ] T017 [US1] 实现结果分类与批次摘要聚合 `src/evals/runners/outcome_classifier.py` 和 `src/evals/reports/batch_summary.py`
- [ ] T018 [US1] 实现 `run_skill_eval_batch` CLI 入口并接入启动器 `src/cli/run_skill_eval_batch.py` 和 `.codex/scripts/rere.cmd`
- [ ] T019 [US1] 完善 smoke suite case 与示例元数据 `specs/002-workbuddy-eval-harness/examples/rollup-smoke.yaml` 和 `specs/002-workbuddy-eval-harness/examples/README.md`

**Checkpoint**: 用户故事 1 完成后，应能批量运行 smoke suite，并输出批次级和单 case 级结果记录。

---

## Phase 4: User Story 2 - 维护者能采集可复盘的评测证据 (Priority: P2)

**Goal**: 为每条 case 落下可复盘的证据包，覆盖最小必备证据、缺口标记、人工导航入口和可选深度留痕。

**Independent Test**: 针对成功、正确止步、环境失败三类 case，验证每条结果都能关联 `stdout`、`stderr`、`final.json`、`evidence.md`，并在证据缺失时明确标记影响。

### Tests for User Story 2

- [ ] T020 [P] [US2] 编写结果包契约测试 `tests/contract/eval_harness/test_result_bundle_contract.py`
- [ ] T021 [P] [US2] 编写证据采集集成测试 `tests/integration/eval_harness/test_evidence_collection.py`

### Implementation for User Story 2

- [ ] T022 [P] [US2] 实现证据包模型与完整性判断逻辑 `src/evals/evidence/models.py` 和 `src/evals/evidence/completeness.py`
- [ ] T023 [P] [US2] 实现 stdout、stderr、final JSON 与 transcript 采集逻辑 `src/evals/evidence/collector.py`
- [ ] T024 [P] [US2] 实现可选 OTel trace 采集与降级处理 `src/evals/evidence/telemetry.py`
- [ ] T025 [US2] 实现单 case 结果产物写入与证据导航页生成 `src/evals/reports/result_bundle_writer.py` 和 `src/evals/reports/evidence_markdown.py`
- [ ] T026 [US2] 将证据采集与证据影响标记接入运行主流程 `src/evals/runners/batch_runner.py` 和 `src/evals/reports/batch_summary.py`
- [ ] T027 [US2] 实现批次级产物索引，支持人和 Agent 快速定位 `src/evals/reports/artifact_index.py` 和 `src/evals/reports/batch_summary.py`

**Checkpoint**: 用户故事 2 完成后，应能产出既适合机器读取，也适合人工复盘的证据包。

---

## Phase 5: User Story 3 - 评测维护者能自动评分并沉淀基线 (Priority: P3)

**Goal**: 让每条 case 自动生成 `scorecard.json`，并支持把一轮结果保存成 baseline，随后与新一轮运行做结构化 diff。

**Independent Test**: 对同一套 case 连续运行两轮，验证系统能够输出每条 case 的评分、结论、`baseline.json` 与 `diff.json`/`diff.md`，并区分 `unchanged`、`fixed`、`regressed`、`not_comparable`。

### Tests for User Story 3

- [ ] T028 [P] [US3] 编写 baseline 快照契约测试 `tests/contract/eval_harness/test_baseline_snapshot_contract.py`
- [ ] T029 [P] [US3] 编写评分与 baseline diff 集成测试 `tests/integration/eval_harness/test_baseline_compare.py`

### Implementation for User Story 3

- [ ] T030 [P] [US3] 实现默认评分维度的确定性评分器 `src/evals/graders/deterministic_graders.py`
- [ ] T031 [P] [US3] 实现 rubric / 人工复核占位评分器与评分卡聚合逻辑 `src/evals/graders/rubric_graders.py` 和 `src/evals/graders/scorecard_service.py`
- [ ] T032 [US3] 实现 baseline 快照保存与晋升流程 `src/evals/baselines/snapshot_service.py`
- [ ] T033 [US3] 实现回归 diff 计算与对比报告生成 `src/evals/baselines/diff_service.py` 和 `src/evals/reports/compare_report_writer.py`
- [ ] T034 [US3] 实现 baseline 相关 CLI 入口并接入启动器 `src/cli/save_skill_eval_baseline.py`、`src/cli/compare_skill_eval_baseline.py` 和 `.codex/scripts/rere.cmd`
- [ ] T035 [US3] 将评分、`scorecard.json` 输出和 baseline 对比接入主流程 `src/evals/runners/batch_runner.py` 和 `src/evals/reports/result_bundle_writer.py`

**Checkpoint**: 用户故事 3 完成后，应能自动评分、保存 draft baseline，并将重跑结果与 baseline 做对比。

---

## Phase 6: User Story 4 - 人与 Agent 调用方都能扩展评测观测与评分 (Priority: P4)

**Goal**: 让默认配置之外的证据规则、评分维度与结果视图可以增量扩展，同时保持人和 Agent 共用同一套主契约。

**Independent Test**: 在不修改 case 结构和主 CLI 入口的前提下，新加一项扩展 settings profile，验证新证据规则或评分维度能进入结果输出，并保留兼容性说明。

### Tests for User Story 4

- [ ] T036 [P] [US4] 编写 settings profile 扩展集成测试 `tests/integration/eval_harness/test_settings_profile_extension.py`
- [ ] T037 [P] [US4] 编写注册表与双视图输出单元测试 `tests/unit/eval_harness/test_registry_and_views.py`

### Implementation for User Story 4

- [ ] T038 [P] [US4] 新增默认与扩展 settings profile 定义 `src/evals/profiles/default-minimal.yaml` 和 `src/evals/profiles/transcript-otel.yaml`
- [ ] T039 [P] [US4] 实现 profile 合并与兼容性说明处理逻辑 `src/evals/profiles/extension_loader.py` 和 `src/evals/profiles/merge.py`
- [ ] T040 [P] [US4] 实现带版本的评分器注册表与结果视图注册表 `src/evals/graders/registry.py` 和 `src/evals/reports/view_registry.py`
- [ ] T041 [US4] 实现面向人工的摘要视图与面向 Agent 的结构化结果视图 `src/evals/reports/summary_writer.py` 和 `src/evals/reports/agent_result_view.py`
- [ ] T042 [US4] 将 profile 驱动的证据、评分器和结果视图接入主流程 `src/evals/bootstrap.py`、`src/evals/runners/batch_runner.py` 和 `src/cli/run_skill_eval_batch.py`

**Checkpoint**: 用户故事 4 完成后，应能在不推翻主流程的前提下扩展证据、评分和结果视图。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 补齐文档、示例说明和端到端验证覆盖，确保团队能稳定复用这套评测底座。

- [ ] T043 [P] 更新功能使用说明与操作注意事项 `specs/002-workbuddy-eval-harness/README.md`
- [ ] T044 [P] 更新 quickstart 命令与预期输出说明 `specs/002-workbuddy-eval-harness/quickstart.md`
- [ ] T045 [P] 更新示例 suite 文档与排障说明 `specs/002-workbuddy-eval-harness/examples/README.md`
- [ ] T046 编写 quickstart smoke 验证测试 `tests/integration/eval_harness/test_quickstart_smoke.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: 无依赖，可立即开始
- **Phase 2: Foundational**: 依赖初始化完成，且会阻塞所有用户故事
- **Phase 3: US1**: 依赖基础能力完成，这是 MVP 主链路
- **Phase 4: US2**: 依赖 US1 的运行生命周期能力，因为证据采集建立在单 case 产物之上
- **Phase 5: US3**: 依赖 US1 与 US2，因为评分与 baseline 对比需要消费运行结果和证据包
- **Phase 6: US4**: 依赖 US2 与 US3，因为扩展能力要建立在稳定的证据、评分和结果契约之上
- **Phase 7: Polish**: 依赖所有目标用户故事完成

### User Story Dependencies

- **US1 (P1)**: 基础能力完成后即可开始，不依赖其他用户故事
- **US2 (P2)**: 复用 US1 的批量运行结果，在其上补充证据包装
- **US3 (P3)**: 复用 US1 的运行产物和 US2 的证据包来构建评分卡与基线
- **US4 (P4)**: 在 US2 与 US3 已稳定的主契约之上做可扩展能力，而不改主 CLI 形状

### Within Each User Story

- 先写测试，并确认测试在实现前失败
- 先实现 case / contract / profile 加载能力，再做主流程编排
- 先完成编排，再做产物落盘
- 先有稳定产物，再做评分与 baseline 对比
- 扩展加载能力要建立在默认契约已经稳定的前提上

### Parallel Opportunities

- 所有带 `[P]` 的初始化任务都可以并行执行
- 基础能力中的 `T004` 到 `T009` 可并行，因为它们修改的是不同模块
- 在 US1 中，`T011` 到 `T015` 可先并行，再由 `T016` 做主编排收口
- 在 US2 中，`T020` 到 `T024` 可并行，再由 `T025` 到 `T027` 做接线
- 在 US3 中，`T028` 到 `T031` 可并行，再由 `T032` 到 `T035` 做基线接线
- 在 US4 中，`T036` 到 `T040` 可并行，再由 `T042` 做最终集成

---

## Parallel Example: User Story 1

```text
T011 tests/contract/eval_harness/test_case_manifest_contract.py
T012 tests/contract/eval_harness/test_run_eval_batch_contract.py
T013 tests/integration/eval_harness/test_rollup_smoke_batch.py
T014 src/evals/cases/suite_repository.py + src/evals/cases/case_selector.py
T015 src/integrations/codebuddy_cli/headless_runner.py
```

## Parallel Example: User Story 2

```text
T020 tests/contract/eval_harness/test_result_bundle_contract.py
T021 tests/integration/eval_harness/test_evidence_collection.py
T022 src/evals/evidence/models.py + src/evals/evidence/completeness.py
T023 src/evals/evidence/collector.py
T024 src/evals/evidence/telemetry.py
```

## Parallel Example: User Story 3

```text
T028 tests/contract/eval_harness/test_baseline_snapshot_contract.py
T029 tests/integration/eval_harness/test_baseline_compare.py
T030 src/evals/graders/deterministic_graders.py
T031 src/evals/graders/rubric_graders.py + src/evals/graders/scorecard_service.py
```

## Parallel Example: User Story 4

```text
T036 tests/integration/eval_harness/test_settings_profile_extension.py
T037 tests/unit/eval_harness/test_registry_and_views.py
T038 src/evals/profiles/default-minimal.yaml + src/evals/profiles/transcript-otel.yaml
T039 src/evals/profiles/extension_loader.py + src/evals/profiles/merge.py
T040 src/evals/graders/registry.py + src/evals/reports/view_registry.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1：Setup
2. 完成 Phase 2：Foundational
3. 完成 Phase 3：User Story 1
4. 独立验证 3 条 case 的 smoke batch
5. 把这条链路作为后续阶段的第一条可运行评测闭环

### Incremental Delivery

1. 先交付 US1，证明“能稳定批量跑”
2. 再交付 US2，证明“失败也能复盘”
3. 再交付 US3，证明“结果能自动评分并做回归比较”
4. 再交付 US4，证明“后续扩展不需要推翻主流程”
5. 最后补齐文档和 quickstart 验证

### Team Strategy

1. 一位同学先集中完成 Phase 1 和 Phase 2 的共享契约与基础装配
2. 基础能力完成后，一位同学可主做 US1 编排，另一位同学可并行准备 US2 证据模块
3. 当 US2 的产物结构稳定后，US3 的评分与 baseline 工作可以和 US4 的扩展机制并行推进

---

## Notes

- `[P]` 表示任务可以并行，因为它修改的是不同文件，且不依赖未完成任务
- 用户故事标签和 `spec.md` 中的优先级一一对应，方便追踪
- 建议把 `US1` 作为 MVP 范围，因为它先建立第一条可执行评测闭环
- 主入口应持续保持为 `run_skill_eval_batch`，新增需求优先通过 profile 扩展，而不是额外分叉一套临时流程
