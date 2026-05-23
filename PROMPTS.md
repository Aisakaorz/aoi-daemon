# AoiDaemon Prompt 大全

> 所有 Prompt 直接复制粘贴到 Kimi Code 即可使用。

---

## 【从零开发】生成 v0.1 MVP

```
请读取当前目录下的 PRD.md，按 v0.1 要求生成完整可运行代码。

当前环境：
- 空项目，已创建目录结构
- lib/ 目录已放置对应平台的 Live2D Core 库（Windows: Core.dll / macOS: libCore.dylib）
- resources/model/ 下已放置 Live2D 模型文件（haru02.model.json 为入口）
- 使用 Python 3.10+ 虚拟环境
- 目标平台：Windows + macOS

要求：
1. 按 PRD 第 3 节文件结构生成所有目录和 __init__.py
2. 先实现 core/app.py、ui/main_window.py、ui/live2d_canvas.py，确保 main.py 可直接运行
3. 启动后显示 400×600 透明置顶窗口，加载 Live2D 模型
4. 实现视线跟踪（ParamEyeBallX/Y）和呼吸动画（ParamBreath）
5. 实现点击反馈（Head→flickHead / Body→tapBody），附带 snd/ 音效播放
6. 实现 core/state_machine.py（Idle/Greeting/Thinking/TapHead/TapBody，优先级管理）
7. 实现 ui/chat_panel.py（气泡组件、输入框、打字指示器）
8. 实现 ai/kimi_claw_provider.py（API 占位符，直接 echo 用户输入）
9. 实现系统托盘 + 右键菜单（任务栏与角色右键共用同一份菜单：显示/隐藏葵酱、聊天开关、置顶、角色大小、关于、退出）
10. 所有代码中文注释，异常处理完善（特别是 live2d 初始化和模型加载失败）
11. 生成 requirements.txt（PySide6, live2d-py, requests）
12. 不要生成 v0.2 及以后的代码

特别注意：
- 模型是 Cubism 2.x 格式，使用 import live2d.v2 as live2d
- 模型入口文件路径：resources/model/live2d-widget-model-haru/haru02.model.json
- 可用动作文件在 mtn/ 目录下：idle_00.mtn~idle_02.mtn、flickHead_00.mtn、tapBody_00.mtn~tapBody_09.mtn、pinchIn_00.mtn、pinchOut_00.mtn、shake_00.mtn
- 点击音效在 snd/ 目录下，可选播放
- 根据 sys.platform 自动选择 Live2D Core 库路径（lib/Core.dll 或 lib/libCore.dylib）
- 默认使用 haru 模型作为演示角色（葵酱），模型入口 haru02.model.json
- glewInit() 必须在 QOpenGLWidget.initializeGL() 中调用
- 透明窗口需处理鼠标事件穿透问题（参考 PRD 第 6 节踩坑提示）
- 聊天面板使用手动布局（禁用 QVBoxLayout 自动布局），spacing 固定 4px
- widget 首次显示前 height() 可能返回 0，所有布局计算必须使用 _layout_height 属性存储
- FFmpeg stderr 需在 main.py 开头用 os.dup2 重定向到 devnull，同时恢复 sys.stderr

完成后请列出所有生成的文件，并告诉我运行前需要执行的命令。
```

---

## 【版本迭代】开发 v0.2 ~ v0.x

```
请读取当前目录下的 TASK.md 和 PRD.md。

v0.1 已完成，代码可运行。现在继续实现 [v0.2 / v0.3 / v0.4 / v0.5 / v0.6]，具体任务见 TASK.md 对应章节。

要求：
1. 严格按 TASK.md 中的任务清单逐项实现
2. 不要实现该版本以外的功能
3. 不破坏已有功能（窗口/Live2D/聊天/托盘/音效）
4. 保持代码风格一致（中文注释、异常 try/except、logger 记录）
5. 更新 requirements.txt（如有新依赖）
6. 完成后更新 TASK.md，将该版本任务标记为 [✔]

约束：
- 异步逻辑（网络/TTS/STT）使用 QThread，不阻塞主线程
- 新模块放到对应目录下，别忘了 __init__.py
- 参考 PRD 第 6 节踩坑提示处理平台差异
```

---

## 【添加新功能】规范流程

### 步骤 1：你自己在 TASK.md 里写

在 TASK.md 对应版本的合适位置添加：
```markdown
- [ ] 任务名称
  - 输入: [触发条件]
  - 输出: [预期结果]
  - 边界: [不改动哪些模块]
  - 验收: [怎么算完成]
```

### 步骤 2：复制下面这段话发给 Kimi Code

```
请读取当前目录下的 TASK.md。

我新增了任务：[复制你刚写的任务描述]

请实现它，要求：
1. [具体实现要求 1]
2. [具体实现要求 2]
3. 不要改动 [已有模块列表]
4. 保持代码风格和异常处理一致
5. 完成后更新 TASK.md 中该任务为 [✔]
```

---

## 【修复 Bug】

```
请读取 TASK.md 和相关代码文件。

[模块名] 出现 Bug：
- 现象: [描述]
- 预期: [描述]
- 实际: [描述]
- 相关文件: [路径]
- 错误日志:
```
[贴出 traceback]
```

请修复，并确保不破坏其他模块。修复后更新 TASK.md 中的技术债务项。
```

---

## 【重构 / 优化】

```
请读取 TASK.md 和当前所有 .py 文件。

我计划重构 [模块名]，原因：[性能 / 冗余 / 扩展性]

目标：
- [ ] 目标 1
- [ ] 目标 2

约束：
- 接口不变（输入输出参数保持一致）
- 现有调用方无需改动
- 完成后更新 TASK.md
```

---

## 【长期维护】让 Kimi Code 自己规划

```
请读取 TASK.md 和 PRD.md。

我想实现：[描述你的想法]

请帮我在 TASK.md 中规划任务（写明输入/输出/边界/验收，归入对应版本），然后直接实现。
```

Kimi Code 会自动：
1. 在 TASK.md 对应版本下添加任务
2. 分析依赖关系
3. 生成代码
4. 更新 TASK.md 状态

---

*文档结束*
