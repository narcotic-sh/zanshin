import os
import sqlite3
import random
import string
import signal
import json
import numpy as np
from misc import resolve_bookmark
import config

#######################################################################
#   Database (media.db) tables defn, init
#######################################################################

def initialize(db_path=config.DB_PATH):
    db_exists = os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='media'")
    media_table_exists = cursor.fetchone() is not None

    if not db_exists or not media_table_exists:
        cursor.execute(get_create_media_table_sql())
    else:
        add_missing_columns(cursor, 'media', get_media_columns())

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='frames'")
    frames_table_exists = cursor.fetchone() is not None

    if not db_exists or not frames_table_exists:
        cursor.execute(get_create_frames_table_sql())
        cursor.execute("CREATE INDEX idx_frames_media_id ON frames(media_id)")
    else:
        add_missing_columns(cursor, 'frames', get_frames_columns())

    conn.commit()
    conn.close()

    initialize_settings()

def get_media_columns():
    """Define media table columns with their types and constraints"""
    return {
        'id': 'TEXT PRIMARY KEY',                           # 11 char unique ID for media item

        # ============================================================================================
        #  General
        # ============================================================================================

        'source': 'TEXT NOT NULL',                          # [youtube, local]
        'uri': 'TEXT NOT NULL',                             # (YouTube video_id) or (macOS filesystem bookmark, base64) or (POSIX path, if not on macOS)
        'media_type': 'TEXT NOT NULL',                      # [video, audio]
        'title': 'TEXT DEFAULT NULL',                       # YouTube video title or filename
        'duration': 'REAL DEFAULT NULL',                    # Media duration
        'aspect_ratio': 'REAL DEFAULT NULL',                # (e.g. 16:9 = 16/9)
        'thumbnail': 'BLOB DEFAULT NULL',                   # jpeg raw data,
        'thumbnail_low_res': 'BLOB DEFAULT NULL',           # jpeg raw data (low res for list view) (3x downsample)

        # ============================================================================================
        #  Local
        # ============================================================================================

        'creation_timestamp': 'INTEGER DEFAULT NULL',       # UNIX timestamp of file creation
        'hash': 'TEXT DEFAULT NULL',                        # xxh3_64 hash for local files

        # ============================================================================================
        #  YouTube
        # ============================================================================================

        'date_uploaded': 'TEXT DEFAULT NULL',               # YYYYMMDD
        'channel': 'TEXT DEFAULT NULL',                     # channel title
        'channel_id': 'TEXT DEFAULT NULL',                  # YouTube channel ID
        'chapters': 'TEXT DEFAULT NULL',                    # [ { "start_time": , "title": , "end_time": }, ... ]
        'embeddable': 'BOOLEAN DEFAULT NULL',               # can video be played using yt iframe player
        'video_stream_url': 'TEXT DEFAULT NULL',            # if not embeddable, 360p video+audio stream URL
        'force_get_raw_stream': 'BOOLEAN DEFAULT NULL',     # some videos claim embeddable but are actually not; so need to force get raw stream
        'storyboards_fetched': 'BOOLEAN DEFAULT NULL',      # whether storyboard frames have been extracted
        'seconds_per_frame': 'INTEGER DEFAULT NULL',        # seconds represented by each storyboard frame
        'available_timestamps': 'TEXT DEFAULT NULL',        # JSON array of available frame timestamps for local videos

        # ============================================================================================
        #  Processing
        # ============================================================================================

        'status': 'TEXT NOT NULL',                          # [queued, processing, success, failed]
        'metadata_status': 'TEXT DEFAULT "pending"',        # [pending, success, failed]
        'metadata_error': 'TEXT DEFAULT NULL',              # metadata fetch error json dict, fields 'type', 'full_str'
        'submitted_t': 'INTEGER NOT NULL',                  # job sumitted timestamp
        'started_t': 'INTEGER DEFAULT NULL',                # job started processing timestamp
        'finished_t': 'INTEGER DEFAULT NULL',               # UNIX timestamp for when finished processing
        'error': 'TEXT DEFAULT NULL',                       # download error json dict, fields 'type': {age_restricted, bot, interrupted, no_speakers, other}, 'full_str'
        'diarization_time': 'REAL DEFAULT NULL',            # Seconds taken to diarize

        # ============================================================================================
        #  Diarization data
        # ============================================================================================

        'raw_segments': 'TEXT DEFAULT NULL',
        'merged_segments': 'TEXT DEFAULT NULL',
        'speaker_centroids': 'TEXT DEFAULT NULL',
        'speaker_color_sets': 'TEXT DEFAULT NULL',
        'timing_stats': 'TEXT DEFAULT NULL',                # JSON: total_time, vad_time, fbank_time, embeddings_time, clustering_time

        # ============================================================================================
        #  Saved player state
        # ============================================================================================

        'selected_colorset_num': 'INTEGER DEFAULT 2',
        'speaker_visibility': 'TEXT DEFAULT NULL',
        'speaker_speeds': 'TEXT DEFAULT NULL',
        'playback_position': 'REAL DEFAULT 0',
        'skip_silences': 'BOOLEAN DEFAULT 0',
        'zoom_window': 'TEXT DEFAULT NULL',
        'auto_skip_disabled_speakers': 'BOOLEAN DEFAULT NULL'
    }

