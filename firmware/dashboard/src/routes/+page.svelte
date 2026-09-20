<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { servoController } from "$lib/stores/servoStore.svelte";
    import * as Resizable from "$lib/components/ui/resizable/index.js";
    import Render from "$lib/components/Render.svelte";
    import Speedometer from "$lib/components/Speedometer.svelte";
    import * as Card from "$lib/components/ui/card/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { fly } from "svelte/transition";
    import RangeBar from "$lib/components/RangeBar.svelte";
    import MotorCard from "$lib/components/MotorCard.svelte";

    import { PowerOff, OctagonX, LayoutGrid, Cpu, Sliders } from "lucide-svelte";

    const RobotStatus = {
        OFFLINE: 0,
        OFF: 1,
        HOMING_REQ: 2,
        HOMING: 3,
        READY: 4,
        ERROR: 5
    } as const;
    type RobotStatus = (typeof RobotStatus)[keyof typeof RobotStatus];

    let robotState: RobotStatus = $state(RobotStatus.READY);

    function switchState(newState: RobotStatus) {
        robotState = newState;
    }

    // View Navigation
    const VIEWS = [
        { id: "overview", label: "Overview", icon: LayoutGrid },
        { id: "motors", label: "Motors", icon: Cpu },
        { id: "controls", label: "Controls", icon: Sliders }
    ] as const;
    type ViewId = (typeof VIEWS)[number]["id"];
    let currentView: ViewId = $state("overview");
    let slideDirection: 1 | -1 = $state(1);

    function setView(view: ViewId) {
        const prevIdx = VIEWS.findIndex((v) => v.id === currentView);
        const nextIdx = VIEWS.findIndex((v) => v.id === view);
        if (prevIdx !== nextIdx) {
            slideDirection = nextIdx > prevIdx ? 1 : -1;
            currentView = view;
        }
    }

    onMount(() => {
        servoController.init();
    });

    onDestroy(() => {
        servoController.destroy();
    });

    // 6V Rail (RS485 joints M0-M3)
    let joints6V = $derived(servoController.joints.filter((j) => j.id < 4 && j.o));
    let voltage6V = $derived(
        joints6V.length > 0
            ? joints6V.reduce((acc, j) => acc + (j.v || 0), 0) / joints6V.length / 1000
            : 0
    );

    // 7V Rail (PWM joints M4-M6)
    let joints7V = $derived(servoController.joints.filter((j) => j.id >= 4 && j.o));
    let voltage7V = $derived(
        joints7V.length > 0
            ? joints7V.reduce((acc, j) => acc + (j.v || 0), 0) / joints7V.length / 1000
            : 0
    );

    // Total Bus Current
    let totalCurrent = $derived(
        servoController.joints.reduce((acc, j) => acc + (j.o ? j.c || 0 : 0), 0)
    );

    // Peak Actuator Temperature
    let peakTemp = $derived(
        servoController.joints.reduce((max, j) => Math.max(max, j.o ? j.t || 0 : 0), 0)
    );
</script>

<svelte:head>
    <title>Revo</title>
</svelte:head>

<div class="fixed w-screen h-12 border-b">
    <div class="flex justify-between h-full">
        <span class="my-auto font-bold mx-3">revo</span>
        <span class="my-auto text-red-500 mx-3 text-sm">offline</span>
    </div>
</div>

