# Condition Expression Design

## 目的

本文定义 `run_recog_rollup` 中 `condition` 字段的设计方案，目标是：

- 保留接近 Python 的表达方式，不引入一套新的 DSL，降低 Agent 使用和编写门槛
- 严格限制可执行边界，避免 `condition` 退化为任意脚本执行入口
- 在不阻塞整体项目开发进度的前提下，优先支持现有确认项目中的条件汇总
- 为后续 helper 扩展、治理、自动检测和维护工具预留清晰边界

本文只讨论 `condition` 体系本身，不覆盖整个汇总工具的所有业务逻辑。

## 一、首版范围

### 1.1 首版目标

首版的核心目标不是把 condition 做成完整扩展平台，而是用最小方案跑通当前真实业务。

首版需要满足：

- 不阻塞 `run_recog_rollup` 主流程开发
- 支持当前已经存在的条件汇总
- 让 Agent 能在能力边界内稳定生成 condition
- 当能力不足时，Agent 能识别边界并明确告知用户

### 1.2 当前真实业务范围

当前所有确认项目中，条件汇总仅涉及以下两类：

1. 回款到账信息类，按结算时间过滤
2. 按某个 `GROUP` 型、值可枚举的源文件字段取某个值过滤

因此，首版只需覆盖：

- 基于结算时间的期间判断
- 基于单字段枚举值的等值或集合包含判断

### 1.3 首版不追求的内容

首版不追求：

- 开放式自定义 helper 平台
- Agent 自主创建和注册 helper
- 复杂跨字段、跨行、跨 sheet、跨文件条件逻辑
- 一次性实现完整 helper 治理工具链

## 二、condition 的语义边界

### 2.1 condition 的语义

`condition` 是针对“当前源数据记录”的单行布尔表达式。仅在 `SUM` 字段解析时使用，以支持按条件汇总。

- `condition` 为空：当前规则对所有行生效
- `condition` 非空：只有表达式求值为 `True` 的行参与该规则汇总
- `condition` 不负责做聚合
- `condition` 不负责跨行计算
- `condition` 不负责访问目标表或源文件环境

### 2.2 首版支持的表达式能力

首版建议支持以下能力：

- 布尔运算：`and`、`or`、`not`
- 比较运算：`==`、`!=`、`>`、`>=`、`<`、`<=`
- 成员判断：`in`、`not in`
- 括号分组：`(...)`
- 常量：字符串、数字、`True`、`False`、`None`
- 白名单运行时变量引用
- 白名单 helper 调用
- 统一字段访问：`F("字段名")`

首版不必为了当前业务额外开放复杂算术能力；如后续确有需要，再扩展 AST 白名单。

### 2.3 首版不支持的能力

首版明确不支持：

- 赋值语句
- `if/else` 语句块
- `for` / `while`
- `import`
- `lambda`
- 属性访问，如 `obj.attr`
- 下标访问，如 `obj[key]`
- 列表、字典、集合推导式
- 任意对象方法调用
- 任意模块函数调用
- 多行脚本

### 2.4 首版业务表达示例

当前两类真实业务场景，首版表达式应尽量收敛为以下形态：

```python
period_of(F("结算时间")) == current_period
period_of(F("结算时间")) == add_months(current_period, 1)
F("订单类型") == "堂食"
F("订单类型") in ["堂食", "外带"]
```

这几类表达式已经足以覆盖当前已知条件汇总需求。

## 三、字段访问统一写法与 `F` 的固定语义

### 3.1 统一写法

字段访问统一固定为：

```python
F("字段名")
```

### 3.2 为什么统一使用 `F("字段名")`

这是推荐的固定方案，理由如下：

- 避免出现“有的字段直接写变量、有的字段要特殊处理”的双轨规则
- 对所有字段一视同仁，规则写法更稳定
- 底层字段解析策略变化时，condition 本身不需要整体重写

### 3.3 `F` 的严格语义

`F` 的语义必须在设计上钉死，避免后续实现漂移。`F` 应满足以下约束：

