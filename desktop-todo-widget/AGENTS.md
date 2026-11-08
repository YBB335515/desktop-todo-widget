# AGENTS.md

本文件为 DSH / Codex 在此仓库中工作时提供指导。

## 常用命令

```bash
# 重新打包 exe（需先关闭正在运行的程序）
taskkill /f /im "桌面待办.exe" 2>/dev/null
rm -f dist/桌面待办.exe
python -m PyInstaller --noconfirm build/desktop_todo_widget.spec

# 每次重新打包前递增构建号
NEW_NO=$(printf "%02d" $((10#$(cat BUILD_NO) + 1)))
echo $NEW_NO > BUILD_NO

# 从源码运行
python main.py
```

## 架构

**入口点**: `main.py` — 将项目根目录加入 `sys.path`，获取单实例锁，构建 `DesktopTodoWidget`（整个 Tkinter 应用），调用 `app.run()`（进入 `mainloop`）。

### 模块分层

| 层 | 模块 | 职责 |
|-------|---------|----------------|
| `core/` | `task_manager`, `reminder_service`, `voice_recognizer`, `natural_language`, `single_instance` | 纯逻辑，不导入 UI 模块，不依赖 tkinter |
| `ui/` | `main_window`, `edit_dialog`, `settings_dialog`, `reminder_popup`, `close_dialog`, `tray_icon` | 所有 Tkinter 组件和对话框 |
| `utils/` | `common_utils`, `registry_utils`, `update_checker` | 共享常量、Windows 注册表操作、GitHub 自动更新 |
| `config/` | `settings_manager` | JSON 设置持久化（`data/settings.json`） |

### 数据流

- **任务增删改查**: `load_tasks()` → 修改 → `save_tasks()` → `_refresh_task_list()`（重建所有行组件）。任务格式：`{"id": int, "content": str, "done": bool, "due": ISO8601 | optional}`。
- **提醒**: `reminder_service.py` 是无状态的 —— `main_window._periodic_check()` 每 1 秒调用一次纯函数。通知通过 `root.after()` 定时器触发，`_notified_ids` 集合去重。
- **语音**: 麦克风按钮 → 后台线程采集 PyAudio → 三级级联：Vosk（离线）→ Google（在线）→ SAPI（Windows 内置）→ `parse_voice_task()` 提取 `(content, due_iso)` → 创建任务或填入输入框。
- **托盘**: `TrayIcon` 在守护线程中运行 pystray，通过 `root.after(0, ...)` 将回调调度到主线程。

### 关键设计决策

- **纯 Tkinter** — 不使用 Qt/Wx。唯一的额外 GUI 依赖：`pystray`（托盘图标）+ `PIL`（托盘图标图片）。
- **单实例锁** 位于 `%LOCALAPPDATA%/DesktopTodoWidget/_app.lock` — 一个 PID 文件，`.bat`（源码）和 `.exe`（打包）启动时共享。重复启动时，`FindWindowW` + `ShowWindow(SW_SHOWNORMAL)` 恢复已有窗口。
- **Catppuccin Mocha 主题** — 颜色常量集中在 `utils/common_utils.py`。
- **三级语音引擎降级** 带自动下载：Vosk 模型（解压后约 66MB）不会打包在内。缺失时 UI 会提示从 Alphacephei 或 HF 镜像下载，并显示进度和预计时间。

### 关键注意事项

- **Google 语音在中国卡住**: `recognize_google()` 在 Google 不可达时会阻塞 30 秒以上。代码在尝试 Google 之前会先检查 `is_model_missing()`，模型缺失时跳过 Google。
- **打包与源码的路径差异**: 打包时（`FROZEN = getattr(sys, 'frozen', False)`），`BASE_DIR` = `sys.executable` 所在目录。源码运行时则是项目根目录。**数据文件统一存放在 `%LOCALAPPDATA%\DesktopTodoWidget\data`（与项目/exe 位置无关，源码和 exe 共用同一份，项目搬家不会丢）**。
- **`data/tasks.json`** 是用户数据 — 永远不要提交它的变更。
- **`.gitignore`** 屏蔽了 `build/` 目录，但 `.spec` 文件和 `build_exe.py` 通过 `git add -f` 强制加入。

### Skills

本项目工作流由两个 Claude Code Skills（位于 `../.claude/skills/`）管理：

- **`post-edit`** — 每次对 `core/`、`ui/`、`utils/` 或 `main.py` 的代码修改后，提醒：重新打包 exe（自动递增 `BUILD_NO`）、推送到 GitHub、如果新增模块则更新 spec 的 hiddenimports。
- **`context-check`** — 每次回复后，显示目录 + 模型 + 上下文使用百分比。上下文低于 40% 时警告并建议 `/compact`。
