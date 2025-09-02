<svelte:head>
   <title>Zanshin Vault</title>
</svelte:head>

<script>
    import { onMount, onDestroy, tick } from 'svelte';
    import { goto, invalidateAll, afterNavigate, beforeNavigate } from '$app/navigation';
    import { page } from '$app/stores';

    import { socket } from '$lib/socket.js';
    import { click_outside } from './helpers';

    import Filters from './Filters/Filters.svelte';
    import MediaItemsList from '$lib/MediaItem/MediaItemsList.svelte';
    import AddMediaDialog from './AddMediaDialog.svelte';
    import ProcessingDialog from './ProcessingDialog.svelte';
    import DialogStack from '$lib/DialogStack.svelte';

    /*
    =========================================================
        Page I/O
    =========================================================
    */

    /** @type {import('./$types').PageProps} */
	let { data } = $props();

    let active_job_status = $derived(data.active_job_status);

    /*
    =========================================================
        Filters
    =========================================================
    */

    let filters = $state();
    let filtered_and_searched_results = $state();

    // When any filters change, scroll to the top
    async function scroll_to_top() {
        scroll_to(0);
    }

    /*
    =========================================================
        Scroll Position Saving
    =========================================================
    */

    let processed_previews_container = $state();

    async function scroll_to(pos) {
        if (processed_previews_container && filtered_and_searched_results) {
            await tick();
            processed_previews_container.scrollTop = pos;
        }
    }

    // Save scroll position
    beforeNavigate(() => {
        if (processed_previews_container) {
            sessionStorage.setItem('vault-scroll', processed_previews_container.scrollTop.toString());
        }
    });

    // Restore scroll position
    afterNavigate(async () => {
        scroll_to(sessionStorage.getItem('vault-scroll') ?? '0');
    });

    /*
    =========================================================
        Reset
    =========================================================
    */

    function reset_vault() {
        filters.reset();
        scroll_to(0);
    }

    // Expose reset function globally for nav bar access
    $effect(() => {
        if (typeof window !== 'undefined') {
            window.reset_vault = reset_vault;
        }
    });

    /*
    =========================================================
        Search
    =========================================================
    */

    let search_active = $state(false);
    let search_box = $state();
    let search_box_value = $state('');
    let search_box_empty = $derived(search_box_value.trim().length === 0);

    $effect(() => {
        if (!search_box_empty) filters.reset();
    });

    /*
    =========================================================
        Media + Processing Dialogs
    =========================================================
    */

    let add_media_dialog;
    let processing_dialog;

    let add_media_dialog_visible = $state(false);
    let processing_dialog_visible = $state(false);
    let dialog_stack_visible = $derived(add_media_dialog_visible || processing_dialog_visible);

    $effect(() => {
        if (processing_dialog_items.length === 0 && !add_media_dialog_visible) {
            dialog_stack_visible = false;
        }
        if (!dialog_stack_visible) {
            add_media_dialog_visible = false;
            processing_dialog_visible = false;
        }
    });

    let processing_dialog_items = $derived([...data.processing, ...data.queued, ...data.failed]);
    let only_failed_jobs = $derived(data.failed.length > 0 && processing_dialog_items.length === data.failed.length);
    let should_glow_proc_button = $derived(data.processing.length > 0 || data.queued.length > 0);

    /*
    =========================================================
        Websocket comms w/ backend
    =========================================================
    */

    let page_load_timestamp = Date.now();
    onMount(() => {
        socket.connect();
        socket.on('connect', () => {
            console.log('ws connected');
        });
        // If already have vault page open in another tab ; only invalidate if the event happened sufficiently after page load
        socket.on('new_job_submission', async (eventData) => {
            if (eventData && eventData.timestamp && eventData.timestamp > (page_load_timestamp + 300)) {
                await invalidateAll();
                if (add_media_dialog_visible) {
                    processing_dialog_visible = true;
                }
            }
            console.log('new_job_submission');
        });
        socket.on('new_job_started', () => {
            invalidateAll();
            console.log('new_job_started');
        });
        socket.on('progress_update', (socket_data) => {
            active_job_status = socket_data;
        });
        socket.on('job_done', () => {
            invalidateAll();
        });
        socket.on('metadata_refresh', () => {
            invalidateAll();
            console.log('metadata_refresh')
        });
    });

    onDestroy(() => {
        socket.off('connect');
        socket.off('new_job_submission');
        socket.off('new_job_started');
        socket.off('progress_update');
        socket.off('job_done');
        socket.off('metadata_refresh');
        socket.off('file_submitted');
        socket.off('file_already_exists');
        if (socket.connected) socket.disconnect();
    });

</script>

