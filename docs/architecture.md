# 架构与支持范围

软件许可：MIT。Python内核提供lint_text、rewrite_text、verify_edit和finalize_artifact。CLI支持doctor、lint、rewrite、verify、pipeline、finalize、dataset build/annotate/validate、eval run/report、resume和hook install/disable/uninstall。

规则层提供保护区和确定性线索，独立模型评审处理语义。没有语义证据时返回unchecked，不用绿灯掩盖未知。运行时只导出公开输入，离线标注保留于数据流水线，不进入Skill或工具包。

默认目标zh-Hans。简体中文中合理的英文术语、代码和引用保留；英文主体为unsupported，其他未校准locale为unvalidated。语言启发式可能误判混排和繁简混用，应结合输入locale和范围测试解释，不声称通用语言识别能力。

SQLite通过事务预留请求名额，失败和重试不清零。每供应商最多一个在途模型请求，整体最多四个。成功且配置未变的请求可重放。账本记录usage、请求ID、提示hash、模型名和未知费用；动态别名不等于锁定权重版本。

Codex采用合法CLI登录，无OpenAI API Key转用或认证文件复制。纯文本工作者禁用网络搜索、shell、hooks、plugins、apps和记忆等可关闭功能，只接收公开输入。宿主仍有固定上下文，同用户文件访问也不是硬隔离，因此只作系统级比较。

MCP保留为未来适配层：可把四个产品函数映射为有版本的输入输出契约；当前没有声称这些是MCP标准方法，也没有运行MCP服务器。
