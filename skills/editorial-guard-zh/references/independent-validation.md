# 独立验收

本技能的普通宿主改写产生候选稿。若用户要求正式验证，需另行安装 Editorial Guard 0.2.0，配置编辑/裁判服务，并准备原稿、候选和 context.json。安装与环境要求见 https://github.com/rrrrrredy/editorial-guard/blob/main/docs/quickstart.md 。

已有候选时不必重新生成：

```sh
editorial-guard verify original.md --candidate candidate.md --context context.json --config config.json --mode both --judge glm --sidecar review.json --receipt receipt.json
```

外部编辑器的身份不能猜测；声称裁判独立之前，核对其与候选生成者使用不同供应商。无法确认时如实说明。退出码 0 是本次通过，1 不通过，2 未验收，3 运行错误；没有通过时不得 finalize。

```sh
editorial-guard finalize candidate.md published.md --root . --context context.json --config config.json --mode both --receipt receipt.json
```

验证与 finalize 使用同一工作目录、上下文、配置、模式及候选字节。候选或声音样本变动后重新校验。finalize 只约束授权目录内的受控写入，不控制聊天消息和外部发布，不是网站自动发布功能。
