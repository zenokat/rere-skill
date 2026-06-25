# Implementation Plan: 收入确认 WorkBuddy 自动化评测底座

**Branch**: `002-workbuddy-eval-harness` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-workbuddy-eval-harness/spec.md`

## Summary

本 feature 要交付一套面向 Agent 的评测底座，用来对运行在 WorkBuddy / CodeBuddy 同核
环境中的收入确认 skill 做可重复、可批量、可对比的自动化评测。首版采用
CodeBuddy CLI 官方无头模式作为自动化执行面，围绕稳定 case 清单、批量运行器、证据包、
自动评分卡、基线快照和回归视图建立统一产物契约。

设计重点不是“把一次脚本跑通”，而是把评测闭环搭成长期资产：

- 同一组 case 可以被重复重跑，并保留稳定身份。
- 每次运行都会落下结构化结果、证据引用和失败归因。
- 评分以确定性规则为主，以 Rubric 和人工校准为辅。
- 首版优先覆盖收入确认 SOP 第 3 步“汇总”的 validate / preview 场景。
- upload 仅在 case 明确声明安全环境时才进入评测范围。

## Technical Context

**Language/Version**: Python 3.13.2（harness 编排、评分器、产物落盘） + Node.js 18+（CodeBuddy CLI 运行时）

**Primary Dependencies**: 现有仓库 Python 技术栈（Typer、Pydantic、pytest）、CodeBuddy CLI（`codebuddy` / `cbc`）、可选 `jq`（本地结果查看）、可选 OpenTelemetry Collector

**Storage**: 仓库内本地文件系统工件为主，包括 case manifest、批次运行目录、证据包、评分结果、基线快照和 Markdown 摘要；可选接入外部 OTLP Collector 保存 trace

**Testing**: pytest 单元测试、契约测试、集成测试；至少 3 条代表性 case 的 smoke batch；基线保存/比较测试；fake runner + fixture 驱动的评分器测试

**Target Platform**: 首版自动化执行目标为 CodeBuddy CLI 无头模式，验证 WorkBuddy 同核行为；本地开发以 Windows 为主，设计需兼容 Linux 上的 CLI 自动化

**Project Type**: 可复用 Python 包 + 仓库级 CLI 入口 + 文件系统工件契约

**Performance Goals**: 首版 3 条代表性 case 的 smoke batch 在稳定本地环境下应于 15 分钟内完成；单 case 在运行结束后 60 秒内完成证据整理；smoke 规模下基线 diff 在 30 秒内可得

**Constraints**:

- 无头执行必须基于官方 `-p/--print` 入口，而不是依赖 WorkBuddy GUI 自动点选。
- 需要结构化输出，首版标准输出为 `json`，深度留痕时补充 `stream-json`。
- 官方文档要求：无头执行若涉及文件读写、命令执行、网络请求等授权动作，需在受信环境下显式带 `-y/--dangerously-skip-permissions`。
- 评分应优先看结果和关键守卫，而不是僵硬检查完整工具路径。
- trial 之间必须隔离，不能让上一轮遗留产物影响下一轮结果。
- telemetry 默认应最小化，prompt 内容、工具参数和工具内容记录都必须保持 opt-in。
- 未显式声明安全环境的 case 不得默认触发 upload 风险。

**Scale/Scope**: 首版最低验收是 3 条代表性 rollup case；设计应能平滑扩展到 20-50 条 capability eval，以及后续不断增长的 regression suite，而不改主契约

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [PASS] 核心能力先行，可复用优先：评测底座与被测 skill、仓库本地启动器、WorkBuddy / CodeBuddy 适配层分离，避免把评测逻辑写进业务 skill 包装脚本。
- [PASS] Agent 调用契约稳定且可机读：case manifest、批量运行、结果包和基线快照都以结构化契约对外，支持人和 Agent 共用。
- [PASS] 规格驱动渐进交付：先做最小可用默认设置和 3 条代表性 case，再按能力评测到回归评测的节奏扩展，不追求一次做全。
- [PASS] 可验证、可观测、可追踪：每个 case 都有运行记录、证据包、评分卡和失败归因；CLI `json` / `stream-json` 与可选 OTel trace 共同支撑复盘。
- [PASS] 安全优先、简单实现、显式配置：upload 默认关闭；telemetry 内容采集默认关闭；扩展评分和留痕通过显式配置接入，不用隐式魔法。

设计后复核结论：Phase 1 设计仍满足以上原则，无需记录宪章偏离项。

## Project Structure

### Documentation (this feature)

```text
specs/002-workbuddy-eval-harness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── case-manifest.md
│   ├── run-eval-batch.md
│   ├── result-bundle.md
│   └── baseline-snapshot.md
└── tasks.md
```

### Source Code (repository root)

```text
skill/
└── revenue-recognition/
    ├── SKILL.md
    └── references/

