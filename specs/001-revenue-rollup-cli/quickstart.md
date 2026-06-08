# Quickstart: Ralph 式校准开发与验证

## Purpose

本指南用于通过真实的 202603 源文件和真实历史记录，验证阶段一汇总引擎的正确
性，并建立 preview-first 的日常开发循环。

## Prerequisites

- Python 3.13.2 环境可用
- 关键依赖已安装：`typer`、`pydantic`、`pandas`、`openpyxl`、`requests`
- Feishu 凭证已通过安全环境变量提供
- 本地源数据已准备在 `202603-source-excel/`
- 202603 历史记录可从飞书业务数据库的拷贝镜像表访问
- 项目覆盖矩阵已建立：[project-coverage-matrix.md](./project-coverage-matrix.md)
- 多数项目建议将 `source_file` 直接指向一个目录；对于 `csv` 或只有单个 sheet 的
  `xlsx`，配置表中的 `sheet` 应统一使用 `DEFAULT`

## Recommended First-Wave Scope

第一波不要一次上 10+ 个项目，建议先选 2 到 3 个代表性项目：

- 高频支付或回款项目
- 一个 POS 风格的汇总项目
- 一个已知存在多 sheet 或复杂 condition 的项目

## Validation Workflow

### 1. 列出可用项目

```bash
list_recog_projects
```

期望结果：

- 能逐条返回项目清单
- 每条至少包含 `recog_id`、`recog_name`、`bitable_table_id`、`bitable_table_exists`

### 2. 选择一个首批项目

选定一个 `recog_id`，并将其写入 [project-coverage-matrix.md](./project-coverage-matrix.md)。

### 3. 执行结构检验

```bash
run_recog_rollup --validate --recog_id <recog_id> --source_file <path>
```

期望结果：

- 要么所有检查通过
- 要么返回明确的 sheet / 范围 / 字段 / condition / 飞书字段问题
- 如果传入的是目录，工具只随机抽检一个代表文件，并在结果中标明该文件路径

### 4. 执行试算

```bash
run_recog_rollup --preview --recog_id <recog_id> --period 202603 --source_file <path>
```

期望结果：

- 成功：返回结果文件路径以及条数、字段数概览
- 失败：返回可定位到文件、sheet、行、字段的异常信息
- 如果传入的是目录，工具会对目录下全部匹配源文件执行试算

### 5. 将试算结果与 202603 历史记录对账

使用生成的结果文件，与同一个 `recog_id` 的 202603 历史记录逐项对比。

通过标准：

- 字段级金额和口径在约定精度与归一化规则下与历史记录一致

不通过标准：

- 必须先整理差异结果和判断建议并汇报给业务负责人
- 仅在业务负责人确认口径后，才可将差异归类为：
  - 通用引擎缺口
  - 项目特有规则缺口
  - 实现 bug

### 6. 修正并回归

每次修正后都执行：

1. 重跑当前首批项目
2. 重跑所有已通过项目
3. 更新 [project-coverage-matrix.md](./project-coverage-matrix.md)

### 7. 仅在 preview 稳定后执行上传

```bash
run_recog_rollup --upload --recog_id <recog_id> --result_file <preview_file>
```

在活跃开发阶段，优先上传到飞书业务数据库的拷贝镜像表。

强制上传策略：

```bash
run_recog_rollup --upload --append --recog_id <recog_id> --result_file <preview_file>
run_recog_rollup --upload --upsert --recog_id <recog_id> --result_file <preview_file>
```

## Done Criteria for One Project

一个项目只有在满足以下条件后才算校准通过：

- `list_recog_projects` 能正确暴露该项目
- `--validate` 通过
- `--preview` 输出与 202603 历史记录一致
- 所有 preview/baseline 差异都已经过业务负责人确认
- 后续新增规则后回归仍通过
- 至少在一个安全环境中验证过上传行为

## References

- [research.md](./research.md)
- [data-model.md](./data-model.md)
- [project-coverage-matrix.md](./project-coverage-matrix.md)
- [docs/feishu_bitable_api_notes.md](../../docs/feishu_bitable_api_notes.md)
