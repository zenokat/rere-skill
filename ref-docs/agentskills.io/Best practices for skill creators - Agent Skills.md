---
url: https://agentskills.io/skill-creation/best-practices
date: 2026-06-21
---
## AI摘要

本文系统阐述了为 AI Agent 编写高质量 Skill（技能指令文件）的最佳实践，围绕"真实专业经验驱动"、"上下文高效利用"和"控制力校准"三条主线展开。首先，有效的 Skill 必须源自真实的操作经验——从实际任务的对话中提取可复用模式（成功步骤、纠正点、输入输出格式、项目特定上下文），或从团队已有的文档、API 规范、代码评审记录、版本控制历史等项目中综合而成。Skill 不应是让 LLM 凭空生成泛泛的"最佳实践"，而应封装项目特有的 API 模式、边界情况和约定。初稿完成后需通过实际执行迭代改进，阅读 Agent 执行轨迹（而非仅看最终输出），识别出指令过于模糊导致 Agent 试错、指令不适用当前任务但被盲目执行、或给出过多选项而无默认值等问题。

在上下文预算方面，Skill 进入 Agent 上下文窗口后与对话历史和系统指令竞争注意力。核心原则是"添加 Agent 所缺的，省略 Agent 已知的"——只需写项目特定约定、领域特定流程、非显而易见的边界情况和具体工具/API 用法，不必解释 PDF 是什么或 HTTP 如何工作。Skill 的范围应像一个函数，封装一个连贯的工作单元并与其他 Skill 良好组合，过窄则多个 Skill 加载导致开销和冲突，过宽则激活不精确。推荐 SKILL.md 控制在 500 行、5000 token 以内，超出部分放入 references/ 目录并告知 Agent 何时按需加载。细节程度宜"适度"而非穷举——简洁的分步指导加一个可运行的示例通常优于详尽文档。

控制力校准方面，灵活可变的部分（如代码评审检查项）给予自由度并解释原因以帮助 Agent 做好上下文判断，脆弱操作（如数据库迁移）则严格规定具体序列。提供明确默认值而非菜单式选项，用程序性方法（教会 Agent 如何处理一类问题）而非声明式答案（针对特定实例的特定输出）。文章还总结了几种高价值指令模式：Gotchas 段落记录违反合理假设的环境特定事实（如 soft delete、字段命名不一致）；输出模板比文字描述格式更可靠；多步骤工作流用显式 Checklist 跟踪进度；验证循环模式让 Agent 先做再检查再修复；计划-验证-执行三步法用于批量或破坏性操作；当 Agent 跨测试用例重复发明相同逻辑时，将该逻辑固化为脚本捆绑在 scripts/ 目录下。

### 核心洞察

**Skill 质量的天花板由源经验决定。** 文章最核心的观点是"从真实任务中提取"优于"让 LLM 凭空生成"——你的 Skill 封装的是项目特有的失败模式、恢复流程和命名约定，这些信息不在任何通用训练数据中。这与用户在 RQZY 收入确认 Agent 上积累的循环迭代经验完全吻合。

**"添加 Agent 所缺的，省略 Agent 已知的"是上下文效率的黄金法则。** 每 token 都在与对话历史竞争注意力。可以用来反思 Hermes skill 的编写质量：SKILL.md 中是否有大量解释 Agent 本身就知道的东西的冗余内容？这一原则直接适用于用户正在维护的多个 skill。

**控制力校准不应一刀切——灵活处解释原因，脆弱处硬编码序列。** 这解决了"Skill 写多具体"的常见困惑。解释原因比 rigid directives 更有效，因为理解目的的 Agent 能在上下文中做出更好的判断。对用户构建 RQZY skill 有实操指导意义。

**Gotchas 段落是 Skill 中 ROI 最高的内容。** 记录那些"违反合理假设的环境特定事实"——Agent 会犯错但不会意识到自己犯了错的东西。文章建议每次纠正 Agent 的错误时立即追加到 Gotchas，这是最直接的迭代改进路径。

