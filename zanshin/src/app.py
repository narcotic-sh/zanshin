import sys
import threading
import time
import os
import json
import logging
import argparse
import sqlite3
import webbrowser
import subprocess
from collections import deque
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from flask import send_from_directory
import zmq
from termcolor import colored
import warnings
warnings.filterwarnings("ignore", message=".*Matplotlib.*")
warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*torchaudio.*", category=UserWarning) # Suppress torchaudio deprecation warnings

from diarize_loop import diarize_loop
from metadata_loop import metadata_loop
import db
import config
import shared_dict
import rust_comms
from releases_manager import ZanshinReleaseManager
from stream_local_file import stream_local_file
from misc import (
    extract_video_id,
    router_to_all_dealers,
    collect_dealers,
    get_media_types,
    get_file_hash,
    create_bookmark_data,
    get_filename,
    router_to_dealer,
    get_zanshin_application_support_path,
    MarkerManager,
    get_file_extension,
    is_supported_format,
    check_internet_connection,
    create_or_clean_dir
)

# Flask server setup
cli = sys.modules["flask.cli"]
cli.show_server_banner = lambda *args, **kwargs: None
log = logging.getLogger("werkzeug")
log.disabled = True
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
socketio = SocketIO(app, cors_allowed_origins="*")

# Flask state
connected_clients = deque()

# ZMQ state
context = None
socket = None
worker_identities = set()

# Zanshin version
version = None

#######################################################################
#   Fetch Zanshin version
#######################################################################

@app.route("/api/zanshin_version", methods=["GET"])
def get_zanshin_version_endpoint():
    return jsonify({"version": version}), 200

#######################################################################
#   Submission / retry
#######################################################################

@app.route("/api/submit_youtube", methods=["POST"])
def submit_youtube_endpoint():
    data = request.json
    youtube_url = data["url"]
    id = db.submit_job("youtube", extract_video_id(youtube_url), "video")
    router_to_all_dealers(socket, worker_identities, "new_job_submission")
    socketio.emit(
        "new_job_submission", {"timestamp": time.time() * 1000}
    )  # milliseconds
    return jsonify({"id": id}), 202

@app.route("/api/check_media_item_exists", methods=["POST"])
def check_media_item_exists_endpoint():
    data = request.json
    video_id = data["video_id"]
    id = db.check_media_item_exists(video_id)
    if id:
        return jsonify({"id": id}), 200
    else:
        return "", 404

@app.route("/api/retry_processing", methods=["POST"])
def retry_processing_endpoint():
    data = request.json

    id = data["id"]
    jobs_to_retry = data["jobs_to_retry"]
    force_get_raw_stream = data["force_get_raw_stream"]

    if "metadata_refetch" in jobs_to_retry:
        db.refetch_metadata(id, force_get_raw_stream)
        router_to_dealer(socket, "metadata_loop".encode(), "new_job_submission")
        socketio.emit(
            "new_job_submission", {"timestamp": time.time() * 1000}
        )  # milliseconds

    if "processing_retry" in jobs_to_retry:
        db.retry_processing(id)
        router_to_dealer(socket, "diarize_loop".encode(), "new_job_submission")
        socketio.emit(
            "new_job_submission", {"timestamp": time.time() * 1000}
        )  # milliseconds

    return "", 200

#######################################################################
#   Open local file dialog
#######################################################################

