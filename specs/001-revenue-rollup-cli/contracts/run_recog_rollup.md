# CLI Contract: `run_recog_rollup`

## Purpose

执行阶段一收入确认汇总流程，既支持完整流程，也支持单独运行某个环节。

## Invocation

### 完整流程

```bash
run_recog_rollup --recog_id <recog_id> --period <YYYYMM> --source_file <path>
```

### 仅结构检验

```bash
run_recog_rollup --validate --recog_id <recog_id> --source_file <path>
```

### 仅试算

```bash
run_recog_rollup --preview --recog_id <recog_id> --period <YYYYMM> --source_file <path>
```

### 仅上传

```bash
run_recog_rollup --upload --recog_id <recog_id> --result_file <path>
run_recog_rollup --upload --append --recog_id <recog_id> --result_file <path>
run_recog_rollup --upload --upsert --recog_id <recog_id> --result_file <path>
```

## Mode Rules

- `--validate`、`--preview`、`--upload` 互斥
- 如果三者都不传，则默认执行完整流程：
  `validate -> preview -> upload`
- `--append` 与 `--upsert` 互斥，且只能和 `--upload` 一起使用
- `--source_file` 可以是单文件路径或目录路径，目录路径是多数项目的常态输入
- 当 `--source_file` 为目录路径时，`--validate` 仅随机抽检一个代表文件；`--preview`
  对目录下全部匹配源文件执行试算
- 对 `csv` 或只有单个 sheet 的 `xlsx`，配置中的 `sheet` 使用 `DEFAULT`

## Success Output

### `--validate` 成功

```json
{
  "status": "ok",
  "mode": "validate",
  "recog_id": "wechat_pay_settlement",
  "checks": [
    {
      "check_name": "sheet_exists",
      "scope": "sheet:流水明细",
      "passed": true,
      "message": "Sheet exists",
      "details": []
    }
  ],
  "sampled_source_file": "D:/AI/rere-agent/202603-source-excel/微信/武汉市蔡林记餐饮发展有限公司.csv",
  "error_count": 0
}
```

### `--preview` 成功

```json
{
  "status": "ok",
  "mode": "preview",
  "recog_id": "wechat_pay_settlement",
  "period": "202603",
  "result_file": "/tmp/revenue-recognition/outputs/202603_wechat_pay_settlement_20260606-210000.xlsx",
  "row_count": 120,
  "field_count": 38,
  "warnings": []
}
```

### `--upload` 成功

```json
{
  "status": "ok",
  "mode": "upload",
  "recog_id": "wechat_pay_settlement",
  "result_file": "/tmp/revenue-recognition/outputs/202603_wechat_pay_settlement_20260606-210000.xlsx",
  "target_table_id": "tblyOiWLnWW4QiYO",
  "upload_strategy": "append",
  "row_count": 120,
  "field_count": 38
}
```

## Failure Output

```json
{
  "status": "error",
  "mode": "preview",
  "stage": "preview",
  "recog_id": "wechat_pay_settlement",
  "errors": [
    {
      "source_file": "D:/AI/rere-agent/202603-source-excel/微信/example.xlsx",
      "sheet": "流水明细",
      "row": 123,
      "field": "结算金额",
      "message": "Condition cannot be evaluated"
    }
  ]
}
```

## Exit Semantics

- `0`: 成功
- `2`: 参数无效或模式冲突
- `10`: 结构检验失败
- `11`: 试算失败
- `12`: 上传时发生重复期间冲突
- `13`: 上传远端失败
- `14`: 项目或配置读取失败
- `15`: 本地文件读写失败

## Notes

- `--result_file` 是 `--preview` 和 `--upload` 之间的正式交接产物。
- 在高频开发阶段，`--preview` 是主对账路径，`--upload` 应作为单独受控动作。
