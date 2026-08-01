# SkyCUA Android

Mobile app for monitoring Computer Use agent on your Mac.

## Requirements
- Python server running: `cd server && pip install websockets && python server.py`
- Android 8.0+ (API 26)

## Features
- Real-time screen streaming from your Mac
- Accessibility tree view
- Quick actions: type, click, press keys
- App switcher (Safari, Finder, etc.)

## Build
1. Open `android/` in Android Studio
2. Sync Gradle
3. Run on device/emulator

## Connect
1. Run server on your Mac: `python server.py`
2. Find your Mac's IP: `ifconfig | grep "inet "`
3. Open app → Enter IP → Connect
