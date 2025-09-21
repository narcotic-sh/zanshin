# Zanshin Development Setup Guide
This guide covers how to get Zanshin up and running for development.

It is also applicable for users trying to get Zanshin running on Windows (through WSL) and Linux. Zanshin is currently only available in packaged form for macOS (Apple Silicon). Therefore, to get it running on Windows (WSL) and Linux, you'll need to run through these steps (for now). I hope to have packaging for Windows and Linux soon, to make easy one click installs possible.

## Hardware
[Senko](https://github.com/narcotic-sh/senko) is the diarization pipeline that powers Zanshin. Currently it supports NVIDIA GPUs (`cuda`) and Macs (CoreML). If neither are present, it falls back to CPU (`cpu`) execution. Thefore, if you're on Windows (WSL) or Linux, it's best to have an NVIDIA GPU for fast diarization, or, if not, then at the very least a high-end modern CPU (ex. Ryzen 9 9950X). If you don't have an NVIDIA GPU, and only an older, slower CPU, Senko will still work, but diarization speed will be quite slow.

Support for Intel and AMD GPUs is coming soon.

## Pre-requisites
The following tools and packages are required. Please install them before continuing.
- [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) if on Windows
- NVIDIA drivers, if running on Linux or WSL and have an NVIDIA GPU
    - Check for proper install by running `nvidia-smi`
    - If on WSL, don't try to install them from _within_ WSL; simply install them in regular Windows and the GPU will automatically be passed through to WSL.
- `ffmpeg`
    - `brew install ffmpeg` on macOS
    - `sudo apt update; sudo apt install ffmpeg` on Debian-based Linux/WSL
- `clang` if on Linux or WSL
    - `sudo apt update; sudo apt install clang`, for Debian-based distros
- `git`
    - `sudo apt update; sudo apt install git` on Debian-based Linux/WSL
    - On macOS, should already have it if you have the Xcode Command Line Tools installed
- [`uv`](https://docs.astral.sh/uv/#installation)
- [`bun`](https://bun.com/docs/installation)

## Development Setup Steps
First clone the repo and `cd` into the `zanshin` folder
```
git clone https://github.com/narcotic-sh/zanshin.git
cd zanshin/zanshin
```
Create and activate a Python virtual environment
```
uv venv --python 3.11.13 .venv
source .venv/bin/activate
```
Install the dependancies (run one of the following, whichever one applies to your system)
```bash
# For NVIDIA GPUs with CUDA compute capability >= 7.5 (~GTX 16 series and newer)
uv pip install -r requirements.txt "git+https://github.com/narcotic-sh/senko.git[nvidia]"

# For NVIDIA GPUs with CUDA compute capability < 7.5 (~GTX 10 series and older)
uv pip install -r requirements.txt "git+https://github.com/narcotic-sh/senko.git[nvidia-old]"

# For Mac (macOS 14+) and CPU execution on all other platforms
uv pip install -r requirements.txt "git+https://github.com/narcotic-sh/senko.git"
```
For NVIDIA, make sure the installed driver is CUDA 12 capable (should see `CUDA Version: 12.x` in the top right of `nvidia-smi`)

Install `yt-dlp` pre-release version
```
uv pip install --pre yt-dlp
```
Build the frontend code
```
cd src/ui
bun install
bun run build
cd -
```
Now start Zanshin in dev mode (`Ctrl`+`C` for exit)
```
python src/app.py --dev
```
This will take some time to start up on this very first launch, after which the UI will open in a web browser

## Updating
If you're running on WSL or Linux (not for development) and would like updates, you'll have to do them manually for now.

Exit Zanshin if it's running, then:
```
# Go to root of repo
cd zanshin

# Get the latest code
git pull

# Update Python packages
cd zanshin/zanshin
source .venv/bin/activate
uv pip install --upgrade -r requirements.txt "git+https://github.com/narcotic-sh/senko.git[nvidia|nvidia-old]"
uv pip install --upgrade --pre yt-dlp

# Rebuild the frontend code
cd src/ui; bun install; bun run build; cd -

# Rerun Zanshin
python src/app.py --dev
```
