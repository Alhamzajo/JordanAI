# بناء Jordan AI APK

## الطريقة الأسهل: GitHub Actions

1. ارفع مجلد `android_app` إلى مستودع GitHub.
2. افتح تبويب **Actions**.
3. اختر **Build Jordan AI APK**.
4. اضغط **Run workflow**.
5. بعد نجاح البناء افتح الـrun ثم **Artifacts**.
6. نزّل `JordanAI-debug-apk`.

الـworkflow يستخدم Java 17 وPython 3.13 وAndroid API 36 وGradle 8.13.

## Android Studio

افتح مجلد `android_app` في Android Studio، وتأكد من وجود Android SDK 36، ثم نفّذ:

`./gradlew :app:assembleDebug`

الناتج:

`app/build/outputs/apk/debug/app-debug.apk`

## ملاحظة عن Termux

البناء الكامل على الهاتف ممكن نظريًا لكنه أكثر تعقيدًا بسبب أدوات Android الرسمية الموجهة عادةً لبيئات Linux/desktop. لذلك GitHub Actions أو Android Studio على الكمبيوتر هو المسار الأسهل والأكثر ثباتًا.
