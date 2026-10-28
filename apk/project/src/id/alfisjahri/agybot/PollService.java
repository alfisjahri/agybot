package id.alfisjahri.agybot;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

/**
 * AgyBot v1.0.2 — foreground service untuk polling di background.
 *
 * Alasan: di Infinix Note 50X (XOS) Alfi tidak ada setelan "Alarms & reminders"
 * (izin exact alarm), dan AlarmManager saja tidak cukup — aplikasi tidak pernah
 * jalan di background (Background Running Duration 0 min) walau baterai sudah
 * "No Restrictions". Foreground service menjaga proses tetap hidup sehingga
 * polling 30 detik jalan terus, juga saat aplikasi diminimize.
 *
 * Cara kerja: service mengirim broadcast ACTION_POLL ke PollReceiver tiap
 * 30 detik (logika poll tetap di PollReceiver, tidak diduplikasi). Service
 * ini yang memegang jadwal — PollReceiver TIDAK lagi menjadwalkan alarm
 * berikutnya (AlarmManager tidak dipakai untuk polling sejak v1.0.2).
 *
 * Notifikasi permanen "AgyBot memantau routine" (channel LOW, tanpa suara)
 * adalah syarat Android untuk foreground service — tidak bisa di-swipe.
 * Kalau service dihentikan, polling berhenti; MainActivity + BootReceiver
 * menjalankan ulang service ini.
 */
public class PollService extends Service {

    private static final String TAG = "AgyBotPoll";
    private static final int FOREGROUND_ID = 900000;
    private static final String KEEPALIVE_CHANNEL_ID = "agybot_keepalive";

    private Handler handler;
    private final Runnable pollTask = new Runnable() {
        @Override
        public void run() {
            try {
                Intent poll = new Intent(PollService.this, PollReceiver.class)
                        .setAction(PollScheduler.ACTION_POLL);
                sendBroadcast(poll);
            } catch (Exception e) {
                Log.w(TAG, "kirim poll gagal: " + e.getMessage());
            }
            if (handler != null) {
                handler.postDelayed(this, PollScheduler.INTERVAL_MS);
            }
        }
    };

    /** Jalankan service dari mana saja (MainActivity, BootReceiver). */
    public static void start(Context ctx) {
        try {
            Intent svc = new Intent(ctx, PollService.class);
            if (Build.VERSION.SDK_INT >= 26) {
                ctx.startForegroundService(svc);
            } else {
                ctx.startService(svc);
            }
        } catch (Exception e) {
            Log.w(TAG, "start service gagal: " + e.getMessage());
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        handler = new Handler(Looper.getMainLooper());
        ensureKeepaliveChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(FOREGROUND_ID, buildKeepaliveNotification());
        handler.removeCallbacks(pollTask);
        handler.post(pollTask);
        Log.i(TAG, "foreground service jalan — polling 30 detik");
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (handler != null) {
            handler.removeCallbacks(pollTask);
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void ensureKeepaliveChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager)
                    getSystemService(NOTIFICATION_SERVICE);
            if (nm != null && nm.getNotificationChannel(KEEPALIVE_CHANNEL_ID) == null) {
                NotificationChannel ch = new NotificationChannel(
                        KEEPALIVE_CHANNEL_ID, "AgyBot berjalan",
                        NotificationManager.IMPORTANCE_LOW);
                ch.setDescription("Tanda polling routine AgyBot aktif di background");
                nm.createNotificationChannel(ch);
            }
        }
    }

    private Notification buildKeepaliveNotification() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            b = new Notification.Builder(this, KEEPALIVE_CHANNEL_ID);
        } else {
            b = new Notification.Builder(this);
        }
        return b.setContentTitle("AgyBot memantau routine")
                .setContentText("Polling tiap 30 detik — ketuk untuk membuka AgyBot")
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(pi)
                .build();
    }
}
