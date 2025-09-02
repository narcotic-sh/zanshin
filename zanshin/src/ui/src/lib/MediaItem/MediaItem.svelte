<script>

    import { onMount, onDestroy, createEventDispatcher } from 'svelte';
    import { invalidateAll } from '$app/navigation';
    import { delete_media_item, retry_processing, get_setting } from '$lib/api';
    import { format_duration, format_timestamp, format_local_path } from '$lib/misc';

    /*
    =========================================================
        Page I/O
    =========================================================
    */

    const { item_data, active_job_status, processor_status } = $props();

    /*
    =========================================================
        State
    =========================================================
    */

    let delete_confirmation = $state(false);

    /*
    =========================================================
        Helpers
    =========================================================
    */

    function was_click_in_empty_area(event) {
        let target = event.target;
        let isDeleteButton = false;
        while (target !== event.currentTarget) {
            if (target.classList && (target.classList.contains('cs-btn') && target.classList.contains('delete-btn'))) {
                isDeleteButton = true;
                break;
            }
            target = target.parentElement;
        }
        return !isDeleteButton;
    }

</script>

<main>

    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="media-item"
        onmouseleave={() => { delete_confirmation = false }}
        onclick={(e) => { if (was_click_in_empty_area(e)) delete_confirmation = false }}>

        <!--
        =========================================================
            Thumbnail
        =========================================================
        -->

        <div class="thumbnail-outline">
            <div class="thumbnail-container">
                <a href="{`/id/${item_data.id}`}">

                    <!-- Metadata fetched -->
                    {#if item_data.metadata_status === 'success'}

                        <!-- If thumbnail exists -->
                        {#if item_data.thumbnail_exists}
                            <img src={`/api/thumbnail/${item_data.id}?low_res=true`} alt={item_data.title} />

                        <!-- If doesn't exist and media type is audio, render audio placeholder icon -->
                        {:else if item_data.media_type === 'audio'}
                            <div class="audio-thumbnail">
                                <div class="audio-icon"></div>
                            </div>

                        <!-- Thumbnail not available text -->
                        {:else}
                            <div class="placeholder-thumbnail">
                                <span class="no-thumbnail-text">Thumbnail not available</span>
                            </div>
                        {/if}

                        <!-- Duration badge (bottom right in thumbnail) -->
                        <div class="duration-badge">{format_duration(item_data.duration)}</div>

                    <!-- Metadata pending -->
                    {:else if item_data.metadata_status === 'pending'}
                        <div class="placeholder-thumbnail">
                            <div class="thumbnail-loading loading-animation"></div>
                        </div>

                    <!-- Metadata fetch failed -->
                    {:else if item_data.metadata_status === 'failed'}
                        <div class="placeholder-thumbnail">
                            <span class="no-thumbnail-text">Thumbnail not available</span>
                        </div>
                    {/if}

                </a>
            </div>
        </div>

        <!--
        =========================================================
            Title, media details
        =========================================================
        -->

        <div class="media-details">

            <!-- Local Media -->
            {#if item_data.source === 'local'}

                <!-- For local files, guaranteed to have filename, no need to wait for metadata to fetch for that -->
                <a href="/id/{item_data.id}" class="media-title">{item_data.title}</a>

                <!-- Metadata pending for local files; placeholder animation -->
                {#if item_data.metadata_status === 'pending'}
                    <div class="loading-text-placeholder channel-placeholder loading-animation"></div>
                    <div class="loading-text-placeholder date-placeholder loading-animation"></div>

                {:else if item_data.metadata_status === 'failed'}
                    <!-- TODO -->

                <!-- Metadata fetched for local file; display parent folder path, time since date added -->
                {:else if item_data.metadata_status === 'success'}

                    <!-- Parent folder file path -->
                    <p class="video-detail-text">
                        {#if item_data.uri}
                            {format_local_path(item_data.uri)}
                        {:else}
                            Local file - couldn't be found
                        {/if}
                    </p>

                {/if}

            <!-- YouTube Media Items -->
            {:else if item_data.source === 'youtube'}

                <!-- Placeholder animation if still fetching YouTube metadata -->
                {#if item_data.metadata_status === 'pending'}
                    <div class="loading-text-placeholder title-placeholder loading-animation"></div>
                    <div class="loading-text-placeholder channel-placeholder loading-animation"></div>
                    <div class="loading-text-placeholder date-placeholder loading-animation"></div>

                <!-- YouTube metadata fetch failed -->
                {:else if item_data.metadata_status === 'failed'}
                    <a class="media-title" href="{`/id/${item_data.id}`}">{`https://www.youtube.com/watch?v=${item_data.uri}`}</a>
                    <p class="video-detail-text">Metadata fetch failed</p>

                <!-- YouTube metadata fetched; display title, channel, time since date added -->
                {:else if item_data.metadata_status === 'success'}
                <a class="media-title" href="{`/id/${item_data.id}`}">{item_data.title}</a>
                    <p class="video-detail-text">{item_data.channel}</p>
                {/if}

            {/if}

            <!-- Processing -->
            {#if item_data.status === 'processing'}
                <p class="video-detail-text processing-text">
                    {#if active_job_status}
                        {active_job_status.stage}
                        {#if active_job_status.stage === 'Downloading audio' && active_job_status.progress !== undefined}
                            ({active_job_status.progress.toFixed(2)}%)
                        {/if}
                    {:else}
                        Starting...
                    {/if}
                </p>

            <!-- Queued -->
            {:else if item_data.status === 'queued'}
                {#if processor_status === 'loading'}
                    <p class="video-detail-text queued-text">Loading processor...</p>
                {:else if processor_status === 'warming up'}
                    <p class="video-detail-text queued-text">Processor warming up...</p>
                {:else if item_data.metadata_status !== 'pending'}
                    <p class="video-detail-text queued-text">Queued</p>
                {/if}

            <!-- Failed -->
            {:else if item_data.status === 'failed'}
                <p class="video-detail-text error-text">Failed to process</p>
                {#if item_data.error}
                    <p class="video-detail-text error-message">
                        {#if item_data.error.type === 'age_restricted'}
                            Age restricted video
                            {#await get_setting('cookies_from_browser') then cookies_setting}
                                {#if !cookies_setting}
                                    <a href="/settings?highlight=cookies_from_browser" style="color: var(--accent)">[Fix]</a>
                                {/if}
                            {/await}
                        {:else if item_data.error.type === 'bot'}
                            YouTube bot guard trigerred
                            {#await get_setting('cookies_from_browser') then cookies_setting}
                                {#if !cookies_setting}
                                    <a href="/settings?highlight=cookies_from_browser" style="color: var(--accent)">[Fix]</a>
                                {/if}
                            {/await}
                        {:else}
                            Error: {item_data.error.full_str}
                        {/if}
                    </p>
                {/if}

            <!-- Processed successfully -->
            {:else if item_data.status === 'success'}
                <p class="video-detail-text" style="margin-left: -1px">Added {format_timestamp(item_data.finished_t)}</p>
            {/if}

        </div>

        <!--
        =========================================================
            Buttons
        =========================================================
        -->

        <div class="buttons-container">
            <!-- Delete button -->
            {#if item_data.status !== 'processing'}
                {#if !delete_confirmation}
                    <button class="cs-btn delete-btn" onclick={() => { delete_confirmation = true }}>X</button>
                {:else}
                    <button class="cs-btn delete-btn" onclick={async () => {
                        const delete_success = await delete_media_item([item_data.id]);
                        if (delete_success) {
                            setTimeout(() => {
                                invalidateAll();
                            }, 100);
                        }
                        delete_confirmation = false;
                    }}>✔</button>
                {/if}
            {/if}

            <!-- Retry buttons -->

            {#if !item_data.error || (item_data.error && item_data.error.type !== 'no_speakers')}

                <!-- If metadata AND processing failed -->
                {#if item_data.status === 'failed' && item_data.metadata_status === 'failed'}
                    <button class="cs-btn" onclick={() => {
                        retry_processing(item_data.id, ['metadata_refetch', 'processing_retry']);
                    }}>Retry</button>
                {/if}

                <!-- If only processing failed -->
                {#if item_data.status === 'failed' && item_data.metadata_status !== 'failed'}
                    <button class="cs-btn" onclick={() => {
                        retry_processing(item_data.id, ['processing_retry']);
                    }}>Retry</button>
                {/if}

                <!-- If only metadata failed -->
                {#if item_data.status !== 'failed' && item_data.metadata_status === 'failed'}
                    <button class="cs-btn" onclick={() => {
                        retry_processing(item_data.id, ['metadata_refetch']);
                    }}>Retry Metadata Fetch</button>
                {/if}

            {/if}

        </div>

    </div>

</main>

<style>

    /*
    =========================================================
        Top Level div
    =========================================================
    */

    .media-item {
        display: flex;
        flex-wrap: wrap;
        position: relative;
    }

    /*
    =========================================================
        Thumbnail
    =========================================================
    */

    .thumbnail-loading {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: var(--bg);
    }

    .thumbnail-container {
        position: relative;
        width: 150px;
        min-width: 200px;
        margin-right: 8px;
        border: 1px solid var(--border-light);
        border-right-color: var(--border-dark);
        border-bottom-color: var(--border-dark);
        box-sizing: content-box;
        padding: 1px; /* border created using padding */
        background-color: var(--bg); /* created border will have this color */
    }

    .thumbnail-container a {
        display: block;
        position: relative;
        width: 100%;
        height: 0;
        padding-bottom: 56.25%; /* 16:9 aspect ratio */
        overflow: hidden;
        border: 1px solid var(--border-dark);
        border-right-color: var(--border-light);
        border-bottom-color: var(--border-light);
    }

    .audio-thumbnail {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: #45513d;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .audio-icon {
        width: 60px;
        height: 60px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='12' viewBox='0 0 14 12'%3E%3Cpath d='M0,4 1,4 1,8 0,8 M1,4 2,4 2,8 1,8 M2,3 3,3 3,9 2,9 M3,2 4,2 4,10 3,10 M4,1 5,1 5,11 4,11 M7,3 8,3 8,4 7,4 M8,4 9,4 9,5 8,5 M9,5 10,5 10,7 9,7 M8,7 9,7 9,8 8,8 M7,8 8,8 8,9 7,9 M10,2 11,2 11,3 10,3 M11,3 12,3 12,4 11,4 M12,4 13,4 13,8 12,8 M11,8 12,8 12,9 11,9 M10,9 11,9 11,10 10,10' fill='%23c4b550'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: center;
        background-size: 60px 60px; /* Scale it up to match the emoji size */
        margin-right: -2px;
    }

    .thumbnail-container img {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    /*
    =========================================================
        Placeholder Thumbnail
    =========================================================
    */

    .placeholder-thumbnail {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: #000;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .no-thumbnail-text {
        color: #808080;
        font-size: 14px;
        text-align: center;
    }

    /*
    =========================================================
        Duration Badge
    =========================================================
    */

    .duration-badge {
        position: absolute;
        bottom: 0px;
        right: 0px;
        background-color: rgba(0, 0, 0, 0.8);
        color: var(--text);
        font-size: 12px;
        padding: 2px 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
    }

    /*
    =========================================================
        Media Details (Loading)
    =========================================================
    */

    .loading-text-placeholder {
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        margin-bottom: 8px;
    }

    .title-placeholder {
        height: 18px;
        width: 95%;
    }

    .channel-placeholder {
        height: 14px;
        width: 70%;
    }

    .date-placeholder {
        height: 14px;
        width: 50%;
    }

    .loading-animation {
        position: relative;
        overflow: hidden;
    }

    .loading-animation::after {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 50%;
        height: 100%;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.2),
            transparent
        );
        animation: loading-shimmer 1.5s infinite;
    }

    @keyframes loading-shimmer {
        0% {
            left: -100%;
        }
        100% {
            left: 100%;
        }
    }

    /*
    =========================================================
        Media Details
    =========================================================
    */

    .media-details {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        flex-basis: 0;
        min-width: 100px;
        margin-top: 1px;
    }

    .media-title {
        color: var(--text);
        font-size: 16px;
        line-height: 1.2;
        text-decoration: none;
        margin-bottom: 8px;
    }

    .media-title:hover {
        color: var(--accent);
    }

    .video-detail-text {
        font-size: 14px;
        color: var(--text-3);
    }

    .buttons-container {
        display: flex;
        flex-direction: row-reverse;
        gap: 8px;
        align-items: center;
        margin-left: auto;
        opacity: 0;
        align-self: flex-start;
        padding-left: 10px;
    }

    .media-item:hover .buttons-container {
        opacity: 1;
    }

    .error-text {
        color: #ff6b6b;
        font-weight: 500;
    }

    .processing-text {
        color: #e8c200;
        font-weight: 500;
    }

    .queued-text {
        color: #bebebe;
        font-weight: 500;
    }

    .error-message {
        color: #ff6b6b;
        font-size: 12px;
        max-width: 400px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

</style>
