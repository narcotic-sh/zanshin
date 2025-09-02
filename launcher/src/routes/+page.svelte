<script>
    import { invoke } from "@tauri-apps/api/core";
    import { listen } from '@tauri-apps/api/event';
    import { onMount } from "svelte";

    let zanshin_status = $state("");
    let first_run = $state(false);
    let showJapanese = $state(true);

    function toggleLanguage() {
        showJapanese = !showJapanese;
    }

    onMount(async () => {
        listen('zmq_notification', (event) => {
            const { status, is_first_run } = event.payload;
            zanshin_status = `${status}`;
            first_run = is_first_run;
        });
        setTimeout(async () => { await invoke("initialize") }, 50);
    });
</script>

<main>
    <div class="container">
        <div class="title" role="button" tabindex="0" onclick={toggleLanguage} onkeydown={(e) => e.key === 'Enter' && toggleLanguage()}>
            {showJapanese ? '残心' : 'Zanshin'}
        </div>
        <p class="status">{zanshin_status}</p>
        {#if first_run}
            <div class="first-run-message">
                <p>This first launch can take a while.</p>
                <p>Pass the time by watching a cool video like <span class="video-link" onclick={() => { invoke("open_tiger_video") }}>this one</span></p>
            </div>
        {/if}
    </div>
</main>

<style>
    main {
        width: 100%;
        height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        user-select: none;
        cursor: default;
    }

    .container {
        display: flex;
        flex-direction: column;
        padding: 10vh;
        text-align: center;
    }

    .title {
        font-size: 5rem;
        font-weight: bold;
        margin-bottom: -2vh;
        cursor: pointer;
        display: inline-block;
    }

    .status {
        font-size: 6vh;
        font-style: italic;
        text-align: center;
        color: var(--accent);
    }

    .first-run-message {
        font-size: 0.85rem;
        text-align: center;
        margin-top: 1rem;
        color: var(--text-3);
    }

    .video-link {
        cursor: pointer;
        text-decoration: underline;
    }

    :global(body) {
        overflow: hidden;
        user-select: none;
        cursor: default;
    }

    :global(html, body) {
        overflow: hidden;
        height: 100vh;
    }
</style>