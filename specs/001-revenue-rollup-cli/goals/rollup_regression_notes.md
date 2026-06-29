# Rollup Regression Notes

## 2026-06-17

### dine_in_revenue / 堂食收入

- `validate`：通过
  抽样/输入文件：`202605-source-excel/收银汇总表 202605-202605(2026-06-01 09_43_35)_888.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_dine_in_revenue_20260617-203120.xlsx`
- `baseline` 对账：不一致
  `preview_count=297`，`baseline_count=297`
- 当前已定位差异：
  联合键显示为 `期间=null, 全来店ID=10180`
  字段 `支付宝神券`：`preview=130.86`，`baseline=151.96`
- 当前判断：
  这是本轮回归发现的首个真实字段值差异，先记录，不在 14 个项目全部跑完前改代码
- 待确认点：
  对账输出中的联合键 `期间` 显示为 `null`，需要在后续统一复核这是否只是对账展示噪音，还是当前产物中 `期间` 字段存在缺失
- 2026-06-18 溯因补充：
  用 preview 元数据动态回放后，联合键实际是 `期间 + 全来店ID`，唯一差异键准确为 `202605 + 10180`；此前看到的 `期间=null` 来自临时诊断脚本里的中文键编码噪音，不是 preview 结果缺少 `期间`
  回查 `202605-source-excel/收银汇总表 202605-202605(2026-06-01 09_43_35)_888.xlsx` 原始行，门店 `10180 / 蔡林记同济店` 的源字段 `支付宝神券` 实际值就是 `130.86`，与 preview 完全一致
  当前判断进一步收敛为：本地汇总代码没有把 `支付宝神券` 算错，更像是目标表 `tbl362y6MNstoTnE` 的 `202605` baseline 中该门店记录仍保留旧口径值 `151.96`，或曾被人工调整过
- 2026-06-18 处理结果：
  已按用户指令直接执行 `run_recog_rollup --upload --upsert --recog_id dine_in_revenue --result_file .tmp/outputs/202605_dine_in_revenue_20260617-203120.xlsx`
  上传返回 `row_count=297`、`field_count=32`；随后按同一 preview 产物回读目标表 `tbl362y6MNstoTnE` 的 `202605` baseline，结果为 `preview_count=297`、`baseline_count=297`、`difference_count=0`

### member_collection / 代收会员储值

- `validate`：通过
  抽样/输入文件：`202605-source-excel/收入收款方式构成表 20260501-20260531(2026-06-01 09_53_29)_888.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_member_collection_20260617-214156.xlsx`
- `baseline` 对账：一致
  `preview_count=231`，`baseline_count=231`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### wechat_pay_settlement / 微信回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/微信/会员商城.csv`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_wechat_pay_settlement_20260617-214415.xlsx`
- `baseline` 对账：一致
  `preview_count=486`，`baseline_count=486`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### alipay_settlement / 支付宝回款

