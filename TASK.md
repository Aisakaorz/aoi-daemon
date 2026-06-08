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
- [✔] FR-LE-003: 全局视线跟踪（鼠标离开窗口后角色仍看向鼠标方向，QCursor 全局定时器驱动）
- [✔] FR-LE-003: 呼吸动画（ParamBreath / ParamBodyAngleX/Y/Z，正弦波驱动）
- [✔] FR-LE-004: 点击反馈（Head→flickHead / Body→tapBody，随机选择，附带 snd/ 音效）
- [✔] FR-LE-005: 动作状态机（Idle/Greeting/Thinking/TapHead/TapBody，优先级管理，Idle 5~8s 轮播）
- [✔] FR-LE-001: 模型居中补偿（SetOffset(0.45, 0.0)）
- [✔] FR-LE-002: 纹理参数（GL_CLAMP_TO_EDGE + GL_NEAREST）消除接缝线

#### 聊天系统
- [✔] FR-CH-001: 自定义气泡组件（QPainter 自绘圆角渐变背景 + 手动字符级换行 + 文本垂直居中）
- [✔] FR-CH-001: 用户消息右对齐蓝色气泡，AI 消息左对齐粉色气泡
- [✔] FR-CH-001: 顶部高度渐变淡出（消息超出面板后随高度平方曲线淡出，底部 mask 硬截断保留消息）
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
- [✔] FR-CH-002: 录音时语音按钮实时音量可视化（从下到上填充红色音量条）
- [✔] FR-CH-002: faster-whisper tiny 模型本地转录，临时 WAV 自动清理
- [✔] FR-CH-002: 转录结果直接填入输入框（覆盖式，不清空已有内容，因为录音前已清空）
- [✔] FR-CH-003: 首次使用 STT 时检测本地模型，无模型则提示去菜单栏下载
- [✔] FR-CH-003: 下载支持取消（协作式取消：HFProgressBar._cancelled 标志位 + RuntimeError 异常）
- [✔] FR-CH-003: 下载失败友好提示（网络超时、连接失败等）
- [✔] FR-CH-002: STT 初始化失败静默降级（捕获异常，语音按钮失效但不崩溃）
- [✔] FR-CH-002: 输入框圆角 10px，focus 状态 2px 高亮边框 + 外发光
- [✔] FR-CH-002: 输入框 galgame 风格（暖白底 rgba(255,250,245) + 珊瑚粉边框 + #4A3F3A 字体）
- [✔] 安装依赖：faster-whisper、sounddevice

---

### v0.1.3 —— 任务栏吸附与聊天面板位置优化
- [✔] FR-WS-001: 拖拽释放时角色底部靠近任务栏自动吸附（阈值 = 任务栏高度的一半，动态适应 DPI）
- [✔] FR-WS-001: 以角色底部为基准吸附（比例 0.955，经视觉微调），吸附后角色底部贴住任务栏顶部
- [✔] FR-WS-001: 角色底部远离任务栏时不吸附，允许拖到屏幕外
- [✔] FR-WS-001: 多屏幕兼容（使用 QApplication.screenAt 获取当前屏幕）
- [✔] FR-WS-001: 仅处理底部任务栏（通过 availableGeometry 检测）
- [✔] FR-WS-002: 菜单栏添加"任务栏吸附"选项（checkable，默认开启）
- [✔] FR-WS-002: 关闭任务栏吸附后拖拽不再自动吸附
- [✔] FR-WS-002: 开启任务栏吸附时若窗口已在阈值内立即吸附
- [✔] FR-WS-001: 启动时默认吸附到任务栏顶部
- [✔] FR-CH-001: 聊天面板底部与角色底部对齐（比例 0.955）
- [✔] FR-CH-001: 聊天面板向下偏移 3px 遮住一点脚部，避免遮挡角色腿部

---

