import subprocess, sys, os, traceback

log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "_launcher.log"), "w", encoding="utf-8")

try:
    widget = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "desktop_todo_widget.py")
    log.write("widget path: %s\n" % widget)
    log.write("widget exists: %s\n" % os.path.exists(widget))
    log.write("python: %s\n" % sys.executable)

    if sys.platform == "win32":
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        log.write("pythonw: %s\n" % pythonw)
        log.write("pythonw exists: %s\n" % os.path.exists(pythonw))

        DETACHED_PROCESS = 0x00000008
        p = subprocess.Popen(
            [pythonw, widget],
            creationflags=DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        log.write("spawned pid: %s\n" % p.pid)
    else:
        p = subprocess.Popen([sys.executable, widget], close_fds=True)

    log.write("launcher done\n")
except Exception:
    log.write("ERROR:\n")
    traceback.print_exc(file=log)
finally:
    log.close()
