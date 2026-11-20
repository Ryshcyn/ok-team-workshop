"""Keep imported team code working when ok-ww drops the built-in subsystem.

ok-ww v3.8.4 (commit 52e80b9d) removed the "character code" feature together with
the Tacet Elimination task: it deleted ``src/char/CustomCharLoader.py``, the
``apply_team_char_classes()`` helper in ``src.char.CharFactory`` and the
``BaseCombatTask.load_chars()`` call that applied imported code. 队伍工坊 still
stores imported team code, so the plugin restores those three pieces from inside
the plugin, at import time, without editing anything in the ok-ww folder:

1. loader: keep the host module if present, otherwise execute the vendored copy
   (``vendor/CustomCharLoader.py``) as ``src.char.CustomCharLoader``;
2. helper: keep the host function if present, otherwise attach an equivalent
   ``apply_team_char_classes()`` to ``src.char.CharFactory``;
3. hook: keep the host call if present, otherwise wrap
   ``BaseCombatTask.load_chars`` so imported code is applied after the host read
   the team from the screen.

Teams without imported code, including teams switched back to 内置代码, keep the
built-in character classes, so nothing changes for them.
"""
import functools
import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

from ok import Logger

logger = Logger.get_logger(__name__)

HOOK_MARKER = '_ok_team_workshop_team_code_hook'
HELPER_MARKER = '_ok_team_workshop_team_code_helper'
LOADER_NAME = 'src.char.CustomCharLoader'
VENDOR_LOADER = Path(__file__).with_name('vendor') / 'CustomCharLoader.py'
LOADER_REQUIRED = (
    'load_team_char_class', 'normalize_team', 'save_team_code_as_import',
    'team_code_state', 'TEAM_CODE_MODE_IMPORT', 'TEAM_CODE_STATE_NONE',
)


def find_tab_class(source):
    """Return the page class a plugin module defines (a CustomTab subclass).

    ``source`` is a module or its ``globals()`` dict, so callers work even when
    the module was executed by path without being registered in ``sys.modules``.
    """
    from ok.ui.qt.widget.CustomTab import CustomTab
    namespace = source if isinstance(source, dict) else vars(source)
    module_name = None if isinstance(source, dict) else getattr(source, '__name__', None)
    for value in namespace.values():
        if (isinstance(value, type) and value is not CustomTab
                and issubclass(value, CustomTab)
                and (module_name is None or value.__module__ == module_name)):
            return value
    return None


