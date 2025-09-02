<script>

    let { header_text, padding_left = null, padding_right = null, margin_right = null, header_right_content = null, children } = $props();

    const padding_left_str = padding_left ? `padding-left: ${padding_left}` : '';
    const padding_right_str = padding_right ? `padding-right: ${padding_right}` : '';
    const margin_right_str = margin_right ? `margin-right: ${margin_right}` : '';

</script>

<main>

    <div class="panel-container">
        <div class="header">
            <p>{header_text}</p>
            {#if header_right_content}
                <div class="header-right">
                    {@render header_right_content()}
                </div>
            {/if}
        </div>
        <div class="inner" style="{padding_left_str}; {padding_right_str}; {margin_right_str};">
            {@render children()}
        </div>
    </div>

</main>

<style>

    .panel-container {
        background-color: var(--bg);
        border: 1px solid;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        display: flex;
        flex-direction: column;
    }

    .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 4px 4px 7px;
        border-bottom: 1px solid var(--border-dark);
        height: 25px;
        color: var(--text);
        font-size: 16px;
        user-select: none;
    }

    .header-right {
        display: flex;
        align-items: center;
    }

    .inner {
        padding: 6px 10px 6px 10px;
        overflow-y: auto;
        max-height: 220px;
    }

</style>