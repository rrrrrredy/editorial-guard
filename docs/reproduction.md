# 安装、运行与重放

软件许可：MIT。需要Python 3.11或更新版本。先准备 UTF-8 编码的 input.md，并把对应资料和要求填写到 context.example.json。安装源码后运行：

```text
python -m pip install .
editorial-guard doctor
editorial-guard lint input.md --mode both --context context.example.json
editorial-guard rewrite input.md --mode both --config config.example.json --context context.example.json --work-dir ../editorial-guard-private --sidecar review.json
editorial-guard resume --work-dir ../editorial-guard-private
```

将DEEPSEEK_API_KEY、GLM_API_KEY设置为进程环境变量。不要把真实密钥写进配置、终端参数、站点或Git。Codex使用其官方CLI登录机制。

规则lint只能提供线索，正常返回unchecked并使用退出码2；它不是完整语义验收。rewrite默认stdout仅正文，stderr为诊断，不通过时保留原稿，候选保存在sidecar。退出码0通过、1内容不合格、2无法判定、3运行错误。

验收已有候选并交付：

```text
editorial-guard verify input.md --candidate candidate.md --config config.example.json --context context.example.json --judge glm --work-dir .eg --receipt receipt.json
editorial-guard finalize candidate.md delivered.md --receipt receipt.json --config config.example.json --context context.example.json --mode both --root . --work-dir .eg
```

凭证只在语义通过后生成。配置和稿件变化须重新验收。目标父目录须存在，输出只限授权本地根目录。

数据构建和实验需要真实模型资源；成功记录自动重放，重复命令不代表重复请求：

```text
editorial-guard dataset build --config config.example.json --work-dir ../editorial-guard-private --phase calibration
editorial-guard dataset annotate --config config.example.json --work-dir ../editorial-guard-private --phase calibration
editorial-guard dataset validate --input ../editorial-guard-private/data/calibration/annotated.jsonl --work-dir ../editorial-guard-private
editorial-guard eval run --config config.example.json --work-dir ../editorial-guard-private --input samples.jsonl --manifest experiment.json --output ../editorial-guard-private/evaluation
editorial-guard eval report --work-dir ../editorial-guard-private --output ../editorial-guard-private/evaluation
```

模型动态别名与无seed接口不保证逐字重现。重放已有记录可以复核计算；重新调用会产生新输出。跨平台支持范围以实际CI结果为准。

研究基线需要完整源码仓库。B3 的 Codex 原生加载使用 providers.codex.native_skill_root 指向两项 Skill 的父目录（仓库内示例为 skills）；裸 API 的 B3 只运行等价提示。Humanizer 等固定第三方规则放在 evals/third_party，不包含在 Python 工具 wheel 中。工作进程不能读取到规则或无法完成宿主加载时，报告未加载，不以返回了一段正文作为成功证据。

三家实验协议0.2.0固定60个基础比较与20个四状态干预单元。实际调用与已有记录重算分开；来源完整的历史单元明确标记，不冒充新的盲测。发布结果可用 `python scripts/replay_results.py --directory reports` 无密钥重算。重算一致只证明计算与记录一致，不证明模型判断为真。

Saved-cell operational metrics can be reconstructed without inference using `scripts/summarize_experiment.py`. Supply the public original samples and, optionally, your local request ledger. See [operational metrics](standards/operational-metrics.md) for cache/retry accounting, missing cost attribution and timing limits. This report is descriptive and does not establish a newly registered primary comparison.

## Static-site data assembly

`python scripts/prepare_site_data.py --data-export exported-data --experiment .eg/experiments/formal --output site-input --models requested-models.json` prepares two minimal files: `datasets/public_samples.json` and `reports/public_summary.json`. The optional model file maps provider names to the actual requested model IDs; it contains no keys. The output directory must be empty.

Only records included in the validated, hash-bound data export enter the sample view. Locked text requires the export's recorded exposure approval. Result rows retain mode, suite, route and profile, including unknown metadata for missing source inputs. Registration, recorded results, completed calls and operational errors remain separate. Undefined rates stay undefined.

This command does not publish or approve a release. The publication process copies the two reviewed files into their corresponding source-tree locations before building the accepted site. `scripts/check_site.py` checks both the file manifest and the result table's count and denominator consistency. Browser validation additionally covers pagination, filters, mobile scrolling and literal rendering of untrusted sample text.
