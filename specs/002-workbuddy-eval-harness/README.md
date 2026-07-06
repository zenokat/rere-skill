# WorkBuddy / CodeBuddy Eval Harness 使用说明

## 一句话结论

这套 harness 只做一件事：把每条评测 case 放进一次性隔离环境里，用 CodeBuddy CLI 尽量还原 WorkBuddy 的可见上下文真实执行，然后产出一套最小、清楚、可复盘的结果包。

评测者主要看四类东西：

- `batch.json`：整批评测有没有跑完、总共有多少 case、完成了多少、通过多少、失败多少、耗时多少。
- `cases/<case_id>/result.json`：单条 case 的运行状态、模型最终回答、grader 判断、耗时和 token 指标。
- `cases/<case_id>/session.jsonl`：CodeBuddy / WorkBuddy 原始 session JSONL，作为 Agent 轨迹的唯一事实源，逐行原文保留，不做归一化或路径屏蔽。
- `cases/<case_id>/outputs/`：这条 case 在隔离环境里产出的业务文件，例如 preview Excel。

首版不做 baseline 保存与比较，不生成 Markdown 报告，不生成重复 JSON 视图，不提供多套 profile。评测者只有一条固定路径：组织 case 文件夹，运行评测命令，读取结果文件。

## 基本概念

一次评测由一个 suite 文件夹组成。有两种组织方式：

**方式一：case 级自包含（适合少量、差异大的 case）**

```text
revenue-recognition-real-smoke/
├── suite.yaml
└── cases/
    └── revenue-recognition-dine-in-202605/
        ├── instruction.md
        ├── skills/
        │   └── revenue-recognition/
        │       ├── SKILL.md
        │       ├── references/
        │       └── scripts/
        └── input/
            └── 收银汇总表 202605.xlsx
```

**方式二：suite 级共享资源（适合大量 case 共用同一套 skill 和 input）**

当多条 case 使用相同的 skill 包和输入文件时，可以在 `suite.yaml` 中声明 suite 级共享路径，避免在每个 case 里重复放置。case 级 `skills/` 和 `input/` 为空目录即可，harness 会自动回退到 suite 级路径。

```text
Rollup_Core_20260630/
├── suite.yaml              # 声明 suite 级 input 和 skills 路径
└── cases/
    └── dine_in_revenue_202605/
        ├── instruction.md
        ├── skills/        # 空目录，回退到 suite 级
        └── input/          # 空目录，回退到 suite 级
```

每个 case 文件夹就是一份完整的评测材料：

| 路径 | 含义 |
|---|---|
| `instruction.md` | 发给 Agent 的任务说明。这里写真实用户请求、边界和必要提示。 |
| `skills/` | 本 case 提供给 Agent 的 skill 包。为空且 suite 级有 `skills` 声明时，自动回退。 |
| `input/` | 本 case 允许 Agent 读取的输入文件。为空且 suite 级有 `input` 声明时，自动回退。 |

不要在 case 里引用开发仓库绝对路径，不要要求 Agent 读取仓库根目录。case 应该像一个可搬走的包，离开原始代码仓库也能被放进隔离环境运行。

## suite.yaml

`suite.yaml` 描述这批评测包含哪些 case、用哪些 grader 判分，以及可选的 suite 级共享资源路径。

**最小示例（case 级自包含）：**

```yaml
suite_id: revenue-recognition-real-smoke
graders:
  - preview_file_exists
cases:
  - revenue-recognition-dine-in-202605
```

**带 suite 级共享资源的示例：**

```yaml
suite_id: Rollup_Core_20260630
model:
  id: glm-5
  config_file: ${EVAL_MODELS_JSON}
graders:
  - preview_file_exists
  - preview_matches_baseline
input: d:/AI/rere-agent/202605-source-excel
skills: d:/AI/rere-agent/skill/revenue-recognition
cases:
  - dine_in_revenue_202605
  - eleme_delivery_revenue_202605
```

