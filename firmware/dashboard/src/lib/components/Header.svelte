<script lang="ts">
	import { servoController } from '../stores/servoStore.svelte';

	let isEmergencyStopped = $state(false);

	function handleEmergencyStop() {
		isEmergencyStopped = true;
		for (let i = 0; i < 7; i++) {
			servoController.stopJog(i);
		}
		setTimeout(() => {
			isEmergencyStopped = false;
		}, 1500);
	}
</script>

<header class="h-12 border-b border-white/[0.06] bg-[#0c0c0c] px-4 flex items-center justify-between select-none shrink-0">
	<!-- Left: Brand & Live Status -->
	<div class="flex items-center gap-3">
		<span class="text-[14px] font-semibold text-white tracking-tight">Revo</span>

		<div class="flex items-center gap-1.5 text-[12px] text-[#737373]">
			<span
				class="w-1.5 h-1.5 rounded-full {servoController.connectionState === 'connected'
					? 'bg-emerald-400'
					: servoController.connectionState === 'connecting'
						? 'bg-amber-400 animate-pulse'
						: 'bg-[#444]'}"
			></span>
			<span>{servoController.connectionState === 'connected' ? 'Live' : servoController.connectionState === 'connecting' ? 'Connecting...' : 'Disconnected'}</span>
			{#if servoController.connectionState === 'connected'}
				<span class="text-[#444]">·</span>
				<span class="tabular-nums">#{servoController.packetCounter}</span>
				<span class="text-[#444]">·</span>
				<span class="tabular-nums">{servoController.rateHz} Hz</span>
			{/if}
		</div>
	</div>

	<!-- Right: Minimal Actions -->
	<div class="flex items-center gap-1.5">
		<button
			onclick={() => servoController.restPose()}
			class="px-2.5 py-1 text-[12px] rounded-md text-[#a3a3a3] hover:text-white bg-[#171717] hover:bg-[#222] border border-white/[0.06] hover:border-white/[0.12] transition-colors"
		>
			Rest
		</button>
		<button
			onclick={() => servoController.zeroAll()}
			class="px-2.5 py-1 text-[12px] rounded-md text-[#a3a3a3] hover:text-white bg-[#171717] hover:bg-[#222] border border-white/[0.06] hover:border-white/[0.12] transition-colors"
		>
			Zero
		</button>
		<button
			onclick={() => servoController.calibrateAll()}
			class="px-2.5 py-1 text-[12px] rounded-md text-[#a3a3a3] hover:text-white bg-[#171717] hover:bg-[#222] border border-white/[0.06] hover:border-white/[0.12] transition-colors"
		>
			Calibrate
		</button>

		<button
			onclick={handleEmergencyStop}
			class="px-2.5 py-1 text-[12px] rounded-md transition-colors font-medium
				{isEmergencyStopped
				? 'bg-red-500 text-white'
				: 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20'}"
		>
			Stop
		</button>
	</div>
</header>
