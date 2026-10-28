package id.alfisjahri.agybot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * AgyBot v1.0.2 — jalankan foreground service setelah HP restart
 * (service memegang jadwal polling; AlarmManager tidak dipakai lagi).
 */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            PollService.start(ctx);
        }
    }
}
