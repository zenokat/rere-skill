# Iteration Progress

## Purpose

本文件只承担两件事：

1. 追踪迭代循环进度，确保一个项目未对账通过前，不跳到下一个项目；遇到需要业
务确认的问题时，明确停下，避免反复撞墙。
2. 记录每轮迭代的增量改动，沉淀开发历程，帮助后续项目复用已验证的修复和经验。

## Usage

- 总表只看当前推进状态，用来决定“下一个该做哪个项目，当前项目该不该继续”
- 每个项目保留一个简短历史表，用来记录每轮关键结论和增量改动
- 如果最近一轮结论是 `业务TBD` 或 `blocked`，在问题解决前不要继续该项目
- 只有 `status=matched` 的项目，才可以纳入稳定回归集合

## Project Status

| recog_id | recog_name | status | last_round | next_action | latest_delta |
|---|---|---|---|---|---|
| dine_in_revenue | 堂食收入 | matched | 1 | 保持在稳定回归集合中，后续规则改动后持续回归 | 修复测试侧字段解包、期间筛选、负数 `last_row` 边界与联合键归一化 |
| eleme_delivery_settlement | 饿了么回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现期间或联合键问题，优先回归该项目 | 修复大账单流式读取、只读模式维度误判、忽略 `~$` 临时文件；补强联合键归一化与字段类型规范化 |
| member_collection | 代收会员储值 | matched | 1 | 保持在稳定回归集合中；后续若再出现源表多层表头或 baseline 类型噪音，优先回归该项目 | 修正远端 `category_row/category/optional` 配置；补强 baseline 数字字符串归一化 |
| wechat_pay_settlement | 微信回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 CSV 反引号、虚拟来源文件字段或缺失平台ID 聚合问题，优先回归该项目 | 增加 `FILE_NAME` 虚拟列、放宽单选 GROUP 类型校验、清洗 CSV 反引号并回填缺失 `平台ID` 后重聚合 |
| alipay_settlement | 支付宝回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 Agent 预处理目录过滤、空汇总文件剔除或 CSV 空白行问题，优先回归该项目 | 保持“解压与来源文件中文映射都不属于工具职责”边界；补强 CSV 空白行过滤；验证保留原始文件名的真实源目录可完成汇总阶段对账 |
| shouqianba_settlement | 收钱吧回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 `xlsx` 目录模式、`FILE_NAME` 虚拟列或支付方式单选字段问题，优先回归该项目 | 复用 `FILE_NAME` 虚拟列与单选 GROUP 类型兼容；验证 `202605-source-excel/收钱吧` 目录可直接完成对账 |
| douyin_voucher_settlement | 抖音回款 | matched | 3 | 保持在稳定回归集合中；后续若再改 `upsert` 语义或抖音回款口径，优先回归该项目 | 用户已接受现行 `preview` 口径并手动清理最后 1 条旧残留；现有 `upsert` 已成功将 `preview` 282 条上传到结果表 |

`status` 只使用以下几种值：

- `working`：还在继续工程迭代
- `matched`：已与 baseline 对账一致
- `业务TBD`：需要业务确认，当前停止
- `blocked`：遇到外部硬阻碍，当前停止

## Template

为新项目建记录时，复制以下模板：

```md
### <recog_id> / <recog_name>

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | YYYY-MM-DD | validate通过，preview/baseline不一致，继续迭代 | 本轮新增修改 | 本轮关键结论、阻断或下一步 |
```

字段说明：

- `result`：只写本轮最重要的结果，足以判断是否继续、是否换项目、是否应停下等业务确认
- `delta`：只写本轮新增代码、规则、文档、环境处理等增量改动
- `notes`：补充关键背景，例如条数、耗时、阻断原因、下一步动作

## Active Projects

### dine_in_revenue / 堂食收入

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-12 | `validate` 与 `preview` 通过，`preview` 287 条、baseline 287 条，对账一致 | 修复测试侧字段解包、期间筛选、负数 `last_row` 边界与联合键归一化；补强 baseline helper | 已纳入稳定回归集合 |

### eleme_delivery_settlement / 饿了么回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-12 | `validate` 与 `preview` 通过，最新 `preview` 232 条，与 baseline 对账一致 | 修复大账单流式读取、只读模式维度误判、忽略 `~$` 临时文件；补强联合键归一化与字段类型规范化 | 已纳入稳定回归集合 |

### member_collection / 代收会员储值

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-13 | 先修复远端配置后，`validate` 与 `preview` 通过，`preview` 231 条、baseline 231 条，对账一致 | 修正远端 `category_row=3`，为多层表头字段补 `category`，将 `抖音券` 调整为 `optional`；补强 baseline 数字字符串归一化测试 | `202605` 样本使用 `收入收款方式构成表`；问题先归因到远端配置，其次修复对账 helper 的类型噪音 |

