# Codex项目集成

许可：MIT。已探测CLI版本0.155.0-alpha.9.2。原生Stop事件存在；本项目不定义虚构的BeforeFinalResponse或BeforePublish事件。

```text
editorial-guard hook install --root .
editorial-guard hook disable --root .
editorial-guard hook uninstall --root .
```

安装合并项目.codex/hooks.json并保存所管理条目。不会修改全局配置。禁用/卸载仅移除本工具的未变更条目，保留其他hook。宿主要求先在/hooks审阅并信任具体定义；安装成功不等于原生事件已经运行，不绕过信任机制。

只检查通过register明确登记的txt/md文件。可运行 editorial-guard hook register --root . --candidate candidate.md --receipt receipt.json --config config.json --context context.json --mode both。登记后，内容和配置发生变化都会使旧验收失效。通过记录绑定内容hash、规则、配置、run/turn；同一版本重复检查不发模型请求。reentrancy锁与stop_hook_active防止递归和无限续跑。本版本在Windows官方CLI的真实exec调用中未观察到Stop触发，不能据此宣称原生路径已可用；命令级事件模拟和受控finalize分别有独立记录。实际事件覆盖、触发结果和未测路径见实验报告。

严格发布只由finalize保证。已经输出的聊天文本、任意shell或外部上传不受全局控制。wrapper可独立使用，不依赖原生hook获得权限。

两个Skill可分别复制到目标项目.agents/skills下。工具包需要另行安装，Skill包不含隐藏答案。解释概念时不触发编辑；真正需要两个模块时选择both。

Coding Plan 的客户端模型目录字段依据 [智谱官方 Codex 指南](https://docs.bigmodel.cn/cn/coding-plan/tool/codex)。示例仅适用于已合法获得套餐权限的真实 Codex CLI；标准 API 和订阅额度分开。批量基准任务使用适用的标准 API 配置，不伪装客户端或转发订阅能力。
