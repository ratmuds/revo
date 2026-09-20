# REVO Servo Telemetry & Kinematics Dashboard

A minimalist, high-performance SvelteKit dashboard with real-time servo telemetry, low-latency control, live waveform graphs, and an interactive Tesla FSD-inspired 3D kinematic arm viewport built with Three.js.

## 🚀 Quick Start

### 1. Launch the Web Dashboard
```bash
cd dashboard
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 2. Connect to Hardware (Optional)
To stream live telemetry from the Raspberry Pi Pico 2 on COM3:
```bash
# In the repository root
python webui.py COM3
```
The dashboard automatically connects to `http://localhost:8000` via Server-Sent Events (`/events`) and POST commands (`/cmd`). If no hardware is connected, the dashboard seamlessly activates its built-in **Simulation Mode** so you can test all UI controls, sliders, jogs, presets, and 3D kinematics immediately.

---

## ✨ Features
- **Tesla FSD-Style 3D Viewport**: Built with Three.js featuring an obsidian grid plane, coordinate readouts, camera orbit/pan/zoom damping, and live 7-DOF kinematic articulation driven by incoming joint angles.
- **Minimalist Dark Aesthetics**: Deep obsidian backdrop (`#09090b`), high-legibility foreground values paired with same-size supporting midground labels, and subtle crimson accenting.
- **Live Telemetry & Controls**:
  - Continuous RS485 actuators (IDs 0–3: MG996R)
  - Local PWM actuators (IDs 4–6: DS5180)
  - Angle sliders, fine step `±1°`, hold-to-jog (`REV`/`FWD`), and calibration triggers.
- **Waveform Graphs**: Real-time streaming charts for total bus current (`mA`), bus voltage (`V`), and max thermal monitor (`°C`).
- **Motion Macros**: One-click REST, ZERO ALL, CALIBRATE ALL, and cooperative Sine Wave motions.
