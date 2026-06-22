# Feature Specification: 财务收入流水汇总 CLI 工具

**Feature Branch**: `001-revenue-rollup-cli`

**Created**: 2026-06-05

**Status**: Implemented

**Input**: User description: "开发一个供Agent使用的，通过CLI方式调用的，财务收入流水数据汇总工具脚本。根据汇总规则表中配置的汇总规则，按照GROUP字段对SUM字段做条件汇总，计算生成Excel表格，作为财务上确认收入或回款的依据，并且上传专门的数据库（另一个飞书多维表）做留存。"

## Business Context & Scope

### Revenue Recognition Skill SOP

收入确认 Skill 的完整业务 SOP 依次包括：

1. 下载源文件
2. 文件预处理
3. 汇总
4. 收入回款确认
5. 后处理
6. RPA 入账
7. 验算
8. 分发
9. 调整
10. 封版

完整的仓库级业务工作流说明见
[revenue_recognition_skill_workflow.md](../../ref-docs/revenue_recognition_skill_workflow.md)。

### Scope of This Specification

本规格只覆盖第 3 步“汇总”。

汇总步骤的职责是：读取已经完成预处理的流水级源数据，按照确认项目规则完成门店口径汇总，并将汇总结果上传到业务数据库（飞书多维表），作为下一步收入回款确认的字段原材料。

本规格不覆盖以下职责：

- 下载源文件
- 文件预处理
- 在飞书多维表中通过查找引用、公式字段完成收入回款确认
- 对业务表做后处理小修小补
- 调用 RPA 入账
- 验算、分发、调整、封版

### Upstream and Downstream Contract

- 上游“文件预处理”负责对平台下载得到的多种业务文件做解压、识别和分拣。例如同一平台下载目录下可能同时存在“收益列表”和“收益明细”等不同业务文件，预处理需要把当前确认项目真正需要的那一类文件单独整理到干净目录，供后续汇总消费。
- 对本工具而言，`source_file` 表示已经完成预处理的单文件或干净目录，而不是原始压缩包，也不是仍混放多种业务文件的下载目录。
- 下游“收入回款确认”在飞书多维表中通过查找引用、公式字段等配置，对汇总结果中的基础字段做字段间运算，得出折后收入、实际回款、平台服务费、税费、配送费等确认结果。
- 因此，汇总步骤输出的是可审计、可复用的基础事实字段，不直接替代下游确认公式，也不在工具内封装最终会计计量判断。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent 调用 `list_recog_items` 与 `run_recog_rollup` 完成端到端汇总 (Priority: P1)

作为任务执行方的 Agent，在接收到人类同事给出的确认项目、期间和已完成预处
理的干净源文件目录后，需要先调用 `list_recog_items` 获取注册项目列表，并
查看每个项目对应的 `bitable_table_id` 是否存在；在完成目标项目判断后，再调
用 `run_recog_rollup --recog_id --period --source_file` 执行完整汇总流程。
通过这种方式，Agent 可以把汇总步骤的结果直接上传到飞书多维表，为下一步收
入回款确认提供字段原材料。

**Why this priority**: 这是 Agent 视角下最核心的主流程。如果 Agent 不能把
“接收指令、收集项目信息、判断目标项目、调用完整汇总工具、交付结果”完整串
起来，这个项目就还不能算作真正可用的 Agent 工具能力。

**Independent Test**: 给定一条来自人类同事的任务指令，其中包含确认项目、
期间和已经完成预处理的合法源文件目录。Agent 先调用 `list_recog_items` 获取完整注册项目列
表，再判断出正确的 `recog_id` 并将其作为 `recog_id` 传入
`run_recog_rollup`。测试通过的标志是：Agent 能输出清晰的执行结论，人类同
事能在目标飞书数据表中直接看到该期间的门店级汇总结果，并可继续在同表中完
成收入回款确认；若任一环节失败，Agent 能获得工具返回的明确失败阶段和下一
步行动依据。

**Acceptance Scenarios**:

