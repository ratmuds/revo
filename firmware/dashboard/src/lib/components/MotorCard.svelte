<script lang="ts">
    import type { JointTelemetry } from "../types";
    import { servoController } from "../stores/servoStore.svelte";
    import { getMotorJointConfig } from "../config/robotConfig";
    import { ChevronDown, ChevronUp } from "lucide-svelte";

    interface Props {
        joint: JointTelemetry;
    }

    let { joint }: Props = $props();

    let expanded = $state(false);
    let isCalibrating = $state(false);

    let config = $derived(getMotorJointConfig(joint.id));
    let isContinuous = $derived(joint.id < 4);
    let maxAngle = $derived(isContinuous ? 360 : 270);

    let goalAngle = $state(90);
    let interpolateEnabled = $derived(servoController.interpolateEnabled[joint.id] ?? false);
    let currentSetAngle = $derived(servoController.currentSetAngles[joint.id] ?? goalAngle);

    let targetAngleDeg = $derived(goalAngle);
    let realAngleDeg = $derived(joint.ra);

    let deltaDeg = $derived(targetAngleDeg - realAngleDeg);
    let isMoving = $derived(Math.abs(deltaDeg) > 0.8 && joint.o === 1);
    let movingForward = $derived(deltaDeg > 0);

    // Active Calibration status check (true only during active calibration command)
    let isHomingOrCalibrating = $derived(isCalibrating && joint.o === 1);
    let isCalibrated = $derived(joint.cal === 1);

    // Percentage calculations for bottom gradient bar
    let currentPct = $derived(Math.max(0, Math.min(100, (realAngleDeg / maxAngle) * 100)));
    let targetPct = $derived(Math.max(0, Math.min(100, (targetAngleDeg / maxAngle) * 100)));

    let spanMinPct = $derived(Math.min(currentPct, targetPct));
    let spanMaxPct = $derived(Math.max(currentPct, targetPct));
    let spanWidthPct = $derived(Math.max(2, spanMaxPct - spanMinPct));

    // Physical LED mirror logic:
    let ledState = $derived.by(() => {
        if (!joint.o) return "offline";
        if (joint.chk === 0) return "error";
        if (isHomingOrCalibrating) return "homing";
        if (isCalibrated) return "calibrated";
        return "uncalibrated";
    });

    // Gradient Colors
    let ledGradient = $derived.by(() => {
        switch (ledState) {
            case "offline":
                return "from-zinc-600/10 via-zinc-600/3 to-transparent";
            case "error":
                return "from-rose-500/20 via-rose-500/5 to-transparent animate-pulse";
            case "homing":
                return "from-amber-400/20 via-amber-400/5 to-transparent animate-pulse";
            case "calibrated":
                return "from-[#2bd666]/15 via-[#2bd666]/4 to-transparent";
            case "uncalibrated":
                return "from-sky-400/15 via-sky-400/4 to-transparent";
        }
    });

    // Sync if external controllers (IK, Zero All, Rest Pose) update targetAngles
    $effect(() => {
        const target = servoController.targetAngles[joint.id];
        if (target !== undefined) {
            goalAngle = target;
        }
    });

    function setGoal(val: number) {
        const clamped = Math.max(0, Math.min(maxAngle, val));
        goalAngle = clamped;
        servoController.setJointGoal(joint.id, clamped);
    }

    function handleSlider(e: Event) {
        const val = parseFloat((e.target as HTMLInputElement).value);
        setGoal(val);
    }

    function stepAngle(delta: number) {
        setGoal(goalAngle + delta);
    }

    function triggerCalibrate() {
        isCalibrating = true;
        servoController.calibrateJoint(joint.id);
        setTimeout(() => {
            isCalibrating = false;
        }, 3500);
    }
</script>

<!-- Motor Card Container -->
<div
    class="group relative w-full bg-[#16171b] border border-white/[0.07] overflow-hidden shadow-lg transition-all duration-200 select-none {joint.o
        ? 'hover:border-white/[0.14]'
        : 'opacity-50 grayscale'}"