### v0.1.4 —— 空闲时自动播放动作
- [✔] FR-LE-005: 角色空闲时每 10~15 秒自动随机播放动作
- [✔] FR-LE-005: 动作列表扩充到 9 个（idle_00/01/02 + shake_00 + pinch_in_00 + pinch_out_00 + tap_body_00/01/02）
- [✔] FR-LE-005: 自动播放动作不触发音效（仅动作切换，无声音）
- [✔] FR-LE-005: Live2DCanvas 渲染循环中调用 state_machine.update(delta_time)
- [✔] FR-LE-005: 空闲动作使用 NORMAL 优先级，确保能替换当前循环的 MotionPriority.IDLE 动作
- [✔] FR-LE-005: _busy_timer 机制：播放期间阻止新的随机动作触发，避免重叠
- [✔] FR-LE-005: 单击触发 TAP 时重置 _idle_timer，单击优先级高于随机播放
- [✔] FR-LE-005: 非 IDLE 状态时（Thinking/Tap/Talking 等）不打断，保持当前动作，不触发随机动作
- [✔] FR-LE-005: Live2DCanvas 渲染循环中调用 state_machine.update(delta_time)
- [✔] FR-LE-005: 状态机 update() 中每 5~8 秒随机触发 _notify(IDLE)，经优先级映射后走 MotionPriority.IDLE

---

### v0.1.5 —— 语音模型下载入口重构
- [✔] FR-CH-002: 长按语音按钮且模型未下载时，不弹窗，改为气泡提示「请去菜单栏下载语音转文字模型」
- [✔] FR-CH-002: 长按语音按钮且模型下载中时，气泡提示「当前模型下载中，请稍候再试」
- [✔] FR-WS-002: 菜单栏「角色大小」下方新增「语音转文字模型」子菜单
- [✔] FR-WS-002: 子菜单显示模型名称（如 Whisper Tiny），已下载显示勾选，单击直接切换
- [✔] FR-WS-002: 未下载模型单击直接开始下载，弹出气泡提示「开始下载语音模型啦」
- [✔] FR-CH-003: 下载进度常驻在输入框位置（替换输入框，显示 ⏳ 图标 + 进度详情）
- [✔] FR-CH-003: 输入框位置进度条实时显示已下载/总大小/当前速度
- [✔] FR-CH-003: 点击 ⏳ 图标取消下载，悬停显示 ❌
- [✔] FR-CH-003: 下载完成/失败/取消均通过气泡消息 + 托盘通知反馈
- [✔] FR-CH-003: 下载完成自动设为当前模型（如果之前无已选模型）
- [✔] FR-WS-002: 菜单打开时自动检测模型完整性（模型文件被删除后自动取消勾选）
- [✔] FR-WS-003: 后台下载期间托盘 tooltip 实时显示进度（百分比、速度）
- [✔] FR-WS-003: 下载完成/失败时托盘气泡通知
- [✔] voice/model_manager.py: 模型注册表 + DownloadManager（全局单例，支持后台下载和取消）
- [✔] FR-CH-001: 手动滚轮滚动浏览历史消息（wheelEvent 调整 _scroll_offset）
- [✔] FR-CH-001: 跳到底部按钮（▼，24×20，滚动到上方历史时显示，点击重置 scroll_offset）
- [✔] FR-CH-001: 跳到底部按钮添加描边边框（珊瑚粉 1.5px，与输入框 focus 边框一致）
- [✔] FR-CH-001: LayoutRequest 拦截（event() 覆盖，防止 Qt 自动压缩 spacing）
- [✔] FR-CH-001: 输入框 z-order 保证（add_message / show_typing_indicator 中调用 raise_()）
- [✔] FR-CH-001: 顶部透明化规则重构（动态 fade_zone：从 0 增长到 150px，基于 max_available_h - _FADE_ZONE 的固定 threshold）
- [✔] FR-CH-001: 底部 mask 硬截断（clip_y = panel_height - input_height + 5px，不再用 opacity 截断）
- [✔] FR-CH-001: 滚动边界扩展（max_offset = total_h，最旧消息可完全滚入视图）
- [✔] FR-CH-001: 滚轮方向修复（delta > 0 增加 offset 查看旧历史）
- [✔] FR-CH-001: 聊天面板打开时自动聚焦输入框（showEvent 中调用 setFocus）
- [✔] FR-CH-003: 下载进度渐变背景（从左到右珊瑚粉渐变填充进度条，与输入框 focus 边框风格统一）