#######################################################################
#   Submission / retry
#######################################################################

def generate_short_id(length=11):
    chars = string.ascii_letters + string.digits + "-_"
    return "".join(random.choice(chars) for _ in range(length))

def submit_job(
    source,
    uri,
    media_type,
    filename=None,
    file_hash=None,
    file_creation_timestamp=None,
    db_path=config.DB_PATH,
):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    id = generate_short_id()

    cursor.execute(
        """
    INSERT INTO media (
        id,
        source,
        uri,
        title,
        media_type,
        hash,
        creation_timestamp,
        status,
        submitted_t
    )
    VALUES (
        ?,        -- id
        ?,        -- source
        ?,        -- uri
        ?,        -- title (filename)
        ?,        -- media_type
        ?,        -- hash
        ?,        -- creation_timestamp
        'queued',
        strftime('%s', 'now')
    )
    """,
        (id, source, uri, filename, media_type, file_hash, file_creation_timestamp),
    )

    conn.commit()
    conn.close()

    return id

def retry_processing(id, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        update media
        set status = 'queued', submitted_t = strftime('%s', 'now')
        where id = ?
        """,
        (id,),
    )
    conn.commit()
    conn.close()

def cleanup_interrupted_jobs(db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find all entries with processing status or pending metadata
    cursor.execute("""
        SELECT id, status, metadata_status
        FROM media
        WHERE status = 'processing' OR metadata_status = 'pending'
    """)

    interrupted_jobs = cursor.fetchall()

    for job_id, status, metadata_status in interrupted_jobs:

        if status == 'processing':
            cursor.execute("""
                UPDATE media
                SET status = 'failed',
                    finished_t = strftime('%s', 'now'),
                    error = ?
                WHERE id = ?
            """, (json.dumps({'type': 'interrupted', 'full_str': 'Processing interrupted'}), job_id))

    conn.commit()
    conn.close()

    return len(interrupted_jobs)

#######################################################################
#   Check if exists
#######################################################################

def check_media_item_exists(video_id, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        select id, status from media
        where source = 'youtube' and uri = ?
        """,
        (video_id,),
    )
    entry = cursor.fetchone()
    conn.close()
    if not entry:
        return False

    # needs handling for failed videos
    id, status = entry
    if status != "failed":
        return id


