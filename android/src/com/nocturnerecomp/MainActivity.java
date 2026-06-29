package com.nocturnerecomp;

import android.app.Activity;
import android.os.Bundle;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.graphics.Color;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
    private SurfaceView surfaceView;
    private TextView statusView;

    private static boolean nativeAvailable = false;

    static {
        try {
            System.loadLibrary("rexruntime");
            System.loadLibrary("nocturnerecomp");
            nativeAvailable = true;
        } catch (UnsatisfiedLinkError err) {
            nativeAvailable = false;
        }
    }

    private static native void nativeStart(Surface surface);
    private static native void nativeSetSurface(Surface surface);
    private static native void nativeStop();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        );

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        surfaceView = new SurfaceView(this);
        surfaceView.getHolder().addCallback(this);
        root.addView(surfaceView, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        statusView = new TextView(this);
        statusView.setTextColor(Color.WHITE);
        statusView.setText(nativeAvailable
            ? "NocturneRecomp starting…"
            : "NocturneRecomp Android scaffold — native game libraries not packaged");
        statusView.setBackgroundColor(0x66000000);
        statusView.setPadding(24, 24, 24, 24);
        root.addView(statusView);

        setContentView(root);
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        if (!nativeAvailable) {
            return;
        }
        statusView.setText("NocturneRecomp native surface ready");
        nativeStart(holder.getSurface());
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        if (nativeAvailable) {
            nativeSetSurface(holder.getSurface());
        }
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        if (nativeAvailable) {
            nativeSetSurface(null);
        }
    }

    @Override
    protected void onDestroy() {
        if (nativeAvailable) {
            nativeStop();
        }
        super.onDestroy();
    }
}
