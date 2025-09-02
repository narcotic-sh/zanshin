<script>
    import SubmitJob from '$lib/SubmitJob.svelte';
    let { visible = $bindable(), processing_dialog_visible = $bindable(), form } = $props();
</script>

<main>

    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    {#if visible}
        <div class="cs-dialog" onclick={(e) => e.stopPropagation()}>
            <div class="heading">
                <div class="wrapper">
                    <p id="add-media-dialog-heading-text" class="text">Add new media</p>
                </div>
            </div>
            <div class="content">
                <SubmitJob
                    add_media_dialog={true}
                    bind:processing_dialog_visible
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

    #add-media-dialog-heading-text {
        color: var(--text);
        padding-left: 7px;
        padding-top: 4px;
    }

</style>
