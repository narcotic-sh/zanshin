import time
import sqlite3
import requests
import db
import json
from yt_dlp import YoutubeDL
from PIL import Image
import io
import os
import re
from misc import (
    broadcast_active_job_status,
    create_dealer_socket,
    get_media_duration,
    get_video_aspect_ratio,
    extract_first_bright_frame,
    extract_first_bright_frame_av,
    extract_yt_error,
    extract_audio_artwork
)
import config
import av

#######################################################################
#   metadata_loop
#######################################################################

def metadata_loop(parent_address, db_path=config.DB_PATH):

    context, socket = create_dealer_socket(parent_address, "metadata_loop")

    while True:

        # Fetch metadata gathering job
        job = db.fetch_job('metadata')

        if not job:
            while True:
                message = socket.recv_string()
                if message == "new_job_submission":
                    break
                else:
                    continue
        else:
            # Job exists
            id = job['id']

            identify_speakers_setting = db.get_setting('identify_speakers')
            if identify_speakers_setting is False:
                # If identify_speakers is False, we need to handle the processing status here since diarize_loop will skip this job entirely

                # Update job status to processing
                db.update_diarization_job_status(id, 'processing')

                broadcast_active_job_status(socket, 'progress_update', {
                    'id': id,
                    'stage': 'Fetching metadata...'
                })

            source = job['source']
            uri = job['uri']
            media_type = job['media_type']
            force_get_raw_stream = job['force_get_raw_stream']

            is_local_file = source == 'local'

            if is_local_file:
                duration = get_media_duration(uri)
                aspect_ratio = get_video_aspect_ratio(uri) if media_type == 'video' else None
                if media_type == 'video':
                    thumbnail_data = extract_first_bright_frame_av(uri) if config.RUNNING_LINUX else extract_first_bright_frame(uri)
                else:
                    thumbnail_data = extract_audio_artwork(uri)
                thumbnail_low_res_data = create_low_res_thumbnail(thumbnail_data)

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    update media
                    set aspect_ratio = ?,
                        thumbnail = ?,
                        thumbnail_low_res = ?,
                        duration = ?,
                        metadata_status = 'success'
                    where id = ?
                    ''',
                    (   aspect_ratio,
                        thumbnail_data,
                        thumbnail_low_res_data,
                        duration,
                        id
                    )
                )
                conn.commit()
                conn.close()

                if media_type == 'video' and duration:
                    storyboard_success = extract_thumbnail_previews_local(
                        uri, id, duration,
                        output_width=320,
                        interval=10.0 if duration > 5*60 else 5.0,
                        quality=50
                    )

                    # Update storyboards_fetched status
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE media SET storyboards_fetched = ? WHERE id = ?",
                        (storyboard_success, id)
                    )
                    conn.commit()
                    conn.close()

                    broadcast_active_job_status(socket, 'metadata_refresh')

            else:
                # Fetch metadata with retries
                video_info, error = get_video_info_with_retries(uri, force_get_raw_stream)

                # If metadata could not be fetched, update DB and exit
                if not video_info:
                    db.mark_job_failed('metadata', id, json.dumps(error))
                    broadcast_active_job_status(socket, 'metadata_refresh')
                    # onto next job
                    continue

                # Fetch thumbnail
                thumbnail_data = None
                thumbnail_low_res_data = None
                if video_info['thumbnail_url']:
                    thumbnail_data = fetch_online_thumbnail(video_info['thumbnail_url'])
                    thumbnail_low_res_data = create_low_res_thumbnail(thumbnail_data)

                # Write metadata into db
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    update media
                    set aspect_ratio = ?,
                        thumbnail = ?,
                        thumbnail_low_res = ?,
                        title = ?,
                        duration = ?,
                        date_uploaded = ?,
                        channel = ?,
                        channel_id = ?,
                        embeddable = ?,
                        video_stream_url = ?,
                        metadata_status = 'success',
                        chapters = ?
                    where id = ?
                    ''',
                    (   video_info['aspect_ratio'],
                        thumbnail_data,
                        thumbnail_low_res_data,
                        video_info['title'],
                        video_info['duration'],
                        video_info['date_uploaded'],
                        video_info['channel'],
                        video_info['channel_id'],
                        video_info['embeddable'],
                        video_info['video_stream_url'],
                        json.dumps(video_info['chapters']),
                        id
                    )
                )
                conn.commit()
                conn.close()

            # Alert client of new metadata
            broadcast_active_job_status(socket, 'metadata_refresh')

            # Process storyboards
            if not is_local_file and not force_get_raw_stream:
                if media_type == 'video' and video_info.get('storyboard_available'):
                    storyboard_success = fetch_youtube_thumbnail_previews(uri, id, video_info['duration'], video_info.get('storyboard_subimage_resolution'))

                    # Update storyboards_fetched status
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE media SET storyboards_fetched = ? WHERE id = ?",
                        (storyboard_success, id)
                    )
                    conn.commit()
                    conn.close()

                    broadcast_active_job_status(socket, 'metadata_refresh')

            if identify_speakers_setting is False:
                # Mark the main processing job as success
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    update media
                    set finished_t = strftime('%s', 'now'),
                        status = 'success'
                    where id = ?
                    ''',
                    (id,)
                )
                conn.commit()
                conn.close()

                # Alert job done
                broadcast_active_job_status(socket, 'job_done', {
                    'id': id
                })

            # Onto next job
            continue

#######################################################################
#   get_video_info
#######################################################################

def get_video_info(video_id, force_get_raw_stream):
    if not video_id.startswith(('http://', 'https://')):
        url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        url = video_id

    ydl_opts = {
        'no_warnings': True,
        'skip_download': True,
        'quiet': True,
        'noprogress': True,
    }

    # If user has allowed reading youtube browser cookies
    cookies_setting = db.get_setting('cookies_from_browser')
    if cookies_setting:
        ydl_opts['cookiesfrombrowser'] = (cookies_setting,)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        width = info.get('width')
        height = info.get('height')
        title = info.get('title', '') or ''
        duration = info.get('duration', 0) or 0
        thumbnail_url = info.get('thumbnail', None) or None
        date_uploaded = info.get('upload_date', '') or ''
        channel = info.get('uploader', '') or info.get('channel', '') or ''
        channel_id = info.get('channel_id', '') or info.get('uploader_id', '') or ''
        embeddable = info.get('playable_in_embed', None) or None
        chapters = info.get('chapters') or []

        # Filter out "<Untitled Chapter 1>" chapters
        chapters = [chapter for chapter in chapters if chapter.get('title') != '<Untitled Chapter 1>']

        # TODO: Put this behind a setting
        # Verify chapters are manual, not auto-generated
        # description = info.get('description', '')
        # if chapters and description:
        #     if not are_chapters_manual(description):
        #         chapters = []  # Reject auto-generated chapters

        # Get video stream URL if not embeddable
        video_stream_url = None
        if not embeddable or force_get_raw_stream:
            # Look for a combined audio+video stream
            for format in info.get('formats', []):
                if format.get('acodec') != 'none' and format.get('vcodec') != 'none':
                    video_stream_url = format.get('url')
                    break

        aspect_ratio = None
        if width and height:
            aspect_ratio = width / height

        # Check for storyboard availability
        storyboard_available = False
        formats = info.get('formats', [])
        for fmt in formats:
            if fmt.get('format_id') == 'sb0':
                storyboard_available = True
                storyboard_subimage_resolution = {
                    'width': fmt.get('width'),
                    'height': fmt.get('height')
                }
                break

        return {
            'aspect_ratio': aspect_ratio,
            'title': title,
            'duration': duration,
            'thumbnail_url': thumbnail_url,
            'date_uploaded': date_uploaded,
            'channel': channel,
            'channel_id': channel_id,
            'embeddable': False if force_get_raw_stream else embeddable,
            'video_stream_url': video_stream_url,
            'chapters': chapters,
            'storyboard_available': storyboard_available,
            'storyboard_subimage_resolution': None if not storyboard_available else storyboard_subimage_resolution
        }

def get_video_info_with_retries(video_id, force_get_raw_stream, max_retries=3):
    retry_count = 0
    error = {}

    while retry_count < max_retries:
        try:
            return (get_video_info(video_id, force_get_raw_stream), None)
        except Exception as e:
            error_str = str(e)

            # Age restricted video
            if 'age' in error_str.lower() and 'sign in' in error_str.lower():
                error = {
                    'type': 'age_restricted',
                    'full_str': extract_yt_error(error_str)
                }
                break

            # Bot guard trigerred
            elif 'bot' in error_str.lower() and 'sign in' in error_str.lower():
                error = {
                    'type': 'bot',
                    'full_str': extract_yt_error(error_str)
                }
                break

            # Some other error ; note, but do not exit (keep retrying)
            else:
                error = {
                    'type': 'other',
                    'full_str': extract_yt_error(error_str)
                }

            # For other errors, retry
            retry_count += 1

            if retry_count >= max_retries:
                break

            time.sleep(2 ** retry_count)

    return (None, error)

#######################################################################
#   fetch_youtube_thumbnail_previews
#######################################################################

def fetch_youtube_thumbnail_previews(video_id, media_id, video_duration, subimage_res, db_path=config.DB_PATH):
    """
    Download storyboard fragments and extract individual frames to database
    """

    if not video_duration:
        print(f"Warning: Could not get video duration for media_id {media_id}")
        return False

    if not subimage_res:
        return False

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        'format': 'sb0',
        'keep_fragments': True,
        'writeinfojson': False,
        'writethumbnail': False,
        'outtmpl': os.path.join(config.PROCESSING_TEMP_DIR, f'storyboard_{media_id}.%(ext)s'),
        'quiet': True,
        'noprogress': True,
    }

    # Add cookies if available
    cookies_setting = db.get_setting('cookies_from_browser')
    if cookies_setting:
        ydl_opts['cookiesfrombrowser'] = (cookies_setting,)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Process fragment files
        frag_pattern = re.compile(rf'storyboard_{media_id}.*Frag(\d+)$')

        fragment_files = []
        for filename in os.listdir(config.PROCESSING_TEMP_DIR):
            if frag_pattern.search(filename):
                fragment_files.append(filename)

        if not fragment_files:
            return False

        # Sort by fragment number
        fragment_files.sort(key=lambda x: int(frag_pattern.search(x).group(1)))

        # First pass: count total sub-images to calculate seconds_per_image
        total_subimages_across_all_fragments = 0
        fragment_info = []  # Store info about each fragment for second pass

        for filename in fragment_files:
            file_path = os.path.join(config.PROCESSING_TEMP_DIR, filename)

            match = frag_pattern.search(filename)
            if not match:
                continue

            frag_num = int(match.group(1))

            try:
                with Image.open(file_path) as img:
                    width, height = img.size

                    # Calculate both rows and columns
                    if subimage_res and subimage_res.get('width') and subimage_res.get('height'):
                        cols = width // subimage_res['width']
                        rows = height // subimage_res['height']
                        sub_width = subimage_res['width']
                        sub_height = subimage_res['height']
                    else:
                        # Fallback: assume square grid if subimage resolution unknown
                        cols = rows = int((width / height) ** 0.5) or 3
                        sub_width = width // cols
                        sub_height = height // rows

                    total_subimages_in_fragment = rows * cols

                    fragment_info.append({
                        'filename': filename,
                        'frag_num': frag_num,
                        'rows': rows,
                        'cols': cols,
                        'sub_width': sub_width,
                        'sub_height': sub_height,
                        'total_subimages': total_subimages_in_fragment
                    })

                    total_subimages_across_all_fragments += total_subimages_in_fragment

            except Exception as e:
                print(f"Error reading fragment {filename} for counting: {e}")
                continue

        if total_subimages_across_all_fragments == 0:
            print("No valid fragments found")
            return False

        # Calculate seconds per image based on video duration and total sub-images
        seconds_per_image = round(video_duration / total_subimages_across_all_fragments)

        # Update the media table with seconds_per_frame
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE media SET seconds_per_frame = ? WHERE id = ?",
            (seconds_per_image, media_id)
        )
        conn.commit()
        conn.close()

        # Second pass: process fragments and save to database in batches
        cumulative_subimages = 0
        frame_batch = []  # Batch frames for database writes
        batch_size = 10

        for frag_info in fragment_info:
            filename = frag_info['filename']
            frag_num = frag_info['frag_num']
            rows = frag_info['rows']
            cols = frag_info['cols']
            sub_width = frag_info['sub_width']
            sub_height = frag_info['sub_height']
            file_path = os.path.join(config.PROCESSING_TEMP_DIR, filename)

            try:
                with Image.open(file_path) as img:
                    # Extract each sub-image from rows×cols grid
                    for row in range(rows):
                        for col in range(cols):
                            sub_image_index = (row * cols) + col

                            # Calculate timestamp based on cumulative sub-images processed
                            timestamp_seconds = (cumulative_subimages + sub_image_index) * seconds_per_image

                            # Crop coordinates
                            left = col * sub_width
                            top = row * sub_height
                            right = left + sub_width
                            bottom = top + sub_height

                            # Crop and convert to JPEG bytes
                            sub_image = img.crop((left, top, right, bottom))
                            img_buffer = io.BytesIO()
                            sub_image.save(img_buffer, format='JPEG', quality=50)
                            img_data = img_buffer.getvalue()

                            # Add to batch
                            frame_id = f"{media_id}-{timestamp_seconds}"
                            frame_batch.append((frame_id, media_id, timestamp_seconds, img_data))

                            # Write batch to database when it reaches batch_size
                            if len(frame_batch) >= batch_size:
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()
                                cursor.executemany(
                                    "INSERT OR REPLACE INTO frames (frame_id, media_id, timestamp, frame) VALUES (?, ?, ?, ?)",
                                    frame_batch
                                )
                                conn.commit()
                                conn.close()
                                frame_batch = []  # Clear batch

                    # Update cumulative count for next fragment
                    cumulative_subimages += frag_info['total_subimages']

                # Clean up fragment file
                os.remove(file_path)

            except Exception as e:
                print(f"Error processing fragment {filename}: {e}")
                continue

        # Write any remaining frames in the batch
        if frame_batch:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR REPLACE INTO frames (frame_id, media_id, timestamp, frame) VALUES (?, ?, ?, ?)",
                frame_batch
            )
            conn.commit()
            conn.close()

        # Clean up any remaining temp files
        for filename in os.listdir(config.PROCESSING_TEMP_DIR):
            if filename.startswith(f'storyboard_{media_id}'):
                try:
                    os.remove(os.path.join(config.PROCESSING_TEMP_DIR, filename))
                except:
                    pass

        return True

    except Exception as e:
        print(f"Error downloading storyboard: {e}")
        return False

#######################################################################
#   extract_thumbnail_previews_local
#######################################################################

def extract_thumbnail_previews_local(video_path, media_id, video_duration, output_width=320, interval=1.0, quality=50, db_path=config.DB_PATH):
    """
    Extract frames from local video file at specified intervals and store in database
    """
    # Start timing
    start_time = time.time()

    if not video_duration:
        print(f"Warning: Could not get video duration for media_id {media_id}")
        return False

    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found")
        return False

    try:
        # Open video container
        container = av.open(video_path)
        video_stream = container.streams.video[0]

        # Get video info
        orig_width = video_stream.width
        orig_height = video_stream.height

        # Calculate output dimensions
        aspect_ratio = orig_width / orig_height
        output_height = int(output_width / aspect_ratio)

        # Calculate timestamps to extract
        timestamps = []
        current_time = 0.0
        while current_time <= video_duration:
            timestamps.append(current_time)
            current_time += interval

        # Don't add final timestamp if it would be very close to the last one
        if timestamps and (video_duration - timestamps[-1]) > (interval * 0.1):
            timestamps.append(video_duration)

        if not timestamps:
            print("No valid timestamps to extract")
            container.close()
            return False

        successful_extractions = 0
        actual_timestamps = []  # Store the actual timestamps we extracted
        frame_batch = []  # Batch frames for database writes
        batch_size = 10

        for timestamp in timestamps:
            try:
                # Seek to timestamp (in microseconds)
                seek_time = int(timestamp * 1000000)
                container.seek(seek_time)

                # Get the next frame
                frame_extracted = False
                for frame in container.decode(video=0):
                    # Get the ACTUAL timestamp of this frame
                    actual_timestamp = float(frame.pts * frame.time_base)

                    # Resize frame
                    frame = frame.reformat(width=output_width, height=output_height)

                    # Convert to PIL Image
                    img = frame.to_image()

                    # Convert to JPEG bytes
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=quality, optimize=True)
                    img_data = img_buffer.getvalue()

                    # Store with the actual timestamp (rounded to nearest integer)
                    rounded_timestamp = int(round(actual_timestamp))
                    frame_id = f"{media_id}-{rounded_timestamp}"

                    # Add to batch
                    frame_batch.append((frame_id, media_id, rounded_timestamp, img_data))

                    # Write batch to database when it reaches batch_size
                    if len(frame_batch) >= batch_size:
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.executemany(
                            "INSERT OR REPLACE INTO frames (frame_id, media_id, timestamp, frame) VALUES (?, ?, ?, ?)",
                            frame_batch
                        )
                        conn.commit()
                        conn.close()
                        frame_batch = []  # Clear batch

                    actual_timestamps.append(rounded_timestamp)
                    successful_extractions += 1
                    frame_extracted = True
                    break  # Only take the first frame after seeking

                if not frame_extracted:
                    print(f"Warning: Could not extract frame at {timestamp:.2f}s")

            except Exception as e:
                print(f"Error extracting frame at {timestamp:.2f}s: {e}")
                continue

        # Write any remaining frames in the batch
        if frame_batch:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR REPLACE INTO frames (frame_id, media_id, timestamp, frame) VALUES (?, ?, ?, ?)",
                frame_batch
            )
            conn.commit()
            conn.close()

        # Store the list of actual timestamps in the media table
        if actual_timestamps:
            # Remove duplicates and sort
            unique_timestamps = sorted(list(set(actual_timestamps)))

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE media SET available_timestamps = ? WHERE id = ?",
                (json.dumps(unique_timestamps), media_id)
            )
            conn.commit()
            conn.close()

        container.close()

        # Calculate and print timing information
        end_time = time.time()
        total_processing_time = end_time - start_time

        return successful_extractions > 0

    except Exception as e:
        end_time = time.time()
        print(f"Error processing local video storyboards: {e}")
        return False

#######################################################################
#   Helpers
#######################################################################

def fetch_online_thumbnail(thumbnail_url):
    try:
        response = requests.get(thumbnail_url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException:
        return None

def create_low_res_thumbnail(high_res_data, target_width=426):
    if not high_res_data:
        return None

    try:
        # Load the high-res image
        img = Image.open(io.BytesIO(high_res_data))

        # Calculate target height maintaining aspect ratio
        original_width, original_height = img.size
        aspect_ratio = original_width / original_height
        target_height = int(target_width / aspect_ratio)

        # Resize with high-quality resampling
        low_res_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Convert to JPEG bytes with good quality
        img_buffer = io.BytesIO()
        low_res_img.save(img_buffer, format='JPEG', quality=85, optimize=True)

        return img_buffer.getvalue()

    except Exception as e:
        print(f"Error creating low-res thumbnail: {e}")
        return None

def are_chapters_manual(description):
    """
    Detect if chapters are manually added by checking the description.
    Returns True if manual chapters are detected (user-added),
    False if they appear to be auto-generated or missing.
    """
    if not description:
        return False

    # Regex pattern to find timestamps
    # Matches: H:MM:SS, HH:MM:SS, M:SS, MM:SS
    timestamp_pattern = r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})'

    lines = description.split('\n')
    timestamps = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Look for ANY timestamp in the line
        match = re.search(timestamp_pattern, line)
        if match:
            # Extract hours, minutes, seconds
            hours = match.group(1) or '0'
            minutes = match.group(2)
            seconds = match.group(3)

            # Convert to total seconds
            total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            timestamps.append(total_seconds)

    # Find the 0:00 timestamp (start of chapters)
    if 0 not in timestamps:
        return False

    # Get the index of the first 0:00 timestamp
    zero_index = timestamps.index(0)

    # Use only timestamps from the 0:00 onwards (this is the chapter list)
    chapter_timestamps = timestamps[zero_index:]

    # Check if we have valid manual chapters (as per https://support.google.com/youtube/answer/9884579?hl=en):
    # 1. At least 3 timestamps (including the 0:00)
    # 2. Timestamps are in ascending order
    # 3. Minimum gap of 10 seconds between timestamps
    if len(chapter_timestamps) >= 3:
        if chapter_timestamps == sorted(chapter_timestamps):  # Should be in ascending order
            # Check minimum gaps
            valid_gaps = all(
                chapter_timestamps[j] - chapter_timestamps[j-1] >= 10
                for j in range(1, len(chapter_timestamps))
            )
            if valid_gaps:
                return True

    return False