def check_file_exists(file_hash, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id FROM media
        WHERE source = 'local' AND hash = ?
        """,
        (file_hash,),
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

#######################################################################
#   Fetch
#######################################################################

def fetch_media_previews(db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id,
           source,
           media_type,
           uri,
           creation_timestamp,
           duration,
           title,
           date_uploaded,
           channel,
           status,
           metadata_status,
           submitted_t,
           started_t,
           finished_t,
           error,
           metadata_error,
           CASE WHEN thumbnail IS NOT NULL THEN 1 ELSE 0 END as thumbnail_exists
    FROM media
    """)

    rows = cursor.fetchall()

    # Convert to list of dictionaries
    all_media = []
    for row in rows:
        result = {key: row[key] for key in row.keys()}

        # convert base64 encoded macOS bookmark data to POSIX filepath
        if result["source"] == "local":
            result["uri"] = resolve_bookmark(result["uri"])

        # convert error, metadata_error json strings to dicts
        if result["error"]:
            result["error"] = json.loads(result["error"])
        if result["metadata_error"]:
            result["metadata_error"] = json.loads(result["metadata_error"])

        # Convert the integer to a boolean
        result["thumbnail_exists"] = bool(result["thumbnail_exists"])

        all_media.append(result)

    conn.close()

    # Categorize and sort each category
    processing_items = [item for item in all_media if item["status"] == "processing"]
    processing_items.sort(key=lambda x: x["started_t"] or 0)  # Oldest first

    queued_items = [item for item in all_media if item["status"] == "queued"]
    queued_items.sort(key=lambda x: x["submitted_t"] or 0)  # Oldest first

    failed_items = [item for item in all_media if item["status"] == "failed"]
    failed_items.sort(key=lambda x: -(x["finished_t"] or 0))  # Newest first

    success_items = [item for item in all_media if item["status"] == "success"]
    success_items.sort(key=lambda x: -(x["finished_t"] or 0))  # Newest first

    return {
        "processing": processing_items,
        "queued": queued_items,
        "failed": failed_items,
        "success": success_items,
    }

# Fetch speaker centroids for a media item and convert from JSON to dict with numpy arrays
def fetch_speaker_centroids(id, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT speaker_centroids FROM media WHERE id = ?",
        (id,)
    )

    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        # Parse JSON string
        centroids_dict = json.loads(result[0])

        # Convert lists back to numpy arrays
        for speaker_id in centroids_dict:
            centroids_dict[speaker_id] = np.array(centroids_dict[speaker_id], dtype=np.float32)

        return centroids_dict

    return None

def fetch_media_item(id, router_socket, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT
        -- General Info
        id,
        source,
        media_type,
        uri,
        title,
        duration,
        aspect_ratio,

        -- Metadata
        metadata_status,
        metadata_error,
        CASE WHEN thumbnail IS NOT NULL THEN 1 ELSE 0 END as thumbnail_exists,

        -- YouTube specific
        channel,
        channel_id,
        date_uploaded,
        embeddable,
        video_stream_url,
        chapters,
        storyboards_fetched,
        seconds_per_frame,
        available_timestamps,

        -- Timing
        creation_timestamp,
        submitted_t,
        started_t,
        finished_t,
        diarization_time,

        -- Status
        status,
        error,

        -- Results
        merged_segments,
        speaker_color_sets,

        -- Saved player state
        selected_colorset_num,
        speaker_visibility,
        speaker_speeds,
        playback_position,
        skip_silences,
        zoom_window,
        auto_skip_disabled_speakers
    FROM media
    WHERE id = ?
    """,
        (id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        result = {key: row[key] for key in row.keys()}

        if result["source"] == "local":
            # replaces uri with actual posix filepath (if found)
            # if not found, will simply return None for uri (frontend will alert user file is gone)
            result["uri"] = resolve_bookmark(result["uri"])

        # Convert JSON fields
        json_fields = ['error', 'metadata_error', 'chapters', 'available_timestamps', 'speaker_visibility', 'speaker_speeds', 'zoom_window']
        for field in json_fields:
            if result[field]:
                result[field] = json.loads(result[field])

        # Convert the integer to a boolean
        result["thumbnail_exists"] = bool(result["thumbnail_exists"])

        return result
    else:
        return None

#######################################################################
#   Delete
#######################################################################

def delete_media_item(id_list, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join(["?"] * len(id_list))

    # Delete from frames table first
    cursor.execute(
        f"""
        DELETE FROM frames
        WHERE media_id IN ({placeholders})
        """,
        id_list,
    )

    # Delete from media table
    cursor.execute(
        f"""
        DELETE FROM media
        WHERE id IN ({placeholders})
        """,
        id_list,
    )

    media_rows_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    return media_rows_deleted

#######################################################################
#   VACUUM
#######################################################################

def vacuum(db_path=config.DB_PATH):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("VACUUM")
        conn.close()
    except Exception as e:
        print(f"VACUUM failed: {e}")

#######################################################################
#   Media item-specific settings (colorset, selected speakers, etc.)
#######################################################################

def set_colorset(id, colorset_num, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET selected_colorset_num = ?
        WHERE id = ?
        """,
        (colorset_num, id),
    )
    conn.commit()
    conn.close()

