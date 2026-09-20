/**
 * =============================================================================
 * CENTRAL ROBOT MOTOR-TO-JOINT ASSIGNMENT CONFIGURATION
 * =============================================================================
 * Edit this file to reassign motor IDs (M0–M6) to URDF joints, change directions,
 * degree offsets, or custom display names.
 *
 * URDF Joint Names in robot.urdf:
 *  - "base_rot"
 *  - "shoulder_lift"
 *  - "elbow_lift"
 *  - "wrist_lift"
 *  - "wrist_rotate"
 *  - "end_rotate"
 */

export interface JointMapping {
	motorId: number;
	jointName: string;
	displayName: string;
	type: "PWM" | "RS485";
	direction?: number; // 1 for normal, -1 to invert rotation
	neutralDeg?: number; // physical servo angle for URDF 0 deg (typically 90)
	offsetDeg?: number; // fine calibration degree offset
	minServoDeg?: number; // min safe physical servo limit (default: 0)
	maxServoDeg?: number; // max safe physical servo limit (default: 270 for PWM, 360 for RS485)
	flipDS5180Deg?: boolean; // if true, servo angle is flipped (DS5180 ONLY) from 0-270
	interpolate?: boolean; // if true, the motor angle will be interpolated to the target angle
}

export const MOTOR_CONFIG: Record<number, JointMapping> = {
	// --- RS485 Actuators (Motors 0–3 · MG996R continuous/calibrated) ---
	0: {
		motorId: 0,
		jointName: "wrist_rotate",
		displayName: "Wrist Rotate",
		type: "RS485",
		direction: -1,
		neutralDeg: 90,
		offsetDeg: 0,
		minServoDeg: 0,
		maxServoDeg: 360,
		interpolate: false,
	},
	1: {
		motorId: 1,
		jointName: "end_rotate",
		displayName: "End Rotate",
		type: "RS485",
		direction: -1,
		neutralDeg: 90,
		offsetDeg: 20,
		minServoDeg: 0,
		maxServoDeg: 360,
		interpolate: false,
	},
	2: {
		motorId: 2,
		jointName: "wrist_lift",
		displayName: "Wrist Lift",
		type: "RS485",
		direction: -1,
		neutralDeg: 90,
		offsetDeg: -55,
		minServoDeg: 0,
		maxServoDeg: 360,
		interpolate: false,
	},
	3: {
		motorId: 3,
		jointName: "",
		displayName: "Aux / Gripper",
		type: "RS485",
		direction: -1,
		neutralDeg: 90,
		offsetDeg: 0,
		minServoDeg: 0,
		maxServoDeg: 360,
		interpolate: false,
	},

	// --- Local PWM Motors (Motors 4–6: DS5180 270 deg) ---
	// Interpolate these as they will violently go to the target
	4: {
		motorId: 4,
		jointName: "shoulder_lift",
		displayName: "Shoulder Lift",
		type: "PWM",
		direction: 1,
		neutralDeg: 90,
		offsetDeg: -90,
		minServoDeg: 0,
		maxServoDeg: 270,
		interpolate: true,
	},
	5: {
		motorId: 5,
		jointName: "base_rot",
		displayName: "Base Rot",
		type: "PWM",
		direction: -1,
		neutralDeg: 90,
		offsetDeg: 0,
		minServoDeg: 0,
		maxServoDeg: 270,
		interpolate: true,
	},
	6: {
		motorId: 6,
		jointName: "elbow_lift",
		displayName: "Elbow Lift",
		type: "PWM",
		direction: 1,
		neutralDeg: 90,
		offsetDeg: 45,
		minServoDeg: 0,
		maxServoDeg: 270,
		interpolate: true,
	},
};

/**
 * Helper to lookup joint config by motor ID
 */
export function getMotorJointConfig(motorId: number): JointMapping | undefined {
	return MOTOR_CONFIG[motorId];
}

/**
 * Helper to lookup motor ID by URDF joint name
 */
export function getMotorIdByJointName(jointName: string): number | undefined {
	for (const [idStr, config] of Object.entries(MOTOR_CONFIG)) {
		if (config.jointName === jointName) {
			return Number(idStr);
		}
	}
	return undefined;
}

/**
 * Converts a URDF/IK joint angle (degrees, relative to 0) to a physical Servo angle (0..180 or 0..360)
 */
export function urdfToServoDeg(motorId: number, urdfDeg: number): number {
	const config = MOTOR_CONFIG[motorId];
	if (!config) return urdfDeg;
	const neutral = config.neutralDeg ?? 90;
	const dir = config.direction ?? 1;
	const offset = config.offsetDeg ?? 0;

	if (config.type === "RS485") {
		// Continuous 0..360 deg actuator: wrap cleanly around the circle
		const raw = neutral + urdfDeg * dir + offset;
		return ((raw % 360) + 360) % 360;
	}

	// Local PWM actuators (DS5180 0..270 deg) clamp to linear safe limits
	const min = config.minServoDeg ?? 0;
	const max = config.maxServoDeg ?? 270;
	const servoDeg = neutral + urdfDeg * dir + offset;
	return Math.max(min, Math.min(max, servoDeg));
}

/**
 * Converts a physical Servo angle to a URDF/IK joint angle (degrees, relative to 0)
 */
export function servoToUrdfDeg(motorId: number, servoDeg: number): number {
	const config = MOTOR_CONFIG[motorId];
	if (!config) return servoDeg;
	const neutral = config.neutralDeg ?? 90;
	const dir = config.direction ?? 1;
	const offset = config.offsetDeg ?? 0;

	let urdfDeg = (servoDeg - neutral - offset) * dir;
	if (config.type === "RS485") {
		// Normalize continuous circular angle to URDF revolute joint range [-180, 180]
		urdfDeg = ((((urdfDeg + 180) % 360) + 360) % 360) - 180;
	}

	return urdfDeg;
}
