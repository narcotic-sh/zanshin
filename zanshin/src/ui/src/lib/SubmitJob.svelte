<script>
    import { goto } from '$app/navigation';
    import { check_media_item_exists } from '$lib/api';
    import { extract_youtube_video_id } from '$lib/misc';
    import { onMount, onDestroy } from 'svelte';
    import { socket } from '$lib/socket.js';
    import { tick } from 'svelte';
    import { page } from '$app/state';
    import { browser } from '$app/environment';
    import Processing from '../routes/id/[slug]/Processing.svelte';

    let { add_media_dialog = false, processing_dialog_visible = $bindable() } = $props();

    let youtube_url_input = $state();
    let error = $state(null);
    let youtubeUrl = $state('');

    $effect(async () => {
        if (add_media_dialog) {
            await tick();
            youtube_url_input.focus();
        }
    });

    async function handleYoutubeSubmit(event) {
        event.preventDefault();
        error = null;

        // Check if video is already processed
        const youtube_video_id = extract_youtube_video_id(youtubeUrl);
        if (!youtube_video_id) {
            error = 'Invalid YouTube URL';
            return;
        }

        const id = await check_media_item_exists(youtube_video_id);

        if (id) {
            goto(`/id/${id}`);
            return;
        }

        // Send to your backend
        try {
            const response = await fetch('/api/submit_youtube', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: youtubeUrl })
            });

            if (response.ok) {
                if (add_media_dialog) {
                    processing_dialog_visible = true;
                    youtubeUrl = '';
                    youtube_url_input.blur();
                } else {
                    const data = await response.json();
                    const assigned_id = data.id;
                    goto(`/id/${assigned_id}`);
                }
            } else {
                error = 'Failed to process YouTube URL';
            }
        } catch (e) {
            error = 'Error connecting to server';
            console.error(e);
        }
    }

    async function trigger_file_select_dialog() {
        try {
            await fetch('/api/open_file', {
                method: 'GET',
            });
        } catch (error) {
            console.error('Error opening file dialog:', error);
        }
    }

    function handleGlobalPaste(event) {
        if (browser) {
            if (youtube_url_input && document.activeElement !== youtube_url_input) {
                youtube_url_input.focus();
            }
        }
    }

    onMount(() => {
        if (browser) {
            socket.connect();
            socket.on('connect', () => {
                console.log('ws connected');
            });
            socket.on('file_submitted', (eventData) => {
                console.log(eventData);
                if (page.url.pathname === '/') goto(`/id/${eventData.id}`);
            });
            socket.on('file_already_exists', async (eventData) => {
                goto(`/id/${eventData.id}`);
            });
            socket.on('file_extension_invalid', () => {
                error = 'Invalid file extension\nSupported: [mp4, webm, ogv, mpg, mpeg, mp3, wav, ogg, aac, m4a, opus]';
            });
            socket.on('file_empty', () => {
                error = 'Empty file!';
            });

            document.addEventListener('paste', handleGlobalPaste);
        }
    });

    onDestroy(() => {
        if (browser) {
            socket.off('connect');
            socket.off('file_submitted');
            socket.off('file_already_exists');
            socket.off('file_extension_invalid');
            socket.off('file_empty');
            if (socket.connected) socket.disconnect();

            document.removeEventListener('paste', handleGlobalPaste);
        }
    });

</script>


<main>

    <form class="search-container" onsubmit={handleYoutubeSubmit}>
        <input
            type="text"
            placeholder="YouTube URL"
            class="cs-input search-input"
            bind:value={youtubeUrl}
            autocomplete="off"
            spellcheck="false"
            autocorrect="off"
            autocapitalize="off"
            bind:this={youtube_url_input}
        />
        <button class="cs-btn" type="submit">Go</button>
    </form>

    {#if error}
        <div class="error-message">
            {#each error.split('\n') as line}
                <p>{line}</p>
            {/each}
        </div>
    {/if}

    <p class="drag-drop-text">or <a href="#" class="select-link" onclick={trigger_file_select_dialog}>select</a> a local file</p>

</main>

<style>

    .search-container {
        display: flex;
        align-items: center;
        gap: 10px;
        user-select: none;
    }

    .search-input {
        width: 400px;
    }

    .error-message {
        color: #ff3e00;
        margin-top: 10px;
        font-size: 14px;
        text-align: left;
    }
    .select-link {
        color: var(--accent); /* Using accent color by default */
        text-decoration: none;
        cursor: pointer;
        transition: color 0.2s ease;
        user-select: none;
    }

    .select-link:hover {
        filter: brightness(1.2); /* Make it slightly brighter on hover */
        text-decoration: none;
    }

    .drag-drop-text {
        font-size: 15px;
        text-align: left;
        margin: 10px 0 0 0;
        padding: 0;
        color: #B7B7B7;
        user-select: none;
    }

</style>
