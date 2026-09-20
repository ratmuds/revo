import type { JointTelemetry, TelemetryPacket, TelemetryHistoryPoint, ConnectionState } from '../types';
import { urdfToServoDeg, getMotorIdByJointName, MOTOR_CONFIG } from '../config/robotConfig';

// Default initial state for 7 servos before first packet arrives
const INITIAL_JOINTS: JointTelemetry[] = [
	{ id: 0, o: 0, a: 0, ra: 0, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 1, o: 0, a: 0, ra: 0, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 2, o: 0, a: 0, ra: 0, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 3, o: 0, a: 0, ra: 0, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 4, o: 0, a: 90, ra: 90, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 5, o: 0, a: 90, ra: 90, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 },
	{ id: 6, o: 0, a: 90, ra: 90, ta: 0, cpr: 4096, cal: 0, t: 0, c: 0, v: 0, m: 0, h: 0, f: 0, chk: 1 }
];

export class ServoController {
	joints = $state<JointTelemetry[]>(JSON.parse(JSON.stringify(INITIAL_JOINTS)));
	targetAngles = $state<number[]>([90, 90, 85, 90, 180, 70, 180]);
	currentSetAngles = $state<number[]>([90, 90, 85, 90, 180, 70, 180]);
	interpolateEnabled = $state<Record<number, boolean>>({
		0: MOTOR_CONFIG[0]?.interpolate ?? false,
		1: MOTOR_CONFIG[1]?.interpolate ?? false,
		2: MOTOR_CONFIG[2]?.interpolate ?? false,
		3: MOTOR_CONFIG[3]?.interpolate ?? false,
		4: MOTOR_CONFIG[4]?.interpolate ?? true,
		5: MOTOR_CONFIG[5]?.interpolate ?? true,
		6: MOTOR_CONFIG[6]?.interpolate ?? true
	});
	connectionState = $state<ConnectionState>('disconnected');
	packetCounter = $state<number>(0);
	rateHz = $state<number>(0);
	latencyMs = $state<number>(0);
	history = $state<TelemetryHistoryPoint[]>([]);
	activeJogs = $state<Record<number, 'back' | 'forth' | null>>({});
	backendUrl = $state<string>('');

	// Inverse Kinematics (IK) State
	ikMode = $state<boolean>(false);
	liveReplicate = $state<boolean>(false);
	ikTarget = $state<[number, number, number]>([5.15, 7.15, 6.7]);
	ikAchieved = $state<[number, number, number]>([5.15, 7.15, 6.7]);
	ikErrorMm = $state<number>(0);
	ikSuccess = $state<boolean>(true);
	ikSolvedAngles = $state<Record<string, number>>({});

	// Wrist offsets applied to MG996R orientation motors (motor 0 = wrist_rotate, motor 2 = wrist_lift)
	wristOffsets = $state<Record<number, number>>({
		0: 0,
		2: 0
	});

	// Optional single-motor filter for testing (null = all motors)
	testOnlyServoId = $state<number | null>(null);

	setWristOffset(motorId: number, offsetDeg: number) {
		this.wristOffsets[motorId] = Number(offsetDeg.toFixed(1));
	}

	addWristOffset(motorId: number, deltaDeg: number) {
		const current = this.wristOffsets[motorId] ?? 0;
		let updated = current + deltaDeg;
		if (motorId === 0) {
			// Continuous wrap around -180..180
			updated = ((((updated + 180) % 360) + 360) % 360) - 180;
		} else if (motorId === 2) {
			// Linear clamp -180..180
			updated = Math.max(-180, Math.min(180, updated));
		}
		this.wristOffsets[motorId] = Number(updated.toFixed(1));
	}

	resetWristOffsets() {
		this.wristOffsets[0] = 0;
		this.wristOffsets[2] = 0;
	}

	private eventSource: EventSource | null = null;
	private jogIntervals: Record<number, any> = {};
	private lastPacketTime = performance.now();
	private packetCountWindow = 0;
	private hzTimer: any = null;
	private reconnectTimer: any = null;
	private interpTimer: any = null;

	constructor() {
		this.initHistory();
		if (typeof window !== 'undefined') {
			this.init();
		}
	}

	init() {
		this.connectLive();

		if (typeof window !== 'undefined') {
			this.hzTimer = setInterval(() => {
				this.rateHz = this.packetCountWindow;
				this.packetCountWindow = 0;
			}, 1000);

			this.interpTimer = setInterval(() => {
				this.stepInterpolation();
			}, 40);
		}
	}

	private initHistory() {
		const points: TelemetryHistoryPoint[] = [];
		const now = Date.now();
		for (let i = 40; i >= 0; i--) {
			points.push({
				time: now - i * 200,
				totalCurrent: 0,
				avgVoltage: 0,
				maxTemp: 0,
				jointCurrents: [0, 0, 0, 0, 0, 0, 0],
				jointAngles: [0, 0, 0, 0, 0, 0, 0]
			});
		}
		this.history = points;
	}

