# Paste-free launcher: open this file in Blender's Text Editor and press Run Script (Alt+P).
# It runs build_body.py from the same folder, and writes everything it prints to log.txt next to it.
import bpy, os, sys, io, traceback, contextlib
HERE = r"C:\Health Os"
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    try:
        src = open(os.path.join(HERE, "build_body.py"), encoding="utf-8").read()
        exec(compile(src, "build_body.py", "exec"), {"__name__": "__main__", "HERE": HERE})
        print("RUN OK")
    except Exception:
        traceback.print_exc()
        print("RUN FAILED")
open(os.path.join(HERE, "log.txt"), "w", encoding="utf-8").write(buf.getvalue())
