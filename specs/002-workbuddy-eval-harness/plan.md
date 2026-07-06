# Implementation Plan: WorkBuddy / CodeBuddy Eval Harness

**Branch**: `002-workbuddy-eval-harness` | **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

## Summary

本 feature 交付一套面向评测执行者的最小 eval harness：每条 case 以文件夹组织，在一次性 sandbox workspace 中由 CodeBuddy CLI 真实运行，并生成固定、简洁、可复盘的结果包。

首版保留的能力：

- suite YAML 只定义 `suite_id`、可选 `model`、`graders`、`cases`，可选 `input`/`skills` 共享路径。
- 每条 case 是一个文件夹，包含 `instruction.md`、`skills/` 和 `input/`。
- 每条 case 运行时在公开结果包之外创建一次性 sandbox workspace，并在结束后销毁。
- sandbox 内按 WorkBuddy 形态提供 `.workbuddy/skills/<skill-name>/`。
- `instruction.md` 原文进入首条用户消息的 `<user_query>`，不复制进 workspace。
- 启动上下文尽量还原 WorkBuddy session 中观察到的 `system-reminder` 结构。
- 使用 CodeBuddy CLI 无头模式运行真实模型。
- 默认通过 Docker/OCI 容器强隔离当前 case workspace；CodeBuddy 权限参数只作为辅助护栏。
- grader 做 0/1 二元评分，结果写回 `result.json.graders[]`。
- 输出固定为 `batch.json`、`cases/<case_id>/result.json`、`cases/<case_id>/session.jsonl` 和 `cases/<case_id>/outputs/`。

首版明确不做：

- 仅依赖 CodeBuddy 权限体系作为主要隔离边界。
- baseline 快照保存（首版通过 `preview_matches_baseline` grader 支持逐行比对，但不保存 baseline 到结果包）。
- Markdown 报告。
- 重复 JSON 视图。
- 多套 profile。
- fake runner 作为用户路径。
- upload 或真实外部写入评测。
- 在原始代码仓库 cwd 中裸跑 Agent。
- 由 harness 生成 `.bin/`、`.runtime/` 或 `EVAL_CASE_CONTEXT.md` 来补运行能力。

判断原则：如果删掉某个字段、文件或参数后，评测仍然能定义、隔离运行、评分和复盘，就不进入首版。

## Technical Context

**Language/Version**: Python 3.13.2（harness 编排、评分、结果落盘） + Node.js 18+（CodeBuddy CLI 运行时）

**Primary Dependencies**: 现有仓库 Python 技术栈（Typer、Pydantic、pytest）、CodeBuddy CLI（`codebuddy` / `cbc`）

**Storage**: 本地文件系统。每次运行生成一个批次目录；每条 case 结果写入自己的结果目录。临时 sandbox 不属于结果包，运行后销毁。

**Testing**: pytest 单元测试、契约测试、集成测试；真实 CodeBuddy CLI 堂食收入单 case 冒烟测试在本机 Docker、CodeBuddy 登录态和 skill 运行前提满足时必须跑通。

**Target Platform**: 本地 Windows 开发环境发起评测；case 实际运行在一次性本地 sandbox workspace 中。workspace 不暴露原始代码仓库和用户主目录。

**Project Type**: Python 包 + 仓库级 CLI 入口 + 文件系统结果契约 + Docker/OCI 容器隔离边界。

**Performance Goals**: 单条真实 CodeBuddy 冒烟 case 能在稳定本地环境下完成；运行结束后 60 秒内完成证据整理、产物复制和评分。

**Constraints**:

- 用户发起命令固定为 `run_skill_eval_batch --suite <suite.yaml> --output_root <output-dir>`。
- 每条 case 必须在一次性 sandbox workspace 中运行，不能退回宿主机裸跑。
- sandbox 不挂载原始代码仓库和用户主目录。
- 业务产物只允许写入 sandbox `output/`，结束后复制到结果目录 `outputs/`。
- `instruction.md` 不作为文件出现在 workspace 中。
- skill 的可运行脚本必须由 skill 自己的 `scripts/` 提供并说明前提，harness 不生成隐藏运行时。
- 结果读取入口固定，不用额外报告文件解释同一批结果。
- token、成本等底层 CLI 暂时拿不到的指标仍保留字段，并写为 `null`。

## Project Structure

