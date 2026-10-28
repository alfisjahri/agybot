package id.alfisjahri.agybot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.CookieManager;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/**
 * AgyBot v6 — polling notifikasi routine selesai.
 *
 * Perbaikan v6 (28 Okt 20:39 — polling v2-v5 TIDAK PERNAH sampai server,
 * 0 baris GET /api/notifications di log server 20:15-20:39 padahal Alfi
 * sudah install v5, buka APLIKASI-nya, battery Unrestricted):
 *
 *  Penyebab yang ditemukan dari audit kode + perilaku server:
 *  (a) Tanpa cookie Cloudflare Access yang valid, server membalas 302 ke
 *      halaman login — TERBUKTI via curl (302 ke alfisjahri.cloudflareaccess.com).
 *      HttpURLConnection v2-v5 MENGIKUTI redirect itu (default true),
 *      dapat 200 berupa HTML login, lalu gagal parse JSON dan DITELAN
 *      diam-diam oleh catch (Exception ignored) — tanpa jejak apa pun.
 *  (b) Kalau cookie di SharedPreferences kosong, doPoll return sebelum
 *      request apa pun — juga diam-diam.
 *  (c) saveSessionCookie() menyimpan string cookie mentah tanpa validasi
 *      apakah CF_Authorization ada di dalamnya.
 *
 *  Yang diubah di v6:
 *   1. Logcat di setiap titik keputusan (tag AgyBotPoll) — v2-v5 menelan
 *      semua kegagalan diam-diam. Nilai cookie TIDAK PERNAH di-log.
 *   2. setInstanceFollowRedirects(false): 302/301/403 kini terdeteksi
 *      sebagai "sesi habis", bukan diikuti lalu gagal parse JSON.
 *   3. Cookie: hanya simpan kalau mengandung CF_Authorization; kalau
 *      SharedPreferences kosong/tidak valid, doPoll mencoba baca langsung
 *      dari CookieManager WebView sebagai fallback.
 *   4. Kalau sesi habis, tampilkan SATU Toast (sekali per episode) supaya
 *      Alfi tahu harus buka aplikasi + login ulang.
 *   5. MainActivity kini memicu poll langsung saat aplikasi dibuka
 *      (baseline langsung ditetapkan, sesi habis langsung ketahuan).
 *   6. (v6 tambahan, 28 Okt 20:45) Strip Markdown dari teks notifikasi —
 *      summary "Hadir **1** ..." tampil literal di shade HP Alfi.
 *   7. (v6 tambahan, 28 Okt 20:45) Anti-banjir: kalau satu poll menemukan
 *      >1 event baru (backlog menumpuk saat HP lama tidak poll), kirim
 *      SATU notifikasi ringkasan "N routine selesai" (detail event
 *      terbaru di isinya), bukan N notifikasi sekaligus.
 *   8. (v6 tambahan, 28 Okt 20:47) Channel notifikasi BARU
 *      "agybot_routine_v2" dengan IMPORTANCE_HIGH — channel lama
 *      "routine_selesai" (v2-v5) masuk ke bagian Silent di HP Alfi;
 *      importance channel yang sudah dibuat tidak bisa diubah aplikasi.
 *
 * Poll PERTAMA setelah install hanya menetapkan baseline (server_time)
 * tanpa menampilkan notifikasi, supaya event lama tidak tiba-tiba muncul
 * semua sebagai notifikasi.
 */
public class PollReceiver extends BroadcastReceiver {

    private static final String TAG = "AgyBotPoll";
    private static final String BASE = "https://agybot.alfisjahri.my.id";