def set_speaker_visibility(id, speaker_visibility, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET speaker_visibility = ?
        WHERE id = ?
        """,
        (json.dumps(speaker_visibility), id),
    )
    conn.commit()
    conn.close()

def set_playback_position(id, playback_position, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET playback_position = ?
        WHERE id = ?
        """,
        (playback_position, id),
    )
    conn.commit()
    conn.close()

def set_speaker_speeds(id, speaker_speeds, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET speaker_speeds = ?
        WHERE id = ?
        """,
        (json.dumps(speaker_speeds), id),
    )
    conn.commit()
    conn.close()

def set_skip_silences(id, skip_silences, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET skip_silences = ?
        WHERE id = ?
        """,
        (skip_silences, id),
    )
    conn.commit()
    conn.close()

def set_zoom_window(id, zoom_window, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET zoom_window = ?
        WHERE id = ?
        """,
        (json.dumps(zoom_window), id),
    )
    conn.commit()
    conn.close()

def set_duration(id, duration, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET duration = ?
        WHERE id = ?
        """,
        (duration, id),
    )
    conn.commit()
    conn.close()

def set_auto_skip_disabled_speakers(id, auto_skip_disabled_speakers, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE media
        SET auto_skip_disabled_speakers = ?
        WHERE id = ?
        """,
        (auto_skip_disabled_speakers, id),
    )
    conn.commit()
    conn.close()

#######################################################################
#   Metadata + diarization processing jobs related
#######################################################################

def fetch_job(job_type, db_path=config.DB_PATH):
    db_conn = sqlite3.connect(db_path)
    db_conn.row_factory = sqlite3.Row
    cursor = db_conn.cursor()

    if job_type == "main":
        cursor.execute(
            """
            select id, source, uri from media where status = 'queued'
            order by submitted_t ASC
            """
        )
    else:
        cursor.execute(
            """
            select id, source, uri, media_type, force_get_raw_stream from media where metadata_status = 'pending'
            order by submitted_t ASC
            """
        )

    row = cursor.fetchone()
    db_conn.close()

    job = dict(row) if row else None

    if job and job["source"] == "local":
        # resolve macOS bookmark into POSIX filepath ; None if bookmark couldn't be resolved
        job["uri"] = resolve_bookmark(job["uri"])

    return job

def update_diarization_job_status(id, new_status, db_path=config.DB_PATH):
    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()
    cursor.execute(
        """
        update media
        set status = ?, started_t = strftime('%s', 'now')
        where id = ?
        """,
        (
            new_status,
            id,
        ),
    )
    db_conn.commit()
    db_conn.close()

def mark_job_failed(job_type, id, error, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if job_type == "main":
        cursor.execute(
            """
            update media
            set status = 'failed',
                finished_t = strftime('%s', 'now'),
                error = ?
            where id = ?
            """,
            (error, id),
        )
    else:
        cursor.execute(
            """
            update media
            set metadata_status = 'failed',
                metadata_error = ?
            where id = ?
            """,
            (error, id),
        )

    conn.commit()
    conn.close()

def refetch_metadata(id, force_get_raw_stream=None, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        update media
        set metadata_status = 'pending',
            force_get_raw_stream = ?
        where id = ?
        """,
        (force_get_raw_stream, id),
    )
    conn.commit()
    conn.close()

