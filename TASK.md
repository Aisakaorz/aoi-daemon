# AoiDaemon Task Board

## 任务看板

### v0.1 MVP —— 最小可玩版本

#### 窗口系统
- [✔] FR-WS-001: 透明无边框置顶窗口（Tool + FramelessWindowHint + WindowStaysOnTopHint）
- [✔] FR-WS-001: 背景透明（WA_TranslucentBackground）
- [✔] FR-WS-001: 窗口拖拽（Live2DCanvas 中计算 delta 并调用 window().move()）
- [✔] FR-WS-002: 右键菜单（显示聊天/置顶勾选/关于/退出）
- [✔] FR-WS-003: 系统托盘（自定义图标 tray_icon.png / 左键显示隐藏 / 右键菜单 / 关于弹窗）
- [✔] FR-WS-001: Windows 透明区域鼠标穿透（WS_EX_TRANSPARENT + 30ms 定时器）

#### Live2D 渲染
- [✔] FR-LE-001: Cubism 2.x 模型加载（resources/model/live2d-widget-model-haru/haru02.model.json）
- [✔] FR-LE-002: 60 FPS 渲染循环（QOpenGLWidget + QTimer）
- [✔] FR-LE-003: 视线跟踪（ParamEyeBallX / ParamEyeBallY）
- [✔] FR-LE-003: 呼吸动画（ParamBreath / ParamBodyAngleX/Y/Z，正弦波驱动）
- [✔] FR-LE-004: 点击反馈（Head→flickHead / Body→tapBody，随机选择，附带 snd/ 音效）
- [✔] FR-LE-005: 动作状态机（Idle/Greeting/Thinking/TapHead/TapBody，优先级管理，Idle 5~8s 轮播）
- [✔] FR-LE-001: 模型居中补偿（SetOffset(0.45, 0.0)）
- [✔] FR-LE-002: 纹理参数（GL_CLAMP_TO_EDGE + GL_NEAREST）消除接缝线

#### 聊天系统
- [✔] FR-CH-001: 自定义气泡组件（QPainter 自绘圆角渐变背景 + 手动字符级换行 + 文本垂直居中）
- [✔] FR-CH-001: 用户消息右对齐蓝色气泡，AI 消息左对齐粉色气泡
- [✔] FR-CH-001: 顶部高度渐变淡出（消息超出面板后随高度平方曲线淡出，完全推出后自动删除）
- [✔] FR-CH-001: 手动布局（禁用 QVBoxLayout 自动布局，固定 spacing=4px，根治压缩/重叠）
- [✔] FR-CH-002: 文本输入（Enter 发送，placeholder「跟葵酱说点什么吧~ ✨」）
- [✔] FR-CH-001: 打字指示器（三个跳动圆点波浪动画）

