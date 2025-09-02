<script>

    import Panel from './Panel.svelte';
    import { format_duration } from '$lib/misc.js';
    import { createEventDispatcher } from 'svelte';
    import { onDestroy } from 'svelte';
    import { afterNavigate } from '$app/navigation';
    import { set_auto_skip_disabled_speakers, get_setting, set_skip_silences } from '$lib/api.js';

    const dispatch = createEventDispatcher();

    /*
    =========================================================
        I/O
    =========================================================
    */

    let {
       id,
       merged_segments,
       speaker_color_sets,
       selected_colorset_num = $bindable(),
       duration,
       speaker_visibility = $bindable(),
       speaker_speeds = $bindable(),
       is_speaker_visible,
       switch_colorset_func,
       reset_colorset_func,
       padding_right = null,
       skip_silences = $bindable(),
       auto_skip_disabled_speakers = $bindable(),
       chapters_exist,
       current_time,
       hovered_speaker = $bindable(),
       hovered_speaker_from_panel = $bindable(),
       dragging = false
    } = $props();

    /*
    =========================================================
        Hover Grace Period
    =========================================================
    */

    let hover_enter_timeout = null;
    let hover_grace_timeout = null;

    /*
    =========================================================
        Speaker Stats
    =========================================================
    */

    const speaker_stats = $derived.by(() => {
        if (!merged_segments) return [];
        const segments = merged_segments;
        const color_set = speaker_color_sets[selected_colorset_num];
        const total_duration = duration;

        const speaker_times = {};
        segments.forEach(segment => {
            const duration = segment.end - segment.start;
            if (speaker_times[segment.speaker]) {
                speaker_times[segment.speaker] += duration;
            } else {
                speaker_times[segment.speaker] = duration;
            }
        });

        const sorted_speakers = Object.entries(speaker_times)
            .map(([speaker, total_time]) => ({
                name: speaker,
                totalTime: total_time,
                color: color_set[speaker] || '#666666',
                formattedTime: format_duration(total_time),
                percentage: total_duration ? ((total_time / total_duration) * 100).toFixed(1) : null
            }))
            .sort((a, b) => b.totalTime - a.totalTime);

        return sorted_speakers;
    });

    function get_visible_speaker_count() {
        return Object.values(speaker_visibility).filter(visible => visible).length;
    }

    /*
    =========================================================
        Color Sqaure
    =========================================================
    */

    function handle_color_square_click(speakerName) {
        if (is_speaker_visible(speakerName)) {
            dispatch('seek_to_next_speaker_segment', speakerName);
        }
    }

    function handle_color_square_right_click(event, speakerName) {
        event.preventDefault();
        isolate_speaker(speakerName);
    }

    function isolate_speaker(speakerName) {
        if (speaker_visibility && merged_segments) {
            const allSpeakers = [...new Set(merged_segments.map(seg => seg.speaker))];
            allSpeakers.forEach(speaker => {
                speaker_visibility[speaker] = speaker === speakerName;
            });
        }
    }

    // Helper function to determine if a speaker should be highlighted
    function isHighlightedSpeaker(speakerName) {
        // Only highlight if the speaker is visible
        // if (!is_speaker_visible(speakerName)) {
        //     return false;
        // }

        // If we have a hovered speaker (and it's not false for silence) and not dragging, highlight that one
        if (!dragging && hovered_speaker && hovered_speaker !== false) {
            return speakerName === hovered_speaker;
        }

        // Otherwise, find the current speaker at current_time (only if hovered_speaker is null/false, or if dragging)
        if ((hovered_speaker === false || hovered_speaker === null || dragging) && current_time && merged_segments) {
            const current_segment = merged_segments.find(segment =>
                current_time >= segment.start && current_time < segment.end
            );
            return current_segment && speakerName === current_segment.speaker;
        }

        return false;
    }

    /*
    =========================================================
        Speaker Speeds
    =========================================================
    */

    let speeds_visible = $state(false);

    // Check if any speaker has non-default speed (not 1.0)
    const hasCustomSpeeds = $derived(() => {
        if (!speaker_speeds) return false;
        return Object.values(speaker_speeds).some(speed => speed !== 1.0);
    });

    // Initialize speeds visibility based on whether there are custom speeds
    $effect(() => {
        if (speaker_speeds && Object.keys(speaker_speeds).length > 0) {
            speeds_visible = hasCustomSpeeds();
        }
    });

    $effect(() => {
        if (!speeds_visible) {
            // set all speeds to 1.0
            if (speaker_speeds) {
                Object.keys(speaker_speeds).forEach(speaker => {
                    speaker_speeds[speaker] = 1.0;
                });
            }
        }
    });

    /*
    =========================================================
        Grid Layout
    =========================================================
    */

    /*
        Grid Layout Logic:

        - 1-5 speakers: Single column (no grid)
        - 6-10 speakers: 2 columns, max 5 speakers per column
        - 11-15 speakers: 3 columns, max 5 speakers per column
        - 16-20 speakers: 4 columns, max 5 speakers per column
        - 21+ speakers: 6 columns, expand rows as needed

        Grid fills column-first: items 1,2,3... in first column, then 4,5,6... in second column, and so on
    */

    const grid_config = $derived.by(() => {
        const count = speaker_stats.length;

        if (count <= 5) {
            return { columns: 1, rows: count };
        } else if (count <= 10) {
            return { columns: 2, rows: 5 };
        } else if (count <= 15) {
            return { columns: 3, rows: 5 };
        } else if (count <= 20) {
            return { columns: 4, rows: 5 };
        } else {
            return { columns: 6, rows: Math.ceil(count / 6) };
        }
    });

    /*
    =========================================================
        Speaker Percentages Width
    =========================================================
    */

    // Remove this line:
    // let percentageElements = [];

    // Replace the entire afterNavigate block with this derived value:
    const columnMaxWidths = $derived.by(() => {
        const columns = grid_config.columns;
        const rows = grid_config.rows;
        const maxWidths = new Array(columns).fill(0);

        speaker_stats.forEach((speaker, index) => {
            const col = Math.floor(index / rows);
            if (speaker.percentage) {
                // Estimate width based on percentage string length with logarithmic scaling
                const percentText = speaker.percentage + '%';
                const charCount = percentText.length;
                // Logarithmic scaling: more boost for fewer chars, tapers off for more
                const logWidth = Math.log(charCount + 1)*1.05 + 1; // Adjust multipliers as needed
                if (logWidth > maxWidths[col]) {
                    maxWidths[col] = logWidth;
                }
            }
        });

        return maxWidths;
    });

    // Helper function to get the estimated width for a speaker
    function getPercentageWidth(speakerIndex) {
        const col = Math.floor(speakerIndex / grid_config.rows);
        const maxLogWidth = columnMaxWidths[col];
        return `${maxLogWidth}em`;
    }


    onDestroy(() => {
        // Clean up hover grace timeout
        if (hover_grace_timeout) {
            clearTimeout(hover_grace_timeout);
        }
        // Clean up hover enter timeout
        if (hover_enter_timeout) {
            clearTimeout(hover_enter_timeout);
        }
    });

    /*
    =========================================================
        Buttons
    =========================================================
    */

    function areAllSpeakersVisible() {
        if (!merged_segments) return true;
        const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
        return speakers.every(speaker => is_speaker_visible(speaker));
    }

    function resetSpeakers() {
        if (speaker_visibility && merged_segments) {
            const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
            speakers.forEach(speaker => {
                speaker_visibility[speaker] = true;
            });
            speaker_visibility = { ...speaker_visibility }; // Force reactivity
        }
    }

    function hasDisabledSpeakers() {
        if (!speaker_visibility || !merged_segments) return false;
        const speakers = [...new Set(merged_segments.map(seg => seg.speaker))];
        return speakers.some(speaker => !is_speaker_visible(speaker));
    }

    // Track when we transition from no disabled speakers to having disabled speakers and set the default auto-skip value based on the user's setting
    let previous_has_disabled_speakers = false;
    $effect(() => {
        const current_has_disabled_speakers = hasDisabledSpeakers();
        // If we're transitioning from no disabled speakers to having disabled speakers
        if (!previous_has_disabled_speakers && current_has_disabled_speakers) {
            // Check if this is the first time - indicated by null value from database
            if (auto_skip_disabled_speakers === null || auto_skip_disabled_speakers === undefined) {
                get_setting('auto_skip_by_default').then(setting_value => {
                    // Apply the user's default setting preference
                    const new_value = setting_value !== false; // Default to true if setting is null/undefined
                    auto_skip_disabled_speakers = new_value;
                    set_auto_skip_disabled_speakers(id, new_value); // Save the newly applied default

                    // Now that the setting has been applied, handle any needed position adjustment
                    dispatch('auto_skip_setting_applied');
                });
            }
        }
        previous_has_disabled_speakers = current_has_disabled_speakers;
    });

    let autoSkipButtonStyle = $derived(`width: 24px; height: 24px; margin-right: -2px; background-image: url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2716%27 height=%2716%27 viewBox=%270 0 16 16%27%3E%3Cpath d=%27M3,4 3,12 8,8 M8,4 8,12 13,8%27 fill=%27${auto_skip_disabled_speakers !== false && auto_skip_disabled_speakers !== 0 ? '%23bcab4d' : '%23888888'}%27/%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: center; border: none; background-color: transparent; cursor: pointer;`);

