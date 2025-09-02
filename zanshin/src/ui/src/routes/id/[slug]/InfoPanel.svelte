<script>

    import Panel from './Panel.svelte';
    import { format_timestamp, format_youtube_date } from '$lib/misc.js';
    import { delete_media_item } from '$lib/api.js';
    import { goto, invalidateAll } from '$app/navigation';
    import { socket } from '$lib/socket.js';
    import { onMount, onDestroy, tick } from 'svelte';

    /*
    =========================================================
        I/O
    =========================================================
    */

    const { media_data, padding_right = null, margin_right = null, dragging = $bindable() } = $props();

    /*
    =========================================================
        State
    =========================================================
    */

    let delete_confirmation = $state(false);

    /*
    =========================================================
        Helper Functions
    =========================================================
    */

    function was_click_in_empty_area(event) {
        let target = event.target;
        let isDeleteButton = false;
        while (target !== event.currentTarget) {
            if (target.classList && (target.classList.contains('cs-btn') && target.classList.contains('delete-btn'))) {
                isDeleteButton = true;
                break;
            }
            target = target.parentElement;
        }
        return !isDeleteButton;
    }

    // Format date display based on source
    function getDateDisplay() {
        if (media_data.source === 'youtube' && media_data.date_uploaded) {
            return format_youtube_date(media_data.date_uploaded);
        } else if (media_data.source === 'local' && media_data.creation_timestamp) {
            return format_youtube_date(new Date(media_data.creation_timestamp * 1000).toISOString().slice(0, 10).replace(/-/g, ''));
        }
        return 'Unknown';
    }

    // Get uploader/source info
    function getUploaderDisplay() {
        if (media_data.source === 'youtube' && media_data.channel) {
            return media_data.channel;
        }
        return null;
    }

    // Get "added" time ago
    function getAddedTimeDisplay() {
        if (media_data.submitted_t) {
            return format_timestamp(media_data.submitted_t);
        }
        return 'Unknown';
    }

    onMount(() => {
        socket.connect();
        socket.on('connect', () => {
            console.log('ws connected');
        });
        socket.on('delete_complete', (deleted_ids) => {
            if (deleted_ids.includes(media_data?.id)) {
                goto('/vault');
            }
        });
    });

    onDestroy(() => {
        socket.off('connect');
        socket.off('delete_complete');
        if (socket.connected) socket.disconnect();
    });

</script>

<main>

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div onmouseleave={() => { delete_confirmation = false }}
         onclick={(e) => { if (was_click_in_empty_area(e)) delete_confirmation = false }}>

        <Panel header_text={'Info'} {padding_right} {margin_right}>
            <div style="display: flex; flex-direction: column; gap: 8px; {dragging ? `user-select: none;`: ``}">

                <!-- Info Items -->
                <div style="display: flex; flex-direction: column; ">

                    <!-- Uploader (YouTube only) -->
                    {#if getUploaderDisplay()}
                        <a href="https://www.youtube.com/channel/{media_data.channel_id}"
                           target="_blank"
                           rel="noopener noreferrer"
                           style="color: var(--text-3); margin: 0; font-size: 0.9em; text-decoration: none;">
                            {getUploaderDisplay()}
                        </a>
                    {/if}

                    <!-- Date -->
                    <p style="color: var(--text-3); margin: 0; font-size: 0.9em;">
                        {media_data.source === 'youtube' ? 'Uploaded' : 'Created'} {getDateDisplay()}
                    </p>

                    <!-- Added Time -->
                    <p style="color: var(--text-3); margin: 0 0 0 -1px; font-size: 0.9em;">
                        Added {getAddedTimeDisplay()}
                    </p>

                    <!-- Processing time -->
                    {#if media_data.diarization_time}
                    <p style="color: var(--text-3); margin: 0 0 0 -1px; font-size: 0.9em;">
                        Processed in {media_data.diarization_time?.toFixed(1)} seconds
                    </p>
                    {/if}

                </div>

                <!-- Delete Button -->
                <div class="delete-btn-container">
                    {#if !delete_confirmation}
                        <button class="cs-btn delete-btn" style="color: var(--text); white-space: nowrap; width: 100%;" onclick={(e) => { delete_confirmation = true; e.target.blur(); }}>Delete</button>
                    {:else}
                        <button class="cs-btn delete-btn" style="color: var(--text); white-space: nowrap; width: 100%;" onclick={(e) => { delete_media_item([media_data.id]); e.target.blur(); }}>Confirm</button>
                    {/if}
                </div>

            </div>
        </Panel>

    </div>

</main>

<style>

    .delete-btn-container {
        padding-bottom: 4px;
    }

</style>