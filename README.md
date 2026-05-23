# 葵之使魔 ~ AoiDaemon ~

> 桌面级 Live2D AI 伴侣应用 —— 你的桌面使魔/看板娘
>
> **葵酱（Aoi）** 是基于 Live2D 免费模型 **haru** 的桌面看板娘。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)

<p align="center">
  <!-- 在此处放置演示 GIF -->
  <img src="docs/demo.gif" alt="AoiDaemon Demo" width="320">
</p>

## ✨ 功能特性

- 🎭 **Live2D 实时渲染** —— 60 FPS 流畅渲染，视线跟随鼠标，自然呼吸动画
- 💬 **AI 对话聊天** —— 接入 Kimi Claw API，支持文本交互（v0.1 为占位模式，v0.2 接入真实 API）
- 🔊 **语音交互** —— TTS 语音输出 + STT 语音输入（v0.3 / v0.4）
- 👆 **点击互动** —— 点击头部/身体触发不同动作反应，附带音效反馈
- 🎨 **透明无边框窗口** —— 悬浮桌面最上层，不打扰正常工作
- 🖱️ **鼠标穿透** —— 点击角色外区域不遮挡底层窗口操作
- 💻 **系统托盘** —— 最小化到托盘，右键快捷菜单

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

### 4. 配置 Live2D Core 库

Live2D Core 动态库**不随仓库分发**，需手动下载：

1. 访问 [Live2D Cubism SDK for Native](https://www.live2d.com/sdk/download/native/)
2. 下载对应平台的 Core 库
3. 放置到 `lib/` 目录：
   - **Windows**: `lib/Core.dll`
   - **macOS**: `lib/libCore.dylib`

### 5. 配置 Live2D 模型（必需）

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
| **右键** | 弹出菜单（显示/隐藏聊天、置顶开关、关于、退出） |
| **左键托盘图标** | 显示/隐藏主窗口 |
| **Enter** | 在聊天面板输入框中发送消息 |

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
│   ├── chat_panel.py           # 聊天气泡面板
│   └── tray_icon.py            # 系统托盘
├── l2d/
│   ├── __init__.py             # MeshContext 修复
│   └── model_wrapper.py        # Live2D 模型封装
├── ai/
│   ├── base_provider.py        # AI Provider 抽象基类
│   └── kimi_claw_provider.py   # Kimi Claw API 封装
├── utils/
│   └── logger.py               # 统一日志
├── lib/
│   ├── Core.dll                # Windows Live2D Core（需自行下载）
│   └── libCore.dylib           # macOS Live2D Core（需自行下载）
└── resources/
    ├── icons/                  # 应用图标
    └── model/                  # Live2D 模型文件（需自行放置，见上文）
```

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 |
| Live2D 渲染 | live2d-py (v2, Cubism 2.x) |
| AI 对话 | Kimi Claw API（v0.2 接入） |
| 语音合成 | edge-tts（v0.3） |
| 语音识别 | faster-whisper（v0.4） |
| 日志 | Python logging |

## 📋 版本路线图

| 版本 | 内容 | 状态 |
|------|------|------|
| v0.1 | 透明窗口 + Live2D 渲染 + 聊天气泡 + 托盘 | ✅ |
| v0.2 | 接入真实 Kimi Claw API | 🔜 |
| v0.3 | TTS 语音输出 + 口型同步 | 📋 |
| v0.4 | STT 语音输入 | 📋 |
| v0.5 | 设置窗口 + 配置持久化 + 情感分析 | 📋 |
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
- [Kimi](https://kimi.moonshot.cn/) — AI 对话 API
