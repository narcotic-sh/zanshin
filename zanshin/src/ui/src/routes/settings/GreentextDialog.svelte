<script>
    import { capitalize_string } from "$lib/misc";
    import { set_setting } from "$lib/api";
    import { onMount, onDestroy } from 'svelte';
    import { escape_key } from '$lib/actions/escape_key.js';
    import fyPoolDayImage from '$lib/static/fy_pool_day.jpg';

    let { visible = $bindable(), title, text } = $props();
</script>

{#if visible}
    <div class="cs-dialog" onclick={(e) => e.stopPropagation()}>
        <p id="dialog-title">{title}</p>
        <div id="greentext-box">
            <div class="image-container">
                <img
                    src={fyPoolDayImage}
                    alt="Pepe"
                    id="greentext-image"
                />
                <div class="file-info">240 KB JPG</div>
            </div>
            <p id="dialog-text">{text}</p>
        </div>
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

    #greentext-box {
        background-color: #d6daed;
        padding: 10px;
        position: relative;
    }

    .image-container {
        float: left;
        margin-right: 10px;
        margin-bottom: 5px;
    }

    #greentext-image {
        display: block;
        width: 120px;
        height: auto;
    }

    .file-info {
        font-family: arial, helvetica, sans-serif;
        font-size: 9pt;
        color: rgb(121, 112, 110);
        text-align: center;
        margin-top: 2px;
    }

    #dialog-text {
        color: #7f9839;
        line-height: 1.15;
        white-space: pre-line;
        margin: 0;
        font-family: arial, helvetica, sans-serif;
        font-size: 11pt;
    }
</style>