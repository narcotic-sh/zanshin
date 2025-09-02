<!-- I have no idea how any of this works; this is all Claude 3.7 generated. Works fine though. -->

<svelte:window on:resize={calculateBars} on:focus={switchToRAF} on:blur={switchToInterval} />

<script>
    import { browser } from '$app/environment';

    let { percentage = 0, slide = false, side_to_side = false } = $props();
    let containerElement = $state(null);
    let bars = $state([]);
    let animationFrameId = $state(null);
    let animationInterval = $state(null);
    let lastFrameTime = $state(0);
    let animationPhase = $state('moving'); // 'moving' or 'returning'
    let returningIndex = $state(0);
    let returnDelay = $state(0);
    let direction = $state(1); // 1 for right, -1 for left
    let hasFocus = $state(true); // Track focus state
    let lastUpdateTime = $state(0); // Track last update time

    // Animation speed in pixels per second
    const ANIMATION_SPEED = 150; // Faster movement
    const RETURN_INTERVAL = 15; // Time between returning bars in ms
    const ANIMATION_INTERVAL = 16; // ~60fps
    const MAX_DELTA_TIME = 0.1; // Maximum time delta in seconds (prevents large jumps)

    // Function to calculate and render the exact number of bars
    function calculateBars() {
        if (!containerElement) return;

        // Get available width
        const containerWidth = containerElement.clientWidth;

        // Bar dimensions
        const barWidth = 8;
        const gapWidth = 4;
        const totalBarWidth = barWidth + gapWidth;

        // Calculate max number of bars that fit the container
        const maxBars = Math.floor(containerWidth / totalBarWidth);

        if (side_to_side) {
            // Similar to slide mode, but we'll start with bars at the left
            const barsToShow = Math.floor(maxBars*0.56);

            // If animation is not already running, initialize and start it
            if (!animationFrameId && !animationInterval) {
                // Create initial bars
                bars = Array(barsToShow).fill().map((_, i) => ({
                    x: i * totalBarWidth
                }));

                // Set initial direction
                direction = 1; // Start moving right

                // Start animation
                startAnimation();
            } else {
                // Handle resize while animation is running
                if (bars.length !== barsToShow) {
                    const currentDirection = direction;

                    // Adjust number of bars while preserving their positions
                    let newBars;
                    if (barsToShow > bars.length) {
                        // Add more bars
                        newBars = [...bars];
                        for (let i = bars.length; i < barsToShow; i++) {
                            // Position new bars to continue the pattern
                            newBars.push({
                                x: newBars.length > 0
                                    ? newBars[newBars.length - 1].x + totalBarWidth
                                    : 0
                            });
                        }
                    } else {
                        // Remove excess bars
                        newBars = bars.slice(0, barsToShow);
                    }

                    bars = newBars;
                    direction = currentDirection;
                }
            }
        } else if (slide) {
            const barsToShow = Math.floor(maxBars*0.65);

            // If animation is not already running, initialize and start it
            if (!animationFrameId && !animationInterval) {
                // Create initial bars
                bars = Array(barsToShow).fill().map((_, i) => ({
                    x: i * totalBarWidth
                }));

                // Set initial animation state
                animationPhase = 'moving';
                returningIndex = 0;

                // Start animation
                startAnimation();
            } else {
                // If already running but container size changed, adjust number of bars
                if (bars.length !== barsToShow) {
                    const currentPhase = animationPhase;
                    const currentIndex = returningIndex;

                    bars = Array(barsToShow).fill().map((_, i) => {
                        if (i < bars.length) {
                            return bars[i];
                        } else {
                            return { x: i * totalBarWidth };
                        }
                    });

                    animationPhase = currentPhase;
                    returningIndex = Math.min(currentIndex, bars.length);
                }
            }
        } else {
            // Stop animation if neither slide nor side_to_side is active
            stopAnimation();

            const validPercentage = Math.max(0, Math.min(100, percentage));
            let barsToShow;

            if (validPercentage >= 100) {
                barsToShow = maxBars;
            } else if (validPercentage > 0) {
                barsToShow = Math.max(1, Math.floor((maxBars * validPercentage) / 100));
            } else {
                barsToShow = 0;
            }

            // Update bars array for non-animation mode
            bars = Array(barsToShow).fill().map((_, i) => ({
                x: i * totalBarWidth
            }));
        }
    }

    function startAnimation() {
        stopAnimation(); // Clear any existing animation first
        lastFrameTime = performance.now();
        lastUpdateTime = performance.now();

        if (side_to_side) {
            direction = 1; // Start moving right
        } else if (slide) {
            animationPhase = 'moving';
            returningIndex = 0;
        }

        // Start with appropriate animation method based on focus state
        if (hasFocus) {
            startRAFAnimation();
        } else {
            startIntervalAnimation();
        }
    }

    function stopAnimation() {
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        if (animationInterval) {
            clearInterval(animationInterval);
            animationInterval = null;
        }
    }

    function switchToRAF() {
        hasFocus = true;
        if ((slide || side_to_side) && animationInterval && !animationFrameId) {
            // Save current animation state
            const currentBars = [...bars];
            const currentDirection = direction;
            const currentPhase = animationPhase;

            // Handle potential edge cases before switching
            validatePositions();

            clearInterval(animationInterval);
            animationInterval = null;

            // Update timing to prevent jumps
            lastFrameTime = performance.now();
            lastUpdateTime = performance.now();

            startRAFAnimation();

            // Ensure animation state consistency
            direction = currentDirection;
            animationPhase = currentPhase;
        }
    }

    function switchToInterval() {
        hasFocus = false;
        if ((slide || side_to_side) && animationFrameId && !animationInterval) {
            // Save current animation state
            const currentBars = [...bars];
            const currentDirection = direction;
            const currentPhase = animationPhase;

            // Handle potential edge cases before switching
            validatePositions();

            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;

            // Update timing to prevent jumps
            lastFrameTime = performance.now();
            lastUpdateTime = performance.now();

            startIntervalAnimation();

            // Ensure animation state consistency
            direction = currentDirection;
            animationPhase = currentPhase;
        }
    }

    function validatePositions() {
        if (!containerElement || !side_to_side) return;

        const containerWidth = containerElement.clientWidth;
        const barWidth = 8;
        const gapWidth = 4;
        const totalBarWidth = barWidth + gapWidth;

        // Check if we're at an edge
        if (bars.length > 0) {
            // Check right edge
            const rightmostBar = bars[bars.length - 1];
            const buffer = 6; // Buffer distance in pixels

            if (rightmostBar.x + barWidth >= containerWidth - buffer) {
                // We're at the right edge - ensure we're moving left
                direction = -1;

                // Move bars slightly away from the edge to prevent "sticking"
                let newBars = [...bars];
                for (let i = 0; i < newBars.length; i++) {
                    newBars[i].x -= 1;
                }
                bars = newBars;
            }

            // Check left edge
            const leftmostBar = bars[0];
            if (leftmostBar.x <= 0) {
                // We're at the left edge - ensure we're moving right
                direction = 1;

                // Move bars slightly away from the edge to prevent "sticking"
                let newBars = [...bars];
                for (let i = 0; i < newBars.length; i++) {
                    newBars[i].x += 1;
                }
                bars = newBars;
            }
        }
    }

    function startRAFAnimation() {
        lastFrameTime = performance.now();
        lastUpdateTime = performance.now();
        animateRAF(lastFrameTime);
    }

    function startIntervalAnimation() {
        lastFrameTime = performance.now();
        lastUpdateTime = performance.now();
        animationInterval = setInterval(() => {
            const now = performance.now();
            // Cap delta time to prevent large jumps after tab becomes inactive
            const deltaTime = Math.min((now - lastFrameTime) / 1000, MAX_DELTA_TIME);
            lastFrameTime = now;

            updateBarPositions(deltaTime);
        }, ANIMATION_INTERVAL);
    }

    function animateRAF(timestamp) {
        if ((!slide && !side_to_side) || !containerElement) {
            stopAnimation();
            return;
        }

        // Calculate time delta since last frame in seconds
        // Cap delta time to prevent large jumps after tab becomes inactive
        const deltaTime = Math.min((timestamp - lastFrameTime) / 1000, MAX_DELTA_TIME);
        lastFrameTime = timestamp;

        updateBarPositions(deltaTime);

        animationFrameId = requestAnimationFrame(animateRAF);
    }

    function updateBarPositions(deltaTime) {
        if ((!slide && !side_to_side) || !containerElement) {
            stopAnimation();
            return;
        }

        // Update last update time
        const now = performance.now();
        const timeSinceLastUpdate = (now - lastUpdateTime) / 1000;
        lastUpdateTime = now;

        // If it's been too long since the last update (tab was inactive),
        // use a smaller delta to prevent large jumps
        const adjustedDeltaTime = timeSinceLastUpdate > 1 ? 0.016 : deltaTime;

        const containerWidth = containerElement.clientWidth;
        const barWidth = 8;
        const gapWidth = 4;
        const totalBarWidth = barWidth + gapWidth;

        // Calculate movement amount based on time delta and speed
        const moveAmount = ANIMATION_SPEED * adjustedDeltaTime;

        if (side_to_side) {
            // Side to side animation logic
            let newBars = [...bars];

            // Move all bars based on current direction
            for (let i = 0; i < newBars.length; i++) {
                newBars[i].x += moveAmount * direction;
            }

            // Check boundaries and reverse direction if needed
            if (direction > 0) {
                // Moving right - check if rightmost bar is ~20px from edge
                const rightmostBar = newBars[newBars.length - 1];
                const buffer = 6; // Buffer distance in pixels
                if (rightmostBar.x + barWidth >= containerWidth - buffer) {
                    direction = -1; // Reverse to moving left

                    // Ensure we don't go past the edge
                    const overshot = (rightmostBar.x + barWidth) - (containerWidth - buffer);
                    if (overshot > 0) {
                        for (let i = 0; i < newBars.length; i++) {
                            newBars[i].x -= overshot;
                        }
                    }
                }
            } else {
                // Moving left - check if leftmost bar hits edge
                const leftmostBar = newBars[0];
                if (leftmostBar.x <= 0) {
                    direction = 1; // Reverse to moving right

                    // Ensure we don't go past the edge
                    if (leftmostBar.x < 0) {
                        const offset = Math.abs(leftmostBar.x);
                        for (let i = 0; i < newBars.length; i++) {
                            newBars[i].x += offset;
                        }
                    }
                }
            }

            bars = newBars;
        } else if (slide) {
            if (animationPhase === 'moving') {
                // Move all bars based on time delta
                let newBars = [...bars];
                let allOffScreen = true;

                for (let i = 0; i < newBars.length; i++) {
                    newBars[i].x += moveAmount;

                    // Check if any bar is still visible
                    if (newBars[i].x < containerWidth) {
                        allOffScreen = false;
                    }
                }

                bars = newBars;

                // If all bars are off-screen, switch to returning phase
                if (allOffScreen) {
                    animationPhase = 'returning';
                    returningIndex = 0;
                    returnDelay = 0;

                    // Move all bars off-screen to the right
                    bars = bars.map(() => ({ x: containerWidth }));
                }
            } else if (animationPhase === 'returning') {
                // First time entering returning phase, position bars
                if (returningIndex === 0) {
                    // Position all bars off-screen to the left, maintaining their relative spacing
                    let newBars = [...bars];
                    for (let i = 0; i < newBars.length; i++) {
                        // Position bars to the left of the screen, preserving their formation
                        newBars[i].x = -totalBarWidth * (newBars.length - i);
                    }
                    bars = newBars;
                    returningIndex = 1; // Mark initialization as complete
                }

                // Move all bars rightward together
                let newBars = [...bars];
                let allBarsVisible = true;

                for (let i = 0; i < newBars.length; i++) {
                    newBars[i].x += moveAmount;

                    // Check if any bar is still off-screen to the left
                    if (newBars[i].x < 0) {
                        allBarsVisible = false;
                    }
                }

                bars = newBars;

                // When all bars have fully entered the screen, resume normal sliding
                if (allBarsVisible) {
                    // Reset to proper positions if needed
                    let needsReset = false;

                    // Check if any bars are not in proper position
                    for (let i = 0; i < bars.length; i++) {
                        if (Math.abs(bars[i].x - (i * totalBarWidth)) > 1) {
                            needsReset = true;
                            break;
                        }
                    }

                    if (needsReset) {
                        // Reset bars to their proper initial positions
                        let resetBars = [...bars];
                        for (let i = 0; i < resetBars.length; i++) {
                            resetBars[i].x = i * totalBarWidth;
                        }
                        bars = resetBars;
                    }

                    // Switch back to moving phase
                    animationPhase = 'moving';
                    returningIndex = 0;
                }
            }
        }
    }

    // Run calculateBars when containerElement or percentage changes
    $effect(() => {
        if (containerElement && percentage !== undefined) {
            calculateBars();
        }
    });

    // Visibility API for better focus detection
    $effect(() => {
        if (browser) {
            // Set up visibility change detection
            if (typeof document !== 'undefined') {
                document.addEventListener('visibilitychange', handleVisibilityChange);

                // Initial check
                hasFocus = document.visibilityState === 'visible';

                return () => {
                    document.removeEventListener('visibilitychange', handleVisibilityChange);
                    stopAnimation();
                };
            }
        }
    });

    function handleVisibilityChange() {
        if (browser) {
            if (document.visibilityState === 'visible') {
                switchToRAF();
            } else {
                switchToInterval();
            }
        }
    }
</script>
<div class="progress-container" bind:this={containerElement}>
    <svg class="bars-svg" width="100%" height="100%">
        {#each bars as bar}
            <rect
                x={bar.x}
                y="50%"
                width="8"
                height="16"
                class="bar"
                transform="translate(0, -8)"
            />
        {/each}
    </svg>
</div>
<style>
    .progress-container {
        width: 100%;
        height: 24px;
        padding: 3px;
        background-color: var(--secondary-bg);
        border: 1px solid;
        border-color: var(--border-dark) var(--border-light) var(--border-light) var(--border-dark);
        transform: translateZ(0);
    }
    .bars-svg {
        transform: translateZ(0);
    }
    .bar {
        fill: var(--accent);
    }
</style>
