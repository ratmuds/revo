export interface JointTelemetry {
	id: number;
	o: number;       // 1 = online, 0 = offline
	a: number;       // commanded angle in tenths of a degree (900 = 90.0°) or degrees
	ra: number;      // real measured angle in tenths of a degree
	ta: number;      // total raw ticks / counts
	cpr: number;     // counts per revolution
	cal: number;     // 1 = calibrated, 0 = uncalibrated
	t: number;       // temperature (°C)
	c: number;       // current (mA)
	v: number;       // voltage (mV, e.g. 7400 = 7.4V)
	m?: number;      // magnet detected flag
	h?: number;      // homed flag
	f?: number;      // firmware version
	chk?: number;    // checksum valid (1 = OK, 0 = BAD)
}

export interface TelemetryPacket {
	magic: 'STAT';
	counter: number;
	joints: JointTelemetry[];
	timestamp?: number;
}

export interface ServoCommandItem {
	id: number;
	a: number;       // target angle
	c?: number;      // current limit or parameter
	rgb?: [number, number, number];
	h?: number;      // home flag
	jog?: number;    // jog mode active
}

export interface ServoCommandPacket {
	magic: 'REVO';
	servos: ServoCommandItem[];
}

export interface TelemetryHistoryPoint {
	time: number;
	totalCurrent: number;
	avgVoltage: number;
	maxTemp: number;
	jointCurrents: number[];
	jointAngles: number[];
}

export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'mock';