1. **Given** Agent 接收到的人类指令包含有效的确认项目、期间和已经完成预处理的干净源文件目录，且 `list_recog_items` 返回的注册项目列表中存在明确对应项并显示目标 `bitable_table_id` 可用，**When** Agent 先调用 `list_recog_items` 完成项目匹配判断，再调用 `run_recog_rollup --recog_id --period --source_file`，**Then** 系统完成结构检验、试算和上传，并让人类同事在目标飞书数据表中直接看到可用于后续收入回款确认的汇总字段。
2. **Given** Agent 已调用 `list_recog_items` 并拿到注册项目列表，但无法从中判断出唯一可信的目标项目，或返回结果显示目标 `bitable_table_id` 不可用，**When** Agent 完成项目判断阶段，**Then** Agent 不调用 `run_recog_rollup`，而是向人类同事返回待澄清或阻断信息。
3. **Given** `run_recog_rollup` 在默认完整流程中的结构检验、试算或上传任一环节发生异常，**When** Agent 调用 `run_recog_rollup --recog_id --period --source_file`，**Then** 工具返回明确的失败环节和失败原因，且 Agent 基于该结果停止错误后续操作。

---

### User Story 2 - Agent 使用 `run_recog_rollup --validate` 与 `--preview` 完成复杂汇总 (Priority: P2)

作为任务执行方的 Agent，当一个确认项目依赖多个 sheet、多个 GROUP 字段以
及带条件的 SUM 汇总规则时，需要能够依赖 `run_recog_rollup --validate` 和
`run_recog_rollup --preview` 正确处理这些复杂规则，而不是在推理层自行重写
业务计算逻辑。工具应先给出可算、可上传的检验结果，再输出汇总步骤需要的结
果文件和结果概览，以便下游收入回款确认继续把这些字段作为原材料使用。

**Why this priority**: Agent 的强项是理解任务、组织步骤和处理例外，不应把
复杂财务汇总公式放在模型自由推理里完成。规则型能力越稳定，Agent 的整体执
行可靠性越高。

**Independent Test**: 准备一个包含多个 sheet 的源文件和一组带 GROUP、
SUM、条件表达式以及 optional 标记的规则。Agent 先调用
`run_recog_rollup --validate --recog_id --source_file`，再调用
`run_recog_rollup --preview --recog_id --period --source_file`。执行后应得
到逐项检验结果，以及与规则一致的汇总结果文件或明确异常信息。

**Acceptance Scenarios**:

1. **Given** Agent 已确认目标 `recog_id`，且同一确认项目依赖多张 sheet 的 GROUP 汇总，**When** Agent 调用 `run_recog_rollup --validate --recog_id --source_file`，**Then** 系统返回每个检测项目的通过情况，并在发现异常时明确指出缺失 sheet、错误范围、缺失或重复字段、不可算 condition 或飞书字段不匹配的具体位置。
2. **Given** 结构检验通过，**When** Agent 调用 `run_recog_rollup --preview --recog_id --period --source_file`，**Then** 系统生成 `/tmp/revenue-recognition/outputs/{period}_{recog_id}_{timestamp}.xlsx` 格式的结果文件，并返回路径与结果概览。
3. **Given** 某个 SUM 字段被标记为 optional 且源文件缺失该字段，或某条汇总规则带有条件表达式，**When** Agent 调用 `run_recog_rollup --preview --recog_id --period --source_file`，**Then** 系统按约定处理 optional 缺失，仅让满足条件的源记录参与对应规则计算，并在不可算时返回定位到源文件、sheet、行和字段的异常信息。

---

### User Story 3 - Agent 使用 `run_recog_rollup --upload`、`--append`、`--upsert` 恢复执行并控制上传策略 (Priority: P3)

作为需要持续推进任务的 Agent，当完整流程在某个环节因配置、数据或外部系统
问题中断后，需要能够重新选择单一环节继续执行。对上传场景而言，Agent 需要
能够调用 `run_recog_rollup --upload --recog_id --result_file` 只上传已经生
成的结果文件；当目标表中已存在同期间数据时，还需要能够根据任务需要追加上
传或按分组键覆盖已有记录。

**Why this priority**: Agent 不只是一次性调用工具，还需要在失败后继续推进
任务。能否低成本恢复执行，直接决定这个能力是否适合被纳入更长链路的 Agent
工作流或未来的 skill。

**Independent Test**: 让 `run_recog_rollup` 先在某一环节故意失败，例如结构
检验缺字段、试算规则异常或上传冲突。修正问题后，Agent 使用
`--validate`、`--preview` 或 `--upload` 重新调用工具，只执行指定环节。
对于上传场景，还应验证默认拒绝重复上传以及 `--append`、`--upsert` 两种强
制上传模式。