	connectLive(url: string = '') {
		if (typeof window === 'undefined') return;

		this.backendUrl = url;
		if (this.eventSource) {
			this.eventSource.close();
			this.eventSource = null;
		}

		this.connectionState = 'connecting';
		const eventUrl = url ? `${url}/events` : '/events';

		try {
			const es = new EventSource(eventUrl);
			this.eventSource = es;

			es.onopen = () => {
				this.connectionState = 'connected';
			};

			es.onmessage = (event) => {
				try {
					const data = JSON.parse(event.data);
					this.handleTelemetry(data);
					this.connectionState = 'connected';
				} catch (e) {
					console.error('Failed parsing telemetry:', e);
				}
			};

			es.onerror = () => {
				this.connectionState = 'disconnected';
				// Auto retry reconnect
				if (!this.reconnectTimer) {
					this.reconnectTimer = setTimeout(() => {
						this.reconnectTimer = null;
						this.connectLive(this.backendUrl);
					}, 2000);
				}
			};
		} catch (e) {
			this.connectionState = 'disconnected';
		}
	}

	handleTelemetry(data: any) {
		const now = performance.now();
		this.latencyMs = Math.round(Math.max(1, now - this.lastPacketTime));
		this.lastPacketTime = now;
		this.packetCountWindow++;

		if (data.counter !== undefined) {
			this.packetCounter = data.counter;
		}

		if (Array.isArray(data.joints)) {
			const updated = [...this.joints];
			for (const inJoint of data.joints) {
				const idx = updated.findIndex((j) => j.id === inJoint.id);
				const isContinuous = inJoint.id < 4;
				const jointData = { ...inJoint };

				if (jointData.o === 0) {
					jointData.c = 0;
					jointData.v = 0;
					jointData.t = 0;
				} else if (!isContinuous && (!jointData.ra || jointData.ra === 0)) {
					// If it's a PWM direct servo (M4-M6) and no physical encoder is present/calibrated,
					// assume actual angle is the commanded angle.
					jointData.ra = jointData.a;
				}

				if (idx >= 0) {
					updated[idx] = { ...updated[idx], ...jointData };
				} else {
					updated.push(jointData as JointTelemetry);
				}
			}
			this.joints = updated;
			this.recordHistory(updated);
		}
	}

	private recordHistory(joints: JointTelemetry[]) {
		const totalCurrent = joints.reduce((acc, j) => acc + (j.o ? j.c : 0), 0);
		const onlineJoints = joints.filter((j) => j.o && j.v > 0);
		const avgVoltage = onlineJoints.length
			? (onlineJoints.reduce((acc, j) => acc + j.v, 0) / onlineJoints.length) / 1000
			: 0;
		const maxTemp = joints.reduce((max, j) => Math.max(max, j.o ? j.t : 0), 0);

		const point: TelemetryHistoryPoint = {
			time: Date.now(),
			totalCurrent,
			avgVoltage: Number(avgVoltage.toFixed(2)),
			maxTemp,
			jointCurrents: joints.map((j) => j.c),
			jointAngles: joints.map((j) => j.id < 4 ? j.ra / 10 : (j.ra ?? j.a))
		};

		this.history = [...this.history.slice(-49), point];
	}

