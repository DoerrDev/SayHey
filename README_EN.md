# SayHey

![SayHey](resource/brand-banner.png)

[中文说明](README.md) | English

SayHey is a Windows desktop app for real-time voice translation and game subtitle overlay.

It currently supports two main workflows:

1. Live interpretation: capture your microphone, translate speech in real time, and forward translated audio into a virtual audio device.
2. Game subtitles: capture current Windows speaker or headphone output and render translated subtitles in a desktop overlay.

## Download First

If you just want to try it:

1. Open the `Releases` page of this repository.
2. Download the latest Windows package.
3. Unzip it.
4. Run `sayhey.exe`.
5. Open the in-app settings page and fill in your own service credentials.

## Engine Notes

### OpenAI engine

- Supports live interpretation
- Does not support game subtitles
- Requires your own OpenAI API key and service configuration

### Volcengine engine

- Supports live interpretation
- Supports game subtitles
- Requires your own Volcengine key

Volcengine console shortcut:

https://console.volcengine.com/speech/new/overview?projectName=default

## Before Use

### For live interpretation

- VB-Cable is recommended
- In your target app or game, set the microphone to `CABLE Output`

Default audio route:

```text
Real microphone -> SayHey -> CABLE Input -> CABLE Output -> target app
```

### For game subtitles

- VB-Cable is not required
- SayHey captures system playback audio through WASAPI loopback
- This workflow currently depends on Volcengine

## Run From Source

### Requirements

- Windows
- Python 3.11 or newer

### Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### Start the GUI

```powershell
python main.py
```

On first run, the app creates `settings.json` automatically if it does not exist yet. You can also manage settings from the in-app settings dialog.

### List local audio devices

```powershell
python scripts\list_audio_devices.py
```

### CLI demo

```powershell
python scripts\realtime_s2s_voice_demo.py
```

## Build

```powershell
build\build_nuitka.bat
```

The build script generates the Windows executable directory and zip package in `dist\`.

## Notes

- This project is a desktop translation and subtitle tool. It does not inject into games.
- Bring your own API keys and any required proxy or service configuration.
