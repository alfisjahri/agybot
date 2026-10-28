#!/bin/bash
# AgyBot APK v1.0.3 build (channel v3 + ikon siluet putih + polling 30 detik, tanpa Firebase) — manual aapt2 + d8 (no Gradle, no network at build time).
# Re-runnable: ./build-v8.sh  (from this directory)
# Output: project/out/agybot-v1.0.3.apk  +  copied to ~/workspace/goals/agybot/files/agybot-v1.0.3.apk
# Same toolchain + same release keystore as v1/v2/v3 — v4 installs
# over v3 because package + signing key are identical, versionCode naik (8).
set -euo pipefail

export JAVA_HOME="$HOME/android-tools/jdk-17.0.21+9"
export PATH="$JAVA_HOME/bin:$PATH"

SDK="$HOME/Android/Sdk"
BT="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
PROJ="$(cd "$(dirname "$0")/project" && pwd)"
OUT="$PROJ/out"
KS="$HOME/workspace/goals/agybot/hidden_files/agybot-release.keystore"
PASSFILE="$HOME/workspace/goals/agybot/hidden_files/agybot-keystore-pass.txt"
FINAL="$HOME/workspace/goals/agybot/files/agybot-v1.0.3.apk"

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex"

echo "== 1. compile resources =="
"$BT/aapt2" compile --dir "$PROJ/res" -o "$OUT/compiled.zip"

echo "== 2. link (manifest + resources -> unsigned APK) =="
"$BT/aapt2" link -o "$OUT/app-unsigned.apk" \
    --manifest "$PROJ/AndroidManifest.xml" \
    -I "$ANDROID_JAR" \
    "$OUT/compiled.zip" \
    --auto-add-overlay \
    --java "$OUT/rjava"

echo "== 3. compile Java (all sources) =="
# shellcheck disable=SC2046
javac -encoding UTF-8 -cp "$ANDROID_JAR" -d "$OUT/classes" \
    $(find "$PROJ/src" -name '*.java') \
    $(find "$OUT/rjava" -name '*.java')

echo "== 4. dex =="
"$BT/d8" --lib "$ANDROID_JAR" --output "$OUT/dex" \
    "$OUT"/classes/id/alfisjahri/agybot/*.class

echo "== 5. add classes.dex to APK =="
(cd "$OUT/dex" && zip -q "$OUT/app-unsigned.apk" classes.dex)

echo "== 6. zipalign =="
"$BT/zipalign" -f -p 4 "$OUT/app-unsigned.apk" "$OUT/app-aligned.apk"

echo "== 7. sign (release key, SAMA dengan v1) =="
"$BT/apksigner" sign \
    --ks "$KS" --ks-pass "file:$PASSFILE" \
    --ks-key-alias agybot --key-pass "file:$PASSFILE" \
    --out "$OUT/agybot-v1.0.3.apk" "$OUT/app-aligned.apk"

echo "== 8. verify =="
"$BT/apksigner" verify --verbose "$OUT/agybot-v1.0.3.apk"

cp "$OUT/agybot-v1.0.3.apk" "$FINAL"
echo
echo "OK: $FINAL"
ls -la "$FINAL"
