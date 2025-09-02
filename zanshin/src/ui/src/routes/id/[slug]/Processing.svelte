<script>
    import { get_setting } from '$lib/api';
    import { format_duration, format_youtube_date, format_local_path, format_timestamp } from '$lib/misc';
    import ProgressBar from '$lib/ProgressBar.svelte';

    const { item_data, active_job_status, processor_status } = $props();
</script>

<main>
    <div class="container">
        <div class="processing-modal">
            <!--
            =========================================================
                Title Section
            =========================================================
            -->
            <div class="title">
                {#if item_data.source === 'local'}
                    <!-- Local files: always show the title (filename) -->
                    <p class="truncate-text">{item_data.title}</p>
                {:else if item_data.source === 'youtube'}
                    <!-- YouTube: show URL until metadata is fetched, then show title -->
                    {#if item_data.metadata_status === 'success'}
                        <a class="truncate-text" href="https://www.youtube.com/watch?v={item_data.uri}">{item_data.title}</a>
                    {:else}
                        <a class="truncate-text" href="https://www.youtube.com/watch?v={item_data.uri}">https://www.youtube.com/watch?v={item_data.uri}</a>
                    {/if}
                {/if}
            </div>

            <!--
            =========================================================
                Thumbnail
            =========================================================
            -->
            <div class="thumbnail-container">
                <!-- Metadata fetched -->
                {#if item_data.metadata_status === 'success'}
                    <!-- If thumbnail exists -->
                    {#if item_data.thumbnail_exists}
                        <img src={`/api/thumbnail/${item_data.id}`} alt={item_data.title} />

                    <!-- If doesn't exist and media type is audio, render audio placeholder icon -->
                    {:else if item_data.media_type === 'audio'}
                        <div class="audio-thumbnail">
                            <div class="audio-icon">🎵</div>
                        </div>

                    <!-- Thumbnail not available text -->
                    {:else}
                        <div class="placeholder-thumbnail">
                            <span class="no-thumbnail-text">Thumbnail not available</span>
                        </div>
                    {/if}

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

                <!-- Overlay with media details -->
                {#if item_data.metadata_status === 'success'}
                    <div class="title-overlay">
                        {#if item_data.source === 'youtube'}
                            <p class="overlay-title truncate-text">{item_data.channel}</p>
                            <p class="overlay-details">{format_youtube_date(item_data.date_uploaded)} • {format_duration(item_data.duration)}</p>
                        {:else if item_data.source === 'local'}
                            <p class="overlay-title truncate-text">{format_local_path(item_data.uri)}</p>
                        {/if}
                    </div>
                {/if}
            </div>

            <!--
            =========================================================
                Progress Container with Status Displays
            =========================================================
            -->
            <div class="progress-container">
                <!-- Processing -->
                {#if item_data.status === 'processing'}
                    <p>
                        {#if active_job_status}
                            {active_job_status.stage}
                            {#if active_job_status.stage === 'Downloading audio' && active_job_status.progress !== undefined}
                                ({active_job_status.progress.toFixed(2)}%)
                            {/if}
                        {:else}
                            Starting...
                        {/if}
                    </p>
                    <div class="progress-bar-and-cancel">
                        {#if active_job_status?.progress != null}
                            <ProgressBar percentage={active_job_status.progress}/>
                        {:else}
                            <ProgressBar side_to_side={true}/>
                        {/if}
                        <button class="cs-btn" onclick={alert("Cancelling running jobs is not supported yet. Quit Zanshin to cancel this current job.")}>Cancel</button>
                    </div>

                <!-- Queued -->
                {:else if item_data.status === 'queued'}
                    {#if processor_status === 'loading'}
                        <p class="queued-text">Loading processor...</p>
                    {:else if processor_status === 'warming up'}
                        <p class="video-detail-text queued-text">Processor warming up...</p>
                    {:else}
                        <p class="queued-text">Queued</p>
                    {/if}

                <!-- Failed -->
                {:else if item_data.status === 'failed'}
                    <p class="error-text">Failed to process</p>
                    {#if item_data.error}
                        <p class="error-message">
                            {#if item_data.error.type === 'age_restricted'}
                                Age restricted video
                                {#await get_setting('cookies_from_browser') then cookies_setting}
                                    {#if !cookies_setting}
                                        <a href="/settings?highlight=cookies_from_browser" style="color: var(--accent)">[Fix]</a>
                                    {/if}
                                {/await}
                            {:else if item_data.error.type === 'bot'}
                                YouTube bot guard triggered
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
                    <p>Added {format_timestamp(item_data.finished_t)}</p>
                {/if}
            </div>
        </div>
    </div>
</main>

<style>
    .container {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .processing-modal {
        width: 650px;
        border: solid 1px;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        display: flex;
        flex-direction: column;
        background-color: var(--bg);
    }

    .title {
        display: flex;
        align-items: center;
        padding: 5px 5px 3px 7px;
        border-bottom: 1px solid var(--border-dark);
        height: 25px;
    }

    .truncate-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
        margin: 0;
        text-decoration: none;
        color: var(--text);
    }

    .thumbnail-container {
        margin: 8px;
        border: solid 1px;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
        position: relative;
        width: calc(100% - 16px); /* Account for margin */
        height: 0;
        padding-bottom: 56.25%; /* 16:9 aspect ratio */
    }

    .thumbnail-container img {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        filter: sepia(0.9);
    }

    .audio-thumbnail {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: var(--secondary-bg);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .audio-icon {
        font-size: 48px;
        color: var(--text);
    }

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

    .thumbnail-loading {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: var(--secondary-bg);
    }

    .title-overlay {
        position: absolute;
        bottom: 10px;
        right: 10px;
        background-color: var(--accent);
        /* opacity: 0.85; */
        padding: 8px;
        max-width: 400px;
        border: 1px solid var(--border-dark);
    }

    .overlay-title {
        color: #292c21;
        font-size: 14px;
        line-height: 1.2;
        margin: 0;
        margin-bottom: 3px;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }

    .overlay-details {
        color: #292c21;
        font-size: 12px;
        line-height: 1.2;
        margin: 0;
    }

    .progress-container {
        margin: 10px;
        margin-top: -2px;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .progress-container p {
        padding-left: 3px;
        margin: 0;
    }

    .progress-bar-and-cancel {
        display: flex;
        gap: 8px;
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