**Acceptance Scenarios**:

1. **Given** Agent 先前调用 `run_recog_rollup` 时在结构检验环节失败，且相关问题已修正，**When** Agent 以 `run_recog_rollup --validate --recog_id --source_file` 重新调用工具，**Then** 系统只执行结构检验并返回该环节的结果，不自动继续试算或上传。
2. **Given** Agent 先前已成功完成试算并生成结果文件，**When** Agent 以 `run_recog_rollup --upload --recog_id --result_file` 重新调用工具，且目标数据表中不存在同期间记录，**Then** 系统只执行上传，并返回上传结果回读概览或成功结果概览。
3. **Given** 目标数据表中已存在同期间记录，**When** Agent 以 `run_recog_rollup --upload --recog_id --result_file` 执行上传，**Then** 系统默认拒绝上传并说明冲突原因。
4. **Given** 目标数据表中已存在同期间记录，**When** Agent 以 `run_recog_rollup --upload --append --recog_id --result_file` 或 `run_recog_rollup --upload --upsert --recog_id --result_file` 调用工具，**Then** 系统按指定策略完成追加或覆盖，并返回上传结果概览。

---

### Edge Cases

- `source_file` 如果指向尚未解压的压缩包，或仍混放多种业务文件的原始下载目录，系统应如何阻断并提示先完成文件预处理？
- `list_recog_items` 返回的注册项目中，目标项目存在多个相似名称时，Agent
  应如何判断需要澄清而不是继续调用 `run_recog_rollup`？
- 注册项目存在，但 `bitable_table_id` 缺失或对应飞书数据表不存在时，Agent
  是否应直接阻断完整流程？
- `run_recog_rollup --validate` 时，如果源文件中目标 sheet 存在但
  `category_row`、`field_row`、`last_row` 指向空范围或越界，应如何返回异常？
- `run_recog_rollup --validate` 时，如果源数据字段缺失、重复或 condition
  引用了不存在的字段，应如何精确返回问题位置？
- `run_recog_rollup --validate` 时，如果 `source_file` 传入的是目录且目录下存在
  多个格式相同的源文件，系统应如何在不扫描全部文件的情况下完成结构检验？
- `run_recog_rollup --preview` 时，如果多个 sheet 参与汇总且同一 GROUP 字段
  在部分 sheet 中缺失，该次试算是否整体失败，还是仅对允许缺失的字段降级处理？
- `run_recog_rollup --upload` 时，如果表内已存在同期间但仅部分 GROUP 值重复
  的记录，系统应如何识别并提示冲突范围？
- `run_recog_rollup --upload --result_file` 时，如果结果文件不存在、不可读或
  与 `recog_id` 不一致，应如何阻止错误上传并提示 Agent？
