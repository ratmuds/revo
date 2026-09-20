<script lang="ts">
    import { servoController } from "$lib/stores/servoStore.svelte";
    import { tweened } from "svelte/motion";
    import { cubicOut } from "svelte/easing";

    let { off } = $props();

    // Geometry settings for SVG circular gauge
    const CX = 140;
    const CY = 140;
    const R = 98;
    const STROKE_WIDTH = 14;

    // Highest current usage across all online servos (mA)
    // Filter if current is reported as >= 3200 (broken)
    let maxCurrentMa = $derived(
        servoController.joints.reduce(
            (max, j) => (j.c >= 3200 ? max : Math.max(max, j.o ? j.c || 0 : 0)),
            0
        )
    );

    // Load percentage: highest servo current divided by 500 mA
    let targetLoad = $derived(Math.min(100, Math.max(0, Math.round((maxCurrentMa / 500) * 100))));

    // Highest temperature across all online servos
    const MAX_TEMP_SCALE = 80;
    let maxTemp = $derived(
        servoController.joints.reduce((max, j) => Math.max(max, j.o ? j.t || 0 : 0), 0)
    );

    // Yellow bar percentage based on highest temperature
    let tempPercent = $derived(
        maxTemp > 0 ? Math.min(100, Math.max(0, Math.round((maxTemp / MAX_TEMP_SCALE) * 100))) : 0
    );

    // Load value
    const animatedLoad = tweened(0, { duration: 300, easing: cubicOut });
    $effect(() => {
        animatedLoad.set(Number(targetLoad));
    });

    // Temp value
    const animatedTemp = tweened(0, { duration: 300, easing: cubicOut });
    $effect(() => {
        animatedTemp.set(Number(tempPercent));
    });

    // Polar coordinate conversion
    function polarToCartesian(centerX: number, centerY: number, radius: number, angleDeg: number) {
        const rad = ((angleDeg - 90) * Math.PI) / 180.0;
        return {
            x: centerX + radius * Math.cos(rad),
            y: centerY + radius * Math.sin(rad)
        };
    }

    function describeArc(
        centerX: number,
        centerY: number,
        radius: number,
        startAngleDeg: number,
        endAngleDeg: number
    ) {
        const start = polarToCartesian(centerX, centerY, radius, endAngleDeg);
        const end = polarToCartesian(centerX, centerY, radius, startAngleDeg);
        const largeArcFlag = endAngleDeg - startAngleDeg <= 180 ? "0" : "1";
        return ["M", start.x, start.y, "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(
            " "
        );
    }

    // Angular ranges
    const LEFT_MIN_DEG = 215;
    const LEFT_MAX_DEG = 330;
    const LEFT_SPAN = LEFT_MAX_DEG - LEFT_MIN_DEG;

    const RIGHT_MIN_DEG = 30;
    const RIGHT_MAX_DEG = 145;
    const RIGHT_SPAN = RIGHT_MAX_DEG - RIGHT_MIN_DEG;

    // Dynamic active angles derived from animatedLoad (guarantees the dot stays on the circular perimeter)
    let leftActiveSpan = $derived((Math.max(1, $animatedLoad) / 100) * LEFT_SPAN);
    let leftActiveEndDeg = $derived(LEFT_MIN_DEG + leftActiveSpan);

    let rightActiveSpan = $derived((Math.max(1, $animatedTemp) / 100) * RIGHT_SPAN);
    let rightActiveEndDeg = $derived(RIGHT_MIN_DEG + rightActiveSpan);

    let leftPipPos = $derived(polarToCartesian(CX, CY, R, leftActiveEndDeg));
    let rightEndPos = $derived(polarToCartesian(CX, CY, R, rightActiveEndDeg));

    // Full background tracks
    const leftTrack = describeArc(CX, CY, R, LEFT_MIN_DEG, LEFT_MAX_DEG);
    const rightTrack = describeArc(CX, CY, R, RIGHT_MIN_DEG, RIGHT_MAX_DEG);

    // Active colored arcs
    let leftActiveArc = $derived(describeArc(CX, CY, R, LEFT_MIN_DEG, leftActiveEndDeg));
    let rightActiveArc = $derived(describeArc(CX, CY, R, RIGHT_MIN_DEG, rightActiveEndDeg));
</script>

<div class="flex flex-col items-center select-none font-['GeneralSans',sans-serif]">
    <div class="relative w-[280px] h-[280px] flex items-center justify-center">
        <!-- SVG Arcs & Circular Tracks -->
        <svg viewBox="0 0 280 280" class="w-full h-full overflow-visible">
            <!-- Left Background Dark Track -->
            <path
                d={leftTrack}
                fill="none"
                stroke="#222226"
                stroke-width={STROKE_WIDTH}
                stroke-linecap="round"
            />

            <!-- Right Background Dark Track -->
            <path
                d={rightTrack}
                fill="none"
                stroke="#222226"
                stroke-width={STROKE_WIDTH}
                stroke-linecap="round"
            />

            {#if !off}
                <!-- Left Active Blue Arc (Load) -->
                <path
                    d={leftActiveArc}
                    fill="none"
                    stroke="#1d75f2"
                    stroke-width={STROKE_WIDTH}
                    stroke-linecap="round"
                />

                <!-- Right Active Amber Arc (Voltage) -->
                <path
                    d={rightActiveArc}
                    fill="none"
                    stroke="#f59e0b"
                    stroke-width={STROKE_WIDTH}
                    stroke-linecap="round"
                />

                <!-- White Indicator Dot on the Left Arc -->
                <circle cx={leftPipPos.x} cy={leftPipPos.y} r="4" fill="#ffffff" />

                <!-- Dot at the end of the Right Arc -->
                <circle
                    cx={rightEndPos.x}
                    cy={rightEndPos.y}
                    r="4.5"
                    fill="#18181b"
                    stroke="#f59e0b"
                    stroke-width="2.5"
                />
            {/if}
        </svg>

        <!-- Center Giant Numerals -->
        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none font-['GeneralSans',sans-serif]">
            <span class="text-7xl font-bold tracking-tight text-white tabular-nums leading-none">
                {off ? "--" : Math.round($animatedLoad)}
            </span>
            <span class="text-sm font-medium tracking-wide text-zinc-300 mt-1">{off ? "OFF" : "LOAD"}</span>
        </div>
    </div>
</div>
