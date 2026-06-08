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
- 位置：默认屏幕右下角，启动时角色底部自动吸附任务栏顶部
- 拖拽：按住角色任意区域可拖拽移动，释放后若角色底部靠近任务栏则自动吸附
- 任务栏吸附：以角色底部为基准（约占窗口高度 95.5%），阈值 = 任务栏高度的一半；支持菜单开关，默认开启
- 多屏幕兼容：使用 `QApplication.screenAt()` 获取窗口所在屏幕的任务栏位置

**FR-WS-002 右键菜单（与托盘菜单一致）**
- 显示/隐藏葵酱（动态文字，根据窗口可见性自动切换）
- 聊天开关（动态文字：想和葵酱聊天 / 不和葵酱聊天）
- 窗口置顶（checkable，默认开启）
- 任务栏吸附（checkable，默认开启；关闭后拖拽不再自动吸附）
- 角色大小（子菜单：小 0.75x / 中 1.0x / 大 1.25x）
- 语音转文字模型（子菜单：显示模型名称，已下载显示勾选，未下载点击弹窗）
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
- 全局视线跟踪：即使鼠标离开窗口，角色也会持续看向鼠标方向（QCursor 全局定时器，16ms 刷新）
- 头部跟随：ParamAngleX / ParamAngleY / ParamAngleZ（轻微幅度）
- 呼吸动画：正弦波驱动 ParamBreath，周期 3~4 秒

**FR-LE-004 点击反馈 (Hit Area)**
- Head -> flickHead_00.mtn（摸头反应）
- Body -> tapBody_00.mtn ~ tapBody_09.mtn（身体互动）
- 可选播放 snd/ 目录下对应音效

**FR-LE-005 动作状态机**

| 状态 | 可用动作文件 | 触发条件 |
|------|-------------|---------|
| Idle | idle_00~02 / shake_00 / pinchIn_00 / pinchOut_00 / tapBody_00~02 | 空闲时 10~15 秒随机轮播 |
| Greeting | shake_00 | 启动时播放一次 |
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
- 面板底部与角色底部对齐（约占窗口高度 95.5%），并向下偏移 3px 遮住一点脚部，避免遮挡角色腿部

**FR-CH-002 文本输入与语音输入**
- Enter 发送（当前使用单行 QLineEdit，Shift+Enter 换行待 v0.5 设置窗口中升级为 QTextEdit 后支持）
- placeholder：跟葵酱说点什么吧~
- 发送后清空输入框，触发 Thinking 状态
- **语音按钮**：输入框左侧 🎙 按钮，长按 300ms 开始录音，松开结束
  - 录音时清空输入框，placeholder 变为 "🎙 正在聆听... 松开按钮结束录音"
  - 输入框禁用键盘输入（避免语音与键盘冲突）
  - 录音时语音按钮实时显示音量可视化（从下到上填充红色音量条，RMS 归一化）
  - 录音结果直接填入输入框，用户自行回车发送
  - 单击或长按不够时，显示提示气泡（葵酱的提醒）
  - STT 初始化失败静默降级（模型缺失/依赖异常时语音按钮失效，应用不崩溃）
- **输入框 galgame 风格**：
  - 暖白底 rgba(255,250,245) + 珊瑚粉边框 rgba(255,200,195)
  - focus 时 2px 高亮边框 + 外发光
  - 圆角 10px，字体 #4A3F3A
- 语音按钮与输入框随面板宽度同步缩放

