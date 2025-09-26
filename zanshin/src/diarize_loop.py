import os
import ffmpeg
import sqlite3
import time
import db
import json
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled
from misc import (
    broadcast_active_job_status,
    create_dealer_socket,
    get_filename,
    dealer_to_router,
    extract_yt_error
)
from senko import Diarizer
import config
import shared_dict
import rust_comms

#######################################################################
#   diarize_loop
#######################################################################

def diarize_loop(parent_address, db_path=config.DB_PATH):

    context, socket = create_dealer_socket(parent_address, "diarize_loop")

    # Create & warm up diarizer
    warmup = db.get_setting('warmup_processor')

    if warmup:
        shared_dict.write('processor_status', 'warming up')

    diarizer = Diarizer(warmup=warmup, quiet=False)

    shared_dict.write('processor_status', 'warmed up')

    dealer_to_router(socket, json.dumps({
        'message_type': 'processor_status_update',
        'content': 'warmed up'
    }))
    print('Processor warmed up')

    rust_comms.send({
        "status": "processor warmed up"
    })

    while True:

        # Grab job from db table
        job = db.fetch_job('main')

        if not job:
            while True:
                message = socket.recv_string()
                if message == "new_job_submission":
                    break
                else:
                    continue
        else:
            # Check if speaker identification is disabled
            if db.get_setting('identify_speakers') is False:
                # Skip
                continue

            # Job exists, start processing
            id = job['id']
            source = job['source']
            uri = job['uri']

            is_local_file = source == 'local'

            # Update job status from queued to processing
            db.update_diarization_job_status(id, 'processing')

            broadcast_active_job_status(socket, 'new_job_started')

            # Temp processing dir
            output_dir = config.PROCESSING_TEMP_DIR

            # Download audio if a YouTube video
            if not is_local_file:
                broadcast_active_job_status(socket, 'progress_update', {
                    'id': id,
                    'stage': 'Starting download'
                })
                downloaded_file, error = download_youtube_audio(id, uri, output_dir, socket)

                # If download failed, update DB and exit
                if downloaded_file is None:
                    db.mark_job_failed('main', id, json.dumps(error))
                    broadcast_active_job_status(socket, 'job_done', {
                        'id': id
                    })
                    # Continue to next video
                    continue

            # Decompress the audio
            broadcast_active_job_status(socket, 'progress_update', {
                'id': id,
                'stage': 'Decompressing audio'
            })
            input_file = uri if is_local_file else downloaded_file
            output_file = os.path.join(output_dir, f"{get_filename(input_file) if is_local_file else uri}.wav")
            wav_file = decompress_audio(input_file, output_file)

            # Decompression failed
            if wav_file is None:
                if not is_local_file:
                    os.remove(downloaded_file)

                db.mark_job_failed('main', id, json.dumps({
                    'type': 'no_audio',
                    'full_str': "No audio track found in file"
                }))
                broadcast_active_job_status(socket, 'job_done', {
                    'id': id
                })
                # Continue to next video
                continue

            # Decompression succeeded, so delete downloaded (compressed) audio
            if not is_local_file:
                os.remove(downloaded_file)

            # Diarize
            broadcast_active_job_status(socket, 'progress_update', {
                'id': id,
                'stage': 'Identifying speakers...'
            })
            diar_result = diarizer.diarize(wav_file, generate_colors=True)

            # Remove wav file
            os.remove(wav_file)

            # Check if no speech was detected
            if diar_result is None:
                db.mark_job_failed('main', id, json.dumps({
                    'type': 'no_speakers',
                    'full_str': "No speakers in audio!"
                }))
                broadcast_active_job_status(socket, 'job_done', {
                    'id': id
                })
                # Continue to next video
                continue

            # Convert centroids dict with numpy arrays to JSON-serializable format
            speaker_centroids = {}
            for speaker_id, centroid_array in diar_result["speaker_centroids"].items():
                speaker_centroids[speaker_id] = centroid_array.tolist()

            # Write diarization data + diarization time to db
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                update media
                set raw_segments = ?,
                    merged_segments = ?,
                    speaker_centroids = ?,
                    speaker_color_sets = ?,
                    timing_stats = ?,
                    diarization_time = ?,
                    finished_t = strftime('%s', 'now'),
                    status = 'success'
                where id = ?
                ''',
                (
                    json.dumps(diar_result["raw_segments"]),
                    json.dumps(diar_result["merged_segments"]),
                    json.dumps(speaker_centroids),
                    json.dumps(diar_result["speaker_color_sets"]),
                    json.dumps(diar_result["timing_stats"]),
                    diar_result["timing_stats"]["total_time"],
                    id
                )
            )
            conn.commit()
            conn.close()

            # Alert job done
            broadcast_active_job_status(socket, 'job_done', {
                'id': id
            })

            # Continue to next video in the queue
            continue

#######################################################################
#   download_youtube_audio
#######################################################################

def download_youtube_audio(id, video_id, output_dir, socket):
    def progress_hook(d):
        if d['status'] == 'downloading':
            downloaded = d['downloaded_bytes']
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            percent = (downloaded / total * 100) if total > 0 else 0

            if d.get('speed'):
                speed = d['speed']
                if speed > 1024*1024:
                    speed_str = f"{speed/1024/1024:.2f} MB/s"
                else:
                    speed_str = f"{speed/1024:.2f} KB/s"
            else:
                speed_str = "N/A"

            broadcast_active_job_status(socket, 'progress_update', {
                'id': id,
                'stage': 'Downloading audio',
                'progress': percent,
                'other_info': {
                    'downloaded_mb': downloaded/1024/1024,
                    'total_mb': total/1024/1024,
                    'speed': speed_str,
                }
            })

    def match_filter(info_dict, *, incomplete=False):
        """Filter out live and upcoming streams"""
        live_status = info_dict.get('live_status')
        if live_status == 'is_live':
            raise DownloadCancelled('Video is currently live streaming')
        elif live_status == 'is_upcoming':
            raise DownloadCancelled('Video is an upcoming scheduled stream')
        return None  # None means video passes the filter

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Download audio with retries
    retry_count = 0
    max_retries = 3
    downloaded_file = None
    error = {}

    while retry_count < max_retries:
        try:
            ydl_opts = {
                'progress_hooks': [progress_hook],
                'format': 'bestaudio',
                'outtmpl': os.path.join(output_dir, f'temp_{video_id}.%(ext)s'),
                'retries': 3,
                'socket_timeout': 10,
                'quiet': True,
                'noprogress': True,
                'match_filter': match_filter
            }

            # If user has allowed reading youtube browser cookies
            cookies_setting = db.get_setting('cookies_from_browser')
            if cookies_setting:
                ydl_opts['cookiesfrombrowser'] = (cookies_setting,)

            # Start download
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)  # could call download() but even that, internally, pulls all metadata using extract_info
                downloaded_file = ydl.prepare_filename(info)

            # Download was successful
            break

        except DownloadCancelled:
            error = {
                'type': 'live_stream',
                'full_str': 'Cannot download currently streaming or upcoming live streams'
            }
            break

        except Exception as e:
            error_str = str(e)

            # Age restricted video
            if check_error_str(error_str, ['age', 'sign in']):
                error = {
                    'type': 'age_restricted',
                    'full_str': extract_yt_error(error_str)
                }
                break

            # Bot guard triggered
            elif check_error_str(error_str, ['bot', 'sign in'], ['403', 'forbidden']):
                error = {
                    'type': 'bot',
                    'full_str': extract_yt_error(error_str)
                }
                break

            # Specific format not available error - try fallback once and exit
            elif check_error_str(error_str, 'requested format is not available'):
                broadcast_active_job_status(socket, 'progress_update', {
                    'id': id,
                    'stage': 'Audio-only format not available, trying low-res video+audio...'
                })

                try:
                    # Get available formats to find lowest resolution with audio
                    info_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'skip_download': True,
                    }

                    # Add cookies if available
                    if cookies_setting:
                        info_opts['cookiesfrombrowser'] = (cookies_setting,)

                    with YoutubeDL(info_opts) as ydl_info:
                        info = ydl_info.extract_info(video_url, download=False)

                        # Find combined formats (both audio and video)
                        combined_formats = []
                        for fmt in info.get('formats', []):
                            if (fmt.get('acodec') != 'none' and
                                fmt.get('vcodec') != 'none' and
                                fmt.get('height')):
                                combined_formats.append(fmt)

                        if combined_formats:
                            # Sort by height (lowest resolution first)
                            combined_formats.sort(key=lambda x: x.get('height', 0))
                            fallback_format = combined_formats[0]['format_id']

                            broadcast_active_job_status(socket, 'progress_update', {
                                'id': id,
                                'stage': f'Downloading with format {fallback_format} ({combined_formats[0].get("height", "unknown")}p)'
                            })

                            # Try downloading with the fallback format
                            ydl_opts['format'] = fallback_format

                            with YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(video_url, download=True)
                                downloaded_file = ydl.prepare_filename(info)

                            # Success with fallback format
                            break
                        else:
                            # No suitable combined formats found
                            error = {
                                'type': 'no_suitable_format',
                                'full_str': 'No suitable audio+video formats available'
                            }
                            break

                except Exception as fallback_error:
                    # Fallback attempt failed - treat as terminal error
                    error = {
                        'type': 'no_suitable_format',
                        'full_str': extract_yt_error(str(fallback_error))
                    }
                    break

            # Some other error ; note, but do not exit (keep retrying)
            else:
                error = {
                    'type': 'other',
                    'full_str': extract_yt_error(error_str)
                }

            retry_count += 1

            # Wait before retrying (only if more retries remain)
            if retry_count < max_retries:
                time.sleep(2 ** retry_count)

    return (downloaded_file, error)

#######################################################################
#   decompress_audio
#######################################################################

def decompress_audio(input_file, output_file):
    try:
        (
            ffmpeg
            .input(input_file)
            .output(output_file, acodec='pcm_s16le', ac=1, ar=16000)
            .run(quiet=True, overwrite_output=True)
        )
        return output_file
    except ffmpeg.Error:
        return None

#######################################################################
#   check_error_str
#######################################################################

def check_error_str(error_str, *conditions):
    """
    # Check if ('bot' AND 'sign in') OR ('403' AND 'forbidden') in error_str.lower()
    check_error_str(error_str, ['bot', 'sign in'], ['403', 'forbidden'])

    # Check if 'requested format is not available' in error_str.lower()
    check_error_str(error_str, 'requested format is not available')
    """
    error_lower = error_str.lower()

    for condition in conditions:
        if isinstance(condition, str):
            # Single string - just check if it's present
            if condition.lower() in error_lower:
                return True
        elif isinstance(condition, (list, tuple)):
            # List/tuple - all items must be present
            if all(term.lower() in error_lower for term in condition):
                return True

    return False