</script>

<main>

    <Panel header_text={'Speakers'} {padding_right}>

        {#snippet header_right_content()}
            {#if hasDisabledSpeakers()}
                <button
                    class="auto-skip-btn"
                    style={autoSkipButtonStyle}
                    onclick={(e) => {
                        const new_value = (auto_skip_disabled_speakers === false || auto_skip_disabled_speakers === 0) ? true : false;
                        auto_skip_disabled_speakers = new_value;
                        e.target.blur();
                        set_auto_skip_disabled_speakers(id, new_value);
                    }}
                    title="Auto-skip unchecked speakers"
                >
                </button>
            {/if}
        {/snippet}

        <div class="toplevel-container" style="padding-top: {speeds_visible && grid_config.columns > 1 ? '1' : '0'}px;">

            <div class="speakers-container"
                style="gap: 2px {speeds_visible ? '8' : '4'}px;"
                style:grid-template-columns={`repeat(${grid_config.columns}, 1fr)`}
                style:grid-template-rows={`repeat(${grid_config.rows}, auto)`}>

                {#each speaker_stats as speaker, index}
                    <div class="speaker" class:second-column={Math.floor(index / grid_config.rows) === 1}>
                        <!--
                        =========================================================
                            Checkbox
                        =========================================================
                        -->

                        <!-- svelte-ignore a11y_no_static_element_interactions -->
                        <div class="cs-checkbox" oncontextmenu={(event) => handle_color_square_right_click(event, speaker.name)}>
                            <input id="checkbox-{speaker.name}" type="checkbox" checked={is_speaker_visible(speaker.name)} disabled={is_speaker_visible(speaker.name) && get_visible_speaker_count() === 1}
                                onchange={(e) => {
                                    if (speaker_visibility) {
                                        speaker_visibility[speaker.name] = e.target.checked;
                                        speaker_visibility = { ...speaker_visibility }; // Force reactivity by creating new object
                                    }
                                    // Auto-blur to restore keyboard shortcuts
                                    e.target.blur();
                                }}
                            />
                          <label class="cs-checkbox__label" for="checkbox-{speaker.name}"></label>
                        </div>

                        <div class="speaker-inner">

                            <!--
                            =========================================================
                                Speaker Color Square
                            =========================================================
                            -->

                            <!-- svelte-ignore a11y_click_events_have_key_events -->
                            <!-- svelte-ignore a11y_no_static_element_interactions -->
                            <svg
                                class="speaker-color-square"
                                class:clickable={is_speaker_visible(speaker.name)}
                                class:highlighted={isHighlightedSpeaker(speaker.name)}
                                width="20"
                                height="20"
                                viewBox="0 0 20 20"
                                onclick={() => handle_color_square_click(speaker.name)}
                                oncontextmenu={(event) => handle_color_square_right_click(event, speaker.name)}
                                onmouseenter={() => {
                                    // Don't trigger hover effects during dragging
                                    if (dragging) return;

                                    // Clear any pending grace period timeout
                                    if (hover_grace_timeout) {
                                        clearTimeout(hover_grace_timeout);
                                        hover_grace_timeout = null;
                                    }

                                    // Clear any existing hover enter timeout
                                    if (hover_enter_timeout) {
                                        clearTimeout(hover_enter_timeout);
                                        hover_enter_timeout = null;
                                    }

                                    // Set a timeout to activate hover after 1 second
                                    if (is_speaker_visible(speaker.name)) {
                                        hover_enter_timeout = setTimeout(() => {
                                            hovered_speaker_from_panel = speaker.name;
                                            hover_enter_timeout = null;
                                        }, 250); // 0.25 second delay
                                    }
                                }}
                                onmouseleave={() => {
                                    // Don't trigger hover effects during dragging
                                    if (dragging) return;

                                    // Clear the hover enter timeout if mouse leaves before 1 second
                                    if (hover_enter_timeout) {
                                        clearTimeout(hover_enter_timeout);
                                        hover_enter_timeout = null;
                                    }

                                    // Clear any existing grace period timeout first
                                    if (hover_grace_timeout) {
                                        clearTimeout(hover_grace_timeout);
                                        hover_grace_timeout = null;
                                    }

                                    // Set a grace period before clearing hover state
                                    // This now handles both the current speaker and any stuck speaker
                                    if (hovered_speaker_from_panel !== null) {
                                        hover_grace_timeout = setTimeout(() => {
                                            hovered_speaker_from_panel = null;
                                            hover_grace_timeout = null;
                                        }, 150); // 150ms grace period
                                    }
                                }}>
                                <!-- Inner color square -->
                                <rect
                                    x="2"
                                    y="2"
                                    width="16"
                                    height="16"
                                    fill={speaker.color}
                                />
                                <!-- Outline with gap -->
                                <rect
                                    class="speaker-outline"
                                    x="0.5"
                                    y="0.5"
                                    width="19"
                                    height="19"
                                    fill="none"
                                    stroke="#ac9d39"
                                    stroke-width="1"
                                />
                            </svg>

                            <!--
                            =========================================================
                                Speaker Percentage / Duration
                            =========================================================
                            -->

                            <!-- svelte-ignore a11y_no_static_element_interactions -->
                            <!-- svelte-ignore a11y_mouse_events_have_key_events -->
                            <!-- svelte-ignore a11y_click_events_have_key_events -->
                            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                            <p
                                class="speaker-percentage"
                                style="width: {getPercentageWidth(speaker_stats.indexOf(speaker))}; {speeds_visible || grid_config.columns === 1 ? 'margin-right: -5px;' : ''}"
                                onclick={(e) => {
                                    if (speaker.percentage) {
                                        // Clear any existing timeout
                                        if (e.target.resetTimeout) {
                                            clearTimeout(e.target.resetTimeout);
                                            e.target.resetTimeout = null;
                                        }
                                        if (e.target.dataset.showingTime === 'true') {
                                            // Currently showing time, switch back to percentage
                                            e.target.textContent = speaker.percentage + '%';
                                            e.target.dataset.showingTime = 'false';
                                        } else {
                                            // Currently showing percentage, switch to time
                                            e.target.textContent = `[${speaker.formattedTime}]`;
                                            e.target.dataset.showingTime = 'true';
                                        }
                                    }
                                }}
                                onmouseleave={(e) => {
                                    if (e.target.dataset.showingTime === 'true') {
                                        e.target.resetTimeout = setTimeout(() => {
                                            if (e.target.dataset.showingTime === 'true') {
                                                e.target.textContent = speaker.percentage + '%';
                                                e.target.dataset.showingTime = 'false';
                                            }
                                        }, 1500);
                                    }
                                }}
                                onmouseenter={(e) => {
                                    // Cancel any pending reset when mouse re-enters
                                    if (e.target.resetTimeout) {
                                        clearTimeout(e.target.resetTimeout);
                                        e.target.resetTimeout = null;
                                    }
                                }}
                            >
                                {#if speaker.percentage}
                                    {speaker.percentage}%
                                {/if}
                            </p>

                            <!--
                            =========================================================
                                Speed Dropdown Select
                            =========================================================
                            -->

                            <select
                                class="cs-select speed-dropdown"
                                style={grid_config.columns === 1
                                    ? `visibility: ${speeds_visible && (is_speaker_visible(speaker.name) || !auto_skip_disabled_speakers) ? 'visible' : 'hidden'};`
                                    : `display: ${speeds_visible ? 'block' : 'none'}; visibility: ${is_speaker_visible(speaker.name) || !auto_skip_disabled_speakers ? 'visible' : 'hidden'};`
                                }
                                bind:value={speaker_speeds[speaker.name]}
                                onchange={(e) => e.target.blur()}
                            >
                                <option value={0.25}>0.25x</option>
                                <option value={0.5}>0.5x</option>
                                <option value={0.75}>0.75x</option>
                                <option value={1.0}>1.0x</option>
                                <option value={1.25}>1.25x</option>
                                <option value={1.5}>1.5x</option>
                                <option value={1.75}>1.75x</option>
                                <option value={2.0}>2.0x</option>
                            </select>

                        </div> <!-- speaker-inner -->

                    </div> <!-- speaker -->
                {/each}

            </div> <!-- speakers-container -->

            <div class="buttons-container" class:compact={grid_config.columns <= 2}>
                <button
                  class="cs-btn switch-colors-btn"
                  style="color: var(--text); white-space: nowrap;"
                  onclick={(e) => {
                      switch_colorset_func();
                      e.target.blur();
                  }}
                  oncontextmenu={(e) => {
                      e.preventDefault();
                      reset_colorset_func();
                      e.target.blur();
                  }}
                >Change Colors</button>

                <div class="bottom-buttons">
                    <button
                        class="cs-btn"
                        style="color: {speeds_visible ? '#bcab4d' : 'var(--text)'}; white-space: nowrap;"
                        onclick={(e) => { speeds_visible = !speeds_visible; e.target.blur(); }}
                    >
                        Speeds
                    </button>

                    <button
                        class="cs-btn"
                        style="color: {skip_silences ? '#bcab4d' : 'var(--text)'}; white-space: nowrap;"
                        onclick={(e) => { skip_silences = !skip_silences; e.target.blur(); set_skip_silences(id, skip_silences); }}
                    >
                        Skip Silences
                    </button>
                </div>
            </div>


        </div> <!-- toplevel-container -->

    </Panel>


</main>

<style>
    .toplevel-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-bottom: 5px;
    }

    .speakers-container {
        display: grid;
        grid-auto-flow: column;
    }

    .speaker {
        display: flex;
        align-items: center;
        justify-self: start; /* Default for first, third, fourth+ columns */
    }

    .speaker.second-column {
        justify-self: center; /* Only second column */
    }

    .speaker-inner {
        display: flex;
        align-items: center;
        gap: 5px; /* Adjusted for the 20px SVG */
    }

    .speaker-color-square {
        width: 20px;
        height: 20px;
        position: relative;
        display: block;
        margin-left: -1px;
    }

    .speaker-color-square.clickable {
        cursor: pointer;
    }

    .speaker-color-square .speaker-outline {
        opacity: 0;
        transition: opacity 0.35s ease;
    }

    .speaker-color-square.highlighted .speaker-outline {
        opacity: 1;
    }

    .speaker-percentage {
        color: var(--text-3);
        font-size: 0.85em;
        cursor: pointer;
        white-space: nowrap;
        user-select: none;
    }

    .speed-dropdown {
        min-width: 70px;
        max-width: 70px;
        height: 25px;
    }

    .buttons-container {
        display: flex;
        gap: 8px;
    }

    .buttons-container.compact {
        flex-direction: column;
    }

    .buttons-container.compact .switch-colors-btn {
        width: 100%;
    }

    .bottom-buttons {
        display: flex;
        gap: 8px;
    }

    .buttons-container.compact .bottom-buttons button {
        width: 100%;
    }

    .buttons-container:not(.compact) {
        flex-direction: row;
    }

    .buttons-container:not(.compact) .switch-colors-btn,
    .buttons-container:not(.compact) .bottom-buttons button {
        width: 100%;
    }

    .buttons-container:not(.compact) .bottom-buttons {
        display: contents;
    }
</style>