| 字段 | 必填 | 含义 |
|---|---|---|
| `suite_id` | 是 | 评测集 ID，用来区分不同评测批次。 |
| `model` | 否 | suite 级模型选择。首版一个 suite 只指定一个模型。 |
| `model.id` | `model` 存在时必填 | CodeBuddy 模型 ID，会传给 `codebuddy --model`。 |
| `model.config_file` | 否 | CodeBuddy `models.json` 路径。支持绝对路径、相对 suite.yaml 的相对路径，以及 `${ENV_VAR}`。声明后 harness 会复制到每条 case 的隔离 CodeBuddy 配置目录。 |
| `graders` | 是 | 本批评测要运行的评分器。所有 grader 都只返回 `0` 或 `1`。 |
| `cases` | 是 | case 文件夹名列表。harness 会读取 `cases/<case_id>/`。 |
| `input` | 否 | suite 级共享输入文件目录的绝对路径或相对路径（相对于 suite.yaml 所在目录）。当 case 级 `input/` 为空时，harness 自动回退到此目录。 |
| `skills` | 否 | suite 级共享 skill 目录的绝对路径或相对路径（相对于 suite.yaml 所在目录）。当 case 级 `skills/` 为空时，harness 自动回退到此目录。 |

case 的 skill、输入和任务说明不再写在 YAML 里，而是放在 case 文件夹里（或通过 suite 级共享路径统一提供）。

如果声明了 `model.config_file`，该文件必须定义 `model.id`。否则 harness 会在加载 suite 时直接失败，避免你以为走自定义 API，实际回退到 CodeBuddy 内置模型。公开结果只记录配置指纹，不记录本机路径、文件内容或 API key。

## 隔离运行

每条 case 都会在一次性 sandbox workspace 中运行。sandbox 的目的不是整理目录，而是让 CodeBuddy 只围绕本 case 的材料工作，并把业务产物稳定收集到约定位置。运行 sandbox 不属于公开结果包，默认放在系统临时目录下的专用根目录，避免继承原始仓库的 `AGENTS.md`、历史 `.tmp` 或用户主目录上下文。

运行时，harness 会为每条 case 做这些事：

1. 创建一次性 sandbox workspace。
2. 把 `input/` 和 `skills/` materialize 到 workspace。
3. 在 workspace 内创建 `output/`，作为业务产物的唯一约定写入位置。
4. 把 `skills/<skill-name>/` 安装成接近 WorkBuddy 的加载结构：`.workbuddy/skills/<skill-name>/`。
5. 将 WorkBuddy 风格的 `system-reminder` 上下文和 `instruction.md` 中的用户请求作为首条用户消息发给 CodeBuddy。
6. 如果 suite 声明了 `model.config_file`，把该 `models.json` 复制到隔离的 CodeBuddy 配置目录。
7. 以 sandbox workspace 作为 CodeBuddy 的工作区运行 `codebuddy -p ...`。
8. 收集 session、最终回答、grader 结果和 `output/` 文件。
9. 把证据写入结果目录。
10. 销毁 sandbox workspace。

CodeBuddy 面对的 workspace 形态固定为：

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

隔离边界固定为：

- CodeBuddy 的工作区是当前 case 的 sandbox workspace。
- 原始代码仓库不作为 CodeBuddy workspace 暴露。
- 用户主目录不作为 CodeBuddy workspace 暴露。
- CodeBuddy 不应读取或写入 sandbox workspace 之外的业务文件。
- 业务产物只能写入 sandbox 的 `output/`，结束后复制到 `cases/<case_id>/outputs/`。
- `instruction.md` 是 case 源材料，运行时作为用户请求进入首条消息；它不需要作为文件留在 CodeBuddy workspace 中。
- sandbox workspace 不包含 `EVAL_CASE_CONTEXT.md`、`.bin/` 或 `.runtime/` 这类额外辅助目录。

harness 使用 Docker/OCI 容器作为默认安全边界。运行时 CodeBuddy CLI 以当前 sandbox workspace 为 cwd，并启用 `--sandbox container --sandbox-new --sandbox-kill`；容器只应看到当前 case workspace，不能挂载原始代码仓库或用户主目录。CodeBuddy 权限参数只作为辅助护栏和 session 取证信号，不再承担主要隔离职责。

CodeBuddy CLI 自己的会话历史、日志、模型配置副本和缓存写入独立的内部 `codebuddy-state/` 目录，不放进 case workspace。这样业务 sandbox 只承载 `input/`、`output/` 和 `.workbuddy/`，状态缓存清理失败也不会被误判为业务证据缺失。

