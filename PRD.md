# AoiDaemon PRD ~葵之使魔~

## 1. 项目概述

桌面级 Live2D AI 伴侣应用，支持 Windows 与 macOS。透明无边框窗口悬浮桌面最上层，接 Kimi Claw API，支持打字/语音聊天，角色实时改变表情、口型和动作。

**角色形象**：葵酱（Aoi）基于 Live2D 免费模型 haru，可通过替换模型资源自定义为其他 Live2D 角色。

**核心定位**：桌面使魔/看板娘 + AI 对话伴侣 + 语音交互。

**技术栈**：PySide6 + live2d-py(v2) + requests + faster-whisper + sounddevice + numpy

---

## 2. 功能需求

### 2.1 窗口系统

**FR-WS-001 透明无边框置顶窗口**
- 窗口类型：Qt.Tool + Qt.WindowStaysOnTopHint + Qt.FramelessWindowHint
- 背景透明：Qt.WA_TranslucentBackground
- 尺寸：默认 400×600（竖屏），用户可配置
- 位置：默认屏幕右下角，记忆上次关闭位置
- 拖拽：按住角色任意区域可拖拽移动，释放后记录新位置

**FR-WS-002 右键菜单（与托盘菜单一致）**
- 显示/隐藏葵酱（动态文字，根据窗口可见性自动切换）
- 聊天开关（动态文字：想和葵酱聊天 / 不和葵酱聊天）
- 窗口置顶（checkable，默认开启）
- 角色大小（子菜单：小 0.75x / 中 1.0x / 大 1.25x）
- 关于
- 退出

**FR-WS-003 系统托盘**
- 最小化到托盘，左键显示/隐藏主窗口
- 右键弹出菜单（与角色右键菜单共用同一份菜单，功能完全一致）

### 2.2 Live2D 渲染引擎

**FR-LE-001 模型加载**
- 使用 live2d.v2（Cubism 2.x）加载用户自备模型
- 模型路径可配置，默认 resources/model/live2d-widget-model-haru/haru02.model.json
- 支持模型热切换，加载失败显示占位提示不崩溃

**FR-LE-002 渲染循环**
- 60 FPS，QTimer/paintGL 驱动 Update() 和 Draw()
- resize 时自动调用 model.Resize(w, h)

**FR-LE-003 鼠标交互映射**
- 视线跟踪：鼠标归一化坐标 (-1~1) -> ParamEyeBallX / ParamEyeBallY
- 头部跟随：ParamAngleX / ParamAngleY / ParamAngleZ（轻微幅度）
- 呼吸动画：正弦波驱动 ParamBreath，周期 3~4 秒

**FR-LE-004 点击反馈 (Hit Area)**
- Head -> flickHead_00.mtn（摸头反应）
- Body -> tapBody_00.mtn ~ tapBody_09.mtn（身体互动）
- 可选播放 snd/ 目录下对应音效

**FR-LE-005 动作状态机**

| 状态 | 可用动作文件 | 触发条件 |
|------|-------------|---------|
| Idle | idle_00.mtn / idle_01.mtn / idle_02.mtn | 默认循环 |
| Greeting | idle_00.mtn | 启动时播放一次 |
| Thinking | idle_01.mtn | 用户发送后等待 API 回复期间 |
| Talking | idle_00.mtn | TTS 播放期间 |
| Happy | pinchOut_00.mtn | AI 回复情感积极 |
| Sad | pinchIn_00.mtn | AI 回复情感消极 |
| TapHead | flickHead_00.mtn | 点击头部 hit area |
| TapBody | tapBody_00.mtn ~ tapBody_09.mtn | 点击身体 hit area |

- 优先级：交互状态(Tap/Thinking/Talking) > 情感状态(Happy/Sad) > Idle
- 非循环 motion 播放完自动回 Idle

**FR-LE-006 口型同步**
- TTS 播放时实时分析音频帧 RMS 音量
- 音量 (0~1) 映射到 ParamMouthOpenY
- 音频结束后缓降到 0（不要瞬间归零）
- smooth_factor 配置项（默认 0.3）

### 2.3 聊天系统

