<script>
    import { page } from '$app/state';
    import '$lib/static/cs16.css';
    import { showJapanese } from '$lib/stores/language.js';
    import favicon_light from '$lib/static/favicon_light.png';
    import favicon_dark from '$lib/static/favicon_dark.png';
    import { onMount } from 'svelte';
    import { browser } from '$app/environment';

    /** @type {import('./$types').LayoutData} */
    let { data } = $props();

    // Reactive statement to update background color when data changes
    $effect(() => {
        if (browser) {
            if (data.alternate_bg_color) {
                document.body.style.backgroundColor = '#363d31';
                document.documentElement.style.backgroundColor = '#363d31';
            } else {
                document.body.style.backgroundColor = 'var(--bg)';
                document.documentElement.style.backgroundColor = 'var(--bg)';
            }
        }
    });

    onMount(() => {
        if (browser) {
            let intervalId = null;

            // Update favicon (dark mode / light mode)
            const updateFavicon = (isDark) => {
                const favicon = isDark ? favicon_dark : favicon_light;
                // Remove existing favicon links
                const existingLinks = document.querySelectorAll("link[rel='icon']");
                existingLinks.forEach(link => link.remove());
                // Add new favicon
                const link = document.createElement('link');
                link.rel = 'icon';
                link.type = 'image/png';
                link.href = favicon;
                document.head.appendChild(link);
            };

            const checkAndUpdate = () => {
                const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
                updateFavicon(darkModeQuery.matches);
            };

            // Check initial preference
            const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
            updateFavicon(darkModeQuery.matches);

            // Listen for changes when tab is visible
            const handleChange = (e) => {
                updateFavicon(e.matches);
            };
            darkModeQuery.addEventListener('change', handleChange);

            // Handle visibility changes
            const handleVisibilityChange = () => {
                if (document.hidden) {
                    // Tab lost focus - start polling
                    intervalId = setInterval(checkAndUpdate, 1000);
                } else {
                    // Tab regained focus - stop polling and do immediate update
                    if (intervalId) {
                        clearInterval(intervalId);
                        intervalId = null;
                    }
                    checkAndUpdate(); // Immediate update when returning to tab
                }
            };

            document.addEventListener('visibilitychange', handleVisibilityChange);

            return () => {
                darkModeQuery.removeEventListener('change', handleChange);
                document.removeEventListener('visibilitychange', handleVisibilityChange);
                if (intervalId) {
                    clearInterval(intervalId);
                }
            };
        }
    });
</script>

<svelte:head>
    <!-- Initial favicon - will be replaced by JavaScript -->
    <link rel="icon" href={favicon_light} type="image/png" />
</svelte:head>

<main class="main-container" class:with-background={data.background_image}>
    {#if page.url.pathname !== '/' && page.url.pathname !== '/acknowledgements'}
        <div class="nav-container">
            <nav class="floating-nav">
                <!-- Zanshin logo -->
                <a href="/" class="nav-brand" class:japanese={$showJapanese}>
                    {$showJapanese ? '残心' : 'Zanshin'}
                </a>
                <!-- Seperator -->
                <div class="nav-separator"></div>
                <!-- Vault, Settings -->
                <div style="margin-left: -8.6px; padding-right: 2px; margin-top: -1.25px;">
                    <a href="/vault" class="nav-link" class:active={page.url.pathname === '/vault'} data-sveltekit-preload-data onclick={() => {
                        if (page.url.pathname === '/vault') {
                            event.preventDefault();
                            if (typeof window !== 'undefined' && window.reset_vault) {
                                window.reset_vault();
                            }
                        }
                    }}>Vault</a>
                    <a href="/settings" style="margin-left: -7px; padding-right: 0px;" class="nav-link" class:active={page.url.pathname === '/settings'}>Settings</a>
                </div>
            </nav>
        </div>
    {/if}
    <div class="page-content">
        <slot/>
    </div>
</main>

<style>
    /*
    =========================================================
        Main Container
    =========================================================
    */
    .main-container {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    .main-container.with-background {
        background-image: url('$lib/static/bg.png');
    }
    /*
    =========================================================
        Nav Container
    =========================================================
    */

    .nav-container {
        position: relative;
        height: 70px;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    /*
    =========================================================
        Container
    =========================================================
    */
    .floating-nav {
        position: absolute;
        top: 19px;
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 8px 16px 8px 16px;
        background-color: var(--bg);
        border: 1px solid;
        border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
        font-family: ArialPixel, system-ui, sans-serif;
    }

    /*
    =========================================================
        Zanshin logo
    =========================================================
    */
    .nav-brand {
        font-size: 18px;
        font-weight: bold;
        color: var(--text);
        text-decoration: none;
        user-select: none;
        transform: translateY(0.5px) translateX(1.5px);
        margin-left: -2px;
    }

    .nav-brand.japanese {
        transform: translateY(2px) translateX(1px);
    }

    /*
    =========================================================
        Seperator
    =========================================================
    */
    .nav-separator {
        width: 1px;
        height: 22px;
        background-color: var(--border-dark);
        margin: 0 4px;

    }

    /*
    =========================================================
        Page links
    =========================================================
    */
    .nav-link {
        color: var(--text-3);
        text-decoration: none;
        font-size: 14px;
        font-weight: 400;
        user-select: none;
        padding: 4px 8px;
        border: 1px solid transparent;
        background-color: transparent;
    }

    /*.nav-link:hover:not(.active) {
        filter: brightness(1.2);
    }*/

    .nav-link.active {
        color: var(--accent);
    }

    /*
    =========================================================
        Page content
    =========================================================
    */
    .page-content {
        flex: 1;
    }
</style>