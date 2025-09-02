# yt-dlp command to download json3
# yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs en --sub-format json3 <video_id>

import json
import sys
import os
from pathlib import Path
from yt_dlp import YoutubeDL

def download_json3_subtitles(video_url, output_dir='.'):
    """
    Download JSON3 subtitles using yt-dlp Python API
    Returns the path to the downloaded JSON3 file, or None if failed
    """

    # Configure yt-dlp options
    ydl_opts = {
        'skip_download': True,           # Don't download the video
        'writesubtitles': True,          # Write manual subtitles
        'writeautomaticsub': True,       # Write auto-generated subtitles
        'subtitleslangs': ['en'],        # English subtitles
        'subtitlesformat': 'json3',      # JSON3 format
        'outtmpl': os.path.join(output_dir, '%(title)s [%(id)s].%(ext)s'),  # Output template
        'quiet': True,                   # Reduce output noise
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Extract info to get the title and ID
            info = ydl.extract_info(video_url, download=False)
            video_id = info.get('id')
            title = info.get('title', 'Unknown')

            print(f"Found video: {title} [{video_id}]")

            # Download the subtitles
            ydl.download([video_url])

            # Find the downloaded JSON3 file
            # yt-dlp saves subtitles as: title [id].en.json3
            safe_title = ydl.sanitize_info(info)['title']
            possible_filenames = [
                f"{safe_title} [{video_id}].en.json3",
                f"{title} [{video_id}].en.json3",
            ]

            for filename in possible_filenames:
                filepath = os.path.join(output_dir, filename)
                if os.path.exists(filepath):
                    print(f"Downloaded JSON3 subtitles to: {filepath}")
                    return filepath

            # If exact match not found, search for any JSON3 file with the video ID
            for file in os.listdir(output_dir):
                if video_id in file and file.endswith('.en.json3'):
                    filepath = os.path.join(output_dir, file)
                    print(f"Found JSON3 subtitles at: {filepath}")
                    return filepath

            print("Error: Could not find downloaded JSON3 file")
            return None

    except Exception as e:
        print(f"Error downloading subtitles: {e}")
        return None

def convert_json3_to_simple(input_file, output_file, word_level=True):
    """
    Convert YouTube JSON3 subtitle format to simple format with start, end, and words fields.

    Args:
        word_level: If True, create word-level segments. If False, group by events (original behavior)
    """

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    simple_segments = []

    if word_level:
        # First pass: collect all segments with their absolute timestamps
        all_segments = []

        for event in data.get('events', []):
            if 'segs' not in event:
                continue

            event_start_ms = event.get('tStartMs', 0)

            for seg in event['segs']:
                text = seg.get('utf8', '').strip()
                if not text or text == '\n':  # Skip empty segments and newlines
                    continue

                seg_offset_ms = seg.get('tOffsetMs', 0)
                start_time_ms = event_start_ms + seg_offset_ms

                all_segments.append({
                    'start_ms': start_time_ms,
                    'text': text
                })

        # Sort all segments by start time
        all_segments.sort(key=lambda x: x['start_ms'])

        # Second pass: calculate end times using next segment's start time
        for i, seg in enumerate(all_segments):
            start_seconds = seg['start_ms'] / 1000.0

            if i + 1 < len(all_segments):
                # Use next segment's start time as this segment's end time
                end_seconds = all_segments[i + 1]['start_ms'] / 1000.0
            else:
                # For the very last segment, estimate a reasonable duration
                # Use a default of 0.5 seconds for the last word
                end_seconds = start_seconds + 0.5

            # Ensure minimum duration of 50ms to avoid zero-duration segments
            if end_seconds - start_seconds < 0.05:
                end_seconds = start_seconds + 0.05

            simple_segments.append({
                'start': round(start_seconds, 3),
                'end': round(end_seconds, 3),
                'words': seg['text']
            })

    else:
        # Original behavior: group all segments within an event
        for event in data.get('events', []):
            if 'segs' not in event:
                continue

            event_start_ms = event.get('tStartMs', 0)
            event_duration_ms = event.get('dDurationMs', 0)

            start_seconds = event_start_ms / 1000.0
            end_seconds = (event_start_ms + event_duration_ms) / 1000.0

            # Extract all text from segments
            text_parts = []
            for seg in event['segs']:
                text = seg.get('utf8', '')
                if text and text.strip():  # Skip empty segments and whitespace-only
                    text_parts.append(text)

            # Only add segments that have actual words
            if text_parts:
                # Join text parts directly (they already contain proper spacing)
                combined_text = ''.join(text_parts).strip()

                if combined_text:  # Make sure we have actual content
                    simple_segments.append({
                        'start': round(start_seconds, 3),
                        'end': round(end_seconds, 3),
                        'words': combined_text
                    })

    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(simple_segments, f, indent=2, ensure_ascii=False)

    level_desc = "word-level" if word_level else "event-grouped"
    print(f"Converted {len(simple_segments)} {level_desc} segments from {input_file} to {output_file}")

def main():
    if len(sys.argv) not in [2, 3, 4]:
        print("Usage: python transcript_downloader.py <video_url_or_id> [output_json_file] [--word-level|--event-level]")
        print("Examples:")
        print("  python transcript_downloader.py 'https://www.youtube.com/watch?v=LF0TQ0uFdlE'")
        print("  python transcript_downloader.py 'LF0TQ0uFdlE' simple_transcript.json")
        print("  python transcript_downloader.py 'LF0TQ0uFdlE' transcript.json --word-level")
        print("  python transcript_downloader.py 'LF0TQ0uFdlE' transcript.json --event-level")
        sys.exit(1)

    video_url = sys.argv[1]

    # Parse arguments
    word_level = True  # Default to word-level
    output_file = None

    for arg in sys.argv[2:]:
        if arg == '--word-level':
            word_level = True
        elif arg == '--event-level':
            word_level = False
        else:
            output_file = arg

    # If it's just a video ID, construct the full URL
    if not video_url.startswith('http'):
        video_url = f"https://www.youtube.com/watch?v={video_url}"

    # Set output file name if not provided
    if not output_file:
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                video_id = info.get('id', 'unknown')
            level_suffix = "word_level" if word_level else "event_level"
            output_file = f"{video_id}_transcript_{level_suffix}.json"
        except:
            output_file = "transcript.json"

    print(f"Downloading subtitles from: {video_url}")
    print(f"Processing mode: {'Word-level' if word_level else 'Event-level'} segmentation")

    # Step 1: Download JSON3 subtitles
    json3_file = download_json3_subtitles(video_url)

    if not json3_file:
        print("Failed to download subtitles")
        sys.exit(1)

    # Step 2: Convert to simple format
    try:
        convert_json3_to_simple(json3_file, output_file, word_level=word_level)
        print(f"\nSuccess! Simple transcript saved to: {output_file}")

        # Show sample of the output
        with open(output_file, 'r', encoding='utf-8') as f:
            sample_data = json.load(f)

        print(f"\nSample output (first 5 segments):")
        for i, segment in enumerate(sample_data[:5]):
            print(f"  {segment['start']:.3f}-{segment['end']:.3f}s: '{segment['words']}'")

        # Optionally clean up the JSON3 file
        cleanup = input("\nDelete the original JSON3 file? (y/N): ").lower().strip()
        if cleanup == 'y':
            os.remove(json3_file)
            print(f"Deleted {json3_file}")

    except Exception as e:
        print(f"Error converting transcript: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()