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
- [✔] FR-CH-003: 转录结果直接填入输入框（覆盖式，不清空已有内容，因为录音前已清空）
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
- [✔] FR-LE-005: 非 IDLE 状态时（Thinking/Tap 等）不打断，保持当前动作，不触发随机动作
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
- [✔] Live2DCanvas.model_ready 信号：initializeGL 完成后通知 MainWindow 关闭启动画面
- [✔] 启动画面圆角窗口居中显示、无边框、置顶、珊瑚粉主题配色
- [✔] 启动画面精简：移除进度条（避免 initializeGL 中 processEvents/msleep 卡住）
  - [✔] 保留图标 + 标题 + 加载文案

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
- [✔] 修复 KeyError('song_detail')：JSON 中缺失该字段的条目安全跳过

---

### v0.1.13 —— 高危 bug 修复
- [✔] voice/stt_provider.py: WhisperModel 加载移入 TranscribeRunnable 工作线程（_load_model 加锁防并发重复加载），首次转录不再冻结 UI
- [✔] voice/stt_provider.py: AudioRecorder.stop() 的 PortAudio 异常兜底；新增 abort_recording() 供退出清理
- [✔] ai/command_router.py: /成绩 指令防御性读取（缺失字段 / None 值 / 非 dict 条目 / 非字符串歌名不再崩溃）
- [✔] voice/model_manager.py: _on_finished 先清理状态再 emit finished，修复极端时序下的并发下载竞态
- [✔] voice/model_manager.py: 新增 DownloadManager.shutdown() 协作式取消并等待下载线程结束（3s 超时兜底）
- [✔] ui/main_window.py: _on_quit 退出时 shutdown 下载线程 + 调用 ChatPanel.shutdown() 停止录音流
- [✔] ui/chat_panel.py: 新增 ChatPanel.shutdown() 清理录音相关定时器并中止录音
- [✔] ui/main_window.py: 关于弹窗文案移除 Kimi 字样

---

### v0.1.14 —— 精简（移除太鼓成绩查询）
- [✔] 删除 ai/command_router.py（/成绩 指令与太鼓成绩查询整体移除，功能已在其他软件实现）
- [✔] core/file_manager.py: 移除太鼓文件扫描/读取/自动替换逻辑，精简为通用上传暂存（保留上传存储与退出清理）
- [✔] core/file_manager.py: save_upload 前确保暂存目录存在（clear_all 清理后可再次上传）
- [✔] ui/main_window.py: 移除 CommandRouter 导入/初始化与消息指令路由分支，普通消息统一走占位回复；上传反馈改为通用系统提示
- [✔] ui/chat_panel.py: 文件选择对话框改为通用文案，不再限定 JSON 文件

---

### v0.1.15 —— 渲染画质优化（消除模型锯齿）
- [✔] ui/live2d_canvas.py: 纹理采样 NEAREST → LINEAR（CLAMP_TO_EDGE 保留，接缝线由 CLAMP 解决与采样方式无关），显著减轻模型像素锯齿
- [✔] ui/live2d_canvas.py: resizeGL 视口按 devicePixelRatio 换算物理像素，修复高 DPI 屏下渲染结果被拉伸放大导致的模糊/锯齿（实测 dpr=1.25 下绘制后视口 500x750，与 FBO 1:1 对齐，MSAA 生效）
- [✔] ui/live2d_canvas.py: model.Resize 同步传物理像素，保证库内部（如遮罩裁剪）恢复视口时与实际视口一致；新增首帧 GL 诊断日志（dpr/视口/MSAA 采样数，排查渲染问题时用）
- [✔] ui/live2d_canvas.py: 新增 2x 超采样渲染（SSAA_SCALE=2）：模型渲染到 2 倍物理分辨率离屏纹理后线性降采样，消除细微移动时的边缘闪烁；FBO 创建失败自动回退直接渲染，常量改为 1 可关闭
- [✔] ui/live2d_canvas.py: 降采样 quad 改用语着色器 + VAO 绘制（固定管线在核心上下文静默无效），并修复两个 GL 状态污染问题：绘制前显式切回纹理单元 0（live2d 遮罩采样后 active unit 停在 1）、强制关闭面剔除（live2d 遗留 GL_CULL_FACE + GL_CW，CCW quad 被整体剔除）；着色器失败回退固定管线
- [✔] ui/live2d_canvas.py: 处理 DevicePixelRatioChange 事件（跨屏拖动等 DPR 变化场景自动重绘并重建渲染目标），适配不同缩放比例与多显示器环境
- [✔] core/app.py: 新增 _setup_surface_format()，在 QApplication 创建前设置默认 OpenGL 格式（4x MSAA + Alpha8），平滑模型网格几何边缘

