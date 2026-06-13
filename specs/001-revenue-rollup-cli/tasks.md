---

description: "Task list for revenue recognition stage-one rollup implementation"
---

# Tasks: 收入确认阶段一汇总工具

**Input**: Design documents from `/specs/001-revenue-rollup-cli/`

**Prerequisites**: `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/`

**Tests**: 本功能明确依赖 CLI 契约验证、preview/baseline 对账验证、镜像表上传验证，因此包含契约测试、集成测试与必要单元测试任务。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. [US1], [US2], [US3])
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths below follow the structure defined in `plan.md`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立 Python CLI 项目的基础骨架与开发配置

- [X] T001 在 `pyproject.toml` 中创建 Python 项目元数据与依赖声明
- [X] T002 在 `src/cli/`、`src/core/`、`src/integrations/`、`src/models/`、`src/utils/`、`tests/contract/`、`tests/integration/`、`tests/unit/` 中创建源码与测试包骨架
- [X] T003 [P] 在 `pytest.ini` 和 `tests/conftest.py` 中配置 pytest 发现规则与共享测试引导

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共享的基础能力，完成前不得进入故事实现

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 在 `src/utils/settings.py` 中实现基于环境变量的配置与密钥加载
- [X] T005 [P] 在 `src/models/cli_results.py` 中实现共享 CLI 结果与错误模型
- [X] T006 [P] 在 `src/integrations/feishu_bitable/client.py` 中实现飞书 token 提供器与 Bitable API 客户端
- [X] T007 [P] 在 `src/core/catalog/project_catalog_repository.py` 和 `src/core/rules/rule_repository.py` 中实现项目目录 / 源 sheet 结构 / 规则加载仓库
- [X] T008 [P] 在 `src/utils/output_paths.py` 中实现输出路径与文件命名辅助函数
- [X] T009 [P] 在 `src/core/rules/project_patches.py` 中实现按 `recog_id` 作用域的小型规则扩展注册器
- [X] T010 在 `src/cli/formatters.py` 中实现共享 CLI 格式化与 JSON 输出辅助函数
- [X] T011 在 `tests/helpers/normalizers.py` 中实现 baseline 对比使用的数据归一化工具

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Agent 调用 `list_recog_items` 与 `run_recog_rollup` 完成端到端汇总 (Priority: P1) 🎯 MVP

**Goal**: 让 Agent 能先获取项目列表，再对一个已确认项目执行默认完整流程

**Independent Test**: Agent 可以调用 `list_recog_items` 获取项目清单，并成功调用 `run_recog_rollup --recog_id --period --source_file` 完成完整流程；若任一环节失败，工具能明确返回失败阶段

### Tests for User Story 1

- [X] T012 [P] [US1] 在 `tests/contract/test_catalog_and_full_flow_cli.py` 中补充 `list_recog_items` 与 `run_recog_rollup` 默认完整流程的 CLI 契约测试
- [ ] T013 [P] [US1] 在 `tests/integration/test_full_flow_wave1_smoke.py` 中补充一个首波项目对镜像表的完整流程冒烟测试

### Implementation for User Story 1

- [X] T014 [P] [US1] 在 `src/core/catalog/list_projects_use_case.py` 中实现项目列表查询用例
- [X] T015 [US1] 在 `src/cli/list_recog_items.py` 中实现 `list_recog_items` 命令
- [X] T016 [P] [US1] 在 `src/core/run_recog_rollup_service.py` 中实现 `validate -> preview -> upload` 的完整流程编排器
- [X] T017 [US1] 在 `src/cli/run_recog_rollup.py` 中实现 `run_recog_rollup` 默认模式的参数解析与分发
- [X] T018 [US1] 在 `src/core/run_recog_rollup_service.py` 中加入目标表可用性闸门与失败即停止的流程控制

**Checkpoint**: User Story 1 should let Agent complete one end-to-end stage-one run or stop safely with actionable errors

---

## Phase 4: User Story 2 - Agent 使用 `run_recog_rollup --validate` 与 `--preview` 完成复杂汇总 (Priority: P2)