---

### v0.1.7 —— 模型库缺失时的优雅降级 + 启动加载画面
- [✔] 启动前置检查：resources/model/ 下是否存在 .model.json 文件
- [✔] 缺失时弹出 QMessageBox（标题「资源文件缺失」，提示按 README 配置）
- [✔] 点击确定后优雅退出（return 0），不进入 Live2D 渲染
- [✔] 保持代码结构整洁（_has_model_files / _show_missing_model_dialog 两个独立函数）
- [✔] 延迟导入 Qt，确保 stderr 重定向等环境准备已就绪
- [✔] 启动画面（SplashScreen）：Live2D 模型加载期间显示，避免空白窗口
- [✔] 启动画面包含应用图标 + 标题 + 加载文案 + 确定进度条（0~100，分阶段反馈真实加载进度）
- [✔] Live2DCanvas.model_ready 信号：initializeGL 完成后通知 MainWindow 关闭启动画面
- [✔] 启动画面圆角窗口居中显示、无边框、置顶、珊瑚粉主题配色
- [✔] 进度条 ease-out 平滑动画（set_progress 设目标值，QTimer 60fps 插值，step = max(1, |diff| * 0.2)）
- [✔] 下载进度条同步增加平滑动画（_animate_download_progress，与启动画面共用同一套 ease-out 插值逻辑）

---

### v0.1.8 —— 配置持久化（config.json）
- [✔] utils/config_manager.py: JSON 配置管理器（load/save/get/set，变更时自动 save）
- [✔] 配置文件路径：项目根目录 config.json（已加入 .gitignore）
- [✔] 持久化 window_geometry: x, y, width, height（moveEvent/resizeEvent 500ms 防抖保存）
- [✔] 持久化 character_size: small/medium/large（菜单切换时保存）
- [✔] 持久化 always_on_top: bool（菜单切换时保存）
- [✔] 持久化 taskbar_snap: bool（菜单切换时保存）
- [✔] 持久化 chat_enabled: bool（菜单切换时保存）
- [✔] main.py: 启动入口调用 cfg.load()，确保配置在程序启动时被加载到内存
- [✔] main_window.py _apply_config(): 启动时自动恢复所有配置
- [✔] 恢复顺序：角色大小 → 置顶 → 吸附 → 聊天 → 窗口位置（覆盖默认位置）
- [✔] showEvent(): 窗口首次显示后重新 move() 确认位置，覆盖窗口管理器可能的默认定位
- [✔] 无配置时 fallback 到默认行为

---

### v0.1.9 —— 日志分级支持
- [✔] utils/logger.py 重写：控制台固定 DEBUG 输出（显示全部日志）
- [✔] WARNING/ERROR 级别日志通过独立 FileHandler 写入 logs/aoi.log
- [✔] 高频调试信息降级为 DEBUG（如 _on_transcribe_done 调用轨迹）
- [✔] 用户操作记录保持 INFO，异常和错误保持 ERROR/WARNING
- [✔] .gitignore: 添加 logs/ 目录，防止日志文件被提交

### v0.1.12 —— UI 微调与日志简化
- [✔] ui/chat_panel.py: 上传按钮右间距与语音按钮左间距对齐（8px）
- [✔] ui/chat_panel.py: 统一上传按钮与语音按钮的样式（背景色、hover 透明度一致）
- [✔] ui/main_window.py: 移除托盘菜单「日志级别」子菜单
- [✔] utils/logger.py: 控制台默认 DEBUG，不再从环境变量或配置读取级别
- [✔] utils/logger.py: 移除 log_level 配置持久化
- [✔] utils/logger.py: 日志文件从 aoi-error.log 更名为 aoi.log
- [✔] main.py: 移除启动时恢复日志级别的代码

