<script>
    import MediaItem from '$lib/MediaItem/MediaItem.svelte';
    const { youtube_previews, processor_status, active_job_status } = $props();
</script>

<main>
    <div class="media-list">
        {#each youtube_previews as preview}
            <MediaItem
                item_data={preview}
                active_job_status={active_job_status ? (preview.id === active_job_status.id ? active_job_status : null) : null}
                {processor_status}
            />
        {/each}
    </div>
</main>

<style>
    .media-list {
        display: flex;
        flex-direction: column;
        gap: 7px;
    }
</style>
