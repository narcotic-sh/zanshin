export const ssr = false;        // Disable server-side rendering
export const csr = true;         // Enable client-side rendering
export const prerender = false;  // Disable prerendering for SPA mode

import { get_setting } from '$lib/api';

export async function load() {
    const background_image = await get_setting('background_image') ?? true;
    const alternate_bg_color = await get_setting('alternate_bg_color') ?? false;

    return {
        background_image,
        alternate_bg_color
    };
}