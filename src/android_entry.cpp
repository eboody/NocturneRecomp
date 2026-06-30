#if defined(__ANDROID__)

#include <jni.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>

#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unistd.h>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/ui/windowed_app.h>
#include <rex/ui/windowed_app_context_android.h>

namespace {
std::mutex g_mutex;
std::unique_ptr<rex::ui::AndroidWindowedAppContext> g_context;
std::unique_ptr<rex::ui::WindowedApp> g_app;
std::thread g_thread;
std::atomic<bool> g_started{false};
ANativeWindow* g_window = nullptr;
std::string g_data_dir;

void PrepareWritableWorkingDirectory() {
  std::string dir;
  {
    std::lock_guard<std::mutex> lock(g_mutex);
    dir = g_data_dir;
  }
  if (dir.empty()) {
    dir = "/data/local/tmp/nocturnerecomp";
  }
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  setenv("REX_ANDROID_DATA_DIR", dir.c_str(), 1);
  chdir(dir.c_str());
}

void RunNocturne() {
  PrepareWritableWorkingDirectory();

  const char* argv[] = {"nocturnerecomp"};
  auto remaining = rex::cvar::Init(1, const_cast<char**>(argv));
  (void)remaining;
  rex::cvar::ApplyEnvironment();
  rex::InitLoggingEarly();

  {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_context = std::make_unique<rex::ui::AndroidWindowedAppContext>();
    g_context->Initialize();
    if (g_window) {
      g_context->SetNativeWindow(g_window);
    }
    auto creator = rex::ui::WindowedApp::GetCreator("nocturnerecomp");
    if (!creator) {
      return;
    }
    g_app = creator(*g_context);
    g_app->SetParsedArguments({});
  }

  bool initialized = false;
  {
    std::lock_guard<std::mutex> lock(g_mutex);
    initialized = g_app && g_app->OnInitialize();
  }

  if (initialized) {
    g_context->RunMainMessageLoop();
  }

  {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_app) {
      g_app->InvokeOnDestroy();
      g_app.reset();
    }
    g_context.reset();
  }

  rex::ShutdownLogging();
  g_started.store(false, std::memory_order_release);
}
}  // namespace

extern "C" JNIEXPORT void JNICALL
Java_com_nocturnerecomp_MainActivity_nativeSetDataDirectory(JNIEnv* env, jclass, jstring path) {
  const char* chars = path ? env->GetStringUTFChars(path, nullptr) : nullptr;
  {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_data_dir = chars ? chars : "";
  }
  if (chars) {
    env->ReleaseStringUTFChars(path, chars);
  }
}

extern "C" JNIEXPORT void JNICALL
Java_com_nocturnerecomp_MainActivity_nativeStart(JNIEnv* env, jclass, jobject surface) {
  std::lock_guard<std::mutex> lock(g_mutex);
  if (surface && !g_window) {
    g_window = ANativeWindow_fromSurface(env, surface);
  }
  if (g_context && g_window) {
    g_context->SetNativeWindow(g_window);
  }
  bool expected = false;
  if (g_started.compare_exchange_strong(expected, true, std::memory_order_acq_rel)) {
    g_thread = std::thread(RunNocturne);
    g_thread.detach();
  }
}

extern "C" JNIEXPORT void JNICALL
Java_com_nocturnerecomp_MainActivity_nativeSetSurface(JNIEnv* env, jclass, jobject surface) {
  std::lock_guard<std::mutex> lock(g_mutex);
  ANativeWindow* new_window = surface ? ANativeWindow_fromSurface(env, surface) : nullptr;
  ANativeWindow* old_window = g_window;
  g_window = new_window;
  if (g_context) {
    g_context->SetNativeWindow(g_window);
  }
  if (old_window) {
    ANativeWindow_release(old_window);
  }
}

extern "C" JNIEXPORT void JNICALL
Java_com_nocturnerecomp_MainActivity_nativeStop(JNIEnv*, jclass) {
  std::lock_guard<std::mutex> lock(g_mutex);
  if (g_context) {
    g_context->RequestDeferredQuit();
  }
}

#endif  // __ANDROID__
