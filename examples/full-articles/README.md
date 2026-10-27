# 完整文章改稿：删去无增量的重复，保留有用途的复述

这组案例把完整原文、首次候选、后续修订和不应修改的内容放在一起，便于判断改稿是否推进了表达。两篇均来自本项目已公开的合成材料，不是人类文章；`natural` 表示模型自然输出路线，不表示人类创作。

| 案例 | 完整正文 | 主要问题与保留内容 |
| --- | --- | --- |
| [工作报告](work-report/README.md) | [原文](work-report/original.md) · [示范稿](work-report/edited.md) · [全文并排](../../reports/article-study-20261027/artifacts/work-report.html) | 收紧同一限制的多次解释，把记录规则放近；保留样本范围、预计安排及证据限制。 |
| [参与者教程](tutorial/README.md) | [原文](tutorial/original.md) · [示范稿](tutorial/edited.md) · [全文并排](../../reports/article-study-20261027/artifacts/tutorial.html) | 合并段内的同义说明；保留引句、概念区分、十个章节和九项执行清单。 |

每个目录都有 `brief.md`、`previous-skill.md`、`updated-skill.md`：分别是简短改写提示、旧统一 Skill、新统一 Skill 初稿的一次完整输出。六份原始候选没有事后修补。`edited.md` 是观察候选后由本轮主编辑模型继续修订的示范，不能计为新 Skill 的首次输出成绩。

对这两篇稿件，三种方法都有局部收紧；新增指导没有显示出稳定优势，原始候选也均保留了不必要的重复。教程的三份候选都移除了受保护的独立引词，说明仅有保真要求仍不够。示范稿保留了修复这些问题的记录，也包含整段不改的选择。完整比较、方法快照和验证边界见[本次观察](../../reports/article-study-20261027/README.md)。

原文来自基线提交 `2be3a97` 的 `datasets/public_samples.json`，逐篇 ID、来源分区、原生成任务及正文哈希保存在各目录的 `source.json`。当前改稿要求另存于 `context.json`；原生成任务的字数要求没有被当成本轮压缩配额。选择依据是问题适配，没有随机抽样，也不是未见测试。

本文及两篇原文、候选和解释按 [CC BY 4.0](../../LICENSES/CC-BY-4.0.txt) 提供，署名 Editorial Guard / Song Luo。改写及改动记录在各案例中明示；合成内容不被宣称为人类创作或现实事实。
