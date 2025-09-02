<script>

    import Panel from './Panel.svelte';
    import { createEventDispatcher } from 'svelte';

    /*
    =========================================================
        I/O
    =========================================================
    */

    const { chapters, current_time = 0, merged_segments, is_speaker_visible, padding_left = null, padding_right = null, dragging = $bindable() } = $props();
    const dispatch = createEventDispatcher();

    let chapters_container = $state();

    // Find the current active chapter based on current time
    const active_chapter_index = $derived.by(() => {
        for (let i = chapters.length - 1; i >= 0; i--) {
            if (current_time >= chapters[i].start_time) {
                return i;
            }
        }
        return 0; // Default to first chapter if no match
    });

    // Auto-scroll to center the active chapter
    $effect(() => {
        if (chapters_container && active_chapter_index !== undefined) {
            const chapter_elements = chapters_container.querySelectorAll('.chapter-title');
            const active_element = chapter_elements[active_chapter_index];

            if (active_element) {
                active_element.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                    inline: 'nearest'
                });
            }
        }
    });

    function seek_to_chapter(start_time) {
        dispatch('chapter_seek', start_time);
    }

    let chapter_elements = $state({});
    let truncation_states = $state({});

    function checkTruncation(element, text) {
        if (!element) return false;
        return element.scrollWidth > element.clientWidth;
    }

    export function updateTruncationStates() {
        const newStates = {};
        chapters.forEach((chapter, index) => {
            if (chapter_elements[index]) {
                newStates[index] = checkTruncation(chapter_elements[index], chapter.title);
            }
        });
        truncation_states = newStates;
    }

</script>

<main>
    <Panel header_text={'Chapters'} {padding_left} {padding_right}>
        <div bind:this={chapters_container}>
            {#each chapters as chapter, index}
                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <p
                    class="chapter-title"
                    class:dragging-disabled={dragging}
                    style="color: {index === active_chapter_index ? 'var(--accent)' : 'var(--text-3)'}; font-size: 0.95em; {dragging ? `user-select: none;`: ``}"
                    title={truncation_states[index] ? chapter.title : undefined}
                    bind:this={chapter_elements[index]}
                    onclick={(e) => { seek_to_chapter(chapter.start_time); e.target.blur(); }}
                >
                    {chapter.title}
                </p>
            {/each}
        </div>
    </Panel>
</main>

<style>
    .chapter-title {
        cursor: pointer;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding-left: 1px;
        /*transition: filter 0.1s ease-in-out;*/
    }

    .chapter-title:hover:not(.dragging-disabled) {
        filter: brightness(1.2);
    }
</style>