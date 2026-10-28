package id.alfisjahri.agybot;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.RingtoneManager;
import android.os.Build;

/**
 * AgyBot v6 — local notifications (no androidx, no Firebase SDK).
 *
 * Channel "agybot_routine_v2" + show(). Dipanggil PollReceiver saat polling
 * menemukan event routine selesai. Tap notifikasi membuka MainActivity.
 *
 * v1.0.1 (29 Okt 02:58): channel BARU LAGI ("agybot_routine_v3") + ikon
 * notifikasi siluet putih sendiri (R.drawable.ic_notification).
 * Alasan: (1) Alfi melaporkan ikon status bar tampil "!" bukan ikon
 * aplikasi — android.R.drawable.ic_dialog_info bukan siluet putih
 * transparan sehingga gagal render di status bar; (2) channel v2
 * ("agybot_routine_v2") sudah terlanjur dibuat di HP Alfi dan tidak bisa
 * dipastikan importance-nya, jadi pakai ID baru + uninstall bersih.
 * WAJIB: Alfi uninstall aplikasi lama dulu sebelum install v1.0.1,
 * supaya semua channel terkunci ikut terhapus.
 */
public class NotificationHelper {

    /** v1.0.1: channel baru (ganti "agybot_routine_v2" + "routine_selesai"). */
    public static final String CHANNEL_ID = "agybot_routine_v3";

    /** ID notifikasi ringkasan saat >1 event baru dalam satu poll (v6). */
    public static final int SUMMARY_ID = 900001;

    public static void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager)
                    ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) {
                return;
            }
            // v1.0.1: HAPUS kedua channel lama (v2-v5 + v6-v8) supaya tidak
            // ada lagi notifikasi yang nyangkut di channel terkunci.
            try {
                nm.deleteNotificationChannel("routine_selesai");
            } catch (Exception ignored) {
            }
            try {
                nm.deleteNotificationChannel("agybot_routine_v2");
            } catch (Exception ignored) {
            }
            if (nm.getNotificationChannel(CHANNEL_ID) == null) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL_ID, "Routine selesai",
                        NotificationManager.IMPORTANCE_HIGH);
                ch.setDescription("Notifikasi saat routine AgyBot selesai");
                nm.createNotificationChannel(ch);
            }
        }
    }

    public static void show(Context ctx, int id, String title, String text) {
        ensureChannel(ctx);
        Intent intent = new Intent(ctx, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            b = new Notification.Builder(ctx, CHANNEL_ID);
        } else {
            b = new Notification.Builder(ctx);
        }
        b.setContentTitle(title)
         .setContentText(text)
         .setSmallIcon(R.drawable.ic_notification)
         .setContentIntent(pi)
         .setAutoCancel(true)
         // v7 (28 Okt 21:02): paksa bunyi + getar + heads-up. Channel
         // "agybot_routine_v2" sudah IMPORTANCE_HIGH, tapi notifikasi v6
         // tetap masuk Silent di HP Alfi — jadi paksa juga dari sisi
         // Builder (priority HIGH + defaults ALL = suara + getar).
         // v8 (28 Okt 21:27): naikkan ke PRIORITY_MAX + setSound +
         // setVibrate eksplisit (di API 26+ suara diatur channel, tapi
         // di beberapa perangkat Samsung ini membantu memaksa bunyi).
         .setPriority(Notification.PRIORITY_MAX)
         .setDefaults(Notification.DEFAULT_ALL)
         .setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
         .setVibrate(new long[]{0, 500, 200, 500})
         .setStyle(new Notification.BigTextStyle().bigText(text));

        NotificationManager nm = (NotificationManager)
                ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(id, b.build());
        }
    }
}