- `F` 只允许接收一个字符串字面量参数
- `F("字段名")` 表示“从当前行上下文中，按已解析出的唯一字段名精确读取该字段原始值”
- `F` 只做读取，不做模糊匹配、不做 fallback、不做默认值填充
- `F` 不做隐式类型转换；字符串转数值、空值判断等由其他 helper 负责
- `F` 不接触分类、sheet、文件路径、工作簿对象等外部上下文
- `F` 不允许把字段不存在、字段重复等结构问题吞掉并返回静默默认值

### 3.4 `F` 不应承担的职责

以下能力不应由 `F` 承担：

- 自动猜字段别名
- 自动把日期、数字、布尔值做强制转换
- 依据项目、平台、文件名决定取哪个字段
- 在字段缺失时自动返回 `0`、空串或其他默认值

这些能力如果有需要，应分别落在：

- 结构校验阶段
- 明确命名的 helper
- 规则表配置
- 经人工确认后的框架级改造

## 四、首版运行时变量与内置 helper

### 4.1 首版运行时变量

首版只建议内置：

```python
current_period
```

保留理由：

- 它是当前业务中的明确高频上下文
- 它不暴露内部对象
- 它不把规则绑定到文件路径、部署方式或项目补丁机制

### 4.2 明确不建议内置的变量

| 变量名 | 是否建议内置 | 理由 |
|---|---|---|
| `recog_id` | 否 | helper 和 condition 不应按项目 id 分流；如果必须按项目分流，通常意味着它已经不是通用纯运算，而是项目特例逻辑 |
| `logical_sheet` | 否 | 当前规则本身已经显式绑定 `sheet`，条件表达式通常不应再依赖 sheet 名做业务分流 |
| `source_file_name` | 否 | 业务规则不应依赖文件名，否则会把目录治理、命名习惯耦合进汇总语义 |
| `source_file_path` | 否 | 会让规则依赖本地或云端部署路径，不适合作为稳定业务语义输入 |
| `dataset` / `worksheet` / `workbook` 等内部对象 | 否 | 会突破“条件表达式只做单行条件判断”的边界 |

### 4.3 首版内置 helper

首版只建议内置以下 helper：

| helper | 返回类型 | 说明 |
|---|---|---|
| `F(field_name)` | `Any` | 统一字段访问入口 |
| `is_blank(value)` | `bool` | 空值判断 |
| `has_value(value)` | `bool` | 非空判断 |
| `as_number(value)` | `float \| None` | 数值归一化 |
| `period_of(value)` | `str \| None` | 从结算时间提取期间 |
| `add_months(period, offset)` | `str` | 对期间做月偏移 |

说明：

- 第一类条件汇总依赖 `period_of` 与 `add_months`
- 第二类条件汇总只依赖 `F(...)` 和基础表达式能力
- 这已经足够跑通当前所有已知条件汇总

## 五、首版对 Agent 的能力边界

### 5.1 首版允许 Agent 做的事情

首版中，Agent 可以：

- 读取并理解现有 condition 设计
- 在规则表中编写和修改 `condition`
- 使用首版内置变量与内置 helper 组织表达式
- 在 validate 或 review 阶段识别 condition 超出当前能力边界

### 5.2 首版明确不允许 Agent 做的事情

首版中，Agent 不可以：

- 自主新增 helper
- 自主注册 helper
- 自主修改 helper 白名单
- 通过 project patch 或其他方式绕过 condition 边界

### 5.3 首版超出能力时的处理方式

如果用户提出的条件需求超出首版内置能力，Agent 应：

- 识别当前需求无法仅通过现有 `condition` 与内置 helper 表达
- 明确告知这是当前能力边界
- 不私自发明新 helper 或绕过框架边界
- 提醒用户联系开发者扩展 condition 能力或新增框架内置 helper

当前文档只界定这个 fallback 的产品边界，不定义完整交互细节。如何让 Agent 做到更丝滑的 fallback，仍需单独讨论设计。

## 六、`validate` 阶段如何检验 condition

### 6.1 validate 的职责

`validate` 负责对 `condition` 做结构性和可执行性校验，不负责替代业务口径评审。

