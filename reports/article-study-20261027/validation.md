# 本轮本地验证记录

环境为 Windows、Python 3.12，使用仓库已有的运行与开发锁定依赖。没有新增依赖或单元测试。仓库 CI 的三系统 Python 3.11 矩阵未在本机重现。

| 检查 | 命令或入口 | 观察 |
| --- | --- | --- |
| 既有测试 | `python -m pytest -q` | 初次 133 passed、1 failed、1 skipped。失败为子进程无法导入尚未安装的本地包。 |
| 环境修复后的失败项 | 先 `python -m pip install --no-build-isolation .`，再 `python -m pytest -q tests/test_release_boundaries.py::test_real_cross_process_reservation` | 1 passed。未重跑已通过的 133 项；合计 134 项通过、1 项跳过。 |
| 提示同步 | `python scripts/sync_prompts.py --check` | 通过。 |
| 供应商范围 | `python scripts/check_provider_scope.py` | 通过；不调用模型。 |
| 冻结结果重放 | `python scripts/replay_results.py --directory reports` | core 60/60、H2 20/20；只复算既有记录，model_calls=0，不是重做编辑效果实验。 |
| 软件构建与分发边界 | `python -m build --no-isolation`；`python scripts/check_distribution.py --directory dist` | wheel、sdist 成功，分别检查 25、40 个条目。 |
| 平台包 | `python scripts/build_platform_packages.py --output <仓库外空目录>` | 五个包及现有头像生成成功；`platform_import_tested=false`。 |
| 站点 | `python scripts/build_site.py --output <空目录> --commit unpublished`；`python scripts/check_site.py --directory <该目录>` | 7 页、964 个既有样本，通过；未发布。 |
| Skill 格式 | skill-creator 的 `quick_validate.py`，分别检查三个 Skill | 以 `python -X utf8` 运行均通过。Windows 默认 GBK 首次无法解码，未改动校验工具。 |
| 完整文章 | `python -X utf8 scripts/inspect_article_cases.py --output reports/article-study-20261027/artifacts` | 原文哈希匹配；保留六份原始候选、两份后续示范的现有检查结果及全文 HTML。无语义自动通过。 |

测试日志没有保存跳过项的具体原因，因此不推断其覆盖。平台包初次使用相对路径被输出目录保护拒绝，改用明确的仓库外绝对路径后通过。它们都是本地执行记录，不等同于托管 CI 或平台导入结果。

实际语义阅读和发现的问题见[观察记录](README.md)及案例。格式检查、构建、冻结结果重放都不能证明文章写得更好；没有真实读者评价或独立语义凭证。

如要核实尚未验证的宿主使用体验，最小手动步骤是将本轮生成的统一 Skill 包导入目标宿主，给出案例原文和 `context.json` 的同一改稿要求。预期入口直接返回正文，允许保留有用比较和教程清单，不先要求配置 CLI、凑候选或确认。再对照原文核对数字、引用及禁止条件；即使入口正确，输出仍须按具体文章判断，不能把一次导入视为质量验证。本轮没有实施这项额外平台测试。
