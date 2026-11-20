# 兼容层说明（OK-WW v3.8.4+）

OK-WW v3.8.4（提交 52e80b9d）移除「角色代码」功能时删了三样东西：

1. `src/char/CustomCharLoader.py`（队伍工坊的核心依赖，约 780 行）；
2. `src/char/CharFactory.py` 里的 `apply_team_char_classes()`；
3. `BaseCombatTask.load_chars()` 里调用它的那一行。

只把第 3 行补回去并不够：宿主升级时会把文件覆盖回官方版本，插件又会失效。所以从 1.1.2
起，兼容逻辑放在插件内部，**不改动 OK-WW 安装目录里的任何文件**：

| 文件 | 作用 |
| --- | --- |
| `TeamCodeCompat.py` | 在插件加载时执行：宿主有 `CustomCharLoader` 就用宿主的，没有就把 `vendor/CustomCharLoader.py` 以 `src.char.CustomCharLoader` 的名字加载；`CharFactory` 缺 `apply_team_char_classes` 就挂一个等价实现；`load_chars()` 没调用它就包一层。 |
| `vendor/CustomCharLoader.py` | 取自 ok-ww 提交 `21829df6`（该功能最后一个完整版本），与 ok-ww 同为 AGPL-3.0。 |
| `WorkshopExtras.py` | 队伍工坊左侧的「更新插件」按钮：查 GitHub Release、下载、把兼容层合并进新包、交给主程序暂存。 |
| `WorkshopTab.py` 两段标记代码 | `# >>> ok-workshop compatibility ...` 和 `# >>> ok-workshop extras ...`，是上面两个模块的接入点，也是自更新合并时保留的内容。 |

每一步都先检测宿主现状：v3.8.3 这种自带完整接口的版本会显示 `{'loader': 'host', 'helper': 'host', 'hook': 'host'}`，不做任何包装；重复加载插件不会重复安装。

## 自更新如何保住兼容层

「更新插件」下载到新版 zip 后，会用当前安装目录里的 `WorkshopTab.py` 提取两段标记代码，
注入新版的对应位置，再连同 `TeamCodeCompat.py`、`WorkshopExtras.py`、
`vendor/CustomCharLoader.py`、`LOCAL_PATCH.md` 一起打包，交给主程序的
`stage_plugin_update()` 暂存，下次启动时先应用再加载插件。

合并只依赖两段标记注释和 `from src.char` 这一行导入；如果新版结构变化导致无法安全注入，
插件会直接报错并放弃更新，不会装上一个没有兼容层的版本。

## 日志

`logs/ok-script.log` 里可以确认：

```
ok-workshop compatibility: {'loader': 'host', 'helper': 'attached', 'hook': 'wrapped'}
```

- `loader: vendored`：宿主已删除 `CustomCharLoader`，用的是插件内置副本；
- `helper: attached`：宿主已删除 `apply_team_char_classes`，用的是插件挂载的实现；
- `hook: wrapped`：插件接管了 `BaseCombatTask.load_chars`；
- `imported code ... not applied`：某份队伍代码与当前 OK-WW 版本不兼容，只影响该角色。
