# 结果与适用范围

本版本已构建580个合成源家族，公开482个家族、964条实例；另外98个未评测锁定家族保留本地。两套中文任务独立报告。方法比较仅覆盖两个已暴露家族，每套任务各一个；结果可用于检查具体失败方式，不能据此宣布某种编辑方法或某家模型普遍更好。数据规模与实验任务数是两个不同分母。

软件与数据版本为0.1.0，标注协议为0.1.2，实验协议为0.2.0。所有语义标签和候选评审来自模型，没有人工验证。历史保留结果与登记后补齐结果在逐单元文件的evidence_cohort中区分；未重新取得独立未见测试集。

## 数据标签保留分歧与证据不足

|套件|家族|实例|有效格式的独立标注|一致|争议|证据不足|模型确认无需编辑|
|---|---:|---:|---:|---:|---:|---:|---:|
|StyleBench-ZH|241|482|952|131|339|12|111|
|DeliveryBench-ZH|241|482|956|133|341|8|98|

每套完整本地数据包括40个校准家族和250个主家族；主数据按150/50/50分为development、validation和locked_test。每套公开包含40个校准、150个开发、50个验证及1个已评测锁定家族，共241个家族、482条实例；其余49个锁定家族不公开。每家族含自然输出与受控变体。分区名称只表明分配方式；本版本公布后的题目已暴露。未公开题目仍共享已见模板，不因此宣称完全未见。模板复用、模型生成与同源变体使行数不能等同于完全独立的实际用户任务。

一致仅表示两名裁判在指定字段上的判断一致，不证明事实正确。quality-index.json逐条保留任务有效性分歧、原稿保真争议、缺少指定引句、语言边界与证据不足。此类记录没有从版本中静默删除。

cal-0001-natural提供了一个标签边界案例。文本处于plan阶段；Codex将“这一数据来自项目内部资料”和“目前尚无其他来源可交叉核对这一数值”标为process问题，理由实际指向来源和事实证据。GLM未标过程问题，并给出保真通过。按本项目的双任务定义，这暴露了裁判把保真争议混入过程标签的风险；程序可定位片段并不能消除分类错误。此记录保留disputed，不作为一致过程标签。逐字段分歧计数见annotation-disagreements.json，各字段相互重叠，不能相加为样本数。

## 基础方法比较限定于两个具体案例

B0保留原文；B1通用改写；B2规则提示；B3任务Skill；B4检查与有限修复；B5生成多个候选后选择。B1与B4每个案例重复三次，其余一次；重复次数不增加独立家族数。B3实际加载能力以逐单元skill_support及集成报告为准。

|任务与配置|编辑模型|方法|完成/登记|有效成功/登记|保真失败候选|裁判分歧单元|
|---|---|---|---:|---:|---:|---:|
|DeliveryBench-ZH / editorial-zh|codex|B0|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|codex|B1|3/3|0/3|0|3|
|DeliveryBench-ZH / editorial-zh|codex|B2|1/1|1/1|0|0|
|DeliveryBench-ZH / editorial-zh|codex|B3|1/1|0/1|1|0|
|DeliveryBench-ZH / editorial-zh|codex|B4|3/3|0/3|0|3|
|DeliveryBench-ZH / editorial-zh|codex|B5|1/1|0/1|0|1|
|DeliveryBench-ZH / editorial-zh|deepseek|B0|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|deepseek|B1|3/3|0/3|1|3|
|DeliveryBench-ZH / editorial-zh|deepseek|B2|1/1|0/1|0|1|
|DeliveryBench-ZH / editorial-zh|deepseek|B3|1/1|0/1|0|1|
|DeliveryBench-ZH / editorial-zh|deepseek|B4|3/3|0/3|2|3|
|DeliveryBench-ZH / editorial-zh|deepseek|B5|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|glm|B0|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|glm|B1|3/3|0/3|0|0|
|DeliveryBench-ZH / editorial-zh|glm|B2|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|glm|B3|1/1|0/1|0|0|
|DeliveryBench-ZH / editorial-zh|glm|B4|3/3|0/3|2|0|
|DeliveryBench-ZH / editorial-zh|glm|B5|1/1|0/1|0|0|
|StyleBench-ZH / general-zh|codex|B0|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|codex|B1|3/3|3/3|0|0|
|StyleBench-ZH / general-zh|codex|B2|1/1|1/1|0|0|
|StyleBench-ZH / general-zh|codex|B3|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|codex|B4|3/3|2/3|0|1|
|StyleBench-ZH / general-zh|codex|B5|1/1|1/1|0|0|
|StyleBench-ZH / general-zh|deepseek|B0|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|deepseek|B1|3/3|0/3|2|2|
|StyleBench-ZH / general-zh|deepseek|B2|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|deepseek|B3|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|deepseek|B4|3/3|0/3|3|1|
|StyleBench-ZH / general-zh|deepseek|B5|1/1|0/1|1|1|
|StyleBench-ZH / general-zh|glm|B0|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|glm|B1|3/3|0/3|2|0|
|StyleBench-ZH / general-zh|glm|B2|1/1|0/1|1|1|
|StyleBench-ZH / general-zh|glm|B3|1/1|0/1|1|0|
|StyleBench-ZH / general-zh|glm|B4|3/3|0/3|2|3|
|StyleBench-ZH / general-zh|glm|B5|1/1|1/1|0|0|

