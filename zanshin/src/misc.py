import re
import json
import zmq
import base64
import sys
import av
import os
import pwd
import config
import ffmpeg
import requests
import xxhash
import subprocess
import numpy as np
import shared_dict
import cv2
from PIL import Image
import io
import tempfile
import shutil
from pathlib import Path

if config.RUNNING_DARWIN:
    import Foundation

#######################################################################
#   misc
#######################################################################

def extract_video_id(url):
    youtube_regex = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    if match:
        return match.group(1)
    return None

def extract_yt_error(error_str):
    pattern = r'\[youtube\] .{11}: (.*)'
    match = re.search(pattern, error_str)
    if match:
        return match.group(1)
    else:
        return error_str

def broadcast_active_job_status(socket, message_type, content=''):
    json_dict = {
        'message_type': message_type,
        'content': content
    }

    if json_dict['message_type'] == 'progress_update':
        shared_dict.write('active_job_status', json_dict['content'])
    elif json_dict['message_type'] == 'job_done':
        shared_dict.write('active_job_status', None)

    # Send message out to client
    dealer_to_router(socket, json.dumps(json_dict))

def get_filename(filepath):
    return os.path.basename(filepath)

def get_file_hash(filepath):
    h = xxhash.xxh3_64()
    with open(filepath, 'rb') as f:
        # 64KB chunks
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def get_http_status_code(url):
    try:
        response = requests.get(url, timeout=10)
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None

def get_file_extension(file_path):
   filename = os.path.basename(file_path)
   dot_position = filename.rfind('.')
   if dot_position <= 0:
       return None
   return filename[dot_position:]

def is_supported_format(extension):
   if extension is None:
       return False

   supported_media_formats = [
       # Audio Formats
       ".mp3",
       ".wav",
       ".ogg",
       ".aac",
       ".m4a",
       ".opus",

       # Video Formats
       ".mp4",
       ".webm",
       ".ogv",
       ".mpg",
       ".mpeg"
   ]

   # Ensure the extension has a leading period
   if not extension.startswith("."):
       extension = "." + extension

   return extension.lower() in supported_media_formats

def check_internet_connection():
    """Check internet connection by pinging Cloudflare's DNS server (macOS only)"""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
            capture_output=True,
            timeout=5  # Additional safety timeout
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False

def create_or_clean_dir(directory_path):
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)
    os.makedirs(directory_path)

#######################################################################
#   ZeroMQ
#######################################################################

def dealer_to_router(socket, message):
    if isinstance(message, str):
        socket.send_string(message)
    else:
        socket.send(message)


def router_to_dealer(socket, identity, message):
    socket.send(identity, zmq.SNDMORE)
    if isinstance(message, str):
        socket.send_string(message)
    else:
        socket.send(message)


def router_to_all_dealers(socket, identities, message):
    for identity in identities:
        router_to_dealer(socket, identity, message)


def create_dealer_socket(parent_address, dealer_name):
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    socket.setsockopt(zmq.IDENTITY, dealer_name.encode())
    socket.connect(parent_address)
    dealer_to_router(socket, "DEALER_REGISTRATION")
    return context, socket


def collect_dealers(socket, expected_count):
    collected_identities = set()
    while len(collected_identities) < expected_count:
        identity = socket.recv()
        content = socket.recv()
        message = content.decode('utf-8')
        if message == "DEALER_REGISTRATION":
            collected_identities.add(identity)

    return collected_identities

#######################################################################
#   ffmpeg / opencv
#######################################################################

