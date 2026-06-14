<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/001-revenue-rollup-cli/plan.md
<!-- SPECKIT END -->

## 沙盒白名单命令审批申请
在开发过程中如果某操作需要频繁做提权申请且申请的操作没有安全风险，为了以后不再需要麻烦总申请，可以将审批写入 `sandbox-rules-allow-list.md` ，一经审批以后都不会再面临提权需要。


## 环境记忆
查阅`environment.md`，了解开发过程中可能遇到的环境问题与处理经验，并将新遇到的任何多次尝试才成功的环境、工具交互经验写入，形成复利闭环

### 应该记什么
`environment.md` 只记录“跨多轮迭代、跨多个任务仍会反复遇到”的通用环境或工具交互经验，例如：
- shell / PowerShell / heredoc 的编码、转义、参数传递、代理继承问题；
- 本地运行环境、权限、白名单、网络、路径、临时目录等带来的稳定约束；
- 第三方平台或外部工具在“如何调用”层面的通用坑位与稳定做法。
### 不要记什么
以下内容不要记入 `environment.md`：
- 某个 `recog_id`、某份样本数据、某个目录、某张表、某次对账的项目特例；
- 已经被源码吸收并有测试覆盖的实现细节，除非仍需要保留一条“如何与环境交互”的操作约束；
- 业务规则、字段语义、聚合口径、上传键规则、预处理规则等项目逻辑。


### 命令调用方式

- 本仓库不需要把所有命令都包一层。像 `git`、`rg`、`pytest` 这类标准工具，优先直接调用；
- 对于需要仓库级 Python 运行环境初始化的自研 CLI，需统一走仓库启动器 `.\.codex\scripts\rere.cmd`。
- 举例：
  `.\.codex\scripts\rere.cmd list_recog_items`

  `.\.codex\scripts\rere.cmd run_recog_rollup --validate --recog_id <recog_id> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --preview --recog_id <recog_id> --period <period> --source_file <source_file>`

  `.\.codex\scripts\rere.cmd run_recog_rollup --upload --append|--upsert --recog_id <recog_id> --result_file <result_file>`

## git提交要求
- 使用中文