- `validate`：通过
  抽样/输入文件：`.tmp/alipay-summary-202605/张林交易账单-1.csv`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_alipay_settlement_20260617-214514.xlsx`
- `baseline` 对账：不一致
  `preview_count=355`，`baseline_count=252`
- 当前已定位差异：
  `difference_count=607`
  样例显示联合键中 `期间` 为 `null`，且存在大量 `missing_in_baseline / missing_in_preview`
- 当前判断：
  这一轮更像是输入口径或 baseline 归属范围不一致，不先改代码，继续记录后再做业务确认
- 2026-06-18 溯因补充：
  用 preview 元数据动态回放后，联合键实际是 `期间 + 门店编号 + 来源文件`；此前样例里出现的 `期间=null` 同样来自临时诊断脚本中的中文键编码噪音，不是 preview 或 baseline 真缺 `期间`
  当前 `607` 条差异全部可以收敛为 `来源文件` 口径不一致，而不是金额聚合错误：本轮 preview 使用 `.tmp/alipay-summary-202605`，目录内共有 `9` 个原始文件名来源，因此产出 `355` 条；baseline 当前保存的是 `7` 个主体名来源口径，因此是 `252` 条
  已复核历史对齐产物 `.tmp/outputs/202605_alipay_settlement_20260613-140218.xlsx` 和 `.tmp/outputs/202605_alipay_settlement_20260617-090936.xlsx`：它们都使用主体名作为 `来源文件`，分别对应 `.tmp/alipay-rollup-ready-202605` 里的 `武汉市蔡林记餐饮发展有限公司.csv`、`张林.csv`、`换乘.csv`、`武汉蔡林记餐饮管理有限公司.csv`、`蔡林记（郑州）餐饮服务有限公司.csv`、`蔡林记商业餐饮管理有限公司.csv`、`武汉蔡林记主题餐饮有限公司.csv`，因此与 baseline 的 `252` 条完全一致
  本轮误用的 `.tmp/alipay-summary-202605` 中，`张林交易账单-1.csv` 与 `张林资金账单-3.csv` 的明细行数与金额完全相同，属于同一主体被拆成两个原始文件；目录里还存在 `商贸交易账单-0.csv` 与 `餐饮交易账单-0.csv` 等原始文件名口径，工具按 `FILE_NAME=source_file.stem` 分组后会自然产出更多 `来源文件` 键
  当前判断进一步收敛为：问题首先是输入目录/预处理产物选错，不是汇总算法计算错误；若要复现与结果表 `tblRqpGT6MMq3V6M` 一致的现行 baseline 口径，应继续使用去重并重命名后的 `.tmp/alipay-rollup-ready-202605`
- 2026-06-18 错误输入文件明细：
  真正导致本轮从 `252` 条膨胀到 `355` 条的多余文件只有两份：
  `张林资金账单-3.csv`：与 `张林交易账单-1.csv` 内容同量同额，属于同一主体 `张林` 的重复文件，额外引入 `59` 条
  `商贸交易账单-0.csv`：当前 baseline 对应的正确输入集中没有这份文件，额外引入 `44` 条
  两者合计正好是 `103` 条，也就是 `355 - 252`
  其余 `7` 份原始文件虽然金额口径本身可用，但不能直接用于和当前 baseline 对账，因为 `来源文件` 键还是原始文件名而不是主体名；对应关系如下：
  `主题交易账单-1.csv -> 武汉蔡林记主题餐饮有限公司.csv`
  `发展交易账单-0.csv -> 武汉市蔡林记餐饮发展有限公司.csv`
  `商业交易账单-1.csv -> 蔡林记商业餐饮管理有限公司.csv`
  `张林交易账单-1.csv -> 张林.csv`
  `换乘交易账单-0.csv -> 换乘.csv`
  `郑州交易账单-0.csv -> 蔡林记（郑州）餐饮服务有限公司.csv`
  `餐饮交易账单-0.csv -> 武汉蔡林记餐饮管理有限公司.csv`

### shouqianba_settlement / 收钱吧回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/收钱吧/武汉蔡林记餐饮管理有限公司.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_shouqianba_settlement_20260617-214728.xlsx`
- `baseline` 对账：一致
  `preview_count=931`，`baseline_count=931`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### douyin_voucher_settlement / 抖音回款

- `validate`：通过
  抽样/输入文件：`.tmp/douyin-rollup-ready-202605/麻城广场-账单_2026-05-01_2026-05-31.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_douyin_voucher_settlement_20260618-100212.xlsx`
  备注：CLI 结果已成功返回，但本次命令执行耗时超过我给的 `120s` 窗口，外层工具把它标成 timeout；不影响产物本身可用
- `baseline` 对账：一致
  `preview_count=282`，`baseline_count=282`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### meituan_voucher_settlement / 美团团购回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/美团团购/收益明细/总账号-新版收益明细_2026-05-01~2026-05-31_团购_1105325132026060210-2076965380.xlsx`
  备注：`validate` 实际成功返回，但执行耗时超过我给的默认窗口，外层工具将命令标记为 timeout；不影响返回结果本身可用
- `preview`：通过
  结果文件：`.tmp/outputs/202605_meituan_voucher_settlement_20260618-100942.xlsx`
- `baseline` 对账：一致
  `preview_count=273`，`baseline_count=273`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### meituan_delivery_revenue / 美团外卖收入

- `validate`：通过
  抽样/输入文件：`202605-source-excel/美团外卖收入/门店_蔡林记（文理理工学院食堂二楼店）_20260501_20260531_wmclj323955_2026-06-01+14_34_17.csv`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_meituan_delivery_revenue_20260618-101123.xlsx`
- `baseline` 对账：一致
  `preview_count=237`，`baseline_count=237`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### meituan_delivery_settlement / 美团外卖回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/美团外卖回款/全部门店2026-05-01~2026-05-31订单-1780291683243-60231828.zip-2.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_meituan_delivery_settlement_20260618-105320.xlsx`
  备注：CLI 结果已成功返回，但目录级大工作簿耗时超过外层工具窗口，命令被标记为 timeout；不影响产物本身可用
