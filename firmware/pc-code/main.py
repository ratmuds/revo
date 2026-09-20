import json
import math
import time
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200

# temporary testing thingy to like only do one motor this prob doesnt work anymore tho :(
TEST_ONLY_SERVO_ID = None

# Shared state
state = {"joints": [], "counter": 0}
state_lock = threading.Lock()

cmd = {
    "magic": "REVO",
    "servos": [
        {"id": 0, "a": 0, "c": 500, "rgb": [255, 0, 0], "h": 0, "jog": 0},
        {"id": 1, "a": 0, "c": 400, "rgb": [255, 255, 0], "h": 0, "jog": 0},
        {"id": 2, "a": 0, "c": 600, "rgb": [10, 0, 0], "h": 0, "jog": 0},
        {"id": 3, "a": 0, "c": 500, "rgb": [255, 255, 0], "h": 0, "jog": 0},
        {"id": 4, "a": 90, "c": 0, "rgb": [0, 0, 0], "h": 0, "jog": 0},
        {"id": 5, "a": 90, "c": 0, "rgb": [0, 0, 0], "h": 0, "jog": 0},
        {"id": 6, "a": 90, "c": 0, "rgb": [0, 0, 0], "h": 0, "jog": 0},
    ],
}
cmd_lock = threading.Lock()
home_until = [0.0] * 7  # one-shot home window per servo


def apply_cmd(data):
    try:
        sid = int(data.get("id"))
    except (TypeError, ValueError):
        return
    if sid < 0 or sid > 6:
        return
    s = cmd["servos"][sid]
    action = data.get("action")
    if action == "calibrate":
        home_until[sid] = time.time() + 3.0
        s["jog"] = 0
        s["h"] = 1
        s["a"] = 0
        return
    if action == "set_angle":
        s["jog"] = 0
        s["h"] = 0
        if "deg" in data:
            try:
                deg = float(data["deg"])
                if sid < 4:
                    s["a"] = int(round(deg * 10))
                else:
                    s["a"] = int(round(max(0, min(270, deg))))
            except (ValueError, TypeError):
                pass
        elif "a" in data:
            s["a"] = int(data["a"])
        return
    d = data.get("dir")
    if sid < 4:
        # RS485 MG996R continuous servo: raw PWM jog (90 = rest)
        s["h"] = 0
        if d == "back":
            s["jog"] = 1
            s["a"] = 70
        elif d == "forth":
            s["jog"] = 1
            s["a"] = 110
        elif d == "stop":
            s["jog"] = 0
            # Hold at the current measured angle (avoids snapping back to 90)
            with state_lock:
                for j in state.get("joints", []):
                    if j.get("id") == sid and j.get("o"):
                        s["a"] = int(j.get("ra", 0))
                        break
    else:
        # DS5180 local PWM servo: real angle, step by 1 degree
        s["jog"] = 0
        s["h"] = 0
        a = int(s.get("a", 90))
        if d == "back":
            a -= 1
        elif d == "forth":
            a += 1
        a = max(0, min(270, a))
        s["a"] = a