有效成功采用冻结判据，同时要求有效证据与所需语义条件；不能由字数减少或规则命中减少替代。调用完成也不等于候选成功。原稿已有事实问题与编辑新增损伤分开，详见core-results.json中的fidelity_transitions及逐单元判断。

每套比较仅一个家族，因此分层置信区间不可估计。汇总两家族的自助法区间仅为描述性计算，且混合了套件与风格配置，不支持显著性、稳健排序或个人配置收益推断。

## 一次变得更清楚却扩大事实范围的改写

main-0439-controlled的GLM B1候选把原文“运输记录覆盖11天，不能推算全年损耗”改写并补充为“全年损耗数据目前没有依据，请勿外推或引用”。Codex裁判判定保真失败：11天记录不足以外推，并不证明全年数据没有其他依据。DeepSeek裁判则接受这一补充，判定保真通过。两份意见的证据片段均可在对应文本定位。

候选还把“不能在复核前直接改为正常”扩展为“如需修改，须待复核完成后按流程处理”。这显示删除模板式总结后，仍可能新增更强的流程限制。该例保留相反的裁判意见，并按两票均须通过的规则判为未成功；它只能说明这个候选的边界，不能估计全库或供应商错误率。

## 四状态、阶段变化与重复编辑

H2以一个源家族的四种受控状态比较B0、B1及B2的style、process、both模式，共20个登记单元，编辑模型固定为Codex。状态来自程序变换，不是四个独立自然任务。详细单元、输入、指标分别见H2-cells.jsonl、H2-inputs.jsonl和H2-results.json。

H1在同一文本上切换阶段；Codex和DeepSeek符合预设判据的记录各为4/4，GLM为3/4，其method阶段差异保留。直接奖励投机检查中，有效证据支持的拒绝数分别为Codex 4/4、DeepSeek 3/4、GLM 4/4。H3、H4编辑器和H5结果见retained-core-evidence.md。无效证据票不被改写为通过；重复候选复用同一裁判请求时不增加独立票数。

## 集成与运行成本

手动与自动Skill加载有实际记录。受控finalize已验证内容绑定及篡改阻断；命令harness有通过、变化阻断、恢复通过的记录。Windows宿主实测未观察到原生Stop触发，因此不宣称原生Stop可用或能拦截宿主所有输出。支持范围和证据见integration-results.md。

自动化请求账本累计记录4017次，其中客户端958次；上限分别为8000和1000。计数包含可归因记录与历史未归因消耗，复用已有结果不增加新的请求。

request-cost-summary.json给出按币种分列的已知估计费用、可得实际费用与未知项。保留记录中的估计费用不等于供应商账单；历史未归因请求的费用未知，订阅客户端调用不能虚构逐次金额，也未设置新增金额预算。交互式宿主会话的订阅消耗不在这份逐请求账本中，不能据此推算账户总账单。core-operations.json与H2-operations.json按实际关联请求去重计费；跨组共享请求的金额不可直接求和，未关联失败请求以全局账本为准。

## 复算范围

运行 `python scripts/replay_results.py --directory reports` 可检查公开文件哈希、登记单元覆盖与指标重算。该过程不调用模型，也不重新验证语义真值。输入、候选、裁判意见与失败单元保留在公开结果文件中；完整认证、私有原始日志和执行状态不进入发布包。