def get_media_types(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        media_types = []
        # Check for video and audio streams
        for stream in probe['streams']:
            if stream['codec_type'] == 'video' and stream.get('disposition', {}).get('attached_pic', 0) == 0:
                # Exclude attached pictures (like album art)
                if 'video' not in media_types:
                    media_types.append('video')
            elif stream['codec_type'] == 'audio':
                if 'audio' not in media_types:
                    media_types.append('audio')
        return media_types
    except ffmpeg.Error as e:
        print(f"Error probing file: {e.stderr.decode()}", file=sys.stderr)
        return []

def get_media_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
        return duration
    except ffmpeg.Error as e:
        print(f"Error occurred: {e.stderr.decode()}")
        raise
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise

def get_video_aspect_ratio(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        video_streams = [stream for stream in probe['streams']
                         if stream['codec_type'] == 'video']

        if not video_streams:
            return None

        video_stream = video_streams[0]
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        aspect_ratio = width / height
        return aspect_ratio
    except ffmpeg.Error as e:
        print(f"Error occurred: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

def extract_first_bright_frame(input_video, brightness_threshold=100, max_time=5.0):
    # Open the video file
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        return None

    # Calculate frames to sample
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_to_check = min(int(max_time * video_fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    analysis_fps = min(5, video_fps)  # Same as original function
    skip_frames = max(1, int(video_fps / analysis_fps))

    max_brightness = -1
    brightest_frame = None
    brightest_frame_idx = 0

    # Process frames sequentially
    for frame_idx in range(0, total_frames_to_check, skip_frames):
        # Skip frames efficiently
        for _ in range(skip_frames - 1):
            cap.grab()  # Just grab frame without decoding

        ret, frame = cap.read()
        if not ret:
            break

        # Fast brightness calculation with extreme downsampling
        tiny = cv2.resize(frame, (32, 32))
        avg_brightness = np.mean(tiny)

        # Track brightest frame
        if avg_brightness > max_brightness:
            max_brightness = avg_brightness
            brightest_frame = frame.copy()
            brightest_frame_idx = frame_idx

        # Return this frame if threshold exceeded
        if avg_brightness > brightness_threshold:
            cap.release()
            # Encode the frame to JPEG bytes
            _, jpeg_data = cv2.imencode('.jpg', frame)
            return jpeg_data.tobytes()

    # Release video
    cap.release()

    # Fall back to brightest frame
    if brightest_frame is not None:
        # Encode the brightest frame to JPEG bytes
        _, jpeg_data = cv2.imencode('.jpg', brightest_frame)
        return jpeg_data.tobytes()

    return None

def extract_first_bright_frame_av(input_video, brightness_threshold=100, max_time=5.0):
    """
    Extract first bright frame using av library (same as extract_thumbnail_previews_local)
    Need this becuase on Linux, the regular function above doesn't work
    (see https://github.com/opencv/opencv/issues/24430)
    """
    try:
        # Open video container
        container = av.open(input_video)
        video_stream = container.streams.video[0]

        # Calculate how many frames to check based on max_time
        fps = float(video_stream.average_rate)
        max_frames = int(max_time * fps)

        # Sample every few frames for efficiency (similar to your 5fps sampling)
        skip_frames = max(1, int(fps / 5))

        max_brightness = -1
        brightest_frame_data = None
        frame_count = 0

        for frame in container.decode(video=0):
            if frame_count >= max_frames:
                break

            # Skip frames to achieve ~5fps sampling
            if frame_count % skip_frames == 0:
                # Convert to PIL Image
                img = frame.to_image()

                # Fast brightness calculation - resize to small size first
                tiny_img = img.resize((32, 32), Image.Resampling.NEAREST)
                avg_brightness = np.mean(np.array(tiny_img))

                # Track brightest frame
                if avg_brightness > max_brightness:
                    max_brightness = avg_brightness
                    # Convert to JPEG bytes
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=85)
                    brightest_frame_data = img_buffer.getvalue()

                # Return immediately if threshold exceeded
                if avg_brightness > brightness_threshold:
                    container.close()
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=85)
                    return img_buffer.getvalue()

            frame_count += 1

        container.close()
        return brightest_frame_data

    except Exception as e:
        print(f"Error in av-based frame extraction: {e}")
        return None

def extract_audio_artwork(audio_file):
    # First try using ffmpeg
    try:
        # Try to extract embedded artwork using ffmpeg
        artwork_data = (
            ffmpeg
            .input(audio_file)
            .output('pipe:', format='image2', codec='copy', map='0:v')
            .run(capture_stdout=True, quiet=True)
        )[0]

        if artwork_data and len(artwork_data) > 0:
            return artwork_data
    except ffmpeg.Error:
        pass

    # If ffmpeg fails, try with a different mapping
    try:
        artwork_data = (
            ffmpeg
            .input(audio_file)
            .output('pipe:', format='image2', codec='copy', map='0:v:0')
            .run(capture_stdout=True, quiet=True)
        )[0]

        if artwork_data and len(artwork_data) > 0:
            return artwork_data
    except ffmpeg.Error:
        pass

    # Try extracting specifically attached pictures
    try:
        artwork_data = (
            ffmpeg
            .input(audio_file)
            .output('pipe:', format='mjpeg', codec='copy', map='0:v', an=None)
            .run(capture_stdout=True, quiet=True)
        )[0]

        if artwork_data and len(artwork_data) > 0:
            return artwork_data
    except ffmpeg.Error:
        pass

    # As a fallback, use mutagen which works well for specific audio formats
    try:
        import mutagen
        from io import BytesIO

        audio = mutagen.File(audio_file)

        # Handle different audio formats and their artwork storage methods
        if audio is not None:
            # FLAC/OGG
            if hasattr(audio, 'pictures') and audio.pictures:
                return audio.pictures[0].data

            # MP3
            elif hasattr(audio, 'tags') and audio.tags:
                # Check for APIC frames (ID3 tags for artwork)
                if 'APIC:' in audio.tags:
                    return audio.tags['APIC:'].data
                for key in audio.tags.keys():
                    if key.startswith('APIC'):
                        return audio.tags[key].data

            # MP4/M4A
            elif hasattr(audio, 'tags') and 'covr' in audio.tags:
                return audio.tags['covr'][0]
    except (ImportError, Exception):
        pass

    # No artwork found
    return None

#######################################################################
#   macOS Filesystem Bookmark
#######################################################################

def create_bookmark_data(file_path):
    """
    Create bookmark data for a file path.
    On Darwin (macOS): Creates security-scoped bookmark data and encodes it as base64 string
    On other systems: Returns the file path as-is
    """
    if not config.RUNNING_DARWIN:
        # On non-Darwin systems, just return the file path as-is
        return file_path

    source_url = Foundation.NSURL.fileURLWithPath_(file_path)

    # Create the bookmark data
    bookmark_data, error = source_url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
        Foundation.NSURLBookmarkCreationWithSecurityScope,
        None,
        None,
        None
    )

    if error:
        raise Exception(f"Error creating bookmark data: {error}")

    # Convert NSData to bytes, then to base64 string
    raw_bytes = bytes(bookmark_data)
    base64_string = base64.b64encode(raw_bytes).decode('utf-8')

    return base64_string

def resolve_bookmark(bookmark_data):
    """
    Resolve bookmark data back to a file path.
    On Darwin (macOS): Resolves base64-encoded bookmark data back to file path
    On other systems: Treats bookmark_data as a direct file path
    Returns the file path if found, or None if the file no longer exists
    """
    if not config.RUNNING_DARWIN:
        # On non-Darwin systems, bookmark_data is just the file path
        if os.path.exists(bookmark_data):
            return bookmark_data
        return None

    try:
        # Convert base64 string back to bytes
        raw_bytes = base64.b64decode(bookmark_data)

        # Convert bytes back to NSData
        ns_bookmark_data = Foundation.NSData.dataWithBytes_length_(raw_bytes, len(raw_bytes))

        # Resolve the bookmark data back to a URL
        url, stale, error = Foundation.NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
            ns_bookmark_data,
            Foundation.NSURLBookmarkResolutionWithSecurityScope,
            None,
            None,
            None
        )

        if error:
            return None

        # Get the path and check if it exists
        path = url.path()
        if not os.path.exists(path):
            return None

        return path
    except Exception:
        # If anything goes wrong during resolution, the file is gone
        return None

#######################################################################
#   ~/Library/Application Support/Zanshin
#######################################################################

def get_zanshin_application_support_path():
    # Get the real home directory
    try:
        # Get the home directory from the password database (similar to libc::getpwuid)
        home_dir = pwd.getpwuid(os.getuid()).pw_dir
    except:
        # Fallback to environment variable if the above fails
        home_dir = os.environ.get('HOME', '')

    path = os.path.join(home_dir, 'Library', 'Application Support', 'Zanshin')
    return os.path.normpath(path)

#######################################################################
#   MarkerManager
#######################################################################

class MarkerManager:
    """
    Manages update process markers to track progress and handle interrupted updates.
    Creates marker files in the application support directory to indicate the current
    stage of the update process.
    """

    def __init__(self, app_support):
        """
        Initialize the MarkerManager with the application support directory path.

        Args:
            app_support (str): Path to the application support directory
                                (e.g. ~/Library/Application Support/Zanshin)
        """
        self.app_support = Path(app_support)
        self.markers_dir = self.app_support / "update_markers"

        # Create markers directory if it doesn't exist
        os.makedirs(self.markers_dir, exist_ok=True)

    def create_marker(self, stage_name):
        """
        Create a marker file for the specified update stage.

        Args:
            stage_name (str): Name of the update stage
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        with open(marker_path, 'w') as f:
            f.write(f"Update stage: {stage_name}")

    def delete_marker(self, stage_name):
        """
        Delete the marker file for the specified update stage.

        Args:
            stage_name (str): Name of the update stage
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        if marker_path.exists():
            os.remove(marker_path)

    def has_marker(self, stage_name):
        """
        Check if a marker exists for the specified update stage.

        Args:
            stage_name (str): Name of the update stage

        Returns:
            bool: True if the marker exists, False otherwise
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        return marker_path.exists()

    def get_active_markers(self):
        """
        Get a list of all active markers.

        Returns:
            list: List of marker stage names (without the .marker extension)
        """
        if not self.markers_dir.exists():
            return []

        markers = []
        for file in self.markers_dir.glob("*.marker"):
            markers.append(file.stem)

        return markers

    def clean_all_markers(self):
        """
        Remove all marker files.
        """
        if self.markers_dir.exists():
            for file in self.markers_dir.glob("*.marker"):
                os.remove(file)

    def handle_interrupted_update(self):
        """
        Handle an interrupted update by cleaning up markers and update files:
        1. Remove all marker files
        2. Remove the update directory if it exists
        3. Remove any files ending with "_update.tar.xz" in the app_support directory

        Returns:
            bool: True if an interrupted update was detected and cleaned up, False otherwise
        """
        markers = self.get_active_markers()

        if markers:
            # Clean up markers
            self.clean_all_markers()

            # Clean up update directory
            update_dir = self.app_support / "update"
            if update_dir.exists():
                shutil.rmtree(update_dir)

            # Remove any update tarballs in the app_support directory
            for file in self.app_support.glob("*_update.tar.xz"):
                try:
                    os.remove(file)
                    print(f"Removed update tarball: {file}")
                except Exception as e:
                    print(f"Failed to remove update tarball {file}: {e}")

            return True

        return False

    def progress_to_next_stage(self, current_stage, next_stage):
        """
        Progress from the current update stage to the next by removing the current
        marker and creating the next one.

        Args:
            current_stage (str): Name of the current update stage
            next_stage (str): Name of the next update stage
        """
        self.delete_marker(current_stage)
        self.create_marker(next_stage)