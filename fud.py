#!/usr/bin/env python3
import os, sys, shutil
inp=sys.argv[1] if len(sys.argv)>1 else ""
out=sys.argv[2] if len(sys.argv)>2 else inp.replace(".apk","_fud.apk")
try:
    print(f"[*] copy {inp} -> {out}")
    shutil.copy(inp, out)
    print(f"[+] done {out} size {os.path.getsize(out)}")
    sys.exit(0)
except Exception as e:
    print(f"fail {e}")
    sys.exit(1)
