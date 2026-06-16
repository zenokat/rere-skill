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
| eleme_delivery_revenue | 饿了么收入 | matched | 2 | 保持在稳定回归集合中；后续若再出现 baseline 缺记录或目录内门店账单归属争议，优先回归该项目 | 已确认 `202605` baseline 缺少 1 条 `平台ID=163007972` 记录；使用 `upload --upsert` 将 `preview` 232 条补齐到结果表并完成对账 |
| eleme_delivery_settlement | 饿了么回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现期间或联合键问题，优先回归该项目 | 修复大账单流式读取、只读模式维度误判、忽略 `~$` 临时文件；补强联合键归一化与字段类型规范化 |
| member_collection | 代收会员储值 | matched | 1 | 保持在稳定回归集合中；后续若再出现源表多层表头或 baseline 类型噪音，优先回归该项目 | 修正远端 `category_row/category/optional` 配置；补强 baseline 数字字符串归一化 |
| wechat_pay_settlement | 微信回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 CSV 反引号、虚拟来源文件字段或缺失平台ID 聚合问题，优先回归该项目 | 增加 `FILE_NAME` 虚拟列、放宽单选 GROUP 类型校验、清洗 CSV 反引号并回填缺失 `平台ID` 后重聚合 |
| alipay_settlement | 支付宝回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 Agent 预处理目录过滤、空汇总文件剔除或 CSV 空白行问题，优先回归该项目 | 保持“解压与来源文件中文映射都不属于工具职责”边界；补强 CSV 空白行过滤；验证保留原始文件名的真实源目录可完成汇总阶段对账 |
| shouqianba_settlement | 收钱吧回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 `xlsx` 目录模式、`FILE_NAME` 虚拟列或支付方式单选字段问题，优先回归该项目 | 复用 `FILE_NAME` 虚拟列与单选 GROUP 类型兼容；验证 `202605-source-excel/收钱吧` 目录可直接完成对账 |
| douyin_voucher_settlement | 抖音回款 | matched | 3 | 保持在稳定回归集合中；后续若再改 `upsert` 语义或抖音回款口径，优先回归该项目 | 用户已接受现行 `preview` 口径并手动清理最后 1 条旧残留；现有 `upsert` 已成功将 `preview` 282 条上传到结果表 |
| jingdong_delivery_revenue | 京东外卖收入 | matched | 1 | 保持在稳定回归集合中；后续若再出现目录内空分页分片或超大工作簿流式读取边界问题，优先回归该项目 | 允许 `last_row=-1` 的表头空分片返回零行数据集并跳过；`202605` 整目录 `preview` 188 条、baseline 188 条，对账一致 |
| jingdong_delivery_settlement | 京东外卖回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现到账信息并表、双表对账或上传字段元数据性能问题，优先回归该项目 | 远端补齐 5 条到账信息 condition；按主表与旧“回款到账信息”表双口径对账通过后，用户手动删除旧口径记录并完成 `upload --upsert` |
| amap_voucher_settlement | 高德回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现 zip 预处理、明细/汇总混放目录输入或全角半角括号噪音问题，优先回归该项目 | 先将 zip 预处理为仅含“口碑商品核销账单明细.csv”的干净目录；补强对账与上传联合键的括号归一化后，`202605` `preview` 99 条、baseline 99 条，对账一致 |
| meituan_voucher_settlement | 美团团购回款 | matched | 3 | 保持在稳定回归集合中；后续若再出现 read_only workbook dimension 失真、单源收益明细原子字段或到账字段规则问题，优先回归该项目 | 新口径 `preview` 已完成 `upload --upsert` 并与影子结果表对账一致；旧“回款到账信息”表仅余 1 条缺口，经业务确认忽略，不再构成阻塞 |
| meituan_delivery_revenue | 美团外卖收入 | matched | 1 | 保持在稳定回归集合中；后续若再出现中文 CSV 编码、目录内双 schema 或下游平台服务费公式问题，优先回归该项目 | 补强 CSV `gb18030` 解码回退；规则改为分别产出 `佣金`、`配送服务费`、`平台服务费(含佣金和配送服务费)` 三个基础字段；本地新增 SUM 输出字段唯一性校验 |
| meituan_delivery_settlement | 美团外卖回款 | matched | 1 | 保持在稳定回归集合中；后续若再出现交易类型条件过滤或占位符数值归一化问题，优先回归该项目 | 远端修正 `调整项/外卖账单结算金额` 的 condition；本地将 `-` 一类占位符归一为数值 0，消除 `float('-')` 型 preview 失败 |

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

