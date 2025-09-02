export async function check_media_item_exists(video_id) {
    const response = await fetch('/api/check_media_item_exists', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            video_id: video_id
        })
    });

    if (response.status === 200) {
        const data = await response.json();
        return data.id;
    } else {
        return false;
    }
}

export async function fetch_media_previews() {

    const response = await fetch('/api/fetch_media_previews', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    });

    if (response.status === 200) {
        return await response.json();
    } else {
        return false;
    }
}

export async function fetch_media_item(id) {
    const response = await fetch('/api/fetch_media_item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id
        })
    });

    if (response.status === 200) {
        const media_data = await response.json();
        return media_data;
    } else {
        return { error: true, status: response.status };
    }
}

export async function delete_media_item(ids) {
    const response = await fetch('/api/delete_media_item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ids: ids
        })
    });

    return response.ok;
}

export async function retry_processing(id, jobs_to_retry, force_get_raw_stream = null) {
    const response = await fetch('/api/retry_processing', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            jobs_to_retry: jobs_to_retry,
            force_get_raw_stream: force_get_raw_stream
        })
    });
    return response.status === 200;
}

export async function get_setting(key) {
    const response = await fetch(`/api/get_setting?key=${key}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    });

    if (response.status === 200) {
        const data = await response.json();
        return data[key];
    } else {
        return null;
    }
}

export async function set_setting(key, value) {
    const response = await fetch('/api/set_setting', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            key: key,
            value: value
        })
    });

    return response.status === 200;
}

export async function set_multiple_settings(settings_dict) {
    const response = await fetch('/api/set_multiple_settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings_dict)
    });

    return response.status === 200;
}

export async function get_all_settings() {
    const response = await fetch(`/api/get_all_settings`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    });

    if (response.status === 200) {
        return await response.json();
    } else {
        return null;
    }
}

export async function set_colorset(id, colorset_num) {
    const response = await fetch('/api/set_colorset', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            colorset_num: colorset_num
        })
    });

    return response.status === 200;
}

export async function set_speaker_visibility(id, speaker_visibility) {
    const response = await fetch('/api/set_speaker_visibility', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            speaker_visibility: speaker_visibility
        })
    });

    return response.status === 200;
}

export async function set_playback_position(id, playback_position) {
    const response = await fetch('/api/set_playback_position', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            playback_position: playback_position
        })
    });

    return response.status === 200;
}

export async function set_speaker_speeds(id, speaker_speeds) {
    const response = await fetch('/api/set_speaker_speeds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            speaker_speeds: speaker_speeds
        })
    });

    return response.status === 200;
}

export async function set_skip_silences(id, skip_silences) {
    const response = await fetch('/api/set_skip_silences', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            skip_silences: skip_silences
        })
    });

    return response.status === 200;
}

export async function set_zoom_window(id, zoom_window) {
    const response = await fetch('/api/set_zoom_window', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            zoom_window: zoom_window
        })
    });

    return response.status === 200;
}

export async function fetch_zanshin_version() {
    try {
        const response = await fetch('/api/zanshin_version');
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error fetching version:', error);
        return null;
    }
}

export async function set_duration(id, duration) {
    const response = await fetch('/api/set_duration', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            duration: duration
        })
    });

    return response.status === 200;
}

export async function set_auto_skip_disabled_speakers(id, auto_skip_disabled_speakers) {
    const response = await fetch('/api/set_auto_skip_disabled_speakers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: id,
            auto_skip_disabled_speakers: auto_skip_disabled_speakers
        })
    });

    return response.status === 200;
}