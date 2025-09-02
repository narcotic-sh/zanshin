<svelte:head>
    <title>Zanshin Settings</title>
</svelte:head>

<script>
    import { capitalize_string } from "$lib/misc";
    import { set_setting, set_multiple_settings } from "$lib/api";
    import { invalidateAll } from '$app/navigation';
    import { onMount, onDestroy } from 'svelte';
    import { socket } from '$lib/socket.js';
    import CookiesDialog from './CookiesDialog.svelte';
    import SimpleDialog from "$lib/SimpleDialog.svelte";
    import GreentextDialog from "./GreentextDialog.svelte";
    import DialogStack from "$lib/DialogStack.svelte";

    /*
    =========================================================
        Page I/O
    =========================================================
    */

    /** @type {import('./$types').PageProps} */
    let { data } = $props();

    /*
    =========================================================
        cookies_from_browser Dialog
    =========================================================
    */

    let cookes_info_dialog_visible = $state(false);
    let cookies_selection_dialog_visible = $state(false);
    let selected_browser = $derived(data.cookies_from_browser);

    /*
    =========================================================
        identify_speakers Dialog
    =========================================================
    */

    let identify_speakers_info_dialog_visible = $state(false);
    let identify_speakers_on = $state(data.identify_speakers ?? true);

    /*
    =========================================================
        background_image Dialog
    =========================================================
    */

    let background_image_info_dialog_visible = $state(false);
    let background_image_on = $state(data.background_image ?? true);

    /*
    =========================================================
        alternate_bg_color Dialog
    =========================================================
    */

    let alternate_bg_color_info_dialog_visible = $state(false);
    let alternate_bg_color_on = $state(data.alternate_bg_color ?? false);

    /*
    =========================================================
        warmup_processor Dialog
    =========================================================
    */

    let warmup_processor_info_dialog_visible = $state(false);
    let warmup_processor_on = $state(data.warmup_processor ?? true);

    /*
    =========================================================
        restore_zoom_window Dialog
    =========================================================
    */

    let restore_zoom_window_info_dialog_visible = $state(false);
    let restore_zoom_window_on = $state(data.restore_zoom_window ?? true);

    /*
    =========================================================
        auto_skip_by_default Dialog
    =========================================================
    */

    let auto_skip_by_default_info_dialog_visible = $state(false);
    let auto_skip_by_default_on = $state(data.auto_skip_by_default ?? true);

    /*
    =========================================================
        Websocket comms w/ backend
    =========================================================
    */

    onMount(() => {
        socket.connect();
        socket.on('connect', () => {
            console.log('ws connected');
        });
        socket.on('settings_update', async () => {
            invalidateAll();
        });
    });

    onDestroy(() => {
        socket.off('connect');
        socket.off('settings_update');
        if (socket.connected) socket.disconnect();
    });
</script>