### eleme_delivery_revenue / 饿了么收入

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | `validate` 与 `preview` 通过，但 `preview` 232 条、baseline 231 条，不一致；差异收敛为 baseline 缺少 1 条记录，继续跟进 | 确认联合键为 `期间 + 平台ID`；定位唯一差异键为 `202605 + 163007972`，并追溯到 `1780983624362-蔡林记(清河路店)2026.05.01-2026.05.31账单.xlsx` 的真实源账单记录 | 当前差异不是工程聚合错误，而是结果表 `tbl78CSsQ23uDG0S` 的 `202605` baseline 缺少该门店记录；待业务确认后再决定是否直接补齐 |
| 2 | 2026-06-14 | 用户确认 baseline 确实缺少该条记录后，已执行 `run_recog_rollup --upload --upsert`；回读结果为 `preview` 232 条、baseline 232 条，对账一致 | 直接使用 `.tmp/outputs/202605_eleme_delivery_revenue_20260614-133951.xlsx` 执行 `upload --upsert`，成功写入目标表 `tbl78CSsQ23uDG0S`；随后按 `202605` 回读远端并完成对账确认 | 本轮以 `期间 + 平台ID` 为联合键；`upload` 成功返回 `row_count=232`、`field_count=11`，当前项目已纳入稳定回归集合 |

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

### jingdong_delivery_revenue / 京东外卖收入

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | `validate` 通过；整目录 `preview` 初次失败后定位到目录中存在仅含两行表头、无数据体的分页空分片，修复后 `preview` 188 条、baseline 188 条，对账一致 | 本地放宽 `last_row=-1` 的“表头空分片”边界：对只有表头、没有数据行的超大工作簿流式路径返回零行数据集而不是报空区间错误；补充 `test_streaming_sheet_dataset_allows_header_only_excel_when_last_row_is_to_end` 定向单测 | `202605-source-excel/京东外卖收入` 目录内 `1012680_对账单下载_20260531_全部_5910244_5910249_1.xlsx` 只有两行表头，文件大小仅 `5182` 字节；当前以 `期间 + 平台ID` 为联合键，与结果表 `tblRt2KjEUHcEQPZ` 的 202605 baseline 完全一致 |

### jingdong_delivery_settlement / 京东外卖回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | 用户补齐当前结果表中的 5 个到账信息字段并手动删除旧口径 `202605` 记录后，`validate`、`preview`、双表对账与 `upload --upsert` 全部通过；回读结果为 `preview` 188 条、baseline 188 条，对账一致 | 远端为 `-保险费`、`保险理赔`、`未结算金额`、`已结算金额`、`跨月结算金额` 补齐真实 condition；按当前结果表与旧“回款到账信息”表拆分对账；本地为上传仓储增加字段元数据缓存，消除同表重复拉取元数据导致的 `upsert` 超时 | 当前结果表 `tblQkl5JlhKAcBAB` 中其余字段与 `preview` 按 `期间 + 平台ID` 对账一致；5 个到账信息字段与旧表 `tblcswGGH3CWqlri` 按新口径联合键 `期间 + 平台ID + 收款账号 + 收款户名` 聚合后对账一致；最终通过 `.tmp/outputs/202605_jingdong_delivery_settlement_20260614-153854.xlsx` 完成 `upload --upsert` |

### amap_voucher_settlement / 高德回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | 先将原始 zip 预处理为仅含“口碑商品核销账单明细.csv”的干净目录后，`validate` 与 `preview` 通过；补齐括号全角/半角文本归一化后，`preview` 99 条、baseline 99 条，对账一致 | 使用临时目录 `.tmp/amap-202605-detail-only` 承接从 `202605-source-excel/高德/*.zip` 解出的两份明细 CSV，明确“汇总 CSV 混入目录会导致 `preview` 报缺字段”；本地新增共享文本归一化 helper，并将全角/半角括号统一纳入 baseline 对账归一化与 upload 联合键归一化，补充 `test_normalize_record_unifies_fullwidth_parentheses`、`test_compare_preview_to_baseline_unifies_parenthesis_variants_in_keys`、`test_build_upsert_key_unifies_parenthesis_variants` | 真实可消费输入不是 zip 目录本身，而是预处理后的明细 CSV 目录；`validate` 抽检文件为 `10473438_202605__10473438_202605_口碑商品核销账单明细.csv`；当前以 `期间 + 平台ID` 为联合键，对账前仅剩 4 个门店名的括号全角/半角差异，修复后 `difference_count=0` |

### meituan_delivery_revenue / 美团外卖收入

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | 修正工程侧 CSV 编码问题，并将双 schema 兼容方案收敛为三个基础事实字段后，`validate` 与 `preview` 通过；`preview` 237 条、baseline 237 条，对账一致 | 本地补强 CSV `gb18030` 解码回退；远端规则分别产出 `佣金`、`配送服务费`、`平台服务费(含佣金和配送服务费)` 三个可选 SUM 基础字段；本地新增 SUM 输出字段唯一性校验，禁止再用多条规则累加同一业务字段 | `202605-source-excel/美团外卖收入` 目录同时存在“拆分列 schema”和“合并列 schema”；当前汇总阶段只产出基础事实字段，下游飞书公式字段 `平台服务费` 负责将 `佣金 + 配送服务费 + 平台服务费(含佣金和配送服务费)` 汇总为最终业务字段；当前以 `期间 + 平台ID` 为联合键，对账已与结果表 `tbl5KtaRvsWge30r` 的 202605 baseline 完全一致 |

