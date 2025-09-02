<svelte:head>
    <title>{title}</title>
</svelte:head>

<svelte:window bind:innerWidth={inner_width} bind:innerHeight={inner_height} />

<script>
    import { onMount, onDestroy } from "svelte";
    import { socket } from '$lib/socket.js';
    import { invalidateAll } from "$app/navigation";
    import { base } from "$app/paths";
    import MediaPlayer from "$lib/MediaPlayer/MediaPlayer.svelte";
    import MediaItem from "$lib/MediaItem/MediaItem.svelte";
    import Processing from "./Processing.svelte";
    import SpeakersPanel from "./SpeakersPanel.svelte"
    import ChaptersPanel from "./ChaptersPanel.svelte"
    import InfoPanel from "./InfoPanel.svelte"
    import HotReloadModal from "./HotReloadModal.svelte";
    import SimpleDialog from "$lib/SimpleDialog.svelte";
    import DialogStack from "$lib/DialogStack.svelte";
    import { set_speaker_visibility, set_speaker_speeds, set_colorset, set_auto_skip_disabled_speakers } from '$lib/api.js';
    import { browser } from '$app/environment';

    let inner_width = $state();
    let inner_height = $state();

    /*
    =========================================================
        Page I/O
    =========================================================
    */

    /** @type {import('./$types').PageProps} */
    let { data } = $props();

    let welcome_dialog_visible = $state(false);
    $effect(() => {
        // Show dialog if data.show_welcome_dialog is true (but don't hide it if data.show_welcome_dialog becomes false; only user can hide the welcome dialog)
        if (data.show_welcome_dialog) {
            welcome_dialog_visible = true;
        }
    });

    // Welcome dialog state
    const media_data = $derived(data.media_data);
    const id = $derived(media_data?.id);
    const title = $derived(media_data?.title ? media_data?.title : `https://www.youtube.com/watch?v=${media_data?.uri}`);
    let duration = $derived(media_data?.duration)
    let merged_segments = $derived(media_data?.merged_segments ? JSON.parse(media_data?.merged_segments) : null)
    let speaker_color_sets = $derived(media_data?.speaker_color_sets ? JSON.parse(media_data?.speaker_color_sets) : null)
    let original_colorset_num = media_data?.selected_colorset_num;
    let selected_colorset_num = $derived(media_data?.selected_colorset_num);
    let active_job_status = $derived(data.active_job_status);
    let status = $derived(media_data?.status);

    let colorset_update_timer;

    // Watch for changes to selected_colorset_num and debounce the original_colorset_num update
    $effect(() => {
        // Clear any existing timer
        if (colorset_update_timer) {
            clearTimeout(colorset_update_timer);
        }

        // Only set timer if selected_colorset_num is defined and different from original
        if (selected_colorset_num !== undefined && selected_colorset_num !== original_colorset_num) {
            colorset_update_timer = setTimeout(() => {
                original_colorset_num = selected_colorset_num;
                colorset_update_timer = null;
            }, 7000);
        }
    });

    // Clean up timer on component destroy
    onDestroy(() => {
        // Clear colorset timer
        if (colorset_update_timer) {
            clearTimeout(colorset_update_timer);
        }
    });

    /*
    =========================================================
        Speakers
    =========================================================
    */

    const speakers = $derived(merged_segments ? [...new Set(merged_segments.map(seg => seg.speaker))] : []);

    let skip_silences = $derived(media_data?.skip_silences ?? false);

    let auto_skip_disabled_speakers = $derived(media_data?.auto_skip_disabled_speakers);

    /*
    =========================================================
        Speakers Visibility
    =========================================================
    */

    // Use stored speaker visibility if it exists, otherwise default to all visible
    let speaker_visibility = $state({});
    $effect(() => {
        if (media_data?.speaker_visibility) speaker_visibility = { ...media_data?.speaker_visibility }
        else speaker_visibility = Object.fromEntries(speakers.map(speaker => [speaker, true]))
    });

    const is_speaker_visible = (speaker) => speaker_visibility[speaker] ?? true;

    // When speakers visibility changes
    $effect(() => {
        if (Object.keys(speaker_visibility).length > 0) {
            if (media_player)
                media_player.handle_speaker_visibility_change();

            // Save speaker visibility changes to database
            set_speaker_visibility(media_data?.id, speaker_visibility);
        }
    });

    /*
    =========================================================
        Speaker Speeds
    =========================================================
    */

    // Use stored speaker speeds if they exist, otherwise default to 1.0x for all speakers
    let speaker_speeds = $state({});
    $effect(() => {
        if (media_data?.speaker_speeds) speaker_speeds = { ...media_data?.speaker_speeds }
        else speaker_speeds = Object.fromEntries(speakers.map(speaker => [speaker, 1.0]));
    });

    const get_speaker_speed = (speaker) => speaker_speeds[speaker] ?? 1.0;

    // Save speaker speed changes to database
    $effect(() => {
        if (Object.keys(speaker_speeds).length > 0) {
            set_speaker_speeds(media_data?.id, speaker_speeds);
        }
    });

    /*
    =========================================================
        Media Player
    =========================================================
    */

    let media_player = $state();
    let media_player_container = $state();
    let media_player_width = $state(800);

    let current_time = $derived(media_data?.playback_position || 0);

    let hovered_speaker = $state(null);
    let hovered_speaker_from_panel = $state(null);

    let dragging = $state(false);

    /*
    =========================================================
        Speaker Key Functions (X, L, C keys)
    =========================================================
    */

    // State for temporary reset functionality (C key)
    let saved_speaker_visibility = $state(null);
    let is_temp_reset_active = $state(false);

    // Monitor for manual changes during temp reset
    $effect(() => {
        if (is_temp_reset_active && speaker_visibility && saved_speaker_visibility) {
            const speakers = [...new Set(merged_segments?.map(seg => seg.speaker) || [])];
            const all_visible = speakers.every(speaker => speaker_visibility[speaker]);

            if (!all_visible) {
                saved_speaker_visibility = null;
                is_temp_reset_active = false;
            }
        }
    });

    function get_visible_speaker_count() {
        return Object.values(speaker_visibility).filter(visible => visible).length;
    }

    function isolate_speaker(speakerName) {
        if (speaker_visibility && merged_segments) {
            const allSpeakers = [...new Set(merged_segments.map(seg => seg.speaker))];
            allSpeakers.forEach(speaker => {
                speaker_visibility[speaker] = speaker === speakerName;
            });
            speaker_visibility = { ...speaker_visibility }; // Force reactivity
        }
    }

    function toggleTempReset() {
        if (!speaker_visibility || !merged_segments) return;

        if (!is_temp_reset_active) {
            saved_speaker_visibility = { ...speaker_visibility };
            const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
            speakers.forEach(speaker => {
                speaker_visibility[speaker] = true;
            });
            speaker_visibility = { ...speaker_visibility }; // Force reactivity
            is_temp_reset_active = true;
        } else {
            if (saved_speaker_visibility) {
                Object.keys(saved_speaker_visibility).forEach(speaker => {
                    speaker_visibility[speaker] = saved_speaker_visibility[speaker];
                });
            }
            speaker_visibility = { ...speaker_visibility }; // Force reactivity
            saved_speaker_visibility = null;
            is_temp_reset_active = false;
        }
    }

    function toggleHoveredSpeaker() {
        // Only proceed if we have a hovered speaker and it's not false/null
        if (!hovered_speaker || hovered_speaker === false || !speaker_visibility) return;

        const isCurrentlyVisible = is_speaker_visible(hovered_speaker);

        if (isCurrentlyVisible) {
            // Speaker is visible, disable it (but only if it's not the last one)
            if (get_visible_speaker_count() <= 1) return;
            speaker_visibility[hovered_speaker] = false;
        } else {
            // Speaker is disabled, re-enable it
            speaker_visibility[hovered_speaker] = true;
        }

        speaker_visibility = { ...speaker_visibility }; // Force reactivity
    }

    function isolateHoveredSpeaker() {
        // Only proceed if we have a hovered speaker and it's not false/null
        if (!hovered_speaker || hovered_speaker === false || !speaker_visibility) return;

        // Use the same logic as the right-click on color square
        isolate_speaker(hovered_speaker);
    }

    $effect(() => {
        if (inner_width && inner_height && media_player_container && (panels_container || !panels_visible)) {
            const player_rect = media_player_container.getBoundingClientRect();
            const aspect_ratio = media_data?.aspect_ratio || 16/9;

            let total_used_height, available_height;
            const FUDGE = 0.73;

            if (panels_visible && panels_container) {
                const panels_rect = panels_container.getBoundingClientRect();
                total_used_height = player_rect.height + panels_rect.height + 15;
                available_height = FUDGE * (inner_height - total_used_height + player_rect.height);
            } else {
                // When panels are hidden, only account for player height
                available_height = FUDGE * (inner_height - player_rect.height + player_rect.height);
            }

            // Set initial width based on screen width breakpoint
            let desired_width = inner_width > (panels_visible ? 1250 : 1250*1.1) ? 1200 : 950;

            // Scale down if height constraint is violated
            const player_height = desired_width / aspect_ratio;
            if (player_height > available_height) {
                desired_width = available_height * aspect_ratio;
            }

            // Apply minimum width (different for portrait vs landscape)
            const is_portrait = aspect_ratio < 1;
            const min_width = is_portrait ? 400 : 850;

            // Increase size of player slightly if panels not active
            if (!panels_visible) desired_width *= 1.1;

            media_player_width = Math.max(desired_width, min_width);
        }
    });

    /*
    =========================================================
        Panels
    =========================================================
    */

    let panels_visible = $state(true);
    let panels_container = $state();
    let chapters_panel = $state();

    // Update chapter title truncation states when window size changes or when chapters panel is first mounted
    $effect(() => {
        if (chapters_panel) {
            // Small delay to ensure layout has updated
            setTimeout(() => {
                chapters_panel.updateTruncationStates();
            }, 0);
        }
    });

    // Also update truncation states when window size changes
    $effect(() => {
        if (chapters_panel && (inner_width || inner_height)) {
            // Small delay to ensure layout has updated
            setTimeout(() => {
                chapters_panel.updateTruncationStates();
            }, 0);
        }
    });

    /*
    =========================================================
        Hot Reload Segments Data (for debugging)
    =========================================================
    */

    let showHotReloadModal = $state(false);

    // Replace the hot reload functions with just this:
    function handleKeydown(event) {
        // Only trigger if not typing in an input/textarea
        if (['INPUT', 'TEXTAREA'].includes(event.target.tagName)) {
            return;
        }

        if (event.key === 'H' || event.key === 'h') {
            event.preventDefault();
            showHotReloadModal = true;
        }

        // Only handle 'C' key when it's not combined with Ctrl/Cmd (to allow Ctrl+C/Cmd+C for copy)
        if (event.code === 'KeyC' && !event.ctrlKey && !event.metaKey) {
            event.preventDefault();
            toggleTempReset();
        }

        if (event.code === 'KeyX') {
            event.preventDefault();
            toggleHoveredSpeaker();
        }

        if (event.code === 'KeyO') {
            event.preventDefault();
            isolateHoveredSpeaker();
        }
    }

    function handleHotReloadSubmit(event) {
        const newSegmentsData = event.detail;

        if (media_data) {
            // Extract both merged_segments and speaker_color_sets from newSegmentsData
            if (newSegmentsData.merged_segments) {
                media_data.merged_segments = JSON.stringify(newSegmentsData.merged_segments);
            }

            if (newSegmentsData.speaker_color_sets) {
                media_data.speaker_color_sets = JSON.stringify(newSegmentsData.speaker_color_sets);
            }

            // Force reactivity update
            data = { ...data, media_data: { ...media_data } };
        }

        console.log('Hot reloaded data:', {
            merged_segments: newSegmentsData.merged_segments,
            speaker_color_sets: newSegmentsData.speaker_color_sets
        });
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

    /*
    =========================================================
        Websocket comms w/ backend
    =========================================================
    */

    // Sometimes new_job_started fires in between page load, so refresh
    if (status !== 'success') {
        setTimeout(() => { invalidateAll() }, 0);
    }

    onMount(() => {
        socket.connect();
        socket.on('connect', () => {
            console.log('ws connected');
        });
        socket.on('new_job_started', async () => {
            invalidateAll();
            console.log('new_job_started');
        });
        socket.on('progress_update', (socket_data) => {
            active_job_status = socket_data;
        });
        socket.on('job_done', async () => {
            invalidateAll();
            sessionStorage.setItem('reset-filters', 'true');
            sessionStorage.setItem('vault-scroll', '0');
        });
        socket.on('metadata_refresh', async () => {
            invalidateAll();
            console.log('metadata_refresh')
        });;
    });

    onDestroy(() => {
        socket.off('connect');
        socket.off('new_job_started');
        socket.off('progress_update');
        socket.off('job_done');
        socket.off('metadata_refresh');
        if (socket.connected) socket.disconnect();
    });

</script>


<main>

    <!--
    =========================================================
        media_data fetching error
    =========================================================
    -->

    {#if data.error}
        <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; pointer-events: none;">
            <div style="pointer-events: auto; text-align: center;">
                <h1 style="font-size: 72px; margin: 0; color: var(--text-3);">{data.status}</h1>
                <p style="font-size: 20px; color: var(--text);">{data.error}</p>
            </div>
        </div>
    {:else}

        <!--
        =========================================================
            Processing
        =========================================================
        -->

        {#if media_data?.status === 'queued' || media_data?.status === 'processing'}

            <div class="processing-container">
                <Processing
                    item_data={media_data}
                    active_job_status={active_job_status ? (media_data?.id === active_job_status.id ? active_job_status : null) : null}
                    processor_status={data.processor_status}
                />
            </div>

        <!--
        =========================================================
            Processing failed
        =========================================================
        -->

        {:else if media_data?.status === "failed"}

            <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; pointer-events: none;">
                <div style="pointer-events: auto; text-align: center;">
                    <p>Processing failed!</p>
                    <p style="max-width: 800px; padding: 0 20px; text-align: center;">
                        {#if media_data?.error.type === 'bot'}
                            YouTube bot detection trigerred <a href="/settings?highlight=cookies_from_browser" style="color: var(--accent)">[Fix]</a>
                        {:else if media_data?.error.type === 'age_restricted'}
                            Age restricted video <a href="/settings?highlight=cookies_from_browser" style="color: var(--accent)">[Fix]</a>
                        {:else if media_data?.error.type === 'interrupted'}
                            Zanshin was shut down during processing
                        {:else}
                            {media_data?.error.full_str}<br><br>
                            {#if !media_data?.error.full_str?.includes('No speakers in audio') && media_data?.source !== 'local'}
                                If the above error is a download error, try restarting Zanshin, so that the YouTube downloader can update (if an update exists)
                            {/if}
                        {/if}
                    </p>
                </div>
            </div>

        <!--
        =========================================================
            Processing succeeded
        =========================================================
        -->

        {:else if media_data?.status === "success"}

            <!-- Top level -->
            <div class="toplevel-container" style="padding-top: {media_data?.media_type === 'video' ? '9px' : '15vh'}">

                <!-- Media player -->
                <div class="media-player-container" style="width: {media_player_width}px" bind:this={media_player_container}>
                    <MediaPlayer
                        id={media_data?.id}
                        source={media_data?.source}
                        media_type={media_data?.media_type}
                        uri={media_data?.uri}
                        video_title={media_data?.title}
                        chapters={media_data?.chapters}
                        embeddable={media_data?.embeddable}
                        video_stream_url={media_data?.video_stream_url}
                        bind:duration
                        {merged_segments}
                        {speaker_visibility}
                        {is_speaker_visible}
                        {get_speaker_speed}
                        {speaker_color_sets}
                        bind:selected_colorset_num
                        aspect_ratio={media_data?.aspect_ratio || 16/9}
                        storyboards_fetched={media_data?.storyboards_fetched}
                        seconds_per_frame={media_data?.seconds_per_frame}
                        available_timestamps={media_data?.available_timestamps}
                        saved_zoom_window={media_data?.zoom_window}
                        bind:panels_visible
                        bind:this={media_player}
                        bind:current_time
                        bind:skip_silences
                        bind:auto_skip_disabled_speakers
                        bind:hovered_speaker
                        bind:hovered_speaker_from_panel
                        bind:dragging
                    />
                </div>

                {#if panels_visible}
                    <div class="panels-container" style="width: {media_player_width}px" bind:this={panels_container}>
                        <!-- Info panel -->
                        <div class="info-panel">
                            <InfoPanel
                                media_data={media_data}
                                bind:dragging
                            />
                        </div>

                        <!-- Speakers panel -->
                        {#if merged_segments}
                        <div class="speakers-panel">
                            <SpeakersPanel
                                {id}
                                {merged_segments}
                                {speaker_color_sets}
                                bind:selected_colorset_num
                                {duration}
                                bind:speaker_visibility
                                bind:speaker_speeds
                                {is_speaker_visible}
                                switch_colorset_func={async () => {
                                    selected_colorset_num = (selected_colorset_num + 1) % 10;  // Increment and wrap around
                                    await set_colorset(id, selected_colorset_num); // Persist to database
                                }}
                                reset_colorset_func={async () => {
                                    selected_colorset_num = original_colorset_num;
                                    await set_colorset(id, selected_colorset_num);
                                }}
                                bind:skip_silences
                                bind:auto_skip_disabled_speakers
                                on:seek_to_next_speaker_segment={(e) => media_player.seekToNextSpeakerSegment(e.detail)}
                                on:auto_skip_setting_applied={() => media_player.handle_speaker_visibility_change()}
                                chapters_exist={media_data?.chapters?.length > 0}
                                {current_time}
                                bind:hovered_speaker
                                bind:hovered_speaker_from_panel
                                {dragging}
                            />
                        </div>
                        {/if}

                        <!-- Chapters panel -->
                        {#if media_data?.chapters?.length > 0}
                            <div class="chapters-panel">
                                <ChaptersPanel
                                    chapters={media_data?.chapters}
                                    padding_right={'40px'}
                                    {current_time}
                                    {merged_segments}
                                    {is_speaker_visible}
                                    bind:this={chapters_panel}
                                    on:chapter_seek={(e) => media_player.seekTo(e.detail, true)}
                                    bind:dragging
                                />
                            </div>
                        {/if}
                    </div>
                {/if}

            </div>

        {:else}

            <p>¯\_(ツ)_/¯</p>

        {/if}
    {/if}

    <!-- Hot Reload Modal -->
    <HotReloadModal
        bind:show={showHotReloadModal}
        initialData={{
            merged_segments: merged_segments,
            speaker_color_sets: speaker_color_sets
        }}
        on:submit={handleHotReloadSubmit}
    />

    <!-- Welcome Dialog -->
    <DialogStack bind:visible={welcome_dialog_visible}>
        <SimpleDialog
            bind:visible={welcome_dialog_visible}
            title="Welcome to Zanshin"
            text={`Zoom into the colored segments bar and slide or drag it side to side.
Left click a segment to seek to the beginning of it, right click to seek to exact position.
Also explore the various panels underneath the player.
See Settings -> Mouse & Keyboard Shortcuts for more controls as well.
<a href="https://www.youtube.com/embed/cAwsP4ee65M?autoplay=1" target="_blank" style="color: inherit; text-decoration: none; cursor: pointer;">Cheers</a>.`}
        />
    </DialogStack>

</main>

<style>

    .processing-container {
        display: flex;
        flex-direction: row;
        justify-content: center;
        padding-top: 35px;
    }

    .toplevel-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 15px;
        padding-bottom: 25px;
    }

    /* .media-player-container {
        width: var(--test-width);
    } */

    .panels-container {
        display: flex;
        flex-direction: row;
        gap: 15px;
        /* width: var(--test-width); */
    }

    .info-panel {
        flex: 0 0 auto; /* Don't grow or shrink, use natural width */
        max-width: 33%;
    }

    .speakers-panel {
        flex: 0 0 auto; /* Don't grow or shrink, use natural width */
    }

    .chapters-panel {
        flex: 0 1 auto; /* Natural size, but cap width to not extend past container width */
        min-width: 0;
    }

</style>