如果 CodeBuddy CLI、登录状态、Docker、容器网络或必要运行时缺失，这条 case 应该判为环境失败，并写入 `result.json`，而不是退回到非 sandbox workspace 裸跑。

## WorkBuddy 上下文还原

真实 WorkBuddy session 中没有单独的 `role=system` 消息。已观察到的形态是：WorkBuddy 会把生产上下文包装进第一条 `role=user` 消息里的 `<system-reminder ...>` 块，例如：

- `user_info`：操作系统、shell、界面主题等。
- `identity_context`：默认 WorkBuddy 身份模板。
- `product_identity`：声明当前产品身份是 WorkBuddy。
- `project_context`：当前工作区文件概览。
- `additional_data`：固定评测时间和连接器状态；连接器默认全部 `disconnected`。
- `memory_and_skills_reminder`：记忆和 skill 管理规则。
- `manually_attached_skills`：本轮手动挂载的 skill 名称与描述。
- `user_query`：用户原始请求。

CodeBuddy CLI 自己可能还有内置 system prompt。harness 不尝试覆盖或复制它，也不额外伪造第二套 system prompt。首版做法是：把 WorkBuddy 生产上下文作为普通输入中的 `system-reminder` 片段提供给 CodeBuddy，让它尽量接近 WorkBuddy 的可见上下文，同时避免两个 system prompt 相互打架。

`manually_attached_skills` 不作为额外 case 配置项。harness 根据 `instruction.md` 中的用户请求判断：如果请求里出现 `/<skill-name>` 形式的斜杠指令，例如 `/revenue-recognition`，就视为用户在真实 WorkBuddy 交互中手动调用了该 skill，并在 `manually_attached_skills` 中注入对应 skill 信息。没有斜杠指令时，skill 仍可作为 workspace 材料存在，但不会被声明为本轮手动挂载。

在 sandbox workspace 中，skill 的呈现方式要尽量接近 WorkBuddy：

```text
<sandbox>/
├── input/
├── output/
└── .workbuddy/
    └── skills/
        └── revenue-recognition/
            ├── SKILL.md
            ├── references/
            └── scripts/
```

Agent 可以通过 Skill 工具加载 `revenue-recognition`，也可以按上下文读取 `.workbuddy/skills/revenue-recognition/SKILL.md`。如果 CodeBuddy CLI 的 Skill 工具无法识别本地 sandbox skill，harness 必须在 prompt 中明确给出 skill 路径作为降级入口。

## Skill 脚本

skill 附带的可运行脚本应放在 skill 自己的 `scripts/` 目录下，并在 `SKILL.md` 或 `references/` 中用相对路径说明如何调用。harness 不额外生成 `.bin/` 或 `.runtime/` 来补脚本运行能力。

推荐约束：

- 脚本路径相对 skill 根目录，例如 `scripts/run_recog_rollup.py`。
- 脚本应提供 `--help`，让 Agent 能自己理解参数。
- 脚本应非交互运行，不依赖 TTY 确认、密码输入或弹窗。
- 脚本应把输入参数、环境变量和输出位置说清楚。
- 脚本应优先输出结构化结果，例如 JSON。
- 脚本如果依赖第三方包，应在 skill 包内、脚本内联元数据或清晰的运行前提中声明，而不是隐式依赖原始开发仓库。

如果某个 skill 的 `scripts/` 离开原始仓库后无法运行，这条 case 应判为 skill 打包或环境失败，而不是由 harness 在 workspace 中临时补一套隐藏运行时。

## 本机运行前的 Codex / Docker policy

本 harness 的主隔离边界是 CodeBuddy 的 Docker/OCI 容器。外层 Codex 会话不应再使用 Windows `unelevated` restricted-token sandbox，否则可能出现两个表面像权限问题、实质是外层沙盒拦截的问题：

- 非提权 `docker version` 无法访问 `npipe:////./pipe/dockerDesktopLinuxEngine`，即使用户已经在 `docker-users` 组里。
- `D:\tmp` 已经给了 Users / Authenticated Users 写权限，但 Codex 非提权命令仍无法创建评测 sandbox 目录。

不要再通过修改用户级 `C:\Users\<user>\.codex\config.toml` 里的 `[windows] sandbox = "unelevated"` 来修复本仓库评测问题。当前 Windows / Codex Desktop 环境已经多次验证：改这个全局配置后，Codex 重启可能直接无法启动，必须改回才能进入会话。

