<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import * as THREE from "three";
    import { Canvas } from "@threlte/core";
    import { XRButton } from "@threlte/xr";
    import VRScene from "$lib/components/VRScene.svelte";
    import Speedometer from "$lib/components/Speedometer.svelte";
    import { servoController } from "$lib/stores/servoStore.svelte";
    import { ArrowLeft } from "lucide-svelte";

    onMount(() => {
        servoController.init();
    });

    onDestroy(() => {
        servoController.destroy();
    });

    // Reactive telemetry
    let isConnected = $derived(servoController.connectionState === "connected");
    let onlineCount = $derived(servoController.joints.filter((j) => j.o).length);
    let joints6V = $derived(servoController.joints.filter((j) => j.id < 4 && j.o));
    let voltage6V = $derived(
        joints6V.length > 0
            ? (joints6V.reduce((acc, j) => acc + (j.v || 0), 0) / joints6V.length / 1000).toFixed(1)
            : "6.0"
    );

    // Relative stream paths proxied by Vite (same origin, zero CORS/canvas taint issues)
    const mainStreamUrl = "/stream/main";
    const secondaryStreamUrl = "/stream/secondary";

    let mainStreamConnected = $state(true);
    let secondaryStreamConnected = $state(true);
    let vrErrorMessage = $state<string | null>(null);
    let isVrPresenting = $state(false);

    // Image DOM references passed to VRScene for reliable WebGL texture blitting
    let mainImgElement = $state<HTMLImageElement | null>(null);
    let secImgElement = $state<HTMLImageElement | null>(null);

    // VR Scene reference and controls
    let vrSceneRef = $state<any>(null);
    let mirrorCamera = $state(false);

    function handleRecenter() {
        vrSceneRef?.recenterTeleopRig();
    }

    function handleToggleMirror() {
        mirrorCamera = !mirrorCamera;
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === "r" || e.key === "R" || e.key === "c" || e.key === "C") {
            handleRecenter();
        } else if (e.key === "m" || e.key === "M" || e.key === "f" || e.key === "F") {
            handleToggleMirror();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
    <title>revo (VR)</title>
</svelte:head>

<div
    class="relative w-screen h-screen overflow-hidden bg-[#0c0c0c] text-white select-none font-sans"
>
    <!-- Main Camera Feed (Fullscreen Background - Camera 3) -->
    <div class="absolute inset-0 z-0 bg-[#08080a] flex items-center justify-center overflow-hidden">
        <!-- Live MJPEG Stream from camera_server.py -->
        <img
            bind:this={mainImgElement}
            crossorigin="anonymous"
            src={mainStreamUrl}
            alt="Main Camera Stream"
            class="w-full h-full object-cover select-none pointer-events-none transition-opacity duration-300 {mainStreamConnected
                ? 'opacity-90'
                : 'opacity-0'} {mirrorCamera ? '-scale-x-100' : ''}"
            onload={() => (mainStreamConnected = true)}
            onerror={() => (mainStreamConnected = false)}
        />

        <!-- Minimal Standby Camera Grid (visible when camera is offline or connecting) -->
        {#if !mainStreamConnected}
            <div
                class="absolute inset-0 flex flex-col items-center justify-center text-zinc-700 select-none pointer-events-none"
            >
                <div
                    class="absolute inset-0 bg-[radial-gradient(#18191e_1px,transparent_1px)] [background-size:28px_28px] opacity-40"
                ></div>
                <div class="absolute inset-x-0 top-1/2 h-[1px] bg-white/[0.03]"></div>
                <div class="absolute inset-y-0 left-1/2 w-[1px] bg-white/[0.03]"></div>

                <div class="relative z-10 flex flex-col items-center gap-2">
                    <div
                        class="flex items-center gap-2 px-3.5 py-1 bg-[#121316]/80 border border-white/[0.06] backdrop-blur-md"
                    >
                        <span class="w-2 h-2 bg-amber-500/80 animate-pulse"></span>
                        <span
                            class="text-[11px] font-mono font-medium tracking-wider text-zinc-300 uppercase"
                            >CAM 03 // MAIN TELEOP</span
                        >
                    </div>
                    <span class="text-[10px] font-mono text-zinc-600"
                        >Connecting to stream on port 8080...</span
                    >
                </div>
            </div>
        {/if}
    </div>

    <!-- Fullscreen 3D WebXR Canvas -->
    <div class="absolute inset-0 z-10">
        <Canvas shadows={THREE.PCFShadowMap}>
            <VRScene
                bind:this={vrSceneRef}
                bind:mirrorCamera
                {mainImgElement}
                {secImgElement}
                onsessionstart={() => (isVrPresenting = true)}
                onsessionend={() => (isVrPresenting = false)}
            />
        </Canvas>
    </div>

    <!-- Top Left: Minimal Nav Pill -->
    <a
        href="/"
        class="fixed top-6 left-6 z-30 px-3.5 py-1.5 bg-muted border border-white/[0.08] backdrop-blur-xl flex items-center gap-2 text-xs font-semibold text-zinc-300 hover:text-white transition-colors"
    >
        <ArrowLeft class="w-3.5 h-3.5" />
        <span>Dashboard</span>
    </a>

    <!-- Top Left: Floating Window for Secondary Camera Feed (PIP - Left Camera 1) -->
    <div
        class="fixed top-18 left-6 z-30 w-64 bg-[#121316]/85 backdrop-blur-xl border border-white/[0.08] shadow-2xl overflow-hidden pointer-events-auto"
    >
        <div
            class="flex items-center justify-between px-3.5 py-2 border-b border-white/[0.06] bg-white/[0.02]"
        >
            <div class="flex items-center gap-2">
                <span
                    class="w-1.5 h-1.5 rounded-full {secondaryStreamConnected
                        ? 'bg-emerald-400'
                        : 'bg-zinc-500'}"
                ></span>
                <span
                    class="text-[10px] font-mono font-medium tracking-wider text-zinc-300 uppercase"
                    >CAM 01 // LEFT AUX</span
                >
            </div>
            <span class="text-[9px] font-mono text-zinc-400 uppercase"
                >{secondaryStreamConnected ? "LIVE" : "STANDBY"}</span
            >
        </div>
        <div
            class="relative w-full aspect-video bg-[#090a0d] flex items-center justify-center overflow-hidden"
        >
            <!-- Live MJPEG Stream from camera_server.py -->
            <img
                bind:this={secImgElement}
                crossorigin="anonymous"
                src={secondaryStreamUrl}
                alt="Secondary Camera Stream"
                class="w-full h-full object-cover select-none pointer-events-none transition-opacity duration-300 {secondaryStreamConnected
                    ? 'opacity-100'
                    : 'opacity-0'}"
                onload={() => (secondaryStreamConnected = true)}
                onerror={() => (secondaryStreamConnected = false)}
            />

            {#if !secondaryStreamConnected}
                <div
                    class="absolute inset-0 flex flex-col items-center justify-center gap-1 text-zinc-600 select-none"
                >
                    <span class="text-[10px] font-mono tracking-widest text-zinc-600"
                        >NO SIGNAL</span
                    >
                </div>
            {/if}
        </div>
    </div>

    <!-- Top Right Controls: Recenter, Flip Camera, and VR Trigger -->
    <div class="fixed top-6 right-6 z-30 flex items-center gap-3">
        <!-- Recenter Workspace Button -->
        <button
            onclick={handleRecenter}
            title="Recenter virtual workspace to your current head position (Hotkeys: R or B on Quest)"
            class="px-3.5 py-1.5 bg-[#121316]/80 hover:bg-white/10 active:scale-95 backdrop-blur-xl border border-white/[0.08] text-xs font-semibold tracking-wider text-cyan-300 hover:text-cyan-200 uppercase shadow-lg transition-all cursor-pointer flex items-center gap-1.5"
        >
            <span class="text-sm">⟲</span>
            <span>RECENTER [R]</span>
        </button>

        <!-- Flip / Mirror Camera Button -->
        <button
            onclick={handleToggleMirror}
            title="Toggle horizontal mirror on camera feed (Hotkeys: M or Right Stick)"
            class="px-3.5 py-1.5 bg-[#121316]/80 hover:bg-white/10 active:scale-95 backdrop-blur-xl border border-white/[0.08] text-xs font-semibold tracking-wider {mirrorCamera
                ? 'text-amber-300 border-amber-500/30'
                : 'text-zinc-300'} hover:text-white uppercase shadow-lg transition-all cursor-pointer flex items-center gap-1.5"
        >
            <span>{mirrorCamera ? "MIRRORED" : "NORMAL"} [M]</span>
        </button>

        <!-- WebXR Button -->
        <XRButton
            mode="immersive-vr"
            styled={false}
            sessionInit={{
                optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking", "layers"]
            }}
            onerror={(err: any) => {
                console.error("[WebXR Error]:", err);
                vrErrorMessage = err?.message || "Failed to start VR. Check Oculus Link / Headset.";
            }}
            class="px-4 py-1.5 bg-[#121316]/80 hover:bg-white/10 active:scale-95 backdrop-blur-xl border border-white/[0.08] text-xs font-semibold tracking-wider text-zinc-300 hover:text-white uppercase shadow-lg transition-all cursor-pointer flex items-center gap-2"
        >
            {#snippet children(payload?: { state?: string })}
                {#if payload?.state === "supported" || !payload}
                    <span
                        class="w-2 h-2 {isVrPresenting
                            ? 'bg-emerald-400 animate-ping'
                            : 'bg-blue-400'}"
                    ></span>
                    <span>{isVrPresenting ? "EXIT VR" : "ENTER VR"}</span>
                {:else if payload?.state === "unsupported"}
                    <span class="w-2 h-2 bg-amber-400"></span>
                    <span class="text-amber-300">NO VR HEADSET DETECTED</span>
                {:else if payload?.state === "insecure"}
                    <span class="w-2 h-2 bg-rose-400"></span>
                    <span class="text-rose-300">HTTPS REQUIRED</span>
                {:else if payload?.state === "blocked"}
                    <span class="w-2 h-2 bg-rose-400"></span>
                    <span class="text-rose-300">VR PERMISSION BLOCKED</span>
                {/if}
            {/snippet}
        </XRButton>
    </div>

    <!-- Optional VR Error banner if one occurred -->
    {#if vrErrorMessage}
        <div
            class="fixed top-18 right-6 z-30 max-w-sm px-4 py-2 bg-red-950/80 border border-red-500/40 text-red-200 text-xs font-mono shadow-xl flex items-center justify-between gap-3"
        >
            <span>{vrErrorMessage}</span>
            <button
                class="text-red-400 hover:text-white text-sm"
                onclick={() => (vrErrorMessage = null)}>✕</button
            >
        </div>
    {/if}

    <!-- Bottom Infotainment Bar: Three Minimal Out-Of-The-Way Widgets -->
    <div
        class="fixed bottom-6 left-6 right-6 z-20 flex items-end justify-between pointer-events-none"
    >
        <!-- 1. Bottom Left: Speedometer Gauge -->
        <div class="pointer-events-auto flex items-end">
            <div class="w-[180px] h-[180px] flex items-center justify-center overflow-visible">
                <div class="scale-[0.65] origin-center">
                    <Speedometer off={false} />
                </div>
            </div>
        </div>

        <!-- 2. Middle: Long Div For Future User Widgets & Minimal Clutch Status -->
        <div
            class="pointer-events-auto flex-1 max-w-2xl h-20 mx-6 bg-muted flex items-center justify-between px-6 transition-all"
        >
            <div class="flex items-center gap-3">
                <div class="flex flex-col">
                    <span class="text-[10px] font-mono uppercase tracking-wider text-zinc-500"
                        >Right Trigger Clutch</span
                    >
                    <div class="flex items-center gap-2 mt-0.5">
                        <span
                            class="text-xs font-mono font-semibold tracking-wide {servoController.liveReplicate
                                ? 'text-emerald-300'
                                : 'text-zinc-400'}"
                        >
                            {!servoController.liveReplicate
                                ? "released bruh please press trigger"
                                : "ENGAGED uhh be careful"}
                        </span>
                    </div>
                </div>
            </div>

            <div
                class="flex items-center gap-6 text-xs font-mono text-zinc-400 border-l border-white/[0.06] pl-6"
            >
                <div>
                    <span class="text-[10px] text-zinc-500 block uppercase">Gripper [A]</span>
                    <span
                        class="font-medium {servoController.activeJogs[3]
                            ? 'text-emerald-400'
                            : 'text-zinc-200'}"
                    >
                        {servoController.activeJogs[3] ? 'GRIPPING' : 'READY'}
                    </span>
                </div>
                <div>
                    <span class="text-[10px] text-zinc-500 block uppercase">IK Solver</span>
                    <span class="text-zinc-200 font-medium"
                        >{servoController.ikSuccess ? "ACTIVE" : "LIMIT"}</span
                    >
                </div>
            </div>
        </div>

        <!-- 3. Bottom Right: Clean Infotainment Status Card -->
        <div class="pointer-events-auto flex items-end">
            <div
                class="min-w-[210px] h-20 px-4 py-3 bg-[#121316]/85 bg-muted flex flex-col justify-between"
            >
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="relative flex h-2 w-2">
                            {#if isConnected}
                                <span
                                    class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"
                                ></span>
                                <span
                                    class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"
                                ></span>
                            {:else}
                                <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"
                                ></span>
                            {/if}
                        </span>
                        <span class="text-xs font-semibold tracking-wider text-zinc-200">
                            {isConnected ? "it good :)" : "CONNECTING"}
                        </span>
                    </div>
                    <span
                        class="text-[11px] font-mono font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-500/20 px-2 py-0.5"
                    >
                        {onlineCount}/7 OK
                    </span>
                </div>

                <div
                    class="flex items-center justify-between text-xs text-zinc-400 pt-1 border-t border-white/[0.05]"
                >
                    <div class="flex items-center gap-1.5 font-mono">
                        <span class="text-zinc-500">BUS</span>
                        <span class="text-zinc-200 font-medium">{voltage6V}V</span>
                    </div>
                    <div class="flex items-center gap-1.5 font-mono">
                        <span class="text-zinc-500">LINK</span>
                        <span class="text-zinc-200 font-medium"
                            >{servoController.rateHz || 20}Hz</span
                        >
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