---

### v0.1.16 —— 修复非中档尺寸启动时聊天面板被截断
- [✔] ui/chat_panel.py: 修复 `_get_max_panel_height` 在窗口首次显示前按未激活布局的过期父高度（实测 30px）钳制面板高度，导致小/大尺寸恢复时面板被永久压成 19px、输入框截断；父高度异常（≤50px）时退回固定上限 _MAX_PANEL_HEIGHT
- [✔] ui/chat_panel.py: 新增公开方法 `refresh_panel_height()`（重算面板高度）
- [✔] ui/main_window.py: showEvent 首次显示（布局已激活）时调用 `refresh_panel_height()`，彻底消除初始化期的过期高度
- [✔] 三档尺寸（小/中/大）启动恢复路径实测：面板高度统一 48px，输入框完整显示，底部与角色底部对齐

---

### v0.1.17 —— 启动画面美化（galgame 风格加载卡片）+ 子进程化（动画全程流畅滚动）
**视觉设计**
- [✔] ui/splash_screen.py: 弃用 QBitmap 1bit 遮罩（圆角锯齿），改为透明背景 + 抗锯齿自绘圆角卡片
- [✔] ui/splash_screen.py: 奶白→浅珊瑚渐变底 + 珊瑚粉双边框（外框 + 顶部内高光线）+ 多层手绘柔影（弃用 QGraphicsDropShadowEffect：透明窗口上残留白色圆角幻影、且干扰子控件动画刷新）
- [✔] ui/splash_screen.py: 圆形白色徽章头像（64px 粉边徽章 + 48px 图标）
- [✔] ui/splash_screen.py: 标题玫瑰粉 + 2px 字距、新增 AOIDAEMON 字距小字幕；四角手绘星星与圆点装饰
- [✔] ui/splash_screen.py: 不定态滚动进度条（高饱和珊瑚渐变小条匀速向右循环滚动、带方向性拖尾，按墙钟时间定位，1.1s 单程）与静态状态文案
- [✔] ui/splash_screen.py: 最短展示时长 1.2s（request_close），剩余时间≤0 时直接淡出（避免 singleShot(0) 个别场景不触发）；新增 220ms 淡出动画；WA_DeleteOnClose 确保关闭后动画定时器销毁

**动画流畅化（子进程启动画面）**
- [✔] splash_child.py: 新增启动画面子进程——动画运行在子进程专属事件循环中，不被主进程的重型导入/窗口构建/模型加载阻塞，从显示到关闭全程流畅滚动；孤儿防护（父进程退出 → stdin 断开 → 自行退出）+ 主动退出兜底
- [✔] main.py: ~0.3s（无需 Qt）派生子进程，早于一切重型导入；加载完成经 stdin 管道发送 close；子进程启动失败自动回退进程内启动画面；退出时通知关闭 → 等待 → taskkill 进程树兜底
- [✔] main.py / splash_child.py: 解释器选型踩坑记录——不能用 pythonw（GUI 子系统关闭 stdio，stdin 管道协议失效）、不能用 sys._base_executable（脱离 venv 找不到 PySide6）、不能用 venv 的 pythonw 重定向器（派生双进程、管道写句柄泄漏、EOF 永不送达）；正确配方：sys.executable + CREATE_NO_WINDOW
- [✔] core/bootstrap.py: 新增轻量引导模块（平台环境变量 + 默认 OpenGL 表面格式），须在 QApplication 创建前调用，独立于重型依赖链
- [✔] core/app.py: AoiDaemonApp 改为接收外部创建的 QApplication 与启动画面（SplashScreen 或子进程代理，均实现 request_close）
- [✔] ui/main_window.py: 否决并回退"构建期 _pump_events 插帧"方案（稀疏插帧导致进度条断续跳跃）
- [✔] 端到端实测：子进程 297ms 内派发并独立显示；加载全程进度条滚动；close 指令后淡出退出、无孤儿残留