推荐按任务使用一次性启动参数。常规调试优先用下面的方式启动本仓库会话：

```powershell
codex -C D:\AI\rere-agent --sandbox workspace-write --add-dir D:\tmp
```

如果当前 Codex / Windows 会话仍然拦截 `D:\tmp` 写入或 Docker named pipe，可以在受控本机调试场景直接用：

```powershell
codex -C D:\AI\rere-agent --sandbox danger-full-access
```

这只是在外层 Codex 会话放开本机文件沙盒，真实 eval case 的隔离仍由 CodeBuddy 的 Docker/OCI 容器负责。不要把修改全局 `windows.sandbox` 当成常规修复手段。Docker Desktop 的 `tcp://localhost:2375 without TLS` 只适合短时诊断，常规运行应关闭。

## 发起评测

使用仓库启动器运行：

```powershell
# 临时 smoke 测试 -- 输出到 .tmp/evals/
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml `
  --output_root .tmp/evals/revenue-real-smoke

# 正式评测 -- 输出到 evals/results/
.\.codex\scripts\rere.cmd run_skill_eval_batch `
  --suite evals/datasets/Rollup_Core_20260630/suite.yaml `
  --output_root evals/results/Rollup_Core_20260630
```

`--output_root` 决定结果输出位置：临时调试和 smoke 测试放 `.tmp/evals/`，正式评测结果统一放 `evals/results/<suite_id>/`。

正式评测建议把模型写在 suite.yaml 的 `model` 字段。`--model <model-id>` 只作为临时覆盖入口；如果 suite 同时声明了 `model.config_file`，覆盖后的模型 ID 也必须存在于该配置文件中。

命令执行后，stdout 只需要返回：

```json
{
  "batch_id": "20260627-130214-revenue-recognition-real-smoke",
  "status": "passed",
  "case_counts": {
    "total": 1,
    "completed": 1,
    "passed": 1,
    "failed": 0
  },
  "batch_json": ".tmp/evals/revenue-real-smoke/20260627-130214-revenue-recognition-real-smoke/batch.json"
}
```

## 结果文件

一次运行只需要看下面这些文件：

```text
<output_root>/<batch_id>/
├── batch.json
└── cases/
    └── <case_id>/
        ├── result.json
        ├── session.jsonl
        └── outputs/
            └── <case产物文件>