def load_sibling(name):
    """Load a module that ships next to this page, once per process."""
    module_name = 'ok_team_workshop_' + name.lower()
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    path = Path(__file__).with_name(f'{name}.py')
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_vendored_loader():
    spec = importlib.util.spec_from_file_location(LOADER_NAME, VENDOR_LOADER)
    if spec is None or spec.loader is None:
        raise ImportError(f'no vendored character code loader at {VENDOR_LOADER}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[LOADER_NAME] = module
    try:
        spec.loader.exec_module(module)
        missing = [name for name in LOADER_REQUIRED if not hasattr(module, name)]
        if missing:
            raise ImportError(f'vendored character code loader lacks {missing}')
    except BaseException:
        sys.modules.pop(LOADER_NAME, None)
        raise
    setattr(sys.modules['src.char'], 'CustomCharLoader', module)
    return module


def ensure_loader():
    """Return the character code loader, vendoring it when the host removed it."""
    module = sys.modules.get(LOADER_NAME)
    if module is not None:
        return 'vendored' if Path(getattr(module, '__file__', '')) == VENDOR_LOADER else 'host'
    try:
        importlib.import_module(LOADER_NAME)
        return 'host'
    except ImportError:
        _load_vendored_loader()
        logger.info(f'ok-workshop: hosting character code loader from {VENDOR_LOADER}')
        return 'vendored'


def _make_apply_helper(char_dict, load_team_char_class, normalize_team):
    def apply_team_char_classes(task, chars):
        """Apply imported code once the complete three-character team is known."""
        if len(chars) != 3 or any(char is None for char in chars):
            return chars
        infos = [char_dict.get(char.char_name) for char in chars]
        if any(info is None for info in infos):
            return chars
        builtin_classes = [info['cls'] for info in infos]
        try:
            team = normalize_team(builtin_classes)
        except ValueError:
            return chars
        for index, (char, builtin_cls) in enumerate(zip(chars, builtin_classes)):
            try:
                desired_cls = load_team_char_class(builtin_cls, team)
                if type(char) is desired_cls:
                    continue
                replacement = desired_cls(
                    task,
                    char.index,
                    char_name=char.char_name,
                    confidence=char.confidence,
                    ring_index=char.ring_index,
                    char_type=char.char_type,
                    buff_time=char.buff_time,
                )
                replacement.__dict__.update(char.__dict__)
                chars[index] = replacement
            except Exception as error:
                logger.error(f'ok-workshop: imported code for {builtin_cls.__name__} not applied', error)
        return chars

    setattr(apply_team_char_classes, HELPER_MARKER, True)
    return apply_team_char_classes


def ensure_apply_helper():
    """Return how imported classes get applied: the host helper or an attached one."""
    factory = importlib.import_module('src.char.CharFactory')
    helper = getattr(factory, 'apply_team_char_classes', None)
    if helper is not None:
        return 'attached' if getattr(helper, HELPER_MARKER, False) else 'host'
    loader = importlib.import_module(LOADER_NAME)
    factory.apply_team_char_classes = _make_apply_helper(
        factory.char_dict, loader.load_team_char_class, loader.normalize_team)
    logger.info('ok-workshop: attached apply_team_char_classes to src.char.CharFactory')
    return 'attached'


def _apply_imported_team_code(task):
    chars = getattr(task, 'chars', None)
    if not chars or len(chars) != 3 or any(char is None for char in chars):
        return
    try:
        importlib.import_module('src.char.CharFactory').apply_team_char_classes(task, chars)
        # v3.8.3 applied the classes before the reset loop; mirror that order so a
        # custom class's own reset_state() runs on the replacement objects too.
        current = [char.is_current_char for char in chars]
        for char, is_current in zip(chars, current):
            char.reset_state()
            char.is_current_char = is_current
    except Exception as error:
        logger.error('ok-workshop: apply imported team code failed', error)


def _wrap_load_chars(load_chars):
    @functools.wraps(load_chars)
    def load_chars_with_team_code(self, *args, **kwargs):
        result = load_chars(self, *args, **kwargs)
        # load_chars returns None when it did not read a team from the screen, so
        # only touch the characters after a successful read.
        if result:
            _apply_imported_team_code(self)
        return result

    setattr(load_chars_with_team_code, HOOK_MARKER, True)
    return load_chars_with_team_code


def _host_applies_team_code(load_chars):
    try:
        source = inspect.getsource(load_chars)
    except (OSError, TypeError):
        return False
    return 'apply_team_char_classes' in source


def ensure_load_hook():
    """Return how a fresh combat gets imported code: host, wrapped or already installed."""
    base_combat_task = importlib.import_module('src.task.BaseCombatTask').BaseCombatTask
    if getattr(base_combat_task, HOOK_MARKER, False):
        return 'already-installed'
    load_chars = base_combat_task.load_chars
    if _host_applies_team_code(load_chars):
        setattr(base_combat_task, HOOK_MARKER, True)
        return 'host'
    base_combat_task.load_chars = _wrap_load_chars(load_chars)
    setattr(base_combat_task, HOOK_MARKER, True)
    logger.info('ok-workshop: wrapped BaseCombatTask.load_chars for imported team code')
    return 'wrapped'


def install():
    """Install all three compatibility pieces; safe to call more than once."""
    status = {
        'loader': ensure_loader(),
        'helper': ensure_apply_helper(),
        'hook': ensure_load_hook(),
    }
    logger.info(f'ok-workshop compatibility: {status}')
    return status
