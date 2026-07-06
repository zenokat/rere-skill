---
url: https://agentskills.io/skill-creation/evaluating-skills
date: 2026-06-21
---
## AI摘要

本文提出了一个完整的 Agent Skill 评测框架（eval-driven iteration），用于系统性地测试和改进 Skill 输出质量。核心流程是：设计测试用例、运行评测、编写断言、评分聚合、人工审查、迭代改进，形成闭环。

测试用例由 prompt（真实用户消息）、expected_output（成功标准的人类描述）和可选的 input_files 三部分组成，存储在 skill 目录下的 evals/evals.json 中。编写建议：从 2-3 个用例起步，变化措辞和正式程度，覆盖至少一个边界条件，使用真实的文件路径和上下文。评测运行的核心模式是每个用例跑两遍——带 Skill 和不带 Skill（或旧版本），形成 baseline 对照。每次迭代在独立目录（iteration-N/）下隔离，每用例分 with_skill/ 和 without_skill/ 子目录存放输出、耗时和评分数据。运行要求干净上下文（subagent 或独立 session），避免状态污染。耗时数据（total_tokens 和 duration_ms）记录到 timing.json，用于衡量 Skill 的资源开销。

断言（assertions）是可验证的输出陈述，在首轮运行后根据实际输出添加，而非提前预设。好的断言具体可观察（"图表有两个标签轴"、"报告包含至少3条建议"），差的断言要么太模糊（"输出不错"）要么太脆弱（精确匹配特定措辞）。评分（grading）对每个断言给出 PASS/FAIL 并引用具体证据，可由 LLM 判断或验证脚本执行——机械检查优先用脚本。评分原则：PASS 要求具体证据不给好处，同时审查断言本身是否合理。对于版本对比，推荐盲评：隐藏版本信息让 LLM 从组织性、格式、可用性等维度打分，补充断言评分的盲区。聚合统计存入 benchmark.json，包含 pass_rate、time_seconds、tokens 的均值/标准差及 with_skill 与 without_skill 的 delta。

模式分析阶段：移除两种配置都恒通过的断言（无区分度），调查恒失败的断言（断言损坏/测试过难），重点研究"带 Skill 通过、不带 Skill 失败"的断言（Skill 的核心价值）。高 stddev 的用例可能指 instruction 有歧义或评测不稳定。人工审查补充断言盲区，用 feedback.json 记录可操作的反馈（空字符串表示通过）。迭代阶段将失败断言、人工反馈和执行轨迹一起交给 LLM 提出改进建议，遵循原则：从反馈中泛化（不针对特定用例打补丁）、保持精简（移除无用指令而非不断加规则）、解释原因（推理型指令优于 rigid directives）、捆绑重复工作为脚本。循环直到满意、反馈一致为空或不再有明显改进。

### 核心洞察

**"每个用例跑两遍"是最简但最有效的评测设计——带 Skill vs 不带 Skill 的 A/B 对照。** 很多 Skill 作者只跑"有 Skill"的 case 就宣布成功，但无法回答"Skill 到底有没有用"这个问题。Delta（pass_rate 差值 + token/time 开销）才是衡量 Skill 价值的真指标。这一模式直接适用于用户给 RQZY Agent skill 做评测时对比"有 skill vs 无 skill"的差异。

**断言应该在首轮运行后根据实际输出添加，而非提前预设。** 这是一条反直觉但有实操价值的原则——你往往不知道"好"长什么样，直到看到 Skill 跑出的实际输出。先跑再看再断言，避免了"闭门造车式"的评测设计。

**移除两种配置都恒通过的断言是精简评测的关键步骤。** 恒通过的断言只制造虚假的 pass rate 数字，不反映 Skill 的真实价值。这个清洗步骤容易忽略但至关重要，类似 ML 评测中去除 trivial examples。

**推理型指令（"做 X 因为 Y 会导致 Z"）优于 rigid directives（"永远做 X"）的实证依据在这篇文章中反复出现。** 从评分改进到迭代建议，"解释原因"是贯穿全文的优化策略。这与上一篇 best practices 的观点一致，形成互证。