<main>

    <div style="display: flex; flex-direction: column; gap: 15px;">


        <div class="settings-container">
            <div class="settings-container-content">
                <h2 class="settings-heading">Settings</h2>
                <div class="settings-panel" style="overflow-y: hidden; height: 100%; max-height: 100%;">

                    <!-- Warmup processor on startup -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "warmup_processor"}>
                        <span class="setting-title">Warmup processor on startup<span class="info-link" onclick={() => { warmup_processor_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {warmup_processor_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    warmup_processor_on = !warmup_processor_on;
                                    await set_setting('warmup_processor', warmup_processor_on);
                                    e.target.blur();
                                }}
                            >
                                {warmup_processor_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Cookies from browser -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "cookies_from_browser"}>
                        <span class="setting-title">Use YouTube cookies from browser<span class="info-link" onclick={() => { cookes_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            {#if !selected_browser}
                                <p style="color: var(--text-3)">No browser selected</p>
                            {:else}
                                <p style="color: var(--text)">{capitalize_string(selected_browser)}</p>
                            {/if}
                            <button class="cs-btn" onclick={() => { cookies_selection_dialog_visible = true }}>Select</button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Auto-skip by default -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "auto_skip_by_default"}>
                        <span class="setting-title">Auto-skip unchecked speakers by default<span class="info-link" onclick={() => { auto_skip_by_default_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {auto_skip_by_default_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    auto_skip_by_default_on = !auto_skip_by_default_on;
                                    await set_setting('auto_skip_by_default', auto_skip_by_default_on);
                                    e.target.blur();
                                }}
                            >
                                {auto_skip_by_default_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Restore zoom window -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "restore_zoom_window"}>
                        <span class="setting-title">Restore zoom window on player load<span class="info-link" onclick={() => { restore_zoom_window_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {restore_zoom_window_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    restore_zoom_window_on = !restore_zoom_window_on;
                                    await set_setting('restore_zoom_window', restore_zoom_window_on);
                                    e.target.blur();
                                }}
                            >
                                {restore_zoom_window_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Identify speakers -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "identify_speakers"}>
                        <span class="setting-title">Identify speakers<span class="info-link" onclick={() => { identify_speakers_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {identify_speakers_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    identify_speakers_on = !identify_speakers_on;
                                    await set_setting('identify_speakers', identify_speakers_on);
                                    e.target.blur();
                                }}
                            >
                                {identify_speakers_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Alternate background color -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "alternate_bg_color"}>
                        <span class="setting-title">Alternate background color<span class="info-link" onclick={() => { alternate_bg_color_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {alternate_bg_color_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    alternate_bg_color_on = !alternate_bg_color_on;
                                    // Use batch update to avoid race conditions
                                    const updates = { 'alternate_bg_color': alternate_bg_color_on };

                                    // If turning on alternate_bg_color, turn off background_image
                                    if (alternate_bg_color_on && background_image_on) {
                                        background_image_on = false;
                                        updates['background_image'] = false;
                                    }

                                    await set_multiple_settings(updates);
                                    e.target.blur();
                                }}
                            >
                                {alternate_bg_color_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <hr class="cs-hr" />

                    <!-- Background image -->
                    <div class="setting-row" class:highlight={data.highlight_setting === "background_image"}>
                        <span class="setting-title">Background image<span class="info-link" onclick={() => { background_image_info_dialog_visible = true }}>[i]</span></span>
                        <div class="setting-control">
                            <button
                                class="cs-btn"
                                style="color: {background_image_on ? '#bcab4d' : 'var(--text)'}"
                                onclick={async (e) => {
                                    background_image_on = !background_image_on;
                                    // Use batch update to avoid race conditions
                                    const updates = { 'background_image': background_image_on };

                                    // If turning on background_image, turn off alternate_bg_color
                                    if (background_image_on && alternate_bg_color_on) {
                                        alternate_bg_color_on = false;
                                        updates['alternate_bg_color'] = false;
                                    }

                                    await set_multiple_settings(updates);
                                    e.target.blur();
                                }}
                            >
                                {background_image_on ? 'On' : 'Off'}
                            </button>
                        </div>
                    </div>

                    <!-- <hr class="cs-hr" /> -->

                    <!-- Additional Setting -->
                    <!-- <div class="setting-row">
                        <span class="setting-title">Setting 2</span>
                        <div class="setting-control">
                            <select class="cs-select">
                                <option value="option1">Standard View</option>
                                <option value="option2">Compact View</option>
                                <option value="option3">Detailed View</option>
                            </select>
                        </div>
                    </div> -->

                </div>
            </div>
        </div>

        <div class="settings-container" style="margin-bottom: 20px">
            <div class="settings-container-content" class:highlight={data.highlight_setting === "controls"}>
                <h2 class="settings-heading">Mouse & Keyboard Shortcuts</h2>
                <div class="settings-panel" style="max-height: calc(100vh - 645px); overflow-y: auto;">
                    <h3 class="shortcut-heading">Media player</h3>
                    <div class="keyboard-shortcuts">
Spacebar - play/pause
Right/Left Arrows - advance/rewind by 5s
M - mute/unmute
K - restart playback
I - toggle info, speakers, chapters panels visibility
                    </div>

                    <div style="height: 8px;"></div>

                    <h3 class="shortcut-heading">Segments bar</h3>
                    <div class="keyboard-shortcuts">
Left click - seek to beginning of hovered segment
Right click - seek to exact location
Wheel/vertical scroll - zoom in/out
Horizontal scroll / hold and drag - pan
WASD - zoom and pan
> - skip to next segment
&lt; - go back one segment
&#123; - go to prev segment of current speaker
&#125; - go to next segment of current speaker
X - toggle hovered speaker
O - solo hovered speaker
C - enable all speakers (toggle)
G - seek to hovered chapter start
V - bring current time marker into view
                    </div>

                    <div style="height: 8px;"></div>

                    <h3 class="shortcut-heading">Speakers Panel</h3>
                    <div class="keyboard-shortcuts">
Left click speaker color square - go to next segment of that speaker
Right click speaker color square - solo that speaker
Click percentages - toggle percentage/duration
T - toggle auto-skip unchecked speakers
                    </div>

                </div>
            </div>
        </div>

    </div>

</main>

<DialogStack bind:visible={cookes_info_dialog_visible}>
    <SimpleDialog
        bind:visible={cookes_info_dialog_visible}
        title={'cookies_from_browser'}
        text={`Sometimes YouTube's anti-bot measures kick in and block a download. This happens if you've been downloading a lot, or if you're on a large network like at a university, where others may have downloaded a bunch off YouTube recently.
            Or, you may have tried downloading an age restricted video, which you have to be signed in to view.
            In both cases, to allow the download and subsequent processing to proceed, one option is to allow the downloader to access your YouTube browser cookies, to authenticate you, so that the bot guard can unflag you and age restricted videos can be accessed, respectively.
        `}
    />
    <SimpleDialog
        bind:visible={cookes_info_dialog_visible}
        title={'Note for WSL users'}
        text={
        `You'll need to install Firefox *within* WSL. "sudo apt install firefox", and then open Firefox by running command "firefox". Sign into YouTube, and then select Firefox for this setting and the cookies will be accessible by the downloader.
        `}
    />
</DialogStack>

<DialogStack bind:visible={cookies_selection_dialog_visible}>
    <CookiesDialog
        bind:visible={cookies_selection_dialog_visible}
        bind:selected_browser
    />
</DialogStack>

<DialogStack bind:visible={identify_speakers_info_dialog_visible}>
    <SimpleDialog
        bind:visible={identify_speakers_info_dialog_visible}
        title={'identify_speakers'}
        text={`Identify speakers, create colored segments bar, when a media item is added.
        Turn off if you just like the UI/interface and would like to use it without this.`}
    />
</DialogStack>

<DialogStack bind:visible={background_image_info_dialog_visible}>
    <GreentextDialog
        bind:visible={background_image_info_dialog_visible}
        title={'background_image'}
        text={`>be me
>playing fy_pool_day
>guy with username "dEmEnTeD_sOcK_eNtHuSiAsT"
>has walmart microphone
>sounds like he's underwater
>"guys can you hear me?"
> *glub glub glub*
>annoyed.jpeg
>keeps talking
>thoroughly_vexed.jpeg
>still keeps talking
>becoming_homicidal.jpeg
>jump in the pool to calm my nerves
>he's there`}
    />
</DialogStack>

<DialogStack bind:visible={restore_zoom_window_info_dialog_visible}>
    <SimpleDialog
        bind:visible={restore_zoom_window_info_dialog_visible}
        title={'restore_zoom_window'}
        text={`Automatically restores your last segments bar zoom window upon page load of the media player.`}
    />
</DialogStack>

<DialogStack bind:visible={auto_skip_by_default_info_dialog_visible}>
    <SimpleDialog
        bind:visible={auto_skip_by_default_info_dialog_visible}
        title={'auto_skip_by_default'}
        text={`Whether unchecked speakers should be auto-skipped by default.
        I.e. when you first uncheck a speaker in a given media item, should auto-skip be on or off?`}
    />
</DialogStack>

<DialogStack bind:visible={alternate_bg_color_info_dialog_visible}>
    <SimpleDialog
        bind:visible={alternate_bg_color_info_dialog_visible}
        title={'alternate_bg_color'}
        text={`Switch the background color from the default to an alternate dark <a href="https://www.youtube.com/watch?v=om-WhQGhD2Q&t=67s" target="_blank" style="cursor: pointer; text-decoration: none; color: inherit;">green</a>.`}
    />
</DialogStack>

<DialogStack bind:visible={warmup_processor_info_dialog_visible}>
    <SimpleDialog
        bind:visible={warmup_processor_info_dialog_visible}
        title={'warmup_processor'}
        text={`Upon startup, we warm up the diarization processor so that the processing time of the first job doesn't take longer than it should. Turn this setting off if you'd like the first job to start right away with no warmup. First few jobs might take longer than they would with warmup though.`}
    />
</DialogStack>

<style>
    main {
        position: relative;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        min-height: calc(100vh - 90px);
        padding-top: 10px;
    }

    /*
    =========================================================
        Settings container
    =========================================================
    */

    .settings-container {
        width: 600px;
        background-color: var(--bg);
        border: solid 1px;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
    }

    .settings-container-content {
        padding: 16px 32px 20px;
        color: var(--text);
        position: relative;
    }

    /*
    =========================================================
        Settings Heading
    =========================================================
    */

    .settings-heading {
        color: var(--text);
        margin-bottom: 8px;
        user-select: none;
    }

    /*
    =========================================================
        Settings Panel
    =========================================================
    */

    .settings-panel {
        overflow-y: auto;
        max-height: calc(100vh - 300px);
        background-color: var(--secondary-bg);
        padding: 10px;
        border: solid 1px;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
    }

    /*
    =========================================================
        Individual Settings
    =========================================================
    */

    .setting-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 5px 10px;
    }

    .setting-row:first-child {
        padding-top: 5px;
    }

    .setting-row:last-child {
        border-bottom: none;
        margin-bottom: -6px;
    }

    .setting-title {
        color: var(--text);
        font-size: 16px;
        line-height: 15px;
    }

    .setting-control {
        display: flex;
        gap: 10px;
        align-items: center;
    }

    .info-link {
        color: var(--accent);
        cursor: pointer;
        user-select: none;
        padding-left: 2px;
    }

    .info-link:hover {
        filter: brightness(1.2);
    }

    /*
    =========================================================
        Glow animation
    =========================================================
    */

    @keyframes glow_golden {
        0%, 100% { background-color: transparent; }
        50% { background-color: var(--secondary-accent); }
    }

    .highlight {
        animation: glow_golden 1s;
    }

    .shortcut-heading {
        color: var(--text); /* or whatever color you want for headings */
        font-size: 16px;
        font-weight: normal;
        margin: 0 0 2px 0;
        line-height: 1.1;
    }

    .keyboard-shortcuts {
        white-space: pre-wrap;
        line-height: 1.1;
        color: var(--text-3);
        padding-left: 14px;
    }
</style>