#!/usr/bin/env python3
"""Build a playable Android APK for NocturneRecomp.

Requires assets/default.xex. The XEX is not redistributed; it is used locally by
ReXGlue codegen to emit generated C++ sources.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[object], **kwargs) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def newest_ndk(android_home: Path) -> Path:
    ndks = sorted((android_home / "ndk").glob("*"))
    if not ndks:
        raise SystemExit(f"error: no NDK installed under {android_home / 'ndk'}")
    return ndks[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--android-home", default=os.environ.get("ANDROID_HOME") or str(Path.home() / "AndroidSDK"))
    parser.add_argument("--rexglue-android-sdk", default="out/rexglue-android-sdk")
    parser.add_argument("--host-sdk", default="sdk", help="Linux host ReXGlue SDK used for codegen")
    parser.add_argument("--build-dir", default="out/android-native-build")
    parser.add_argument("--apk", default="out/android/nocturnerecomp-debug.apk")
    parser.add_argument("--skip-rexglue-sdk", action="store_true")
    args = parser.parse_args()

    xex = ROOT / "assets" / "default.xex"
    if not xex.exists():
        raise SystemExit("error: missing assets/default.xex; provide your game XEX before building a playable APK")

    android_home = Path(args.android_home).expanduser().resolve()
    ndk = newest_ndk(android_home)
    rex_android_sdk = (ROOT / args.rexglue_android_sdk).resolve()
    host_sdk = (ROOT / args.host_sdk).resolve()
    build_dir = (ROOT / args.build_dir).resolve()

    host_rexglue = host_sdk / "bin" / "rexglue"
    if not host_rexglue.exists():
        run([sys.executable, ROOT / "scripts" / "download-sdk.py"])
    if not host_rexglue.exists():
        raise SystemExit(f"error: host rexglue not found at {host_rexglue}")

    # Generate sources with the host SDK before creating Android SDK source/install
    # trees under out/. ReXGlue's migration scanner walks the project tree, so
    # doing this first avoids scanning generated copies of ReXGlue itself.
    manifests = sorted(ROOT.glob("*_manifest.toml"))
    if len(manifests) != 1:
        raise SystemExit(f"error: expected one *_manifest.toml, found {manifests}")
    run([host_rexglue, "--force", "codegen", manifests[0]], cwd=ROOT)

    # The Android SDK patch currently builds as 0.8.0.0-dev.unknown, while the
    # host codegen SDK emits a generated helper that asks CMake for rexglue
    # 0.8.1 exactly. For this experimental Android target, use the explicitly
    # supplied Android rexglue_DIR and relax the versioned lookup.
    rexglue_cmake = ROOT / "generated" / "rexglue.cmake"
    text = rexglue_cmake.read_text()
    text = text.replace("find_package(rexglue ${REXSDK_VERSION} EXACT QUIET CONFIG)",
                        "find_package(rexglue QUIET CONFIG)")
    text = text.replace("find_package(rexglue 0.8.1 QUIET CONFIG)",
                        "find_package(rexglue QUIET CONFIG)")
    rexglue_cmake.write_text(text)

    if not args.skip_rexglue_sdk or not (rex_android_sdk / "lib" / "librexruntime.so").exists():
        run([sys.executable, ROOT / "scripts" / "build_rexglue_android_sdk.py", "--prefix", rex_android_sdk])

    shutil.rmtree(build_dir, ignore_errors=True)
    run([
        "cmake", "-S", ROOT, "-B", build_dir, "-G", "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={ndk / 'build/cmake/android.toolchain.cmake'}",
        "-DANDROID_ABI=arm64-v8a",
        "-DANDROID_PLATFORM=android-26",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_PREFIX_PATH={rex_android_sdk}",
        f"-Drexglue_DIR={rex_android_sdk / 'lib/cmake/rexglue'}",
        "-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH",
    ])
    run(["cmake", "--build", build_dir, "--target", "nocturnerecomp", "--parallel", str(os.cpu_count() or 4)])

    native_dir = ROOT / "out" / "android-native-libs"
    shutil.rmtree(native_dir, ignore_errors=True)
    native_dir.mkdir(parents=True)
    shutil.copy2(build_dir / "libnocturnerecomp.so", native_dir / "libnocturnerecomp.so")
    shutil.copy2(rex_android_sdk / "lib" / "librexruntime.so", native_dir / "librexruntime.so")

    run([sys.executable, ROOT / "scripts" / "build_android_apk.py", "--native-lib-dir", native_dir, "--out", args.apk], cwd=ROOT)
    print(f"\nPlayable Android APK built: {ROOT / args.apk}")


if __name__ == "__main__":
    main()