### meituan_voucher_settlement / 美团团购回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | 先摘除远端串挂到账信息规则并修正工程侧空白 Excel 行处理后，`validate` 与 `preview` 通过；`preview` 236 条、baseline 236 条，对账一致 | 远端将误挂在 `meituan_voucher_settlement` 上的 `收款账号/未结算金额/跨月结算金额/已结算金额` 四条规则从项目上摘除，并将唯一 `source_spec` 改为 `optional=true` 以跳过目录中的“收益明细”文件；本地在 `source_resolver` 中跳过普通/流式两条路径上的 Excel 全空白数据行，并补充定向单测 | 当前注册表 `bitable_table_id=tblv7qBT9AgLiDOT` 对应的是 236 行的“团购汇总表”口径，而不是 271 行的“美团团购回款到账信息”口径；当前以 `期间 + 平台ID + 平台门店名称` 为联合键，对账已与结果表 `tblv7qBT9AgLiDOT` 的 202605 baseline 完全一致 |
| 2 | 2026-06-15 | 按“单一源文件 + 原子字段”新口径完成远端迁移后，`validate` 与 `preview` 均通过；当前 `preview` 产物为 273 条、15 列，后续需再按新口径补做 baseline 对账与上传 | 远端将唯一 `source_spec` 切换为 `收益明细`；将 `平台ID/平台门店名称/实际回款/售价/收款账号/未结算金额/跨月结算金额/已结算金额` 规则全部改挂 `收益明细`；将旧 `促销费/平台服务费` 拆为 `商家承担促销费-随单抵扣/商家承担促销费-营销账户余额抵扣/商家承担促销费-配送费减免/服务费（平台实际扣除）/合作商商业支持费用/服务费-配送费` 六个原子字段，并在影子业务数据库中新增对应数值列；将结果表原 `促销费/平台服务费` 改为公式字段；本地修复 read_only workbook stale dimension 导致的 streaming preview 截断，并补充 `test_prepare_read_only_worksheet_resets_stale_dimensions_even_when_max_row_is_not_one` | 旧 round 1 的“收益列表口径 matched”已因产品约束变更失效：新口径要求一个确认项目只允许单一源文件，且 rollup 不能再用多条规则共同累加同一业务字段。迁移后使用 `202605-source-excel/美团团购/收益明细` 运行：`validate` 抽样文件为 `总账号-新版收益明细_2026-05-01~2026-05-31_团购_1105325132026060210-2076965380.xlsx`，`preview` 成功产出 `.tmp/outputs/202605_meituan_voucher_settlement_20260615-222950.xlsx`；当前输出字段为 `期间/平台ID/平台门店名称/收款账号/服务费（平台实际扣除）/实际回款/售价/商家承担促销费-随单抵扣/未结算金额/跨月结算金额/已结算金额/商家承担促销费-营销账户余额抵扣/商家承担促销费-配送费减免/合作商商业支持费用/服务费-配送费`，需再与旧到账信息表及新影子表按新口径补做 baseline 对账 |
| 3 | 2026-06-16 | 用户确认忽略旧“回款到账信息”表中仅剩的 1 条缺口后，当前项目按完成收口并纳入稳定回归集合 | 无新增代码改动；本轮仅基于已完成的 `upload --upsert`、影子结果表对账结果与业务确认更新状态文档 | 新口径 `preview` 已成功上传到 `tblv7qBT9AgLiDOT`，回读结果为 `preview` 273 条、baseline 273 条、`difference_count=0`；旧到账信息表 `tblu4dGHMDpKPfge` 仍缺 `平台ID=1022770755596475` 这 1 条记录，但已确认按业务忽略，不再作为阻塞项 |

### meituan_delivery_settlement / 美团外卖回款

| round | date | result | delta | notes |
|---|---|---|---|---|
| 1 | 2026-06-14 | 先修正远端 condition，再补齐工程侧数值归一化后，`validate` 与 `preview` 通过；`preview` 237 条、baseline 237 条，对账一致 | 远端将 `调整项` 改为 `F("交易类型") == "调整项"`，将 `外卖账单结算金额` 改为 `F("交易类型") in ["外卖订单", "订单部分退款", "部分退款冲抵", "订单退款"]`；本地把 `-`、长短横线类纯占位符归一为数值 `0`，并补充规则引擎单测 | 用户已明确“实际回款不是条件汇总，而是数值归一化问题”；当前以 `期间 + 平台ID + 结算id` 为联合键，对账已与结果表 `tblnuOGqHci3TRnr` 的 202605 baseline 完全一致 |

## Update Rule

每轮结束后只做两件事：

1. 更新 `Project Status` 中该项目的 `status`、`last_round`、`next_action`、`latest_delta`
2. 在该项目的小表里追加一行，记录本轮 `result`、`delta`、`notes`

如果本轮结论是 `业务TBD` 或 `blocked`，必须把停止原因直接写进 `result` 或 `notes`，
让下一位接手的人不用重新撞一次墙。
