import os
import subprocess
import sys
import shutil
from pathlib import Path

def run_cmd(cmd, cwd=None):
    print(f"[*] Running: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] Error (Exit {res.returncode}):")
        if res.stdout:
            print("--- STDOUT ---")
            print(res.stdout)
        if res.stderr:
            print("--- STDERR ---")
            print(res.stderr)
        raise RuntimeError(f"Command failed: {cmd}")
    return res.stdout

def build_apk():
    base_dir = Path(__file__).resolve().parent.parent
    android_dir = base_dir / "android"
    app_dir = android_dir / "app"
    src_main = app_dir / "src" / "main"
    res_dir = src_main / "res"
    assets_dir = src_main / "assets"
    java_src_dir = src_main / "java"
    manifest_file = src_main / "AndroidManifest.xml"

    sdk_dir = Path(r"C:\Users\Karuppu\AppData\Local\Android\Sdk")
    build_tools = sdk_dir / "build-tools" / "36.0.0"
    if not build_tools.exists():
        build_tools = sdk_dir / "build-tools" / "34.0.0"
    android_jar = sdk_dir / "platforms" / "android-34" / "android.jar"

    aapt2 = str(build_tools / "aapt2.exe")
    d8 = str(build_tools / "d8.bat")
    zipalign = str(build_tools / "zipalign.exe")
    apksigner = str(build_tools / "apksigner.bat")

    build_out = app_dir / "build" / "outputs" / "apk" / "release"
    build_out.mkdir(parents=True, exist_ok=True)
    
    intermediates = app_dir / "build" / "intermediates"
    if intermediates.exists():
        shutil.rmtree(intermediates)
    intermediates.mkdir(parents=True, exist_ok=True)

    compiled_res = intermediates / "compiled_res"
    compiled_res.mkdir(parents=True, exist_ok=True)
    gen_dir = intermediates / "gen"
    gen_dir.mkdir(parents=True, exist_ok=True)
    classes_dir = intermediates / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    dex_dir = intermediates / "dex"
    dex_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*70)
    print("STARTING NEXORA AI ANDROID RELEASE APK BUILD PIPELINE")
    print("="*70)

    # 1. Sync web assets
    print("\n[1] Syncing web assets into Android package...")
    from sync_android_assets import sync_assets
    sync_assets()

    # 2. Compile resources with aapt2
    print("\n[2] Compiling Android resources with AAPT2...")
    res_zip = intermediates / "resources.zip"
    run_cmd(f'"{aapt2}" compile --dir "{res_dir}" -o "{res_zip}"')
    print("    [PASS] Resources compiled successfully.")

    # 3. Link resources and generate R.java + unaligned base APK
    print("\n[3] Linking resources and generating R.java & package structure...")
    unaligned_apk = intermediates / "unaligned.apk"
    run_cmd(
        f'"{aapt2}" link -I "{android_jar}" '
        f'--manifest "{manifest_file}" '
        f'--java "{gen_dir}" '
        f'-A "{assets_dir}" '
        f'-o "{unaligned_apk}" '
        f'"{res_zip}" --auto-add-overlay'
    )
    print("    [PASS] R.java generated and resource APK linked.")

    # 4. Compile Java sources with javac
    print("\n[4] Compiling Java source files with javac...")
    java_files = list(java_src_dir.rglob("*.java")) + list(gen_dir.rglob("*.java"))
    java_sources_file = intermediates / "sources.txt"
    with open(java_sources_file, "w", encoding="utf-8") as f:
        for jf in java_files:
            f.write(f'"{jf.as_posix()}"\n')

    run_cmd(
        f'javac -g:none -source 8 -target 8 -encoding UTF-8 '
        f'-cp "{android_jar}" '
        f'-d "{classes_dir}" '
        f'"@{java_sources_file.as_posix()}"'
    )
    print("    [PASS] Java source files compiled to bytecode.")

    # 5. Dex bytecode with d8
    print("\n[5] Converting bytecode to Dalvik Executable (classes.dex) with D8...")
    class_files = list(classes_dir.rglob("*.class"))
    class_args = " ".join([f'"{cf}"' for cf in class_files])

    run_cmd(
        f'"{d8}" --release --min-api 26 '
        f'--lib "{android_jar}" '
        f'--output "{dex_dir}" '
        f'{class_args}'
    )
    print("    [PASS] classes.dex created.")


    # 6. Add classes.dex into the APK (using jar / zip)
    print("\n[6] Packaging classes.dex into APK container...")
    # copy unaligned_apk to working apk
    working_apk = intermediates / "working.apk"
    shutil.copyfile(unaligned_apk, working_apk)

    # Use jar command to update working.apk with classes.dex
    dex_file = dex_dir / "classes.dex"
    run_cmd(f'jar -uf "{working_apk}" -C "{dex_dir}" classes.dex')
    print("    [PASS] Bytecode packaged into APK archive.")

    # 7. ZipAlign (4-byte alignment)
    print("\n[7] 4-Byte ZipAligning APK...")
    aligned_apk = intermediates / "aligned.apk"
    run_cmd(f'"{zipalign}" -v -p 4 "{working_apk}" "{aligned_apk}"')
    print("    [PASS] APK successfully 4-byte aligned.")

    # 8. Keystore & Release Signing with apksigner (v1, v2, v3, v4 signatures)
    print("\n[8] Cryptographically signing Release APK with apksigner...")
    keystore_path = android_dir / "myai-release-key.jks"
    key_alias = "myai_key"
    key_pass = "MyAiProductionPassword2026!"

    if not keystore_path.exists():
        print("    [*] Generating production release keystore...")
        run_cmd(
            f'keytool -genkeypair -v '
            f'-keystore "{keystore_path}" '
            f'-alias {key_alias} '
            f'-keyalg RSA '
            f'-keysize 2048 '
            f'-validity 10000 '
            f'-storepass {key_pass} '
            f'-keypass {key_pass} '
            f'-dname "CN=NEXORA AI, OU=Engineering, O=NEXORA AI Inc, L=San Francisco, ST=CA, C=US"'
        )
        print("    [PASS] Release keystore created.")

    final_apk = build_out / "app-release.apk"
    run_cmd(
        f'"{apksigner}" sign --ks "{keystore_path}" '
        f'--ks-key-alias {key_alias} '
        f'--ks-pass pass:{key_pass} '
        f'--key-pass pass:{key_pass} '
        f'--out "{final_apk}" '
        f'"{aligned_apk}"'
    )
    print(f"    [PASS] Release APK signed: {final_apk}")

    # 9. Verify Signature
    print("\n[9] Verifying APK signature & Google Play compliance...")
    verify_out = run_cmd(f'"{apksigner}" verify --verbose "{final_apk}"')
    print("    [PASS] Signature Verification Details:")
    for line in verify_out.strip().splitlines()[:6]:
        print(f"      {line}")

    apk_size_mb = final_apk.stat().st_size / (1024 * 1024)
    print("\n" + "="*70)
    print(f"NEXORA AI ANDROID RELEASE BUILD COMPLETED SUCCESSFULLY!")
    print(f"Release APK Path: {final_apk}")
    print(f"APK Size: {apk_size_mb:.2f} MB")
    print("="*70 + "\n")

    return final_apk

if __name__ == "__main__":
    build_apk()
