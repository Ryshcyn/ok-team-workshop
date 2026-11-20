"""Self-update button for 队伍工坊 (see LOCAL_PATCH.md).

ok-ww no longer shows the Plugins management page on recent releases, so the
plugin carries its own updater: it asks the GitHub repository this copy was
installed from for a newer release, downloads it, re-applies this build's two
local sections to the new WorkshopTab.py and stages the result with the host's
plugin staging API (the update is applied on the next launch, like the host's
own updater).

The merge is why a plugin update does not lose the character-code compatibility
layer: the local sections are marked in WorkshopTab.py and copied into the new
file, together with TeamCodeCompat.py and the vendored loader.
"""
import functools
import json
import re
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter

from ok import Logger
from ok.ui.qt.kit.buttons import Button
from ok.ui.qt.kit.feedback import show_toast

logger = Logger.get_logger(__name__)

MARKER = '_ok_workshop_update_installed'
COMPAT_BEGIN = '# >>> ok-workshop compatibility'
COMPAT_END = '# <<< ok-workshop compatibility'
EXTRAS_BEGIN = '# >>> ok-workshop extras'
EXTRAS_END = '# <<< ok-workshop extras'
LOCAL_FILES = (
    'TeamCodeCompat.py', 'WorkshopExtras.py', 'vendor/CustomCharLoader.py', 'LOCAL_PATCH.md',
)
PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAMESPACE = PLUGIN_DIR.name


def plugin_version():
    try:
        manifest = json.loads((PLUGIN_DIR / 'manifest.json').read_text(encoding='utf-8'))
        return str(manifest.get('version') or '')
    except (OSError, ValueError, TypeError):
        return ''


def install(tab_cls):
    """Add the update row every time the page is constructed."""
    if getattr(tab_cls, MARKER, False):
        return
    original = tab_cls.__init__

    @functools.wraps(original)
    def __init__(self, *args, **kwargs):
        original(self, *args, **kwargs)
        try:
            attach(self)
        except Exception as error:  # the page keeps working without the update row
            logger.error('ok-workshop: update button not installed', error)

    tab_cls.__init__ = __init__
    setattr(tab_cls, MARKER, True)


def attach(tab):
    if getattr(tab, '_ok_workshop_update_button', None) is not None:
        return
    splitter = tab.findChild(QSplitter)
    left = splitter.widget(0) if splitter is not None and splitter.count() else None
    layout = left.layout() if left is not None else None
    if layout is None:
        return
    row = QHBoxLayout()
    row.setContentsMargins(0, 4, 0, 0)
    button = Button('更新插件', icon='refresh')
    button.setToolTip('从 GitHub 检查新版本，下载后重启 ok-ww 生效')
    label = QLabel('')
    row.addWidget(button, 1)
    row.addWidget(label)
    layout.addLayout(row)
    button.clicked.connect(lambda: _start_update(tab, button, label))
    tab._ok_workshop_update_button = button
    tab._ok_workshop_update_label = label
    _refresh(button, label)


def _refresh(button, label):
    from ok.core.plugin_staging import pending_plugin_changes
    try:
        pending = pending_plugin_changes().get(PLUGIN_NAMESPACE) or {}
    except Exception:
        pending = {}
    version = plugin_version()
    staged = str(pending.get('version') or '').lstrip('v')
    if staged:
        button.setEnabled(False)
        button.setText(f'重启 ok-ww 应用 {staged}')
        label.setText(f'v{version} → v{staged}')
    else:
        button.setEnabled(True)
        button.setText('更新插件')
        label.setText(f'v{version}' if version else '')


def _toast(parent, message, error=False):
    show_toast(parent.window(), message, title='插件更新', tone='danger' if error else 'success')


def _start_update(tab, button, label):
    button.setEnabled(False)
    button.setText('检查更新中…')
    label.setText(f'v{plugin_version()}')
    try:
        _check_and_stage(tab)
    except Exception as error:
        logger.error('ok-workshop: plugin update failed', error)
        _toast(tab, f'更新失败：{error}', error=True)
    finally:
        _refresh(button, label)


