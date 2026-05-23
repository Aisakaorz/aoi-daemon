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
- [✔] 项目目录结构（core/ / ui/ / l2d/ / ai/ / utils/ 目录 + __init__.py）
- [✔] 统一日志（utils/logger.py，级别/格式/文件输出到 stdout）
- [✔] FR-LE-005: 状态机（core/state_machine.py，优先级/动作选取/回调）
- [✔] Monkey-patch MeshContext 导入 bug（l2d/__init__.py）
- [✔] requirements.txt（PySide6, live2d-py, requests）

---

### v0.2 —— 接入真实 AI
- [ ] FR-AI-001: 实现真实 HTTP POST（requests，30s 超时）
- [ ] FR-AI-001: 解析 choices[0].message.content
- [ ] FR-AI-001: 在 `_do_reply` 中调用 provider.chat() 并显示真实回复
- [ ] FR-CH-003: 对话历史内存级管理（最近 20 条上下文传入 history 参数）
- [ ] FR-AI-001: API 超时/断网容错：超时提示「葵酱好像走神了...」
- [ ] FR-AI-001: `_offline_mode` 开关：配置有效时自动切换为在线模式

### v0.3 —— 语音输出（TTS）
- [ ] FR-VO-001: edge-tts 集成，中文女声合成
- [ ] FR-VO-001: 音频播放 + 临时文件自动清理
- [ ] FR-VO-001: TTS 开关（设置中可关闭）
- [ ] FR-LE-006: 口型同步：音频 RMS 音量 → ParamMouthOpenY
- [ ] FR-LE-006: smooth_factor = 0.3，音频结束后缓降到 0
- [ ] FR-LE-005: 状态机扩展 TALKING 状态
- [ ] 安装依赖：edge-tts、sounddevice、numpy
- [ ] voice/base_tts.py + voice/edge_tts_provider.py
- [ ] voice/audio_player.py：非阻塞播放 + 实时音量回调

### v0.4 —— 语音输入（STT）
- [ ] FR-VO-002: faster-whisper base 模型本地推理
- [ ] FR-VO-002: 长按空格键录音，松开结束
- [ ] FR-VO-002: 录音波形动画
- [ ] FR-VO-002: 录音参数：16kHz, 16bit, 单声道, 最大 30 秒
- [ ] FR-VO-002: 转录结果自动填入输入框并触发发送
- [ ] FR-VO-002: STT 开关（默认关闭）
- [ ] FR-LE-005: 状态机扩展 LISTENING 状态
- [ ] 安装依赖：faster-whisper

### v0.5 —— 设置与配置
- [ ] FR-ST-001: 设置窗口（QTabWidget：通用 / AI / 语音 / 显示）
- [ ] FR-ST-002: 配置持久化（~/.aoi-daemon/config.yaml）
- [ ] FR-ST-002: Pydantic Settings 类型校验
- [ ] FR-ST-001: 通用页：开机自启、透明度滑条、置顶开关、模型路径
- [ ] FR-ST-001: AI 页：API Key（密码框）、Instance ID、Base URL
- [ ] FR-ST-001: 语音页：TTS 开关、音色下拉、STT 开关
- [ ] FR-AI-003: 情感分析（关键词匹配 positive/neutral/negative）
- [ ] FR-AI-003: 情感驱动状态机 Happy / Sad 状态

### v0.6 —— 完善与打包
- [ ] FR-CH-003: 聊天历史 SQLite 持久化（~/.aoi-daemon/history.db，最近 50 条）
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
- [ ] 透明窗口鼠标事件兼容性（Windows/macOS 差异待验证）
- [ ] macOS 麦克风/辅助功能权限处理（STT 阶段需要）
- [ ] edge-tts 异步生成器在同步代码中的封装方式待统一
- [ ] faster-whisper 首次下载模型无进度提示