<div class="h-screen w-screen">
    <Resizable.PaneGroup direction="horizontal" class="h-screen w-screen border">
        <Resizable.Pane defaultSize={30}>
            {#if robotState === RobotStatus.OFF}
                <div class="flex h-full w-full items-center justify-center">
                    <Speedometer off={true} />
                </div>
            {:else}
                <div class="flex h-full w-full items-center justify-center">
                    <Speedometer off={false} />
                </div>
            {/if}
        </Resizable.Pane>
        <Resizable.Pane defaultSize={40}>
            <!-- Floating E-STOP Button -->
            {#if robotState !== RobotStatus.OFF}
                <button
                    class="fixed bottom-10 left-0 right-0 mx-auto flex w-52 items-center justify-center space-x-2 rounded-full bg-red-800 p-3 px-5 font-semibold z-10"
                >
                    <OctagonX class="h-5 w-5 mr-2" />
                    E-STOP
                </button>
            {/if}

            <Render />
        </Resizable.Pane>
        <Resizable.Pane defaultSize={30}>
            {#if robotState === RobotStatus.OFF}
                <div class="flex h-full items-center justify-center p-6">
                    <button
                        class="bg-blue-500 font-semibold p-3 px-5 rounded-full"
                        onclick={() => switchState(RobotStatus.READY)}
                    >
                        Power On
                    </button>
                </div>
            {:else if robotState === RobotStatus.READY}
                <div
                    class="relative flex h-full w-full items-center justify-center p-6 overflow-hidden"
                >
                    <!-- Views Container -->
                    <div class="w-full max-w-md pr-6">
                        {#key currentView}
                            <div in:fly={{ y: slideDirection * 24, duration: 250, opacity: 0.1 }}>
                                {#if currentView === "overview"}
                                    <Card.Root class="w-full rounded-none shadow-2xl p-1">
                                        <Card.Header
                                            class="px-5 pt-5 pb-4 flex flex-row items-center justify-between"
                                        >
                                            <Card.Title
                                                class="flex items-center gap-2.5 text-base font-bold text-white tracking-tight"
                                            >
                                                <span>Overview</span>
                                                <Badge
                                                    class="bg-[#153422] text-[#2bd666] border-[#2bd666]/30 text-[11px] font-bold tracking-wider px-2.5 py-0.5 rounded-full"
                                                    variant="outline"
                                                >
                                                    READY
                                                </Badge>
                                            </Card.Title>
                                            <Card.Action>
                                                <button
                                                    class="bg-muted hover:bg-yellow-500/50 text-white border border-white/[0.08] font-medium text-xs py-1.5 px-4 rounded-full shadow-sm active:scale-95 transition-all"
                                                >
                                                    Rehome
                                                </button>

                                                <button
                                                    onclick={() => switchState(RobotStatus.OFF)}
                                                    class="bg-muted hover:bg-red-500/50 text-white border border-white/[0.08] font-medium text-xs py-1.5 px-4 rounded-full shadow-sm active:scale-95 transition-all"
                                                >
                                                    Turn Off
                                                </button>
                                            </Card.Action>
                                        </Card.Header>
                                        <Card.Content class="px-5 pb-5 pt-0">
                                            <!-- 2x2 Telemetry Grid -->
                                            <div class="grid grid-cols-2 gap-x-6 gap-y-5">
                                                <!-- Row 1 Col 1: 6V Rail -->
                                                <RangeBar
                                                    label="Voltage (6V)"
                                                    value={voltage6V}
                                                    unit="V"
                                                    mode="range"
                                                    min={5.0}
                                                    max={7.0}
                                                    targetMin={5.7}
                                                    targetMax={6.3}
                                                    formatDecimals={2}
                                                />

                                                <!-- Row 1 Col 2: Bus Current (Lower is better) -->
                                                <RangeBar
                                                    label="Bus Current"
                                                    value={totalCurrent || 1240}
                                                    unit="mA"
                                                    mode="lower-better"
                                                    min={0}
                                                    max={4000}
                                                    warnThreshold={2200}
                                                    critThreshold={3200}
                                                    formatDecimals={0}
                                                />

                                                <!-- Row 2 Col 1: 7V Rail (Range Mode: green around 7V - 7.4V, orange outside) -->
                                                <RangeBar
                                                    label="Voltage (7V)"
                                                    value={voltage7V}
                                                    unit="V"
                                                    mode="range"
                                                    min={6.0}
                                                    max={8.4}
                                                    targetMin={6.8}
                                                    targetMax={7.6}
                                                    formatDecimals={2}
                                                />

                                                <!-- Row 2 Col 2: Peak Temperature (Lower is better) -->
                                                <RangeBar
                                                    label="Peak Temp"
                                                    value={peakTemp}
                                                    unit="°C"
                                                    mode="lower-better"
                                                    min={15}
                                                    max={80}
                                                    warnThreshold={48}
                                                    critThreshold={65}
                                                    formatDecimals={0}
                                                />
                                            </div>

                                            <div
                                                class="flex flex-row items-center justify-between mt-4"
                                            >
                                                <span
                                                    >Motor Status: <span
                                                        class="font-bold text-amber-500"
                                                        >{servoController.joints.filter((j) => j.o)
                                                            .length}/7 OK</span
                                                    ></span
                                                >
                                            </div>
                                        </Card.Content>
                                    </Card.Root>
                                {:else if currentView === "motors"}
                                    <div
                                        class="flex flex-col gap-2.5 max-h-[82vh] overflow-y-auto pr-1 pb-6"
                                    >
                                        {#each servoController.joints as joint (joint.id)}
                                            <MotorCard {joint} />
                                        {/each}
                                    </div>
                                {:else if currentView === "controls"}
                                    <Card.Root class="w-full shadow-2xl p-1 rounded-none">
                                        <Card.Header
                                            class="px-5 pt-5 pb-4 flex flex-row items-center justify-between"
                                        >
                                            <Card.Title
                                                class="flex items-center gap-2.5 text-base font-bold text-white tracking-tight"
                                            >
                                                <span>Controls</span>
                                            </Card.Title>
                                        </Card.Header>
                                        <Card.Content class="px-5 pb-5 pt-1 space-y-4">
                                            <!-- Enable IK Switch -->
                                            <div class="flex items-center justify-between py-2">
                                                <div class="flex flex-col">
                                                    <span class="text-sm font-medium text-white"
                                                        >Inverse Kinematics</span
                                                    >
                                                    <span class="text-xs text-zinc-400"
                                                        >Draggable 3D target in render</span
                                                    >
                                                </div>
                                                <button
                                                    type="button"
                                                    role="switch"
                                                    aria-label="Toggle Inverse Kinematics"
                                                    aria-checked={servoController.ikMode}
                                                    onclick={() =>
                                                        (servoController.ikMode =
                                                            !servoController.ikMode)}
                                                    class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {servoController.ikMode
                                                        ? 'bg-cyan-500'
                                                        : 'bg-zinc-700'}"
                                                >
                                                    <span
                                                        class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out {servoController.ikMode
                                                            ? 'translate-x-5'
                                                            : 'translate-x-0'}"
                                                    ></span>
                                                </button>
                                            </div>

                                            <div class="h-px bg-white/[0.06]"></div>

                                            <!-- Control Motors Switch -->
                                            <div
                                                class="flex items-center justify-between py-2 transition-opacity {servoController.ikMode
                                                    ? 'opacity-100'
                                                    : 'opacity-40 pointer-events-none'}"
                                            >
                                                <div class="flex flex-col">
                                                    <span class="text-sm font-medium text-white"
                                                        >Control Motors</span
                                                    >
                                                    <span class="text-xs text-zinc-400"
                                                        >Stream IK solution to motors</span
                                                    >
                                                </div>
                                                <button
                                                    type="button"
                                                    role="switch"
                                                    aria-label="Toggle Control Motors"
                                                    aria-checked={servoController.liveReplicate}
                                                    disabled={!servoController.ikMode}
                                                    onclick={() =>
                                                        (servoController.liveReplicate =
                                                            !servoController.liveReplicate)}
                                                    class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {servoController.liveReplicate
                                                        ? 'bg-emerald-500'
                                                        : 'bg-zinc-700'}"
                                                >
                                                    <span
                                                        class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out {servoController.liveReplicate
                                                            ? 'translate-x-5'
                                                            : 'translate-x-0'}"
                                                    ></span>
                                                </button>
                                            </div>
                                        </Card.Content>
                                    </Card.Root>
                                {/if}
                            </div>
                        {/key}
                    </div>

                    <!-- Navigation -->
                    <div
                        class="absolute right-1.5 top-1/2 -translate-y-1/2 z-20 flex flex-col gap-1.5 p-1 rounded-full bg-[#18191c]/80 backdrop-blur-md border border-white/[0.08] shadow-lg"
                    >
                        {#each VIEWS as view}
                            {@const Icon = view.icon}
                            {@const isActive = currentView === view.id}
                            <button
                                onclick={() => setView(view.id)}
                                class="flex items-center justify-center w-7 h-7 rounded-full transition-all duration-200 {isActive
                                    ? 'bg-white/15 text-white shadow-sm'
                                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05]'}"
                                title={view.label}
                                aria-label={view.label}
                            >
                                <Icon class="w-3.5 h-3.5" />
                            </button>
                        {/each}
                    </div>
                </div>
            {/if}
        </Resizable.Pane>
    </Resizable.PaneGroup>
</div>