---

### v0.1.10 —— 文件上传 + 斜杠指令 + 气泡交互优化
- [✔] core/file_manager.py: 用户上传文件管理器（单例、临时存储、退出清空）
- [✔] ai/command_router.py: 斜杠指令本地路由（/成绩 <歌曲名>）
- [✔] 太鼓成绩 JSON 解析：模糊匹配歌曲名（song_name / song_name_jp / subtitle）
- [✔] 成绩回复格式化（多次迭代）：
  - [✔] 歌曲名双行显示：`🎵 {song_name_jp}` + `🎵 （{song_name}）`
  - [✔] 难度只看 level_4/5：魔王 / 魔王(表) / 魔王(裏)，显示星级
  - [✔] 评价等级映射：1→无 2→白粋 3→铜粋 4→银粋 5→金雅 6→粉雅 7→紫雅 8→极
  - [✔] history 解析：[游玩, 通关, 全连, 全良]，大于 0 才显示
  - [✔] 分隔线动态适配气泡宽度（超长分隔线 + _wrap_text 截断）
  - [✔] 去除判定详情（良/可/不可/准确率/最大连打）和玩家信息行
- [✔] ui/chat_panel.py: 输入框右侧 📎 上传按钮
- [✔] ui/main_window.py: 连接 file_uploaded 信号，上传后显示系统提示
- [✔] ui/main_window.py: _on_user_message 优先尝试指令路由，命中则本地即时回复
- [✔] 非指令消息返回 None，走原有 AI 聊天流程
- [✔] 应用退出时自动清空 temp/uploads/ 临时目录
- [✔] 消息气泡支持文本选择和复制：
  - [✔] BubbleWidget 从 QPainter 自绘改为 QLabel 子控件
  - [✔] 支持鼠标拖拽选中和 Ctrl+C 复制
  - [✔] 用 QPalette 颜色 alpha + paintEvent.setOpacity() 替代 QGraphicsOpacityEffect
  - [✔] 修复 QGraphicsOpacityEffect + 手动 setGeometry 导致的渲染异常（气泡消失/截断）
- [✔] 系统消息气泡（add_system_message）：文件上传提示移入消息列表
  - [✔] 粉色渐变背景、8pt 字体、圆角 6px、居中显示
  - [✔] 跟随消息列表正常滚动和淡出
- [✔] 启动画面精简：移除进度条（避免 initializeGL 中 processEvents/msleep 卡住）
  - [✔] 保留图标 + 标题 + 加载文案
- [✔] 修复 KeyError('song_detail')：JSON 中缺失该字段的条目安全跳过

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

- [✔] live2d-py v2 为纯 Python 实现，不需要 Core 动态库
- [✔] QGraphicsOpacityEffect + border-radius 不兼容 → 改用 QPainter 自绘
- [✔] QBoxLayout 空间不足时压缩 spacing → 改用禁用自动布局 + 手动计算 y
- [✔] widget 首次显示前 height() 返回 0 → 使用 _layout_height 属性存储
- [✔] faster-whisper 首次下载模型无进度提示 → 已实现输入框位置常驻下载进度条
- [✔] 底部消息截断：从 opacity 淡出改为 mask 硬裁剪（QRegion + setMask）
- [✔] 顶部 fade_zone 动态化：固定 threshold + 增长的 fade_zone，替代固定 150px 方案
- [ ] 透明窗口鼠标事件兼容性（Windows/macOS 差异待验证）
- [ ] macOS 麦克风/辅助功能权限处理（STT 阶段需要）
- [ ] edge-tts 异步生成器在同步代码中的封装方式待统一
