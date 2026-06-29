# Android APK status

This branch contains the start of a real Android port, not just a Java shell.

## What works now

- ReXGlue can be patched and built for Android arm64-v8a with the NDK.
- The Android APK packager can include native `.so` files under
  `lib/arm64-v8a/`.
- The Java launcher owns a fullscreen `SurfaceView` and passes its native
  surface to JNI.
- The native Android entry point creates a ReXGlue
  `AndroidWindowedAppContext`, creates the generated Nocturne app, and runs the
  ReXGlue app loop.

## Required local game asset

A playable APK cannot be generated from source alone because ReXGlue codegen
requires the game binary:

```text
assets/default.xex
```

This file is intentionally not tracked or redistributed. Put your legally
obtained Xbox 360 game XEX at that path, then run:

```bash
JAVA_HOME=/opt/android-studio/jbr ANDROID_HOME=$HOME/AndroidSDK \
  python scripts/build_android_game_apk.py
```

The script will:

1. Build an experimental Android ReXGlue SDK from source using
   `android/rexglue-android.patch`.
2. Run host/Linux `sdk/bin/rexglue codegen nocturnerecomp_manifest.toml`.
3. Cross-compile `libnocturnerecomp.so` for Android arm64-v8a.
4. Package `libnocturnerecomp.so` and `librexruntime.so` into a signed debug APK.

Expected APK path:

```text
out/android/nocturnerecomp-debug.apk
```

## Current verification

Verified locally without the XEX:

```text
python -m py_compile scripts/build_rexglue_android_sdk.py scripts/build_android_game_apk.py scripts/build_android_apk.py
python scripts/build_android_game_apk.py --skip-rexglue-sdk
# -> error: missing assets/default.xex; provide your game XEX before building a playable APK
```

Also verified native APK packaging with the Android ReXGlue runtime:

```text
lib/arm64-v8a/librexruntime.so
```

## ReXGlue Android patch notes

`android/rexglue-android.patch` currently adds/changes:

- Android platform detection in ReXGlue CMake.
- Android pthread-backed fiber fallback, replacing unavailable bionic
  `ucontext` APIs.
- Android CMake helper behavior that skips GTK/XCB and desktop `main()`.
- Android surface/window/windowed-app-context stubs using `ANativeWindow`.
- Android link dependency cleanup (`android`, `log`, no GTK/XCB/rt).
- FFmpeg Android arm64 non-PIC assembly disabled for first successful shared
  runtime linkage.
- Minimal Android content-URI stub; full JNI ContentResolver support remains a
  future improvement.

## Caveats

This is an experimental first port path. Once `assets/default.xex` is provided,
the next validation steps are:

1. Build the full playable APK.
2. Install on a Vulkan-capable Android device.
3. Capture `adb logcat` for ReXGlue/Nocturne startup errors.
4. Iterate on input/audio/surface lifecycle issues.
