[app]
title = Veresiya
package.name = veresiya
package.domain = org.dimcho
source.dir = .
source.main = main.py
source.include_exts = py,kv,png,jpg,jpeg,ttf,otf,wav,mp3,mp4,txt,db,json
source.exclude_dirs = tests,__pycache__
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
ignore_build_tools = 1

[python]
android_runnable = 1

[android]
# Използвай съществуващия SDK (от runner-а)
sdk_dir = /usr/local/lib/android/sdk
ndk_dir = /usr/local/lib/android/sdk/ndk/25.2.9519653
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

# Фиксирани API и инструменти
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2
android.accept_sdk_license = True