**计划-验证-执行三步法是 Agent 执行破坏性操作的安全护栏。** 先让 Agent 生成中间计划（结构化格式），用脚本或 checklist 验证计划与事实源的一致性，确认无误后才执行。这一模式对用户在 RQZY 自动化工作流中执行不可逆操作尤其重要。

---
## 笔记
### 真实流程经验驱动
#### 从结对做成的结果总结
- Steps worked
- Corrections made
- Input/output formats
- Context provided
#### 从历史流程产物中提炼
**project-specific** material, not generic references
#### 在真实执行中闭环迭代
尝试构建Loop  [[Evaluating skill output quality - Agent Skills]]
- 评测系统
- 评测分数、完整轨迹可查
- 分析迭代方法论
### 上下文工程
#### 只留下Agent不知道的
逐项内容追问：如果没有，Agent会出错吗？
- yes——保留
- no——剔除
- not sure——测试一下 [[Evaluating skill output quality - Agent Skills]]
#### 设计成边界清晰的单元模块
就像设计Function一样
当skills数量变多，涉及skills的调用边界时需要重点思考
#### 不要写成大而全的参考文档
- 文档覆盖所有细节和边界，但一次具体的任务可能只用到其中一小部分的信息，大部分相关度不高的信息反而会 1）稀释高价值信息；2）可能被不适合当前任务的信息带偏
- **建议**：提供步骤指引和案例即可，边界和异常情况可以信任Agent自己去解决
#### 渐进式披露
> 组织信息时：考虑Agent加载信息的顺序，做不同任务时不同信息进入context的时机
- SKILL.md只包含**每次调用都需要**的信息
- 其他信息放入references/，并且明确指定**调用条件**
	%%“Read `references/api-errors.md` if the API returns a non-200 status code” is more useful than a generic “see references/ for details.”%%
### 指令控制程度
#### 部分最优
Not every part of a skill needs the same level of prescriptiveness.
根据情况灵活调整控制度
同一个skill内不同部分的控制度往往是不同的
#### 根据脆弱度选择控制度
- 必须要严格执行的任务才列详细操作步骤
```markdown
## Database migration

Run exactly this sequence:
`
python scripts/migrate.py --verify --backup
`
Do not modify the command or add additional flags.
```
- 其他任务：**明确目标**而非指定步骤
```markdown
## Code review process

1. Check all database queries for SQL injection (use parameterized queries)
2. Verify authentication checks on every endpoint
3. Look for race conditions in concurrent code paths
4. Confirm error messages don't leak internal details
```
#### 不要“列示”所有选项
当一个任务有多种做法时，直接给出一个“默认”做法，其他做法带一下
切忌平等地列示所有选项
```
<!-- Too many options -->
You can use pypdf, pdfplumber, PyMuPDF, or pdf2image...


<!-- Clear default with escape hatch -->
Use pdfplumber for text extraction:
`
import pdfplumber
`
For scanned PDFs requiring OCR, use pdf2image with pytesseract instead.
```
### Common Patterns
#### Gotcha Sections
✅environment-specific facts that defy reasonable assumptions
❌general advice
- 专项维护：遇到一次这样的错误，就补一条
#### Templates for output format
需要输出时，提供模板
- 可以在SKILL.md里，也可以抽离出单独的assets
#### Checklist for multi-step workflows
需要多步时，严格控制Agent按步骤执行不偏离
```markdown
## Form processing workflow

Progress:
- [ ] Step 1: Analyze the form (run `scripts/analyze_form.py`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (run `scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (run `scripts/fill_form.py`)
- [ ] Step 5: Verify output (run `scripts/verify_output.py`)
```
#### Validation loops
不能犯错的环节，可以要求循环修改直至达到标准
- 可以是script，可以是reference checklist，也可以放在SKILL.md里
#### Plan-validate-execute
需要审慎思考的环节，要求先出计划并validate计划
#### Bundling reusable scripts
从评测中发现反复出现的临时脚本
[[Using scripts in skills - Agent Skills]]