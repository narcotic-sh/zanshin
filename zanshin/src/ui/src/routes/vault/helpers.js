import { browser } from '$app/environment';

export function click_outside(element, callbackFunction) {
    if (browser) {
        function onClick(event) {
            // Don't close if clicked on the search element itself
            if (element.contains(event.target)) {
                return;
            }

            // Don't close if clicked on buttons, select elements, processed previews, or dialogs
            const isButton = event.target.classList.contains('cs-btn') ||
                            event.target.closest('.cs-btn');
            const isSelect = event.target.classList.contains('cs-select') ||
                            event.target.closest('.cs-select');
            const isFilterLabel = event.target.classList.contains('filter-label') ||
                                event.target.closest('.filter-label');
            const isProcessedPreviews = event.target.id === 'processed-previews' ||
                                    event.target.closest('#processed-previews');

            // Check for dialog components by their class names
            const isDialogBackdrop = event.target.classList.contains('dialog-backdrop') ||
                                event.target.closest('.dialog-backdrop');
            const isDialog = event.target.classList.contains('cs-dialog') ||
                        event.target.closest('.cs-dialog');
            const isDialogsContainer = event.target.classList.contains('dialogs-container') ||
                                    event.target.closest('.dialogs-container');

            if (isButton || isSelect || isFilterLabel || isProcessedPreviews ||
                isDialogBackdrop || isDialog || isDialogsContainer) {
                return;
            }

            callbackFunction();
        }

        document.body.addEventListener('click', onClick);

        return {
            update(newCallbackFunction) {
                callbackFunction = newCallbackFunction;
            },
            destroy() {
                document.body.removeEventListener('click', onClick);
            }
        }
    }
}