# Specification Quality Checklist: 财务收入流水汇总 CLI 工具

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 首版范围明确为收入确认 Skill 十步 SOP 中的第 3 步“汇总”，上游依赖下载与文件预处理，下游衔接收入回款确认、后处理及后续收尾环节。
- `source_file` 已明确限定为预处理后的干净单文件或目录，不接受原始压缩包或仍混放多种业务文件的下载目录。
- 规格已明确区分两个工具：`list_recog_items`，以及默认按“结构检验 -> 试算 -> 上传”顺序执行的 `run_recog_rollup`。
- `User Scenarios & Testing` 已改为以 Agent/模型为主要用户视角撰写，人类同事作为任务发起方与结果接收方出现。
- 规格已包含异常后的单环节重跑能力，单环节选项为 `--validate`、`--preview`、`--upload`，上传强制策略为 `--append` 与 `--upsert`。
- 规格已明确汇总步骤产出的是门店级基础事实字段，作为下游收入回款确认的字段原材料，不直接产出折后收入、实际回款、平台服务费、税费、配送费等最终确认字段。
- 条件规则被定义为业务表达形式，未在规格中绑定具体实现语言。
- 敏感凭证读取方式留待 `plan.md` 阶段细化，但已在假设和宪法中明确不得硬编码。