**FR-CH-001 聊天气泡 UI**
- 浮动面板，圆角矩形，半透明渐变背景
- 用户消息：右对齐蓝色气泡；AI 消息：左对齐粉色气泡
- 消息过多时旧消息随高度淡出消失，气泡大小保持不变，不被压缩
- 手动字符级换行，文本垂直居中
- 打字指示器（三个跳动圆点波浪动画）

**FR-CH-002 文本输入与语音输入**
- Enter 发送，Shift+Enter 换行
- placeholder：跟葵酱说点什么吧~
- 发送后清空输入框，触发 Thinking 状态
- **语音按钮**：输入框左侧 🎙 按钮，长按 300ms 开始录音，松开结束
  - 录音时清空输入框，placeholder 变为 "🎙 正在聆听... 松开按钮结束录音"
  - 输入框禁用键盘输入（避免语音与键盘冲突）
  - 录音结果直接填入输入框，用户自行回车发送
  - 单击或长按不够时，显示提示气泡（葵酱的提醒）
- **输入框 galgame 风格**：
  - 暖白底 rgba(255,250,245) + 珊瑚粉边框 rgba(255,200,195)
  - focus 时 2px 高亮边框 + 外发光
  - 圆角 10px，字体 #4A3F3A
- 语音按钮与输入框随面板宽度同步缩放

**FR-CH-003 模型下载对话框**
- 首次使用 STT 且本地无模型时弹出确认对话框
- 确认后显示进度条，后台下载 faster-whisper tiny 模型（~39MB）
- 支持取消下载（终止线程并清空已下载内容）
- 下载失败友好提示（网络超时、连接失败等）

**FR-CH-004 对话历史**
- v0.1 内存级；v0.5 升级为 SQLite 持久化

### 2.4 AI 后端

**FR-AI-001 API 通信**
- HTTP POST Kimi Claw API，请求体：
  {"instance_id": "<ID>", "message": "...", "include_memory_context": true}
- 提取 choices[0].message.content
- 超时 30 秒，超时提示葵酱好像走神了...

**FR-AI-002 配置管理**
- api_key / instance_id / base_url（默认 https://api.kimi.com/v1/claw/chat）
- 保存在 config.yaml 或 .env，API Key 密码掩码显示

**FR-AI-003 情感分析**
- 积极词：开心、太好了、哈哈、棒、喜欢、！
- 消极词：难过、抱歉、不行、遗憾、...、唉
- 返回 positive / neutral / negative，驱动 Happy/Sad 状态
- 封装 sentiment.py，后续可替换为模型推理

### 2.5 语音系统

**FR-VO-001 语音输入 (STT)**
- faster-whisper tiny 模型本地推理（~39MB，存放于 resources/whisper/tiny/）
- 长按语音按钮 300ms 开始录音，松开结束
- sounddevice InputStream 非阻塞录制，16kHz, 16bit, 单声道
- 录音保存为临时 WAV，转录完成后自动清理
- 转录结果填入输入框
- `grabMouse()` 捕获鼠标，移出窗口松开也能正常停止录音
- 15 秒自动停止后备（防止 grabMouse 失效等极端情况）

**FR-VO-002 语音输出 (TTS)**
- edge-tts，中文女声（zh-CN-XiaoxiaoNeural / zh-CN-XiaoyiNeural）
- 收到 AI 回复后自动生成 MP3 到 temp 目录并播放
- 播放后自动清理临时文件
- 设置中可开关（默认开启）

### 2.6 配置系统

**FR-ST-001 设置窗口**
- QTabWidget 标签页：通用 / AI / 语音 / 显示
- 通用：开机自启、透明度滑条、置顶开关、模型路径选择
- AI：API Key（密码框）、Instance ID、Base URL、情感分析开关
- 语音：TTS 开关、音色下拉、STT 开关、模型大小选择（tiny/base/small）
- 显示：窗口尺寸、初始位置、帧率限制（30/60 FPS）

**FR-ST-002 配置持久化**
- 路径：~/.aoi-daemon/config.yaml
- Pydantic Settings 类型校验，变更即时生效
- API Key 等敏感信息加密存储（至少 base64）

---

## 3. 文件结构

