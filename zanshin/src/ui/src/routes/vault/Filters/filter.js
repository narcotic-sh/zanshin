export function apply_filters(success, filters, search_box_empty, search_box_value) {

    return success
        // Stage 1: Filter by source
        .filter(item => filters.source === 'all' || item.source === filters.source)

        // Stage 2: Filter by YouTube channel (only if applicable)
        .filter(item => {
            if (filters.source !== 'youtube' || filters.channel === 'all') return true;
            return item.channel === filters.channel;
        })

        // Stage 2.5: Filter by search term if provided
        .filter(item => {
            const trimmedSearch = search_box_value.trim();
            if (!trimmedSearch) return true; // If no search term, include all items

            // Case insensitive search in title
            return item.title && item.title.toLowerCase().includes(trimmedSearch.toLowerCase());
        })

        // Stage 3: Determine sort field based on filters
        .sort((a, b) => {
            // If search is active, prioritize best matches
            const trimmedSearch = search_box_value.trim();
            if (trimmedSearch) {
                const aTitle = (a.title || '').toLowerCase();
                const bTitle = (b.title || '').toLowerCase();
                const searchLower = trimmedSearch.toLowerCase();

                // If one title starts with the search term and the other doesn't, prioritize the one that does
                if (aTitle.startsWith(searchLower) && !bTitle.startsWith(searchLower)) return -1;
                if (bTitle.startsWith(searchLower) && !aTitle.startsWith(searchLower)) return 1;

                // If both or neither start with the search term, sort alphabetically
                return aTitle.localeCompare(bTitle);
            }

            // Otherwise, use existing sort logic
            let sortField;
            if (filters.source === 'youtube') {
                sortField = filters.order_by === 'date-added' ? 'finished_t' : 'date_uploaded';
            } else if (filters.source === 'local') {
                sortField = filters.order_by === 'date-added' ? 'finished_t' : 'creation_timestamp';
            } else {
                sortField = 'finished_t';
            }

            // Handle missing values
            if (!a[sortField]) return 1;
            if (!b[sortField]) return -1;

            // Stage 4: Apply sort direction (newest/oldest)
            const isNewest = filters.time === 'newest';

            // Handle string vs. number fields
            if (sortField === 'date_uploaded') {
                // String comparison for YouTube upload dates
                return isNewest
                    ? b[sortField].localeCompare(a[sortField])
                    : a[sortField].localeCompare(b[sortField]);
            } else {
                // Numeric comparison for timestamps
                return isNewest
                    ? b[sortField] - a[sortField]
                    : a[sortField] - b[sortField];
            }
        });

}