src/
├── cli/
├── core/
├── evals/
│   ├── cli/
│   ├── cases/
│   ├── runners/
│   ├── evidence/
│   ├── graders/
│   ├── baselines/
│   └── reports/
├── integrations/
│   ├── codebuddy_cli/
│   └── feishu_bitable/
├── models/
└── utils/

tests/
├── contract/
│   └── eval_harness/
├── integration/
│   └── eval_harness/
└── unit/
    └── eval_harness/
```

**Structure Decision**: 保持单一 Python 项目结构，在现有 `src/cli`、`src/core` 之外新增
`src/evals/` 作为评测底座的核心实现层；`src/integrations/codebuddy_cli/` 负责封装
CodeBuddy / WorkBuddy 同核运行时的调用细节；被测收入确认 skill 继续保留在
`skill/revenue-recognition/`，不与 harness 核心混写。

## Phase 0 Research Output

Phase 0 已将以下关键不确定项收敛到 [research.md](./research.md)：

- 为什么首版应以 CodeBuddy CLI 无头模式而非 GUI 作为自动化入口
- 为什么需要把 `json` 结果、`stream-json` 转录和 OTel traces 拆成“必选最小证据”和“可选深度证据”
- 为什么评分应采用 `code > rubric > human` 的分层，而不是一开始全部交给模型判断
- 为什么“正确止步”必须作为独立通过类型，而不是落入普通失败
- 为什么 capability eval 通过后要毕业为 regression eval，而不是一次性临时验证

## Phase 1 Design

### 1. Batch Runner Design

首版 runner 负责读取稳定 case 清单，并为每个 case 生成独立 trial：

1. 读取 suite manifest 与默认/扩展设置。
2. 为每个 case 计算唯一 `run_id` 与隔离输出目录。
3. 通过 CodeBuddy CLI 无头模式发起运行，标准输出使用 `json`。
4. 当需要更深证据时，额外保存 `stream-json` transcript 或开启 OTel trace。
5. 将执行结果归类为：通过、正确止步、环境失败、证据不足、skill/工具失败、harness 失败。

### 2. Evidence Design

证据分成两层：

- 最小必备层：批次元数据、CLI 命令、stdout/stderr、`session_id`、最终 JSON 结果、失败归因、证据完整性标记。
- 可选扩展层：`stream-json` transcript、OTel traces、更多工具输入输出细节、人工摘要增强。

这样做的原因是：首版必须先保证“每轮必然有可比较结果”，而不是一上来把所有深度留痕都做成 hard dependency。

### 3. Grader Design

评分采用三层结构：

- 确定性评分器：负责结果分类、必需字段、关键边界、必需/禁止行为、证据完整性、环境失败识别。
- Rubric 评分器：负责任务理解、结果解读、摘要质量等较软维度，输出结构化理由。
- 人工评分器：只用于 baseline 晋升、Rubric 校准和争议 case 复核，不作为每轮主路径。

评分强调“结果和关键约束”而不是“完整路径照搬”。例如：如果 case 的正确行为是澄清、阻断或拒绝越界执行，只要边界与结论正确，就应视为通过。

### 4. Baseline Design

baseline 不是单纯保存一个分数，而是保存：

- case 身份与版本
- scorer 版本
- skill / prompt / environment 指纹
- 每条 case 的运行结论、评分卡和证据引用

后续比较输出至少区分：

- `regressed`：出现新增失败或评分下降
- `fixed`：上轮失败、本轮修复
- `unchanged`：无实质变化
- `not_comparable`：版本差异或证据缺失导致不可比

### 5. Failure Attribution Design

首版归因分类固定为四大类：

- `skill_behavior`：skill 提示、推理或边界遵守问题
- `wrapped_tool`：skill 包装脚本或底层汇总工具问题
- `runtime_environment`：WorkBuddy / CodeBuddy 运行环境、权限、凭证、安装缺失问题
- `harness_system`：评测底座自身的 runner、grader、artifact 逻辑问题

这四类会同时进入单 case 结果和批次聚合摘要，帮助产品与研发直接回答“下一轮先改哪里”。

## First Wave Delivery Strategy

首版只聚焦最小却完整的闭环，不追求一开始覆盖整个收入确认 SOP：

1. 先做 3 条代表性 rollup case：
   - 成功跑通 `list_recog_items -> validate -> preview`
   - 正确止步，不继续做下游收入确认
   - 运行环境缺底层 CLI / 凭证，明确归类为环境失败
2. 跑通批量发起、证据收集、自动评分、基线保存、回归比较五个主环节
3. 等首批 case 稳定后，再扩展更多 rollup case
4. upload 相关 case 仅在显式安全环境下纳入

## Validation Strategy

实现阶段的核心验证分三层：

- 契约层：manifest、batch result、baseline snapshot 的 JSON / 文件结构稳定可解析
- 运行层：fake runner 与真实 headless runner 都能产出一致的主结果结构
- 回归层：相同 case 重跑后能输出逐 case、逐评分维度的 diff，并正确标记新增问题与修复项

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
