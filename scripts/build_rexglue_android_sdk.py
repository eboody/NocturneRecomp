#!/usr/bin/env python3
"""Build the experimental Android ReXGlue SDK used by this fork.

The upstream ReXGlue release does not ship Android artifacts yet. This script
clones ReXGlue source, applies android/rexglue-android.patch, builds arm64-v8a,
and installs an SDK tree usable through CMAKE_PREFIX_PATH.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "android" / "rexglue-android.patch"


def run(cmd: list[object], cwd: Path | None = None) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def newest_ndk(android_home: Path) -> Path:
    ndks = sorted((android_home / "ndk").glob("*"))
    if not ndks:
        raise SystemExit(f"error: no NDK installed under {android_home / 'ndk'}")
    return ndks[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="https://github.com/birabittoh/rexglue-sdk.git")
    parser.add_argument("--work", default="out/rexglue-android-src")
    parser.add_argument("--build", default="out/rexglue-android-build")
    parser.add_argument("--prefix", default="out/rexglue-android-sdk")
    parser.add_argument("--android-home", default=os.environ.get("ANDROID_HOME") or str(Path.home() / "AndroidSDK"))
    parser.add_argument("--android-platform", default="android-26")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    android_home = Path(args.android_home).expanduser().resolve()
    ndk = newest_ndk(android_home)
    work = (ROOT / args.work).resolve()
    build = (ROOT / args.build).resolve()
    prefix = (ROOT / args.prefix).resolve()

    if args.clean:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(build, ignore_errors=True)
        shutil.rmtree(prefix, ignore_errors=True)

    if not work.exists():
        run(["git", "clone", "--recursive", "--depth", "1", args.repo, work])
    else:
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=work)

    # Use patch(1), not git apply, because FFmpeg is a submodule and this patch
    # intentionally touches files inside it.
    run(["patch", "-p1", "-N", "-r", "-", "-i", PATCH], cwd=work)

    run([
        "cmake", "-S", work, "-B", build, "-G", "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={ndk / 'build/cmake/android.toolchain.cmake'}",
        "-DANDROID_ABI=arm64-v8a",
        f"-DANDROID_PLATFORM={args.android_platform}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DREXGLUE_ENABLE_TRACY=OFF",
        "-DREXGLUE_ENABLE_PERF_COUNTERS=OFF",
        "-DREXGLUE_BUILD_TESTS=OFF",
        "-DREXGLUE_ENABLE_FIDELITYFX=OFF",
    ])
    run(["cmake", "--build", build, "--parallel", str(os.cpu_count() or 4)])
    shutil.rmtree(prefix, ignore_errors=True)
    run(["cmake", "--install", build, "--prefix", prefix])
    print(f"\nAndroid ReXGlue SDK installed to: {prefix}")


if __name__ == "__main__":
    main()