- `baseline` 对账：一致
  `preview_count=237`，`baseline_count=237`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### eleme_delivery_revenue / 饿了么收入

- `validate`：通过
  抽样/输入文件：`202605-source-excel/饿了么收入/1780292262779-蔡林记(武当山店)2026.05.01-2026.05.31账单.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_eleme_delivery_revenue_20260618-110305.xlsx`
  备注：CLI 结果已成功返回，但目录级 Excel 汇总耗时超过外层工具窗口，命令被标记为 timeout；不影响产物本身可用
- `baseline` 对账：一致
  `preview_count=232`，`baseline_count=232`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### eleme_delivery_settlement / 饿了么回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/饿了么回款/1780285622895-蔡林记(越苑食堂店)2026.05.01-2026.05.31账单.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_eleme_delivery_settlement_20260618-111649.xlsx`
  备注：CLI 结果已成功返回，但目录级 Excel 汇总耗时超过外层工具窗口，命令被标记为 timeout；不影响产物本身可用
- `baseline` 对账：一致
  `preview_count=232`，`baseline_count=232`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### jingdong_delivery_revenue / 京东外卖收入

- `validate`：通过
  抽样/输入文件：`202605-source-excel/京东外卖收入/1012680_对账单下载_20260531_全部_5910244_5910249_0.xlsx`
  备注：`validate` 实际成功返回，但目录级大工作簿耗时超过外层工具窗口，外层工具将命令标记为 timeout；不影响返回结果本身可用
- `preview`：通过
  结果文件：`.tmp/outputs/202605_jingdong_delivery_revenue_20260618-114020.xlsx`
  备注：CLI 结果已成功返回，但目录级大工作簿耗时超过外层工具窗口，命令被标记为 timeout；不影响产物本身可用
- `baseline` 对账：一致
  `preview_count=188`，`baseline_count=188`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### jingdong_delivery_settlement / 京东外卖回款

- `validate`：通过
  抽样/输入文件：`202605-source-excel/京东外卖回款/1012680_对账单下载_20260531_全部_5910244_5910250_0.xlsx`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_jingdong_delivery_settlement_20260618-114655.xlsx`
  备注：目录级工作簿体量较大，但本轮 `preview` 在扩大的外层窗口内成功完成，无需重跑
- `baseline` 对账：一致
  `preview_count=188`，`baseline_count=188`
- 当前判断：
  本轮单项目回归已通过，可继续下一个项目

### amap_voucher_settlement / 高德回款

- `validate`：通过
  抽样/输入文件：`.tmp/amap-202605-detail-only/10360442_202605__10360442_202605_口碑商品核销账单明细.csv`
- `preview`：通过
  结果文件：`.tmp/outputs/202605_amap_voucher_settlement_20260618-121911.xlsx`
- `baseline` 对账：一致
  `preview_count=99`，`baseline_count=99`
- 当前判断：
  本轮单项目回归已通过，14 个注册项目已全部覆盖

## 本轮汇总

- 已完成 14/14 个注册项目的 `validate + preview + 202605 baseline` 回归
- 对账一致：12 项
- 对账不一致：2 项
  `dine_in_revenue`
  `alipay_settlement`
- 当前不一致项均已写入上方项目记录，且遵守约束：在 14 项全部跑完前未改业务代码

## 工程观察

- `shouqianba_settlement` 这次 baseline 拉取“看起来很慢”的根因不是飞书结果太多，而是当前 `records/search` 的分页实现把 `page_token` 放进了 `POST body`
- 对 `收钱吧` 结果表实测：
  第一页 `page_size=500` 约 `1.2s`
  如果把 `page_token` 放进 body，第 2 页会重复返回第 1 页，且 `next_page_token` 仍是同一个值
  如果把 `page_token` 放进 query params，第 2 页会正确返回剩余 `431` 条并结束
- 这说明当前 `BitableApiClient.search_records` / `_paginate_with_body` 的分页方式存在工程缺陷，后续若继续用 baseline helper 或 upload 侧搜索大表，需要优先修这个实现
