# Implementation Plan: 收入确认阶段一汇总工具

**Branch**: `001-revenue-rollup-cli` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-revenue-rollup-cli/spec.md`

**Note**: 本计划将该功能落为“双层循环”开发模型：外层由 Spec Kit 负责治理，
内层由 202603 基线对账驱动 Ralph 式迭代。

## Summary

本功能要交付两个可被 Agent 调用的 CLI 工具：`list_recog_projects` 与
`run_recog_rollup`。其中 `list_recog_projects` 负责暴露可选项目清单，
`run_recog_rollup` 负责阶段一的结构检验、试算和上传。

实现策略采用“通用汇总引擎 + 项目级小规则扩展 + 真实历史记录校准”的组合：

- 规则表承担大部分稳定汇总逻辑
- 引擎预留少量按 `recog_id` 扩展的细粒度补丁点
- 日常开发以 `--preview` 对账为主，不以正式上传为主
- 目录模式下，`--validate` 只随机抽检一个代表文件，避免为格式一致的批量源文件重复做结构校验
- 每通过一个项目，就将其纳入回归样本集合

## Technical Context

**Language/Version**: Python 3.13.2

**Primary Dependencies**: Typer、Pydantic、pandas、openpyxl、requests

**Storage**: 本地开发阶段使用本地 Excel / CSV 源文件、`/tmp/revenue-recognition/outputs/`
下的阶段性结果文件、Feishu Bitable 远端业务表拷贝镜像、Markdown 项目覆盖矩阵。
`source_file` 支持单文件或目录输入，其中目录是多数项目的常态输入

**Testing**: pytest、CLI 契约测试、本地 Excel 样本集成测试、基于 202603 历史
记录的基线差异对比检查

**Target Platform**: 生产目标运行环境为部署在 Linux 云服务器上的通用 Agent
系统（如 OpenClaw、Hermes）；当前本地仓库仅用于开发与验证，CLI 契约需保持对
bash 友好，便于后续迁移到云端 Agent 运行时

**Project Type**: 可复用 Python 库 + CLI 入口

**Performance Goals**: 单个 `recog_id` 的 `--validate` 或 `--preview` 在 202603
基线样本上应在 2 分钟内完成；在生成 preview 结果后，差异报告应在 30 秒内可得

**Constraints**: 正确性高于性能；不得硬编码敏感凭证；上传能力必须与 preview
能力解耦；设计必须支持大量小规则迭代，同时不能破坏已验证项目；任何 preview
与 baseline 不一致的差异都必须先汇报产品负责人并获得业务解释确认，不能由开
发方或 Agent 自行决定规则含义

**Scale/Scope**: 首批范围是 10+ 个 `recog_rollup` 项目，第一波先校准 2 到 3 个
代表性项目；每个项目都可能涉及多个文件和多个 sheet。对 `csv` 或只有单个 sheet 的
`xlsx`，配置中的 `sheet` 使用 `DEFAULT`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [PASS] 核心计算逻辑将与 CLI 入口、Feishu 适配层分离。
- [PASS] 面向 Agent 的命令契约已在 `contracts/` 中显式文档化。
- [PASS] 验证策略明确以本地 202603 源文件和 202603 历史记录作为第一批黄金基线。
- [PASS] 所有敏感信息均计划通过环境变量或安全配置读取，而不是写入源码。
- [PASS] 上传风险与日常开发循环解耦：preview-first 对账是主路径，upload 是单独受控动作，且已有业务表拷贝镜像可安全用于上传验证。

设计后复核：当前无需为宪法豁免引入额外复杂性。

## Project Structure

### Documentation (this feature)

```text
specs/001-revenue-rollup-cli/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── project-coverage-matrix.md
├── contracts/
│   ├── list_recog_projects.md
│   └── run_recog_rollup.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── cli/
│   ├── list_recog_projects.py
│   └── run_recog_rollup.py
├── core/
│   ├── catalog/
│   ├── validation/
│   ├── preview/
│   ├── upload/
│   └── rules/
├── integrations/
│   └── feishu_bitable/
├── models/
└── utils/

tests/
├── contract/
├── integration/
│   ├── baselines/
│   └── fixtures/
├── helpers/
└── unit/
```

**Structure Decision**: 采用单一 Python 项目结构，保持 CLI 层足够薄，核心引擎
可复用，Feishu 集成单独隔离。这样后续封装 skill 时外层会很薄，而规则引擎和上传
逻辑也可以独立演进。preview/baseline 的差异对比仅作为开发阶段测试辅助手段，放在
`tests/helpers/`，不属于工具本体模块。

## Ralph Loop Strategy

### Outer Loop: Spec Kit 治理循环

1. 将稳定工具契约维护在 `spec.md`
2. 将架构、验证策略和扩展规则维护在 `plan.md`
3. 在 `tasks.md` 中按“引擎能力、验证框架、项目波次”拆解任务
4. 每通过 2 到 3 个项目就用 `speckit-analyze` 检查 spec、plan、tasks 和代码是否开始漂移

### Inner Loop: 基线对账循环

1. 从 `project-coverage-matrix.md` 选择一个 `recog_id`
2. 运行 `list_recog_projects`，确认目录可见且目标表可用
3. 运行 `run_recog_rollup --validate`
   目录模式下只抽检一个代表文件做结构校验
4. 运行 `run_recog_rollup --preview`
   目录模式下对全部匹配源文件执行真实试算
5. 将 preview 输出与 202603 历史记录逐项对比
6. 一致则标记该项目通过，并纳入回归集合
7. 不一致则先整理差异结果与判断建议并汇报给业务负责人，由业务负责人确认解释口径后，再将差异分类为：
   - 通用引擎缺口
   - 项目特有规则缺口
   - 简单实现 bug
8. 修正正确层级后，重跑当前项目和所有已通过项目

## First Wave Delivery Strategy

- Wave 1 聚焦引擎骨架、JSON 输出契约、Feishu 项目目录访问和基线差异框架
- Wave 2 校准 2 到 3 个来自 202603 源数据和历史记录的代表性项目
- Wave 3 用相同对账循环扩展剩余 `recog_rollup` 项目
- 日常迭代优先使用 `--preview`；`--upload` 使用已存在的飞书业务数据库拷贝镜像表做安全验证

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
