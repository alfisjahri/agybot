package id.alfisjahri.agybot;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

/**
 * AgyBot v6 — penjadwal polling notifikasi (AlarmManager, tanpa androidx).
 *
 * Interval 1 menit (Alfi, 28 Okt 20:31). Alarm TIDAK berulang otomatis:
 * setiap kali PollReceiver selesai (atau gagal), ia menjadwalkan alarm
 * berikutnya — jadi jadwal tetap jalan walau satu poll gagal.
 * CATATAN BATASAN ANDROID: setExactAndAllowWhileIdle di Doze dibatasi
 * sistem ~9 menit per aplikasi KECUALI aplikasi ada di whitelist
 * optimasi baterai. Alfi sudah set Battery "Unrestricted" di HP-nya
 * (= whitelist), jadi alarm 1 menit seharusnya jalan. Kalau suatu saat
 * diubah kembali ke "Optimized", sistem akan menunda alarm sampai
 * ~9-15 menit — itu batas Android, bukan bug aplikasi.
 *
 * v6: scheduleNext mencatat ke logcat (tag AgyBotPoll) apakah exact alarm
 * bisa dijadwalkan — di v2-v5, kalau izin exact alarm tidak diberikan,
 * aplikasi diam-diam jatuh ke alarm inexact tanpa jejak.
 */
public class PollScheduler {

    private static final String TAG = "AgyBotPoll";

    public static final String PREFS = "agybot";
    public static final String KEY_LAST_SEEN = "last_seen_iso";
    public static final String KEY_COOKIE = "cf_cookie";
    /** Penanda toast "sesi habis" sudah ditampilkan sekali (v6). */
    public static final String KEY_SESSION_TOAST_SHOWN = "session_toast_shown";

    public static final String ACTION_POLL = "id.alfisjahri.agybot.ACTION_POLL";

    /** Interval polling: 30 detik (Alfi, 28 Okt 21:26 — minta 30 atau 15 detik). */
    public static final long INTERVAL_MS = 30 * 1000L;

    public static void scheduleNext(Context ctx) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        if (am == null) {
            Log.w(TAG, "AlarmManager null — polling tidak bisa dijadwalkan");
            return;
        }
        Intent intent = new Intent(ctx, PollReceiver.class).setAction(ACTION_POLL);
        PendingIntent pi = PendingIntent.getBroadcast(ctx, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        long when = System.currentTimeMillis() + INTERVAL_MS;
        if (Build.VERSION.SDK_INT >= 31) {
            if (am.canScheduleExactAlarms()) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, when, pi);
                Log.i(TAG, "alarm exact dijadwalkan (+30 dtk)");
            } else {
                // Izin exact alarm tidak diberikan: pakai alarm inexact.
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, when, pi);
                Log.w(TAG, "exact alarm TIDAK diizinkan (Alarms & reminders belum diberikan)"
                        + " — pakai inexact, alarm bisa tertunda oleh sistem");
            }
        } else if (Build.VERSION.SDK_INT >= 23) {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, when, pi);
            Log.i(TAG, "alarm exact dijadwalkan (+30 dtk)");
        } else {
            am.setExact(AlarmManager.RTC_WAKEUP, when, pi);
            Log.i(TAG, "alarm exact dijadwalkan (+30 dtk)");
        }
    }
}
