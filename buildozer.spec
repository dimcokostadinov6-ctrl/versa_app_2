[app]
title = Veresia
package.name = veresia
package.domain = com.yourstore
source.dir = .
source.include_exts = py,kv,png,jpg,ttf,zip,txt,md,db
version = 0.4

requirements = python3,kivy,pyjnius,pillow,plyer
orientation = all
fullscreen = 0
android.archs = arm64-v8a, armeabi-v7a
android.api = 33
android.minapi = 21
p4a.branch = master

# ML Kit Digital Ink (Google)
android.gradle_dependencies = com.google.mlkit:digital-ink-recognition:19.0.0

# Интернет само за първото сваляне на модела
android.permissions = INTERNET, ACCESS_NETWORK_STATE
