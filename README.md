# Jake Looper — MP4 Video Looper

Desktop utility for **looping MP4 files** so the result is at least as long as a **target runtime** you choose (1–10 hours). It uses **FFmpeg** with the concat demuxer and **stream copy** (`-c copy`), so encoding is fast and lossless relative to the source.

**Platform:** Windows (the app uses Windows-specific process and file-open behavior).

## Features

- Pick a **target runtime** with radio buttons: 1 hour through 10 hours (each option is that many seconds of minimum target length).
- **Add multiple MP4s**; each row shows original duration, target label, computed looped duration, status, and progress.
- **Output folder** picker; click the path label to open the folder in Explorer when set.
- **Per-file Stop / Remove** while processing; **Clear File List** stops active jobs and clears the table.
- Progress is driven from FFmpeg’s stderr (`time=…`) so the bar reflects encode/concat progress.

## How it works

For each file, the app computes how many full loops are needed so the total duration is **≥** the selected target (e.g. target 3 hours and a 20-minute clip → 9 loops). It writes a temporary `list.txt` for FFmpeg’s [concat demuxer](https://ffmpeg.org/ffmpeg-formats.html#concat), then runs:

`ffmpeg -y -f concat -safe 0 -i list.txt -c copy <output>`

Output files are named:

`<original_stem>_<TargetLabel>.mp4`

Example: target **3 Hours** and file `clip.mp4` → `clip_3Hours.mp4`.

Duration is read with **ffprobe** when available, otherwise parsed from **ffmpeg** stderr.

## Requirements

- **Windows**
- **Python 3.8+** (3.9+ recommended) with **tkinter** (included with the standard Windows installer; enable “tcl/tk” if you use a minimal distribution).
- **FFmpeg** and **FFprobe** on your **PATH**, *or* `ffmpeg.exe` / `ffprobe.exe` discoverable the same way (e.g. same folder as the script or `.exe` when using a portable layout).

Install FFmpeg system-wide (e.g. [ffmpeg.org](https://ffmpeg.org/download.html) or [Chocolatey](https://community.chocolatey.org/packages/ffmpeg)) and confirm in a terminal:

```bat
ffmpeg -version
ffprobe -version
```

## Run from source

```bat
cd path\to\your-clone
python jake_looper_gui.py
```

No Python packages are required at runtime beyond the standard library and tkinter.

## Portable Windows build (`jakelooper/`)

**Download (recommended):** [GitHub Releases — latest portable zip](https://github.com/jakeronaldsolis/jake-looper/releases/latest) includes **`jake_looper_gui.exe`**, **`ffmpeg.exe`**, and **`ffprobe.exe`**. Extract all files to one folder and double-click `jake_looper_gui.exe`.

**From this repo:** `jakelooper/jake_looper_gui.exe` is checked in; **you do not need Python**. Add official Windows **`ffmpeg.exe`** and **`ffprobe.exe`** beside it (same folder as the app). Those FFmpeg binaries are **not** committed here (they are large); get them from [ffmpeg.org](https://ffmpeg.org/download.html) or another trusted source, or use the release zip above.

## Build a standalone executable (optional)

Install PyInstaller (see `requirements.txt`), then:

```bat
pyinstaller jake_looper_gui.spec
```

The spec builds a **windowed** (`console=False`) single-folder-style executable as `dist\jake_looper_gui.exe`. You still need FFmpeg/ffprobe available at **run time** (PATH or next to the `.exe`), unless you bundle them yourself in a release zip.

## Project layout (important files)

| Item | Purpose |
|------|--------|
| `jake_looper_gui.py` | Main application |
| `jake_looper_gui.spec` | PyInstaller configuration |
| `requirements.txt` | PyInstaller (optional; for building) |
| `jakelooper/jake_looper_gui.exe` | Portable Windows build (add `ffmpeg.exe` / `ffprobe.exe` beside it) |

Build outputs (`build/`, `dist/`) and local virtualenvs are not required in version control; see `.gitignore`. Large FFmpeg binaries are ignored even under `jakelooper/`.

## Limitations

- Input file picker is **MP4 only** (`.mp4`). Other containers/codecs are not exposed in the UI.
- Looping uses **concat + copy**; very short GOPs or odd files can rarely cause awkward cuts; for difficult sources, re-encode outside this tool.

## License

[MIT](LICENSE) — Copyright (c) 2026 Jake Ronald Solis.

---

Suggestions or ports (e.g. Linux/macOS by dropping `CREATE_NO_WINDOW` / `os.startfile`) are welcome via issues or PRs if you open-source the repo.