```
AoiDaemon/
├── main.py
├── requirements.txt
├── config.yaml
├── README.md
├── PRD.md
├── TASK.md
├── PROMPTS.md
├── .gitignore
├── core/
│   ├── app.py              # 应用主控制器，协调各模块
│   ├── __init__.py
│   └── state_machine.py    # 角色动作状态机
├── ui/
│   ├── main_window.py      # 透明无边框置顶窗口/拖拽/缩放/菜单
│   ├── live2d_canvas.py    # QOpenGLWidget + live2d-py 渲染
│   ├── chat_panel.py       # 聊天气泡面板 + 输入框 + 语音按钮
│   ├── model_download_dialog.py  # STT 模型下载确认+进度对话框
│   ├── tray_icon.py        # 系统托盘
│   └── __init__.py
├── l2d/                    # Live2D 业务封装（避免与第三方 live2d-py 包名冲突）
│   ├── __init__.py         # Monkey-patch MeshContext 导入 bug
│   ├── model_wrapper.py    # LAppModel 封装
│   └── motion_manager.py   # 动作播放管理（优先级/队列/回调）
├── ai/
│   ├── __init__.py
│   ├── base_provider.py    # AI Provider 抽象基类
│   └── kimi_claw_provider.py
├── voice/
│   ├── __init__.py
│   └── stt_provider.py     # STT 封装：AudioRecorder + faster-whisper
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── helpers.py
├── lib/
│   ├── Core.dll            # Windows（需自行下载）
│   └── libCore.dylib       # macOS（需自行下载）
└── resources/
    ├── icons/              # 应用图标
    ├── model/              # Live2D 模型（用户自备，见 README）
    ├── sounds/             # 音效文件
    └── whisper/            # STT 模型（首次使用下载，或手动放置）
        └── tiny/           # faster-whisper tiny 模型文件
```

---

## 4. 版本迭代计划

### v0.1 MVP —— 最小可玩版本
透明窗口 + Live2D 渲染 + 视线/呼吸/点击 + 状态机 + 聊天气泡 + 托盘 + 音效

### v0.1.1 —— 菜单与交互优化
- 任务栏与角色右键菜单统一（共用同一份 QMenu）
- 菜单项动态文字：显示/隐藏葵酱、想和/不和葵酱聊天
- 角色大小选择（小 0.75x / 中 1.0x / 大 1.25x）
- 角色大小切换时已有气泡同步重新换行与调整尺寸（避免截断）

### v0.1.2 —— 语音输入与输入框美化
- 输入框左侧语音转文字按钮（🎙 图标，长按 300ms 录音/松开转录）
- faster-whisper tiny 本地语音转文字，录音保存为临时 WAV
- 输入框 galgame 风格美化（暖白底+珊瑚粉边框+focus 高亮外发光）
- 首次使用 STT 时检测本地模型，无模型则弹出下载对话框（带进度条）
- `grabMouse()` 确保移出窗口松开也能正常停止录音

### v0.2 —— 接入真实 AI
- 接入 Kimi Claw API 真实 HTTP 请求（替换占位模式）
- 对话历史内存级管理（最近 20 条上下文）
- API 超时/断网容错处理

### v0.3 —— 语音输出（TTS）+ 口型同步
- edge-tts 集成，中文女声合成
- 音频播放 + 临时文件自动清理
- TTS 开关（设置中可关闭）
- 口型同步：音频 RMS 音量 → ParamMouthOpenY

### v0.4 —— 情感分析与状态机增强
- 简易情感分析（关键词匹配 positive/neutral/negative）
- 情感驱动状态机 Happy / Sad 状态
- AI 回复后自动触发对应表情动作

### v0.5 —— 设置窗口与配置持久化
- 设置窗口（QTabWidget：通用 / AI / 语音 / 显示）
- 配置持久化（~/.aoi-daemon/config.yaml）
- API Key / Instance ID / Base URL 可配置
- 语音页：TTS 开关、STT 开关、音色选择

### v0.6 —— 聊天历史持久化与打包
- 聊天历史 SQLite 持久化（~/.aoi-daemon/history.db，最近 50 条）
- 开机自启（Windows 注册表 / Mac launchd）
- PyInstaller（Windows）、Py2app（macOS）打包

---

## 5. 接口定义（供 Kimi Code 直接实现）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ChatResponse:
    text: str
    sentiment: str  # "positive" | "neutral" | "negative"