**FR-CH-003 模型下载与进度**
- 菜单栏「语音转文字模型」中选择未下载的模型时直接开始下载
- 开始下载时弹出气泡提示「开始下载语音模型啦，请稍候~」
- 下载进度常驻在输入框位置：隐藏输入框，显示 ⏳ 图标 + 已下载/总大小/当前速度
- 下载进度使用渐变背景（从左到右珊瑚粉渐变填充，与输入框 focus 边框风格统一）
- 点击 ⏳ 图标取消下载，悬停时图标变为 ❌，点击触发取消
- 取消采用协作式方案（HFProgressBar._cancelled 标志位 + RuntimeError 异常），不使用 terminate
- 后台下载期间，托盘 tooltip 实时显示进度（百分比、速度）
- 下载完成/失败/取消均通过气泡消息 + 托盘通知反馈
- 下载完成自动设为当前模型（如果用户此前未选择过任何模型）
- 菜单打开时自动检测模型完整性（模型文件被删除后自动取消勾选状态）
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
- faster-whisper tiny 模型本地推理（~75MB，存放于 resources/whisper/tiny/）
- 长按语音按钮 300ms 开始录音，松开结束
- sounddevice InputStream 非阻塞录制，16kHz, 16bit, 单声道
- 录音保存为固定路径临时 WAV，程序退出时统一清理
- 转录结果填入输入框
- `grabMouse()` 捕获鼠标，移出窗口松开也能正常停止录音
- 15 秒自动停止后备（防止 grabMouse 失效等极端情况）
- 模型未下载时，长按语音按钮不弹窗，改为气泡提示「请去菜单栏下载语音转文字模型」
- 模型下载中时，长按语音按钮气泡提示「当前模型下载中，请稍候再试」

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
│   ├── chat_panel.py       # 聊天气泡面板 + 输入框 + 语音按钮 + 下载进度
│   ├── splash_screen.py    # 启动加载画面（模型加载期间显示，带进度反馈）
│   ├── tray_icon.py        # 系统托盘
│   └── __init__.py
├── l2d/                    # Live2D 业务封装（避免与第三方 live2d-py 包名冲突）
│   ├── __init__.py         # Monkey-patch MeshContext 导入 bug
│   └── model_wrapper.py    # LAppModel 封装 + 动作播放管理
├── ai/
│   ├── __init__.py
│   ├── base_provider.py    # AI Provider 抽象基类
│   └── kimi_claw_provider.py
├── voice/
│   ├── __init__.py
│   ├── model_manager.py    # 模型注册表 + 下载管理器（后台下载、进度跟踪）
│   └── stt_provider.py     # STT 封装：AudioRecorder + faster-whisper
├── utils/
│   ├── __init__.py
│   ├── config_manager.py   # JSON 配置持久化（窗口位置、角色大小、开关状态）
│   └── logger.py
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
- faster-whisper tiny 本地语音转文字，录音保存为固定路径临时 WAV
- 输入框 galgame 风格美化（暖白底+珊瑚粉边框+focus 高亮外发光）
- 首次使用 STT 时检测本地模型，无模型则弹出下载对话框（带进度条）
- `grabMouse()` 确保移出窗口松开也能正常停止录音

### v0.1.3 —— 任务栏吸附与聊天面板位置优化
- 拖拽释放时角色底部靠近任务栏自动吸附（阈值 = 任务栏高度的一半，动态适应 DPI）
- 以角色底部为基准吸附（约占窗口高度 95.5%，经视觉微调），吸附后角色底部贴住任务栏顶部
- 菜单栏添加"任务栏吸附"选项（checkable，默认开启；关闭后不再自动吸附）
- 开启任务栏吸附时若窗口已在阈值内立即吸附
- 应用启动时默认吸附到任务栏顶部
- 聊天面板底部与角色底部对齐，向下偏移 3px 遮住一点脚部
- 多屏幕兼容（`QApplication.screenAt` 获取当前屏幕）

### v0.1.4 —— 空闲时自动播放动作
- 角色空闲时每 10~15 秒自动随机播放动作，避免单调
- 动作列表扩充到 9 个：idle 微表情 + shake 摇头 + pinch_in/out 捏脸 + tap_body 身体互动
- Live2DCanvas 渲染循环中驱动 state_machine.update(delta_time)
- 空闲动作使用 NORMAL 优先级，确保能替换当前循环的 idle 动作
- 动作播放期间（_busy_timer）阻止新的随机动作触发，避免重叠
- 单击触发 TAP 时重置 idle 计时器，单击优先级高于随机播放
- 自动播放不触发音效

### v0.1.5 —— 语音模型下载入口重构
- 长按语音按钮时：模型未下载不再弹窗，改为气泡提示「请去菜单栏下载语音转文字模型」
- 菜单栏「角色大小」下方新增「语音转文字模型」子菜单（显示模型名称，如 Whisper Tiny）
- 已下载模型显示勾选，单击直接切换；未下载模型单击弹出下载对话框
- 下载对话框显示模型名称和大小，保留「下载」和「取消」按钮
- 点击「下载」后按钮变为可点击的「后台下载」，进度条附近显示已下载/总大小/速度
- 点击「后台下载」关闭弹窗，托盘 tooltip 实时显示下载进度
- 下载完成/失败时托盘气泡通知
- 后台下载期间长按语音按钮，气泡提示「当前模型下载中，请稍候再试」

### v0.1.7 —— 启动加载画面 + 模型缺失优雅降级
- 启动画面（SplashScreen）：Live2D 模型加载期间显示，避免用户面对空白窗口
  - 珊瑚粉主题配色，圆角窗口（QBitmap + QPainterPath + setMask）
  - 显示应用图标 + 「葵之使魔」标题 + 加载文案 + 确定进度条（0~100）
  - Live2DCanvas 通过 `loading_progress` 信号分阶段反馈真实进度
  - 进度条 ease-out 平滑插值动画（QTimer 60fps，step = max(1, |diff| * 0.2)）
  - 下载进度条同步增加平滑动画，与启动画面共用同一套插值逻辑
  - 模型加载完成后 `model_ready` 信号自动关闭启动画面
