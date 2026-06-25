# 收入确认 WorkBuddy 自动化评测底座

## 这是什么

这是一套给“评测执行者”使用的评测底座。

它的目标不是只跑通一次收入确认 skill，而是让团队可以稳定地：

1. 准备一组固定 case
2. 批量发起评测
3. 自动收集结果和证据
4. 自动评分
5. 保存成 baseline
6. 下一轮继续重跑并比较差异

如果把它当成一个产品来看，可以把它理解成：

“一套面向收入确认 skill 的自动化评测流水线产品。”

## 这个产品，用户是怎么使用它的

从评测执行者视角看，完整旅程可以分成 4 步，外加两类高级配置动作。

### 第 1 步：先定义我要评什么

这一层对应 [case-manifest.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/case-manifest.md)。

你要先准备一份 case manifest，告诉 harness：

- 这次要跑哪些 case
- 每个 case 的任务说明是什么
- 它的输入材料是什么
- 它预期是“成功跑通”，还是“正确止步”，还是“环境失败”
- 它重点看哪些评分维度
- 它默认使用什么安全和隔离策略

可以把它理解成：

“评测任务清单”。

这一步和新补充设计的关系是：

- 如果某类 case 只能在安全环境下运行，要在这里声明
- 如果这套 case 默认只读，或者需要特定的隔离方式，也是在这里表达

### 第 2 步：发起一批评测

这一层对应 [run-eval-batch.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/run-eval-batch.md)。

你把 case manifest 交给 harness，然后发起一次 batch。

harness 会负责：

- 逐条 case 去调用被测 skill
- 为每条 case 创建独立运行记录
- 为每条 case 创建独立工作目录
- 收集运行过程中的证据
- 按写策略决定是否阻断 upload 或真实外部写动作
- 形成整批的结果目录

可以把它理解成：

“批量执行入口”。

### 第 3 步：查看这次跑出来了什么

这一层对应 [result-bundle.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/result-bundle.md)。

跑完后，你会拿到一整套结果包，而不是只有一个“成功/失败”。

主要会看到两类结果：

- 给机器/Agent看的结构化结果
  - `batch.json`
  - `run.json`
  - `scorecard.json`

- 给人看的可读结果
  - `summary.md`
  - `evidence.md`

这一步你能回答：

- 哪些 case 通过了
- 哪些 case 正确止步了
- 哪些 case 是环境失败
- 哪些 case 证据不完整
- 哪些 case 是因为安全策略被阻断
- 下一轮更应该先改 skill、工具、环境还是 harness

可以把它理解成：

“评测结果包”。

### 第 4 步：把这轮结果沉淀为 baseline，并用于以后比较

这一层对应 [baseline-snapshot.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/baseline-snapshot.md)。

你可以把一轮结果保存成 baseline。以后再跑同一组 case 时，就拿新结果和 baseline 做比较。

这样你就能知道：

- 哪些 case 没变化
- 哪些修复了
- 哪些退化了
- 哪些由于版本、评分器配置或证据问题暂时不可比

可以把它理解成：

“把一次评测结果变成以后持续比较的标准答案快照”。

这里和新补充设计直接相关的是：

- baseline 不只保存结果，还会保存评分器版本、评测设置和环境策略
- 所以后面比较时，不只是比“分数变了没”，也比“这次是不是还在同一套评分和隔离规则下运行”

## 两类高级配置动作

上面的 4 步已经覆盖主用户旅程。除此之外，现在还多了两类“高级使用方式”。

### 高级动作 1：扩展评分器

这块能力没有新增独立入口，而是挂在现有的评测设置体系里。

站在评测执行者视角，它的使用方式是：

1. 先由开发侧在 `graders/` 目录实现一个新评分器
2. 把它注册成系统认识的评分器定义
3. 再通过 `EvalSettingsProfile` 决定本轮要不要启用它

所以对执行者来说，交互点主要还是现有两处：

- `case manifest`
  表达某条 case 重点看哪些评分维度
