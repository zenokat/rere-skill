# 飞书多维表 API 经验沉淀

## 当前项目用到的接口

### 1. 获取 tenant_access_token
- 方法：`POST`
- 地址：`https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`
- 请求体：

```json
{
  "app_id": "YOUR_APP_ID",
  "app_secret": "YOUR_APP_SECRET"
}
```

### 2. 列出某个多维表 App 下的数据表
- 方法：`GET`
- 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=500`

### 3. 列出某张数据表的字段
- 方法：`GET`
- 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=500`

### 4. 分页读取某张数据表的全部记录
- 方法：`GET`
- 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=500`
- 分页参数：`page_token`

### 5. 批量创建记录
- 方法：`POST`
- 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create`
- 请求体示例：

```json
{
  "records": [
    {
      "fields": {
        "期间": "202603",
        "门店编号": "10008",
        "折后收入": 10601.3,
        "服务费": -21.58
      }
    }
  ]
}
```

### 6. 批量更新记录
- 方法：`POST`
- 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update`
- 请求体示例：

```json
{
  "records": [
    {
      "record_id": "recxxxxxx",
      "fields": {
        "期间": "202603",
        "门店编号": "10008"
      }
    }
  ]
}
```

## 当前项目里已经确认的业务理解

### 1. 配置库与开发模拟库是两个不同的飞书 App
- 配置库负责维护确认项目注册表、源文件结构表、汇总规则表。
- 开发模拟库负责存放“目标结果”记录，用于开发测试对比。

### 2. `recognition_id` 在飞书接口返回中是关联字段
- 读取时不能按普通字符串处理。
- 需要优先取其 `text` 值作为业务主键。

### 3. `last_row` 是数据结束边界的重要驱动配置
- 负数代表“相对文件末尾偏移”。
- 例如 `last_row=-4` 表示“数据最后一行 = 总行数 - 4”。

### 4. `FILE_NAME` 是工具内置元数据字段
- 不来自源文件中的某一列。
- 当前首版按物理文件名处理。