- 模型缺失优雅降级：
  - main.py 启动前置检查 `resources/model/**/*.model.json`
  - 缺失时弹出 QMessageBox（标题「资源文件缺失」），提示按 README「配置 Live2D 模型」放置文件
  - 点击确定后 `sys.exit(0)` 优雅退出，不进入 Live2D 渲染

### v0.1.8 —— 配置持久化（config.json）
- 新增 `utils/config_manager.py`：简单的 JSON 配置管理器
  - 接口：load() / save() / get(key, default) / set(key, value)
  - 配置文件路径：项目根目录 `config.json`（已加入 .gitignore）
  - 变更时自动 save，无需手动调用
- 持久化配置项：
  - `window_geometry`: x, y, width, height（窗口移动/resize 时 500ms 防抖保存）
  - `character_size`: "small" | "medium" | "large"（菜单切换时保存）
  - `always_on_top`: true | false（菜单切换时保存）
  - `taskbar_snap`: true | false（菜单切换时保存）
  - `chat_enabled`: true | false（菜单切换时保存）
- `main.py` 启动入口调用 `cfg.load()`，确保配置在程序启动时被加载到内存
- `main_window.py` 启动时自动 `_apply_config()` 恢复所有设置
  - 恢复顺序：角色大小 → 置顶状态 → 任务栏吸附 → 聊天面板 → 窗口位置
  - `showEvent()` 中窗口首次显示后再次 `move()` 确认位置，覆盖窗口管理器可能的默认定位
  - 无配置时 fallback 到默认行为（右下角、中号、置顶开启、吸附开启、聊天关闭）

### v0.1.9 —— 日志分级支持
- 重写 `utils/logger.py`：
  - 控制台固定输出 DEBUG 及以上级别（运行界面显示全部日志）
  - WARNING/ERROR 级别日志通过独立 `FileHandler` 写入 `logs/aoi.log`
- `.gitignore` 添加 `logs/` 目录，防止日志文件被提交
- 梳理现有日志调用：
  - 高频调试信息（如 `_on_transcribe_done` 调用轨迹）降级为 DEBUG
  - 用户操作记录（切换角色大小、点击互动、语音录制）保持 INFO
  - 异常和错误保持 ERROR/WARNING

### v0.1.12 —— UI 微调与日志简化
- `ui/chat_panel.py`：上传按钮右间距与语音按钮左间距对齐（8px）
- `ui/chat_panel.py`：统一上传按钮与语音按钮的样式（背景色、hover 透明度，移除上传按钮多余的 `font-size`）
- `ui/main_window.py`：移除托盘菜单「日志级别」子菜单
- `utils/logger.py`：简化日志级别管理
  - 控制台默认 DEBUG，不再从环境变量或配置读取
  - 移除 `log_level` 配置持久化
  - 日志文件从 `aoi-error.log` 更名为 `aoi.log`

### v0.1.10 —— 文件上传 + 斜杠指令 + 气泡交互优化

**文件上传系统**
- 新增 `core/file_manager.py`：用户上传文件管理器
  - 文件暂存到 `temp/uploads/` 目录
  - `taiko_scores_*.json` 文件自动替换旧文件
  - 应用退出时自动清空临时目录
- `ui/chat_panel.py`：输入框右侧添加 📎 上传按钮
- `ui/main_window.py`：连接 `file_uploaded` 信号，收到文件后显示系统提示

**斜杠指令本地路由**
- 新增 `ai/command_router.py`：本地指令路由器，不经过 LLM
  - 识别 `/keyword args` 格式指令
  - 当前支持 `/成绩 <歌曲名>`：读取太鼓成绩 JSON，模糊匹配 song_name / song_name_jp / subtitle
  - 非指令消息返回 None，走原有 AI 聊天流程
- `ui/main_window.py`：`_on_user_message` 优先尝试指令路由，命中则本地即时回复

**太鼓成绩查询格式化（多次迭代）**
- 歌曲信息：第一行 `🎵 {song_name_jp}`，第二行 `🎵 （{song_name}）`
- 难度只看 level_4（魔王/表）和 level_5（魔王/裏），有两者时分别显示
- 评价等级映射：`1→无 2→白粋 3→铜粋 4→银粋 5→金雅 6→粉雅 7→紫雅 8→极`
- history 解析：`[游玩次数, 通关次数, 全连次数, 全良次数]`，大于 0 才显示
- 分隔线动态适配气泡宽度（超长分隔线 + BubbleWidget 字符级截断）
- 去除判定详情和玩家信息行

**消息气泡交互优化**
- `BubbleWidget` 文本渲染从 `QPainter` 自绘改为 `QLabel` 子控件
  - 支持鼠标拖拽选中和 `Ctrl+C` 复制
  - 用 `QPalette` 颜色 alpha + `paintEvent.setOpacity()` 同步控制透明度
  - 避免 `QGraphicsOpacityEffect` 在手动 `setGeometry()` 场景下的渲染异常
