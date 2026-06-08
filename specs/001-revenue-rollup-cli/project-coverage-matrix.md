# Project Coverage Matrix

## Purpose

用于跟踪内层 Ralph 式迭代循环，而不是把不稳定的项目级细节不断塞进 `spec.md`。

## Usage

- 每个 `recog_id` 一行
- 每次做完结构检验、试算对账、回归后更新这一行
- 只有 `preview_matched=true` 的项目才可以进入稳定回归集合
- 若 preview 与 baseline 不一致，必须先将差异与建议提交业务负责人确认，再继续下一轮规则迭代

## Matrix

| recog_id | recog_name | source_ready | history_ready | validate_passed | preview_matched | business_confirmed | diff_type | rule_delta | regression_status | notes |
|---|---|---|---|---|---|---|---|---|---|
| dine_in_revenue | 堂食收入 | true | true | true | true | true | matched | 修复测试侧字段解包、期间筛选、负数 `last_row` 边界与联合键归一化 | passed | `preview` 287 条、baseline 287 条；对账已匹配，不再存在代码层噪音差异 |