#######################################################################
#   Settings (settings.json)
#######################################################################

def initialize_settings(settings_path=config.SETTINGS_PATH):
    default_settings = get_default_settings()
    if not os.path.exists(settings_path):
        # Create new settings file with defaults
        with open(settings_path, "w") as file:
            json.dump(default_settings, file, indent=4)
    else:
        # Update existing settings file to match expected structure
        update_settings_structure(settings_path, default_settings)

        # Validate that background_image and alternate_bg_color are not both enabled
        # If they are, turn them both off
        try:
            with open(settings_path, "r") as file:
                settings = json.load(file)

            if settings.get('background_image') and settings.get('alternate_bg_color'):
                print("Both background_image and alternate_bg_color are enabled. Disabling both to prevent conflicts.")
                settings['background_image'] = False
                settings['alternate_bg_color'] = False

                with open(settings_path, "w") as file:
                    json.dump(settings, file, indent=4)
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            # If there's any error reading/parsing settings, ignore the validation
            pass

def get_default_settings():
    """Define the expected settings structure with default values"""
    return {
        "cookies_from_browser": None,
        "identify_speakers": True,
        "background_image": False,
        "alternate_bg_color": True,
        "restore_zoom_window": True,
        "warmup_processor": True,
        "auto_skip_by_default": True
        # Add other default settings here as needed
    }

def get_setting(key, settings_path=config.SETTINGS_PATH):
    with open(settings_path, "r") as file:
        settings = json.load(file)
    return settings.get(key)


def set_setting(key, value, settings_path=config.SETTINGS_PATH):
    with open(settings_path, "r") as file:
        settings = json.load(file)

    settings[key] = value

    with open(settings_path, "w") as file:
        json.dump(settings, file, indent=4)

    return True

def set_multiple_settings(settings_dict, settings_path=config.SETTINGS_PATH):
    """Set multiple settings atomically to avoid race conditions"""
    with open(settings_path, "r") as file:
        settings = json.load(file)

    # Update multiple settings
    settings.update(settings_dict)

    with open(settings_path, "w") as file:
        json.dump(settings, file, indent=4)

    return True

def get_all_settings(settings_path=config.SETTINGS_PATH):
    with open(settings_path, "r") as file:
        settings = json.load(file)

    return settings

#######################################################################
#   Settings migration
#######################################################################

def update_settings_structure(settings_path, expected_settings):
    """
    Ensure settings file matches expected structure by adding missing keys
    and removing keys that are no longer expected.

    Args:
        settings_path: Path to the settings.json file
        expected_settings: Dict of expected settings with default values
    """
    try:
        # Read current settings
        with open(settings_path, "r") as file:
            current_settings = json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is corrupted or doesn't exist, use defaults
        current_settings = {}

    expected_keys = set(expected_settings.keys())
    current_keys = set(current_settings.keys())

    # Find missing and extra keys
    missing_keys = expected_keys - current_keys
    extra_keys = current_keys - expected_keys

    # Start with current settings
    updated_settings = current_settings.copy()

    # Add missing keys with default values
    for key in missing_keys:
        updated_settings[key] = expected_settings[key]
        print(f"Added missing setting '{key}' with default value")

    # Remove extra keys
    for key in extra_keys:
        del updated_settings[key]
        print(f"Removed obsolete setting '{key}'")

    # Write updated settings back to file (only if changes were made)
    if missing_keys or extra_keys:
        with open(settings_path, "w") as file:
            json.dump(updated_settings, file, indent=4)
        print(f"Updated settings structure: added {len(missing_keys)} keys, removed {len(extra_keys)} keys")

