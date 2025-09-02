<script>
    import './MediaPlayer.css'
    import SrcYouTube from './SrcYouTube.svelte';
    import SrcHTMLPlayer from './SrcHTMLPlayer.svelte';
    import SegmentsBar from '$lib/SegmentsBar.svelte';
    import { format_duration } from '$lib/misc';
    import { onMount, onDestroy, createEventDispatcher, tick } from 'svelte';
    import { retry_processing, set_playback_position, set_duration, set_zoom_window, get_setting, set_auto_skip_disabled_speakers } from '$lib/api';
    import { socket } from '$lib/socket.js';
    import { invalidateAll, beforeNavigate } from '$app/navigation';
    import { browser } from '$app/environment';

    let {
        // Basic info
        id,
        source,
        media_type,
        uri,
        video_title,
        chapters,
        embeddable,
        video_stream_url,
        duration = $bindable(),
        aspect_ratio,

        // Segbar
        merged_segments,
        speaker_color_sets,
        selected_colorset_num = $bindable(),
        storyboards_fetched,
        seconds_per_frame,
        available_timestamps,

        // Saved
        saved_current_time = 0,
        saved_zoom_window = null,
        speaker_visibility = {},
        is_speaker_visible,
        get_speaker_speed,
        panels_visible = $bindable(),
        skip_silences = $bindable(),
        auto_skip_disabled_speakers = $bindable(),

        // Bindable state
        current_time = $bindable(),
        hovered_speaker = $bindable(),
        hovered_speaker_from_panel = $bindable(),
        dragging = $bindable()

    } = $props();

    const dispatch = createEventDispatcher();

    /*
    =========================================================
        Player options
    =========================================================
    */

    let tint_when_paused = $state(true)
    let big_play_button_when_paused = $state(true);

    /*
    =========================================================
        Player state
    =========================================================
    */

    let player = $state();
    let player_is_ready = $state(false);
    let refetching_stream = $state(false);
    let player_error = $state(false);
    let first_time_update_received = $state(false);
    let play_scheduled = $state(false);
    let is_playing = $state(false);
    let is_muted = $state(false);
    let last_saved_time = current_time;

    let original_start_time = current_time;
    let paused_time = current_time;

    // If user clicks play before player is ready
    $effect(() => {
        if (player_is_ready && play_scheduled) {
            play_scheduled = false;
            toggle_play_pause();
        }
    });

    /*
    =========================================================
        Current position in video saving
    =========================================================
    */

    const save_playback_position_before_unload = () => {
        if (current_time !== last_saved_time) {
            // Use fetch with keepalive for reliable saving during page unload
            fetch('/api/set_playback_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, playback_position: current_time }),
                keepalive: true
            });
        }
    };

    const save_zoom_window_before_unload = () => {
        if (zoom_window !== last_saved_zoom_window) {
            // Use fetch with keepalive for reliable saving during page unload
            fetch('/api/set_zoom_window', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, zoom_window: zoom_window }),
                keepalive: true
            });
        }
    };

    onMount(() => {
        window.addEventListener('beforeunload', save_playback_position_before_unload);
        window.addEventListener('beforeunload', save_zoom_window_before_unload);
    });

    onDestroy(() => {
        window.removeEventListener('beforeunload', save_playback_position_before_unload);
        window.removeEventListener('beforeunload', save_zoom_window_before_unload);
    });

    beforeNavigate(() => {
        // Save final position before leaving
        if (current_time !== last_saved_time && id && current_time) {
            set_playback_position(id, current_time);
        }

        // Save final zoom window before leaving
        if (zoom_window !== last_saved_zoom_window && id) {
            set_zoom_window(id, zoom_window);
        }

        // Reset auto_skip_disabled_speakers if there are no disabled speakers
        if (merged_segments && speaker_visibility) {
            const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
            const has_disabled_speakers = speakers.some(speaker => !is_speaker_visible(speaker));
            // If no speakers are disabled, reset auto_skip_disabled_speakers to NULL
            if (!has_disabled_speakers) {
                set_auto_skip_disabled_speakers(id, null);
            }
        }
    });

    /*
    =========================================================
        Keyboard shortcuts
    =========================================================
    */

    function handleKeydown(event) {
        // Only handle keyboard events if we're not in an input field
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (event.code) {
            case 'Space':
                event.preventDefault();
                toggle_play_pause();
                break;
            case 'ArrowRight':
                event.preventDefault();
                if (player && player_is_ready) {
                    const target_time = Math.min(current_time + 5, duration || 0);
                    const optimal_time = get_optimal_seek_time(target_time, false, false, false);
                    seekTo(optimal_time, false, false);
                }
                break;
                case 'ArrowLeft':
                    event.preventDefault();
                    if (player && player_is_ready) {
                        const target_time = Math.max(current_time - 5, 0);

                        // Check if we would land on unchecked content
                        const target_segment = findCurrentSegment(target_time);
                        const would_land_on_unchecked =
                            (target_segment && !is_speaker_visible(target_segment.speaker)) ||
                            (skip_silences && !target_segment);

                        if (would_land_on_unchecked) {
                            // Look backwards to find the last checked speaker or audible content
                            const segments = merged_segments || [];
                            let found_segment = null;

                            // Search backwards from current time
                            for (let i = segments.length - 1; i >= 0; i--) {
                                const segment = segments[i];
                                if (segment.end <= current_time && is_speaker_visible(segment.speaker)) {
                                    found_segment = segment;
                                    break;
                                }
                            }

                            if (found_segment) {
                                // Calculate seek position: end of segment - 5 seconds, or start if segment < 5 seconds
                                const segment_duration = found_segment.end - found_segment.start;
                                const seek_time = segment_duration >= 5
                                    ? found_segment.end - 5
                                    : found_segment.start;
                                seekTo(Math.max(0, seek_time));
                            } else {
                                // No previous checked segment found, go to beginning
                                seekTo(0);
                            }
                        } else {
                            // Normal rewind - no conflict with unchecked content
                            const optimal_time = get_optimal_seek_time(target_time, false, false, false);
                            seekTo(optimal_time, false, false);
                        }
                    }
                    break;
            case 'KeyI':
                event.preventDefault();
                panels_visible = !panels_visible;
                break;
            case 'Comma': // < key
                event.preventDefault();
                seekToPreviousVisibleSegment();
                break;
            case 'Period': // > key
                event.preventDefault();
                seekToNextVisibleSegment();
                break;
            case 'KeyV':
                event.preventDefault();
                if (duration && segbar) {
                    // Calculate current position as a fraction of total duration
                    const current_position = current_time / duration;

                    // Get current zoom window size
                    const window_size = zoom_window.end - zoom_window.start;

                    // Calculate new start position to place current time at 10% of the window
                    let new_start = current_position - (0.1 * window_size);
                    let new_end = new_start + window_size;

                    // Adjust if we're outside bounds
                    if (new_start < 0) {
                        new_start = 0;
                        new_end = window_size;
                    }
                    if (new_end > 1) {
                        new_end = 1;
                        new_start = 1 - window_size;
                    }

                    // Animate to new zoom window
                    animateZoomWindow({ start: new_start, end: new_end });
                }
                break;
            case 'KeyG':
                event.preventDefault();
                if (hovered_speaker !== null && chapters && chapters.length > 0) {
                    // Find the chapter that contains the hovered time
                    const current_chapter = chapters.find(chapter =>
                        hovered_time >= chapter.start_time && hovered_time < chapter.end_time
                    );

                    if (current_chapter) {
                        seekTo(current_chapter.start_time, true); // use chapter logic for smart seeking
                    }
                }
                break;
            case 'BracketLeft': // { key
                event.preventDefault();
                if (player && player_is_ready) {
                    seekToPreviousSpeakerSegment();
                }
                break;
            case 'BracketRight': // } key
                event.preventDefault();
                if (player && player_is_ready) {
                    const current_segment = findCurrentSegment(current_time);
                    if (current_segment) {
                        seekToNextSpeakerSegment(current_segment.speaker);
                    }
                }
                break;
            case 'KeyK':
                event.preventDefault();
                if (player && player_is_ready) {
                    seekTo(0);
                }
                break;
            case 'KeyM':
                event.preventDefault();
                if (player && player_is_ready) {
                    if (is_muted) {
                        player.unMute();
                        is_muted = false;
                    } else {
                        player.mute();
                        is_muted = true;
                    }
                }
                break;
            case 'KeyT':
                event.preventDefault();
                // Only toggle if there are disabled speakers
                if (merged_segments && speaker_visibility) {
                    const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
                    const has_disabled_speakers = speakers.some(speaker => !is_speaker_visible(speaker));

                    if (has_disabled_speakers) {
                        // Toggle auto_skip_disabled_speakers
                        const new_value = !(auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1);
                        auto_skip_disabled_speakers = new_value;
                        set_auto_skip_disabled_speakers(id, new_value);
                    }
                }
                break;
        }
    }

    onMount(() => {
        if (browser) {
            document.addEventListener('keydown', handleKeydown);
        }
    });

    onDestroy(() => {
        if (browser) {
            document.removeEventListener('keydown', handleKeydown);
        }
    });

    function seekToNextVisibleSegment() {
        if (!merged_segments) return;

        const segments = merged_segments;
        const current_segment = findCurrentSegment(current_time);
        const should_skip_invisible = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;

        if (current_segment) {
            // Find the next segment after the current one
            for (let i = current_segment.index + 1; i < segments.length; i++) {
                const segment = segments[i];

                // If auto-skip is enabled, only consider visible speakers
                // If auto-skip is disabled, consider all speakers
                if (!should_skip_invisible || is_speaker_visible(segment.speaker)) {
                    seekTo(segment.start);
                    return;
                }
            }
        } else {
            // If we're not in any segment, find the first segment after current time
            for (let i = 0; i < segments.length; i++) {
                const segment = segments[i];
                if (segment.start > current_time) {
                    if (!should_skip_invisible || is_speaker_visible(segment.speaker)) {
                        seekTo(segment.start);
                        return;
                    }
                }
            }
        }

        // No suitable next segment found - function exits without seeking
    }

    function seekToPreviousVisibleSegment() {
        if (!merged_segments) return;

        const segments = merged_segments;
        const current_segment = findCurrentSegment(current_time);

        if (current_segment) {
            // Check if we're within 5 seconds of the segment start
            const time_from_start = current_time - current_segment.start;

            if (time_from_start > 5) {
                // Not within 5s of start, seek to beginning of current segment
                seekTo(current_segment.start);
                return;
            }

            // Within 5s of start, find previous segment
            // Start from the segment before current one
            for (let i = current_segment.index - 1; i >= 0; i--) {
                const segment = segments[i];

                // If auto-skip is enabled, only consider visible speakers
                // If auto-skip is disabled, consider all speakers
                const should_skip_invisible = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;

                if (!should_skip_invisible || is_speaker_visible(segment.speaker)) {
                    seekTo(segment.start);
                    return;
                }
            }
        } else {
            // Not in any segment, find the last segment before current time
            for (let i = segments.length - 1; i >= 0; i--) {
                const segment = segments[i];
                if (segment.end <= current_time) {
                    const should_skip_invisible = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;

                    if (!should_skip_invisible || is_speaker_visible(segment.speaker)) {
                        seekTo(segment.start);
                        return;
                    }
                }
            }
        }

        // If no suitable segment found, seek to beginning
        seekTo(0);
    }

    function seekToPreviousSpeakerSegment() {
        if (!merged_segments) return;

        const segments = merged_segments;
        const current_segment = findCurrentSegment(current_time);

        if (!current_segment) return; // Not in any segment

        const current_speaker = current_segment.speaker;

        // Find the previous segment for this speaker before current time
        let previous_segment = null;

        for (let i = segments.length - 1; i >= 0; i--) {
            const segment = segments[i];
            if (segment.speaker === current_speaker && segment.end <= current_time) {
                previous_segment = segment;
                break;
            }
        }

        if (previous_segment) {
            seekTo(previous_segment.start);
        }
    }

    /*
    =========================================================
        Zoom window animation (slide segbar)
    =========================================================
    */

    let zoom_animation_frame = null;
    let zoom_animation_start_time = null;
    let zoom_animation_start_window = null;
    let zoom_animation_target_window = null;
    const ZOOM_ANIMATION_DURATION = 300; // milliseconds

    function animateZoomWindow(targetWindow, speedMultiplier = 1.0) {
        // Cancel any ongoing animation
        if (zoom_animation_frame) {
            cancelAnimationFrame(zoom_animation_frame);
        }

        // Set up animation parameters
        zoom_animation_start_time = performance.now();
        zoom_animation_start_window = { ...zoom_window };
        zoom_animation_target_window = targetWindow;
        const animation_duration = ZOOM_ANIMATION_DURATION / speedMultiplier;

        // Start animation loop
        function animate() {
            const elapsed = performance.now() - zoom_animation_start_time;
            const progress = Math.min(elapsed / animation_duration, 1);

            // Use easeInOutCubic easing function
            const eased = progress < 0.5
                ? 4 * progress * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 3) / 2;

            // Interpolate between start and target windows
            zoom_window = {
                start: zoom_animation_start_window.start + (zoom_animation_target_window.start - zoom_animation_start_window.start) * eased,
                end: zoom_animation_start_window.end + (zoom_animation_target_window.end - zoom_animation_start_window.end) * eased
            };

            if (progress < 1) {
                zoom_animation_frame = requestAnimationFrame(animate);
            } else {
                // Animation complete
                zoom_animation_frame = null;
                zoom_animation_start_time = null;
                zoom_animation_start_window = null;
                zoom_animation_target_window = null;
            }
        }

        animate();
    }

    let last_user_interaction_time = $state(Date.now());
    let auto_slide_timeout = null;
    let marker_out_of_view_time = $state(null);
    let thresholds = [96, 98, 100]; // Array of thresholds as percentages
    let was_below_thresholds = $state(Object.fromEntries(thresholds.map(t => [t, true]))); // Track if marker was below each threshold

    function on_segbar_interaction() {
        last_user_interaction_time = Date.now();

        // Cancel zoom restoration if user interacts with progress bar
        progress_bar_interacted = true;
        zoom_restoration_disabled_until = 0; // Re-enable auto-slide immediately
        if (zoom_restoration_timeout) {
            clearTimeout(zoom_restoration_timeout);
            zoom_restoration_timeout = null;
        }

        // Cancel any ongoing zoom animation
        if (zoom_animation_frame) {
            cancelAnimationFrame(zoom_animation_frame);
            zoom_animation_frame = null;
            zoom_animation_start_time = null;
            zoom_animation_start_window = null;
            zoom_animation_target_window = null;
        }

        // Clear any pending auto-slide
        if (auto_slide_timeout) {
            clearTimeout(auto_slide_timeout);
            auto_slide_timeout = null;
        }
        marker_out_of_view_time = null;
    }

    let auto_slide_check_interval = null;
    let previous_marker_in_window = $state(false);

    function check_auto_slide() {
        if (!duration || !segbar || Date.now() < zoom_restoration_disabled_until) return;

        // Calculate marker's position in the zoom window
        const current_position = current_time / duration;
        const zoom_window_size = zoom_window.end - zoom_window.start;
        const marker_in_window = current_position >= zoom_window.start && current_position <= zoom_window.end;
        const marker_window_position = (current_position - zoom_window.start) / zoom_window_size; // 0 to 1 within window

        // Check if enough time has passed since last interaction (5 seconds)
        const time_since_interaction = Date.now() - last_user_interaction_time;
        const interaction_cooldown_passed = time_since_interaction > 1000;

        if (marker_in_window && interaction_cooldown_passed) {
            // Existing logic for rising edges when marker is in window
            let trigger_auto_slide = false;

            // Create a new state object for the next check
            const new_was_below = { ...was_below_thresholds };

            // Check each threshold for a rising edge
            for (const threshold_percent of thresholds) {
                const threshold = threshold_percent / 100; // Convert percentage to fraction
                const is_above_threshold = threshold_percent === 100 ? marker_window_position >= threshold : marker_window_position > threshold;

                // Detect rising edge: was below and now above (or at for 100%)
                if (was_below_thresholds[threshold_percent] && is_above_threshold) {
                    // Avoid triggering for lower thresholds if already past 100%
                    if (threshold_percent < 100 && marker_window_position >= 1.0) {
                        new_was_below[threshold_percent] = false;
                        continue;
                    }
                    trigger_auto_slide = true;
                }

                // Update state for this threshold
                new_was_below[threshold_percent] = !is_above_threshold;
            }

            // Trigger auto-slide if any rising edge was detected (and not dragging)
            if (trigger_auto_slide && !auto_slide_timeout && !dragging) {
                auto_slide_timeout = setTimeout(() => {
                    const window_size = zoom_window.end - zoom_window.start;
                    let new_start = current_position - (0.1 * window_size); // Place marker at 10% of window
                    let new_end = new_start + window_size;

                    // Adjust if outside bounds
                    if (new_start < 0) {
                        new_start = 0;
                        new_end = window_size;
                    }
                    if (new_end > 1) {
                        new_end = 1;
                        new_start = 1 - window_size;
                    }

                    // Animate to new zoom window
                    animateZoomWindow({ start: new_start, end: new_end });
                    auto_slide_timeout = null;
                }, 0);
            }

            // Update the state for the next check
            was_below_thresholds = new_was_below;
        } else if (previous_marker_in_window && !marker_in_window && interaction_cooldown_passed && !dragging) {
            // Handle case where marker jumped out of window (due to seeking forward or backward)
            if (!auto_slide_timeout) {
                auto_slide_timeout = setTimeout(() => {
                    const window_size = zoom_window.end - zoom_window.start;
                    let new_start = current_position - (0.1 * window_size); // Place marker at 10% of window
                    let new_end = new_start + window_size;

                    // Adjust if outside bounds
                    if (new_start < 0) {
                        new_start = 0;
                        new_end = window_size;
                    }
                    if (new_end > 1) {
                        new_end = 1;
                        new_start = 1 - window_size;
                    }

                    // Animate to new zoom window
                    animateZoomWindow({ start: new_start, end: new_end });
                    auto_slide_timeout = null;
                }, 0);
            }
        } else {
            // Reset state if marker is out of view or cooldown hasn't passed
            was_below_thresholds = Object.fromEntries(thresholds.map(t => [t, true])); // Reset all to true
            if (auto_slide_timeout) {
                clearTimeout(auto_slide_timeout);
                auto_slide_timeout = null;
            }
            marker_out_of_view_time = null;
        }

        // Update previous state for next check
        previous_marker_in_window = marker_in_window;
    }

    $effect(() => {
        if (duration && segbar) {
            // Start monitoring when playing
            if (!auto_slide_check_interval) {
                auto_slide_check_interval = setInterval(check_auto_slide, 100);
            }
        } else {
            // Stop monitoring when not playing
            if (auto_slide_check_interval) {
                clearInterval(auto_slide_check_interval);
                auto_slide_check_interval = null;
            }
            // Reset state when stopping
            was_below_thresholds = Object.fromEntries(thresholds.map(t => [t, true]));
            marker_out_of_view_time = null;
            if (auto_slide_timeout) {
                clearTimeout(auto_slide_timeout);
                auto_slide_timeout = null;
            }
        }
    });

    // Clean up timeout on destroy
    onDestroy(() => {
        if (auto_slide_timeout) {
            clearTimeout(auto_slide_timeout);
        }
        if (zoom_animation_frame) {
            cancelAnimationFrame(zoom_animation_frame);
        }
        if (auto_slide_check_interval) {
            clearInterval(auto_slide_check_interval);
        }
        if (zoom_window_save_timer) {
            clearTimeout(zoom_window_save_timer);
        }
        if (zoom_restoration_timeout) {
            clearTimeout(zoom_restoration_timeout);
        }
    });

    /*
    =========================================================
        Player control
    =========================================================
    */

    function toggle_play_pause() {
        if (player_is_ready) {
            if (is_playing) {
                player.pause();
                is_playing = false;
            } else {
                player.play();
                is_playing = true;
            }
        } else {
            play_scheduled = !play_scheduled;
        }
    }

    /*
    =========================================================
        When tab out of focus
    =========================================================
    */

    let tab_unfocussed_update_interval = null;
    let tab_is_focussed = $state(true);

    onMount(() => {
        if (browser) {
            document.addEventListener('visibilitychange', handle_visibility_change);
            tab_is_focussed = !document.hidden;
        }
    });

    onDestroy(() => {
        if (browser) {
            document.removeEventListener('visibilitychange', handle_visibility_change);
            if (tab_unfocussed_update_interval) clearInterval(tab_unfocussed_update_interval);
        }
    });

    function handle_visibility_change() {
        if (browser) {
            tab_is_focussed = !document.hidden;
            if (tab_is_focussed) {
                // Tab became visible - stop interval, requestAnimationFrame will handle it
                if (tab_unfocussed_update_interval) {
                    clearInterval(tab_unfocussed_update_interval);
                    tab_unfocussed_update_interval = null;
                }
            } else {
                // Tab became hidden - start interval for auto-skip
                if (is_playing && merged_segments && merged_segments) {
                    start_tab_unfocussed_update_interval();
                }
            }
        }
    }

    function start_tab_unfocussed_update_interval() {
        if (tab_unfocussed_update_interval) clearInterval(tab_unfocussed_update_interval);
        tab_unfocussed_update_interval = setInterval(() => {
            if (is_playing && merged_segments && merged_segments && player) {
                const real_time = player.getCurrentTime();
                current_time = real_time;
                auto_skip_unchecked_speakers(real_time);
                update_speaker_speed(real_time);
            }
        }, 50);
    }

    /*
    =========================================================
        Player event handlers
    =========================================================
    */

    function on_ready() {
        is_playing = player.is_playing();
        is_muted = player.is_muted();

        const stored_duration = duration;
        duration = player.get_duration();

        // If duration (new) doesn't match stored_duration, then update it
        if (duration !== stored_duration) {
            set_duration(id, duration);
        }

        player_is_ready = true;
    }

    function on_play() {
        is_playing = true;

        // If tab is hidden, start the interval
        if (!tab_is_focussed && merged_segments && merged_segments) {
            start_tab_unfocussed_update_interval();
        }
    }


    function on_pause() {
        is_playing = false;

        // Stop the interval when paused
        if (tab_unfocussed_update_interval) {
            clearInterval(tab_unfocussed_update_interval);
            tab_unfocussed_update_interval = null;
        }

        paused_time = current_time;

        // Save current time immediately when pausing
        if (current_time !== last_saved_time && id && current_time) {
            set_playback_position(id, current_time);
            last_saved_time = current_time;
        }
    }

    function on_time_update(e) {
        current_time = e.detail;
        paused_time = e.detail;

        if (!first_time_update_received) {
            first_time_update_received = true;
        }

        // Auto-skip functionality - only when tab is visible
        if (is_playing && merged_segments && merged_segments && tab_is_focussed) {
            auto_skip_unchecked_speakers(e.detail);
            update_speaker_speed(e.detail);
        }

        const save_current_time_throttled = (time) => {
            // Only save if time has changed significantly (more than 1 second)
            if (Math.abs(time - last_saved_time) >= 1 && id && current_time) {
                // Save immediately when threshold is crossed
                set_playback_position(id, time);
                last_saved_time = time;
            }
        }

        // Save current time periodically (throttled to avoid too many API calls)
        save_current_time_throttled(e.detail);

        // if (current_time >= duration) {
        //     player.pause();
        //     is_playing = false;
        //     on_end();
        // }
    }

    function on_end() {
        current_time = 0;
        original_start_time = current_time;
        paused_time = current_time;

        zoom_window = {start: 0, end: 1};

        is_playing = false;
        first_time_update_received = false;

        // Clean up interval
        if (tab_unfocussed_update_interval) {
            clearInterval(tab_unfocussed_update_interval);
            tab_unfocussed_update_interval = null;
        }
    }

    function on_error(e) {
        console.error('Error:', e.detail.code)
        if ([4, 101, 150].includes(e.detail.code) && source === 'youtube') {
            // refetch stream
            retry_processing(id, ['metadata_refetch'], true);  // error 101,150 mean video is officially "embeddable" but actually is not; so we force fetch stream and set embeddable to false
            refetching_stream = true;
        } else {
            // Some local file error, likely file deleted
            player_error = true;
        }
    }

    /*
    =========================================================
        Segments bar
    =========================================================
    */

    let segbar = $state(null);
    let zoom_window = $state({start: 0, end: 1});
    let progress = $derived(current_time / duration);
    let progress_in_window = $derived((progress - zoom_window.start) / (zoom_window.end - zoom_window.start));
    let hovered_time = $state(0);

    let last_saved_zoom_window = zoom_window;
    let zoom_window_save_timer;
    let zoom_restoration_timeout;
    let progress_bar_interacted = $state(false);
    let zoom_restoration_disabled_until = $state(0);

    // Save zoom window changes with debouncing (similar to colorset saving)
    $effect(() => {
        // Clear any existing timer
        if (zoom_window_save_timer) {
            clearTimeout(zoom_window_save_timer);
        }

        // Save zoom window changes (save all states, including {start: 0, end: 1})
        if (zoom_window !== last_saved_zoom_window) {
            zoom_window_save_timer = setTimeout(() => {
                last_saved_zoom_window = zoom_window;
                set_zoom_window(id, zoom_window);
                zoom_window_save_timer = null;
            }, 1000);
        }
    });

    // Restore saved zoom window on page load
    onMount(async () => {
        // Check if zoom window restoration is enabled in settings
        const restore_zoom_window_enabled = await get_setting('restore_zoom_window');

        // Only restore if setting is enabled, saved zoom window exists and is not the default full window
        if (restore_zoom_window_enabled && saved_zoom_window && !progress_bar_interacted &&
            !(saved_zoom_window.start === 0 && saved_zoom_window.end === 1)) {
            zoom_restoration_timeout = setTimeout(() => {
                if (!progress_bar_interacted) {
                    // Disable auto-slide for 3 seconds (1s animation + 2s grace period)
                    zoom_restoration_disabled_until = Date.now() + 3000;
                    animateZoomWindow(saved_zoom_window, 0.5); // Half speed for restoration
                }
            }, 500);
        }
    });

    function get_progress_in_window() {
        if (progress_in_window >= 0 && progress_in_window <= 1) {
            return progress_in_window * 100;
        } else {
            return null; // marker is outside the window
        }
    }

    export async function seekTo(time, use_chapter_logic = false, is_manual_seek = true) {
        const optimal_time = get_optimal_seek_time(time, use_chapter_logic, false, is_manual_seek);
        current_time = optimal_time;
        paused_time = optimal_time;
        await tick();

        player.stopTimeUpdates();

        // Use appropriate smart seeking based on context
        current_time = optimal_time; // this line is required. yes I know we set this above already, but for some reason (that I don't understand) without this line, the curr time marker doesn't move instantly
        player.seekTo(optimal_time);

        if (!first_time_update_received) {
            // player.mute();
            // is_muted = true;
            player.play();
            is_playing = true;
        }

        setTimeout(() => {player.startTimeUpdates()}, 100);
    }

    /*
    =========================================================
        Auto-skip functionality
    =========================================================
    */

    let cached_segment_index = $state(-1);

    $effect(() => {
        if (merged_segments) {
            cached_segment_index = -1;
        }
    });

    function findCurrentSegment(time) {
        if (!merged_segments) return null;

        const segments = merged_segments;

        // Check if we're still in the cached segment
        if (cached_segment_index >= 0 && cached_segment_index < segments.length) {
            const segment = segments[cached_segment_index];
            if (time >= segment.start && time < segment.end) {
                return { ...segment, index: cached_segment_index };
            }

            // Check next segment (common case when playing forward)
            if (cached_segment_index + 1 < segments.length) {
                const nextSegment = segments[cached_segment_index + 1];
                if (time >= nextSegment.start && time < nextSegment.end) {
                    cached_segment_index++;
                    return { ...nextSegment, index: cached_segment_index };
                }
            }

            // Check previous segment (for rewinding)
            if (cached_segment_index > 0) {
                const prevSegment = segments[cached_segment_index - 1];
                if (time >= prevSegment.start && time < prevSegment.end) {
                    cached_segment_index--;
                    return { ...prevSegment, index: cached_segment_index };
                }
            }
        }

        // Fall back to full search
        const index = segments.findIndex(segment =>
            time >= segment.start && time < segment.end
        );

        if (index !== -1) {
            cached_segment_index = index;
            return { ...segments[index], index: index };
        }

        cached_segment_index = -1;
        return null;
    }

    function get_optimal_seek_time(time, chapter_skip, require_min_distance, is_manual_seek = false) {
        if (!merged_segments) return time;

        const segments = merged_segments;
        const current_segment = findCurrentSegment(time);

        const handleNoMoreSegments = function(current_segment, skip_silences, duration, time) {
            if (!current_segment) {
                // We're in silence - only skip if skip_silences is enabled
                // But don't skip to duration if we're already very close to it
                if (skip_silences && duration && time < duration - 0.5) {
                    return duration;
                } else {
                    return time;
                }
            } else if (!is_speaker_visible(current_segment.speaker)) {
                // We're in an invisible segment - only skip if auto-skip is explicitly enabled
                // If setting is null/undefined, don't skip (let user's default be applied first)
                const should_auto_skip = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;
                return (should_auto_skip && !is_manual_seek) ? current_segment.end : time;
            } else {
                // We're in a visible segment, no need to skip
                return time;
            }
        };

        if (chapter_skip) {
            // Chapter skip mode - do the fancy checks for upcoming unchecked speakers

            // Check if we're within 3 seconds before an unchecked speaker's segment
            const upcoming_unchecked_segment = segments.find(seg =>
                seg.start > time &&
                seg.start <= time + 3 &&
                !is_speaker_visible(seg.speaker)
            );

            // If we have a segment at target time and speaker is unchecked, skip if auto-skip is explicitly enabled
            if (current_segment && !is_speaker_visible(current_segment.speaker)) {
                const should_auto_skip = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;
                if (should_auto_skip) {
                    const next_visible_segment = segments.find(seg =>
                        seg.start >= time && is_speaker_visible(seg.speaker)
                    );
                    return next_visible_segment ? next_visible_segment.start : time;
                } else {
                    return time; // Allow seeking to disabled speakers when auto-skip is off
                }
            }

            // If we're within 3 seconds of an unchecked speaker starting, skip ahead if auto-skip is explicitly enabled
            if (upcoming_unchecked_segment) {
                const should_auto_skip = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;
                if (should_auto_skip) {
                    const next_visible_segment = segments.find(seg =>
                        seg.start >= upcoming_unchecked_segment.start && is_speaker_visible(seg.speaker)
                    );
                    return next_visible_segment ? next_visible_segment.start : time;
                }
            }

            // Otherwise, use original time
            return time;

        } else {
            // Auto-skip mode - logic for continuous playback skipping

            const has_disabled_speakers = Object.values(speaker_visibility).some(visible => !visible);

            if (has_disabled_speakers && !(skip_silences && !current_segment)) {
                // For manual seeks when auto-skip is disabled, allow seeking anywhere
                if (is_manual_seek && (auto_skip_disabled_speakers === false || auto_skip_disabled_speakers === 0)) {
                    return time;
                }

                // Only apply auto-skip logic if the setting is explicitly enabled
                const should_auto_skip = auto_skip_disabled_speakers === true || auto_skip_disabled_speakers === 1;

                // If auto-skip is not explicitly enabled, don't skip disabled speakers
                if (!should_auto_skip && !is_manual_seek) {
                    return time;
                }
            }

            // Determine if we should skip
            const should_skip =
                (current_segment && !is_speaker_visible(current_segment.speaker)) ||  // Unchecked speaker
                (skip_silences && !current_segment);                                  // Silence (when enabled)

            if (!should_skip) {
                return time; // No need to skip
            }

            let next_segment_index = cached_segment_index >= 0 ? cached_segment_index : 0;

            // Find first segment after current time
            while (next_segment_index < segments.length && segments[next_segment_index].start <= time) {
                next_segment_index++;
            }

            if (next_segment_index >= segments.length) {
                // No more segments after current time
                return handleNoMoreSegments(current_segment, skip_silences, duration, time);
            }

            let total_skip_distance = segments[next_segment_index].start - time;
            let current_check_index = next_segment_index;

            // Add consecutive invisible segments
            while (current_check_index < segments.length && !is_speaker_visible(segments[current_check_index].speaker)) {
                total_skip_distance += (segments[current_check_index].end - segments[current_check_index].start);

                // Add silence to next segment (if any)
                if (current_check_index + 1 < segments.length) {
                    total_skip_distance += (segments[current_check_index + 1].start - segments[current_check_index].end);
                    current_check_index++;
                } else {
                    current_check_index++;
                    break;
                }
            }

            // Apply minimum skip distance check only if required
            if (require_min_distance && total_skip_distance <= 0.5) {
                return time; // Don't skip if distance is too small
            }

            if (current_check_index < segments.length) {
                return segments[current_check_index].start;
            }

            // No more visible segments found
            return handleNoMoreSegments(current_segment, skip_silences, duration, time);
        }
    }

    let auto_skip_cooldown = $state(false);

    function auto_skip_unchecked_speakers(time) {
        // Skip if we're in cooldown period
        if (auto_skip_cooldown) {
            return;
        }

        const optimal_time = get_optimal_seek_time(time, false, true); // Uses default require_min_distance = true

        if (optimal_time !== time) {
            player.seekTo(optimal_time);
            current_time = optimal_time;

            // Add cooldown for local source
            if (source === 'local') {
                auto_skip_cooldown = true;
                setTimeout(() => {
                    auto_skip_cooldown = false;
                }, 200);
            }
        }
    }

    let current_speaker_speed = $state(1.0);
    let time_display_hovered = $state(false);
    let time_display_pressed = $state(false);

    /*
    =========================================================
        Effective time calculation
    =========================================================
    */

    function has_effective_time_changes() {
        const has_disabled_speakers = Object.values(speaker_visibility).some(visible => visible === false);
        return has_disabled_speakers || skip_silences;
    }

    function calculate_effective_total_time() {
        if (!merged_segments) return duration || 0;

        if (!has_effective_time_changes()) {
            // No changes - return original duration
            return duration || 0;
        }

        // Calculate time from enabled speakers only
        const enabled_speaker_time = merged_segments
            .filter(segment => is_speaker_visible(segment.speaker))
            .reduce((total, segment) => total + (segment.end - segment.start), 0);

        if (skip_silences) {
            // If skip silences is on, effective time is just the enabled speaker segments
            return enabled_speaker_time;
        } else {
            // If skip silences is off, we need to include silence gaps in the effective time
            // This means: total duration minus disabled speaker time
            const disabled_speaker_time = merged_segments
                .filter(segment => !is_speaker_visible(segment.speaker))
                .reduce((total, segment) => total + (segment.end - segment.start), 0);
            return (duration || 0) - disabled_speaker_time;
        }
    }

    function calculate_effective_current_time() {
        if (!merged_segments) return current_time;

        if (!has_effective_time_changes()) {
            // No changes - return original current time
            return current_time;
        }

        if (skip_silences) {
            // If skip silences is on, count only enabled speaker time up to current position
            let effective_time = 0;

            for (const segment of merged_segments) {
                if (!is_speaker_visible(segment.speaker)) continue;

                if (segment.end <= current_time) {
                    // Segment is completely before current time
                    effective_time += (segment.end - segment.start);
                } else if (segment.start <= current_time && current_time < segment.end) {
                    // Current time is within this segment
                    effective_time += (current_time - segment.start);
                    break;
                } else {
                    // Segment starts after current time
                    break;
                }
            }

            return effective_time;
        } else {
            // If skip silences is off, subtract disabled speaker time up to current position
            let disabled_time_passed = 0;

            for (const segment of merged_segments) {
                if (is_speaker_visible(segment.speaker)) continue;

                if (segment.end <= current_time) {
                    // Disabled segment is completely before current time
                    disabled_time_passed += (segment.end - segment.start);
                } else if (segment.start <= current_time && current_time < segment.end) {
                    // Current time is within a disabled segment
                    disabled_time_passed += (current_time - segment.start);
                    break;
                } else {
                    // Segment starts after current time
                    break;
                }
            }

            return current_time - disabled_time_passed;
        }
    }

    function calculate_time_saved() {
        if (!merged_segments || !has_effective_time_changes()) return 0;

        const total_duration = duration || 0;
        const effective_total_time = calculate_effective_total_time();

        // Time saved is always total duration minus effective time
        return total_duration - effective_total_time;
    }

    function update_speaker_speed(time) {
        if (!get_speaker_speed) return;

        // Find the current segment
        const current_segment = findCurrentSegment(time);

        if (current_segment) {
            const desired_speed = get_speaker_speed(current_segment.speaker);

            // Only update if speed has changed to avoid unnecessary player calls
            if (desired_speed !== current_speaker_speed) {
                current_speaker_speed = desired_speed;
                if (player && player.setPlaybackRate) {
                    player.setPlaybackRate(desired_speed);
                }
            }
        }
    }

    export function handle_speaker_visibility_change() {
        // Don't auto-skip if the auto_skip_disabled_speakers setting hasn't been determined yet
        // (i.e., it's still null, which means we're in the process of applying the user's default)
        if (auto_skip_disabled_speakers === null || auto_skip_disabled_speakers === undefined) {
            return; // Let the user's default setting be applied first
        }

        if (!first_time_update_received) {
            current_time = get_optimal_seek_time(original_start_time, false, false, false);
            // player.seekTo(current_time);
            // player.pause();
        } else if (first_time_update_received && !is_playing) {
            current_time = get_optimal_seek_time(paused_time, false, false, false);
        }
    }

    export function seekToNextSpeakerSegment(speaker) {
        if (!merged_segments) return;

        const segments = merged_segments;

        // Find the next segment for this speaker after current time
        const next_segment = segments.find(seg =>
            seg.speaker === speaker && seg.start > current_time
        );

        if (next_segment) {
            seekTo(next_segment.start);
        } else {
            // If no segment found after current time, wrap around to first segment of this speaker
            const first_segment = segments.find(seg => seg.speaker === speaker);
            if (first_segment) {
                seekTo(first_segment.start);
            }
        }
    }

    /*
    =========================================================
        Socket Comms
    =========================================================
    */

    onMount(() => {
        socket.connect();
        socket.on('connect', () => {
            console.log('ws connected');
        });
        socket.on('metadata_refresh', async () => {
            await invalidateAll();
            refetching_stream = false;
            console.log('metadata_refresh')
        });
    });

    onDestroy(() => {
        socket.off('connect');
        socket.off('metadata_refresh');
        if (socket.connected) socket.disconnect();
    });

