<script>
    import { onMount, onDestroy } from 'svelte';
    import { invalidateAll } from '$app/navigation';
    import { format_duration } from '$lib/misc';
    import { createEventDispatcher } from 'svelte';
    import { browser } from '$app/environment';

    let {
        merged_segments = [],
        aspect_ratio = 16/9,
        speaker_color_sets,
        selected_colorset_num = $bindable(),
        zoom_window = $bindable(),
        duration,
        chapters = [],
        id,
        storyboards_fetched,
        seconds_per_frame,
        source,
        available_timestamps,
        speaker_visibility = {},
        is_speaker_visible,
        current_time = $bindable(),
        seekTo,
        dragging = $bindable(),
        hovered_speaker = $bindable(),
        hovered_time = $bindable(),
        hovered_speaker_from_panel = null
    } = $props();

    const dispatch = createEventDispatcher();

    const should_fade_in = !duration;

    /*
        =========================================================
            Keyboard Shortcuts
        =========================================================
        */

        let keys = $state({}); // Track key states
        let last_frame = $state(0);
        const TARGET_FRAME_TIME = 16.67; // ms, assumes 60fps as baseline
        const KEY_ZOOM_SENSITIVITY = 0.025*1.5; // Per frame at 60fps
        const KEY_PAN_SENSITIVITY = 0.01*1.5; // Per frame at 60fps

        function handle_keydown(event) {
            // Skip if in input field or textarea
            if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                return;
            }

            // Prevent default for our shortcut keys
            if (['KeyW', 'KeyS', 'KeyA', 'KeyD'].includes(event.code)) {
                event.preventDefault();
                keys[event.code] = true;
                start_interaction();
            }
        }

        function handle_keyup(event) {
            keys[event.code] = false;
        }

        function zoom_action(delta_y) {
            if (!duration) return;

            const zoom_window_size = zoom_window.end - zoom_window.start;
            const zoom_factor = 1 + delta_y;

            let new_window_size = zoom_window_size * zoom_factor;
            new_window_size = Math.max(MIN_ZOOM_WINDOW_WIDTH, Math.min(new_window_size, MAX_ZOOM_WINDOW_WIDTH));

            let zoom_center;

            if (hovering) {
                // Use mouse position as focal point when hovering
                zoom_center = zoom_window.start + mouse_ratio * zoom_window_size;
            } else {
                // Fallback to previous logic when not hovering
                const current_position = current_time / duration;
                const is_current_time_in_window = current_position >= zoom_window.start && current_position <= zoom_window.end;

                if (is_current_time_in_window) {
                    // Zoom around current time if within window
                    zoom_center = current_position;
                } else {
                    // Zoom around the middle of the current zoom window
                    zoom_center = zoom_window.start + zoom_window_size / 2;
                }
            }

            let new_start = zoom_center - (zoom_center - zoom_window.start) * zoom_factor;
            let new_end = zoom_center + (zoom_window.end - zoom_center) * zoom_factor;

            if (new_start < 0) {
                new_start = 0;
                new_end = new_window_size;
            } else if (new_end > 1) {
                new_end = 1;
                new_start = 1 - new_window_size;
            }

            zoom_window = { start: new_start, end: new_end };
        }

        function pan_action(pan_factor) {
            if (!duration) return;

            // Scale pan factor by zoom window size to maintain consistent visual speed
            const zoom_window_size = zoom_window.end - zoom_window.start;
            const scaled_pan_factor = pan_factor * zoom_window_size;

            let new_start = zoom_window.start + scaled_pan_factor;
            let new_end = zoom_window.end + scaled_pan_factor;

            if (new_start < 0) {
                new_end += -new_start;
                new_start = 0;
            } else if (new_end > 1) {
                new_start -= (new_end - 1);
                new_end = 1;
            }

            zoom_window = { start: new_start, end: new_end };
        }

        function segbar_keyboard_loop(timestamp) {
            if (last_frame === 0) {
                last_frame = timestamp;
            }

            const delta_time = timestamp - last_frame;
            const delta_factor = delta_time / TARGET_FRAME_TIME; // Scale relative to 60fps

            if (keys['KeyW']) {
                zoom_action(-KEY_ZOOM_SENSITIVITY * delta_factor); // Zoom in
            }
            if (keys['KeyS']) {
                zooming_out = true;
                zoom_action(KEY_ZOOM_SENSITIVITY * delta_factor); // Zoom out
            }
            if (keys['KeyA']) {
                panning = true;
                pan_action(-KEY_PAN_SENSITIVITY * delta_factor); // Pan left
            }
            if (keys['KeyD']) {
                panning = true;
                pan_action(KEY_PAN_SENSITIVITY * delta_factor); // Pan right
            }

            last_frame = timestamp;
            raf_id = requestAnimationFrame(segbar_keyboard_loop);
        }

        let raf_id = null;

        onMount(() => {
            if (browser) {
                document.addEventListener('keydown', handle_keydown);
                document.addEventListener('keyup', handle_keyup);
                raf_id = requestAnimationFrame(segbar_keyboard_loop);
            }
        });

        onDestroy(() => {
            if (browser) {
                document.removeEventListener('mousemove', handle_document_mouse_move);
                document.removeEventListener('mouseup', handle_document_mouse_up);
                document.removeEventListener('keydown', handle_keydown);
                document.removeEventListener('keyup', handle_keyup);
                if (interaction_timeout) {
                    clearTimeout(interaction_timeout);
                }
                if (raf_id) {
                    cancelAnimationFrame(raf_id);
                }
            }
        });

    /*
    =========================================================
        Color Map
    =========================================================
    */

    let speaker_color_set = $derived(speaker_color_sets[selected_colorset_num]);

    function get_speaker_color(speaker) {
        return speaker_color_set[speaker] || '#777777'; // Fallback gray
    }

    /*
    =========================================================
        Thumbnail Preview
    =========================================================
    */

    const THUMBNAIL_MAX_WIDTH = 160;
    const THUMBNAIL_MAX_HEIGHT = 120;

    let thumbnail_width = $derived(
        aspect_ratio && THUMBNAIL_MAX_WIDTH / aspect_ratio <= THUMBNAIL_MAX_HEIGHT
            ? THUMBNAIL_MAX_WIDTH
            : THUMBNAIL_MAX_HEIGHT * aspect_ratio
    );

    let thumbnail_height = $derived(thumbnail_width / aspect_ratio);

    let hovering = $state(false);
    let thumbnail_timestamp = $state(0);
    let current_chapter = $state(null); // Store the current chapter
    let thumbnail_x_percent = $state(50); // Position as percentage of container width
    let mouse_ratio = $state(0); // Store the mouse position ratio

    function round_down_to_nearest_frame_interval(number) {
        if (!seconds_per_frame) return 0;
        return Math.floor(number / seconds_per_frame) * seconds_per_frame;
    }

    // updates thumbnail when zoom window changes
    $effect(() => {
        if (hovering && duration) {
            const zoomedPosition = zoom_window.start + mouse_ratio * (zoom_window.end - zoom_window.start);
            const hoveredTime = zoomedPosition * duration;
            hovered_time = hoveredTime;

            // Use different logic for local vs YouTube videos
            if (source === 'local' && available_timestamps) {
                thumbnail_timestamp = find_closest_available_timestamp(hoveredTime);
            } else {
                thumbnail_timestamp = round_down_to_nearest_frame_interval(hoveredTime);
            }

            // Find current chapter
            if (chapters && chapters.length > 0) {
                current_chapter = chapters.find(chapter =>
                    hovered_time >= chapter.start_time && hovered_time < chapter.end_time
                ) || null;
            } else {
                current_chapter = null;
            }
        }
    });

    let follow_mouse_cursor = $state(true); // true = follow cursor, false = fixed height above bar

    let thumbnail_x = $state(0);  // Global viewport coordinates (cursor mode)
    let thumbnail_y = $state(0);  // Global viewport coordinates (cursor mode)
    let thumbnail_y_px = $state(-165); // Fixed offset above bar (fixed mode)

    export function toggle_thumbnail_mode() {
        follow_mouse_cursor = !follow_mouse_cursor;
    }

    function find_closest_available_timestamp(time) {
        if (!available_timestamps || available_timestamps.length === 0) return 0;

        // Find the closest previous (or equal) timestamp
        let closest = available_timestamps[0];

        for (let timestamp of available_timestamps) {
            // Only consider timestamps that are <= the current time
            if (timestamp <= time && timestamp > closest) {
                closest = timestamp;
            }
        }

        return closest;
    }

    function handle_mouse_move(event) {
        const rect = event.currentTarget.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        mouse_ratio = mouseX / rect.width;

        const zoomedPosition = zoom_window.start + mouse_ratio * (zoom_window.end - zoom_window.start);
        const hoveredTime = zoomedPosition * duration;

        hovered_time = hoveredTime;

        if (source === 'local' && available_timestamps) {
            thumbnail_timestamp = find_closest_available_timestamp(hoveredTime);
        } else {
            thumbnail_timestamp = round_down_to_nearest_frame_interval(hoveredTime);
        }

        if (follow_mouse_cursor) {
            // Cursor following mode
            thumbnail_x = event.clientX;
            thumbnail_y = event.clientY;
        } else {
            // Fixed height mode
            thumbnail_x_percent = mouse_ratio * 100;
            thumbnail_y_px = -165; // Fixed height above the bar
        }

        hovering = true;

        // Find current chapter
        if (chapters && chapters.length > 0) {
            current_chapter = chapters.find(chapter =>
                hovered_time >= chapter.start_time && hovered_time < chapter.end_time
            ) || null;
        } else {
            current_chapter = null;
        }
    }

    function handle_mouse_leave() {
        hovering = false;
    }

    $effect(() => {
        // whenever hovering changes, this effect should run
        // if hovering is true, using hovered_time, find the speaker at that position (if any); set hovered_speaker to that speaker's name
        // if hovering is false, set hovered_speaker to null

        if (hovering) {
            // Find the segment that contains the hovered_time
            const current_segment = merged_segments.find(segment =>
                hovered_time >= segment.start && hovered_time < segment.end
            );

            // Set hovered_speaker to the speaker name if found, otherwise null
            hovered_speaker = current_segment ? current_segment.speaker : false;
        } else {
            hovered_speaker = null;
        }
    });

    /*
    =========================================================
        Wheel / Scroll
    =========================================================
    */

    const DIRECTION_LOCK_TIMEOUT = 40;

    let scroll_direction = null;  // {'horizontal', 'vertical', null}
    let last_scroll_time = 0;

    /*
    =========================================================
        Zoom
    =========================================================
    */

    const ZOOM_SENSITIVITY = 0.003;
    const MIN_ZOOM_WINDOW_WIDTH = 0.05;
    const MAX_ZOOM_WINDOW_WIDTH = 1;

    /*
    =========================================================
        Horizontal Scroll
    =========================================================
    */

    const HORIZONTAL_SCROLL_SENSITIVITY = 0.00125;

    /*
    =========================================================
        Horizontal Drag
    =========================================================
    */

    let drag_just_ended = false;
    let drag_recently_ended = $state(false);
    let drag_start_x = 0;
    let drag_start_window = { start: 0, end: 0 };

    function handle_document_mouse_move(event) {
        if (browser) {
            const dx = event.clientX - drag_start_x;

            if (Math.abs(dx) > 0) {

                dragging = true;

                start_interaction();

                // Get container element
                const container = document.getElementById('container');
                if (!container) return;

                const rect = container.getBoundingClientRect();
                const dx_percent = dx / rect.width;
                const window_size = drag_start_window.end - drag_start_window.start;

                // Calculate new window position based on original window
                let new_start = drag_start_window.start - dx_percent * window_size;
                let new_end = drag_start_window.end - dx_percent * window_size;

                // Boundary checks
                if (new_start < 0) {
                    new_end -= new_start;
                    new_start = 0;
                }

                if (new_end > 1) {
                    new_start -= (new_end - 1);
                    new_end = 1;
                }

                zoom_window = { start: new_start, end: new_end };

            }
        }
    }

    function handle_document_mouse_up() {
        if (browser) {
            if (dragging) {
                dragging = false;
                drag_just_ended = true;
                drag_recently_ended = true;
                setTimeout(() => { drag_just_ended = false }, 100);
                setTimeout(() => { drag_recently_ended = false }, 450);

                // Clear any text selection that might have occurred
                if (window.getSelection) {
                    window.getSelection().removeAllRanges();
                }
            }
            if (typeof document !== 'undefined') {
                // Re-enable text selection
                document.body.style.userSelect = '';
                document.body.style.webkitUserSelect = '';

                document.removeEventListener('mousemove', handle_document_mouse_move);
                document.removeEventListener('mouseup', handle_document_mouse_up);
            }
        }
    }

    onDestroy(() => {
        if (browser) {
            if (typeof document !== 'undefined') {
                // Ensure text selection is re-enabled on cleanup
                document.body.style.userSelect = '';
                document.body.style.webkitUserSelect = '';

                document.removeEventListener('mousemove', handle_document_mouse_move);
                document.removeEventListener('mouseup', handle_document_mouse_up);
            }
            if (interaction_timeout) {
                clearTimeout(interaction_timeout);
            }
        }
    });

    /*
    =========================================================
        Navigation
    =========================================================
    */

    let is_interacting = $state(false);
    let interaction_timeout = null;
    let panning = $state(false);
    let zooming_out = $state(false);

    function start_interaction() {
        is_interacting = true;

        // Dispatch interaction event to parent
        dispatch('interaction');

        // Clear existing timeout
        if (interaction_timeout) {
            clearTimeout(interaction_timeout);
        }

        // Set new timeout to end interaction after 450ms of inactivity
        interaction_timeout = setTimeout(() => {
            is_interacting = false;
            panning = false;
            zooming_out = false;
        }, 450);
    }