```

不会生成：

- `summary.md`
- `evidence.md`
- `diff.md`
- `agent-result.json`
- `artifact-index.json`
- `baseline.json`
- `compare/diff.json`
- `stdout.txt`
- `stderr.txt`
- `final.json`
- `scorecard.json`

## batch.json 怎么看

`batch.json` 是整批评测入口。

```json
{
  "batch_id": "20260627-130214-revenue-recognition-real-smoke",
  "suite_id": "revenue-recognition-real-smoke",
  "model": {
    "requested": "glm-5",
    "config": {
      "source": "suite_config_file",
      "fingerprint": "sha256:9d3f0c9a2c4b7e11"
    }
  },
  "status": "passed",
  "case_counts": {
    "total": 1,
    "completed": 1,
    "passed": 1,
    "failed": 0
  },
  "metrics": {
    "duration_ms": 48231,
    "tokens": {
      "input": null,
      "output": null,
      "total": null
    },
    "cost": {
      "amount": null,
      "currency": null
    }
  }
}
```

重点看：

| 字段 | 判断方式 |
|---|---|
| `status` | 整批是否通过。 |
| `model.requested` | 本批请求的 CodeBuddy 模型；为 `null` 时表示使用默认模型。 |
| `model.config` | 只在使用 suite `model.config_file` 时出现；记录配置来源和指纹，不记录 API key。 |
| `case_counts.total` | 本轮总 case 数。 |
| `case_counts.completed` | 完成运行、取证和评分的 case 数。 |
| `case_counts.passed` / `case_counts.failed` | 有多少 case 被 grader 判为通过或失败。 |

每条 case 的具体情况不写在 `batch.json` 里。要看某条 case，直接打开 `cases/<case_id>/result.json`。

## result.json 怎么看

`result.json` 是单条 case 的完整结果。

```json
{
  "case_id": "revenue-recognition-dine-in-202605",
  "status": "completed",
  "verdict": "pass",
  "score": 1,
  "final_response": "已完成 202605 堂食收入汇总 preview，未执行 upload。",
  "model": {
    "requested": "glm-5",
    "observed": "glm-5",
    "config": {
      "source": "suite_config_file",
      "fingerprint": "sha256:9d3f0c9a2c4b7e11"
    }
  },
  "metrics": {
    "duration_ms": 48231,
    "tokens": {
      "input": null,
      "output": null,
      "total": null
    },
    "cost": {
      "amount": null,
      "currency": null
    }
  },
  "graders": [
    {
      "id": "preview_file_exists",
      "type": "code",
      "score": 1,
      "summary": "已在 outputs/ 中找到本次 preview 文件。",
      "evidence": {
        "file": "outputs/202605_dine_in_revenue.xlsx",
        "size_bytes": 18642,
        "sha256": "..."
      }
    }
  ],
  "evidence": {
    "session_path": "session.jsonl",
    "outputs_path": "outputs/",
    "missing": []
  }
}
```

读取顺序：

1. 看 `status`：这条 case 是否完成运行。
2. 看 `verdict` 和 `score`：grader 是否判定通过。`score` 只会是 `1` 或 `0`。
3. 看 `final_response`：模型最终回答是什么。
4. 看 `model.requested` / `model.observed`：请求模型和实际采到的模型是否一致；如果使用自定义模型配置，再看 `model.config.fingerprint` 是否存在。
5. 看 `graders[].summary`：每个 grader 为什么给 `1` 或 `0`。
6. 看 `evidence.missing`：证据是否缺失。
7. 看 `outputs/`：业务产物是否真的存在。

## session.jsonl 怎么看

`session.jsonl` 是 CodeBuddy / WorkBuddy 原始 session 的逐行原文，每一行是一个原始事件 JSON。它是 Agent 轨迹的**唯一事实源**：harness 直接把 CodeBuddy 写出的 session 文件原样复制过来，不做归一化、不重命名事件、不屏蔽路径、不丢弃字段。

原始事件类型由 CodeBuddy 决定，常见的有：

| 事件类型 | 含义 |
|---|---|
| `message` + `role=user` | 用户消息（含 system-reminder 上下文与 user_query） |
| `message` + `role=assistant` | Agent 回复（含完整 output_text） |
| `function_call` | 工具调用（含完整 arguments） |
| `function_call_result` | 工具返回（含完整 stdout/stderr/exit code） |
| `reasoning` | 底层思维链（按 CodeBuddy 原样保留） |

事件里还包含 `providerData`（模型、token 用量）、`sessionId`、时间戳等原始字段，全部保留。评测者可以直接在原始事件里看到 Agent 实际读了哪个文件、跑了什么命令、工具返回了什么——包括完整路径，不会有 `<host-path>` 之类的屏蔽。

注意：`session.jsonl` 是原始敏感证据包，可能包含工具输出里的环境变量、凭据片段、绝对路径、provider 细节和 `reasoning`。它适合本地复盘和受控归档，不适合公开分享；如果真实凭据被采进 session，应先轮换凭据，再分发结果包。

Windows 上 CodeBuddy state 里的真实 session 路径可能超过 260 字符。harness 采集时必须支持 Windows 扩展长路径读取 `codebuddy-state/<case>/projects/<cwd-id>/*.jsonl`；结果包里仍只暴露普通相对路径 `session.jsonl`。

因为它是原始 session，体量较大且包含 provider 细节。如果只需要快速复盘核心对话与工具使用，可以用 `tools/transcript-jsonl-viewer.html` 在浏览器里渲染，或自行写筛选脚本读取。

如果某条 case 没有捕获到 session（例如环境失败、CodeBuddy 未写出 session 文件），`session.jsonl` 不会生成，并在 `result.json` 的 `evidence.missing` 里记为 `codebuddy_session_jsonl`。

## outputs/ 怎么看

`outputs/` 是这条 case 在隔离环境里产生的文件集合。它不是额外报告，而是业务产物本身。

规则固定：

- Agent 运行时只能把业务产物写到 sandbox 的 `output/`。
- harness 结束后把 `output/` 原样复制到结果目录的 `cases/<case_id>/outputs/`。
- grader 如果引用产物，必须使用 `outputs/...` 相对路径。
- `outputs/` 可以为空，但目录必须存在。

## 评分器

grader 只做 0/1 二元判断。`suite.yaml` 里写了哪些 grader，本批评测就跑哪些 grader。

```yaml
graders:
  - preview_file_exists
  - preview_matches_baseline
```

当前可用的评分器：

| grader ID | 判断逻辑 |
|---|---|
| `preview_file_exists` | 检查 `outputs/` 中是否存在本次评测产出的 preview 文件。只要文件存在且非空就给 `1`，否则给 `0`。适合作为最低通过门槛。 |
| `preview_matches_baseline` | 从 `outputs/` 的 preview Excel 中提取结果行，与飞书 baseline 记录逐行逐字段比对。完全一致给 `1`，有任何差异给 `0` 并在 evidence 中报告差异类型、差异数量和样本。需要运行环境能访问飞书 API。 |

每个 grader 写回 `result.json.graders[]`：

```json
{
  "id": "preview_file_exists",
  "type": "code",
  "score": 1,
  "summary": "已在 outputs/ 中找到本次 preview 文件。",
  "evidence": {
    "file": "outputs/202605_dine_in_revenue.xlsx"
  }
}
```

`verdict` 的计算规则固定：

- 所有 grader 的 `score` 都是 `1`，`verdict` 就是 `pass`。
- 只要任意一个 grader 的 `score` 是 `0`，`verdict` 就是 `fail`。
- 如果 grader 无法读取证据，也返回 `score: 0`，并在 `summary` 里说明原因。

grader 可以评很多东西：`outputs/` 文件、`result.json`、`session.jsonl`、Agent 是否调用了某个工具、是否触碰禁止动作，或者受控远端结果。扩展方式是新增 grader 代码或模型 grader，不是增加一堆 case 配置字段。

## 推荐工作流

建立一条新 case：

1. 新建 `cases/<case_id>/`。
2. 写 `instruction.md`。
3. 把被测 skill 放入 `skills/<skill-name>/`。
4. 把允许 Agent 使用的输入文件放入 `input/`。
5. 在 `suite.yaml` 的 `cases` 中加入 `<case_id>`。
6. 在 `suite.yaml` 的 `graders` 中选择评分器。
7. 运行 `run_skill_eval_batch`。
8. 看 `batch.json`。
9. 看 `cases/<case_id>/result.json`。
10. 看 `cases/<case_id>/session.jsonl` 和 `outputs/`。

分析失败：

1. 先看 `batch.json.case_counts.failed`。
2. 打开失败 case 的 `result.json`。
3. 用 `status` 判断是环境失败、运行失败还是评分失败。
4. 用 `graders[]` 判断哪个评分器给了 `0`。
5. 用 `session.jsonl` 复盘 Agent 卡在哪一步。
6. 用 `outputs/` 确认产物是否真的生成。

## 当前验收标准

首版 harness 需要满足：

- 每条 case 以一次性本地 sandbox 作为 CodeBuddy workspace，结束后销毁 sandbox。
- CodeBuddy 的 case workspace 不包含原始代码仓库或用户主目录。
- case 以文件夹组织，包含 `instruction.md`、`skills/` 和 `input/`。
- suite YAML 包含 `suite_id`、`graders`、`cases`，可选 `model` 指定 suite 级模型，可选 `input` 和 `skills` 用于 suite 级共享资源。
- 如果 suite 声明 `model.config_file`，harness 必须把该模型配置复制到隔离 CodeBuddy 配置目录，并在模型 ID 不存在时失败。
- 当 case 级 `input/` 或 `skills/` 为空时，harness 自动回退到 suite 级共享路径。
- sandbox 中的 skill 加载方式尽量还原 WorkBuddy 的 `.workbuddy/skills/<skill-name>/`。
- 启动上下文尽量还原 WorkBuddy 的 `system-reminder` 形态，但不覆盖 CodeBuddy CLI 自带 system prompt。
- 每条 case 输出 `result.json`、`session.jsonl` 和 `outputs/`。
- 批次根目录只输出 `batch.json`。
- grader 可扩展，但结果仍写回 `result.json.graders[]`。
