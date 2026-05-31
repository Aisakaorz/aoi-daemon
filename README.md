# 葵之使魔 ~ AoiDaemon ~

> 桌面级 Live2D AI 伴侣应用 —— 你的桌面使魔/看板娘
>
> **葵酱（Aoi）** 是基于 Live2D 免费模型 **haru** 的桌面看板娘

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.11%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)

## ✨ 功能特性

- 🎭 **Live2D 实时渲染** —— 60 FPS 流畅渲染，视线跟随鼠标，自然呼吸动画
- 💬 **AI 对话聊天** —— 接入 Kimi Claw API，支持文本交互（v0.1 为占位模式，v0.2 接入真实 API）
- 🎙️ **语音输入** —— 长按 🎙 按钮说话，faster-whisper 本地转文字填入输入框
- 📥 **语音模型管理** —— 菜单栏选择语音转文字模型，支持后台下载，托盘实时显示进度
- 👆 **点击互动** —— 点击头部/身体触发不同动作反应，附带音效反馈
- 🧲 **任务栏吸附** —— 拖拽释放自动吸附任务栏顶部，可菜单开关
- 🤖 **自动动作** —— 空闲时不定时自动播放动作（摇头/捏脸/身体互动），不触发音效
- 🎨 **透明无边框窗口** —— 悬浮桌面最上层，不打扰正常工作
- 🖱️ **鼠标穿透** —— 点击角色外区域不遮挡底层窗口操作
- 💻 **系统托盘** —— 最小化到托盘，右键快捷菜单
- 📐 **角色大小切换** —— 小/中/大三档缩放，气泡同步自适应
- 📜 **滚轮浏览历史** —— 消息区域滚轮上滚查看历史，顶部消息渐变淡出，底部 mask 硬截断不遮挡输入框
- 🔊 **录音音量可视化** —— 长按录音时语音按钮实时显示音量条，直观反馈麦克风音量
- 👁️ **全局视线跟踪** —— 即使鼠标移出窗口，葵酱也会持续看向鼠标方向
- 🛡️ **模型完整性检查** —— 菜单打开时自动检测模型文件是否存在，缺失时自动取消勾选
- 🔄 **下载自动切换** —— 首次下载完成后自动设为当前语音模型，无需手动切换
- ⏳ **启动加载画面** —— Live2D 模型加载期间显示启动画面，带真实进度反馈，避免空白窗口
- 🚫 **模型缺失优雅降级** —— 首次运行未放置模型文件时弹出友好提示，引导用户查看 README 配置，而非透明窗口无感知崩溃

## 📦 安装

### 环境要求

- Python 3.10+
- Windows 10+ / macOS 12+
- OpenGL 支持

### 1. 克隆仓库

```bash
git clone https://github.com/Aisakaorz/aoi-daemon.git
cd aoi-daemon
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 Live2D 模型（必需）

**本仓库不提供模型文件**，需自行下载后放置到 `resources/model/` 目录。

本项目默认使用 **haru** 模型作为演示角色（葵酱），该模型为 Live2D 官方免费模型。

本项目开发时使用的演示模型为 **haru**（Cubism 2.x 格式），可通过以下方式获取：

**方式一：hexo-helper-live2d（推荐）**

该模型来源于 [hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) 项目，这是 Hexo 博客中广泛使用的 Live2D 看板娘插件：

```bash
# 1. 新建临时目录并安装 npm 包
mkdir temp-model && cd temp-model
npm init -y
npm install live2d-widget-model-haru