</script>

<main>
    {#if !duration}
        <div class="loading-container">
            <div class="loading-bar"></div>
        </div>
    {:else}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div id="container"
            class:fade-in={should_fade_in}

            onmousemove={handle_mouse_move}
            onmouseleave={handle_mouse_leave}

            onwheel={(event) => {
                event.preventDefault();

                start_interaction();

                let delta_x = event.deltaX;
                let delta_y = event.deltaY;
                const abs_x = Math.abs(delta_x);
                const abs_y = Math.abs(delta_y);

                // Reject horizontal scroll if no zoom
                if (zoom_window.start === 0 && zoom_window.end === 1) {
                    delta_x = 0;
                }

                const now = performance.now();
                const time_since_last_scroll = now - last_scroll_time;

                // Reset the lock if enough time has passed without scrolling
                if (time_since_last_scroll > DIRECTION_LOCK_TIMEOUT) {
                    scroll_direction = null;
                }

                // No direction locked; determine based on magnitude
                if (scroll_direction === null) {
                    scroll_direction = (abs_x > abs_y) ? 'horizontal' : 'vertical';
                }

                if (scroll_direction === 'horizontal') {
                    panning = true;

                    // Scale pan factor by zoom window size to maintain consistent visual speed
                    const zoom_window_size = zoom_window.end - zoom_window.start;
                    const scaled_pan_factor = delta_x * HORIZONTAL_SCROLL_SENSITIVITY * zoom_window_size;

                    let new_start = zoom_window.start + scaled_pan_factor;
                    let new_end = zoom_window.end + scaled_pan_factor;

                    if (new_start < 0) {
                        new_end += -new_start;
                        new_start = 0;
                    } else if (new_end > 1) {
                        new_start -= (new_end - 1);
                        new_end = 1;
                    }

                    zoom_window = { start: new_start, end: new_end };
                }

                if (scroll_direction === 'vertical') {
                    zooming_out = delta_y > 0; // Only set to true when zooming out

                    const rect = event.currentTarget.getBoundingClientRect();
                    const x_percent = (event.clientX - rect.left) / rect.width;
                    const zoom_factor = 1 + (delta_y * ZOOM_SENSITIVITY);

                    let new_window_size = (zoom_window.end - zoom_window.start) * zoom_factor;
                    new_window_size = Math.max(MIN_ZOOM_WINDOW_WIDTH, Math.min(new_window_size, MAX_ZOOM_WINDOW_WIDTH));

                    const current_size = zoom_window.end - zoom_window.start;
                    const zoom_center = zoom_window.start + current_size * x_percent;

                    let new_start = zoom_center - (zoom_center - zoom_window.start) * zoom_factor;
                    let new_end = zoom_center + (zoom_window.end - zoom_center) * zoom_factor;

                    if (new_start < 0) {
                        new_start = 0;
                        new_end = new_window_size;
                    } else if (new_end > 1) {
                        new_end = 1;
                        new_start = 1 - new_window_size;
                    }

                    zoom_window = { start: new_start, end: new_end };

                }

                last_scroll_time = now;
            }}

            onmousedown={(event) => {
                if (browser) {
                    if (event.button !== 0) {
                        // Do nothing if not left click
                        return;
                    }

                    // Prevent text selection during drag
                    event.preventDefault();

                    drag_start_x = event.clientX;
                    drag_start_window = { ...zoom_window };

                    if (typeof document !== 'undefined') {
                        // Disable text selection on document
                        document.body.style.userSelect = 'none';
                        document.body.style.webkitUserSelect = 'none';

                        document.addEventListener('mousemove', handle_document_mouse_move);
                        document.addEventListener('mouseup', handle_document_mouse_up);
                    }
                }
            }}

            onclick={(event) => {

                if (drag_just_ended) return;

                const rect = event.currentTarget.getBoundingClientRect();
                const clickX = event.clientX - rect.left;
                const clickRatio = clickX / rect.width;
                const zoomedPosition = zoom_window.start + clickRatio * (zoom_window.end - zoom_window.start);
                const newTime = zoomedPosition * duration;

                const clickedSegment = merged_segments.find(segment =>
                    newTime >= segment.start && newTime < segment.end
                );

                if (clickedSegment && is_speaker_visible(clickedSegment.speaker)) {
                    seekTo(clickedSegment.start);
                }
            }}

            oncontextmenu={(event) => {
                event.preventDefault();
                const rect = event.currentTarget.getBoundingClientRect();
                const clickX = event.clientX - rect.left;
                const clickRatio = clickX / rect.width;
                const zoomedPosition = zoom_window.start + clickRatio * (zoom_window.end - zoom_window.start);
                const newTime = zoomedPosition * duration;

                // For right-click, seek to exact position
                seekTo(newTime);
            }}

        >
            <svg>
                {#each merged_segments as segment}
                    <!-- Only show segment if speaker is visible -->
                    {#if is_speaker_visible(segment.speaker)}
                        {@const zoom_window_size = zoom_window.end - zoom_window.start}

                        {@const seg_start = (segment.start/duration)}
                        {@const seg_end = (segment.end/duration)}

                        {@const seg_start_in_window = (seg_start - zoom_window.start) / zoom_window_size}
                        {@const seg_end_in_window = (seg_end - zoom_window.start) / zoom_window_size}

                        <!-- Calculate opacity based on hover state -->
                        {@const should_fade = hovered_speaker_from_panel && hovered_speaker_from_panel !== segment.speaker}
                        {@const segment_opacity = should_fade ? 0 : 1.0}

                        <!-- If segment is visible within zoom window -->
                        {#if seg_start_in_window < 1 && seg_end_in_window > 0}

                            <!-- clipping -->
                            {@const x_start = Math.max(0, seg_start_in_window) * 100}
                            {@const x_end = Math.min(1, seg_end_in_window) * 100}
                            {@const seg_width = x_end - x_start}

                            <rect
                                x="{x_start}%"
                                y="0"
                                width="{seg_width}%"
                                height="100%"
                                fill={get_speaker_color(segment.speaker)}
                                opacity={segment_opacity}
                                style="transition: opacity 0.2s ease-in-out;"
                            />

                        {/if}
                    {/if}
                {/each}
            </svg>
        </div>
    {/if}

    <!-- To prevent showing thumbnail preview for negative times -->
    {#if hovered_time >= 0}

        <!-- Thumbnail Preview -->
        <div
            class="thumbnail-container"
            class:cursor-mode={follow_mouse_cursor}
            class:fixed-mode={!follow_mouse_cursor}
            class:no-storyboard={!storyboards_fetched}
            class:visible={hovering && !(panning || dragging || drag_recently_ended) && !zooming_out}
            style={follow_mouse_cursor ? `left: ${thumbnail_x}px; top: ${thumbnail_y}px;` : `left: ${thumbnail_x_percent}%; top: ${thumbnail_y_px}px;`
            }
        >
            {#if storyboards_fetched}

                <div class="thumbnail-preview">
                    <div class="thumbnail-image-container">
                        <img
                            src="/api/frame/{id}/{thumbnail_timestamp}"
                            alt="Frame preview"
                            loading="lazy"
                            style="width: {thumbnail_width}px; height: {thumbnail_height}px;"
                        />
                        <div class="thumbnail-time">
                            {format_duration(hovered_time)}
                        </div>
                    </div>
                </div>

                {#if current_chapter}
                    <div class="thumbnail-chapter">
                        {current_chapter.title}
                    </div>
                {/if}

            {:else}

                {#if current_chapter}
                    <div class="thumbnail-chapter">
                        {current_chapter.title}
                    </div>
                {/if}

                <!-- Time marker when no storyboard available -->
                <div class="time-marker">
                    {format_duration(hovered_time)}
                </div>

            {/if}

        </div>

    {/if}

</main>

<style>
    svg {
        width: 100%;
        height: 100%;
        position: absolute;
        pointer-events: none;
    }

    #container {
        position: absolute;
        width: 100%;
        height: 100%;
        cursor: pointer;
        background-color: #595959;
    }

    .loading-container {
        position: absolute;
        width: 100%;
        height: 100%;
        background-color: #333;
        overflow: hidden;
    }

    .loading-bar {
        height: 100%;
        width: 30%;
        background-color: #555;
        position: absolute;
        animation: loading-pulse 1.5s infinite ease-in-out;
    }

    @keyframes loading-pulse {
        0% { left: -30%; }
        100% { left: 100%; }
    }

    .fade-in {
        animation: fadeIn 0.4s ease-in-out;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .thumbnail-container {
        z-index: 101;
        pointer-events: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;

        opacity: 0;
        transition: opacity 0.15s ease-in-out;
    }

    .thumbnail-container.visible {
        opacity: 1;
    }

    .thumbnail-container.cursor-mode {
        position: fixed;
        transform: translate(-50%, -100%);
        margin-top: -31px;
    }

    .thumbnail-container.fixed-mode {
        position: absolute;
        transform: translateX(-50%);
        margin-top: 17px;
    }

    .thumbnail-container.cursor-mode.no-storyboard {
        margin-top: -13px;
    }

    .thumbnail-container.fixed-mode.no-storyboard {
        margin-top: 5px;
    }

    .thumbnail-preview {
        background-color: var(--bg);
        border: 1px solid;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        padding: 3px;
        box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.4);
        user-select: none;
    }

    .thumbnail-image-container {
        position: relative; /* This is where the time badge will be positioned relative to */
        border: 1px solid;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
    }

    .thumbnail-preview img {
        display: block;
        object-fit: cover;
    }

    .thumbnail-time {
        position: absolute;
        bottom: 0px;
        right: 0px;
        background-color: rgba(0, 0, 0, 0.8);
        color: var(--text);
        font-size: 12px;
        padding: 2px 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }

    .thumbnail-chapter {
        background-color: var(--bg);
        border: 1px solid;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        padding: 1px 3px 0px 3px;
        margin-bottom: -1px;
        font-size: 13px;
        color: var(--accent);
        font-weight: 400;
        text-align: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 15px;
        max-width: 400px;
        box-sizing: border-box;
        user-select: none;
    }

    .time-marker {
        background-color: var(--bg);
        border: 1px solid;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        padding: 0px 3px 0px 3px;
        font-size: 12px;
        color: var(--accent);
        font-weight: 400;
        text-align: center;
        white-space: nowrap;
        line-height: 15px;
        box-sizing: border-box;
        user-select: none;
        font-variant-numeric: tabular-nums;
    }
</style>