class BaseAIProvider(ABC):
    @abstractmethod
    def chat(self, message: str, history: list[dict]) -> ChatResponse:
        """Send message, return AI reply text with sentiment tag"""
        pass
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate current config is usable"""
        pass

class BaseTTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: str) -> None:
        """Synthesize text to audio file saved at output_path"""
        pass
    @abstractmethod
    def get_voices(self) -> list[dict]:
        """Return available voice list"""
        pass

class BaseSTTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text"""
        pass

class Live2DModelWrapper:
    def load(self, model_path: str) -> bool: ...
    def update(self, delta_time: float) -> None: ...
    def draw(self) -> None: ...
    def set_param(self, param_name: str, value: float) -> None: ...
    def start_motion(self, motion_name: str, priority: int, loop: bool = False) -> None: ...
    def hit_test(self, x: float, y: float) -> str | None: ...
    def resize(self, width: int, height: int) -> None: ...
```

---

## 6. 踩坑提示

1. **live2d-py Core 库**：不含 Core 动态库，需手动从 Live2D 官网下载 Cubism SDK for Native，放置 lib/Core.dll（Windows）或 lib/libCore.dylib（macOS）。缺失时报 FileNotFoundError 或 OSError。
2. **v2 vs v2cpp**：必须使用 `live2d.v2`（纯 Python），`live2d.v2cpp` 会抛出 `NullFunctionError: glGenFramebuffers`。
3. **MeshContext 导入 bug**：需在 `l2d/__init__.py` 中 monkey-patch `live2d.v2.core.alive2d_model` 的 MeshContext 导入。
4. **OpenGL 上下文**：glewInit() 必须在 QOpenGLWidget.initializeGL() 中调用，__init__ 中提前调用会崩溃。
5. **模型居中**：`Resize()` 会覆盖布局宽度为 2.0，导致模型左偏，需用 `SetOffset(0.45, 0.0)` 补偿。
6. **纹理参数**：加载贴图后必须设置 `GL_TEXTURE_WRAP_S/T = GL_CLAMP_TO_EDGE` 和 `GL_TEXTURE_MIN/MAG_FILTER = GL_NEAREST`，否则出现接缝线。
7. **FFmpeg stderr**：Qt 多媒体播放 MP3 时 C 库会写 stderr（fd 2）， bypass Python sys.stderr。需在 `main.py` 开头用 `os.dup2` 将 fd 2 重定向到 devnull，同时恢复 Python `sys.stderr` 绑定到原始 fd。
8. **QGraphicsOpacityEffect 不兼容**：Qt6 中 `QGraphicsOpacityEffect` + `border-radius` 会导致动画期间变方。解决方案：用 `QPainter.setOpacity()` 在 QWidget 上自绘圆角矩形和文本。
9. **QBoxLayout 压缩 spacing**：`QVBoxLayout` 空间不足时会优先压缩 `spacing` 导致气泡重叠。解决方案：禁用自动布局（`setEnabled(False)`），手动计算每条消息的 y 坐标。
10. **widget 首次显示前 height() 返回 0**：手动布局时 `w.height()` 在 widget 首次显示前可能返回 0。解决方案：创建 widget 时存储 `_layout_height` 属性，所有布局计算使用该属性值。
11. **faster-whisper 模型下载**：首次运行自动从 HuggingFace 下载 tiny 模型（~39MB），应用内弹窗带进度条。也可手动放置到 `resources/whisper/tiny/`。
12. **grabMouse 与模态对话框冲突**：`_VoiceButton` 长按录音时调用 `grabMouse()`，若此时弹出模态下载对话框，需在弹窗前调用 `releaseMouse()` 或 `reset_style()` 释放捕获，否则对话框可能无法交互。
13. **API Key 安全**：不要硬编码，使用环境变量或本地加密配置文件。开源前检查 .gitignore 排除 config.yaml 和 .env。
14. **Live2D 模型版权**：开源仓库不放完整模型。本项目演示使用的 haru 模型来源于 hexo-helper-live2d 项目，版权归属 Live2D Inc.。README 需注明模型文件需用户自行提供。
15. **macOS 权限**：首次运行可能需授予麦克风权限（STT）和辅助功能权限（开机自启）。