@app.route("/api/open_file", methods=["GET"])
def open_file_endpoint():
    def open_dialog():
        try:
            if config.RUNNING_DARWIN:
                # macOS: Use AppleScript
                file_path_script = """
                set the_file to choose file with prompt "Select an audio or video file"
                set file_path to POSIX path of the_file
                return file_path
                """

                # Run first script to get file path
                file_result = subprocess.run(
                    ["osascript", "-e", file_path_script], capture_output=True, text=True
                )
                if file_result.returncode != 0:
                    print("File dialog cancelled or error occurred")
                    return

                file_path = file_result.stdout.strip()

                # Get creation timestamp on macOS
                timestamp_cmd = f"stat -f %B '{file_path}'"
                timestamp_result = subprocess.run(
                    timestamp_cmd, shell=True, capture_output=True, text=True
                )
                creation_timestamp = timestamp_result.stdout.strip()

            elif config.RUNNING_WSL:
                # WSL: Use PowerShell to open Windows file dialog
                powershell_script = '''
                [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
                Add-Type -AssemblyName System.Windows.Forms
                $dialog = New-Object System.Windows.Forms.OpenFileDialog
                $dialog.Filter = "Audio and Video files (*.mp3;*.wav;*.ogg;*.aac;*.m4a;*.opus;*.mp4;*.webm;*.ogv;*.mpg;*.mpeg)|*.mp3;*.wav;*.ogg;*.aac;*.m4a;*.opus;*.mp4;*.webm;*.ogv;*.mpg;*.mpeg|Audio files (*.mp3;*.wav;*.ogg;*.aac;*.m4a;*.opus)|*.mp3;*.wav;*.ogg;*.aac;*.m4a;*.opus|Video files (*.mp4;*.webm;*.ogv;*.mpg;*.mpeg)|*.mp4;*.webm;*.ogv;*.mpg;*.mpeg|All Files (*.*)|*.*"
                $dialog.Title = "Select an audio or video file"
                $dialog.Multiselect = $false
                $result = $dialog.ShowDialog()
                if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
                    [Console]::WriteLine($dialog.FileName)
                }
                '''

                # Call PowerShell from WSL with proper encoding
                file_result = subprocess.run(
                    ["powershell.exe", "-Command", powershell_script],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=60
                )

                if file_result.returncode != 0 or not file_result.stdout.strip():
                    print("File dialog cancelled or error occurred")
                    return

                windows_path = file_result.stdout.strip()
                print(f"Windows path received: {repr(windows_path)}")  # Debug output

                # Convert Windows path to WSL path using wslpath
                wsl_result = subprocess.run(
                    ["wslpath", "-u", windows_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )

                if wsl_result.returncode == 0:
                    file_path = wsl_result.stdout.strip()
                    print(f"WSL path converted: {repr(file_path)}")  # Debug output
                else:
                    print(f"wslpath conversion failed: {wsl_result.stderr}")
                    # Manual conversion fallback
                    if len(windows_path) >= 2 and windows_path[1] == ':':
                        drive = windows_path[0].lower()
                        path_remainder = windows_path[2:].replace('\\', '/')
                        file_path = f"/mnt/{drive}{path_remainder}"
                        print(f"Manual conversion: {repr(file_path)}")  # Debug output
                    else:
                        file_path = windows_path

                # Get creation timestamp on WSL (using stat command)
                try:
                    creation_timestamp = str(int(os.path.getctime(file_path)))
                except OSError as e:
                    print(f"Error getting file creation time: {e}")
                    # Fallback to current time
                    creation_timestamp = str(int(time.time()))

            else:
                # Linux: Try multiple dialog tools in order of preference
                file_path = None
                dialog_tools = [
                    # Try kdialog first (better for KDE environments)
                    {
                        'name': 'kdialog',
                        'cmd': [
                            'kdialog',
                            '--getopenfilename',
                            '.',
                            'Audio and Video files (*.mp3 *.wav *.ogg *.aac *.m4a *.opus *.mp4 *.webm *.ogv *.mpg *.mpeg)|Audio files (*.mp3 *.wav *.ogg *.aac *.m4a *.opus)|Video files (*.mp4 *.webm *.ogv *.mpg *.mpeg)|All files (*)'
                        ]
                    },
                    # Try zenity second (better for GNOME environments)
                    {
                        'name': 'zenity',
                        'cmd': [
                            'zenity',
                            '--file-selection',
                            '--title=Select an audio or video file',
                            '--file-filter=Audio and Video files | *.mp3 *.wav *.ogg *.aac *.m4a *.opus *.mp4 *.webm *.ogv *.mpg *.mpeg',
                            '--file-filter=Audio files | *.mp3 *.wav *.ogg *.aac *.m4a *.opus',
                            '--file-filter=Video files | *.mp4 *.webm *.ogv *.mpg *.mpeg',
                            '--file-filter=All files | *'
                        ]
                    },
                    # Try Xdialog as fallback (works with various DEs)
                    {
                        'name': 'Xdialog',
                        'cmd': [
                            'Xdialog',
                            '--title', 'Select an audio or video file',
                            '--fselect', '.', '20', '80'
                        ]
                    }
                ]

                for tool in dialog_tools:
                    try:
                        # Check if the tool is available
                        subprocess.run(['which', tool['name']], check=True, capture_output=True)

                        # Run the dialog
                        file_result = subprocess.run(
                            tool['cmd'],
                            capture_output=True,
                            text=True,
                            timeout=300  # 5 minute timeout
                        )

                        if file_result.returncode == 0 and file_result.stdout.strip():
                            file_path = file_result.stdout.strip()
                            print(f"Successfully used {tool['name']} for file selection")
                            break

                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Tool not available, try next one
                        continue

                if not file_path:
                    # No GUI dialog tools available
                    print("No GUI dialog tools available (tried kdialog, zenity, Xdialog).")
                    return

                # Get creation timestamp on Linux
                creation_timestamp = str(int(os.path.getctime(file_path)))

            # Common processing for all platforms
            print(f"Final file path for processing: {repr(file_path)}")  # Debug output

            # Verify file exists before proceeding
            if not os.path.exists(file_path):
                print(f"Error: File does not exist at path: {file_path}")
                socketio.emit("file_not_found")
                return

            filename = get_filename(file_path)
            file_extension = get_file_extension(filename)

            # Check if the file extension is supported (playable in browser)
            if not file_extension or not is_supported_format(file_extension):
                socketio.emit("file_extension_invalid")
                return

            # Check if the file is empty (happens with Dropbox online-only (not downloaded) files)
            if os.path.getsize(file_path) == 0:
                socketio.emit("file_empty")
                return

            file_hash = get_file_hash(file_path)
            id = db.check_file_exists(file_hash)

            if id:
                socketio.emit("file_already_exists", {"id": id})
                return

            media_types = get_media_types(file_path)
            media_type = (
                "video"
                if ("audio" in media_types and "video" in media_types)
                or ("video" in media_types)
                else "audio"
            )

            # Create bookmark data (handles Darwin vs non-Darwin internally)
            bookmark = create_bookmark_data(file_path)

            id = db.submit_job(
                source="local",
                uri=bookmark,
                filename=filename,
                media_type=media_type,
                file_hash=file_hash,
                file_creation_timestamp=creation_timestamp,
            )

            if id:
                socketio.emit("file_submitted", {"id": id})
                router_to_all_dealers(socket, worker_identities, "new_job_submission")
                socketio.emit("new_job_submission", {"timestamp": time.time() * 1000})

        except Exception as e:
            print(f"Error opening file dialog: {str(e)}")
            import traceback
            traceback.print_exc()

    dialog_thread = threading.Thread(target=open_dialog)
    dialog_thread.daemon = True
    dialog_thread.start()

    return "", 200

#######################################################################
#   Fetch previews
#######################################################################

@app.route("/api/fetch_media_previews", methods=["GET"])
def fetch_media_previews_endpoint():
    preview_data = db.fetch_media_previews()

    processor_status = shared_dict.read('processor_status')
    active_job_status = shared_dict.read('active_job_status')

    return_data = {
        "processing": preview_data["processing"],
        "queued": preview_data["queued"],
        "failed": preview_data["failed"],
        "success": preview_data["success"],
        "processor_status": processor_status,
        "active_job_status": active_job_status,
    }

    return jsonify(return_data), 200

#######################################################################
#   Fetch media item
#######################################################################

welcome_dialog_shown = False

@app.route("/api/fetch_media_item", methods=["POST"])
def fetch_media_item_endpoint():
    global welcome_dialog_shown

    data = request.json
    id = data["id"]
    media_data = db.fetch_media_item(id, router_socket=socket)
    if media_data:
        # Show welcome dialog only on first call, if first_run is True, AND if processing status for this id is success
        show_welcome = (shared_dict.read('first_run') and not welcome_dialog_shown and media_data.get('status') == 'success')
        if show_welcome:
            welcome_dialog_shown = True

        return_data = {
            "media_data": media_data,
            "processor_status": shared_dict.read('processor_status'),
            "active_job_status": shared_dict.read('active_job_status'),
            "show_welcome_dialog": show_welcome,
        }
        return jsonify(return_data), 200
    else:
        return "", 404

#######################################################################
#   Delete media item
#######################################################################

@app.route("/api/delete_media_item", methods=["POST"])
def delete_media_item_endpoint():
    data = request.json
    ids = data["ids"]

    def delete_thread():
        try:
            db.delete_media_item(ids)
        except Exception as e:
            print(f"Error deleting media items: {str(e)}")
        finally:
            socketio.emit("delete_complete", ids)

    # Launch deletion in a separate thread
    deletion_thread = threading.Thread(target=delete_thread, daemon=True)
    deletion_thread.start()

    # Return immediately
    return "", 202

#######################################################################
#   Media item-specific settings (colorset, selected speakers, etc.)
#######################################################################

@app.route("/api/set_colorset", methods=["POST"])
def set_colorset_endpoint():
    data = request.json
    if not data or "id" not in data or "colorset_num" not in data:
        return "", 400

    id = data["id"]
    colorset_num = data["colorset_num"]

    db.set_colorset(id, colorset_num)
    return "", 200

@app.route("/api/set_speaker_visibility", methods=["POST"])
def set_speaker_visibility_endpoint():
    data = request.json
    if not data or "id" not in data or "speaker_visibility" not in data:
        return "", 400

    id = data["id"]
    speaker_visibility = data["speaker_visibility"]

    db.set_speaker_visibility(id, speaker_visibility)
    return "", 200

@app.route("/api/set_playback_position", methods=["POST"])
def set_playback_position_endpoint():
    data = request.json
    if not data or "id" not in data or "playback_position" not in data:
        return "", 400

    id = data["id"]
    playback_position = data["playback_position"]

    db.set_playback_position(id, playback_position)
    return "", 200

@app.route("/api/set_speaker_speeds", methods=["POST"])
def set_speaker_speeds_endpoint():
    data = request.json
    if not data or "id" not in data or "speaker_speeds" not in data:
        return "", 400

    id = data["id"]
    speaker_speeds = data["speaker_speeds"]

    db.set_speaker_speeds(id, speaker_speeds)
    return "", 200

@app.route("/api/set_skip_silences", methods=["POST"])
def set_skip_silences_endpoint():
    data = request.json
    if not data or "id" not in data or "skip_silences" not in data:
        return "", 400

    id = data["id"]
    skip_silences = data["skip_silences"]

    db.set_skip_silences(id, skip_silences)
    return "", 200

@app.route("/api/set_zoom_window", methods=["POST"])
def set_zoom_window_endpoint():
    data = request.json
    if not data or "id" not in data or "zoom_window" not in data:
        return "", 400

    id = data["id"]
    zoom_window = data["zoom_window"]

    db.set_zoom_window(id, zoom_window)
    return "", 200

@app.route("/api/set_duration", methods=["POST"])
def set_duration_endpoint():
    data = request.json
    if not data or "id" not in data or "duration" not in data:
        return "", 400

    id = data["id"]
    duration = data["duration"]

    db.set_duration(id, duration)
    return "", 200

@app.route("/api/set_auto_skip_disabled_speakers", methods=["POST"])
def set_auto_skip_disabled_speakers_endpoint():
    data = request.json
    if not data or "id" not in data or "auto_skip_disabled_speakers" not in data:
        return "", 400

    id = data["id"]
    auto_skip_disabled_speakers = data["auto_skip_disabled_speakers"]

    db.set_auto_skip_disabled_speakers(id, auto_skip_disabled_speakers)
    return "", 200

#######################################################################
#   Settings
#######################################################################

@app.route("/api/get_setting", methods=["GET"])
def get_setting_endpoint():
    key = request.args.get("key")
    if not key:
        return "", 400
    value = db.get_setting(key)
    return jsonify({key: value}), 200

@app.route("/api/set_setting", methods=["POST"])
def set_setting_endpoint():
    data = request.json
    if not data or "key" not in data or "value" not in data:
        return "", 400

    key = data["key"]
    value = data["value"]

    db.set_setting(key, value)
    socketio.emit("settings_update")
    return "", 200

@app.route("/api/set_multiple_settings", methods=["POST"])
def set_multiple_settings_endpoint():
    data = request.json
    if not data or not isinstance(data, dict):
        return "", 400

    db.set_multiple_settings(data)
    socketio.emit("settings_update")
    return "", 200

@app.route("/api/get_all_settings", methods=["GET"])
def get_all_settings_endpoint():
    return jsonify(db.get_all_settings()), 200

#######################################################################
#   Thumbnail
#######################################################################

@app.route("/api/thumbnail/<id>", methods=["GET"])
def get_thumbnail(id):
    # Check if low_res parameter is provided
    low_res = request.args.get('low_res', 'false').lower() == 'true'

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    if low_res:
        # For low_res request: prefer low_res, fallback to high_res
        cursor.execute(
            "SELECT COALESCE(thumbnail_low_res, thumbnail) as thumbnail_data FROM media WHERE id = ?",
            (id,)
        )
        etag_suffix = "-low"
    else:
        # For regular request: just return high_res
        cursor.execute("SELECT thumbnail FROM media WHERE id = ?", (id,))
        etag_suffix = ""

    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        image_data = result[0]
        response = app.response_class(
            response=image_data, status=200, mimetype="image/jpeg"
        )
        # Add cache headers
        response.headers["Cache-Control"] = "max-age=86400"  # Cache for 24 hours
        response.headers["ETag"] = f'"{id}{etag_suffix}"'
        return response
    else:
        return "", 404

#######################################################################
#   Thumbnail preview frames
#######################################################################

@app.route("/api/frame/<id>/<int:timestamp>", methods=["GET"])
def get_frame(id, timestamp):
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT frame FROM frames WHERE media_id = ? AND timestamp = ?", (id, timestamp))
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        # The frame data is already binary
        frame_data = result[0]
        # Create a response with the binary data
        response = app.response_class(
            response=frame_data, status=200, mimetype="image/jpeg"
        )
        # Add cache headers
        response.headers["Cache-Control"] = "max-age=86400"  # Cache for 24 hours
        response.headers["ETag"] = f'"{id}-{timestamp}"'
        return response
    else:
        return "", 404

#######################################################################
#   Stream local media file
#######################################################################

@app.route("/api/stream/<id>", methods=["GET"])
def stream_local_file_endpoint(id):
    return stream_local_file(id)

#######################################################################
#   Third party licenses
#######################################################################

@app.route("/THIRD_PARTY_LICENSES", methods=["GET"])
def serve_third_party_licenses():
    try:
        with open(config.THIRD_PARTY_LICENSES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # If not packaged, prepend development note
        if not config.IS_PACKAGED:
            dev_note = f"""NOTE: As you're running Zanshin development version, this THIRD_PARTY_LICENSES file does not look the same as the one that comes with the packaged macOS version. This is because license notices and attributions found in that which are not present here are for those open source components which you installed yourself, following the Zanshin development setup instructions. I.e. those components (or derived/modified versions of them) are not actually found in the Zanshin repository source tree (not copied/redistributed). However, in the packaged version, they *are* bundled, and thus require the proper attribution and license texts in the THIRD_PARTY_LICENSES file.

The THIRD_PARTY_LICENSES file that comes with the packaged macOS version can be found at <a href="/THIRD_PARTY_LICENSES_PACKAGED">{config.THIRD_PARTY_LICENSES_PACKAGED_PATH}</a>

"""
            # Convert content to HTML by escaping and preserving line breaks
            import html
            content_html = html.escape(content)
            dev_note_html = html.escape(dev_note)
            # But we want the link to remain as HTML, so we need to unescape it
            dev_note_html = dev_note_html.replace('&lt;a href=&quot;/THIRD_PARTY_LICENSES_PACKAGED&quot;&gt;', '<a href="/THIRD_PARTY_LICENSES_PACKAGED">').replace('&lt;/a&gt;', '</a>')

            full_content = f"""<html>
<head>
    <style>
        body {{
            background-color: rgb(19, 19, 19);
            color: white;
            margin: 0;
            padding: 20px;
        }}
        pre {{
            font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 0;
            line-height: 1.2;
        }}
        a {{
            color: #4A9EFF;
        }}
        a:visited {{
            color: #9A4AFF;
        }}
    </style>
</head>
<body>
    <pre>{dev_note_html}{content_html}</pre>
</body>
</html>"""
        else:
            # For packaged version, just serve as plain text
            full_content = content

        response = app.response_class(
            response=full_content,
            status=200,
            mimetype='text/html' if not config.IS_PACKAGED else 'text/plain'
        )
        if not config.IS_PACKAGED:
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
        else:
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        return response
    except FileNotFoundError:
        return "Third party licenses file not found", 404
    except Exception as e:
        return f"Error reading third party licenses: {str(e)}", 500

@app.route("/THIRD_PARTY_LICENSES_PACKAGED", methods=["GET"])
def serve_packaged_third_party_licenses():
    try:
        with open(config.THIRD_PARTY_LICENSES_PACKAGED_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        response = app.response_class(
            response=content,
            status=200,
            mimetype='text/plain'
        )
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        return response
    except FileNotFoundError:
        return "Packaged third party licenses file not found", 404
    except Exception as e:
        return f"Error reading packaged third party licenses: {str(e)}", 500

#######################################################################
#   UI serving
#######################################################################

@app.route('/', defaults={'path': 'index.html'})
@app.route('/<path:path>')
def serve_static(path):
    try:
        return send_from_directory('ui_dist', path)
    except:
        # Fallback for SPA routing - return index.html for paths that don't exist as files
        return send_from_directory('ui_dist', 'index.html')

#######################################################################
#   Websocket handlers
#######################################################################

@socketio.on("connect")
def handle_connect():
    connected_clients.append(request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    if request.sid in connected_clients:
        connected_clients.remove(request.sid)

#######################################################################
#   main()
#######################################################################

def main(dev_mode=False, no_browser=False, first_run=False, port=1776):
    global context, socket, worker_identities, version

    shared_dict.write('first_run', first_run)

    # ~/Library/Application Support/Zanshin
    app_support = None

    # Read and store version number
    if not dev_mode:
        app_support = get_zanshin_application_support_path()
        # Get contents of ~/Library/Application Support/Zanshin/zanshin/VERSION
        version_file = os.path.join(app_support, 'zanshin', 'VERSION')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()
    else:
        # ../VERSION
        version_file = os.path.join(os.path.dirname(config.SCRIPT_DIR), 'VERSION')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()

    # Init db
    db.initialize()

    if dev_mode:
        db.vacuum()
        # In non-dev mode (macOS packaged), the Rust Tauri code will do the vacuum on exit

    # Cleanup jobs that were processing when app was shutdown
    db.cleanup_interrupted_jobs()

    # Create temp directory / clean it if it already exists
    create_or_clean_dir(config.PROCESSING_TEMP_DIR)

    # ZeroMQ setup
    address = "tcp://127.0.0.1:5545"
    context = zmq.Context()
    socket = context.socket(zmq.ROUTER)
    socket.bind(address)

    print(f'Zanshin v{version} starting on port {port}... {"(development mode)" if dev_mode else ""}')

    # Job processing threads
    diarization_thread = threading.Thread(target=diarize_loop, args=(address,), daemon=True)
    metadata_thread = threading.Thread(target=metadata_loop, args=(address,), daemon=True)
    diarization_thread.start()
    metadata_thread.start()

    # Wait for dealers to connect to router
    worker_identities = collect_dealers(socket, expected_count=2)

    # Thread to relay dealers' messages to client
    def parent_listener():
        while True:
            _ = socket.recv()  # Identity frame
            content = socket.recv()
            message = content.decode("utf-8")
            data = json.loads(message)
            socketio.emit(data["message_type"], data["content"])

    listener_thread = threading.Thread(target=parent_listener, daemon=True)
    listener_thread.start()

    # Update checker thread
    def update_checker_thread_func():
        update_found = False
        while not update_found:
            try:
                # Check internet connection
                if not check_internet_connection():
                    time.sleep(60)  # Wait 1 minute before checking again
                    continue

                # Check for interrupted updates
                marker_manager = MarkerManager(app_support)
                if marker_manager.handle_interrupted_update():
                    print("Detected and cleaned up an interrupted update")

                # Start update process
                marker_manager.create_marker("update_check")

                # Get current version
                version_file = os.path.join(app_support, 'zanshin', 'VERSION')
                with open(version_file, "r") as file:
                    curr_version = file.read().strip()

                # Check if update available
                manager = ZanshinReleaseManager()
                update = manager.get_update_info(curr_version)

                if update and update['download_url']:
                    # Progress to download stage
                    marker_manager.progress_to_next_stage("update_check", "download")

                    api_url = update['download_url']
                    filename = update['filename']
                    save_path = os.path.join(app_support, filename)

                    # Download update tarball
                    success = manager.download_asset(api_url, save_path)

                    if success:
                        # Progress to extraction stage
                        marker_manager.progress_to_next_stage("download", "extraction")

                        # Extract tarball (multithreaded) ; will create a dir called 'update'
                        env = os.environ.copy()
                        env['XZ_DEFAULTS'] = "-T 0"
                        subprocess.run(['tar', '-xf', save_path, '-C', app_support], env=env, check=True)

                        # Delete tarball
                        os.remove(save_path)

                        # Inside 'update' folder will be another tarball called update.tar.xz ; extract that too
                        update_folder = os.path.join(app_support, 'update')
                        update_tarball = os.path.join(update_folder, 'update.tar.xz')
                        subprocess.run(['tar', '-xf', update_tarball, '-C', update_folder], env=env, check=True)

                        # Extracting update.tar.xz inside update folder will create a folder called zanshin
                        # The update.py script that runs at app exit will rsync that folder with the main one at ~/Library/App Support/Zanshin/zanshin

                        # Delete update.tar.xz
                        os.remove(update_tarball)

                        # Progress to final stage - ready for update.py
                        marker_manager.progress_to_next_stage("extraction", "ready_for_install")

                        print(f"Successfully downloaded and extracted update for version {update['version']}")
                        update_found = True  # Stop checking after successful update
                    else:
                        marker_manager.delete_marker("download")
                        print("Failed to download update")

                else:
                    marker_manager.delete_marker("update_check")
                    # No update available, will check again in 1 minute

                # Only sleep if no update was found
                if not update_found:
                    time.sleep(60)  # Wait 1 minute before checking again

            except Exception as e:
                print(f"Error in update checker: {e}")
                # On error, wait before retrying
                if not update_found:
                    time.sleep(60)

        print("Update checker thread completed - update has been prepared")

    # Check for updates only if on macOS, not in dev mode, and ~/Library/Application Support/Zanshin exists
    if config.RUNNING_DARWIN and not dev_mode and os.path.exists(app_support) and not config.OLD_ZANSHIN:
        update_checker_thread = threading.Thread(target=update_checker_thread_func, daemon=True)
        update_checker_thread.start()

    # Notify Tauri that backend has started
    rust_comms.send({
        "status": "started app"
    })

    # Open browser to localhost:{port}
    def open_browser():
        time.sleep(1.5)

        if config.RUNNING_WSL:
            # WSL: Use PowerShell to open browser in Windows
            try:
                subprocess.run(
                    ["powershell.exe", "-Command", "Start-Process", f"http://localhost:{port}"],
                    timeout=10
                )
            except Exception as e:
                print(f"Failed to open browser via PowerShell: {e}")
                # Fallback: try cmd.exe
                try:
                    subprocess.run(
                        ["cmd.exe", "/c", "start", f"http://localhost:{port}"],
                        timeout=10
                    )
                except Exception as e2:
                    print(f"Failed to open browser via cmd.exe: {e2}")
        else:
            # other systems: use webbrowser module
            webbrowser.open(f"http://localhost:{port}")

    if not no_browser:
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    # Run Flask HTTP + Websocket server
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')
    parser.add_argument('--first-run', action='store_true', help='Indicates this is the first run of the application')
    parser.add_argument('--port', type=int, default=1776, help='Port to run the server on (default: 1776)')
    args = parser.parse_args()

    main(dev_mode=args.dev, no_browser=args.no_browser, first_run=args.first_run, port=args.port)