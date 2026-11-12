package com.carsky.verify;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class VerificationActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
        getWindow().setStatusBarColor(Color.rgb(8, 11, 18));
        getWindow().setNavigationBarColor(Color.rgb(8, 11, 18));

        String code = getIntent().getStringExtra("code");
        if (code == null || !code.matches("[1-9][0-9]?")) {
            finish();
            return;
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(32, 40, 32, 40);
        root.setBackgroundColor(Color.rgb(8, 11, 18));

        TextView brand = new TextView(this);
        brand.setText("CARSKY");
        brand.setTextColor(Color.rgb(91, 156, 255));
        brand.setTextSize(18);
        brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        brand.setGravity(Gravity.CENTER);

        TextView title = new TextView(this);
        title.setText("PHONE VERIFICATION");
        title.setTextColor(Color.WHITE);
        title.setTextSize(16);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 28, 0, 8);

        TextView instruction = new TextView(this);
        instruction.setText("Enter this number on your Chromebook");
        instruction.setTextColor(Color.LTGRAY);
        instruction.setTextSize(14);
        instruction.setGravity(Gravity.CENTER);

        TextView number = new TextView(this);
        number.setText(code);
        number.setTextColor(Color.WHITE);
        number.setTextSize(76);
        number.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        number.setGravity(Gravity.CENTER);
        number.setPadding(0, 28, 0, 28);

        TextView note = new TextView(this);
        note.setText("This screen does not unlock your phone.\nThe normal lock screen remains in place.");
        note.setTextColor(Color.GRAY);
        note.setTextSize(12);
        note.setGravity(Gravity.CENTER);

        root.addView(brand);
        root.addView(title);
        root.addView(instruction);
        root.addView(number);
        root.addView(note);
        setContentView(root);
    }
}
