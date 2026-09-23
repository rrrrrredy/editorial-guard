# 从一次改稿开始

软件 0.2.0；公开数据与研究结果仍为 0.1.1，没有因本次更新而重跑模型比较。

## 在已有 Agent 中润色

下载 Release 的 `editorial-guard-zh-v0.2.0.zip`，解压后将 `editorial-guard-zh` 文件夹放进宿主支持的技能目录。Codex 项目目录为 `.agents/skills/`；不同宿主应采用其实际支持的安装入口。WorkBuddy 请使用专门的平铺技能包。

```text
请用 editorial-guard-zh 润色下面的文字，保留技术评论语气和全部限定，只返回候选正文：
[粘贴原稿]
```

需要作者样本时另附一段并注明“只参考表达，不引入其中的事实”。只审阅时说“给建议，不改文件”。这条路径不要求 Python 或另配 API 密钥，但仍使用宿主自身的模型额度；结果没有独立验收凭证。

## 安装 CLI，验证重要文件

从 https://github.com/rrrrrredy/editorial-guard/releases/tag/v0.2.0 下载 wheel，使用 Python 3.11 或更新版本：

```sh
python -m pip install editorial_guard-0.2.0-py3-none-any.whl
editorial-guard doctor
```

从源码安装使用 `python -m pip install .`。复制 config.example.json、context.example.json，并按自己的服务权限修改；密钥仅放环境变量，不写进稿件、ZIP 或 Git。下载的普通 Skill 包不包含 CLI。

```sh
editorial-guard rewrite original.md --output candidate.md --context context.json --config config.json --mode both --editor deepseek --judge glm --sidecar review.json --receipt receipt.json
```

只改文风用 style，只处理交付旁白用 process，两项都需要用 both。正文与诊断分开保存；失败候选不会冒充合格正文。`lint` 只提供程序线索，退出码 2 正常表示尚未语义验收。

正式交付文件前执行 finalize，详见[外部候选校验](verify-external-candidate.md)和[验收边界](acceptance.md)。在线项目站和 HF Space 展示样本及结果，不提供托管模型改写。

## 输入作者声音

context.json 的可选 `voice_sample` 字符串只提供语气和句式参考；`source_bundle` 才是事实材料。声音样本也参与凭证绑定，改动后旧凭证失效。不要将敏感的第三方文稿当作样本上传。

## 文档保护

默认保护标题文本与层级、链接目标、引用式链接定义、显式 ID、列表层级，并识别未改写步骤的换序。列表正文的合法润色可以继续交给语义裁判。代码和结构化数据沿用原有保护。

只有用户明确要求改标题时设置 `constraints.allow_heading_edits: true`；仍保持标题层级与已有链接目标，检查常见内部锚点是否失效。若标题被已有锚点引用，保留原标题或显式 ID；更复杂的结构重排应作为独立任务处理。

结构扫描覆盖常见 Markdown，并非完整 CommonMark 渲染器。含重写的步骤顺序、复杂嵌套、跨段关系仍需语义审阅；结构通过不证明意思正确。