#######################################################################
#   Database migration (very rudimentary lol)
#######################################################################

def get_frames_columns():
    """Define frames table columns with their types and constraints"""
    return {
        'frame_id': 'TEXT PRIMARY KEY',                     # composite key: media_id-timestamp
        'media_id': 'TEXT NOT NULL',                        # 11 char unique ID for media item
        'timestamp': 'INTEGER NOT NULL',                    # location of frame in video (seconds)
        'frame': 'BLOB NOT NULL'                            # jpeg raw data
    }

def get_create_media_table_sql():
    """Generate CREATE TABLE SQL for media table"""
    columns = get_media_columns()
    column_definitions = [f"{name} {definition}" for name, definition in columns.items()]
    newline_indent = ',\n    '
    return f"CREATE TABLE media (\n    {newline_indent.join(column_definitions)}\n)"

def get_create_frames_table_sql():
    """Generate CREATE TABLE SQL for frames table"""
    columns = get_frames_columns()
    column_definitions = [f"{name} {definition}" for name, definition in columns.items()]
    newline_indent = ',\n    '
    return f"CREATE TABLE frames (\n    {newline_indent.join(column_definitions)}\n)"

def add_missing_columns(cursor, table_name, expected_columns):
    """
    Check if all expected columns exist in the table and add missing ones.
    Also removes columns that are no longer in the expected schema.

    Args:
        cursor: SQLite cursor
        table_name: Name of the table to check
        expected_columns: Dict of {column_name: column_definition}
    """
    # Get existing columns
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}  # row[1] is column name

    expected_column_names = set(expected_columns.keys())

    # Find missing columns (need to add)
    missing_columns = expected_column_names - existing_columns

    # Find extra columns (need to remove)
    extra_columns = existing_columns - expected_column_names

    # Add missing columns
    for column_name in missing_columns:
        column_def = expected_columns[column_name]
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
            print(f"Added missing column '{column_name}' to table '{table_name}'")
        except sqlite3.Error as e:
            print(f"Error adding column {column_name} to {table_name}: {e}")

    # Remove extra columns (requires table recreation in SQLite)
    if extra_columns:
        remove_columns_from_table(cursor, table_name, expected_columns, extra_columns)

def remove_columns_from_table(cursor, table_name, expected_columns, columns_to_remove):
    """
    Remove columns from a table by recreating it (SQLite doesn't support DROP COLUMN in older versions).

    Args:
        cursor: SQLite cursor
        table_name: Name of the table
        expected_columns: Dict of expected columns
        columns_to_remove: Set of column names to remove
    """
    print(f"Removing columns {columns_to_remove} from table '{table_name}'")

    # Create new table with correct schema
    temp_table_name = f"{table_name}_temp"
    column_definitions = [f"{name} {definition}" for name, definition in expected_columns.items()]
    newline_indent = ',\n    '
    create_sql = f"CREATE TABLE {temp_table_name} (\n    {newline_indent.join(column_definitions)}\n)"

    try:
        cursor.execute(create_sql)

        # Copy data from old table to new table (only columns that exist in both)
        column_names = list(expected_columns.keys())
        columns_str = ', '.join(column_names)
        cursor.execute(f"INSERT INTO {temp_table_name} ({columns_str}) SELECT {columns_str} FROM {table_name}")

        # Drop old table
        cursor.execute(f"DROP TABLE {table_name}")

        # Rename temp table to original name
        cursor.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}")

        # Recreate indexes if this is the frames table
        if table_name == 'frames':
            cursor.execute("CREATE INDEX idx_frames_media_id ON frames(media_id)")

        print(f"Successfully removed columns {columns_to_remove} from table '{table_name}'")

    except sqlite3.Error as e:
        print(f"Error removing columns from {table_name}: {e}")
        # Try to cleanup temp table if it exists
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
        except:
            pass