**将失败断言、人工反馈、执行轨迹三路信号交给 LLM 提出改进建议，是迭代效率最高的一步。** 手动连接这三类信号非常繁琐，但 LLM 擅长从分散的失败模式中归纳出共性根因。这一工作流对用户做 RQZY skill 的循环迭代有直接借鉴——不必手动分析每次失败，交给 LLM 综合诊断。

---
## 笔记
不必严格遵守它的标准做法，但要提炼关键思想

**prompt variaiton**
即使相同的任务，也要测试不同prompt的效果，构造多个case

**必须有基线做对比**（有/无skill，不同版本的skill），观察delta值，没有对比只有一个分数绝对值就看不出效果

**跑评测的prompt**，不用追求过度真实？
```
Execute this task:
- Skill path: /path/to/csv-analyzer
- Task: I have a CSV of monthly sales data in data/sales_2025.csv.
  Can you find the top 3 months by revenue and make a bar chart?
- Input files: evals/files/sales_2025.csv
- Save outputs to: csv-analyzer-workspace/iteration-1/eval-top-months-chart/with_skill/outputs/
```

除了功能性指标，一定要捕获每次run的token费用指标和耗时指标
**性能和成本的trade-off**是迭代过程中的关键决策

评分器并非是一次设计就一成不变
- 跑过一次，根据实际轨迹设计的评分器可能比评测前设计的更落地
- 评分器代表对一次运行的**观测视角**
	- **评分器≠任务完成标准**
	- 即使用例不变，评分器也可能因为迭代、重点观测的东西有变化，而相应调整
	- 设计评分器观测最重点需要关心的东西
	- 能稳定通过的评分器可以淘汰
	- 不止用例case是随着迭代要维护的，评分器也是


打分/分数聚合方式
- 基线版本与评测版本各自聚合分数（性能、成本、耗时），计算**delta**，The `delta` tells you what the skill costs (more time, more tokens) and what it buys (higher pass rate)
- **稳定性观测**：一个版本，每个用例都应该跑多次，需要测算多次运行的**stddev**（标准差），stddev值越高，说明一个用例每次运行得到的结果越不稳定，评测分数结果越不可信——进一步说明迭代版本的质量有问题，Agent没办法拿着同一个版本的skill产出稳定的结果
- 打分需要附带说明（**evidence**）


**Human Review看三点**，不是可选评分器，而是必要环节
- 查看机评是否正确
- 确认评分器是否能够反映关注的事情
- 发现新的问题


**AI迭代**
- **三素材**一起投喂
	- 评分结果
	- Human review标注
	- 轨迹
	- 当前版本的skill
- 给AI的迭代原则（可能是AI非常容易犯的问题总结而来）
	- Generalize from feedback 不要变成针对badcase本身的优化
	- Keep the skill lean **skill瘦身的方法**
		- 增加内容但评分未上涨
		- 剔除内容但评分未下降
	- Explain the why 
	- Bundle repeated work 关注反复生成的临时脚本，拎出来作为scripts[[Using scripts in skills - Agent Skills]]

---
## 实践
### 如何从零到一构建起Skill开发迭代Loop？

先收集用例，最简单的任务，可以有不同的prompt
按业务成功标准定出首版评分器，必须包含成本和时间指标
评分聚合方式：算总分、算delta、算stddev、附带evidence
评测早期亲自review每次结果，看机评准确率、看评分器合理程度、发现更多问题
让AI迭代，三素材投喂、摸索*迭代prompt*
### Loop系统构想
> 原则：不着急就落成代码，先手动跑通，形成稳定方法论，再考虑代码的事情

### 持续迭代要关注什么
如何分析评测结果？
- 怎么分析的问题从评分器如何设计就开始了，不只是分数结果出来之后才思考的问题
- 关注性能和成本的trade-off
- 持续迭代评测方案、评测harness本身，要随着产品的迭代同步迭代