- 当使用方期待工具直接产出折后收入、实际回款、平台服务费、税费或配送费等最终确认字段时，系统应如何明确提示这些字段属于下游收入回款确认范围？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供可通过 bash 以 CLI 方式调用的 `list_recog_items` 工具。
- **FR-002**: `list_recog_items` MUST 无必填入参。
- **FR-003**: `list_recog_items` MUST 逐条列示确认项目注册表中的项目，并至少返回 `recog_id`、`recog_name`、`bitable_table_id` 以及对应 `bitable_table_id` 是否存在的信息。
- **FR-004**: `list_recog_items` MUST NOT 在工具内部自动完成项目匹配、排序裁决或唯一性判断；项目判断由 Agent 或模型完成。
- **FR-004A**: 系统 MUST 将本功能限定为收入确认 Skill 十步 SOP 中的第 3 步“汇总”，并在规格中明确其上游是下载与文件预处理，下游是收入回款确认、后处理及后续收尾环节。
- **FR-004B**: `source_file` MUST 表示已经完成预处理的单文件或干净目录，而不是原始压缩包，也不是仍混放多种业务文件的下载目录。
- **FR-004C**: 当 `source_file` 指向原始压缩包或仍混放多种业务文件的下载目录时，系统 MUST 阻断汇总并提示先完成文件预处理。
- **FR-005**: 系统 MUST 提供可通过 bash 以 CLI 方式调用的 `run_recog_rollup` 工具。
- **FR-006**: `run_recog_rollup` 默认完整流程 MUST 接收 `recog_id`、`period`、`source_file` 三个必填输入。
- **FR-006A**: `run_recog_rollup` 的 `source_file` MUST 支持传入单个文件路径或目录路径，且目录路径 SHOULD 作为大多数项目的常态输入。
- **FR-007**: `run_recog_rollup` 默认完整流程 MUST 按固定顺序依次执行结构检验、试算和上传三个环节。
- **FR-008**: `run_recog_rollup` 在默认完整流程中，只要任一环节失败，MUST 停止后续环节执行并返回失败阶段及失败原因。
- **FR-009**: `run_recog_rollup --validate` MUST 支持仅执行结构检验，并接收 `recog_id` 与 `source_file` 作为必填输入。
- **FR-009A**: 当 `source_file` 为目录路径时，`run_recog_rollup --validate` MUST 只随机抽取一个代表文件完成结构检验，而不是扫描目录下全部源文件。
- **FR-010**: `run_recog_rollup --validate` MUST 检查目标 sheet 是否存在，并在缺失时指出具体 sheet 名称。
- **FR-011**: `run_recog_rollup --validate` MUST 检查目标 sheet 的源数据范围是否正确，包括 `category_row`、`field_row`、`last_row` 是否有效，并指出具体错误项。
- **FR-012**: `run_recog_rollup --validate` MUST 检查源数据字段是否存在且不重复，并指出缺失或重复的具体字段。
- **FR-013**: `run_recog_rollup --validate` MUST 检查每条 condition 是否可算，并指出不可算 condition 对应的字段或规则项。
- **FR-013A**: 当 condition 超出首版支持范围时，`run_recog_rollup --validate` MUST 返回明确的“不支持表达能力”错误，而不是让 Agent 自行推断规则含义或发明新 helper。
- **FR-014**: `run_recog_rollup --validate` MUST 检查目标飞书数据表字段是否存在且类型符合，并指出不存在或类型不匹配的具体字段。
- **FR-015**: `run_recog_rollup --validate` MUST 返回每条检测项目的通过情况与异常详细信息。
- **FR-015A**: 当 `run_recog_rollup --validate` 采用目录抽样模式时，返回结果 MUST 标明被抽检的代表文件路径。
- **FR-016**: `run_recog_rollup --preview` MUST 支持仅执行试算，并接收 `recog_id`、`period`、`source_file` 作为必填输入。
- **FR-016A**: 当 `source_file` 为目录路径时，`run_recog_rollup --preview` MUST 对目录下全部可匹配源文件执行试算。
- **FR-017**: `run_recog_rollup --preview` MUST 依据规则表中 `GROUP` 与 `SUM` 的定义进行分组汇总，并将结果字段映射为规则指定的输出字段名。
- **FR-018**: `run_recog_rollup --preview` MUST 支持带条件的汇总规则，仅让满足 condition 的源记录参与对应规则的计算。
- **FR-018A**: condition 首版 MUST 至少支持以下两类条件汇总：按结算时间过滤，以及按单个可枚举 `GROUP` 型源字段值过滤。
- **FR-019**: `run_recog_rollup --preview` MUST 支持单个确认项目跨多个 sheet 汇总，并在 GROUP 口径一致的前提下合并结果。
- **FR-020**: `run_recog_rollup --preview` MUST 按业务约定处理 `optional=True` 的字段缺失情况，其中可选 SUM 字段缺失时不导致整体失败，可选 GROUP 字段缺失时允许结果置空。
- **FR-020A**: 对于 `csv` 文件或只有单个 sheet 的 `xlsx` 文件，源文件结构定义中的 `sheet` 值 MUST 使用 `DEFAULT` 作为逻辑默认值。
- **FR-020B**: 同一 `recog_id` 下，`SUM` 类型规则的 `bitable_field` MUST 唯一；汇总规则表中的一条记录只允许描述一个输出字段的一条汇总规则，不允许通过多条规则共同累加同一个业务数据库字段。
- **FR-021**: `run_recog_rollup --preview` MUST 在成功时将结果文件保存到 `/tmp/revenue-recognition/outputs/{period}_{recog_id}_{timestamp}.xlsx`。
- **FR-022**: `run_recog_rollup --preview` MUST 为每一条输出记录带上期间信息，并在成功时返回结果文件路径与结果概览，至少包含条数与字段数。
- **FR-022A**: `run_recog_rollup --preview` 产出的记录 MUST 被定义为门店级基础事实字段，用作下游收入回款确认的字段原材料，而不是最终确认收入、最终回款或最终记账结果。
- **FR-023**: `run_recog_rollup --preview` MUST 在出现不可算数据时返回异常信息，并至少能定位到源文件、sheet、行、字段及记录详情。
- **FR-024**: `run_recog_rollup --upload` MUST 支持仅执行上传，并接收 `recog_id` 与 `result_file` 作为必填输入。
- **FR-025**: `run_recog_rollup --upload` MUST 只上传 `result_file` 指向的结果文件，不重新执行结构检验或试算。
- **FR-026**: `run_recog_rollup --upload` MUST 在上传成功后返回上传结果回读概览或成功结果概览，至少包含条数与字段数。
- **FR-027**: `run_recog_rollup --upload` MUST 在上传失败时返回明确报错信息；如可行，SHOULD 提供进一步查阅飞书错误信息的途径。
- **FR-028**: `run_recog_rollup --upload` MUST 在发现同期间数据已存在时默认报错并阻止上传。
- **FR-029**: `run_recog_rollup --upload` MUST 支持 `--append` 与 `--upsert` 两种强制上传方式，且两者为互斥选项。
- **FR-030**: `run_recog_rollup --upload --append` MUST 在已有同期间数据时执行追加上传。
- **FR-031**: `run_recog_rollup --upload --upsert` MUST 在已有同期间数据时按分组键覆盖冲突记录。
- **FR-032**: `run_recog_rollup` 在任意模式下 MUST 返回清晰结果，包括成功、失败、失败阶段、是否可重试以及影响范围，便于 Agent 判断下一步动作。
- **FR-032A**: 本功能 MUST NOT 直接产出折后收入、实际回款、平台服务费、税费、配送费等最终确认字段；这些字段由下游收入回款确认环节在飞书多维表中基于汇总原材料继续计算。



