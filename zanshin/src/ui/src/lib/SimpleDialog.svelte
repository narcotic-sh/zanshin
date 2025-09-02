<script>
    import { capitalize_string } from "$lib/misc";
    import { set_setting } from "$lib/api";
    import { onMount, onDestroy } from 'svelte';

    let { visible = $bindable(), title, text } = $props();

</script>

{#if visible}
    <div class="cs-dialog" onclick={(e) => e.stopPropagation()}>
        <p id="dialog-title">{title}</p>
        <p id="dialog-text">{@html text}</p>
    </div>
{/if}

<style>
    .cs-dialog {
        position: relative;
        min-width: 350px;
        max-width: 650px;
        padding: 15px;
        background-color: var(--bg);
    }

    #dialog-title {
        padding-left: 2px;
        padding-bottom: 8px;
        margin-top: -2px;
        color: var(--accent);
    }

    #dialog-text {
        padding-left: 2px;
        margin-top: -8px;
        color: var(--secondary-text);
        white-space: pre-line;
    }
</style>