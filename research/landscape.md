# 中文编辑与交付评测的方法依据

许可：CC BY 4.0。核验日期：2026-09-20。固定版本、阅读范围及未复现项见 sources.jsonl。这里区分源项目的设计、代码所支持的机制和本项目的真实实验；引用本身不证明效果。

## 两项任务需要独立判断

[Humanizer](https://github.com/blader/humanizer/tree/9862685f575c65a8247f90369951df1b3416e3d6) 的当前规则明确要求保留事实。其粘贴文本模式可包含中间文本、问题点评和成稿，而文件与嵌入模式强调成稿输出。由此可见，表达是否机械与当前交付是否夹带编辑过程，需要分开控制；不能把工具支持某种讲解模式说成它始终污染成稿。

[Humanizer-zh](https://github.com/op7418/Humanizer-zh/tree/91f3d394db8419c20d67ebe22a96cf8fee0a404b) 提供中文模式及对照例子。所读版本的一些改写例子补入原文未给出的年份、反馈和具体情境。这说明“更具体”不自动等于保真；这里指出的是例子的输入证据不足，不是断言这些细节在现实世界必然为假。正式基线保留原规则，不能替它修补后仍标成原版。

[Stop Slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9) 的轻量规则便于提示对照，但副词、被动结构、破折号等绝对删除倾向及固定总分门槛不适合作为中文真值。本项目只把候选形式作为定位线索，最终结合读者、文体、阶段和信息作用判断。 所读 examples.md 的第二例把“most teams”改为不带范围限定的断言，并把原先的承认意愿改为实际承认行为；这进一步说明，简短改写仍需独立核对范围与关系。此处分析的是固定版本的示例，不代表运行基线在所有任务中都发生同类变化。

## 统计诊断不能代替中文质量

[slop-score](https://github.com/sam-paech/slop-score/tree/289264ab2a0df1358ef81ced3c259610ea709514) 使用词表、三元组和对比结构；README 描述的组合权重是 60%、15%、25%。读取的代码包含英文内容词过滤和每千字符对比结构计数。这些量能描述某种文本模式，不能独立证明表达差、事实正确或作者来源。其许可按组件区分：主要代码 MIT，wordfreq 代码 Apache 2.0，特定词频数据 CC BY-SA 4.0；本项目不复制这些词频数据。

[slop-forensics](https://github.com/sam-paech/slop-forensics/tree/c313f042620f027d49101da3256bd306b628071a) 的统计实现使用英文分词、发音词典及 Flesch–Kincaid 公式。中文没有相同的空格词界和音节计数前提，因此本项目重新构造中文案例，不照搬其分值。

[AntiSlop Sampler](https://github.com/sam-paech/antislop-sampler/tree/0ae330e98fbe6f09351f2d1063a51956378a44b2) 在命中短语后找到起始 token，修改缓存概率并回溯采样；代码支持这一机制。它要求本地推理侧控制，不等同于给普通聊天 API 加一份禁词表。关联[论文](https://arxiv.org/abs/2510.15061)还涉及训练方向。本项目没有复现采样器、训练权重或声称获得论文收益。

## 任务判据、编辑比较与行为测试

[WritingBench](https://github.com/X-PLUG/WritingBench/tree/ae2d5176449b7b769815482641d35926f26793eb) 按任务的 checklist 逐项评分，代码再聚合不同领域和要求。可借鉴的是先确定任务判据，再评价回答；本项目不复制其分数或把任意总分当作保真证明。

[EQ-Bench Creative Writing](https://github.com/EQ-bench/creative-writing-bench/tree/c7c3ceef54c40a8ae02dc1c2e1a5e40970fe5c0b) 提供多维评分和成对比较提示，并允许跳过不适用的创作指标。创意小说标准不能直接成为行业报告标准。读取到了字体许可，但未据此断言整个仓库获得相同许可；研究只引用方法，不分发其提示或数据。

[WritingRewards](https://github.com/salesforce/creativity_eval/tree/3d029879df6878f611363db88cc02d465699bc51/WritingRewards) 与[对应论文](https://arxiv.org/abs/2504.07532)研究编辑反馈、写作质量奖励和测试时计算。其推理代码有成对分类和单段回归输出，数据说明包含人工和专家写作材料。本项目没有人工验证，也没有运行其奖励模型；只采用“增加计算必须有成本对照”和“内容变化可能混淆写作评分”的实验问题。

[CheckList](https://github.com/marcotcr/checklist/tree/4e6e5e33a26f30c20ed602b2050f6c73e123cc23) 的实现明确区分最低功能测试、保持不变的变换与定向变化。本项目对应设置事实破坏、同义改写和任务阶段翻转。[IFEval](https://arxiv.org/abs/2311.07911) 的可程序验证约束启发了字面要求和格式检查，但这些检查不能代替含义判断。

## 裁判会受位置、长度和身份影响

[MT-Bench / Chatbot Arena 论文](https://arxiv.org/abs/2306.05685)讨论位置、冗长和自我偏好。本项目隐藏候选作者和方法名，排除作者担任自己的主要裁判，报告顺序交换与留一供应商敏感性。没有复制论文的人工比较环节，因此不继承其人类偏好有效性。

[JudgeBiasBench](https://arxiv.org/abs/2603.08091v3) 的准确论文名为 *Toward Robust LLM-Based Judges: Taxonomic Bias Evaluation and Debiasing Optimization*；作者为 Hongli Zhou 等。已核验 v3 摘要所述四个维度和十二类偏差，未获取可确认的作者代码仓库，也未复现其训练方法。

[BiasScope](https://github.com/Laip11/BiasScope/tree/74bdf750f143935f408a19878bcfc98b8dac8154) 对应[论文 2602.09383](https://arxiv.org/abs/2602.09383)。读取的检测器用教师模型分类并扩充偏差库。自动发现的偏差仍需独立验证；本项目保留反证与分歧，不把模型命名的新偏差当作已证事实。未发现可确认的整体许可证，未复制代码。

## 本项目没有做强化学习

[Constitutional AI](https://arxiv.org/abs/2212.08073)包含批评修订和后续基于 AI 反馈的训练。一次编辑—校验—修复循环只是推理流程。[GEPA](https://github.com/gepa-ai/gepa/tree/15ee314f9c7d34ec153b809d401f42f55c4dcd76) 的引擎包含候选提案、评估反馈、接受策略及独立验证集缓存。本项目借鉴有限提示优化与冻结验证的边界，不声称运行了 GEPA 或训练出新模型。

## 接口与证据边界

Codex 原生 Stop 事件可要求继续处理，不能撤回已显示正文；项目 hook 需要宿主信任。受控 finalize 只保证它自己写入的本地路径，不能拦截任意上传、邮件或 shell 命令。MCP 是上下文交换协议，本版只保留架构接口，没有宣称部署 MCP 服务。

智谱 Coding Plan 按官方支持的 Codex 客户端接入，使用真实 CLI 与官方 Responses 端点；付费 API 为单独配置。接通通道、通过少量已知对照、完成校准、完成主实验是不同证据层次。

指定 X 帖文访问返回 403；未读取原帖讨论，未用搜索摘要代替。Anthropic 指定工程文章未能访问，列为不可达入口，不据其标题补写内容。其他项目均未执行第三方安装脚本或运行未经授权的代码。

三个直接编辑工具的固定MIT规则随原许可证保存在 evals/third_party，并作为带JSON输出包装的规则级基线执行。原生客户端、交互模式和源项目的效果数字未被复现；实际候选与裁判覆盖须以本项目相应实验结果为准。来源登记中的 reproduced=false 指这一复现边界，不表示没有运行规则级对照。
