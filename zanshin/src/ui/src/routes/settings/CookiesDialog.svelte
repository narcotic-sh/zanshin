<script>
    import { capitalize_string } from "$lib/misc";
    import { set_setting } from "$lib/api";
    import { onMount, onDestroy } from 'svelte';
    import { escape_key } from '$lib/actions/escape_key.js';

    let { visible = $bindable(), selected_browser = $bindable('') } = $props();

    const browsers = ['chrome', 'firefox', 'brave', 'edge', 'opera', 'chromium', 'vivaldi', 'whale'];

    $effect(() => {
        set_setting('cookies_from_browser', selected_browser);
    });

</script>

{#if visible}
    <div class="cs-dialog" onclick={(e) => e.stopPropagation()}>
        <p id="dialog-title">Select an installed browser in which you're signed into YouTube</p>
        <p id="dialog-subtitle">Don't select one you don't have installed</p>
        <p id="dialog-subtitle">Currently no Safari support</p>
        <p id="dialog-subtitle">On Linux/WSL, only Firefox currently works</p>
        <div id="browser-buttons-container">
            <div id="browser-buttons-grid">
                {#each browsers as browser}
                    <button
                        class="cs-btn browser-btn"
                        class:selected={selected_browser === browser}
                        onclick={() => {
                            if (selected_browser === browser) {
                                selected_browser = null;
                            } else {
                                selected_browser = browser;
                            }
                        }}>
                        {capitalize_string(browser)}
                    </button>
                {/each}
            </div>
        </div>
    </div>
{/if}

<style>
    .cs-dialog {
        position: relative;
        min-width: 350px;
        max-width: 700px;
        padding: 15px;
        background-color: var(--bg);
    }

    #dialog-title {
        padding-left: 2px;
        padding-bottom: 8px;
        margin-top: -2px;
    }

    #dialog-subtitle {
        padding-left: 2px;
        margin-top: -8px;
        margin-bottom: 8px;
        font-style: italic;
        font-size: 0.8em;
        color: var(--text-3);
    }

    #browser-buttons-container {
        background-color: var(--secondary-bg);
        padding: 10px;
        border: solid 1px;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
    }

    #browser-buttons-grid {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    .browser-btn {
        color: var(--secondary-text);
    }

    .browser-btn.selected {
        color: var(--accent);
    }
</style>