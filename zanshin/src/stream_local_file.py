import os
import mimetypes
import sqlite3
from flask import request, send_file, Response
from misc import resolve_bookmark
import config

def stream_local_file(id):
    try:
        # Get file path from database
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT uri, media_type FROM media WHERE id = ? AND source = "local"', (id,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return Response("Media not found", status=404)

        macos_bookmark, media_type = result
        file_path = resolve_bookmark(macos_bookmark)

        if not file_path:
            return Response("File not found", status=404)

        # Get file size and modification time for caching
        file_size = os.path.getsize(file_path)
        file_mtime = os.path.getmtime(file_path)
        etag = f'"{id}-{int(file_mtime)}"'

        # Set content type based on media_type
        content_type = "video/mp4" if media_type == "video" else "audio/mpeg"

        # Try to get a more specific content type from the file extension
        specific_type = mimetypes.guess_type(file_path)[0]
        if specific_type:
            content_type = specific_type

        # Check if-none-match for caching
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            return Response(status=304)  # Not Modified

        # Handle range requests for seeking
        range_header = request.headers.get("Range", None)

        # Determine optimal chunk size based on file size
        base_chunk_size = 8192  # 8KB default
        if file_size > 1_073_741_824:  # > 1GB
            chunk_size = 262_144  # 256KB for very large files
        elif file_size > 104_857_600:  # > 100MB
            chunk_size = 131_072  # 128KB for large files
        elif file_size > 10_485_760:  # > 10MB
            chunk_size = 65_536  # 64KB for medium files
        else:
            chunk_size = base_chunk_size  # 8KB for small files

        if range_header:
            try:
                # Parse the range header
                bytes_range = range_header.replace("bytes=", "").split("-")
                start = int(bytes_range[0]) if bytes_range[0] else 0
                end = int(bytes_range[1]) if bytes_range[1] else file_size - 1

                # Clamp the range to valid values
                if start >= file_size:
                    return Response(status=416)  # Range Not Satisfiable

                # Ensure end doesn't exceed file size
                end = min(end, file_size - 1)

                # Calculate content length for the response
                length = end - start + 1

                # Create a streaming response for large files
                def generate():
                    nonlocal file_path  # Use nonlocal to access the variable from the outer scope
                    file_handle = None
                    current_position = start
                    bytes_sent = 0

                    try:
                        file_handle = open(file_path, "rb")
                        file_handle.seek(current_position)

                        while bytes_sent < length:
                            try:
                                # Read smaller chunks to avoid loading the entire range at once
                                chunk = file_handle.read(
                                    min(chunk_size, length - bytes_sent)
                                )
                                if not chunk:
                                    break
                                bytes_sent += len(chunk)
                                current_position += len(chunk)
                                yield chunk

                            except (IOError, OSError):
                                # File access error occurred - the file might have been moved
                                if file_handle:
                                    file_handle.close()

                                # Try to resolve the bookmark again
                                conn = sqlite3.connect(config.DB_PATH)
                                cursor = conn.cursor()
                                cursor.execute(
                                    'SELECT uri FROM media WHERE id = ? AND source = "local"',
                                    (id,),
                                )
                                bookmark_result = cursor.fetchone()
                                conn.close()

                                if not bookmark_result:
                                    raise FileNotFoundError(
                                        "Media record no longer exists"
                                    )

                                new_file_path = resolve_bookmark(bookmark_result[0])
                                if not new_file_path:
                                    raise FileNotFoundError("File could not be located")

                                file_path = new_file_path  # Now properly updates the outer variable

                                # Open the new file location and seek to the current position
                                file_handle = open(file_path, "rb")
                                file_handle.seek(current_position)

                    except Exception as e:
                        # Log the error for debugging
                        print(f"Error during streaming: {str(e)}")
                        # Close the file handle if it's open
                        if file_handle:
                            file_handle.close()
                        # Re-raise to be caught by the outer exception handler
                        raise

                    finally:
                        # Ensure file is closed when done
                        if file_handle:
                            file_handle.close()

                # Create the streaming response with the partial content
                resp = Response(
                    generate(),
                    206,
                    mimetype=content_type,
                    content_type=content_type,
                    direct_passthrough=True,
                )
                resp.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
                resp.headers.add("Accept-Ranges", "bytes")
                resp.headers.add("Content-Length", str(length))
                resp.headers.add("ETag", etag)
                resp.headers.add(
                    "Cache-Control", "private, max-age=3600"
                )  # 1 hour client-side cache
                return resp

            except (ValueError, IndexError) as e:
                # Handle malformed range header
                return Response(f"Invalid range header: {str(e)}", status=400)
            except FileNotFoundError as e:
                return Response(f"File not found: {str(e)}", status=404)
        else:
            # For non-range requests, we need to handle file moves
            # Create a custom file sender
            def custom_send_file():
                nonlocal file_path  # Use nonlocal to access the variable from the outer scope
                try:
                    return send_file(
                        file_path,
                        mimetype=content_type,
                        as_attachment=False,
                        conditional=True,
                    )
                except (IOError, OSError):
                    # Try to resolve the bookmark again
                    conn = sqlite3.connect(config.DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT uri FROM media WHERE id = ? AND source = "local"', (id,)
                    )
                    bookmark_result = cursor.fetchone()
                    conn.close()

                    if not bookmark_result:
                        return Response("Media record no longer exists", status=404)

                    new_file_path = resolve_bookmark(bookmark_result[0])
                    if not new_file_path:
                        return Response("File could not be located", status=404)

                    file_path = new_file_path  # Update the outer scope variable

                    # Try with the new path
                    return send_file(
                        file_path,
                        mimetype=content_type,
                        as_attachment=False,
                        conditional=True,
                    )

            response = custom_send_file()
            if isinstance(response, Response):
                response.headers.add("Accept-Ranges", "bytes")
                response.headers.add("ETag", etag)
                response.headers.add(
                    "Cache-Control", "private, max-age=3600"
                )  # 1 hour client-side cache
            return response

    except Exception as e:
        return Response(f"Error streaming file: {str(e)}", status=500)