---

### v0.1.18 —— 启动画面 VTuber 化（直播间待机风格）
- [✔] ui/splash_screen.py: 漂浮粒子背景——爱心/星星/圆点缓慢上浮 + 首尾淡入淡出 + 透明度呼吸（QPainter 路径绘制，墙钟驱动）
- [✔] ui/splash_screen.py: 徽章头像待机浮动（sin 墙钟驱动 ±5px）+ LIVE 红标骑角（随头像一起浮动）
- [✔] ui/splash_screen.py: 「STARTING ♡」珊瑚粉缎带斜贴卡片左上角（旋转绘制、跨越边缘）
- [✔] ui/splash_screen.py: 状态文案改为气泡样式——圆角白泡 + 小尾巴 + OutBack 弹性弹入
- [✔] ui/splash_screen.py: 标题扫光（斜向高光带按墙钟时间掠过文字）
- [✔] ui/splash_screen.py: 进度条升级——糖针斜纹轨道 + 爱心车头骑滑块右端
- [✔] ui/splash_screen.py: 四角星闪烁脉冲（正弦呼吸，墙钟驱动）
- [✔] 细节修正：爱心车头放大为明显大于轨道（"大爱心拉动进度条"既视感），进度条区加高保证完整显示；LIVE 标移到容器层（徽章圆角样式表会裁剪子控件致骑角截断）并随头像同步浮动；背景粒子缩小、心形改四段贝塞尔曲线、环绕卡片边缘分布（两侧竖带 + 头像/气泡两侧区间，中间内容列保持干净）；新增父窗口 33ms 背景重绘定时器（此前粒子/星星只在首帧绘制、看似静止）；标题扫光改由父窗口 paintEvent 统一绘制——透明子控件自绘扫光会因重绘缓冲累积残影/Source 清空空洞化底层，同一表面直绘才是正确做法
- [✔] 最终抛光：心形路径竖向比例拉长（消除显扁）；扫光改柔边羽化——白色文字渲染进光带位图后经水平渐变 SourceIn 合成，光带两侧透明度渐变过渡，仅字形变色且无矩形边界；LIVE 标/徽章基础位置下移留足上浮余量（最高点不再被容器上缘截断）；最右侧背景心形内移减少贴边
- [✔] 真机截图验证：粒子/浮动/扫光/滚动全部正常动画；close 指令后淡出退出、无残留；主流程 proxy 通知链路正常

---

### v0.2 —— 打包分发
- [ ] PyInstaller 打包（Windows .exe）
- [ ] Py2app 打包（macOS .app）
- [ ] 打包时排除 resources/model/，README 注明需用户自行放置模型

---

### 已取消的方向（备忘，不再规划）
- 接入外部 AI 聊天 API（原 v0.2）：项目定位调整为纯本地桌宠，聊天保持占位回复
- TTS 语音输出 + 口型同步（原 v0.3）
- 情感分析 + 状态机 Happy/Sad 状态（原 v0.4）
- 设置窗口（原 v0.5）：右键菜单 + config.json 已覆盖全部配置项
- 聊天历史 SQLite 持久化 + 开机自启（原 v0.6 部分）：聊天为本地临时交互，无持久化需求
- 太鼓成绩查询与斜杠指令（v0.1.10 实现，v0.1.14 移除）：功能已在其他软件实现；文件上传保留为通用临时暂存

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
- [ ] macOS 麦克风权限处理（STT 阶段需要）
- [ ] 下载取消竞态：run() 开头无条件重置 HFProgressBar._cancelled，极端时序下取消可能被吞（v0.1.13 已修复并发下载竞态，此为剩余边界情况）
