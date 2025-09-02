import os
import sys
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT = os.path.dirname(SCRIPT_DIR)

DB_PATH = os.path.join(ROOT, 'media.db')
SETTINGS_PATH = os.path.join(ROOT, 'settings.json')

FFMPEG_DIR = os.path.join(ROOT, 'third_party', 'ffmpeg')
FFMPEG_PATH = os.path.join(FFMPEG_DIR, 'ffmpeg')
FFPROBE_PATH = os.path.join(FFMPEG_DIR, 'ffprobe')
os.environ['PATH'] = f"{FFMPEG_DIR}:{os.environ.get('PATH', '')}"

PROCESSING_TEMP_DIR = os.path.join(SCRIPT_DIR, 'temp')

RUNNING_DARWIN = platform.system() == 'Darwin'
RUNNING_LINUX = platform.system() == 'Linux'

try:
    RUNNING_WSL = 'microsoft' in open('/proc/version', 'r').read().lower()
except:
    RUNNING_WSL = False

IS_PACKAGED = 'Library/Application Support' in SCRIPT_DIR
THIRD_PARTY_LICENSES_PATH = os.path.join(ROOT, 'THIRD_PARTY_LICENSES') if IS_PACKAGED else os.path.join(os.path.dirname(ROOT), 'THIRD_PARTY_LICENSES')

THIRD_PARTY_LICENSES_PACKAGED_PATH = os.path.join(os.path.dirname(ROOT), 'packaging', 'build', 'THIRD_PARTY_LICENSES') if not IS_PACKAGED else os.path.join(ROOT, 'THIRD_PARTY_LICENSES')