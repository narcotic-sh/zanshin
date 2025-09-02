import { fetch_zanshin_version } from '$lib/api';
import { get_setting } from '$lib/api'; // Add this import

/** @type {import('./$types').PageLoad} */
export async function load({ params }) {
    const version_data = await fetch_zanshin_version();
    const background_image = await get_setting('background_image') ?? true;
    const alternate_bg_color = await get_setting('alternate_bg_color') ?? false;

    if (version_data) {
        return {
            version: version_data.version,
            background_image,
            alternate_bg_color
        };
    } else {
        return {
            version: null,
            background_image,
            alternate_bg_color
        };
    }
}