**Goal**: 让 Agent 能稳定执行结构检验、复杂规则试算以及 preview/baseline 对账。
首版 condition 范围收敛为两类真实已出现条件汇总：按结算时间过滤，以及按单个可枚举 `GROUP` 字段值过滤。

**Independent Test**: Agent 可先执行 `--validate` 获得逐项校验结果，目录模式下只抽检一个代表文件；再执行 `--preview` 对全部匹配源文件完成试算，得到结果文件与概览，并能将输出与 202605 baseline 进行差异对比

### Tests for User Story 2

- [X] T019 [P] [US2] 在 `tests/contract/test_validate_preview_cli.py` 中补充 `--validate` 与 `--preview` JSON 输出契约测试，覆盖目录抽样校验与全量试算语义
- [ ] T020 [P] [US2] 在 `tests/integration/baselines/test_preview_baseline_wave1.py` 中补充首波项目 preview 与 baseline 一致性的集成测试

### Implementation for User Story 2

- [X] T021 [P] [US2] 在 `src/core/validation/validate_stage.py` 中实现结构检验阶段，支持目录模式下随机抽检一个代表文件
- [X] T022 [P] [US2] 在 `src/core/preview/preview_stage.py` 中实现规则驱动的 preview 汇总引擎，支持目录模式下处理全部匹配源文件
- [X] T023 [P] [US2] 在 `src/core/rules/rule_engine.py` 中实现 condition 求值与 optional 字段处理
- [X] T024 [US2] 在 `src/core/preview/preview_artifact_writer.py` 中实现 preview 结果文件写入器与结果摘要构建
- [X] T025 [US2] 在 `tests/helpers/baseline_diff.py` 中实现 baseline 差异报告器与差异分类辅助逻辑
- [X] T026 [US2] 在 `src/cli/run_recog_rollup.py` 中接入 `--validate` 与 `--preview` 模式
- [X] T027 [US2] 在 `tests/helpers/baseline_diff.py` 与 `specs/001-revenue-rollup-cli/iteration-progress.md` 中实现“差异必须先汇报再继续迭代”的流程支持

**Checkpoint**: User Story 2 should let Agent validate, preview, diff, and stop for business confirmation before continuing iteration

---

## Phase 5: User Story 3 - Agent 使用 `run_recog_rollup --upload`、`--append`、`--upsert` 恢复执行并控制上传策略 (Priority: P3)

**Goal**: 让 Agent 能只上传 preview 结果文件，并在镜像表中验证默认冲突报错、追加和覆盖策略

**Independent Test**: Agent 已有 preview 结果文件时，可单独调用 `--upload` 完成上传；在出现同期间冲突时，默认报错，显式指定 `--append` 或 `--upsert` 时按策略执行

### Tests for User Story 3

- [X] T028 [P] [US3] 在 `tests/contract/test_upload_cli.py` 中补充 `--upload`、`--append` 与 `--upsert` 的契约测试
- [ ] T029 [P] [US3] 在 `tests/integration/test_upload_mirror_table.py` 中补充镜像表上传与重复数据处理的集成测试

### Implementation for User Story 3

- [X] T030 [P] [US3] 在 `src/core/upload/upload_stage.py` 中实现结果文件读取器与上传请求构建逻辑
- [X] T031 [P] [US3] 在 `src/core/upload/upload_strategies.py` 中实现同期间重复检测与上传策略解析
- [X] T032 [P] [US3] 在 `src/integrations/feishu_bitable/upload_repository.py` 中实现支持 append/upsert 的镜像表上传仓库
- [X] T033 [US3] 在 `src/cli/run_recog_rollup.py` 中接入 `--upload`、`--append` 与 `--upsert` 标记
- [X] T034 [US3] 在 `src/core/upload/upload_stage.py` 中实现上传回读摘要与飞书错误提示输出

**Checkpoint**: User Story 3 should let Agent safely retest upload behavior against the copied mirror table

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 提升跨故事的稳定性、可维护性与 Ralph 校准效率

