# Research: 收入确认阶段一汇总工具

## Decision 1: 使用 Python 3.13 CLI 技术栈

- **Decision**: 使用 Python 3.13.2，并采用 Typer、Pydantic、pandas、
  openpyxl 和 requests。
- **Rationale**: 当前本地环境已经具备 Python 3.13.2 和这些关键依赖，能够同
  时满足 CLI 体验、Excel 数据处理以及 Feishu HTTP 集成的需求；同时该技术栈
  也适合后续部署到运行于 Linux 云服务器上的通用 Agent 系统中。
- **Alternatives considered**:
  - 仅使用 `argparse` + 标准库：依赖更少，但结构化输出和 CLI 可读性较差，样板代码更多。
  - 仅使用 `openpyxl` 不引入 pandas：更贴近工作表层操作，但对规则驱动型汇总的表格计算不够顺手。

## Decision 2: 阶段一工具采用“薄 CLI + 核心引擎 + Feishu 适配层”

- **Decision**: 保持 `list_recog_projects` 和 `run_recog_rollup` 作为薄入口，核心
  逻辑沉淀在可复用引擎中，Feishu Bitable 调用独立在适配层。
- **Rationale**: 未来 skill 应只编排稳定工具，而不是承载业务逻辑。这种布局也
  更有利于单元测试和后续扩展。
- **Alternatives considered**:
  - 每个命令一个独立大脚本：起步快，但不适合多项目持续迭代。
  - 引入重型框架应用：结构过重，不符合当前本地 CLI 优先的场景。

## Decision 3: 以 202603 源文件和历史记录建立黄金样本

- **Decision**: 将本地 `202603-source-excel` 文件和来源于飞书业务数据库拷
  贝镜像表的 202603 历史记录作为第一批黄金基线。
- **Rationale**: 这能把“看起来像对”转成“确实和历史结果一致”的明确 pass/fail
  机制，只有 `--preview` 输出与历史记录一致，项目才算校准通过。
- **Alternatives considered**:
  - 人工抽查几个数字：对 10+ 个项目的反复迭代约束力太弱。
  - 只用合成数据：后续有价值，但不足以证明业务正确性。

## Decision 4: 日常开发优先 `--preview`，上传在镜像表中单独受控

- **Decision**: 将 `--preview` 作为日常校准主模式，`--upload` 作为单独受控
  动作，并优先写入飞书业务数据库的拷贝镜像表。
- **Rationale**: 在高频迭代中，反复写正式业务表会提高风险并降低信号质量。
  先 preview 再对账是更安全的内层循环；已有镜像表则让 upload 也可以被安全测
  试。
- **Alternatives considered**:
  - 每次都跑完整流程含上传：方便，但在规则探索阶段风险过高。
  - 完全禁用上传直到最后：又会和真实端到端行为脱节。

## Decision 5: 规则优先配置驱动，但预留 `recog_id` 级小扩展点

- **Decision**: 以配置驱动规则引擎为主，但允许针对少量 `recog_id` 建立窄范围
  的项目特例补丁点。
- **Rationale**: 预期 10+ 个项目里会持续暴露很多细小业务规则，纯规则表表达
  不一定足够；但若到处硬编码项目特例，又会破坏复用和回归信心。
- **Alternatives considered**:
  - 纯配置实现：结构最干净，但规则表表达能力不足时会拖慢迭代。
  - 到处写项目特例代码：短期快，长期不可维护。

## Decision 6: 结果文件作为 `--preview` 与 `--upload` 的边界产物

- **Decision**: 将 preview 生成的 Excel 文件视为正式边界产物，用于后续上传。
- **Rationale**: 这符合产品设计，也有利于人工复核，并支持上传与重算解耦。
- **Alternatives considered**:
  - 直接从内存中的 preview 数据上传：路径更短，但可追溯性差，也不利于独立重跑上传。

## Decision 7: 用项目覆盖矩阵跟踪迭代，而不是频繁扩大大 spec

- **Decision**: 用独立的项目覆盖矩阵记录项目校准进度，而不是不断把每个项目的
  细节塞进 `spec.md`。
- **Rationale**: 稳定契约应该留在 spec；项目推进和差异记录应放在运营型文档中。
- **Alternatives considered**:
  - 每个项目单独一份 spec：文档过碎。
  - 把所有项目细节都堆进主 spec：主 spec 会很快变脏、变噪。

## Decision 8: preview 与 baseline 不一致时必须先汇报业务负责人

- **Decision**: 当 preview 结果与 baseline 不一致时，Agent 或开发实现不能
  依据自身判断直接推进规则迭代，必须先输出差异结果和判断建议，并等待业务负
  责人确认最终解释口径。
- **Rationale**: 业务规则的最终解释权属于产品/业务负责人。如果让实现层自己
  推断口径，很容易在连续迭代中跑偏并积累错误规则。
- **Alternatives considered**:
  - 开发自行决定差异解释：速度更快，但业务偏差风险过高。
  - 每次只报告差异不附带建议：更保守，但会降低沟通效率。

## Decision 9: 目录模式下 validate 采用抽样校验，preview 处理全部文件

- **Decision**: `source_file` 支持单文件和目录两种输入，其中目录是多数项目的常态输入。
  当输入为目录时，`--validate` 只随机抽取一个代表文件做结构校验；`--preview` 再对目录
  下全部匹配源文件执行真实试算。对 `csv` 或只有单个 sheet 的 `xlsx`，配置中的 `sheet`
  统一使用 `DEFAULT`。
- **Rationale**: 实际项目常有大量格式相同、按门店或账号拆分的源文件。若在 validate
  阶段扫描全部文件，会增加无效耗时；把逐文件异常定位留给 preview，更符合开发节奏和信号
  价值。
- **Alternatives considered**:
  - validate 扫描目录下全部文件：更完整，但重复度高、耗时更长，且与 preview 的异常信号重叠。
  - 禁止目录输入，只允许单文件：不符合多数项目的真实使用方式。
