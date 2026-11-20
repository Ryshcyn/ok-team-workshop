# 来源与修改说明

原项目：ok-oldking/ok-wuthering-waves
https://github.com/ok-oldking/ok-wuthering-waves

衍生文件：`WorkshopTab.py`
原路径：`src/gui/CharacterCodeTab.py`
来源：本机 OK-WW 安装目录保留的源码。
本机更新仓库中最后修改该文件的提交：`b32c5025afccb3c6a8d870d0e8b11e30dbe07c19`。
该提交仅作为来源线索；未验证更新镜像提交与公共 GitHub 提交逐字节一致。

本衍生版本整理日期：2026-11-04。
修改：复制并重命名页面模块供插件加载；页面标题改为「队伍工坊」；索引和单队伍接口改为公开 GitHub raw 地址；下载优先使用 `rawUrl`；添加插件 manifest、打包与发布流程。
其余界面与队伍处理逻辑沿用原文件，主程序接口由用户安装的 OK-WW 提供。

兼容层（1.1.2 起）：`TeamCodeCompat.py`、`WorkshopExtras.py` 为本仓库新增代码。
`vendor/CustomCharLoader.py` 复制自同一项目提交 `21829df6` 的 `src/char/CustomCharLoader.py`（该功能最后一个完整版本），仅在宿主删除该模块时作为兜底加载，许可证同上（AGPL-3.0）。

原项目公开仓库标示 AGPL-3.0；根目录 LICENSE.txt 为从原项目获取的许可证文本。
原作者及其他贡献者保留其代码版权。此仓库未包含游戏素材、主程序、用户配置或社区配队 ZIP。
