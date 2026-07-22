# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the LightAgent desktop backend (onedir).

Produces a self-contained `lightagent-backend` folder that the Electron app
spawns directly, so end users don't need Python installed.

onedir is chosen over onefile because the backend reads data files via paths
relative to the source tree (e.g. config-template.json, skills/, chat.html);
onedir preserves that layout, while onefile's temp-extraction would break it.

Build from the repo root:
    pyinstaller desktop/build/lightagent-backend.spec --noconfirm
"""
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Resolve the repo root from the spec's own location (desktop/build/ -> root),
# independent of the current working directory. PyInstaller exposes SPECPATH.
ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))


def rp(*parts):
    """Absolute path under the repo root."""
    return os.path.join(ROOT, *parts)

# --- Hidden imports -------------------------------------------------------
# Channels are imported dynamically by channel_factory via string names, so
# PyInstaller's static analysis can't see them. List every channel we ship
# (Feishu is intentionally excluded — lark-oapi is dropped from the desktop
# build to save ~116MB).
hiddenimports = [
    # channels (dynamic import in channel/channel_factory.py)
    'channel.web.web_channel',
    'channel.terminal.terminal_channel',
    'channel.weixin.weixin_channel',
    'channel.wechatmp.wechatmp_channel',
    'channel.wechatcom.wechatcomapp_channel',
    'channel.wechat_kf.wechat_kf_channel',
    'channel.dingtalk.dingtalk_channel',
    'channel.wecom_bot.wecom_bot_channel',
    'channel.qq.qq_channel',
    'channel.telegram.telegram_channel',
    'channel.slack.slack_channel',
    'channel.discord.discord_channel',
]

# Agent tools and model providers are imported lazily in places; collect their
# submodules so nothing is missed at runtime.
hiddenimports += collect_submodules('agent.tools')
hiddenimports += collect_submodules('models')
hiddenimports += collect_submodules('voice')
hiddenimports += collect_submodules('bridge')

# Plugin framework + plugins. WebChannel -> ChatChannel imports
# `from plugins import *`, and desktop mode loads plugins (in a background
# thread) so command plugins like lightagent_cli/godcmd (/status, #help) work. Plugin
# modules are imported dynamically by name in scan_plugins(), so list them
# explicitly. The `cli` package is a lightagent_cli dependency (`from cli import ...`).
hiddenimports += [
    'plugins',
    'plugins.event',
    'plugins.plugin',
    'plugins.plugin_manager',
]
hiddenimports += collect_submodules('plugins')

# `cli` powers lightagent_cli's slash commands (`lightagent skill install`, `lightagent status`, …).
# Its command modules are imported lazily inside functions, so static analysis
# misses them. collect_submodules('cli') alone proved unreliable (a build can
# end up with `cli` but not `cli.commands`), so list the command modules
# explicitly AND ship the package as data (see datas) as a belt-and-suspenders.
hiddenimports += collect_submodules('cli')
hiddenimports += [
    'cli',
    'cli.cli',
    'cli.utils',
    'cli.commands',
    'cli.commands.skill',
    'cli.commands.process',
    'cli.commands.context',
    'cli.commands.install',
    'cli.commands.knowledge',
]

# Third-party SDKs that use lazy/conditional imports internally.
hiddenimports += collect_submodules('dashscope')
hiddenimports += [
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
]

# Document parsing libs. The read / web_fetch tools import these lazily inside
# functions (e.g. `from pypdf import PdfReader`), so PyInstaller's static
# analysis misses them and they'd be dropped from the bundle — leaving the
# desktop client unable to read PDF/Word/Excel/PPT. List them explicitly.
hiddenimports += [
    'pypdf',
    'docx',           # python-docx
    'pptx',           # python-pptx
    'openpyxl',
]
hiddenimports += collect_submodules('pypdf')
hiddenimports += collect_submodules('docx')
hiddenimports += collect_submodules('pptx')
hiddenimports += collect_submodules('openpyxl')

# --- Data files -----------------------------------------------------------
# Runtime-read files/dirs that must travel with the executable. Paths are
# (source, dest_dir_in_bundle).
datas = [
    (rp('config-template.json'), '.'),
    (rp('skills'), 'skills'),
    # PluginManager.scan_plugins() walks the on-disk ./plugins dir at runtime
    # (it doesn't rely solely on imports), so ship the package directory too.
    (rp('plugins'), 'plugins'),
    # Ship the `cli` package as loose files too: onedir adds _internal to
    # sys.path, so `import cli.commands.*` resolves even if PyInstaller's
    # submodule collection misses the lazily-imported command modules.
    (rp('cli'), 'cli'),
    # Web console served on the backend port: ship chat.html plus its static
    # assets (~1.9MB) so the browser-based console works as a debug/fallback
    # entry alongside the Electron UI.
    (rp('channel', 'web', 'chat.html'), 'channel/web'),
    (rp('channel', 'web', 'static'), 'channel/web/static'),
]

# Some libraries (tiktoken encodings, etc.) ship data files.
datas += collect_data_files('tiktoken_ext', include_py_files=False)

# python-docx / python-pptx bundle template files (default.docx / default.pptx,
# content-type XML) inside their packages; they're loaded at import/parse time,
# so ship them or document parsing fails in the frozen build.
datas += collect_data_files('docx')
datas += collect_data_files('pptx')

# --- Excludes -------------------------------------------------------------
# Keep the bundle lean: drop Feishu's heavy SDK, plugins (disabled in desktop
# mode), tests/docs, and dev-only packages.
excludes = [
    'lark_oapi',          # Feishu — ~116MB, excluded from desktop build
    'tests',
    'pip',
    'wheel',
    'pytest',
    'playwright',         # browser tool is opt-in, not bundled
]

block_cipher = None

a = Analysis(
    [rp('app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lightagent-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='lightagent-backend',
)