# 2. 复制模型文件到项目目录
cp -r node_modules/live2d-widget-model-haru/assets/* \
      /path/to/aoi-daemon/resources/model/live2d-widget-model-haru/
```

**方式二：Live2D 官方免费模型**

访问 [Live2D 官方免费素材](https://www.live2d.com/learn/sample/) 下载其他 Cubism 2.x 模型，放置到 `resources/model/` 下并修改 `l2d/model_wrapper.py` 中的加载路径。

模型文件夹结构示例：
```
resources/model/live2d-widget-model-haru/
├── haru02.model.json      # 模型入口文件（程序中硬编码此路径）
├── haru02.physics.json
├── haru02.pose.json
├── exp/                   # 表情文件 .exp.json
├── moc/                   # 模型核心 .moc + 贴图
│   └── haru02.1024/
│       ├── texture_00.png
│       ├── texture_01.png
│       └── texture_02.png
├── mtn/                   # 动作文件 .mtn
│   ├── idle_00.mtn
│   ├── idle_01.mtn
│   ├── idle_02.mtn
│   ├── flickHead_00.mtn
│   ├── tapBody_00.mtn ~ tapBody_09.mtn
│   ├── pinchIn_00.mtn
│   ├── pinchOut_00.mtn
│   └── shake_00.mtn
└── snd/                   # 音效文件 .mp3（可选）
    ├── flickHead_00.mp3
    ├── tapBody_00.mp3
    └── ...
```

> ⚠️ 请确保模型文件路径与 `l2d/model_wrapper.py` 中的 `model_path` 一致。

### 5. 配置语音转文字模型（可选）

语音转文字功能基于 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) tiny 模型（约 75MB）。

**方式一：应用内下载（推荐）**

右键菜单 → 「语音转文字模型」→ 选择「Whisper Tiny」。若未下载，选择后直接开始下载，进度条显示在输入框位置；点击 ⏳ 图标可取消下载，在托盘查看实时进度。

**方式二：手动提前下载**

如果你希望避免首次使用时的下载等待，可提前将模型文件放置到 `resources/whisper/tiny/` 目录：

```bash
# 使用 huggingface-cli 下载
pip install huggingface-hub
huggingface-cli download guillaumekln/faster-whisper-tiny \
  --local-dir resources/whisper/tiny \
  --local-dir-use-symlinks False
```

或直接从 [HuggingFace](https://huggingface.co/guillaumekln/faster-whisper-tiny/tree/main) 手动下载所有文件放入 `resources/whisper/tiny/`。

## 🚀 使用

```bash
python main.py
```

启动后，葵酱会出现在屏幕右下角。

| 操作 | 说明 |
|------|------|
| **左键拖拽** | 按住角色任意区域拖动窗口位置 |
| **点击头部** | 摸头反应（flickHead 动作 + 音效） |
| **点击身体** | 身体互动（随机 tapBody 动作 + 音效） |
| **右键（角色或托盘）** | 显示/隐藏葵酱、聊天开关、窗口置顶、任务栏吸附、角色大小（小/中/大）、关于、退出 |
| **左键托盘图标** | 显示/隐藏主窗口 |
| **Enter** | 在聊天面板输入框中发送消息 |
| **长按 🎙 按钮** | 语音输入：长按 300ms 开始录音，松开自动转文字填入输入框（模型未下载时会提示去菜单栏下载） |
| **滚轮上滚** | 在消息区域滚轮向上滚动查看历史消息，点击 ▼ 按钮或滚轮向下回到底部 |
| **拖拽释放** | 角色靠近任务栏时自动吸附，远离时不吸附 |

## 📁 项目结构

```
aoi-daemon/
├── main.py                     # 应用入口
├── requirements.txt            # 依赖列表
├── core/
│   ├── app.py                  # 应用主控制器
│   └── state_machine.py        # 角色动作状态机
├── ui/
│   ├── main_window.py          # 透明无边框置顶窗口
│   ├── live2d_canvas.py        # Live2D 渲染画布
│   ├── chat_panel.py           # 聊天气泡面板 + 输入框 + 语音按钮 + 下载进度
│   ├── splash_screen.py        # 启动加载画面（模型加载期间显示）
│   └── tray_icon.py            # 系统托盘
├── l2d/
│   ├── __init__.py             # MeshContext 修复
│   └── model_wrapper.py        # Live2D 模型封装
├── ai/
│   ├── base_provider.py        # AI Provider 抽象基类
│   └── kimi_claw_provider.py   # Kimi Claw API 封装
├── voice/
│   ├── model_manager.py        # 模型注册表 + 下载管理器
│   └── stt_provider.py         # STT 封装：录音 + faster-whisper 转录
├── utils/
│   └── logger.py               # 统一日志
└── resources/
    ├── icons/                  # 应用图标
    ├── model/                  # Live2D 模型文件（需自行放置，见上文）
    ├── sounds/                 # 音效文件
    └── whisper/                # STT 模型（首次使用自动下载，或手动放置）
        └── tiny/
```

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 |
| Live2D 渲染 | live2d-py (v2, Cubism 2.x) |
| AI 对话 | Kimi Claw API（v0.2 接入） |
| 语音识别 | faster-whisper tiny |
| 语音合成 | edge-tts（v0.3） |
| 日志 | Python logging |

## 📋 版本路线图

| 版本 | 内容 | 状态 |
|------|------|------|
| v0.1 | 透明窗口 + Live2D 渲染 + 聊天气泡 + 托盘 | ✅ |
| v0.1.1 | 菜单统一 + 动态文字 + 角色大小选择 | ✅ |
| v0.1.2 | 语音输入(STT) + 输入框 galgame 美化 + 模型下载对话框 | ✅ |
| v0.1.3 | 任务栏吸附 + 聊天面板位置优化 | ✅ |
| v0.1.4 | 空闲时自动播放动作 | ✅ |
| v0.1.5 | 语音模型下载入口重构（菜单选择+后台下载+托盘进度） | ✅ |
| v0.1.7 | 启动加载画面 + 模型缺失优雅降级 | ✅ |
| v0.2 | 接入真实 Kimi Claw API | 📋 |
| v0.3 | TTS 语音输出 + 口型同步 | 📋 |
| v0.4 | 情感分析 + 状态机 Happy/Sad 状态 | 📋 |
| v0.5 | 设置窗口 + 配置持久化 | 📋 |
| v0.6 | SQLite 历史 + 开机自启 + 打包 | 📋 |

## 📄 模型与资源声明

### haru 模型来源

本项目开发演示使用的 **haru** 模型来源于 [hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) 项目，这是 Hexo 博客社区广泛使用的 Live2D 看板娘插件。该模型最初由 [Live2D Inc.](https://www.live2d.com/) 发布为免费模型。

- **模型版权归属**：Live2D Inc.
- **仓库分发政策**：本开源仓库**不包含**任何 Live2D 模型文件
- **用户责任**：请自行获取模型文件并放置到 `resources/model/` 目录
- **获取方式**：参见上文「配置 Live2D 模型」章节

### 图标与音效

- 应用图标（`resources/icons/`）为项目原创或开源图标，遵循 MIT 协议
- 模型音效（`snd/*.mp3`）随模型文件一同提供，版权归属 Live2D Inc.

## 📜 License

[MIT License](LICENSE)

## 🙏 致谢

- [Live2D Inc.](https://www.live2d.com/) — Cubism SDK 与免费模型
- [hexo-helper-live2d](https://github.com/EYHN/hexo-helper-live2d) — haru 模型分发
- [live2d-py](https://github.com/EasyLive2D/live2d-py) — Python Live2D 绑定
- [PySide6](https://wiki.qt.io/Qt_for_Python) — Qt Python 绑定
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 本地语音识别
- [Kimi](https://kimi.moonshot.cn/) — AI 对话 API
