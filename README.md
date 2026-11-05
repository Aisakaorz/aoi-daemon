# 葵之使魔 ~ AoiDaemon ~

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.11%2B-green)
![Live2D](https://img.shields.io/badge/Live2D-Cubism%202.x-darkorange)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-steelblue)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-In%20Development-orange.svg)

> 桌面级 Live2D 伴侣应用 —— 你的桌面使魔 / 看板娘
>
> **葵酱（Aoi）** 基于 Live2D 免费模型 **haru**

## ✨ 功能特性

- 🎭 **Live2D 实时渲染** —— 60 FPS，4x MSAA + 2x 超采样，高 DPI 自适应；视线跟随鼠标、呼吸动画、空闲自动播放动作
- 👆 **点击互动** —— 摸头 / 身体互动触发不同动作与音效
- 💬 **聊天面板** —— 气泡式界面，本地占位回复（无需联网），支持文字选择、滚轮浏览历史
- 🎙 **语音输入** —— 长按 🎙 说话，faster-whisper 本地转文字填入输入框
- 🎀 **设置窗口** —— 角色大小、窗口置顶、任务栏吸附、语音模型下载 / 使用 / 删除，即改即存
- 🧲 **任务栏吸附** —— 拖拽释放自动贴住任务栏顶部，可开关
- 🖱 **透明无边框窗口** —— 置顶悬浮、透明区域鼠标穿透、系统托盘
- ⏳ **启动加载画面** —— 独立子进程驱动，模型加载期间动画全程流畅
- 💾 **配置持久化** —— 窗口位置与各项开关自动保存，重启恢复
- 🍎 **双平台** —— Windows / macOS，Windows 已提供单文件 exe 打包

## 🚀 快速开始

**环境要求**：Python 3.10+ · Windows 10+ / macOS 12+ · OpenGL

```bash
git clone https://github.com/Aisakaorz/aoi-daemon.git
cd aoi-daemon

# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

启动后葵酱会出现在屏幕右下角。语音转文字模型首次使用时按提示在「设置」里下载（约 75MB），也可手动放到 `resources/whisper/tiny/`。

## 🕹 使用

| 操作 | 说明 |
|------|------|
| **左键拖拽** | 移动角色 |
| **点击头部 / 身体** | 摸头反应 / 身体互动（动作 + 音效） |
| **右键（角色或托盘）** | 显示 / 隐藏葵酱、聊天开关、设置、退出 |
| **左键托盘图标** | 显示 / 隐藏主窗口 |
| **Enter** | 在聊天输入框发送消息 |
| **长按 🎙 按钮** | 语音输入，松开后自动转文字填入输入框 |
| **滚轮上滚** | 浏览历史消息，点 ▼ 回到底部 |
| **拖拽释放** | 靠近任务栏时自动吸附 |

## 📦 打包

```bash
pip install pyinstaller
.venv\Scripts\pyinstaller.exe aoi_daemon.spec --noconfirm
```

产物为 `dist/AoiDaemon.exe`（单文件，已内置字体与图标）。配置文件、日志、临时文件生成在 exe 同级目录。

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 (Qt 6) |
| Live2D 渲染 | live2d-py v2（Cubism 2.x，纯 Python） |
| 语音识别 | faster-whisper tiny |
| 模型下载 | ModelScope（hf-mirror 回退） |
| 打包 | PyInstaller |

## 📁 项目结构

```
aoi-daemon/
├── main.py · splash_child.py   应用入口 / 启动画面子进程
├── core/      应用装配、平台引导、使魔档案、动作状态机
├── ui/        主窗口、Live2D 画布、聊天、设置、卡片绘制
├── l2d/       live2d-py 封装
├── ai/        聊天 Provider（本地占位回复）
├── voice/     语音模型管理与转录
├── utils/     配置、路径、字体、日志
└── resources/ 图标、字体等资源
```

## 📄 资源声明

- 演示角色 **haru** 由 [Live2D Inc.](https://www.live2d.com/) 发布、经 [hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) 项目分发，版权归 Live2D Inc.
- 内置字体 **ZCOOL 站酷快乐体** 以 [SIL Open Font License 1.1](https://openfontlicense.org/) 发布，许可证全文见 `resources/fonts/OFL-ZCOOLKuaiLe.txt`

## 📜 License

[MIT License](LICENSE)

## 🙏 致谢

[Live2D Inc.](https://www.live2d.com/) · [hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) · [live2d-py](https://github.com/EasyLive2D/live2d-py) · [PySide6](https://wiki.qt.io/Qt_for_Python) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
