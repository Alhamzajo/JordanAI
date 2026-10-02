# Jordan AI Android 16
هذا هو مشروع Android الذي يشغّل محرك Jordan AI داخل APK باستخدام Chaquopy. بعد تثبيت APK لا يحتاج المستخدم إلى فتح Termux أو المتصفح.

## المتطلبات
Android Studio حديث + Android SDK 36 + Python 3.13 على جهاز البناء. المشروع يستخدم compileSdk/targetSdk 36 وChaquopy 17.

## البناء
افتح المجلد في Android Studio ثم Build > Build APK(s). أو بعد توفر Gradle: `gradle :app:assembleDebug`.
الناتج: `app/build/outputs/apk/debug/app-debug.apk`

## البنية
Android Activity → Chaquopy Python → app.py → WebView محلي على 127.0.0.1:8765.
قاعدة البيانات تعمل داخل مساحة التطبيق الخاصة.
