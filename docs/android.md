# Android APK status

This fork contains an Android APK packaging scaffold:

```bash
JAVA_HOME=/opt/android-studio/jbr ANDROID_HOME=$HOME/AndroidSDK \
  python scripts/build_android_apk.py
```

The script uses Android SDK command-line tools directly (`aapt2`, `d8`, `zipalign`, `apksigner`) and writes:

```text
out/android/nocturnerecomp-debug.apk
```

## Current native-game blocker

The APK scaffold builds, signs, and verifies, but it is not yet a playable native Android port of NocturneRecomp.

NocturneRecomp depends on ReXGlue. The public ReXGlue SDK releases currently publish only:

- `linux-amd64`
- `linux-arm64`
- `win-amd64`

There is no Android/bionic SDK artifact to link into an APK.

I also probed ReXGlue source directly with an Android NDK toolchain. After a minimal platform-detection patch, CMake configure succeeds for `android-arm64`, but the native build fails in ReXGlue core on Android-specific gaps:

- `src/core/fiber_posix.cpp` uses `getcontext`, `makecontext`, and `swapcontext`, which Android/bionic does not provide.
- `include/rex/chrono/chrono.h` leaves `clock_time_conversion` unspecialized for the Android platform macro path.
- `src/core/memory_posix.cpp` calls `rex::GetAndroidApiLevel()`, but `rex/main_android.h` is not present in the public SDK source checkout.
- `src/core/threading_posix.cpp` also includes missing `rex/main_android.h`.

So the next real step for a playable APK is an Android ReXGlue port/fork that supplies Android fibers/context switching, platform chrono definitions, and the missing Android main/API-level support. Once that exists, the APK packaging scaffold can be changed to include the native NocturneRecomp shared library.
