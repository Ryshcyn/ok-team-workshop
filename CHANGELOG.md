# 更新记录

## 1.1.2 — 2026-11-20

- 新增 `TeamCodeCompat.py`：自动补齐 OK-WW v3.8.4+ 移除的 `src.char.CustomCharLoader`、`CharFactory.apply_team_char_classes` 和 `BaseCombatTask.load_chars()` 中的调用，并内置 `vendor/CustomCharLoader.py` 作为兜底；导入代码从每场战斗开始就生效，不再只对当前任务生效一次。
- 新增 `WorkshopExtras.py`：队伍工坊左侧加入「更新插件」按钮，直接检查 GitHub Release、下载并把兼容层合并进新包，再交给主程序暂存，重启 OK-WW 生效；不再依赖 v3.8.4 起隐藏的 Plugins 页。
- 打包流程与 README/NOTICE 同步更新，说明兼容层与插件内更新方式。

## 1.1.1 — 2026-11-17

- README 增加工坊列表和角色代码编辑两张界面截图，并随插件包一起分发。

## 1.1.0 — 2026-11-17

- 原 `ok-oldking/ok-ww-char-code` 仓库与 CDN 下线后，工坊索引改读社区抢救镜像。
- 增加多源回退：主镜像失败时自动尝试备用镜像。
- 所有数据源都不可用时明确报错，不再静默显示 0 个配置。
- 「上传队伍」改为打开镜像仓库；更新 README 说明数据源现状。

## 1.0.0 — 2026-11-04

- 将旧版角色代码和工坊界面封装为插件自定义页面。
- 改用 GitHub raw 配队索引和 ZIP 直链。
- 保留配队预览导入、编辑、导出和内置/导入切换功能。
- 添加可复现打包、校验文件与 GitHub Release 工作流。
