---
url: https://agentskills.io/skill-creation/using-scripts
date: 2026-06-21
---
## AI摘要

本文是 agentskills.io "Skill Creation" 系列的第三篇，聚焦于如何在 Agent Skill 中使用和捆绑可执行脚本，覆盖从一次性命令引用到自包含脚本设计再到 Agent 友好接口设计的完整链条。

文章首先介绍了一键命令运行器（one-off commands）的概念：当现有工具包已满足需求时，直接在 SKILL.md 中引用而无需 scripts/ 目录。主流语言生态均有对应工具——Python 的 uvx（uv 内置，隔离环境+激进缓存，推荐）和 pipx（OS 包管理器安装，成熟替代），Node.js 的 npx（随 Node.js 附带，按需下载+缓存，需用 @version 锁版本），Bun 的 bunx（npx 替代，仅在 Bun 环境下适用），Deno 的 deno run（URL/specifier 直接运行，需权限标志），Go 的 go run（编译即运行，内置于 go 命令）。关键建议：始终锁定版本号以保可复现性，在 SKILL.md 中声明前置条件（如"Requires Node.js 18+"），当命令复杂到难以一次写对时迁移到 scripts/ 目录。

对于需要复用的逻辑，文章系统介绍了各语言的"内联依赖声明"机制，使脚本自包含而无需单独的 manifest 或 install 步骤。Python 通过 PEP 723 在 # /// 标记内声明依赖，用 uv run 自动创建隔离环境并安装依赖，支持 PEP 508 版本约束和 requires-python 版本限制，uv lock --script 生成锁文件确保完全可复现。Deno 通过 npm: 和 jsr: 导入路径天然自包含，依赖全局缓存。Bun 运行时自动安装缺失包（仅当无 node_modules 目录时），TypeScript 原生支持。Ruby 通过 bundler/inline 直接在脚本中声明 gemfile。所有语言都强调版本锁定的重要性。

文章核心亮点是"面向 Agent 使用设计脚本"的准则，这是区别于传统脚本开发的关键差异。Agent 在非交互 shell 中运行脚本，无法响应 TTY 提示、密码对话框或确认菜单——交互式输入会导致脚本无限挂起，必须改为通过命令行参数、环境变量或 stdin 接受输入。--help 输出是 Agent 了解脚本接口的主要途径，应包含简短描述、可用参数和使用示例，保持简洁以避免占用过多上下文窗口。错误信息需要具体（说明出了什么、期望什么、如何修正），而非笼统的"invalid input"。输出应首选结构化格式（JSON/CSV/TSV），数据发 stdout、诊断信息发 stderr，实现数据与日志分离。此外文章还列出了多条进阶考量：幂等性（"create if not exists" 优于 "create and fail on duplicate"）、输入约束（用枚举和封闭集合而非猜测）、dry-run 支持（用 --dry-run 预览破坏性操作）、有意义的退出码（不同失败类型用不同 code 并在 --help 中文档化）、安全默认值（破坏性操作需 --confirm/--force 显式确认）、可预测的输出大小（避免超过 Agent 的输出截断阈值，支持 --offset 分页或 --output 写文件）。

### 核心洞察

**"面向 Agent 使用设计脚本"是一个被严重忽视的新范式。** 传统脚本写给人类用，可以假设用户会看 --help、能交互填表、能容忍模糊错误信息。但 Agent 不是人——它无法响应 TTY 提示，靠 stdout 输出决定下一步，错误信息质量直接影响它下一轮行为质量。这条设计哲学的转变对用户维护 Hermes skill 中的 scripts/ 有直接实操价值。

**PEP 723 + uv run 使 Python 脚本真正自包含——不再需要 requirements.txt 或 venv。** 这个机制值得特别关注：脚本头部声明依赖，uv run 自动创建隔离环境并安装，零配置运行。对用户写 RQZY Agent 相关工具脚本时的依赖管理有实际帮助。

**"结构化 stdout + 诊断 stderr"的分离原则是 Agent 管道可组合性的基础。** Agent 捕获 stdout 做解析和决策，stderr 提供调试信息但不干扰主数据流。这与用户在 Hermes 中用 terminal() 工具的输出模式一致，理解这个原则有助于写出更好配合 Agent 工作流的脚本。

**"可预测的输出大小"是 Agent 环境特有的约束。** 大多数 Agent 框架会截断超过 10-30K 字符的工具输出，脚本作者需要主动处理——用 --offset 分页、--output 写文件、或默认输出摘要。这是传统脚本开发中几乎不会考虑的问题，但在 Agent 环境中是硬约束。

**"幂等性 > 唯一性约束"是 Agent 重试安全性的前提。** Agent 可能因网络抖动或超时重试命令，"create if not exists"比"create and fail on duplicate"安全得多。这条原则对用户在 RQZY 自动化流程中设计涉及外部系统写入的脚本尤为重要。