- 新增系统消息气泡（`add_system_message`）：文件上传提示移入消息列表
  - 粉色渐变背景、8pt 字体、圆角 6px、居中显示
  - 跟随消息列表正常滚动和淡出

**启动画面精简**
- 移除进度条（加载过快无视觉效果，且 processEvents/msleep 导致 OpenGL 卡住）
- 保留图标 + 标题 + 「葵酱正在梳妆打扮，请稍候~」文案

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

1. **MeshContext 导入 bug**：需在 `l2d/__init__.py` 中 monkey-patch `live2d.v2.core.alive2d_model` 的 MeshContext 导入。
2. **OpenGL 上下文**：glewInit() 必须在 QOpenGLWidget.initializeGL() 中调用，__init__ 中提前调用会崩溃。
3. **模型居中**：`Resize()` 会覆盖布局宽度为 2.0，导致模型左偏，需用 `SetOffset(0.45, 0.0)` 补偿。
4. **纹理参数**：加载贴图后必须设置 `GL_TEXTURE_WRAP_S/T = GL_CLAMP_TO_EDGE` 和 `GL_TEXTURE_MIN/MAG_FILTER = GL_NEAREST`，否则出现接缝线。
5. **FFmpeg stderr**：Qt 多媒体播放 MP3 时 C 库会写 stderr（fd 2）， bypass Python sys.stderr。需在 `main.py` 开头用 `os.dup2` 将 fd 2 重定向到 devnull，同时恢复 Python `sys.stderr` 绑定到原始 fd。
6. **QGraphicsOpacityEffect 不兼容**：Qt6 中 `QGraphicsOpacityEffect` + `border-radius` 会导致动画期间变方。解决方案：用 `QPainter.setOpacity()` 在 QWidget 上自绘圆角矩形和文本。
7. **QBoxLayout 压缩 spacing**：`QVBoxLayout` 空间不足时会优先压缩 `spacing` 导致气泡重叠。解决方案：保留 `QVBoxLayout` 作为容器（启用状态确保气泡可见），但用 `setGeometry` 手动覆盖每条消息的 y 坐标，并拦截 `LayoutRequest` 事件立即重布局。
8. **widget 首次显示前 height() 返回 0**：手动布局时 `w.height()` 在 widget 首次显示前可能返回 0。解决方案：创建 widget 时存储 `_layout_height` 属性，所有布局计算使用该属性值。
9. **faster-whisper 模型下载**：通过菜单栏「语音转文字模型」选择并下载，支持后台下载，托盘实时显示进度。也可手动放置到 `resources/whisper/tiny/`。
10. **grabMouse 与模态对话框冲突**：`_VoiceButton` 长按录音时调用 `grabMouse()`，若此时弹出模态下载对话框，需在弹窗前调用 `releaseMouse()` 或 `reset_style()` 释放捕获，否则对话框可能无法交互。
11. **角色底部比例需视觉微调**：Live2D 模型在窗口内的实际视觉底部无法通过代码精确计算（hit test 区域 ≠ 视觉边界），需运行后目视微调 `_CHARACTER_BOTTOM_RATIO`。haru 模型经实际微调后约为 0.955。
12. **任务栏高度差异**：不同屏幕/DPI 下任务栏高度不同（40px ~ 75px），吸附阈值应使用任务栏高度的一半动态计算，避免固定阈值在某些屏幕上过大或过小。
13. **顶部透明化区域动态增长**：固定 fade_zone = 150px 会导致面板较矮时过早淡出。解决方案：使用固定 threshold = max_available_h - _FADE_ZONE，fade_zone = min(total_msg_h - threshold, _FADE_ZONE)，从 0 逐渐增长到 150px。
14. **底部截断不要用 opacity**：用 `opacity = 0` 截断底部消息会导致气泡物理区域仍覆盖输入框（鼠标事件被拦截）。解决方案：使用 `QRegion` + `setMask()` 硬裁剪，同时配合 `raise_()` 确保输入框在气泡之上。
15. **输入框 z-order 管理**：新消息加入时 Qt 可能将其置于输入框之上。解决方案：在 `add_message()` 和 `show_typing_indicator()` 中调用 `self._input_frame.raise_()`。
16. **API Key 安全**：不要硬编码，使用环境变量或本地加密配置文件。开源前检查 .gitignore 排除 config.yaml 和 .env。
17. **Live2D 模型版权**：开源仓库不放完整模型。本项目演示使用的 haru 模型来源于 hexo-helper-live2d 项目，版权归属 Live2D Inc.。README 需注明模型文件需用户自行提供。
18. **macOS 权限**：首次运行可能需授予麦克风权限（STT）和辅助功能权限（开机自启）。