### Key Entities *(include if feature involves data)*

- **确认项目注册信息**: 表示一个可执行阶段一汇总任务的业务项目，关键属性
  包括 `recog_id`、`recog_name` 和待上传飞书数据库的目标数据
  表 id `bitable_table_id`。
- **注册项目列表**: 表示 `list_recog_items` 返回给 Agent 的项目清单，关
  键属性包括 `recog_id`、`recog_name`、`bitable_table_id`
  以及对应 `bitable_table_id` 是否存在的基础信息。
- **预处理后源文件集合**: 表示已经完成解压、识别和按确认项目分拣后的单文件或目录，是 `source_file` 可接受的业务输入形态，不包括原始压缩包或混放多种业务文件的下载目录。
- **源文件结构定义**: 描述某个确认项目的源 Excel 应如何读取，关键属性包括
  `sheet`、`category_row`、`field_row`、`last_row`以及sheet是否允许缺失`optional`。
  其中 `sheet=DEFAULT` 表示 `csv` 或只有单个 sheet 的 `xlsx` 的逻辑默认 sheet。
- **汇总规则**: 定义某个输出字段如何从源数据计算得到，关键属性包括 `bitable_field`、`sheet`、`type`、`field`、`condition`和是否允许缺失`optional`。其中对同一 `recog_id`，每个 `SUM bitable_field` 必须唯一，不允许多条规则共同累加同一输出字段。
- **结构检验结果**: 表示 `run_recog_rollup --validate` 的输出，关键属性包括
  检测项名称、通过状态和异常详细信息。
- **结果文件**: 表示 `run_recog_rollup --preview` 生成并供
  `run_recog_rollup --upload` 使用的 Excel 文件，关键属性包括 `period`、
  `recog_id`、时间戳和文件路径。
- **汇总结果记录**: 表示最终导出的单条业务结果，包含期间、分组字段、汇总
  数值和后续上传所需字段。这些字段是下游收入回款确认继续计算的原材料，不等
  同于最终确认结果。
- **收入回款确认结果**: 表示下游在飞书多维表中通过查找引用、公式字段等方式
  计算出的折后收入、实际回款、平台服务费、税费、配送费等结果。该实体依赖汇
  总结果记录，但不属于本工具直接产物。
- **执行模式**: 表示 `run_recog_rollup` 本次调用是默认完整流程，还是
  `--validate`、`--preview`、`--upload` 三种单环节模式之一。
