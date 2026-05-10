---
name: post-edit
description: 代码修改完成后提醒用户是否需要重新打包 exe 和推送 GitHub，自动递增版本号
---

# post-edit Skill

## 触发条件
每次代码修改任务完成后，主动提醒用户检查以下事项。

## 行为流程

### 1. 版本号管理
项目根目录 `BUILD_NO` 文件存储当前版本号（两位数，如 `01`、`02`）。
每次重新打包 exe 时，自动将版本号 +1：
- 读取 `BUILD_NO` 文件获取当前版本号
- 新版本号 = 当前版本号 + 1（格式化为两位数，如 01 → 02）
- 写入新的 `BUILD_NO`
- 在打包命令和 commit 信息中标注版本号

### 2. 询问清单
代码修改完成后，向用户列出以下检查项：

1. **重新打包 exe** — 是否修改了 `core/`、`ui/`、`utils/`、`main.py` 等被打包的文件？
   - 如果是 → 递增版本号 → `python -m PyInstaller --noconfirm build/desktop_todo_widget.spec`
   - 如果只改了 `data/` 或文档 → 不需要

2. **更新 GitHub** — 是否有需要保存的代码变更？
   - `git status` 查看变更
   - `git add` + `git commit` + `git push`
   - Commit 信息应包含版本号，如 `build: v1.0.03 — 修复语音识别模型缺失提示`

3. **更新 spec 文件** — 是否新增了模块文件？
   - 检查 `build/desktop_todo_widget.spec` 的 `hiddenimports` 列表是否需要追加

### 3. 快捷打包命令
```bash
# 终止旧进程
taskkill /f /im "桌面待办.exe" 2>/dev/null
# 删除旧 exe
rm -f dist/桌面待办.exe
# 打包
python -m PyInstaller --noconfirm build/desktop_todo_widget.spec
```

### 4. 版本号递增命令
```bash
# 读取当前版本号并递增
BUILD_NO=$(cat BUILD_NO)
NEW_NO=$(printf "%02d" $((10#$BUILD_NO + 1)))
echo $NEW_NO > BUILD_NO
echo "版本: v1.0.$NEW_NO"
```