首版目标是尽可能在 `preview` 之前拦住“结构上不可算”的问题，而不是裁定表达式是否符合最终业务含义。

### 6.2 首版建议优先实现的校验

为了不阻塞当前开发，首版 validate 至少应优先保证以下检查：

- `condition` 语法是否合法
- 是否只使用允许的 AST 节点
- `F` 的调用是否合法
- 是否只使用首版允许的 helper
- `F("字段名")` 引用字段是否存在且可唯一定位
- 基于采样行执行时不会报运行期错误
- 是否出现明显占位符，如 `CONDITION`

### 6.3 condition 校验的建议错误分类

condition 相关失败建议至少区分：

- `condition_parse_failed`
- `condition_ast_not_allowed`
- `condition_function_not_allowed`
- `condition_invalid_f_call`
- `condition_field_unresolved`
- `condition_placeholder_detected`
- `condition_runtime_error`

如未来引入更多 helper，再考虑增加如 `condition_helper_signature_mismatch` 等更细错误码。

### 6.4 validate 不应承担的职责

`validate` 不应承担以下职责：

- 直接替业务确认“这条规则口径是否正确”
- 依赖项目补丁或文件环境去推断表达式真实含义
- 放过结构问题并期待 preview 再兜底
- 因为表达式在一个样本行可运行，就默认它在所有业务情形下都合理

## 七、与 `project_patches` 的边界

仓库当前已有按项目作用域附加补丁的扩展点，即 [project_patches.py](src/core/rules/project_patches.py:1)。

condition 与 `project_patches` 的边界需要明确：

- condition 负责“当前行是否参与该条 SUM 汇总”
- 内置 helper 负责“字段值的单行纯运算”
- `project_patches` 负责“规则 bundle 的项目级小型补丁”

以下情况通常更像 `project_patches` 或更高层框架问题，而不是首版 condition 问题：

- 需要按项目 id 决定规则结构
- 需要改写规则集合本身
- 需要依赖目录、文件命名或外部环境
- 需要跨行、跨 sheet、跨文件做判断

## 八、未来自定义 helper 的完整设计

本章描述未来如果需要开放自定义 helper 时，应遵循的完整设计。它是演进方向，不属于首版必须实现内容。

### 8.1 自定义 helper 的定位

自定义 helper 的真实定位是：

- 面向字段值的通用纯运算
- 对内置 helper 的受控补充
- 为稳定复用场景提供命名明确的能力

自定义 helper 不应成为：

- 项目特例分支容器
- 业务黑箱
- 任意脚本执行通道
- 读取系统环境、文件、网络或全局状态的入口

### 8.2 自定义 helper 的硬约束

所有自定义 helper 必须满足以下硬约束：

- 只能处理显式传入的参数
- 只能做确定性纯计算
- 不允许隐式读取全局上下文
- 不允许接触外部环境
- 相同输入必须得到相同输出

明确禁止：

- 读写文件
- 发起网络请求
- 读取环境变量
- 读取系统当前时间、随机数、进程状态
- 访问工作簿、sheet、dataset、客户端对象
- 修改全局变量、缓存或外部对象
- 吞掉异常并静默返回业务默认值
- 通过项目 id、表 id、文件名等做分流

### 8.3 低认知复杂度约束

自定义 helper 除了要“能跑”，还要“容易被理解和维护”。因此建议同时满足：

- 单一职责，一个 helper 只表达一个稳定语义
- 参数尽量少
- 避免多层嵌套分支
- 避免把完整业务口径折叠进一个巨型 helper
- 优先返回简单标量，如 `bool`、`str`、`float`、`None`

### 8.4 文件形态与导出接口

自定义 helper 统一收敛到：

```text
src/core/rules/custom_condition_helpers.py
```

主框架通过稳定接口暴露自定义 helper，例如：

```python
def get_custom_condition_helpers() -> dict[str, callable]:
    ...
```

即使未来开放，也不建议设计为按 `recog_id` 暴露 helper。

### 8.5 元数据与维护工具箱

未来每个 helper 至少应维护：

