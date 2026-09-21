# 既有第三方规则与其他轨道记录

以下12条记录均复用实际请求与响应，已核对供应商、请求文件和裁判原文，并离线重新检查逐字证据。没有为此增加模型调用；它们不并入60单元基础比较，不构成新的未见测试。

## 三种第三方规则仅覆盖一个案例

|编辑模型|规则|调用状态|当前判据有效成功|有效证据票|
|---|---|---|---|---:|
|codex|R-HumanizerZH|completed|True|2/2|
|glm|R-HumanizerZH|completed|False|2/2|
|codex|R-Humanizer|completed|False|2/2|
|codex|R-StopSlop|completed|True|2/2|
|glm|R-Humanizer|completed|False|2/2|
|glm|R-StopSlop|completed|False|2/2|

每种规则仅在main-0425-controlled上由Codex和GLM各执行一次。原规则通过统一JSON输出包装调用；不能把结果解释为原项目客户端的完整行为或三家模型全覆盖。引用、版本与许可见THIRD_PARTY_NOTICES.md。

## 检测、直接生成和顺序编辑的覆盖

|模型|轨道|调用状态|有效裁判票/记录票|
|---|---|---|---:|
|codex|generate|completed|2/2|
|codex|detect|completed|0/0|
|codex|style_then_process|completed|2/2|
|glm|detect|completed|0/0|
|deepseek|detect|completed|0/0|
|glm|generate|completed|2/2|

detect返回定位和标注，没有独立人工真值；表中的0/0表示该轨道未附候选裁判票，不能当作检测失败率。generate从给定事实底稿生成。style_then_process按顺序编辑，同样只覆盖一个家族；它不能替代真实宿主workflow验收。

轨道输入、候选和现有裁判意见保留在retained-additional-records.json中。未覆盖的模型与轨道组合未运行，不补模拟成绩。调用完成与质量通过分别报告；带first_execution_status的记录保留首轮失败事实。
