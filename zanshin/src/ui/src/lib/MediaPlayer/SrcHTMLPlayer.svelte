
<script>
    import { onMount, onDestroy, createEventDispatcher } from 'svelte';
    import { cursor_auto_hide } from '$lib/actions/auto_hide_cursor.js';
    import { browser } from '$app/environment';

    const { id, url, aspect_ratio = 16.0/9.0, media_type = 'video', autoplay = false, muted = false, start_time = 0 } = $props();

    // Internal
    let player = null;
    let isPlaying = false;
    const dispatch = createEventDispatcher();

    // Time tracking related
    let currentTime = 0;
    let animationFrameId = null;

    onMount(() => {
        initializePlayer();
    });

    onDestroy(() => {
        stopTimeUpdates();
    });

    function isSafari() {
        return /^((?!chrome|android).)*safari/i.test(navigator.userAgent) ||
                /iPad|iPhone|iPod/.test(navigator.userAgent);
    }

    function initializePlayer() {
        if (browser) {
            // Player is already initialized in the HTML
            player = document.getElementById('html-player');

            if (player) {
                // Set initial properties
                player.muted = muted;
                player.autoplay = autoplay;

                // Check if player is already loaded
                if (player.readyState >= 2) {  // HAVE_CURRENT_DATA or better
                    // Player is already ready
                    setTimeout(() => onPlayerReady(), 0);   // setTimeout is important here; doesn't work without it.
                } else {
                    // Set up normal event listeners
                    if (isSafari()) {
                        player.addEventListener('loadedmetadata', onPlayerReady);
                    } else {
                        player.addEventListener('loadeddata', onPlayerReady);
                    }
                }

                // Add other event listeners
                player.addEventListener('play', onPlay);
                player.addEventListener('pause', onPause);
                player.addEventListener('ended', onEnded);
                player.addEventListener('error', onError);
            }
        }
    }

    function onPlayerReady() {
        // Set the initial start time if specified
        if (start_time > 0) {
            player.currentTime = start_time;
        }
        dispatch('ready');
    }

    function onPlay() {
        isPlaying = true;
        dispatch('play');
        startTimeUpdates();
    }

    function onPause() {
        isPlaying = false;
        dispatch('pause');
        stopTimeUpdates();
    }

    function onEnded() {
        isPlaying = false;
        dispatch('end');
        stopTimeUpdates();
    }

    function onError(event) {
        const error_code = event.target.error.code;
        dispatch('error', { code: error_code });
    }

    export function startTimeUpdates() {
        stopTimeUpdates(); // Ensure we're not duplicating updates

        function updateTime() {
            if (player && isPlaying) {
                currentTime = player.currentTime;
                dispatch('timeupdate', currentTime);
            }
            animationFrameId = requestAnimationFrame(updateTime);
        }

        animationFrameId = requestAnimationFrame(updateTime);
    }

    export function stopTimeUpdates() {
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
    }

    // Public methods (can be called by parent)
    export function play() {
        if (player) player.play();
    }

    export function pause() {
        if (player) player.pause();
    }

    export function seekTo(seconds) {
        if (player) player.currentTime = seconds;
    }

    export function getCurrentTime() {
        return player ? player.currentTime : 0;
    }

    export function getDuration() {
        return player ? player.duration : 0;
    }

    export function mute() {
        if (player) player.muted = true;
    }

    export function unMute() {
        if (player) player.muted = false;
    }

    export function is_muted() {
        return player ? player.muted : false;
    }

    export function is_playing() {
        return player ? !player.paused : false;
    }

    export function get_duration() {
        return player ? player.duration : 0;
    }

    export function setPlaybackRate(rate) {
        if (player) player.playbackRate = rate;
    }

    export function skip(seconds) {
        if (player) {
            const newTime = Math.min(player.currentTime + seconds, player.duration || 0);
            player.currentTime = newTime;
        }
    }

    export function rewind(seconds) {
        if (player) {
            const newTime = Math.max(player.currentTime - seconds, 0);
            player.currentTime = newTime;
        }
    }

</script>

<main>
    <!-- dynamic aspect ratio -->
    <div class="video-container" style="padding-bottom: {(1/aspect_ratio)*100}%">

        {#if media_type === 'video'}
            <div class="click-blocker" use:cursor_auto_hide={{ is_playing, delay: 3000 }}></div>
            <video
                id="html-player"
                src={url}
                preload="metadata">
            </video>
        {:else}
            <audio
                id="html-player"
                src={url}
                preload="metadata">
            </audio>
            <div class="audio-placeholder"></div>
        {/if}

    </div>
</main>

<style>
    .video-container {
        position: relative;
        width: 100%;
        height: 0;
        overflow: hidden;
        background-color: #000;
    }

    #html-player {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
    }

    audio#html-player {
        display: none;
    }

    .audio-placeholder {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(45deg, #333, #111);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .audio-placeholder::after {
        content: '';
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M11 5L6 9H2v6h4l5 4zM19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: center;
        background-size: 64px;
        width: 100%;
        height: 100%;
        opacity: 0.5;
    }

    .click-blocker {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 11;
        cursor: default;
        background: transparent;
        user-select: none;
    }
</style>
