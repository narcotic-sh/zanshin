<script>
    import { onMount, onDestroy, createEventDispatcher } from 'svelte';
    import { cursor_auto_hide } from '$lib/actions/auto_hide_cursor.js';
    import { browser } from '$app/environment';

    const { video_id, autoplay = false, muted = false, aspect_ratio = 16.0/9.0, start_time = 0 } = $props();

    // Internal
    let player = null;
    let videoLoaded = false;
    let isPlaying = false;
    const dispatch = createEventDispatcher();

    // Time tracking related
    let currentTime = 0;
    let animationFrameId = null;

    onMount(() => {
        loadYouTubeAPI().then(() => {
            initializePlayer();
        });
    });

    onDestroy(() => {
        stopTimeUpdates();
        if (player) {
            player.destroy();
        }
    });

    function loadYouTubeAPI() {
        return new Promise((resolve) => {
            // If it's already loaded, resolve immediately
            if (window.YT && window.YT.Player) {
                resolve();
                return;
            }
            // Create a global callback for when the API is ready
            window.onYouTubeIframeAPIReady = () => {
                resolve();
            };
            if (browser) {
                // Load the script
                const tag = document.createElement('script');
                tag.src = "https://www.youtube.com/iframe_api";
                const firstScriptTag = document.getElementsByTagName('script')[0];
                firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
            }
        });
    }

    function initializePlayer() {
      player = new YT.Player('player', {
        videoId: video_id,
        playerVars: {
          'playsinline': 1,
          'disablekb': 1,
          'enablejsapi': 1,
          'iv_load_policy': 3,
          'cc_load_policy': 0,
          'controls': 0,
          'rel': 0,
          'autoplay': autoplay ? 1 : 0,
          'mute': muted ? 1 : 0,
          'start': Math.floor(start_time)
        },
        events: {
          'onReady': onPlayerReady,
          'onStateChange': onPlayerStateChange,
          'onError': onErrorOccurred
        }
      });
    }

    function onPlayerReady(event) {
        seekTo(start_time);
        pause();
        videoLoaded = true;
        // To get time updates started in case they don't run on page load (sometimes)
        if (autoplay) {
            setTimeout(() => {
            if (player && player.getPlayerState() === YT.PlayerState.PLAYING) {
                isPlaying = true;
                startTimeUpdates();
            }
            }, 100);
        }
        dispatch('ready');
    }

    function onPlayerStateChange(event) {
      isPlaying = event.data === YT.PlayerState.PLAYING;

      if (event.data === YT.PlayerState.PLAYING) {
        dispatch('play');
        startTimeUpdates();
      } else if (event.data === YT.PlayerState.PAUSED) {
        dispatch('pause');
        stopTimeUpdates();
      } else if (event.data === YT.PlayerState.ENDED) {
        dispatch('end');
        stopTimeUpdates();
      }
    }

    function onErrorOccurred(event) {
      dispatch('error', { code: event.data });
    }

    export function startTimeUpdates() {
      stopTimeUpdates(); // Ensure we're not duplicating updates

      function updateTime() {
        if (player && isPlaying) {
          currentTime = player.getCurrentTime();
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

    // For later use
    function formatTime(seconds) {
      if (isNaN(seconds)) return "00:00";
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = Math.floor(seconds % 60);
      return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    // Public methods (can be called by parent)
    export function play() {
        if (player) player.playVideo();
    }

    export function pause() {
        if (player) player.pauseVideo();
    }

    export function seekTo(seconds) {
        if (player) player.seekTo(seconds, true);
    }

    export function getCurrentTime() {
        return player ? player.getCurrentTime() : 0;
    }

    export function getDuration() {
        return player ? player.getDuration() : 0;
    }

    export function mute() {
        if (player) player.mute();
    }

    export function unMute() {
        if (player) player.unMute();
    }

    export function is_muted() {
        return player ? player.isMuted() : false;
    }

    export function is_playing() {
        return player && player.getPlayerState() === YT.PlayerState.PLAYING;
    }

    export function get_video_title() {
        const videoData = player.getVideoData();
        const videoTitle = videoData.title;
        return videoTitle;
    }

    export function get_duration() {
        return player ? player.getDuration() : 0;
    }

    export function setPlaybackRate(rate) {
        if (player) player.setPlaybackRate(rate);
    }

    export function skip(seconds) {
        if (player) {
            const currentTime = player.getCurrentTime();
            const duration = player.getDuration();
            const newTime = Math.min(currentTime + seconds, duration || 0);
            player.seekTo(newTime, true);
        }
    }

    export function rewind(seconds) {
        if (player) {
            const currentTime = player.getCurrentTime();
            const newTime = Math.max(currentTime - seconds, 0);
            player.seekTo(newTime, true);
        }
    }

  </script>

  <main>
    <!-- dynamic aspect ratio -->
    <div class="video-container" style="padding-bottom: {(1/aspect_ratio)*100}%">
        <div class="click-blocker" use:cursor_auto_hide={{ is_playing, delay: 3000 }}></div>
        <div id="player"></div>
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

    #player {
        --overflow-amount: 2px;
        position: absolute;
        z-index: 10;
        top: calc(-50% - var(--overflow-amount));
        left: calc(-1 * var(--overflow-amount));
        width: calc(100% + (var(--overflow-amount) * 2));
        height: calc(200% + (var(--overflow-amount) * 2));
        box-sizing: border-box;
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