>
    <!-- Status Gradient -->
    <div
        class="absolute left-0 top-0 bottom-0 w-64 bg-gradient-to-r {ledGradient} pointer-events-none transition-all duration-500"
    ></div>

    <!-- Main Content -->
    <button
        type="button"
        onclick={() => (expanded = !expanded)}
        class="w-full text-left pl-6 pr-5 pt-3.5 pb-2 cursor-pointer focus:outline-none"
    >
        <!-- Motor Info -->
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-white tracking-wide">
                    M{joint.id}
                </span>
                <span class="text-xs text-[#9ca3af] font-medium">
                    {config?.displayName || (isContinuous ? "MG996R" : "DS5180")}
                </span>
                <span
                    class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-[#6b7280]"
                >
                    {isContinuous ? "RS485" : "PWM"}
                </span>
            </div>

            <!-- Calibration badge -->
            <div class="flex items-center gap-1.5">
                {#if !joint.o}
                    <span class="text-[11px] font-mono text-zinc-500">offline</span>
                {:else if isHomingOrCalibrating}
                    <span class="text-[11px] font-medium text-amber-400 flex items-center gap-1">
                        <span class="w-1 h-1 rounded-full bg-amber-400 animate-ping"></span> calibrating
                    </span>
                {:else if joint.cal}
                    <span class="text-[11px] font-medium text-[#2bd666] flex items-center gap-1">
                        <span class="w-1 h-1 rounded-full bg-[#2bd666]"></span> cal
                    </span>
                {:else}
                    <span class="text-[11px] font-medium text-sky-400 flex items-center gap-1">
                        <span class="w-1 h-1 rounded-full bg-sky-400"></span> uncal
                    </span>
                {/if}
                <div class="text-[#6b7280] ml-1">
                    {#if expanded}
                        <ChevronUp class="w-3.5 h-3.5" />
                    {:else}
                        <ChevronDown class="w-3.5 h-3.5" />
                    {/if}
                </div>
            </div>
        </div>

        <!-- Angle -->
        <div class="mt-1 flex items-baseline justify-between">
            <div class="flex items-baseline gap-1.5">
                <span class="text-3xl font-extrabold text-white tabular-nums tracking-tight">
                    {realAngleDeg.toFixed(1)}°
                </span>
                {#if Math.abs(deltaDeg) > 0.5 && joint.o}
                    <span class="text-xs font-mono text-[#9ca3af] tabular-nums">
                        → {targetAngleDeg.toFixed(1)}°
                    </span>
                {/if}
            </div>

            <!-- Telemetry -->
            <div
                class="flex items-center gap-2.5 text-[11px] font-mono text-[#8b909a] tabular-nums"
            >
                <span>{(joint.v / 1000).toFixed(1)}V</span>
                <span>{joint.c}mA</span>
                <span>{joint.t}°C</span>
            </div>
        </div>
    </button>

    <!-- Angle Bar -->
    <div class="relative w-full h-2 bg-[#1c1d22] overflow-hidden">
        {#if isHomingOrCalibrating}
            <!-- Bar -->
            <div
                class="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-amber-400 to-transparent animate-homing-sweep"
            ></div>
        {:else if isMoving}
            <!-- Bar -->
            <div
                class="absolute inset-y-0 bg-gradient-to-r from-[#2bd666]/0 via-[#2bd666]/80 to-[#2bd666]/0 rounded-full transition-all duration-1000 overflow-hidden"
                style="left: {spanMinPct}%; width: {spanWidthPct}%;"
            >
                <!-- Directional Shimmer strictly contained inside as a child -->
                <div
                    class="absolute inset-y-0 w-full bg-gradient-to-r from-transparent via-white/50 to-transparent {movingForward
                        ? 'animate-shimmer-right'
                        : 'animate-shimmer-left'}"
                ></div>
            </div>
        {:else}
            <div
                class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full {joint.cal
                    ? 'bg-[#2bd666] shadow-[0_0_6px_rgba(43,214,102,0.8)]'
                    : 'bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.8)]'} -translate-x-1/2 transition-all duration-150"
                style="left: {currentPct}%;"
            ></div>
        {/if}
    </div>

    <!-- Drawer -->
    {#if expanded}
        <div
            class="px-6 py-3.5 bg-[#121316] border-t border-white/[0.05] space-y-3 animate-in fade-in duration-200"
        >
            <!-- Angle Slider -->
            <div class="space-y-1">
                <div class="flex justify-between items-center text-[11px] font-mono text-[#8b909a]">
                    <div class="flex items-center gap-2">
                        <span>COMMAND ANGLE</span>
                        <label
                            class="flex items-center gap-1 cursor-pointer select-none text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] hover:bg-white/[0.08] text-[#9ca3af]"
                        >
                            <input
                                type="checkbox"
                                bind:checked={servoController.interpolateEnabled[joint.id]}
                                class="rounded border-zinc-700 text-[#2bd666] focus:ring-0 w-3 h-3 cursor-pointer"
                            />
                            <span>Interpolate</span>
                        </label>
                    </div>
                    <div class="flex items-baseline gap-1.5">
                        {#if interpolateEnabled && Math.abs(goalAngle - currentSetAngle) > 0.2}
                            <span class="text-[#2bd666] font-mono text-[10px] animate-pulse">
                                {currentSetAngle.toFixed(1)}° →
                            </span>
                        {/if}
                        <span class="text-white font-bold">{targetAngleDeg.toFixed(1)}°</span>
                    </div>
                </div>
                <input
                    type="range"
                    min="0"
                    max={maxAngle}
                    step="1"
                    value={goalAngle}
                    oninput={handleSlider}
                    class="w-full h-1.5 bg-[#23252a] rounded-full appearance-none cursor-pointer accent-[#2bd666] disabled:opacity-30"
                />
            </div>

            <div class="grid grid-cols-4 gap-2 pt-1">
                <button
                    onclick={() => stepAngle(-5)}
                    disabled={!joint.o}
                    class="py-1 text-xs font-mono font-medium rounded-lg bg-[#1f2126] hover:bg-[#282a30] text-zinc-300 border border-white/[0.06] transition-colors disabled:opacity-30"
                >
                    −5°
                </button>
                <button
                    onclick={() => stepAngle(-1)}
                    disabled={!joint.o}
                    class="py-1 text-xs font-mono font-medium rounded-lg bg-[#1f2126] hover:bg-[#282a30] text-zinc-300 border border-white/[0.06] transition-colors disabled:opacity-30"
                >
                    −1°
                </button>
                <button
                    onclick={() => stepAngle(1)}
                    disabled={!joint.o}
                    class="py-1 text-xs font-mono font-medium rounded-lg bg-[#1f2126] hover:bg-[#282a30] text-zinc-300 border border-white/[0.06] transition-colors disabled:opacity-30"
                >
                    +1°
                </button>
                <button
                    onclick={triggerCalibrate}
                    disabled={!joint.o || isCalibrating}
                    class="py-1 text-xs font-medium rounded-lg {isCalibrating
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
                        : 'bg-[#1f2126] hover:bg-[#282a30] text-zinc-300 border-white/[0.06]'} border transition-colors disabled:opacity-30"
                >
                    {isCalibrating ? "Cal..." : "Calibrate"}
                </button>
            </div>
        </div>
    {/if}
</div>

<style>
    @keyframes homingSweep {
        0% {
            transform: translateX(-100%);
        }
        100% {
            transform: translateX(300%);
        }
    }

    @keyframes shimmerRight {
        0% {
            transform: translateX(-100%);
            opacity: 0;
        }
        50% {
            opacity: 1;
        }
        100% {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    @keyframes shimmerLeft {
        0% {
            transform: translateX(100%);
            opacity: 0;
        }
        50% {
            opacity: 1;
        }
        100% {
            transform: translateX(-100%);
            opacity: 0;
        }
    }

    .animate-homing-sweep {
        animation: homingSweep 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }

    .animate-shimmer-right {
        animation: shimmerRight 0.9s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }

    .animate-shimmer-left {
        animation: shimmerLeft 0.9s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }
</style>
