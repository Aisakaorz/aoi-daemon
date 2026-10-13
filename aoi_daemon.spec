# -*- mode: python ; coding: utf-8 -*-
"""
葵之使魔 PyInstaller 打包配置（Windows 单文件 exe）

用法：.venv\\Scripts\\pyinstaller.exe aoi_daemon.spec --noconfirm

说明：
- 打包用户自备资源：fonts/icons/sounds（模型 resources/model 与语音模型
  resources/whisper 按设计排除——首次运行按 README 引导放置/应用内下载）
- 收集语音链路原生依赖（sounddevice / faster-whisper / ctranslate2）
- 子进程启动画面通过 --splash-child 参数复用本 exe，无需额外文件
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("resources/fonts", "resources/fonts"),
    ("resources/icons", "resources/icons"),
    ("resources/sounds", "resources/sounds"),
    ("splash_child.py", "."),
]

# 语音链路的原生库与数据（sounddevice 的 portaudio、faster-whisper 的 ctranslate2）
for pkg in ("sounddevice", "faster_whisper", "ctranslate2"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

hiddenimports = []

# live2d-py：l2d/__init__.py 动态修改 sys.path 后 import，静态分析不可见，需显式收集
try:
    hiddenimports += collect_submodules("live2d")
    datas += collect_data_files("live2d")
except Exception:
    pass

for pkg in ("faster_whisper", "ctranslate2"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AoiDaemon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/icons/app_icon.ico",
)
