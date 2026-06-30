#!/usr/bin/env python3
"""Build an Android APK for the current Android packaging scaffold.

This intentionally uses only Android SDK command-line tools (aapt2, d8,
apksigner) so the repo can produce an APK without a Gradle wrapper.

The APK built by this scaffold is a Java launcher/status shell. It does not yet
include the native NocturneRecomp runtime because upstream ReXGlue does not
currently ship or build a working Android SDK. See docs/android.md.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_DIR = ROOT / "android"
PACKAGE = "com.nocturnerecomp"


def run(cmd: list[object], **kwargs) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def find_android_home() -> Path:
    candidates = [
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        str(Path.home() / "AndroidSDK"),
        str(Path.home() / "Android" / "Sdk"),
        "/opt/android-sdk",
    ]
    for c in candidates:
        if c and (Path(c) / "platforms").exists():
            return Path(c)
    raise SystemExit("error: Android SDK not found; set ANDROID_HOME or install it under ~/AndroidSDK")


def newest_dir(parent: Path, prefix: str | None = None) -> Path:
    dirs = [p for p in parent.iterdir() if p.is_dir() and (prefix is None or p.name.startswith(prefix))]
    if not dirs:
        raise SystemExit(f"error: no directories found under {parent}")
    return sorted(dirs, key=lambda p: p.name)[-1]


def tool(build_tools: Path, name: str) -> Path:
    p = build_tools / name
    if not p.exists():
        raise SystemExit(f"error: missing {p}")
    return p


def find_jdk_tool(name: str) -> str | Path | None:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / name
        if candidate.exists():
            return candidate
    return shutil.which(name)


def ensure_debug_keystore(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keytool = find_jdk_tool("keytool")
    if not keytool:
        raise SystemExit("error: keytool not found; install a JDK")
    run([
        keytool,
        "-genkeypair",
        "-v",
        "-keystore", path,
        "-storepass", "android",
        "-alias", "androiddebugkey",
        "-keypass", "android",
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-dname", "CN=Android Debug,O=Android,C=US",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/android/nocturnerecomp-debug.apk")
    parser.add_argument("--target-sdk", default="android-35")
    parser.add_argument("--native-lib-dir", help="Directory containing arm64-v8a .so files to package")
    args = parser.parse_args()

    android_home = find_android_home()
    build_tools = newest_dir(android_home / "build-tools")
    platform = android_home / "platforms" / args.target_sdk
    if not platform.exists():
        platform = newest_dir(android_home / "platforms", "android-")
    android_jar = platform / "android.jar"
    if not android_jar.exists():
        raise SystemExit(f"error: missing {android_jar}")

    aapt2 = tool(build_tools, "aapt2")
    d8 = tool(build_tools, "d8")
    zipalign = tool(build_tools, "zipalign")
    apksigner = tool(build_tools, "apksigner")
    javac = find_jdk_tool("javac")
    if not javac:
        raise SystemExit("error: javac not found; install a JDK")

    out_dir = ROOT / "out" / "android"
    compiled_res = out_dir / "compiled-res"
    classes_dir = out_dir / "classes"
    dex_dir = out_dir / "dex"
    unsigned = out_dir / "nocturnerecomp-unsigned.apk"
    aligned = out_dir / "nocturnerecomp-aligned.apk"
    final_apk = (ROOT / args.out).resolve()

    if out_dir.exists():
        shutil.rmtree(out_dir)
    compiled_res.mkdir(parents=True)
    classes_dir.mkdir(parents=True)
    dex_dir.mkdir(parents=True)
    final_apk.parent.mkdir(parents=True, exist_ok=True)

    # Compile resources one file at a time; output .flat files into compiled-res.
    for res in sorted((ANDROID_DIR / "res").rglob("*")):
        if res.is_file():
            run([aapt2, "compile", "-o", compiled_res, res])

    flats = sorted(compiled_res.glob("*.flat"))
    run([
        aapt2, "link",
        "-o", unsigned,
        "--manifest", ANDROID_DIR / "AndroidManifest.xml",
        "-I", android_jar,
        "--java", out_dir / "generated",
        "--min-sdk-version", "26",
        "--target-sdk-version", platform.name.removeprefix("android-"),
        *flats,
    ])

    java_sources = sorted((ANDROID_DIR / "src").rglob("*.java")) + sorted((out_dir / "generated").rglob("*.java"))

    # ReXGlue links SDL statically into librexruntime.so on Android. SDL's
    # JNI_OnLoad still expects its Java-side org.libsdl.app classes to be
    # present in the app ClassLoader, so include the SDL Android support sources
    # whenever a local Android ReXGlue source tree exists.
    sdl_java_roots = [
        ROOT / "out" / "rexglue-android-src" / "thirdparty" / "sdl3" / "android-project" / "app" / "src" / "main" / "java",
        Path("/tmp/rexglue-sdk-src/thirdparty/sdl3/android-project/app/src/main/java"),
    ]
    for root in sdl_java_roots:
        if root.exists():
            java_sources.extend(sorted(root.rglob("*.java")))
            break

    run([javac, "--release", "17", "-classpath", android_jar, "-d", classes_dir, *java_sources])
    run([d8, "--min-api", "26", "--output", dex_dir, *classes_dir.rglob("*.class")])

    # Add classes.dex to the unsigned APK.
    run(["zip", "-j", unsigned, dex_dir / "classes.dex"], cwd=ROOT)

    native_lib_dir = Path(args.native_lib_dir).resolve() if args.native_lib_dir else None
    if native_lib_dir:
        so_files = sorted(native_lib_dir.glob("*.so"))
        if not so_files:
            raise SystemExit(f"error: no .so files found in {native_lib_dir}")
        apk_lib_dir = out_dir / "apk-lib" / "lib" / "arm64-v8a"
        apk_lib_dir.mkdir(parents=True, exist_ok=True)
        for so in so_files:
            shutil.copy2(so, apk_lib_dir / so.name)
        rels = [str(p.relative_to(out_dir / "apk-lib")) for p in sorted(apk_lib_dir.glob("*.so"))]
        run(["zip", "-r", unsigned, *rels], cwd=out_dir / "apk-lib")

    run([zipalign, "-f", "4", unsigned, aligned])

    keystore = ROOT / "out" / "android-debug.keystore"
    ensure_debug_keystore(keystore)
    run([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--out", final_apk,
        aligned,
    ])
    run([apksigner, "verify", "--verbose", final_apk])
    print(f"\nAPK built: {final_apk}")


if __name__ == "__main__":
    main()
