**Outcome**
所有确认项目，工具脚本跑出的结果与baseline完全一致

**Verification surface**
baseline对账

**Constraints**
spec/001-revenue-rollup 目录下的所有文档以及`constitution.md`

**Boundaries**
- `environment.md`：持续记录开发迭代过程中反复遇到的环境处理经验
- 联网：飞书API相关问题优先联网搜索官方文档，切忌自己频繁调API试错
- `sandbox-rules-allow-list`：频繁提权执行的命令在此提交审批，以减少提权阻碍，加速loop
- `iteration-progress.md`：迭代过程追踪，每个确认项目一个表格，每轮都记录测试元信息、测试结果、差异分析、解决方案、迭代增量、是否回归

**Iteration policy**
- 每轮迭代先看`iteration-progress.md`中当前确认项目最近一次记录的“解决方案”是否为“业务TBD”，如果是则什么也不做
- 遇到差异先溯因，如果是代码层面的bug自己修并记录然后进入下轮iteration，如果最终追究到业务语义上的模糊或差异，则记录“业务TBD”
- 一个确认项目实现baseline对账一致后，调用list_recog_items寻找下一个确认项目；如果一个确认项目没有通过对账，**禁止**进入下一个确认项目的迭代循环

**Blocked stop condition**
- 遇到业务模糊需要用户决策的地方
- 硬阻碍，无法继续迭代（如遇到飞书权限问题必须人为开通）

详细原则以 `quickstart.md` 为准。