def _check_and_stage(tab):
    from ok.core.plugin_staging import pending_plugin_changes, stage_plugin_update
    from ok.core.plugins import download_plugin, github_asset_source, plugin_update_assets

    if pending_plugin_changes().get(PLUGIN_NAMESPACE):
        _toast(tab, '已有下载好的更新，重启 ok-ww 生效')
        return
    version = plugin_version()
    assets = plugin_update_assets({'folder': str(PLUGIN_DIR), 'version': version})
    if not assets:
        _toast(tab, f'已是最新版本 v{version}')
        return
    asset = assets[0]
    prepared = download_plugin(asset)
    try:
        merged, work_dir = merge_local_build(Path(prepared.path), PLUGIN_DIR)
        try:
            stage_plugin_update(str(merged), source=github_asset_source(asset))
        finally:
            _remove_tree(work_dir)
    finally:
        prepared.close()
    _toast(tab, f"已下载 {asset['tag']}，重启 ok-ww 后生效")


def _remove_tree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def _extract_block(text, begin, end):
    start = text.find(begin)
    if start < 0:
        return None
    stop = text.find(end, start)
    if stop < 0:
        return None
    return text[start:stop + len(end)]


def _needs_import(text, statement):
    return re.search(r'(?m)^' + re.escape(statement) + r'\s*$', text) is None


def _inject(text, compat_block, extras_block):
    """Return the upstream page text with this build's local sections in place."""
    if compat_block is None or extras_block is None:
        raise ValueError('本地 TeamCodeCompat/WorkshopExtras 段落缺失，无法保留兼容层')
    if 'TEAM_CODE_COMPAT_STATUS' not in text:
        match = re.search(r'(?m)^from src\.char', text)
        if match is None:
            raise ValueError('新版插件改了导入结构，无法自动保留兼容层')
        text = text[:match.start()] + compat_block + '\n\n' + text[match.start():]
    if 'TEAM_CODE_COMPAT.find_tab_class' not in text:
        text = text.rstrip('\n') + '\n\n\n' + extras_block + '\n'
    for statement in ('import importlib.util', 'from pathlib import Path'):
        if _needs_import(text, statement):
            text = statement + '\n' + text
    compile(text, 'WorkshopTab.py', 'exec')
    return text


def _read_archive(archive):
    with zipfile.ZipFile(archive) as source_zip:
        return {info.filename: source_zip.read(info) for info in source_zip.infolist() if not info.is_dir()}


def _plugin_files(entries):
    """Map archive entries onto the plugin root, accepting one enclosing folder."""
    prefix = ''
    if 'manifest.json' not in entries:
        candidates = [name for name in entries if name.count('/') == 1 and name.endswith('/manifest.json')]
        if len(candidates) != 1:
            raise ValueError('下载的压缩包缺少 manifest.json')
        prefix = candidates[0][: -len('manifest.json')]
    if prefix and any(not name.startswith(prefix) for name in entries):
        raise ValueError('下载的压缩包结构异常')
    return {name[len(prefix):]: data for name, data in entries.items() if not prefix or name.startswith(prefix)}


def merge_local_build(archive, plugin_dir):
    """Return (merged zip path, temporary dir) for a downloaded plugin archive."""
    plugin_dir = Path(plugin_dir)
    local_text = (plugin_dir / 'WorkshopTab.py').read_text(encoding='utf-8')
    compat_block = _extract_block(local_text, COMPAT_BEGIN, COMPAT_END)
    extras_block = _extract_block(local_text, EXTRAS_BEGIN, EXTRAS_END)
    files = _plugin_files(_read_archive(archive))
    workshop = files.get('WorkshopTab.py')
    if workshop is None:
        raise ValueError('下载的压缩包里没有 WorkshopTab.py')
    files['WorkshopTab.py'] = _inject(
        workshop.decode('utf-8'), compat_block, extras_block).encode('utf-8')
    for name in LOCAL_FILES:
        path = plugin_dir / name
        if path.is_file():
            files[name] = path.read_bytes()
    temp_dir = Path(tempfile.mkdtemp(prefix='ok-workshop-merge-'))
    merged = temp_dir / 'plugin.zip'
    with zipfile.ZipFile(merged, 'w', zipfile.ZIP_DEFLATED) as target:
        for name, data in files.items():
            target.writestr(name, data)
    from ok.core.script_packager import inspect_script_archive
    if inspect_script_archive(str(merged))['file_name'] != plugin_dir.name:
        _remove_tree(temp_dir)
        raise ValueError('下载的压缩包不是这个插件')
    return merged, temp_dir
