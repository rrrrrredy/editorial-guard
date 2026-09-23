# 平台安装包

软件与技能版本 0.2.0。下载 [GitHub Release](https://github.com/rrrrrredy/editorial-guard/releases/tag/v0.2.0)。

| 文件 | 用途 | ZIP 结构 / 头像 |
|---|---|---|
| editorial-guard-zh-v0.2.0.zip | 通用技能目录安装 | editorial-guard-zh/SKILL.md；无头像 |
| editorial-guard-zh-portable-flat-v0.2.0.zip | 接受根目录 SKILL.md 的上传入口 | SKILL.md 在根目录；无头像 |
| editorial-guard-workbuddy-skill-v0.2.0.zip | WorkBuddy 技能 | SKILL.md 在根目录；头像另传 |
| editorial-guard-workbuddy-expert-v0.2.0.zip | WorkBuddy 单专家 | 单顶层目录；内置头像和技能 |
| editorial-guard-workbuddy-team-v0.2.0.zip | WorkBuddy 专家团 | 单顶层目录；4 个角色、内置头像和技能 |
| editorial-guard-skill-avatar.png | WorkBuddy 技能头像 | 512 × 512 PNG，独立上传 |

## 使用

通用包解压到宿主支持的技能目录，再输入：

> 请用 editorial-guard-zh 润色这段中文，保留原意与文体，只返回候选正文：[原稿]

WorkBuddy 技能、专家和专家团分别使用对应上传入口，不能混用 ZIP。单专家适合日常改稿；专家团由主理人调用团队能力组织表达、原意和交付审阅。团队运行会使用更多宿主额度；通常一轮改写和有针对性的修正足够。平台不支持团队工具时不会伪造多成员结果。

普通技能和专家不需要 Python 或额外模型密钥，使用宿主的模型服务。CLI 独立验收另行安装和配置。多角色审阅不自动构成跨供应商独立验收。

## 兼容与验证

打包脚本检查 ZIP 路径、CRC、元数据、角色映射、技能引用和头像大小。它不表示平台审核通过或实际导入成功。通用平铺包只承诺标准 SKILL.md 结构，特定平台额外清单需按其上传规范适配。

WorkBuddy 规则参照 2026-09-23 的[技能](https://open.workbuddy.cn/docs/skill)、[专家](https://open.workbuddy.cn/docs/expert)、[专家团](https://open.workbuddy.cn/docs/expert-team)说明；兼容既有解析器保留两份相同的 settings.json / setting.json。独立技能包保持根目录 SKILL.md，头像独立上传。

从仓库根目录运行：

```sh
python scripts/build_platform_packages.py --output ../editorial-guard-packages
```

无需在运行时安装头像生成依赖。avatars/ 中 PNG 为发布资产，SVG 为可编辑原图，均使用原创简单图形。包内技能由统一源码生成，避免多份规则漂移。