	async sendCommand(payload: any) {
		try {
			const cmdUrl = this.backendUrl ? `${this.backendUrl}/cmd` : '/cmd';
			const res = await fetch(cmdUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'text/plain' },
				body: JSON.stringify(payload)
			});
			return await res.json();
		} catch (e) {
			console.error('Failed sending command:', e);
			return { error: e };
		}
	}

	setJointGoal(id: number, angleDeg: number) {
		const config = MOTOR_CONFIG[id];
		const max = config?.maxServoDeg ?? (id < 4 ? 360 : 270);
		const min = config?.minServoDeg ?? 0;
		const clamped = Math.max(min, Math.min(max, angleDeg));
		this.targetAngles[id] = Number(clamped.toFixed(1));

		if (!this.interpolateEnabled[id]) {
			this.currentSetAngles[id] = this.targetAngles[id];
			this.sendRawAngle(id, this.targetAngles[id]);
		}
	}

	setJointAngle(id: number, angleDeg: number) {
		this.setJointGoal(id, angleDeg);
	}

	private sendRawAngle(id: number, clamped: number) {
		const isContinuous = id < 4;
		const idx = this.joints.findIndex((j) => j.id === id);
		if (idx >= 0) {
			this.joints[idx].a = isContinuous ? Math.round(clamped * 10) : Math.round(clamped);
			if (!this.joints[idx].o) {
				this.joints[idx].ra = isContinuous ? Math.round(clamped * 10) : Math.round(clamped);
			}
		}

		if (isContinuous) {
			this.sendCommand({ id, action: 'set_angle', a: Math.round(clamped * 10) });
		} else {
			this.sendCommand({ id, action: 'set_angle', a: Math.round(clamped) });
		}
	}

	private stepInterpolation() {
		for (let i = 0; i < 7; i++) {
			if (this.interpolateEnabled[i]) {
				const goal = this.targetAngles[i];
				if (goal === undefined) continue;
				const current = this.currentSetAngles[i] ?? goal;
				if (Math.abs(goal - current) > 0.2) {
					const diff = goal - current;
					const maxStep = 1.5; // Smooth stepping (e.g. ~37.5 deg/sec at 40ms interval)
					if (Math.abs(diff) <= maxStep) {
						this.currentSetAngles[i] = goal;
					} else {
						this.currentSetAngles[i] += Math.sign(diff) * maxStep;
					}
					const sent = Number(this.currentSetAngles[i].toFixed(1));
					this.sendRawAngle(i, sent);
				}
			}
		}
	}

	startJog(id: number, dir: 'back' | 'forth') {
		this.activeJogs[id] = dir;
		this.sendCommand({ id, dir });

		if (this.jogIntervals[id]) clearInterval(this.jogIntervals[id]);
		this.jogIntervals[id] = setInterval(() => {
			this.sendCommand({ id, dir });
		}, 100);
	}

	stopJog(id: number) {
		this.activeJogs[id] = null;
		if (this.jogIntervals[id]) {
			clearInterval(this.jogIntervals[id]);
			delete this.jogIntervals[id];
		}
		this.sendCommand({ id, dir: 'stop' });
	}

	calibrateJoint(id: number) {
		this.sendCommand({ id, action: 'calibrate' });
	}

	calibrateAll() {
		for (let i = 0; i < 7; i++) {
			setTimeout(() => this.calibrateJoint(i), i * 150);
		}
	}

	zeroAll() {
		for (let i = 0; i < 7; i++) {
			this.setJointAngle(i, i < 4 ? 90 : 0);
		}
	}

	restPose() {
		const restAngles = [90, 90, 90, 90, 30, 30, 30];
		restAngles.forEach((a, i) => this.setJointAngle(i, a));
	}

	async solveIK(
		targetPos: [number, number, number],
		applyLive: boolean = false,
		coords: 'urdf' | 'threejs' = 'threejs'
	) {
		try {
			this.ikTarget = targetPos;
			const ikUrl = this.backendUrl ? `${this.backendUrl}/ik` : '/ik';
			const res = await fetch(ikUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					target: targetPos,
					coords: coords,
					apply_live: false, // Backend does not send to motors; frontend dispatches using MOTOR_CONFIG
					offsets: this.wristOffsets
				})
			});
			const data = await res.json();
			if (data.ok) {
				this.ikSuccess = data.success ?? true;
				this.ikErrorMm = Math.round((data.error_m ?? 0) * 1000);
				if (data.achieved_pos_three) {
					this.ikAchieved = data.achieved_pos_three;
				}
				if (data.angles_deg) {
					this.ikSolvedAngles = data.angles_deg;
					if (applyLive) {
						for (const [jointName, deg] of Object.entries(data.angles_deg)) {
							const sid = getMotorIdByJointName(jointName);
							if (sid === undefined) continue;
							if (this.testOnlyServoId !== null && sid !== this.testOnlyServoId) {
								continue;
							}
							const offset = this.wristOffsets[sid] ?? 0;
							const urdfDeg = Number(deg) + offset;
							// Convert URDF angle to physical servo angle using MOTOR_CONFIG
							const physicalServoDeg = urdfToServoDeg(sid, urdfDeg);
							this.setJointGoal(sid, physicalServoDeg);
						}
					}
				}
				return data;
			}
			return null;
		} catch (e) {
			console.error('solveIK error:', e);
			return null;
		}
	}

	async fetchFK() {
		try {
			const fkUrl = this.backendUrl ? `${this.backendUrl}/fk` : '/fk';
			const res = await fetch(fkUrl);
			const data = await res.json();
			if (data.ok && data.ee_pos_three) {
				this.ikAchieved = data.ee_pos_three;
				this.ikTarget = data.ee_pos_three;
				return data.ee_pos_three;
			}
		} catch (e) {
			console.error('fetchFK error:', e);
		}
		return null;
	}

	destroy() {
		if (this.eventSource) this.eventSource.close();
		if (this.hzTimer) clearInterval(this.hzTimer);
		if (this.interpTimer) clearInterval(this.interpTimer);
		if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
		Object.values(this.jogIntervals).forEach((t) => clearInterval(t));
	}
}

export const servoController = new ServoController();
