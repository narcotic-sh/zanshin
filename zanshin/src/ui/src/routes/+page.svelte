<svelte:head>
   <title>Zanshin</title>
</svelte:head>
<script>
   import SubmitJob from '$lib/SubmitJob.svelte';
   import { showJapanese } from '$lib/stores/language.js';
   /** @type {import('./$types').PageProps} */
   let { data } = $props();

   function toggleLanguage() {
       showJapanese.update(value => !value);
   }
</script>
<main>
    <div class="content-container">
        <div class="container">
            <div class="nav-section">
                <div class="version-display">
                    {#if data.version}
                        <span class="version-text">v{data.version}</span>
                    {/if}
                </div>
                <div class="nav-buttons">
                    <a href="/vault" class="nav-link" data-sveltekit-preload-data>[Vault]</a>
                    <a href="/settings" class="nav-link" data-sveltekit-preload-data>[Settings]</a>
                </div>
            </div>
            <div class="content-box">
                <div class="title" role="button" tabindex="0" onclick={toggleLanguage} onkeydown={(e) => e.key === 'Enter' && toggleLanguage()}>
                    {$showJapanese ? '残心' : 'Zanshin'}
                </div>
                <a href="https://www.youtube.com/embed/IYaYGW4PyZE?autoplay=1" target="_blank" rel="noopener noreferrer" class="caption-link">
                    <p class="caption">Relaxed alertness; continuing awareness</p>
                </a>
                <SubmitJob />
            </div>
        </div>
    </div>

   <footer class="footer" class:with-background-bleed={data.background_image} class:with-alternate-bg={data.alternate_bg_color}>
       <div class="footer-text">
           a <a href="https://hamzaq.com" class="footer-link" target="_blank" rel="noopener noreferrer">Hamza Q.</a> production<br>
           <a href="https://narcotic.sh" class="footer-link" target="_blank" rel="noopener noreferrer">Narcotic Software</a> © 2025<br>
           <span class="footer-text">
               <a class="footer-link footer-opensource-link" href="/THIRD_PARTY_LICENSES">Credits</a>
               <span style="color: #808e71;">and</span>
               <a class="footer-link footer-opensource-link" href="/acknowledgements">Acknowledgements</a>
           </span>           <!-- <div class="footer-opensource-line">
               <span
                   class="footer-title-toggle"
                   role="button"
                   tabindex="0"
                   onclick={toggleLanguage}
                   onkeydown={(e) => e.key === 'Enter' && toggleLanguage()}
               >
                   {$showJapanese ? '残心' : 'Zanshin'}
               </span> is made possible by <a href="/THIRD_PARTY_LICENSES" class="footer-link footer-opensource-link">open source software</a>
           </div> -->
       </div>
   </footer>
</main>
<style>
    main {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .content-container {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center
    }

   .container {
       position: absolute;
       top: 25vh;
       left: 50%;
       transform: translateX(-50%);
       width: 500px;
       text-align: center;
       border: solid 1px;
       border-color: var(--border-light) var(--border-dark) var(--border-dark) var(--border-light);
   }

   @media (max-height: 630px) {
       .container {
           position: static;
           top: auto;
           left: auto;
           transform: none;
       }
   }

   /*
   =========================================================
       Navbar
   =========================================================
   */

   .nav-section {
       border-bottom: 1px solid #363a2c;
       padding: 0 8px;
       display: flex;
       justify-content: space-between;
       align-items: center;
       background-color: var(--bg);
   }

   .version-display {
       font-family: ArialPixel, system-ui, sans-serif;
   }

   .version-text {
       color: var(--text-3);
       font-size: 14px;
       padding: 2px;
   }

   .nav-buttons {
       display: flex;
       background-color: var(--bg);
       font-family: ArialPixel, system-ui, sans-serif;
       gap: 2px;
   }

   .nav-link {
       color: var(--text-3);
       text-decoration: none;
       font-size: 14px;
       padding: 2px;
   }

   .nav-link:hover {
       color: var(--accent);
   }

    /*
    =========================================================
        Main box
    =========================================================
    */

   .content-box {
       background: var(--bg);
       padding: 28px 40px 28px 40px;
       color: var(--text);
   }

   .title {
       font-size: 3rem;
       font-weight: bold;
       user-select: none;
       margin-bottom: -10px;
       cursor: pointer;
       display: inline-block;
   }

   .caption-link {
       text-decoration: none;
       color: inherit;
   }

   .caption-link:hover,
   .caption-link:visited,
   .caption-link:active,
   .caption-link:focus {
       text-decoration: none;
       color: inherit;
   }

   .caption {
       font-style: italic;
       color: var(--text-3);
       padding-bottom: 12px;
       cursor: pointer;
   }

   /*
   =========================================================
       Footer
   =========================================================
   */

   .footer {
       background: var(--secondary-bg);
       border-top: 1px solid var(--border-dark);
       padding: 12px 0;
       text-align: center;
       align-self: stretch;
   }

   .footer.with-background-bleed {
       background: color-mix(in srgb, var(--secondary-bg) 50%, transparent);
   }

   .footer.with-alternate-bg {
       background: #414a3a;
   }

   .footer-text {
       color: var(--text-3);
       font-size: 16px;
       line-height: 1.4;
   }

   .footer-link {
       color: var(--text-3);
       text-decoration: none;
   }

   .footer-link:hover {
       color: var(--accent);
   }

   .footer-title-toggle {
       cursor: pointer;
       user-select: none;
       display: inline;
   }

   .footer-opensource-line {
       color: #808e71;
   }

   .footer-opensource-link {
       color: #808e71;
   }

   .footer-opensource-link:hover {
       color: var(--accent);
   }

</style>