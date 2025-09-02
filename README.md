<p align="center">
<img height="182" src="/packaging/assets/Zanshin_512x512.png">
</p>

<p align="center">
<img src="title.svg" alt="Zanshin - Relaxed alertness; continuing awareness">
</p>

<p align="center">
<a href="https://zanshin.sh">Website</a> ·
<a href="https://discord.gg/Nf7m5Ftk3c">Discord</a>
</p>

---

A media player with a novel interface allowing you to navigate by speaker.

- Visualize who speaks when & for how long
- Jump/skip speaker segments
- Disable speakers (auto-skip)
- Set different playback speeds per speaker

It's a better, more efficient way to listen to podcasts, interviews, press confrences etc.

Supports YouTube videos and your own local media files.

Visit the [website](https://zanshin.sh) for demo videos and screenshots of the UI/interface.

残心 / Zanshin is powered by the very fast [Senko](https://github.com/narcotic-sh/senko) speaker diarization pipeline.

## Installation
Zanshin is currently only available in packaged form for macOS (Apple Silicon). Download from the [website](https://zanshin.sh).

For Windows and Linux, packaging is not available yet and will be coming soon. In the mean time, you can get Zanshin running on both of those platforms by entering in some commands in the terminal. Refer to [`DEV_SETUP.md`](/DEV_SETUP.md) for instructions.

## macOS FAQ
<details>
<summary>How do I update Zanshin?</summary>
<br>
Zanshin on macOS comes with an auto-updater built-in. It checks periodically if there's an update available while the app is running. If there is, it fetches it and decompresses it. Then, when you quit the app, it installs the update, so that the next time you run the app, you'll be on the latest version.
<br>
<br>
You can also download the latest Zanshin <code>.pkg</code> file and simply install it. That will update Zanshin as well (won't wipe the items in your Vault).
</details>
<details>
<summary>How do I uninstall Zanshin?</summary>
<br>
Delete two items:
<ul>
  <li><code>Zanshin.app</code> in <code>/Applications</code></li>
  <li>The folder <code>~/Library/Application Support/Zanshin</code></li>
</ul>
</details>
<details>
<summary>Can I backup and restore all the items in my Zanshin Vault?</summary>
<br>
Yes, simply backup the following file:
<ul>
  <li><code>~/Library/Application Support/Zanshin/zanshin/media.db</code></li>
</ul>
To restore it (like after you install Zanshin on a new Mac, for example), simply move the file into that same location.
</details>

## Community, Support, Future Plans
Join the [Discord](https://discord.gg/Nf7m5Ftk3c) server to ask questions, suggest features, talk about Zanshin and Senko development etc.

For planned features and improvements, see [`PLANS.md`](/PLANS.md) .

## Development
For setting up Zanshin for development, see [`DEV_SETUP.md`](/DEV_SETUP.md).
