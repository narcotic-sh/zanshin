<script>

    import { onMount, onDestroy } from 'svelte';
    import { escape_key } from '$lib/actions/escape_key.js';

    let { visible = $bindable(), children } = $props();

</script>

<main>

    {#if visible}
    <div class="dialog-backdrop" use:escape_key={() => { visible = false }} onclick={() => { visible = false }}>
        <div class="dialogs-container">
            {@render children()}
        </div>
    </div>
    {/if}

</main>

<style>

    .dialog-backdrop {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(4px);
        display: grid;
        place-items: center;
        z-index: 9999;
    }

    .dialogs-container {
        display: flex;
        flex-direction: column;
        gap: 16px;
        align-items: center;
        max-height: 90vh;
    }

</style>