    @Override
    public void onReceive(final Context ctx, Intent intent) {
        Log.i(TAG, "alarm fired, mulai poll");
        final PendingResult pending = goAsync();
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    doPoll(ctx);
                } finally {
                    // v1.0.2: TIDAK lagi jadwalkan alarm berikutnya — jadwal
                    // dipegang PollService (foreground service). AlarmManager
                    // tidak dipakai untuk polling sejak v1.0.2 (Infinix
                    // Alfi tidak punya setelan exact alarm).
                    pending.finish();
                }
            }
        }).start();
    }

    private void doPoll(Context ctx) {
        SharedPreferences prefs = ctx.getSharedPreferences(
                PollScheduler.PREFS, Context.MODE_PRIVATE);
        String cookie = prefs.getString(PollScheduler.KEY_COOKIE, null);
        if (cookie == null || cookie.isEmpty()
                || !cookie.contains("CF_Authorization=")) {
            // Fallback: baca langsung dari cookie jar WebView.
            String cmCookie = readWebViewCookie();
            if (cmCookie != null && cmCookie.contains("CF_Authorization=")) {
                Log.i(TAG, "cookie prefs kosong/tidak valid, pakai CookieManager (len="
                        + cmCookie.length() + ")");
                cookie = cmCookie;
                prefs.edit().putString(PollScheduler.KEY_COOKIE, cookie).apply();
            } else {
                Log.w(TAG, "TIDAK ADA cookie CF_Authorization (prefs + CookieManager kosong)"
                        + " — poll dibatalkan, buka aplikasi + login dulu");
                return;
            }
        } else {
            Log.i(TAG, "cookie CF_Authorization ada di prefs (len=" + cookie.length() + ")");
        }
        String since = prefs.getString(PollScheduler.KEY_LAST_SEEN, null);
        HttpURLConnection conn = null;
        try {
            String url = BASE + "/api/notifications?limit=20";
            if (since != null && !since.isEmpty()) {
                url += "&since=" + URLEncoder.encode(since, "UTF-8");
            }
            conn = (HttpURLConnection) new URL(url).openConnection();
            // PENTING v6: jangan ikuti redirect. Tanpa cookie valid, Access
            // membalas 302 ke halaman login — itu harus terdeteksi sebagai
            // sesi habis, bukan diikuti lalu gagal parse JSON diam-diam.
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(20000);
            conn.setRequestProperty("Cookie", cookie);
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("User-Agent", "AgyBot-APK/8.0 (poll)");
            int code = conn.getResponseCode();
            Log.i(TAG, "GET " + url + " -> HTTP " + code);
            if (code == 302 || code == 301 || code == 403) {
                // Sesi Cloudflare Access habis / cookie ditolak.
                Log.w(TAG, "sesi Access tidak valid (HTTP " + code + ") — beri tahu user sekali");
                notifySessionExpired(ctx, prefs);
                return;
            }
            if (code != 200) {
                Log.w(TAG, "HTTP bukan 200: " + code + " — coba lagi poll berikutnya");
                return;
            }
            // Sesi OK lagi: reset penanda toast sesi-habis.
            prefs.edit().putBoolean(PollScheduler.KEY_SESSION_TOAST_SHOWN, false).apply();
            String body = readAll(conn.getInputStream());
            JSONObject json = new JSONObject(body);
            String serverTime = json.optString("server_time", null);

            boolean firstRun = (since == null || since.isEmpty());
            if (!firstRun) {
                JSONArray events = json.optJSONArray("events");
                int n = events != null ? events.length() : 0;
                Log.i(TAG, "dapat " + n + " event baru sejak " + since);
                // v1.0.2 (Alfi, 29 Okt 03:15): satu notifikasi PER routine,
                // bukan ringkasan — supaya semua keterangan kelihatan.
                // v1.0.3 (Alfi, 29 Okt 03:30): jeda 1 detik antar notifikasi
                // supaya tidak ketumpuk di shade saat beberapa routine
                // selesai barengan (Alfi: takut notif lain tidak kelihatan).
                for (int i = 0; i < n; i++) {
                    if (i > 0) {
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ignored) {
                        }
                    }
                    JSONObject e = events.getJSONObject(i);
                    NotificationHelper.show(ctx,
                            e.optInt("id", (int) System.currentTimeMillis() + i),
                            stripMarkdown(e.optString("title", "Routine selesai")),
                            stripMarkdown(e.optString("summary", "")));
                }
                Log.i(TAG, n + " event -> " + n + " notifikasi (satu per routine)");
            } else {
                Log.i(TAG, "poll pertama: tetapkan baseline " + serverTime
                        + " (tanpa notifikasi)");
            }
            if (serverTime != null && !serverTime.isEmpty()) {
                prefs.edit().putString(PollScheduler.KEY_LAST_SEEN, serverTime).apply();
            }
        } catch (Exception e) {
            Log.w(TAG, "poll gagal: " + e.getClass().getSimpleName() + ": " + e.getMessage());
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String readWebViewCookie() {
        try {
            return CookieManager.getInstance().getCookie(BASE + "/");
        } catch (Exception e) {
            Log.w(TAG, "CookieManager tidak bisa dibaca: " + e.getMessage());
            return null;
        }
    }

    /** Toast sekali per episode sesi-habis (jangan spam tiap menit). */
    private void notifySessionExpired(final Context ctx, SharedPreferences prefs) {
        boolean shown = prefs.getBoolean(PollScheduler.KEY_SESSION_TOAST_SHOWN, false);
        if (shown) {
            return;
        }
        prefs.edit().putBoolean(PollScheduler.KEY_SESSION_TOAST_SHOWN, true).apply();
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                try {
                    Toast.makeText(ctx.getApplicationContext(),
                            "Sesi login AgyBot habis — buka aplikasi untuk login ulang",
                            Toast.LENGTH_LONG).show();
                } catch (Exception ignored) {
                }
            }
        });
    }

    /**
     * Hapus markup Markdown dari judul/isi notifikasi (v6, 28 Okt 20:45).
     * Summary routine di server memakai Markdown ("Hadir **1** · Alpa
     * **17** ...") dan notification shade Android menampilkan teks mentah —
     * tanda ** muncul literal di HP Alfi. Bersihkan sebelum tampil.
     */
    private static String stripMarkdown(String s) {
        if (s == null) {
            return "";
        }
        String t = s;
        t = t.replaceAll("\\[([^\\]]+)\\]\\([^\\)]+\\)", "$1"); // [teks](url) -> teks
        t = t.replace("**", "").replace("__", "");              // bold
        t = t.replace("`", "");                                 // inline code
        t = t.replace("~~", "");                                // strikethrough
        t = t.replaceAll("(?m)^\\s*#{1,6}\\s+", "");             // heading
        t = t.replaceAll("\\*([^\\*]+)\\*", "$1");              // *italic*
        t = t.replaceAll("[ \\t]+", " ").trim();
        return t;
    }

    private static String readAll(InputStream in) throws Exception {
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) {
            sb.append(line);
        }
        r.close();
        return sb.toString();
    }
}
