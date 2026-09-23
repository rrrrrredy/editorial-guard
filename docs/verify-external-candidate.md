# 校验其他工具改出的稿件

可以使用 Humanizer-zh 或其他编辑工具生成 candidate.md，再调用已有 verify 命令。无需为验证重新生成稿件；两份文件和任务资料必须对应同一项工作。

```sh
editorial-guard verify original.md --candidate candidate.md --context context.json --config config.json --mode both --judge glm --sidecar review.json --receipt receipt.json
```

确认裁判与候选生成者使用不同供应商后，才能称为独立评审。外部候选来源未知时说明限制，CLI 不会自动发现其作者。

退出码 0 才表示当前任务通过；1 不通过、2 未验收、3 错误。先读 review.json 中的原因与 structure_changes；不要循环重试到偶然通过。

若验证通过并需要受控写入：

```sh
editorial-guard finalize candidate.md published.md --root . --context context.json --config config.json --mode both --receipt receipt.json
```

两步使用相同的目录、context、config 和 mode，候选不得修改。本文是现有接口用法，不宣称已对所有外部 Skill 或平台完成联用实测。源文保真并不等于现实事实核查，签名凭证也不证明裁判不会错。