</script>

<main>
    <div id="media-container">
        <div id="header" style={media_type === 'audio' ? 'border-bottom: none;' : ''}>
            <div id="header-left">
                <div id="header-icon"></div>
                {#if source == 'youtube'}
                    <a href="https://www.youtube.com/watch?v={uri}" id="header-text" target="_blank">{video_title ? video_title : `https://www.youtube.com/watch?v=${uri}`}</a>
                {:else}
                    <p id="header-text">{video_title}</p>
                {/if}
            </div>
            <div id="header-right">
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span class="info-link" class:active={panels_visible} onclick={() => { panels_visible = !panels_visible }}>
                    [i]
                </span>
            </div>
        </div>

        {#if refetching_stream || player_error}

            <div style="display: flex; justify-content: center; align-items: center; height: 100%; width: 100%;">
                <p style="padding: 40px; text-align: center; font-size: 20px;">
                    {refetching_stream ? 'Refetching stream...' : 'Error'}
                </p>
            </div>

        {:else}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div id="player-wrapper" onclick={toggle_play_pause} style={media_type === 'audio' ? 'display: none;' : ''}>
                <!-- Player container -->
                <div id="player-content">
                <div id="player-container" class:hidden={!first_time_update_received} style:filter={is_playing ? 'none' : (tint_when_paused ? 'brightness(0.7)' : 'none')}>
                    {#if source === 'youtube' && embeddable != false}
                        <!-- embeddable can be null (if metadata fetch failed) in which case (embeddable != false) will evaluate to true -->
                        <SrcYouTube
                            bind:this={player}
                            video_id={uri}
                            {aspect_ratio}
                            start_time={current_time}
                                on:ready={on_ready}
                                on:play={on_play}
                                on:pause={on_pause}
                                on:end={on_end}
                                on:timeupdate={on_time_update}
                                on:error={on_error}
                        />
                    {:else}
                        <SrcHTMLPlayer
                            bind:this={player}
                            id={id}
                            url={source === 'youtube' && !embeddable ? video_stream_url : `/api/stream/${id}`}
                            media_type={media_type}
                            {aspect_ratio}
                            start_time={current_time}
                                on:ready={on_ready}
                                on:play={on_play}
                                on:pause={on_pause}
                                on:end={on_end}
                                on:timeupdate={on_time_update}
                                on:error={on_error}
                        />
                    {/if}
                </div>

                {#if media_type === 'video'}
                <div id="thumbnail-overlay" style:z-index={!first_time_update_received || !is_playing ? 10 : -1}>
                    {#if !first_time_update_received}
                        <!-- Instead of fetching thumbnail data through data loading, put raw link here, so that browser can cache the images -->
                        <img src={`/api/thumbnail/${id}`} alt={video_title ? video_title : 'Thumbnail not available'} />
                    {/if}
                    {#if !first_time_update_received || !is_playing}
                        {#if tint_when_paused}
                            <div class="tint-overlay"></div>
                        {/if}
                    {/if}
                    {#if !is_playing}
                        {#if (!first_time_update_received || big_play_button_when_paused) && media_type == 'video'}
                            <button class="cs16-play-btn" aria-label="Play">
                                <div class="play-icon-large"></div>
                            </button>
                        {/if}
                    {/if}
                    </div>
                {/if}
            </div>
            </div>

            <div id="controls-container">
                <div id="controls-left">
                    <button class="cs-btn" id="play-pause-btn" aria-label="{is_playing ? 'Pause' : 'Play'}" onclick={toggle_play_pause}>
                        <div id={is_playing ? 'pause-icon' : 'play-icon'}></div>
                    </button>
                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                    <div
                        id="time-display"
                        style="width: {duration >= 3600 ? '105px' : '82px'}; cursor: {has_effective_time_changes() ? 'none' : 'default'}"
                        onmouseenter={() => time_display_hovered = true}
                        onmouseleave={() => { time_display_hovered = false; time_display_pressed = false; }}
                        onmousedown={() => time_display_pressed = true}
                        onmouseup={() => time_display_pressed = false}
                    >
                        {#if time_display_pressed && has_effective_time_changes()}
                            <span>{format_duration(calculate_time_saved())} saved</span>
                        {:else if time_display_hovered && has_effective_time_changes()}
                            <span>{format_duration(calculate_effective_current_time())}</span>
                            <span id="time-separator">/</span>
                            <span>{format_duration(calculate_effective_total_time())}</span>
                        {:else}
                            <span>{format_duration(current_time)}</span>
                            <span id="time-separator">/</span>
                            <span>{format_duration(duration)}</span>
                        {/if}
                    </div>
                </div>


                <div id="line-and-segments-bar-container">

                    {#if chapters && chapters.length > 0}

                        <div id="line-container">
                            <svg width="100%" height="100%">
                                <!-- Main horizontal line centered in the container -->
                                <!-- <line x1="0" y1="50%" x2="100%" y2="50%" stroke="var(--secondary-accent)" stroke-width="1"/> -->

                                <!-- Vertical chapter markers -->
                                {#each chapters as chapter}
                                    {@const zoom_window_size = zoom_window.end - zoom_window.start}
                                    {@const chapter_pos = (chapter.start_time / duration)}
                                    {@const chapter_pos_in_window = (chapter_pos - zoom_window.start) / zoom_window_size}

                                    <!-- Only show marker if it's visible within the zoom window -->
                                    {#if chapter_pos_in_window > 0 && chapter_pos_in_window < 1}
                                        {@const marker_x = chapter_pos_in_window * 100}
                                        <line
                                            x1="{marker_x}%"
                                            y1="0%"
                                            x2="{marker_x}%"
                                            y2="100%"
                                            stroke="#eddb61"
                                            stroke-width="1"
                                        />
                                    {/if}
                                {/each}
                            </svg>
                        </div>

                    {/if}

                    <div id="progress-bar-container">
                        <SegmentsBar
                            bind:this={segbar}
                            bind:zoom_window
                            {id}
                            {aspect_ratio}
                            {merged_segments}
                            {speaker_visibility}
                            {is_speaker_visible}
                            {speaker_color_sets}
                            bind:selected_colorset_num
                            {duration}
                            {chapters}
                            {storyboards_fetched}
                            {seconds_per_frame}
                            {source}
                            {available_timestamps}
                            bind:current_time
                            {seekTo}
                            on:interaction={on_segbar_interaction}
                            bind:dragging
                            bind:hovered_speaker
                            bind:hovered_time
                            {hovered_speaker_from_panel}
                        />
                        <!-- Separate time tracker marker that sits on top of the SegmentsBar -->
                        {#if segbar && get_progress_in_window() !== null}
                            <div
                                id="time-tracker-marker"
                                style="left: {get_progress_in_window()}%"
                            >
                                <div class="marker-line"></div>
                            </div>
                        {/if}
                    </div>

                </div>


                <div id="controls-right">

                    <!-- svelte-ignore a11y_consider_explicit_label -->
                    <button class="cs-btn" id="next-segment-btn" onclick={seekToNextVisibleSegment} oncontextmenu={(e) => {e.preventDefault(); seekToPreviousVisibleSegment();}}></button>

                    <button class="cs-btn" id="mute-btn" aria-label="{is_muted ? 'Unmute' : 'Mute'}" class:active={!is_muted} onclick={() => {
                        if (player) {
                            if (is_muted) {
                                player.unMute();
                                is_muted = false;
                            } else {
                                player.mute();
                                is_muted = true;
                            }
                        }
                    }}></button>
                    <!-- {#if media_type !== 'audio'}
                        <button class="cs-btn" id="fullscreen-btn"></button>
                    {/if} -->
                </div>
            </div>

        {/if}

    </div>
</main>

<style>
    .info-link {
        color: var(--text-3);
        cursor: pointer;
        user-select: none;
        padding-left: 2px;
    }

    .info-link.active {
        color: var(--accent);
    }

    .info-link:hover {
        filter: brightness(1.2);
    }
</style>