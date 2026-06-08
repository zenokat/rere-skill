# CLI Contract: `list_recog_projects`

## Purpose

暴露已注册的阶段一汇总项目清单，供 Agent 在调用 `run_recog_rollup` 之前选定
正确的 `recog_id`。

## Invocation

```bash
list_recog_projects
```

## Inputs

- 必填入参：无

## Success Output

推荐 JSON 结构：

```json
{
  "status": "ok",
  "projects": [
    {
      "recog_id": "wechat_pay_settlement",
      "recog_name": "微信回款汇总",
      "bitable_table_id": "tblxxxx",
      "bitable_table_exists": true
    }
  ],
  "count": 1
}
```

## Failure Output

```json
{
  "status": "error",
  "stage": "catalog",
  "message": "Unable to read project catalog",
  "details": []
}
```

## Exit Semantics

- `0`: 成功
- `2`: 运行时配置无效
- `14`: 远端目录读取失败

## Notes

- 该工具只列示项目，不负责替 Agent 判断应选哪个项目。
- 项目匹配与歧义处理属于 Agent / 模型层职责。
