import { fetch_media_previews } from '$lib/api';

/** @type {import('./$types').PageLoad} */
export async function load({ params }) {
    const previews_data = await fetch_media_previews();
    if (previews_data) {
        return previews_data;
    } else {
        return {
            error: "couldn't fetch youtube previews"
        }
    }
}