#### 音频
- [✔] 音效播放（QMediaPlayer + QAudioOutput，点击反馈时播放 snd/*.mp3）
- [✔] FFmpeg stderr 屏蔽（os.dup2 到 devnull，恢复 sys.stderr）

#### AI 后端（占位）
- [✔] FR-AI-001: BaseAIProvider 抽象基类 + ChatResponse
- [✔] FR-AI-001: KimiClawProvider 框架（api_key / instance_id / base_url）
- [✔] FR-AI-001: 离线占位模式（直接 echo 用户输入 + 随机模拟回复）

#### 工程骨架
- [✔] 项目目录结构（core/ / ui/ / l2d/ / ai/ / utils/ / voice/ 目录 + __init__.py）
- [✔] 统一日志（utils/logger.py，级别/格式/文件输出到 stdout）
- [✔] FR-LE-005: 状态机（core/state_machine.py，优先级/动作选取/回调）
- [✔] Monkey-patch MeshContext 导入 bug（l2d/__init__.py）
- [✔] requirements.txt（PySide6, live2d-py, requests, faster-whisper, sounddevice）

---

### v0.1.1 —— 菜单与交互优化
- [✔] FR-WS-002: 任务栏与角色右键菜单统一（共用同一份 QMenu）
- [✔] FR-WS-002: 菜单动态文字（显示/隐藏葵酱、想和/不和葵酱聊天）
- [✔] FR-WS-002: 角色大小选择（子菜单：小 0.75x / 中 1.0x / 大 1.25x，以窗口中心为锚点缩放）
- [✔] FR-WS-002: 角色大小切换时同步重算已有气泡尺寸与透明度（根据新宽度重新换行，避免截断）
- [✔] FR-CH-001: 聊天面板最大高度随父窗口比例变化（默认占父窗口高度 65%，避免挡住角色）
- [✔] FR-CH-001: 打字指示器显示/隐藏时同步更新消息透明度

---

### v0.1.2 —— 语音输入与输入框美化
- [✔] FR-CH-002: 输入框左侧添加语音转文字按钮（🎙 图标，适配面板宽度缩放）
- [✔] FR-CH-002: 长按按钮 300ms 开始录音（sounddevice InputStream 非阻塞录制），松开结束
- [✔] FR-CH-002: 录音时清空输入框，placeholder 变为 "🎙 正在聆听... 松开按钮结束录音"
- [✔] FR-CH-002: 录音时禁用键盘输入，避免语音与键盘输入冲突
- [✔] FR-CH-002: `grabMouse()` 捕获鼠标，移出窗口松开也能正常停止录音
- [✔] FR-CH-002: 15 秒自动停止后备（防止 grabMouse 失效等极端情况）
- [✔] FR-CH-002: 录音时长过短（<300ms）或单击时，显示葵酱提示气泡
- [✔] FR-CH-002: faster-whisper tiny 模型本地转录，临时 WAV 自动清理
- [✔] FR-CH-002: 转录结果直接填入输入框（覆盖式，不清空已有内容，因为录音前已清空）
- [✔] FR-CH-003: 首次使用 STT 时检测本地模型，无模型则弹出下载对话框（确认+进度条+取消）
- [✔] FR-CH-003: 下载支持取消（terminate 线程并清空已下载内容）
- [✔] FR-CH-003: 下载失败友好提示（网络超时、连接失败等）
- [✔] FR-CH-002: 输入框圆角 10px，focus 状态 2px 高亮边框 + 外发光
- [✔] FR-CH-002: 输入框 galgame 风格（暖白底 rgba(255,250,245) + 珊瑚粉边框 + #4A3F3A 字体）
- [✔] 安装依赖：faster-whisper、sounddevice

---

### v0.2 —— 接入真实 AI
- [ ] FR-AI-001: 实现真实 HTTP POST（requests，30s 超时）
- [ ] FR-AI-001: 解析 choices[0].message.content
- [ ] FR-AI-001: 在 `_do_reply` 中调用 provider.chat() 并显示真实回复
- [ ] FR-CH-004: 对话历史内存级管理（最近 20 条上下文传入 history 参数）
- [ ] FR-AI-001: API 超时/断网容错：超时提示「葵酱好像走神了...」
- [ ] FR-AI-001: `_offline_mode` 开关：配置有效时自动切换为在线模式

### v0.3 —— 语音输出（TTS）+ 口型同步
- [ ] FR-VO-002: edge-tts 集成，中文女声合成
- [ ] FR-VO-002: 音频播放 + 临时文件自动清理
- [ ] FR-VO-002: TTS 开关（设置中可关闭）
- [ ] FR-LE-006: 口型同步：音频 RMS 音量 → ParamMouthOpenY
- [ ] FR-LE-006: smooth_factor = 0.3，音频结束后缓降到 0
- [ ] FR-LE-005: 状态机扩展 TALKING 状态
- [ ] 安装依赖：edge-tts
- [ ] voice/base_tts.py + voice/edge_tts_provider.py
- [ ] voice/audio_player.py：非阻塞播放 + 实时音量回调

### v0.4 —— 情感分析与状态机增强
- [ ] FR-AI-003: 简易情感分析（关键词匹配 positive/neutral/negative）
- [ ] FR-AI-003: 情感驱动状态机 Happy / Sad 状态
- [ ] FR-AI-003: AI 回复后自动触发对应表情动作

### v0.5 —— 设置窗口与配置持久化
- [ ] FR-ST-001: 设置窗口（QTabWidget：通用 / AI / 语音 / 显示）
- [ ] FR-ST-002: 配置持久化（~/.aoi-daemon/config.yaml）
- [ ] FR-ST-002: Pydantic Settings 类型校验
- [ ] FR-ST-001: 通用页：开机自启、透明度滑条、置顶开关、模型路径
- [ ] FR-ST-001: AI 页：API Key（密码框）、Instance ID、Base URL
- [ ] FR-ST-001: 语音页：TTS 开关、音色下拉、STT 开关

### v0.6 —— 聊天历史持久化与打包
- [ ] FR-CH-004: 聊天历史 SQLite 持久化（~/.aoi-daemon/history.db，最近 50 条）
- [ ] FR-ST-001: 开机自启（Windows 注册表/启动文件夹、Mac launchd）
- [ ] PyInstaller 打包（Windows .exe）
- [ ] Py2app 打包（macOS .app）
- [ ] README.md（项目介绍、安装、配置、模型版权说明）
- [ ] 打包时排除 resources/model/，README 注明需用户自行放置模型

---

## 技术债务

- [✔] live2d-py Core 库需手动配置（lib/Core.dll、libCore.dylib）
- [✔] QGraphicsOpacityEffect + border-radius 不兼容 → 改用 QPainter 自绘
- [✔] QBoxLayout 空间不足时压缩 spacing → 改用禁用自动布局 + 手动计算 y
- [✔] widget 首次显示前 height() 返回 0 → 使用 _layout_height 属性存储
- [✔] faster-whisper 首次下载模型无进度提示 → 已实现 ModelDownloadDialog 带进度条
- [ ] 透明窗口鼠标事件兼容性（Windows/macOS 差异待验证）
- [ ] macOS 麦克风/辅助功能权限处理（STT 阶段需要）
- [ ] edge-tts 异步生成器在同步代码中的封装方式待统一
