[app]
title = Veresiya
package.name = veresiya
package.domain = org.dimcho
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ttf,otf,wav,mp3,mp4,txt,db,json
source.exclude_dirs = tests,__pycache__
source.main = main.py
version = 0.1.0
requirements = python3,kivy,cython,pillow
orientation = portrait
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET
android.allow_cleartext_traffic = 1
android.archs = armeabi-v7a,arm64-v8a
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 0

[python]
android_runnable = 1

[android]
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2
sdk_dir = $ANDROID_SDK_ROOT
ndk_dir = $ANDROID_NDK_HOME
android.sdk_path = $ANDROID_SDK_ROOT
android.ndk_path = $ANDROID_NDK_HOME
android.accept_sdk_license = True
