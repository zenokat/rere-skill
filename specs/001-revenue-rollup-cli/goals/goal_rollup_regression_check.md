**Outcome**
对已经通过迭代循环开发完成的的cli工具 `list_recog_items.py` 和 `run_recog_rollup.py`做回归测试：循环跑所有14个已注册确认项目的validate+preview环节，并与202605的baseline对账，确认结果是否相符

**Verification surface**
跑完14个项目为止
`iteration_progress.md` 中记录的是开发阶段迭代循环的进度，当前目标是回归测试，不以文档中的进度记录为准

**Constraints**
- 禁止在跑完完整14个项目的回归测试前修改代码，把所有分析和建议都归拢到 `regression_notes.md` 中，完成全部测试再根据全局确定代码迭代方向

**Boundaries**
- `environment.md`：持续记录开发迭代过程中反复遇到的环境处理经验
- 联网：飞书API相关问题优先联网搜索官方文档，切忌自己频繁调API试错
- `sandbox-rules-allow-list`：频繁提权执行的命令在此提交审批，以减少提权阻碍，加速loop
- `iteration-progress.md`：迭代过程追踪，每个确认项目一个表格，每轮都记录测试元信息、测试结果、差异分析、解决方案、迭代增量、是否回归

**Iteration policy**
- 每跑完一个项目，如果对账一致则进入下一个项目，如果对账有差异，则追溯导致差异的原因并按项目记入 `regression_notes.md`，明确区分是业务上的模糊还是代码bug
- 每次记入差异原因之前，如果文档中有其他确认项目的差异，则考虑不同项目的差异是否可追溯到相同或关联的原因，重点记录

**Blocked stop condition**
- 遇到业务模糊需要用户决策的地方
- 硬阻碍，无法继续迭代（如遇到飞书权限问题必须人为开通）

