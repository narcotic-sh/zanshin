<script>

    import { createEventDispatcher } from 'svelte';
    import { apply_filters } from './filter.js';
    import { onMount, onDestroy } from "svelte";

    const dispatch = createEventDispatcher();

    /*
    =========================================================
        Input
    =========================================================
    */

    let { success, filtered_and_searched_results = $bindable(), search_box_empty, search_box_value } = $props();

    export function reset() {
        filters = default_filters;
    }

    onMount(() => {
        if (sessionStorage.getItem('reset-filters')) {
            reset();
            sessionStorage.setItem('reset-filters', '');
        }
    });

    /*
    =========================================================
        Output
    =========================================================
    */

    let computed = $derived(apply_filters(success, filters, search_box_empty, search_box_value));
    $effect(() => { filtered_and_searched_results = computed });

    /*
    =========================================================
        Internal
    =========================================================
    */

    const default_filters = {
        source: 'all',
        channel: 'all',
        order_by: 'date-added',
        time: 'newest'
    };

    const saved_filters = sessionStorage.getItem('vault_filters');
    let filters = $state(saved_filters ? JSON.parse(saved_filters) : default_filters);

    let prev_filters = null;
    let filters_initialized = false;

    // Runs every time filters change
    $effect(() => {

        // If source filter changes, set the rest to default values
        if (prev_filters) {
            if (prev_filters.source !== filters.source) {
                console.log('source changed');
                filters.channel = 'all';
                filters.order_by = 'date-added';
                filters.time = 'newest';
            }
        }
        prev_filters = { ...filters };

        sessionStorage.setItem('vault_filters', JSON.stringify(filters));

        // For scrolling to top
        if (filters_initialized) { dispatch('filters_changed') }
        filters_initialized = true;

    });

    let channels = $derived([...new Set(
        success
            .filter(job => job.source === 'youtube' && job.channel)
            .map(job => job.channel)
    )].sort());

</script>

<main>

    <div id="filters-row">

        <div class="filter-group">
            <label for="source" class="filter-label">Source:</label>
            <select id="source" class="cs-select" bind:value={filters.source}>
                <option value="all">All</option>
                <option value="youtube">YouTube</option>
                <option value="local">Local Files</option>
            </select>
        </div>

        {#if filters.source === 'youtube'}
            <div class="filter-group">
                <label for="yt-channel" class="filter-label">Channel:</label>
                <select id="yt-channel" class="cs-select" bind:value={filters.channel}>
                    <option value="all">All</option>
                    {#each channels as channel}
                        <option value="{channel}">{channel}</option>
                    {/each}
                </select>
            </div>
        {/if}

        {#if search_box_empty}
            <div class="filter-group">
                <label for="yt-order-by" class="filter-label">Order by:</label>
                <select id="yt-order-by" class="cs-select" bind:value={filters.order_by}>
                    <option value="date-added">Date added</option>
                    {#if filters.source === 'youtube'}
                        <option value="date-uploaded">Date uploaded</option>
                    {:else if filters.source === 'local'}
                        <option value="creation-timestamp">File created</option>
                    {/if}
                </select>
            </div>

            <div class="filter-group">
                <label for="yt_newest_oldest" class="filter-label">Time:</label>
                <select id="yt_newest_oldest" class="cs-select" bind:value={filters.time}>
                    <option value="newest">Newest</option>
                    <option value="oldest">Oldest</option>
                </select>
            </div>
        {/if}

    </div>

</main>

<style>

    #filters-row {
        display: flex;
        gap: 20px;
        margin-bottom: 16px;
    }

    .filter-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .filter-label {
        color: var(--text-3);
        font-size: 14px;
        user-select: none;
    }

    .cs-select {
        min-width: 0px;
        max-width: 150px;
        height: 25px;
        width: auto;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        padding-right: 20px; /* space for dropdown arrow */
    }

    .cs-select option {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

</style>