### wechat_pay_settlement / 微信回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-13 | `validate` 与 `preview` 通过，最新 `preview` 486 条、baseline 486 条，对账一致 | 增加 `FILE_NAME` 虚拟列；放宽飞书 `SingleSelect(type=3)` 对 `GROUP` 的类型兼容；清洗 CSV 文本前缀反引号；对缺失 `平台ID` 的记录按同源唯一候选回填后重新聚合 | `202605` 样本使用 `202605-source-excel/微信` 目录；先修工程侧输入归一化与聚合逻辑，再完成对账 |

### alipay_settlement / 支付宝回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-13 | 在 Agent 先完成解压和目录整理后，`validate` 与 `preview` 通过；按汇总阶段口径，保留原始文件名时 `preview` 252 条、baseline 252 条，对账一致 | 明确保持“解压与来源文件中文映射都不属于工具职责”的边界；补强 CSV 空白行过滤；验证 `FILE_NAME` 仅保留原始文件名也可复用于整理后的支付宝汇总 CSV 目录 | `202605` 原始源目录只有 zip；实际可用输入是 Agent 预处理后的汇总 CSV 目录，并且需要排除重复/空账单文件后再调用 `run_recog_rollup`。若业务需要把 `来源文件` 映射成中文主体名，应放到汇总之后的后处理阶段，不放进当前工具 |

### shouqianba_settlement / 收钱吧回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-13 | `validate` 与 `preview` 通过，最新 `preview` 931 条、baseline 931 条，对账一致 | 复用 `FILE_NAME` 虚拟列与单选 `GROUP` 类型兼容；验证 `202605-source-excel/收钱吧` 目录模式无需额外预处理即可直接完成汇总阶段对账 | `202605` 样本直接使用 `收钱吧` xlsx 目录；该项目未出现额外业务差异或预处理边界问题 |

### douyin_voucher_settlement / 抖音回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-13 | 先修正远端配置并整理输入目录后，`validate` 通过、`preview` 成功产出 282 条，但与 baseline 220 条不一致；当前结论记为 `业务TBD` | 远端将 `分账明细-退款-团购` 的 `source_spec.optional` 改为 `true`；将 `达人佣金/撮合经纪服务费/服务商佣金/职人激励佣金/店员激励佣金` 的 source field 分别改为 `达人服务费/平台撮合服务费/服务商服务费/职人激励金/店员激励金`；Agent 预处理目录排除了 `洛阳上海市场-每日到账_业务账单_2026-05-01-2026-05-31_收益结算.xlsx` 这个异构文件 | 工程侧问题已收敛：在 `.tmp/douyin-rollup-ready-202605` 上 `validate` 通过，`preview` 成功生成 `282` 条结果；但 baseline 仅 `220` 条，且 `收款账号/收款户名/未结算金额/跨月结算金额/已结算金额` 全为空，同时 baseline 中 `券售卖金额负` 在 `220/220` 行都等于 `券售卖金额正`，而 preview 中仅 `168` 行非零，这说明历史 baseline 与现行规则口径存在明显业务差异，需要业务确认后再继续 |
| 2 | 2026-06-13 | 用户手动删除旧 baseline 后，现有 `--upload --upsert` 已成功上传 `preview` 产物；远端 `202605` 当前为 `283` 条，已定位到仅剩 1 条旧口径残留 | 直接使用 `.tmp/outputs/202605_douyin_voucher_settlement_20260613-145138.xlsx` 执行 `run_recog_rollup --upload --upsert`，成功写入 `282` 条、`21` 列到 `tblnsZ6GV3bHTW9y` | 回读显示远端包含 1 条残留旧记录 `recvlzQECIoFAU`：`平台ID=7461165927363512370`、`平台门店名称=蔡林记(江汉路店)`、`收款账号/收款户名=null`、`券售卖金额负=券售卖金额正=1746.49999999999`。对应新口径记录已存在：`recvmpDY2pC48q`，键为 `期间+平台ID+平台门店名称+收款账号+收款户名 = 202605/7461165927363512370/蔡林记(江汉路店)/招商银行 (0888)/武汉蔡林记主题餐饮有限公司`。删除该残留后，远端应收敛到 `preview` 的 `282` 条 |
| 3 | 2026-06-13 | 用户确认已手动删除最后 1 条江汉路店残留旧记录，当前项目直接判定通过并纳入稳定回归集合 | 无新增代码改动；本轮仅基于用户确认完成状态收尾与文档更新 | 本轮不再重复执行远端核验，结论依据为：`preview` 产物已成功上传 282 条，且上一轮已将唯一剩余残留记录精确定位为 `recvlzQECIoFAU`；用户确认该记录已删除，因此按当前业务确认将 `douyin_voucher_settlement` 标记为 `matched` |

## Update Rule

每轮结束后只做两件事：

1. 更新 `Project Status` 中该项目的 `status`、`last_round`、`next_action`、`latest_delta`
2. 在该项目的小表里追加一行，记录本轮 `result`、`delta`、`notes`

如果本轮结论是 `业务TBD` 或 `blocked`，必须把停止原因直接写进 `result` 或 `notes`，
让下一位接手的人不用重新撞一次墙。
