export function cursor_auto_hide(node, options = {}) {
    const {
        delay = 5000,
        is_playing = false
    } = options;

    let hide_timeout = null;
    let last_position = { x: 0, y: 0 };
    let cursor_hidden = false;

    function set_cursor_visibility(hidden) {
        cursor_hidden = hidden;
        node.style.cursor = hidden ? 'none' : 'default';
    }

    function clear_timeout() {
        if (hide_timeout) {
            clearTimeout(hide_timeout);
            hide_timeout = null;
        }
    }

    function start_hide_timer() {
        clear_timeout();
        if (options.is_playing) {
            hide_timeout = setTimeout(() => {
                set_cursor_visibility(true);
                hide_timeout = null;
            }, delay);
        }
    }

    function handle_mouse_move(event) {
        const current_position = { x: event.clientX, y: event.clientY };

        if (current_position.x !== last_position.x || current_position.y !== last_position.y) {
            last_position = current_position;
            set_cursor_visibility(false);
            start_hide_timer();
        }
    }

    function handle_mouse_enter(event) {
        last_position = { x: event.clientX, y: event.clientY };
        set_cursor_visibility(false);
        start_hide_timer();
    }

    function handle_mouse_leave() {
        set_cursor_visibility(false);
        clear_timeout();
    }

    node.addEventListener('mousemove', handle_mouse_move);
    node.addEventListener('mouseenter', handle_mouse_enter);
    node.addEventListener('mouseleave', handle_mouse_leave);

    return {
        update(new_options) {
            options = { ...options, ...new_options };

            if (options.is_playing) {
                if (!cursor_hidden && !hide_timeout) {
                    start_hide_timer();
                }
            } else {
                set_cursor_visibility(false);
                clear_timeout();
            }
        },
        destroy() {
            clear_timeout();
            node.removeEventListener('mousemove', handle_mouse_move);
            node.removeEventListener('mouseenter', handle_mouse_enter);
            node.removeEventListener('mouseleave', handle_mouse_leave);
        }
    };
}