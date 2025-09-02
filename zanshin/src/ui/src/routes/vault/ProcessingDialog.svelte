<script>

    import MediaItemsList from '$lib/MediaItem/MediaItemsList.svelte';

    let { visible = $bindable(), items = [], processor_status, active_job_status} = $props();

</script>

<main>

    {#if visible && items.length > 0}
        <div class="cs-dialog processing-dialog" onclick={(e) => e.stopPropagation()}>
            <div id="processing-dialog-heading-container">
                <p id="processing-dialog-heading-text">Processing</p>
            </div>
            <div id="processing-previews">
                <MediaItemsList
                    youtube_previews={items}
                    processor_status={processor_status}
                    active_job_status={active_job_status}
                />
            </div>
        </div>
    {/if}

</main>

<style>

    .cs-dialog {
        position: relative;
        min-width: 350px;
        max-width: 700px;
        background-color: var(--bg);
    }

    .cs-dialog.processing-dialog {
        width: 650px;
    }

    #processing-dialog-heading-container {
        position: relative;
        height: 32px;
    }

    #processing-dialog-heading-text{
        position: absolute;
        left: 14px;
        top: 3px;
        font-size: 16px;
    }

    #processing-previews {
        overflow-y: auto;
        max-height: 70vh;
        background-color: var(--secondary-bg);
        padding: 10px;
        border: solid 1px;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
        margin: 0 10px 10px 10px;
    }

</style>