- `settings profile`
  表达本轮启用哪些评分器、执行顺序是什么

也就是说：

- “写评分器实现”本身更偏扩展系统能力
- “启用哪个评分器”才是评测执行者和系统的交互

这也是为什么目前没有单独拆出新的 contract：因为它还没有形成一条新的主入口，而是挂接在现有的 `manifest + settings + scorecard` 这条主链上。

### 高级动作 2：配置隔离环境和写策略

这块能力同样没有新增独立入口，而是挂在已有输入和运行入口上。

站在评测执行者视角，主要是两类操作：

- 在 `case manifest` 里声明 case 的安全属性
- 在 batch run 时选择本轮的工作目录根、清理策略和写策略

执行者实际关心的是三件事：

1. 这条 case 默认是不是只读
2. 它能不能进入真实写环境
3. 每条 case 是否会在独立工作目录里执行

所以这块新功能虽然很重要，但它改变的是：

- manifest 里要补哪些声明
- batch run 时有哪些控制参数
- result bundle 里会多看到哪些状态

它并没有改变“我先准备 case，再跑 batch，再看结果，再做 baseline”这条总体用户旅程。

## 串起来的一句话用户旅程

作为评测执行者，你会这样使用这套产品：

1. 写一份 case manifest，定义我要评什么
2. 选择一套评测设置，决定默认评分器和运行策略
3. 发起一次 batch run，让 harness 批量去跑
4. 查看 result bundle，判断这轮表现如何
5. 把可信结果保存成 baseline
6. 下一轮重跑，再和 baseline 自动比较

如果需要更高级能力，再进一步：

7. 启用或关闭扩展评分器
8. 调整隔离环境和写策略

## 输入、交互、输出，分别是什么

如果只看最外层，可以这样理解：

### 输入

- case manifest
- 输入材料
- 可选 baseline
- 可选评测设置

### 交互

- 通过 batch run 入口发起一次评测
- 可按整套 case 跑，也可挑某几个 case 跑
- 可通过 settings profile 调整评分器与运行策略

### 输出

- 批次级结果
- 单 case 结果
- 证据导航
- 评分卡
- baseline 快照
- regression diff

## 为什么 contracts 很重要

`contracts/` 这 4 份文档，本质上就是这个产品的“外部接口说明书”。

它们决定的不是实现细节，而是：

- 用户如何和产品交互
- Agent 如何稳定调用它
- 结果以后如何沉淀为长期资产

所以你可以把 `contracts/` 理解成：

“这套评测底座作为一个产品，对外长什么样。”

## 为什么没有新增 contract 文档

因为这两块新能力目前都还是挂在已有 contract 上的扩展维度：

- 自定义评分器
  主要扩展的是 `case-manifest`、`result-bundle` 和 baseline compare 的含义
- 隔离与安全策略
  主要扩展的是 `case-manifest`、`run-eval-batch` 和 `result-bundle`

换句话说：

- 如果新增的是一条全新的对外交互入口，通常值得新增 contract
- 如果只是让现有输入/输出契约更丰富，一般优先补进已有 contract

## 建议怎么读

如果你是产品视角，推荐按下面顺序看：

1. 先看本 README，建立整体用户旅程感
2. 再看 [case-manifest.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/case-manifest.md)，理解输入
3. 再看 [run-eval-batch.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/run-eval-batch.md)，理解交互入口
4. 再看 [result-bundle.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/result-bundle.md)，理解输出
5. 最后看 [baseline-snapshot.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/baseline-snapshot.md)，理解长期价值

如果你特别关心这次新增的两块能力，推荐补充这样读：

1. 先看 [plan.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/plan.md) 里的 `Grader Design` 和 `Isolation And Safety Design`
2. 再回到 [case-manifest.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/case-manifest.md) 看这些能力如何落到输入层
3. 再看 [run-eval-batch.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/run-eval-batch.md) 和 [result-bundle.md](/D:/AI/rere-agent/specs/002-workbuddy-eval-harness/contracts/result-bundle.md) 看它们如何落到运行和输出层
