# Quickstart: 收入确认 Skill 第 3 步汇总工具迭代循环指南

## Purpose

本指南不是一次性的“功能试用说明”，而是 `001-revenue-rollup-cli`
循环迭代式开发的操作手册。它只覆盖收入确认 Skill 十步 SOP 中的第 3 步“汇
总”。完整业务工作流见
[revenue_recognition_skill_workflow.md](../../ref-docs/revenue_recognition_skill_workflow.md)。

收入确认的汇总运算，除了核心运算逻辑，还有若干不易梳理归纳的运算细节，为
了覆盖所有这些细节，以 baseline 为黄金标准，采用循环迭代的方式推进开发，逐
个确认项目推进，持续执行 `validate -> preview -> baseline对账 -> 修正 -> 回归`
的闭环，直到汇总工具输出与历史 baseline 完全一致。

本迭代循环只针对 `preview` 的汇总运算逻辑，不包含 `upload` 验证。
下载源文件、文件预处理、收入回款确认、后处理、RPA 入账、验算、分发、调整和
封版均不属于本指南的执行范围。


## Inputs And Artifacts

每一轮迭代至少会使用或更新以下工件：

- [iteration-progress.md](./iteration-progress.md)：记录每个项目当前是否应继续推进，以及每轮迭代的关键结论和增量改动
- [plan.md](./plan.md)：说明外层 Spec Kit 治理方式，以及内层 Ralph 循环的原则
- `environment.md`：沉淀多次踩坑后的环境处理经验
- `sandbox-rules-allow-list.md`：沉淀高频且低风险的提权命令审批入口

## Prerequisites

- Python 3.13.2 环境可用
- 关键依赖已安装：`typer`、`pydantic`、`pandas`、`openpyxl`、`requests`
- Feishu 凭证已通过安全环境变量提供
- 本地源数据已完成文件预处理，能够以干净单文件或干净目录形式提供给 `source_file`
- 目标期间的 baseline 数据可访问
- 当前特性的项目清单可通过 `list_recog_items` 读取

补充约定：

- 大多数项目的 `source_file` 应直接传目录路径
- `source_file` 不能直接指向原始压缩包，也不能指向仍混放多种业务文件的下载目录
- 飞书相关异常优先查官方文档与现有环境经验，不要先频繁试错

## Loop Overview

每次只推进一个 `recog_id`，并严格遵守以下节奏：

1. 先读 [iteration-progress.md](./iteration-progress.md) 中该项目的当前状态和最近一轮记录
2. 如果最近结论是“业务TBD”或其他明确阻断，则先停，不继续代码改动
3. 运行 `validate` 和 `preview`，拿到工具跑出的运算结果
   这里的输入前提是：当前项目所需文件已经被预处理整理为干净目录或单文件
4. 与 baseline 对账并先做差异溯因
5. 只要确认是代码或配置问题，就修复并继续当前项目
6. 如果追到业务语义模糊，就停下来汇报等待业务确认
7. 每次运行和溯因为一次循环，循环记录需写入 `iteration-progress.md`
8. 当该项目已与 baseline 一致后，再把它纳入稳定回归集合，回归已通过项目，确认没有把之前项目搞坏，再挑选下一个项目

## Standard Iteration Procedure

### 1. 选择当前项目

先查看已有记录，选择尚未通过 baseline 对账的项目，如对账均通过，则执行以下命令寻找下一个迭代的确认项目：

```bash
.\.codex\scripts\rere.cmd list_recog_items
```

选定项目后，在 [iteration-progress.md](./iteration-progress.md) 中为该项目补充或新建记
录块，再开始本轮执行。

### 2. 先检查是否存在业务阻断

开始新一轮前，先看该项目当前 `status`，再读最近一条记录中的结论：

- 如果已经标记为“业务TBD”，本轮不继续改代码
- 如果是飞书权限、表结构权限等硬阻碍，也不继续
- 只有确认仍可继续工程迭代时，才进入下一步

### 3. 执行结构检验

```bash
.\.codex\scripts\rere.cmd run_recog_rollup --validate --recog_id <recog_id> --source_file <path>
```

记录重点：

- 若 `source_file` 为目录，记录被抽检的代表文件
- 是否通过
- 若失败，失败点属于 `sheet`、范围、字段、condition 还是飞书字段问题

处理原则：

- `validate` 失败时，不进入 `preview`
- 如果失败原因明确是代码或配置问题，直接修复并进入下一轮
- 如果失败原因涉及业务口径理解，记录后停下等待确认

### 4. 执行试算

```bash
.\.codex\scripts\rere.cmd run_recog_rollup --preview --recog_id <recog_id> --period <period> --source_file <path>
```

记录重点：

- 是否完成
- 总耗时
- 如果失败，是否已定位到文件、sheet、行、字段或具体规则

处理原则：

- `preview` 失败时，先溯因再修复
- 不要直接把“预览失败”当成业务差异；先分清是代码 bug、配置问题，还是业务语义问题

### 5. 与 baseline 对账

使用本轮 `preview` 结果，对同一 `recog_id`、同一期间的 baseline 做逐项比较。

通过标准：

- 字段级金额与口径在约定精度、归一化规则下与 baseline 一致

不通过时的处理顺序：

1. 先判断差异是否来自代码实现、规则配置或辅助脚本
2. 如果是工程问题，直接修复，并在记录中写明修复方案
3. 如果最终追溯到业务语义模糊、历史口径不明确或 baseline 本身需要业务解释，则将结论明确记为“业务TBD”

注意：

- 差异没有被溯因之前，不要贸然继续扩展规则
- 业务语义问题不是代码 bug，不能由开发侧自行拍板

### 6. 修正，当前项目通过后再回归

每次修正后，都至少执行以下动作：

1. 重跑当前项目的必要阶段
2. 只有当前项目已经对账通过时，再重跑所有已进入稳定回归集合的项目
3. 更新 [iteration-progress.md](./iteration-progress.md)



## Stop Conditions

以下情况应停止当前项目迭代，而不是继续盲改：

- 最近一轮结论已经是“业务TBD”，差异需要业务方解释口径
- 飞书权限、表权限或其他外部依赖构成硬阻碍

## Done Criteria For One Project

一个确认项目只有在满足以下条件后，才算完成当前阶段校准：

- `list_recog_items` 能正确暴露该项目
- `--validate` 通过
- `--preview` 输出与目标期间 baseline 一致
- 当前差异已完成溯因且得到解决
- 当前项目对账通过后，回归集合仍通过


## References

- [spec.md](./spec.md)
- [plan.md](./plan.md)
- [research.md](./research.md)
- [data-model.md](./data-model.md)
- [iteration-progress.md](./iteration-progress.md)
- [goal_run_recog_rollup.md](./goals/goal_run_recog_rollup.md)
- [revenue_recognition_skill_workflow.md](../../ref-docs/revenue_recognition_skill_workflow.md)
- [feishu_bitable_api_notes.md](../../ref-docs/feishu_bitable_api_notes.md)
