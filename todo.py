import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# 确保 stdout 使用 UTF-8，避免 Windows GBK 终端乱码
sys.stdout.reconfigure(encoding="utf-8")

TASKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")


def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def cmd_add(args):
    tasks = load_tasks()
    new_id = max((t["id"] for t in tasks), default=0) + 1
    tasks.append({"id": new_id, "content": args.content, "done": False})
    save_tasks(tasks)
    print(f"已添加任务 [{new_id}]: {args.content}")


def cmd_list(args):
    tasks = load_tasks()
    if not tasks:
        print("暂无任务")
        return
    for i, t in enumerate(tasks, 1):
        status = "✓" if t["done"] else " "
        line = f"  {i}. [{status}] {t['content']}"
        if t.get("due"):
            dt = datetime.fromisoformat(t["due"])
            line += f"  ⏰ {dt.strftime('%m-%d %H:%M')}"
        print(line)


def cmd_done(args):
    tasks = load_tasks()
    idx = args.num - 1
    if idx < 0 or idx >= len(tasks):
        print(f"错误: 编号 {args.num} 不存在")
        sys.exit(1)
    tasks[idx]["done"] = True
    save_tasks(tasks)
    print(f"已完成: {tasks[idx]['content']}")


def parse_due_time(text):
    now = datetime.now()
    text = text.strip()

    if text.startswith("明天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=1)
    elif text.startswith("后天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=2)
    elif text.startswith("今天"):
        time_str = text[2:].strip()
        target_date = now.date()
    else:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            return dt.isoformat()
        except ValueError:
            pass
        time_str = text
        target_date = now.date()

    time_str = time_str.strip()
    try:
        hour, minute = map(int, time_str.split(":"))
    except Exception:
        raise ValueError(f"无法解析时间: {text}")

    target_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
    return target_dt.isoformat()


def cmd_remind(args):
    tasks = load_tasks()
    idx = args.num - 1
    if idx < 0 or idx >= len(tasks):
        print(f"错误: 编号 {args.num} 不存在")
        sys.exit(1)

    due = parse_due_time(args.time)
    tasks[idx]["due"] = due
    save_tasks(tasks)

    dt = datetime.fromisoformat(due)
    print(f"已设置提醒: {tasks[idx]['content']}")
    print(f"提醒时间: {dt.strftime('%Y-%m-%d %H:%M')}")


def cmd_delete(args):
    tasks = load_tasks()
    idx = args.num - 1
    if idx < 0 or idx >= len(tasks):
        print(f"错误: 编号 {args.num} 不存在")
        sys.exit(1)
    removed = tasks.pop(idx)
    save_tasks(tasks)
    print(f"已删除: {removed['content']}")


def main():
    parser = argparse.ArgumentParser(description="简易待办事项")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加任务")
    p_add.add_argument("content", help="任务内容")

    sub.add_parser("list", help="查看所有任务")

    p_done = sub.add_parser("done", help="标记任务为已完成")
    p_done.add_argument("num", type=int, help="任务编号")

    p_remind = sub.add_parser("remind", help="设置任务提醒时间")
    p_remind.add_argument("num", type=int, help="任务编号")
    p_remind.add_argument("time", help="提醒时间，如 明天15:00 或 2026-05-03 15:00")

    p_del = sub.add_parser("delete", help="删除任务")
    p_del.add_argument("num", type=int, help="任务编号")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    {"add": cmd_add, "list": cmd_list, "done": cmd_done, "remind": cmd_remind, "delete": cmd_delete}[args.command](args)


if __name__ == "__main__":
    main()
