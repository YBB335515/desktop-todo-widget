# 桌面待办小组件

悬浮在桌面上的待办事项小组件，像手机桌面小组件一样随时查看和编辑。

## 功能

- 始终置顶悬浮窗，拖拽移动，一键收起
- 添加 / 编辑 / 删除待办事项
- 设置提醒时间（支持自然语言：明天15:00、后天9:30）
- 桌面右下角弹窗提醒
- 倒计时精确到秒
- 双击任务直接编辑内容和时间
- 暗色主题

## 使用方式

### 方式一：直接运行 exe（推荐）

下载 `待办小组件.exe`，双击运行。**无需安装 Python 或任何依赖。**

### 方式二：Python 运行

```bash
# 安装依赖（仅需 Python 自带 tkinter，无需额外安装）
python desktop_todo_widget.py

# 或无黑窗口运行
pythonw desktop_todo_widget.py
```

双击 `启动待办小组件.bat` 也可启动。

## 命令行工具

```bash
# 添加任务
python todo.py add "买菜"

# 查看任务
python todo.py list

# 标记完成
python todo.py done 1

# 设置提醒
python todo.py remind 1 明天15:00

# 删除任务
python todo.py delete 1
```

## 构建 exe

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name "待办小组件" desktop_todo_widget.py
```

exe 生成在 `dist/` 目录。
