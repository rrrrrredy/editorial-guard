# Editorial Guard

简体中文表达编辑与交付验收工具。StyleBench-ZH 判断模板依赖、表达效率、连贯性和场景匹配；DeliveryBench-ZH 判断不合交付阶段的过程旁白。两套任务独立评分，共享事实保真检查。

[项目站](https://rrrrrredy.github.io/editorial-guard/) · [v0.1.1 下载](https://github.com/rrrrrredy/editorial-guard/releases/tag/v0.1.1) · [结果与局限](reports/results.md)

本项目不检测作者是否为 AI，不以逃避检测为目标。数据来自程序事实底稿和真实模型调用，标注与评审由模型完成，没有人工标注或人类偏好验证。实验规模、分歧、失败和支持范围见 [实验协议](docs/experiment-protocol.md) 与 reports/ 中相应版本结果。

## 安装与使用

Python 3.11 或更新版本。下载对应版本的 wheel 后安装；从源码安装可运行：

```sh
python -m pip install -r requirements-runtime.lock
python -m pip install .
editorial-guard doctor
editorial-guard lint input.md --context context.example.json --mode both
```

lint 只提供规则线索，退出码 2 表示尚未完成语义验收；规则未命中不等于通过。配置文件不保存密钥，使用 DEEPSEEK_API_KEY、GLM_API_KEY。Codex 使用已合法登录的官方 CLI。

```sh
editorial-guard rewrite input.md --config config.json --context context.json --mode both --editor deepseek --judge glm --output candidate.md --sidecar review.json --receipt receipt.json
editorial-guard finalize candidate.md published.md --root . --config config.json --context context.json --mode both --receipt receipt.json
```

finalize 使用相同工作目录、任务上下文与配置，验证内容字节和签名后才写入目标。它只控制自身的本地路径。先确保原文、候选及目标均位于授权 root；候选、上下文、模型配置或规则变更会使原凭证失效。完整说明见 [验收边界](docs/acceptance.md)。

style、process、both 可独立选择。无需修改的合格文本允许原样保留。中文技术混排受到支持；英文主体、繁体和其他未校准文体保留原文并返回 unsupported/unvalidated，不默默翻译或继承中文分数。

## Skill 与集成

两个 Skill 位于 skills/style-editor-zh 和 skills/delivery-cleaner-zh，可安装至目标项目的 .agents/skills。仅生成候选不代表验收通过；正式验证集中在内核。项目 hook 的安装、信任、登记与卸载见 [Codex 集成](integrations/codex/README.md)。原生事件、手动加载、自动触发和外部 wrapper 的测试分别报告，不互相替代。当前已记录手动与自动Skill加载、受控finalize及篡改阻断；Windows宿主实测未观察到原生Stop触发，因此不宣称该路径已经可用，详见[集成结果](reports/integration-results.md)。

标准 API 配置见 config.example.json；官方支持的 Codex Coding Plan 客户端配置见 config.coding-plan.example.json。套餐并非任意自建 API 服务的额度，批量评测采用适用的标准 API。不同客户端与传输配置分别记录。

## 数据与复现

模型范围为 Codex、DeepSeek、GLM。数据设计包含80个校准家族和500个主数据家族；自然稿与受控稿共享 source_group_id，不重复计算独立家族。实际规模、标注覆盖、分歧和质量排除分别列在两套数据卡及下载包中，生成来源如实记录。完整本地构建为580个家族；公开范围为482个家族、964条实例，另外98个未评测锁定家族保留本地。公开的964条实例中，264条指定判定字段一致、680条有争议、20条证据不足，共保存1908份标注记录。分歧与缺失均保留，不能把模型共识当作人工真值。

协议0.2.0固定60个基础比较单元和20个四状态干预单元。核心比较只覆盖两个已暴露的合成家族，每套一个；历史保留响应与新增执行分开记录。这个案例研究不支持普遍效果或人类偏好声明，详见[实验协议](docs/experiment-protocol.md)。60个核心单元和20个四状态干预单元均已完成。检查加修复（B4）相对简短提示（B1）没有在这两个案例中显示稳定优势；具体分母、保真失败与裁判分歧见[结果报告](reports/results.md)。

两个套件分别保留数据卡、划分和结果。统计单位是 source_group_id，同源变体和重复评审不是独立样本。未完成保留测试的 locked_test 不发布；公开后不再视作未见测试集。可重复运行指的是协议和可观察配置复现，不保证动态模型服务逐字输出一致。

```sh
editorial-guard dataset validate --work-dir private-work --input samples.jsonl
editorial-guard eval report --work-dir private-work --output experiment-results
editorial-guard resume --work-dir private-work
```

resume 继续工作目录中保存的数据或实验任务，复用已完成请求和单元；仅查看持久化账本可加 --status-only。没有保存任务时明确返回未验收状态。不得通过更换工作目录绕过调用上限。产品安装包不包含数据集或隐藏评审答案；完整方法与已获准数据单独分发。

公开结果绑定矩阵、数据和评分器版本，可用 `python scripts/replay_results.py --directory reports` 离线重算。重放验证计算一致性，不把模型共识变成人工真值。原始传输日志和账户配置不进入公开包。

## 许可

软件、CLI、schema、运行提示、profiles、Skill 与集成模板使用 MIT；评测数据、标注、评分标准、研究和公开实验报告使用 CC BY 4.0。具体映射见 [LICENSING.md](LICENSING.md)，引用信息见 CITATION.cff。许可不创造原本不存在的权利，也不授予第三方材料的额外权利。模型服务条款、方法出处与再分发边界另见 research/ 与 THIRD_PARTY_NOTICES.md。
