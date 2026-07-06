# 环境与工具交互记忆

- 飞书相关 CLI 或调试脚本默认不要继承系统代理。本仓库中的 Feishu HTTP 客户端默认使用 `trust_env=False`；只有在明确需要继承系统代理时，才设置 `RERE_TRUST_ENV_PROXIES=true`。
- 在 PowerShell 或 Python heredoc 里临时调试飞书接口、对账脚本时，尽量不要硬编码中文字段名或中文 sheet 名。优先从实际 preview 文件、远端配置或代码对象中读取字段名，减少 shell 编码链路带来的噪音。
- 若必须在 heredoc 中传中文字段名或中文字段值，优先写成 Unicode 转义（如 `\u671f\u95f4`）。否则内容可能在 shell 编码链路里退化成 `??` 或 `????`，进一步触发飞书侧误导性报错。
- 飞书接口报错较多或接口语义不确定时，优先查官方文档或仓库内参考资料，避免靠高频试错去反推接口行为。
- 需要申请稳定白名单入口时，优先使用脚本文件 + `powershell.exe -File` 形式，而不是把整段逻辑塞进 `powershell.exe -Command`；前者更容易做可复用、可审批的命令前缀。
- 飞书多维表 `records/search` 的分页参数需要放在 query params 里传 `page_token`；若把 `page_token` 放进 POST body，容易出现重复返回第一页、分页不推进的假死现象。
- 大体量目录型 `preview` / `validate` 和飞书 baseline 拉取常常超过默认 120s 窗口；这类项目应提前放宽命令超时，避免结果已生成但外层工具先超时导致重跑。
- Windows 本地跑 `pytest` 时，若默认 `tmp_path` 落到用户目录下的 `AppData\\Local\\Temp\\pytest-of-*` 且该目录权限异常，测试会在 fixture setup 阶段直接报 `PermissionError`。稳定做法是把 pytest 临时目录固定到仓库内可写路径，例如 `tests/_pytest_tmp/`。
- 当前 Codex 沙盒中，即使工作区本身可写，涉及 `.git` 元数据写入的 Git 操作（例如 `git checkout -b`、`git branch -m`、更新 `index.lock` 或 `logs/refs`）也可能因权限限制失败。遇到这类报错时，应优先判断为沙盒权限问题并直接申请提权，而不是误判为仓库损坏或分支状态异常。
- `sandbox-rules-allow-list.md` 只是审批申请台账，不是自动生效入口；如果只写"可以申请白名单"而没有把"提权前先查、缺口先登记、真正生效文件是 `.codex/rules/*.rules`"写成明确步骤，后续 Codex 线程通常只会直接走单次提权，不会主动维护台账。稳定做法是把这套动作写进 `AGENTS.md`，并要求与 `environment.md` 同级检查。
- WorkBuddy 作为 skill 运行环境时，用户导入的 skill 会安装到 `C:\ProgramData\WorkBuddy\users\<user_id>\.workbuddy\skills\<skill-name>\`；`Skill` 工具默认只加载 `SKILL.md`，需要由指令明确要求再读取 `references/*.md`。随包脚本运行在 WorkBuddy 自带 Python 下，不会天然拥有本仓库的 `src/cli`、`.venv` 或 PATH 中的 `list_recog_items` / `run_recog_rollup`，因此若 skill 只打包包装脚本而未打包底层 CLI，应预期失败类型为“底层 CLI 未安装 / 未指定 tool-root”。
- 读取 CodeBuddy 官方 CLI 文档做方案核对时，PowerShell 里直接用 `Invoke-WebRequest -UseBasicParsing <url>` 抓页面源码通常比依赖沙盒内置网页检索更稳；若要提取正文，可先截取 `<main class="main">...</main>` 再去标签并 `HtmlDecode`。这类动作属于只读公开网页，适合登记为可复用低风险提权前缀。
- CodeBuddy CLI 官方 npm 包为 `@tencent-ai/codebuddy-code`，安装后通常提供 `codebuddy` 和 `cbc` 两个入口。首次无头运行前需要先启动交互式 `codebuddy`，在登录方式选择界面完成浏览器授权；完成后 `codebuddy -p "<prompt>" --output-format json` 才能进入真实模型调用。
- CodeBuddy CLI 2.112.0 在 Windows / PowerShell 下的 `-p` 无头调用有时会把模型响应写入本地 session JSONL（如 `%USERPROFILE%\.codebuddy\projects\<cwd-id>\<session-id>.jsonl`），同时 stdout 为空或不稳定。做 harness 证据采集时，应优先读 stdout；若 stdout 为空但日志/session 显示模型已完成，则回收新产生或更新的 session JSONL 中最后一条 assistant `output_text` 作为最终响应证据。
- CodeBuddy CLI 的无头权限参数顺序敏感：权限相关参数需要放在 `-p <prompt>` 之前，否则无头模式下可能无法处理权限提示。当前 eval harness 不应使用 `--dangerously-skip-permissions`，而应使用 CodeBuddy 权限参数把 `Read/Edit/Write` 收敛到 sandbox workspace；如果 CLI 版本或平台权限能力无法做到 workspace 级约束，应把 case 记为环境失败。
- `skill/revenue-recognition/scripts/run_recog_rollup.py` 传入 `--tool-root` 后，底层工具会以 tool-root 作为工作目录；此时 `--source_file` 传相对路径会被解析到仓库根目录下，容易报 `source_file path does not exist`。在 eval workspace 中调用该随包脚本时，稳定做法是把 case 输入文件 materialize 后传绝对路径。
- pytest 临时目录不要硬编码到 `tests/_pytest_tmp/`。在当前 Windows 受限沙盒中，该目录可能因为历史残留 ACL 或只读状态导致 `tmp_path` fixture 创建文件时报 `PermissionError`。稳定做法是让 `tests/conftest.py` 优先读取 `PYTEST_BASETEMP`，本地 Codex 运行时可显式设置到 `D:\tmp\rere-agent-pytest`，再退回仓库 `.tmp/pytest-tmp` 或系统临时目录。
- pytest 在 Windows 受限沙盒中默认创建 per-test `tmp_path` 目录时，可能生成当前低权限 token 无法继续写入的 ACL；表现为 base temp 可写，但 `tmp_path / "file"` 或 `tmp_path / "child"` 报 `PermissionError`。稳定做法是在 `tests/conftest.py` 覆盖 `tmp_path` fixture，用 `mode=0o777` 和普通继承权限创建 per-test 目录，并在返回前做嵌套写入 probe。
- eval harness 在 Windows 上不要把内部 sandbox 路径拼得过长。`output_root / batch_id / _sandboxes / case_id / .workbuddy / skills / ...` 这类路径很容易触发 `WinError 206 filename too long`，尤其 pytest 临时目录本身已经很长。稳定做法是公开结果路径保留完整 `case_id`，内部运行目录使用短目录名和 hash 后缀，例如 `_s/<case-prefix>-<hash>`。
- 运行 `model.config_file: ${EVAL_MODELS_JSON}` 的 eval suite 前，优先把 `EVAL_MODELS_JSON` 写在仓库根目录本地 `.env` 中；`run_skill_eval_batch` 会先加载 `.env` / `.env.local`。若只在临时 PowerShell 会话里设置变量，通过 `Start-Process` 启动批量评测时也能继承，但这种做法容易遗忘。未配置时 harness 会在启动阶段报 `model.config_file references missing environment variable(s): EVAL_MODELS_JSON`。
## 2026-06-29 Codex / Docker 沙盒策略
- 当前仓库的 eval harness 已经把单条 case 的主隔离边界交给 Docker/OCI 容器；外层 Codex 再使用 Windows `unelevated` restricted token 会拦截 Docker named pipe，并可能导致 `D:\tmp` 即使 NTFS ACL 放开也无法写入。
- 历史尝试：曾尝试把用户级 `C:\Users\<user>\.codex\config.toml` 中 `[windows] sandbox = "unelevated"` 备份后注释掉，但这台机器上重启 Codex 会导致启动失败，必须改回才能进入会话。后续不要再把修改这个全局配置作为默认修复方案。
- 如果需要在保持 sandbox 的情况下启动本仓库，推荐显式使用 `codex -C D:\AI\rere-agent --sandbox workspace-write --add-dir D:\tmp`，这样外层 Codex 可写评测 sandbox 根目录；真实 case 仍由 CodeBuddy 的 Docker container sandbox 隔离。
- 2026-06-29 实测：在当前 Windows / Codex Desktop 环境中，反复修改用户级 `[windows] sandbox = "unelevated"` 会导致 Codex 重启后无法正常启动，必须改回才能进入会话。因此不要再把“修改全局 `windows.sandbox`”作为本机修复建议；需要绕过外层文件沙盒时，应使用一次性启动参数（例如 `codex -C D:\AI\rere-agent --sandbox danger-full-access` 或在受控场景用 `--dangerously-bypass-approvals-and-sandbox`），避免破坏全局可启动配置。
- 如果非提权 `docker version --format '{{.Server.Version}}'` 仍报 `permission denied ... dockerDesktopLinuxEngine`，先确认用户在 `docker-users` 组并已重新登录；若仍失败，优先判断为 Codex/Windows sandbox token 问题，不要继续修改 D 盘 ACL。
- Docker Desktop 的 `Expose daemon on tcp://localhost:2375 without TLS` 只适合短时诊断；若临时使用，应优先设 `DOCKER_HOST=tcp://127.0.0.1:2375`，不要用 `localhost`，并在诊断后关闭 2375。