### Documentation

```text
specs/002-workbuddy-eval-harness/
├── README.md
├── plan.md
├── spec.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── case-manifest.md
│   ├── run-eval-batch.md
│   └── result-bundle.md
├── examples/
│   └── revenue-recognition-real-smoke/
│       ├── suite.yaml
│       └── cases/
│           └── revenue-recognition-dine-in-202605/
│               ├── instruction.md
│               ├── skills/
│               └── input/
└── tasks.md
```

### Source Code

```text
src/
├── cli/
│   └── run_skill_eval_batch.py
├── evals/
│   ├── cases/
│   ├── evidence/
│   ├── graders/
│   ├── runners/
│   ├── sandbox/
│   └── shared/
└── integrations/
    └── codebuddy_cli/
```

## Design

### 1. 评测集输入

suite YAML 只保留核心字段（外加可选的 suite 级模型和共享资源）：

```yaml
suite_id: revenue-recognition-real-smoke
model:
  id: glm-5
  config_file: ${EVAL_MODELS_JSON}
graders:
  - preview_file_exists
  - preview_matches_baseline
cases:
  - revenue-recognition-dine-in-202605
```

当多条 case 共用同一套 skill 和 input 时，可声明 suite 级共享路径：

```yaml
input: <共享输入目录>
skills: <共享 skill 目录>
```

`model` 是可选字段；声明 `model.config_file` 时，文件必须定义 `model.id`。case 级 `input/` 或 `skills/` 为空时，harness 自动回退到 suite 级路径。

case 的任务说明、skill 和输入文件放在 case 文件夹里：

```text
cases/<case_id>/
├── instruction.md
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
└── input/
```

### 2. Sandbox Materialize

每条 case 运行前，harness 创建一次性 sandbox workspace：

```text
<sandbox>/
├── input/
├── output/
└── .workbuddy/
    └── skills/
        └── <skill-name>/
            ├── SKILL.md
            ├── references/
            └── scripts/
```

case 源目录中的 `skills/<skill-name>/` 会复制到 sandbox 的 `.workbuddy/skills/<skill-name>/`。`instruction.md` 只作为首条用户消息内容使用，不进入 workspace 文件系统。

sandbox 不生成：

- `instruction.md`
- `EVAL_CASE_CONTEXT.md`
- `.bin/`
- `.runtime/`

### 3. WorkBuddy 上下文还原

已观察到的 WorkBuddy session 中，生产上下文不是独立 `role=system`，而是第一条 `role=user` 消息内的 `system-reminder` 块。harness 因此采用普通输入注入方式，而不是伪造第二套 system prompt。

启动输入包含：

- `user_info`：操作系统、shell、主题和 workspace 读写边界提示。
- `identity_context`：默认 WorkBuddy 身份模板。
- `product_identity`：`You are WorkBuddy, a powerful AI assistant.`
- `project_context`：sandbox workspace 文件结构摘要。
- `additional_data`：固定评测时间和 connector status；connector 默认全部 `disconnected`。
- `memory_and_skills_reminder`：WorkBuddy 可见提醒，但约束读写仍在 sandbox 内。
- `manually_attached_skills`：仅当 `instruction.md` 中出现 `/<skill-name>` 时注入。
- `user_query`：`instruction.md` 原文。

如果 CodeBuddy CLI 的 Skill 工具不能直接加载 sandbox skill，prompt 中必须提供 `.workbuddy/skills/<skill-name>/SKILL.md` 的显式路径作为降级入口。

### 4. 批量运行流程

runner 流程固定：

1. 读取 suite YAML。
2. 验证每个 case 文件夹包含 `instruction.md`、`skills/` 和 `input/`；解析 suite 级 `model` 与共享 `input`/`skills` 路径（如有）。
3. 为当前 case 创建 sandbox workspace。
4. 复制 `input/`（case 级为空时回退到 suite 级共享路径），创建 `output/`，按 WorkBuddy 风格 materialize skill（case 级为空时回退到 suite 级共享路径）。
5. 生成 WorkBuddy 风格 `system-reminder` + `<user_query>` 首条用户消息。
6. 如果 suite 声明 `model.config_file`，校验并复制该 `models.json` 到隔离 CodeBuddy 配置目录。
7. 以 sandbox workspace 为 cwd 运行 `codebuddy -p <prompt> --sandbox container --sandbox-new --sandbox-kill --output-format json`。
8. 从 stdout 或 session JSONL 回收最终响应。
9. 将 CodeBuddy 写出的原始 session JSONL 原样复制为结果目录的 `session.jsonl`。
10. 将 sandbox `output/` 复制到结果目录 `outputs/`。
11. 执行 suite YAML 声明的 graders。
12. 写入 `result.json`。
13. 销毁 sandbox。
14. 汇总写入 `batch.json`。

