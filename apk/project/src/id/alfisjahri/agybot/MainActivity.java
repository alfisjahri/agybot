package id.alfisjahri.agybot;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

/**
 * AgyBot — standalone native Android wrapper (NOT a PWA).
 *
 * A single WebView that loads https://agybot.alfisjahri.my.id/.
 * All navigation stays inside the WebView so the Cloudflare Access
 * login (including any identity-provider redirect) completes in the
 * same cookie jar, and the 24-hour Access session persists between
 * launches via the persistent CookieManager.
 */
public class MainActivity extends Activity {

    private static final String HOME_URL = "https://agybot.alfisjahri.my.id/";

    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int NOTIF_PERMISSION_REQUEST = 2001;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);          // AgyBot UI needs JS
        s.setDomStorageEnabled(true);          // localStorage / sessionStorage
        s.setDatabaseEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);       // pinch zoom, no on-screen buttons
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);

        // Cookies must persist: the Cloudflare Access session (24 h) lives
        // in a cookie. CookieManager persists to disk automatically; we
        // flush explicitly on pause so the session survives app restarts.
        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                // Simpan cookie sesi (Cloudflare Access) untuk PollReceiver:
                // polling latar belakang memakai cookie yang sama.
                saveSessionCookie();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view,
                                                    WebResourceRequest request) {
                // Keep EVERYTHING inside the WebView. Returning false lets
                // the WebView load the URL itself — this is what keeps the
                // Cloudflare Access login flow (and any IdP redirect) in
                // the same cookie jar instead of leaking to an external
                // browser, where the session would be lost to the app.
                return false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    String html = "<html><body style='background:#1a1a1a;color:#eaf1f8;"
                            + "font-family:sans-serif;text-align:center;padding:48px 24px'>"
                            + "<h2>AgyBot tidak bisa dibuka</h2>"
                            + "<p>Periksa koneksi internet, lalu coba lagi.</p>"
                            + "<p><a href='javascript:location.reload()' "
                            + "style='color:#007cf7'>Coba lagi</a></p>"
                            + "</body></html>";
                    view.loadDataWithBaseURL(HOME_URL, html,
                            "text/html", "UTF-8", null);
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            // File chooser for <input type="file"> — AgyBot has image input.
            @Override
            public boolean onShowFileChooser(WebView view,
                                             ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("image/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                startActivityForResult(
                        Intent.createChooser(intent, "Pilih gambar"),
                        FILE_CHOOSER_REQUEST);
                return true;
            }
        });

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(HOME_URL);
        }

        // --- v6: notifikasi routine selesai (polling tiap 1 menit) ---
        NotificationHelper.ensureChannel(this);
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    NOTIF_PERMISSION_REQUEST);
        }
        // v1.0.2: jalankan foreground service (pemegang jadwal polling),
        // bukan AlarmManager (Infinix Alfi tidak punya setelan exact alarm).
        PollService.start(this);
        // v6: poll langsung sekali saat aplikasi dibuka — baseline langsung
        // ditetapkan dan sesi habis langsung ketahuan, jangan tunggu 1 menit.
        // (Broadcast eksplisit ke receiver sendiri; exported=false tidak
        // menghalangi broadcast dalam aplikasi yang sama.)
        try {
            sendBroadcast(new Intent(this, PollReceiver.class)
                    .setAction(PollScheduler.ACTION_POLL));
        } catch (Exception e) {
            Log.w("AgyBotPoll", "poll langsung saat buka gagal: " + e.getMessage());
        }

    }

    /**
     * Simpan cookie sesi AgyBot dari WebView ke SharedPreferences, supaya
     * PollReceiver (proses latar belakang) bisa memanggil /api/notifications
     * dengan sesi Cloudflare Access yang sama. Dipanggil tiap halaman
     * selesai dimuat dan tiap onResume, jadi sesi 24 jam yang diperbarui
     * ikut tersimpan.
     *
     * v6: hanya simpan kalau cookie mengandung CF_Authorization (cookie
     * sesi Access yang sebenarnya). Di v2-v5, string cookie mentah disimpan
     * tanpa validasi — kalau WebView belum login, tidak ada yang tersimpan
     * dan polling gagal diam-diam. Hasilnya dicatat ke logcat (tag
     * AgyBotPoll) supaya bisa didiagnosis; nilai cookie tidak pernah di-log.
     */
    private void saveSessionCookie() {
        try {
            String cookie = CookieManager.getInstance().getCookie(HOME_URL);
            if (cookie != null && cookie.contains("CF_Authorization=")) {
                SharedPreferences prefs = getSharedPreferences(
                        PollScheduler.PREFS, MODE_PRIVATE);
                prefs.edit().putString(PollScheduler.KEY_COOKIE, cookie).apply();
                Log.i("AgyBotPoll", "cookie CF_Authorization disimpan dari WebView (len="
                        + cookie.length() + ")");
            } else {
                Log.w("AgyBotPoll", "WebView belum punya cookie CF_Authorization (cookie="
                        + (cookie == null ? "null"
                                : "len " + cookie.length() + ", tanpa CF_Authorization")
                        + ") — polling tidak akan jalan sampai login selesai");
            }
        } catch (Exception e) {
            Log.w("AgyBotPoll", "saveSessionCookie gagal: " + e.getMessage());
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        // Izin notifikasi opsional: kalau ditolak, polling tetap jalan tapi
        // notifikasi tidak tampil sampai Alfi mengizinkan di Pengaturan.
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            ClipData clip = data.getClipData();
            if (clip != null) {
                results = new Uri[clip.getItemCount()];
                for (int i = 0; i < clip.getItemCount(); i++) {
                    results[i] = clip.getItemAt(i).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
        }
        filePathCallback.onReceiveValue(results);
        filePathCallback = null;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webView != null) {
            webView.onPause();
        }
        // Flush cookies to disk now so the Cloudflare Access session
        // survives the app being closed and reopened.
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
        }
        // Sesi Access bisa diperbarui saat aplikasi dibuka: simpan ulang.
        saveSessionCookie();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