- [X] T035 [P] 在 `tests/unit/test_output_paths.py` 与 `tests/unit/test_project_patches.py` 中补充输出路径辅助函数与项目补丁注册器的单元测试
- [X] T036 [P] 在 `tests/unit/test_rule_engine.py` 与 `tests/unit/test_normalizers.py` 中补充 condition 求值与归一化工具的单元测试
- [ ] T037 在 `docs/feishu_bitable_api_notes.md` 与 `specs/001-revenue-rollup-cli/quickstart.md` 中更新镜像表上传与业务确认闸门的开发说明
- [ ] T038 运行首波 quickstart 验证并更新 `specs/001-revenue-rollup-cli/iteration-progress.md`
- [ ] T039 在 `specs/001-revenue-rollup-cli/validate-output-contract.md` 与 `tests/contract/test_validate_preview_cli.py` 中补充“超出首版 condition 能力边界时返回明确错误并提示联系开发者扩展”的契约约束

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，可立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成，阻塞所有用户故事
- **User Story 1 (Phase 3)**: 依赖 Foundational 完成，是 MVP
- **User Story 2 (Phase 4)**: 依赖 User Story 1 的 CLI 骨架与默认流程
- **User Story 3 (Phase 5)**: 依赖 User Story 2 产出的 preview 结果文件边界
- **Polish (Phase 6)**: 依赖所需用户故事完成

### User Story Dependencies

- **User Story 1 (P1)**: 基础 Agent 调用主流程，必须先打通
- **User Story 2 (P2)**: 依赖 `run_recog_rollup` 的基本命令入口，但在规则细化和对账能力上独立扩展
- **User Story 3 (P3)**: 依赖 preview 产物与镜像表访问能力

### Within Each User Story

- 先补契约/集成验证，再补实现
- CLI 入口依赖核心服务，但输出结构必须与 contracts 保持一致
- 每次 preview/baseline 差异都必须先汇报产品负责人确认，再继续补规则

### Parallel Opportunities

- Setup 中依赖声明和目录骨架可并行推进
- Foundational 中 Feishu 客户端、规则仓库、路径工具、patch 注册器可并行
- US2 中 `validate_stage`、`preview_stage`、`rule_engine` 可并行
- US3 中上传仓库、策略解析和 CLI flag 接线可部分并行

---

## Parallel Example: User Story 2

```bash
# 可以并行推进的 US2 实现任务
Task: "Implement structural validation stage in src/core/validation/validate_stage.py"
Task: "Implement rule-driven preview aggregation engine in src/core/preview/preview_stage.py"
Task: "Implement condition evaluation and optional field handling in src/core/rules/rule_engine.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational
3. 完成 Phase 3: User Story 1
4. 停下来验证一个项目是否能端到端跑通
5. 再进入复杂规则和单环节能力

### Incremental Delivery

1. 先交付工具骨架和完整流程
2. 再交付 `--validate` 和 `--preview`，建立 preview/baseline 对账循环
3. 再交付 `--upload`、`--append`、`--upsert`
4. 当前项目对账通过后，再更新 `iteration-progress.md` 并纳入回归集合

### Ralph Loop Delivery

1. 先完成首波 2 到 3 个代表性项目的校准
2. 对每个项目执行 `list -> validate -> preview -> compare -> confirm -> fix current project -> regress passed projects`
3. 不一致时先汇报产品负责人，再决定是补规则、补配置还是修代码
4. 项目波次滚动推进，避免一次覆盖全部 10+ 项目

---

## Notes

- `run_recog_rollup` 的三种单环节模式与两种强制上传策略都已拆成独立子任务
- `quickstart.md` 是 Ralph 内层循环的操作指南，不是一次性试用说明
- `iteration-progress.md` 是 Ralph 内层循环的证据与状态记录，不是装饰文档
- 任何会影响规则解释的差异都不能由实现层自行拍板
- 内层迭代循环只针对 preview/baseline 对账；upload 是独立验证动作