### 5. 结果文件

结果目录固定为：

```text
<output_root>/<batch_id>/
├── batch.json
└── cases/
    └── <case_id>/
        ├── result.json
        ├── session.jsonl
        └── outputs/
```

`batch.json` 回答：整批是否跑完、总 case 数、完成数、通过数、失败数、整体耗时、token 和成本。

`result.json` 回答：单条 case 是否完成、模型最终回答、grader 如何打分、耗时、token、成本、session 和 outputs 是否缺失。

`session.jsonl` 回答：CodeBuddy 原始记录了哪些用户消息、Agent 回复、工具调用、工具返回、provider 元数据、`reasoning` 和 session 标识。

`outputs/` 保存业务产物本身，例如 preview Excel。

### 6. Session

`session.jsonl` 来源不是 harness 猜测事件流，也不是归一化轨迹，而是 CodeBuddy / WorkBuddy 写出的原始 session JSONL。

规则：

- 直接复制 CodeBuddy 原始 session 文件，不做事件归一化。
- 不重命名事件类型，不屏蔽路径，不丢弃字段。
- 保留 `message`、`function_call`、`function_call_result`、`reasoning`、`providerData`、`sessionId`、时间戳、工具参数和工具输出。
- session 缺失时不合成假的轨迹文件，只在 `result.json.evidence.missing` 中记录 `codebuddy_session_jsonl`。
- Windows 上 CodeBuddy state 路径可能超过 260 字符，采集实现必须支持扩展长路径读取；结果包中仍只暴露普通相对路径 `session.jsonl`。
- `session.jsonl` 可能包含环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`，结果包应按敏感证据管理。

### 7. 评分器

grader 只输出 `1` 或 `0`。`verdict` 规则固定：所有 grader 都为 `1` 时是 `pass`，只要有一个 grader 为 `0` 就是 `fail`。

首版示例：

```yaml
graders:
  - preview_file_exists
  - preview_matches_baseline
```

扩展 grader 必须遵守：

- 可以读取 `result.json`、`session.jsonl`、`outputs/` 或受控远端结果。
- 输出写回 `result.json.graders[]`。
- `score` 只能是 `1` 或 `0`。
- 不新增额外结果文件。

### 8. 安全边界

首版评测按受控 workspace 思路运行。目标是验证 Agent 是否能理解任务、读取 skill、处理给定 input、生成 output、遵守边界，而不是验证真实外部写入或 upload。

不允许：

- 将仓库根目录作为 tool-root 暴露给 Agent。
- 将用户主目录挂载或加入 CodeBuddy workspace。
- 在 sandbox 之外写业务产物。
- 失败时退回宿主机裸跑。
- 默认执行 upload。
- 通过 `.bin/` 或 `.runtime/` 临时把仓库运行时注入 workspace。
- 把 CodeBuddy 权限检查当作主要隔离边界，绕过 Docker/OCI 容器运行。

如果后续要评测真实写动作，需要新的安全方案和新的评测契约。

## Validation Strategy

实现验收分四层：

- 契约层：suite YAML、case 文件夹、`batch.json`、`result.json`、`session.jsonl` 和 `outputs/` 字段稳定。
- 隔离层：真实运行时 Agent 只能看到 sandbox workspace，不能看到仓库根目录或用户主目录。
- 运行层：真实 CodeBuddy CLI 单 case 能跑通，并能拿到模型最终响应和 session。
- 评分层：`preview_file_exists` 和 `preview_matches_baseline` 能基于 `outputs/` 给出 0/1 `score`，并由聚合规则生成 `verdict`。

最终验收必须包含一次真实 CodeBuddy CLI 堂食收入 case 冒烟运行；如果当前 Docker、CodeBuddy 登录态或 skill 打包运行前提不满足，应明确判为环境失败，而不是降低隔离边界。