def serial_thread():
    ser = None
    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=0.1)
            print(f"Connected to Pico on {PORT}")
            break
        except Exception as e:
            print(f"Serial open failed ({e}); retrying in 2s...")
            time.sleep(2)
    time.sleep(2)
    while True:
        with cmd_lock:
            for i in range(7):
                if time.time() > home_until[i]:
                    cmd["servos"][i]["h"] = 0
            out = json.dumps(cmd)
        try:
            ser.write((out + "\n").encode())
            ser.flush()
        except Exception as e:
            print("Serial write error:", e)
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(1)
            try:
                ser = serial.Serial(PORT, BAUD, timeout=0.1)
                print(f"Reconnected to Pico on {PORT}")
            except Exception:
                pass
            continue
        start = time.time()
        line = ""
        while time.time() - start < 0.2:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", "replace").strip()
                    if line:
                        break
            except Exception:
                pass
            time.sleep(0.001)
        if line:
            try:
                d = json.loads(line)
                if d.get("magic") == "STAT":
                    with state_lock:
                        state["joints"] = d.get("joints", [])
                        state["counter"] = d.get("counter")
            except Exception:
                pass
        time.sleep(0.05)


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revo Servo Control</title>
<style>
  :root { --bg:#111; --panel:#1b1b1b; --line:#2c2c2c; --text:#e6e6e6; --dim:#9a9a9a; --accent:#3da9fc; --warn:#ff5c5c; --ok:#5ad469; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:14px/1.4 ui-monospace, Menlo, Consolas, monospace; }
  header { padding:12px 16px; border-bottom:1px solid var(--line); }
  h1 { font-size:16px; margin:0; font-weight:600; }
  #grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; padding:16px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; }
  .card h2 { margin:0 0 8px; font-size:14px; display:flex; justify-content:space-between; align-items:center; }
  .id { color:var(--dim); font-weight:400; }
  .online { color:var(--ok); } .offline { color:var(--warn); }
  .rows { color:var(--dim); margin:8px 0; }
  .rows b { color:var(--text); font-weight:600; }
  .badge { font-size:11px; padding:1px 6px; border:1px solid var(--line); border-radius:10px; color:var(--dim); }
  .badge.cal { color:var(--ok); border-color:var(--ok); }
  .angle-row { display:flex; gap:8px; margin-top:8px; }
  .angle-row input { flex:1; background:#161616; border:1px solid var(--line); border-radius:6px; color:var(--text); padding:8px 10px; font:inherit; font-size:13px; outline:none; }
  .angle-row input:focus { border-color:var(--accent); }
  .btns { display:flex; gap:8px; margin-top:8px; }
  button { flex:1; background:#222; color:var(--text); border:1px solid var(--line); border-radius:6px; padding:10px 0; font:inherit; cursor:pointer; user-select:none; -webkit-user-select:none; touch-action:none; }
  button:hover { background:#2a2a2a; }
  button:active { background:var(--accent); color:#000; }
  button.cal { flex:0 0 auto; padding:10px 12px; }
  button.send-angle { flex:0 0 auto; padding:8px 14px; background:#222; border-color:var(--line); }
  .hint { color:var(--dim); font-size:11px; margin-top:6px; }
</style>
</head>
<body>
<header><h1>Revo Servo Control</h1></header>
<div id="grid"></div>
<script>
const grid = document.getElementById('grid');
const cards = {};
const timers = {};

function fmt(n, d=1){ return (n===undefined||n===null)?'-':Number(n).toFixed(d); }

function ensureCard(id){
  if(cards[id]) return cards[id];
  const el = document.createElement('div');
  el.className = 'card';
  el.innerHTML = `
    <h2><span>Motor <span class="id">#${id}</span></span>
        <span class="badge" id="type-${id}"></span></h2>
    <div class="rows" id="rows-${id}"></div>
    <div class="angle-row">
      <input type="number" id="angle-input-${id}" placeholder="Angle (&deg;)" step="any">
      <button class="send-angle" id="send-angle-${id}">Send Angle</button>
    </div>
    <div class="btns">
      <button id="back-${id}">&#9664; Back</button>
      <button id="forth-${id}">Forth &#9654;</button>
      <button class="cal" id="cal-${id}">Calibrate</button>
    </div>
    <div class="hint" id="hint-${id}"></div>`;
  grid.appendChild(el);
  cards[id] = el;

  const continuous = id < 4;
  const angleInput = document.getElementById('angle-input-' + id);
  const sendAngle = document.getElementById('send-angle-' + id);
  angleInput.placeholder = continuous ? 'Angle (0-360\u00B0)' : 'Angle (0-270\u00B0)';

  document.getElementById('type-' + id).textContent = continuous ? 'MG996R' : 'DS5180';
  document.getElementById('hint-' + id).textContent = continuous
    ? 'Hold = raw PWM (80 back / 100 forth / 90 rest)'
    : 'Hold = step angle -/+ 1 deg';

  const back = document.getElementById('back-' + id);
  const forth = document.getElementById('forth-' + id);
  const cal = document.getElementById('cal-' + id);

  const postCmd = (obj) => fetch('/cmd', {method:'POST', headers:{'Content-Type':'text/plain'}, body: JSON.stringify(obj)});
  const stop = () => {
    if (timers[id]) { clearInterval(timers[id]); timers[id] = null; }
    postCmd({id, dir:'stop'});
  };
  const startHold = (dir) => {
    postCmd({id, dir});
    if (timers[id]) clearInterval(timers[id]);
    timers[id] = setInterval(() => postCmd({id, dir}), 100);
    back.onmouseup = stop; back.onmouseleave = stop;
    forth.onmouseup = stop; forth.onmouseleave = stop;
    back.ontouchend = stop; forth.ontouchend = stop;
  };
  back.onmousedown = () => startHold('back');
  forth.onmousedown = () => startHold('forth');
  back.ontouchstart = (e) => { e.preventDefault(); startHold('back'); };
  forth.ontouchstart = (e) => { e.preventDefault(); startHold('forth'); };

  const submitAngle = () => {
    const val = parseFloat(angleInput.value);
    if (!isNaN(val)) {
      postCmd({id, action:'set_angle', deg: val});
    }
  };
  sendAngle.onclick = submitAngle;
  angleInput.onkeydown = (e) => {
    if (e.key === 'Enter') submitAngle();
  };

  cal.onclick = () => postCmd({id, action:'calibrate'});
  return el;
}

function render(state){
  const joints = state.joints || [];
  for(const j of joints){
    const id = j.id;
    ensureCard(id);
    const on = j.o;
    const rows = document.getElementById('rows-' + id);
    if(!on){
      rows.innerHTML = '<span class="offline">OFFLINE</span>';
      continue;
    }
    const cal = j.cal;
    const type = document.getElementById('type-' + id);
    if(cal) type.classList.add('cal'); else type.classList.remove('cal');
    let html = '';
    html += `Angle: <b>${fmt(j.a/10)}&deg;</b> &nbsp; Real: <b>${fmt(j.ra/10)}&deg;</b><br>`;
    html += `Total: <b>${j.ta}</b> raw &nbsp; CPR: <b>${j.cpr}</b><br>`;
    html += `Temp: <b>${j.t}&deg;C</b> &nbsp; Curr: <b>${j.c}mA</b> &nbsp; Volt: <b>${fmt(j.v/1000,2)}V</b><br>`;
    html += `Magnet: <b>${j.m}</b> &nbsp; Homed: <b>${j.h}</b> &nbsp; FW: <b>${j.f}</b> &nbsp; CHK: <b>${j.chk?'OK':'BAD'}</b>`;
    rows.innerHTML = html;
  }
  document.getElementById('grid').querySelectorAll('.card').forEach(()=>{});
}

const es = new EventSource('/events');
es.onmessage = (e) => { try { render(JSON.parse(e.data)); } catch(_){} };
es.onerror = () => { /* auto-reconnect */ };
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ("", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_cors()
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif clean_path in ("/events", "/api/events"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_cors()
            self.end_headers()
            try:
                while True:
                    with state_lock:
                        payload = json.dumps(state)
                    self.wfile.write(("data: " + payload + "\n\n").encode())
                    self.wfile.flush()
                    time.sleep(0.05)
            except Exception:
                pass
        elif clean_path in ("/fk", "/api/fk"):
            try:
                import kinematics
                # Compute FK using current commanded or measured angles
                current_rad = [0.0] * len(kinematics.JOINTS)
                with cmd_lock:
                    for i, joint in enumerate(kinematics.JOINTS):
                        sid = joint["servo_id"]
                        if sid < len(cmd["servos"]):
                            deg = cmd["servos"][sid].get("a", 0)
                            if sid < 4:
                                deg = deg / 10.0
                            current_rad[i] = math.radians(deg)
                T_ee, _, _ = kinematics.forward_kinematics(current_rad)
                pos_urdf = [float(p) for p in T_ee[:3, 3]]
                pos_three = [pos_urdf[0] * 10.0, pos_urdf[2] * 10.0, -pos_urdf[1] * 10.0]
                resp = {
                    "ok": True,
                    "ee_pos_urdf": pos_urdf,
                    "ee_pos_three": pos_three,
                    "joints_rad": current_rad
                }
            except Exception as e:
                resp = {"ok": False, "error": str(e)}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors()
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ("/cmd", "/api/cmd"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except Exception:
                data = {}
            apply_cmd(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors()
            self.end_headers()
            self.wfile.write(b'{"ok":1}')
        elif clean_path in ("/ik", "/api/ik"):
            try:
                import kinematics
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)

                target = data.get("target", [0.5, -0.67, 0.71])
                coords = data.get("coords", "urdf")
                if coords == "threejs":
                    # Convert Three.js scene coordinates (Y up, scaled 10) to URDF coordinates (Z up, meters)
                    target_urdf = [
                        target[0] / 10.0,
                        -target[2] / 10.0,
                        target[1] / 10.0,
                    ]
                else:
                    target_urdf = [float(target[0]), float(target[1]), float(target[2])]

                init_angles = data.get("initial_angles", None)
                sol = kinematics.solve_ik(target_urdf, initial_angles=init_angles)

                # Format response with both coordinate frames
                achieved = sol["achieved_pos"]
                achieved_three = [
                    round(achieved[0] * 10.0, 4),
                    round(achieved[2] * 10.0, 4),
                    round(-achieved[1] * 10.0, 4),
                ]
                target_three = [
                    round(target_urdf[0] * 10.0, 4),
                    round(target_urdf[2] * 10.0, 4),
                    round(-target_urdf[1] * 10.0, 4),
                ]

                apply_live = data.get("apply_live", False)
                single_sid = data.get("single_servo_id", TEST_ONLY_SERVO_ID)
                offsets = data.get("offsets", {})
                if apply_live:
                    for sid, deg in sol["servo_angles"].items():
                        # If testing single motor, skip all other servos
                        if single_sid is not None and sid != single_sid:
                            continue

                        # Add joint / wrist offset if provided
                        off_val = 0.0
                        if str(sid) in offsets:
                            try:
                                off_val = float(offsets[str(sid)])
                            except (ValueError, TypeError):
                                pass
                        elif sid in offsets:
                            try:
                                off_val = float(offsets[sid])
                            except (ValueError, TypeError):
                                pass

                        adj_deg = deg + off_val

                        # Map to hardware angle bounds
                        if sid < 4:
                            raw_a = int(round(((90.0 + adj_deg) % 360) * 10))
                            apply_cmd({"id": sid, "action": "set_angle", "a": raw_a})
                        else:
                            clamped_deg = int(round(max(0, min(270, 90.0 + adj_deg))))
                            apply_cmd({"id": sid, "action": "set_angle", "a": clamped_deg})

                sol_resp = {
                    "ok": True,
                    **sol,
                    "target_pos_urdf": target_urdf,
                    "target_pos_three": target_three,
                    "achieved_pos_three": achieved_three,
                }
            except Exception as e:
                sol_resp = {"ok": False, "error": str(e)}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors()
            self.end_headers()
            self.wfile.write(json.dumps(sol_resp).encode())
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def log_message(self, *a):
        pass


def main():
    t = threading.Thread(target=serial_thread, daemon=True)
    t.start()
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("Web UI at http://localhost:8000  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