- **上传策略**: 表示 `run_recog_rollup --upload` 面对重复数据的处理方式，
  至少包括默认报错、`--append` 追加和 `--upsert` 覆盖三类行为。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 对于已完成配置且已完成文件预处理的确认项目，Agent 在接收到
  人类同事给出的确认项目、期间和干净源文件目录后，能先调用 `list_recog_items` 获取项目清单并完成
  项目判断，再调用 `run_recog_rollup --recog_id --period --source_file`
  完成汇总步骤完整流程，并让人类同事直接在目标飞书数据表中看到结果。
- **SC-002**: `list_recog_items` 的返回结果足以让 Agent 判断目标项目是否
  可继续处理，包括是否能看到目标 `bitable_table_id` 及其存在状态。
- **SC-003**: 当 Agent 调用 `run_recog_rollup --validate --recog_id --source_file`
  时，系统能够对每个检测项目返回通过情况，并在失败时指出具体 sheet、范围、
  字段、condition 或飞书字段问题。
- **SC-004**: 当 Agent 调用 `run_recog_rollup --preview --recog_id --period --source_file`
  时，系统能够返回详细异常信息，或生成符合 `/tmp/revenue-recognition/outputs/{period}_{recog_id}_{timestamp}.xlsx`
  规则的结果文件并附带结果概览。
- **SC-005**: 当 Agent 调用 `run_recog_rollup --upload --recog_id --result_file`
  时，系统默认能够阻止同期间重复上传；在显式指定 `--append` 或 `--upsert`
  时，系统能够按对应策略完成上传。
- **SC-006**: 当完整流程在任一环节失败且问题已修复后，Agent 能通过
  `--validate`、`--preview` 或 `--upload` 只重跑目标环节，而不必无条件重跑
  整个流程。
- **SC-007**: 对于已上线的确认项目，汇总阶段产出能够以门店级基础字段形式直
  接进入业务数据库，供下一步收入回款确认继续做字段间运算，而不要求汇总工具
  直接产出折后收入、实际回款、平台服务费、税费、配送费等最终确认结果。

## Assumptions

- 首版处理对象为单个确认项目对应的一次完整汇总与上传，不包含一次命令同时
  执行多个确认项目的批处理能力。
- Agent 负责串联调用两个工具：先调用 `list_recog_items` 获取注册项目列
  表并完成项目判断，再调用 `run_recog_rollup` 的默认完整流程或
  `--validate`、`--preview`、`--upload` 单环节流程。
- 平台下载结果可能同时包含多种业务文件；文件预处理负责解压、识别并按确认项
  目分拣出干净源文件目录，再把该目录或其中单文件交给汇总步骤消费。
- `source_file` 首版支持传单文件路径或目录路径，其中目录路径是多数项目的主
  要输入方式，且默认指向已经完成预处理的干净输入。
- 规则配置、源文件结构定义和项目注册信息已经维护在约定的数据表中，且调用
  方具备访问这些配置的权限。
- 对于 `csv` 或只有单个 sheet 的 `xlsx`，源文件结构表中的 `sheet` 统一填
  `DEFAULT`。
- 当 `source_file` 传目录时，`--validate` 只随机抽取一个代表文件做结构检验；
  目录下其他文件的具体问题由 `--preview` 阶段按文件逐一暴露。
- 目标输出文件格式为 Excel，且业务方接受通过该文件进行人工复核。
- 条件规则首版采用单行布尔表达式形式，统一使用 `F("字段名")` 访问源字段，不
  包含复杂脚本式流程控制能力。
- 条件规则首版仅承诺支持“按结算时间过滤”与“按单个可枚举 GROUP 字段值过滤”
  两类真实已出现的条件汇总。
- 首版不开放 Agent 自主创建或注册 helper；如现有内置能力无法表达业务需求，
  Agent 负责明确提示联系开发者扩展能力。
- 调用方会通过安全配置方式提供访问外部系统所需的凭证，正式实现不直接硬编
  码敏感信息。
- 默认重复上传判定以“同确认项目 + 同期间”作为第一层拦截条件；更细粒度的
  冲突识别与覆盖范围由上传策略进一步约束。
- 下游收入回款确认通过飞书多维表中的查找引用、公式字段等配置，对汇总结果中
  的基础字段继续做字段间运算，得到折后收入、实际回款、平台服务费、税费、配
  送费等最终确认结果。
- 后处理、RPA 入账、验算、分发、调整与封版属于汇总步骤之后的独立环节，不在
  本规格的直接交付范围内。