<main>
    <div id="vault-container">
        {#if !data.error}
            <div id="vault-content">

                <div id="header-buttons">

                    <!-- + Button -->
                    <button id="add-button" class="cs-btn" onclick={() => { add_media_dialog_visible = true }}>+</button>

                    <!-- Processing Button -->
                    {#if processing_dialog_items.length > 0}
                        <button id="processing-button" class="cs-btn" onclick={() => { processing_dialog_visible = true }}>
                            <span class={should_glow_proc_button ? 'text-glow' : ''} style={only_failed_jobs ? 'color: #ff5252' : ''}>Processing</span>
                        </button>
                    {/if}

                    {#if !search_active}
                        <button id="search-btn" class="cs-btn" onclick={async (event) => {
                            if (!search_active) {
                                search_active = true;
                                await tick();
                                search_box.focus();
                            } else {
                                search_active = false;
                            }
                            event.stopPropagation();
                        }}>Search</button>

                    {:else}
                        <input
                            type="text"
                            placeholder="Search titles"
                            class="cs-input"
                            autocomplete="off"
                            spellcheck="false"
                            autocorrect="off"
                            autocapitalize="off"
                            bind:this={search_box}
                            bind:value={search_box_value}
                            use:click_outside={() => {
                                search_box_value = '';
                                search_active = false;
                            }}
                            onkeydown={(event) => {
                                if (event.key === 'Escape') {
                                    search_box_value = '';
                                    search_active = false;
                                    event.preventDefault();
                                }
                            }}
                        />
                    {/if}

                </div>

                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <h2 id="vault-heading" onclick={() => {
                    event.preventDefault();
                    const scroll_top = processed_previews_container.scrollTop;
                    if (scroll_top != 0) {
                        processed_previews_container.scrollTop = 0;
                    } else {
                        reset_vault();
                    }
                }} style="cursor: pointer">Vault</h2>

                <Filters
                    bind:this={filters}
                    success={data.success}
                    {search_box_value}
                    {search_box_empty}
                    bind:filtered_and_searched_results
                    on:filters_changed={() => { scroll_to_top() }}
                />

                <div id="processed-previews" bind:this={processed_previews_container} style="scroll-behavior: auto;">

                    {#if filtered_and_searched_results?.length > 0}
                        <MediaItemsList
                            youtube_previews={filtered_and_searched_results}
                            processor_status={data.processor_status}
                            active_job_status={active_job_status}
                        />
                    {:else if !search_box_empty}
                        <p class="processed-previews-message">No matching search results</p>
                    {:else if data.success.length === 0}
                        <p class="processed-previews-message">Click the + button to add media</p>
                    {:else}
                        <p class="processed-previews-message">¯\_(ツ)_/¯</p>
                    {/if}
                </div>
            </div>
        {:else}
            <p>Error loading processed media: {data.error}</p>
        {/if}
    </div>
</main>

<DialogStack bind:visible={dialog_stack_visible}>
    <AddMediaDialog
        bind:visible={add_media_dialog_visible}
        bind:processing_dialog_visible
    />
    <ProcessingDialog
        bind:visible={processing_dialog_visible}
        items={processing_dialog_items}
        processor_status={data.processor_status}
        active_job_status={active_job_status}
    />
</DialogStack>

<style>

    main {
        position: relative;
        display: block;
        min-height: calc(100vh - 90px); /* Account for nav spacing */
        padding-top: 10px;
    }

    /*
    =========================================================
        Vault Container
    =========================================================
    */

    #vault-container {
        width: 850px;
        margin: 0 auto;
        background-color: var(--bg);
        border: solid 1px;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
    }

    #vault-content {
        padding: 16px 32px 35px;
        color: var(--text);
        position: relative;
    }

    /*
    =========================================================
        Vault Header
    =========================================================
    */

    #header-buttons {
        position: absolute;
        top: 12px;
        right: 12px;
        display: flex;
        flex-direction: row-reverse;
        gap: 6px;
    }

    @keyframes text-pulse {
        0% {
            filter: brightness(1);
        }
        50% {
            filter: brightness(1.5);
        }
        100% {
            filter: brightness(1);
        }
    }

    .text-glow {
        color: var(--accent);
        animation: text-pulse 2s infinite;
        display: inline-block;
    }

    #vault-heading {
        color: var(--text);
        margin-bottom: 12px;
        user-select: none;
    }

    /*
    =========================================================
        Processed Media
    =========================================================
    */

    #processed-previews {
        overflow-y: auto;
        max-height: calc(100vh - 262px);
        background-color: var(--secondary-bg);
        padding: 10px;
        border: solid 1px;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
    }

    .processed-previews-message {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 20px;
        margin: 0;
        text-align: center;
    }

</style>
