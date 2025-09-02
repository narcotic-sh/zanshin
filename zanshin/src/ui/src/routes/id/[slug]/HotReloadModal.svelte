<script>
    import { createEventDispatcher } from 'svelte';

    const dispatch = createEventDispatcher();

    let {
        show = $bindable(false),
        initialData = null
    } = $props();

    let textarea = $state('');
    let error = $state('');

    // Initialize textarea when modal opens
    $effect(() => {
        if (show && initialData) {
            textarea = JSON.stringify(initialData, null, 2);
            error = '';
        }
    });

    function close() {
        show = false;
        textarea = '';
        error = '';
        dispatch('close');
    }

    function submit() {
        try {
            const newData = JSON.parse(textarea);
            dispatch('submit', newData);
            error = '';
            close();
        } catch (err) {
            error = `Invalid JSON: ${err.message}`;
        }
    }

    function handleKeydown(event) {
        if (event.key === 'Escape') {
            close();
        }
    }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
    <div class="overlay" on:click={close}>
        <div class="cs-dialog modal" on:click|stopPropagation>
            <div class="heading" style="padding: 5px 5px 5px 10px">
                <div class="wrapper">
                    <div class="text">Hot Reload merged_segments and speaker_color_sets</div>
                </div>
                <button class="cs-btn close" on:click={close}></button>
            </div>

            <div class="content">
                <textarea
                    bind:value={textarea}
                    placeholder="Paste your merged_segments and speaker_color_sets here. This script outputs the correct format to paste into here: https://github.com/narcotic-sh/senko/blob/main/examples/diarize.py"
                    rows="20"
                    class="cs-textarea"
                ></textarea>

                {#if error}
                    <div class="error-message">{error}</div>
                {/if}

                <div class="footer-btns" style="margin-top: -3px; margin-bottom: -1px;">
                    <button class="cs-btn" on:click={close}>Cancel</button>
                    <button class="cs-btn" on:click={submit}>Apply</button>
                </div>
            </div>
        </div>
    </div>
{/if}

<style>
    .overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }

    .modal {
        /* Override cs-dialog positioning to center it */
        position: static !important;
        right: auto !important;
        top: auto !important;
        margin: 0 !important;

        width: 90%;
        max-width: 800px;
        max-height: 90vh;
        display: flex;
        flex-direction: column;
        background-color: var(--bg);
    }

    .content {
        display: flex;
        flex-direction: column;
        gap: 16px;
        flex: 1;
        min-height: 0;
    }

    .cs-textarea {
        width: 100%;
        min-height: 400px;
        background-color: var(--secondary-bg);
        color: var(--text);
        border: 1px solid;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
        padding: 3px 2px 2px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.4;
        resize: vertical;
        outline: 0;
    }

    .cs-textarea:focus {
        color: var(--accent);
    }

    .cs-textarea::selection {
        background-color: var(--secondary-accent);
        color: white;
    }

    .error-message {
        color: var(--accent);
        background-color: var(--secondary-bg);
        border: 1px solid;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
        padding: 8px 12px;
        font-size: 14px;
        line-height: 15px;
    }

    .footer-btns {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 8px;
    }

    .footer-btns .cs-btn {
        width: 72px;
        text-align: center;
    }
</style>