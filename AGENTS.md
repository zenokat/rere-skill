<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/001-revenue-rollup-cli/plan.md
<!-- SPECKIT END -->

## 沙盒白名单命令审批申请
在开发过程中如果某操作需要频繁做提权申请且申请的操作没有安全风险，为了以后不再需要麻烦总申请，可以将审批写入 `sandbox-rules-allow-list.md` ，一经审批以后都不会再面临提权需要。


## 环境记忆
请在开发过程中将遇到的任何多次尝试才成功的环境、工具交互经验固化在 `environment.md` ，避免屡次碰壁。
（如：飞书API的调用格式，读取中文文档使用UTF-8转义，调用飞书API填值时shell传中文出现编码丢失问题需要ASCII Unicode码转义等）

### 命令调用方式

- 本仓库不需要把所有命令都包一层。像 `git`、`rg`、`pytest` 这类标准工具，优先直接调用；
- 对于需要仓库级 Python 运行环境初始化的自研 CLI，需统一走仓库启动器 `.\.codex\scripts\rere.cmd`。
- 举例：
  `.\.codex\scripts\rere.cmd list_recog_items`

  `.\.codex\scripts\rere.cmd run_recog_rollup --validate --recog_id <recog_id> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --preview --recog_id <recog_id> --period <period> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --upload --append|--upsert --recog_id <recog_id> --result_file <result_file>`
