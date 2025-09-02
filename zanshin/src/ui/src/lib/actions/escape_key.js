import { browser } from '$app/environment';

export function escape_key(node, callback) {
    if (browser) {
        function handleKeydown(event) {
            if (event.key === 'Escape') {
                callback();
                event.preventDefault();
                // Remove focus from any focused element
                if (document.activeElement && document.activeElement.blur) {
                    document.activeElement.blur();
                }
            }
        }

        document.addEventListener('keydown', handleKeydown);

        return {
            destroy() {
                document.removeEventListener('keydown', handleKeydown);
            }
        };
    }
}