- `name`
- `summary`
- `signature`
- `return_type`
- `tags`
- `status`
- `examples`
- `notes`

同时建议配套维护工具箱，至少包含：

- helper 列表导出工具
- helper 校验工具
- helper 约束扫描工具
- helper 使用检索工具
- helper 变更影响报告

### 8.6 白名单治理建议

未来如果开放 helper 扩展，新增或修改 helper 时，提交中至少应同时包含：

- helper 代码实现
- 完整 docstring
- 对应元数据
- 至少一个正向单元测试
- 至少一个边界或异常测试
- 一个真实表达式使用示例
- 若为修改，还应附带影响说明

同时建议在提交阶段做自动检测，至少包括：

- 检查 helper 是否具备 docstring
- 检查 helper 是否已注册到白名单
- 检查元数据是否完整
- 检查是否存在禁用 import、禁用模块调用或外部环境访问
- 检查是否引用未声明的自由变量
- 检查是否存在缺失测试的 helper

## 九、不可动与可动边界

### 9.1 不可动边界

以下内容属于主框架稳定层，正常业务扩展不应直接修改：

- `src/core/rules/rule_engine.py`
- `src/core/preview/preview_stage.py`
- `src/core/validation/validate_stage.py`
- `src/core/source_resolver.py`

这些模块负责：

- 表达式安全边界
- 条件校验
- 条件执行
- 错误定位

### 9.2 首版默认可动边界

首版中，Agent 默认可动内容限定为：

- 汇总规则表中的 `condition`

首版不包含：

- Agent 自主新增 helper
- Agent 自主注册 helper
- Agent 自主修改 helper 白名单

### 9.3 未来开放扩展后的可动边界

未来如果开放自定义 helper 扩展，可动内容再逐步扩展到：

- `src/core/rules/custom_condition_helpers.py` 中的受管 helper 定义区
- helper 元数据
- 对应 helper 的单元测试
- helper 白名单治理工具与检测脚本

### 9.4 需人工确认后方可改动的内容

- 通用 helper 列表
- 运行时变量列表
- AST 白名单
- `condition` 整体执行语义
- `F` 的固定语义
- 自定义 helper 的统一导出接口
- helper 自动检测规则本身

## 十、最简首版落地方案

### 10.1 首版能力清单

首版只内置：

```python
current_period
F
is_blank
has_value
as_number
period_of
add_months
```

### 10.2 首版承诺支持的条件汇总类型

首版仅承诺支持以下两类条件汇总：

1. 按 `结算时间` 做期间过滤
2. 按单个可枚举 `GROUP` 字段的值做过滤

### 10.3 首版不支持的内容

- Agent 自主创建 helper
- Agent 自主注册 helper
- 依赖新自定义 helper 的业务表达能力
- 复杂跨字段、跨阶段、跨行或跨文件条件判断

### 10.4 首版超出能力时的处理方式

如果用户提出的条件需求超出首版内置能力，Agent 应：

- 明确说明当前 condition 首版无法表达该需求
- 不尝试私自发明新 helper 或绕过框架边界
- 建议联系开发者扩展内置 helper 或 condition 能力

具体如何把这套提醒做得更丝滑、更产品化，仍需后续单独设计。

## 十一、结论

本方案具备以下特征：

- 首版范围收敛，只服务当前真实已出现的两类条件汇总
- 不再保留双轨字段写法，统一只用 `F("字段名")`
- 通过严格定义 `F` 的语义，避免字段访问规则漂移
- 运行时变量压缩为真正必要的最小集合
- 首版以内置 helper 为主，不开放 Agent 自主创建 helper
- 当需求超出首版能力时，Agent 需要识别边界并提醒用户联系开发者扩展能力
- 完整的 helper 治理、工具、检测与维护设计保留为未来演进方案

本方案适用于后续 skill 化演进：

- 当前项目开发不会被 condition 设计过度前置而阻塞
- Agent 容易学会
- Agent 不容易误改核心框架
- 后续业务扩展仍有稳定入口
- condition 的结构校验和 helper 治理都有清晰边界
