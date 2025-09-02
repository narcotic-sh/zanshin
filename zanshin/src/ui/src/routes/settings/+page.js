import { get_all_settings } from '$lib/api';

/** @type {import('./$types').PageLoad} */
export async function load({ url }) {
    const highlight_setting = url.searchParams.get('highlight');
    const settings = await get_all_settings();

    if (settings) {
        return {
            ...settings,
            highlight_setting
        };
    } else {
        return {
            error: "Couldn't fetch settings",
            highlight_setting
        }
    }
}
