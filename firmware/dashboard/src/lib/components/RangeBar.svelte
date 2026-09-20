<script lang="ts">
    interface Props {
        label: string;
        value: number;
        unit: string;
        min?: number;
        max?: number;
        mode?: "range" | "lower-better";
        // For range mode (voltage)
        targetMin?: number;
        targetMax?: number;
        // For lower-better mode (current, temp)
        warnThreshold?: number;
        critThreshold?: number;
        formatDecimals?: number;
    }

    let {
        label,
        value,
        unit,
        min = 0,
        max = 100,
        mode = "lower-better",
        targetMin = min,
        targetMax = max,
        warnThreshold = max * 0.65,
        critThreshold = max * 0.85,
        formatDecimals = 1
    }: Props = $props();

    // Clamp and compute percentage for value
    let clampedVal = $derived(Math.max(min, Math.min(max, value)));
    let valPct = $derived(
        Math.max(0, Math.min(100, ((clampedVal - min) / (max - min || 1)) * 100))
    );

    // Zone percentages for range mode
    let targetMinPct = $derived(
        Math.max(0, Math.min(100, ((targetMin - min) / (max - min || 1)) * 100))
    );
    let targetMaxPct = $derived(
        Math.max(0, Math.min(100, ((targetMax - min) / (max - min || 1)) * 100))
    );
    let targetWidthPct = $derived(Math.max(0, targetMaxPct - targetMinPct));

    // State check: in-range vs warning
    let isInRange = $derived(
        mode === "range" ? value >= targetMin && value <= targetMax : value < warnThreshold
    );
    let isCritical = $derived(mode === "lower-better" ? value >= critThreshold : false);

    // Colors
    let valueColor = $derived(
        isInRange ? "text-[#2bd666]" : isCritical ? "text-[#ff453a]" : "text-[#ff9f0a]"
    );

    let thumbColor = $derived(
        isInRange ? "bg-[#2bd666]" : isCritical ? "bg-[#ff453a]" : "bg-[#ff9f0a]"
    );

    let barFillColor = $derived(
        isInRange ? "bg-[#2bd666]" : isCritical ? "bg-[#ff453a]" : "bg-[#ff9f0a]"
    );
</script>

<div class="flex flex-col gap-2 select-none">
    <!-- Value Readout -->
    <div class="flex items-baseline justify-between">
        <span class="text-[13px] font-medium text-[#9ca3af] tracking-tight">{label}</span>
        <div class="flex items-baseline font-mono tabular-nums">
            <span class="text-sm font-bold {valueColor}">{value.toFixed(formatDecimals)}</span>
            <span class="text-[11px] font-medium text-[#6b7280] ml-1">{unit}</span>
        </div>
    </div>

    <!-- Capsule Track -->
    {#if mode === "range"}
        <div class="relative w-full py-0.5">
            <!-- Background Pill Track -->
            <div class="relative h-2.5 w-full rounded-full bg-background overflow-hidden">
                <!-- Under-voltage -->
                <div
                    class="absolute top-0 bottom-0 left-0 bg-amber-600/50"
                    style="width: {targetMinPct}%"
                ></div>

                <!-- Green Target -->
                <div
                    class="absolute top-0 bottom-0 bg-green-500"
                    style="left: {targetMinPct}%; width: {targetWidthPct}%"
                ></div>

                <!-- Over-voltage subtle amber bed -->
                <div
                    class="absolute top-0 bottom-0 right-0 bg-amber-300/50"
                    style="left: {targetMaxPct}%; right: 0;"
                ></div>
            </div>

            <!-- Current Value -->
            <div
                class="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full {thumbColor} border-2 border-[#16171a] shadow-md transition-all duration-200 -translate-x-1/2 pointer-events-none"
                style="left: {valPct}%"
            ></div>
        </div>

        <!-- Scale bounds -->
         <div class="flex items-center justify-between text-[10px] font-mono text-[#60646c] pt-0.5">
            <span>{min.toFixed(1)}</span>
            <span class="text-[#2bd666]/80 font-medium"
                >{((targetMin + targetMax) / 2).toFixed(1)}V</span
            >
            <span>{max.toFixed(1)}</span>
        </div>
    {:else}
        <!-- Regular Bar -->
        <div class="relative w-full py-0.5">
            <div class="h-2.5 w-full rounded-full bg-[#23252a] overflow-hidden p-[1px]">
                <div
                    class="h-full rounded-full transition-all duration-300 {barFillColor}"
                    style="width: {valPct}%"
                ></div>
            </div>
        </div>

        <!-- Scale bounds -->
        <div class="flex items-center justify-between text-[10px] font-mono text-[#60646c] pt-0.5">
            <span>{min.toFixed(0)}</span>
            <span class="text-[#60646c]">{warnThreshold.toFixed(0)}{unit}</span>
            <span>{max.toFixed(0)}</span>
        </div>
    {/if}
</div>
