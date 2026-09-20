<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import * as THREE from "three";
    import { T, useThrelte, useTask } from "@threlte/core";
    import { XR, Controller, Hand, useController } from "@threlte/xr";
    import URDFLoader from "urdf-loader";
    import { servoController } from "$lib/stores/servoStore.svelte";
    import {
        MOTOR_CONFIG,
        servoToUrdfDeg,
        urdfToServoDeg,
        getMotorIdByJointName
    } from "$lib/config/robotConfig";

    const { scene, renderer, camera } = useThrelte();

    let {
        onsessionstart,
        onsessionend,
        mirrorCamera = $bindable(false),
        mainImgElement = null,
        secImgElement = null,
        streamPort = 8080 // Set to your camera server port
    }: {
        onsessionstart?: () => void;
        onsessionend?: () => void;
        mirrorCamera?: boolean;
        mainImgElement?: HTMLImageElement | null;
        secImgElement?: HTMLImageElement | null;
        streamPort?: number;
    } = $props();

    // Dynamic stream host for local network VR (e.g. Meta Quest browser)
    const streamHost =
        typeof window !== "undefined" ? window.location.hostname || "localhost" : "localhost";
    let mainStreamUrl = $derived(`http://${streamHost}:${streamPort}/stream/main`);
    let secStreamUrl = $derived(`http://${streamHost}:${streamPort}/stream/secondary`);

    // --- Teleoperation Rig (Recentered to user's head in VR) ---
    let teleopRig = $state<THREE.Group | undefined>(undefined);
    let monitorGroup = $state<THREE.Group | undefined>(undefined);
    let robotHolder = $state<THREE.Group | undefined>(undefined);
    let xrFrameCount = 0;
    let lastBButtonPressed = false;
    let lastLeftRecenterPressed = false;
    let lastThumbstickPressed = false;

    // --- Controllers ---
    const rightController = useController("right");
    const leftController = useController("left");

    // --- State variables ---
    let robotModel: any = $state(null);
    let ghostRobotModel: any = $state(null);
    let targetGhost = $state<THREE.Mesh | null>(null);

    let isClutchEngaged = $state(false);
    let isGripping = $state(false);

    let isSolving = false;
    let pendingSolve = false;
    let lastSolvedTarget = new THREE.Vector3();
    let ikAngles: Record<string, number> | null = null;

    // --- Stable Canvas & CanvasTexture Initialization ---
    // Initialized immediately so the texture instance remains persistent
    const monitorCanvas = typeof document !== "undefined" ? document.createElement("canvas") : null;
    if (monitorCanvas) {
        monitorCanvas.width = 1024;
        monitorCanvas.height = 576;
    }
    const monitorCtx = monitorCanvas?.getContext("2d") ?? null;
    const monitorTexture = monitorCanvas ? new THREE.CanvasTexture(monitorCanvas) : null;
    if (monitorTexture) {
        monitorTexture.minFilter = THREE.LinearFilter;
        monitorTexture.magFilter = THREE.LinearFilter;
        monitorTexture.colorSpace = THREE.SRGBColorSpace;
    }

    // Explicitly load GeneralSans variable font for HTML5 Canvas context
    if (typeof document !== "undefined" && typeof FontFace !== "undefined") {
        try {
            const font = new FontFace("GeneralSans", "url(/fonts/GeneralSans-Variable.ttf)", {
                style: "normal",
                weight: "100 900"
            });
            font.load()
                .then((loaded) => {
                    document.fonts.add(loaded);
                })
                .catch(() => {});
        } catch (_) {}
    }

    let fallbackMainImg = $state<HTMLImageElement | null>(null);
    let fallbackSecImg = $state<HTMLImageElement | null>(null);
    let lastTextureUpdate = 0;

    export function recenterTeleopRig() {
        if (!teleopRig) return;
        const headPos = new THREE.Vector3();
        const headQuat = new THREE.Quaternion();

        if (renderer.xr.isPresenting) {
            const xrCam = renderer.xr.getCamera();
            const activeCam = xrCam.cameras && xrCam.cameras.length > 0 ? xrCam.cameras[0] : xrCam;
            activeCam.getWorldPosition(headPos);
            activeCam.getWorldQuaternion(headQuat);
        } else if (camera.current) {
            camera.current.getWorldPosition(headPos);
            camera.current.getWorldQuaternion(headQuat);
        } else {
            return;
        }

        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(headQuat);
        forward.y = 0;
        if (forward.lengthSq() < 0.0001) {
            forward.set(0, 0, -1);
        } else {
            forward.normalize();
        }

        const yaw = Math.atan2(-forward.x, -forward.z);

        teleopRig.position.set(headPos.x, 0, headPos.z);
        teleopRig.rotation.set(0, yaw, 0);

        const eyeY = headPos.y > 0.3 ? headPos.y : 1.45;
        if (monitorGroup) {
            monitorGroup.position.set(0, eyeY, -1.4);
        }
        if (robotHolder) {
            robotHolder.position.set(0.22, Math.max(0.4, eyeY - 0.55), -0.55);
        }
    }

    // Defensive telemetry calculations
    let safeJoints = $derived(servoController?.joints ?? []);
    let maxCurrentMa = $derived(
        safeJoints.reduce((max, j) => (j.c >= 3200 ? max : Math.max(max, j.o ? j.c || 0 : 0)), 0)
    );
    let targetLoad = $derived(Math.min(100, Math.max(0, Math.round((maxCurrentMa / 500) * 100))));
    let maxTemp = $derived(safeJoints.reduce((max, j) => Math.max(max, j.o ? j.t || 0 : 0), 0));
    let tempPercent = $derived(
        maxTemp > 0 ? Math.min(100, Math.max(0, Math.round((maxTemp / 80) * 100))) : 0
    );
    let joints6V = $derived(safeJoints.filter((j) => j.id < 4 && j.o));
    let voltage6V = $derived(
        joints6V.length > 0
            ? (joints6V.reduce((acc, j) => acc + (j.v || 0), 0) / joints6V.length / 1000).toFixed(1)
            : "6.0"
    );

    function createToonGradient() {
        const colors = new Uint8Array([70, 170, 255]);
        const gradient = new THREE.DataTexture(colors, colors.length, 1, THREE.RedFormat);
        gradient.minFilter = THREE.NearestFilter;
        gradient.magFilter = THREE.NearestFilter;
        gradient.generateMipmaps = false;
        gradient.needsUpdate = true;
        return gradient;
    }

    const toonGradient = createToonGradient();
    const outlineMaterial = new THREE.LineBasicMaterial({ color: 0x111111, linewidth: 1 });

    function applyToonAndOutlines(model: THREE.Object3D | null) {
        if (!model) return;
        model.traverse((child: any) => {
            if (child.isMesh && child.geometry && !child.userData.toonApplied) {
                child.userData.toonApplied = true;
                child.geometry.computeVertexNormals();

                const originalColor = child.material?.color
                    ? child.material.color.clone()
                    : new THREE.Color(0xd4d4d8);

                child.material = new THREE.MeshToonMaterial({
                    color: originalColor,
                    gradientMap: toonGradient,
                    polygonOffset: true,
                    polygonOffsetFactor: 1,
                    polygonOffsetUnits: 1
                });
                child.castShadow = true;
                child.receiveShadow = true;

                const edges = new THREE.EdgesGeometry(child.geometry, 25);
                const line = new THREE.LineSegments(edges, outlineMaterial);
                child.add(line);
            }
        });
    }

    function applyGhostMaterial(model: THREE.Object3D | null) {
        if (!model) return;
        model.traverse((child: any) => {
            if (child.isMesh && child.geometry) {
                child.userData.ghostApplied = true;
                const originalColor = child.material?.color
                    ? child.material.color.clone()
                    : new THREE.Color(0xd4d4d8);

                child.material = new THREE.MeshStandardMaterial({
                    color: originalColor,
                    transparent: true,
                    opacity: 0.5,
                    depthWrite: false,
                    roughness: 0.5,
                    metalness: 0.1
                });
                child.castShadow = false;
                child.receiveShadow = false;
            }
        });
    }

    function startGripper() {
        if (!isGripping) {
            isGripping = true;
            servoController.startJog(3, "forth");
            pulseController(0.4, 40);
        }
    }

    function stopGripper() {
        if (isGripping) {
            isGripping = false;
            servoController.stopJog(3);
            pulseController(0.2, 25);
        }
    }

    function pulseController(intensity = 0.5, durationMs = 50) {
        try {
            const inputSource = rightController.current?.inputSource;
            const actuators = inputSource?.gamepad?.hapticActuators;
            if (actuators && actuators.length > 0) {
                actuators[0]?.pulse?.(intensity, durationMs);
            }
        } catch (_) {}
    }

    async function triggerIKSolve(targetWorldPos: THREE.Vector3) {
        if (!robotModel || isSolving) {
            if (isSolving) pendingSolve = true;
            return;
        }

        isSolving = true;
        try {
            robotModel.updateMatrixWorld(true);
            const urdfTarget = robotModel.worldToLocal(targetWorldPos.clone());
            const data = await servoController.solveIK(
                [urdfTarget.x, urdfTarget.y, urdfTarget.z],
                isClutchEngaged,
                "urdf"
            );
            if (data?.angles_deg) {
                ikAngles = data.angles_deg;
            }
        } catch (e) {
            console.error("VR IK solve error:", e);
        } finally {
            isSolving = false;
            if (pendingSolve) {
                pendingSolve = false;
                triggerIKSolve(lastSolvedTarget);
            }
        }
    }

    function updateJointsFromTelemetry(model: any) {
        if (!model || !model.joints) return;

        for (const [idStr, mapping] of Object.entries(MOTOR_CONFIG)) {
            const motorId = Number(idStr);
            if (!mapping.jointName) continue;

            const joint = model.joints[mapping.jointName];
            if (!joint?.setJointValue) continue;

            const telemetry = safeJoints.find((j) => j.id === motorId);
            const isContinuous = motorId < 4;

            let physicalServoDeg: number;
            if (telemetry?.o) {
                if (telemetry.ra != null) {
                    physicalServoDeg = isContinuous ? telemetry.ra / 10 : telemetry.ra;
                } else if (telemetry.a != null) {
                    physicalServoDeg = isContinuous ? telemetry.a / 10 : telemetry.a;
                } else {
                    physicalServoDeg =
                        servoController.targetAngles[motorId] ?? mapping.neutralDeg ?? 90;
                }
            } else {
                physicalServoDeg =
                    servoController.targetAngles[motorId] ?? mapping.neutralDeg ?? 90;
            }

            const urdfDeg = servoToUrdfDeg(motorId, physicalServoDeg);
            joint.setJointValue((urdfDeg * Math.PI) / 180);
        }
    }

    function updateRobotJoints() {
        // 1. Update solid robotModel (target/IK state or default pose)
        if (robotModel?.joints) {
            if (ikAngles) {
                for (const [jointName, deg] of Object.entries(ikAngles)) {
                    const joint = robotModel.joints[jointName];
                    if (joint?.setJointValue) {
                        const sid = getMotorIdByJointName(jointName);
                        const offset =
                            (sid !== undefined ? servoController.wristOffsets[sid] : 0) ?? 0;
                        joint.setJointValue(((deg + offset) * Math.PI) / 180);
                    }
                }
            } else {
                updateJointsFromTelemetry(robotModel);
            }
        }

        // 2. Update ghost arm (current physical telemetry state)
        if (ghostRobotModel?.joints) {
            updateJointsFromTelemetry(ghostRobotModel);
        }
    }

    let displayLoad = 0;
    let displayTemp = 0;

    function drawRect(
        ctx: CanvasRenderingContext2D,
        x: number,
        y: number,
        w: number,
        h: number,
        fillStyle?: string,
        strokeStyle?: string,
        lineWidth = 1
    ) {
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        if (fillStyle) {
            ctx.fillStyle = fillStyle;
            ctx.fill();
        }
        if (strokeStyle) {
            ctx.strokeStyle = strokeStyle;
            ctx.lineWidth = lineWidth;
            ctx.stroke();
        }
    }

    function polarToCartesian(centerX: number, centerY: number, radius: number, angleDeg: number) {
        const rad = ((angleDeg - 90) * Math.PI) / 180.0;
        return {
            x: centerX + radius * Math.cos(rad),
            y: centerY + radius * Math.sin(rad)
        };
    }

    function renderVRMonitor() {
        if (!monitorCtx || !monitorCanvas || !monitorTexture) return;
        const ctx = monitorCtx;
        const w = 1024;
        const h = 576;

        // Smooth animations for gauge
        displayLoad += (targetLoad - displayLoad) * 0.2;
        displayTemp += (tempPercent - displayTemp) * 0.2;

        // 1. Draw video feed or standby
        const mainImg = mainImgElement || fallbackMainImg;
        let drawnStream = false;

        if (mainImg && mainImg.naturalWidth > 0 && mainImg.complete) {
            try {
                if (mirrorCamera) {
                    ctx.save();
                    ctx.translate(w, 0);
                    ctx.scale(-1, 1);
                    ctx.drawImage(mainImg, 0, 0, w, h);
                    ctx.restore();
                } else {
                    ctx.drawImage(mainImg, 0, 0, w, h);
                }
                drawnStream = true;
            } catch (_) {}
        }

        if (!drawnStream) {
            // Minimal Standby Screen matching VR page
            ctx.fillStyle = "#08080a";
            ctx.fillRect(0, 0, w, h);

            ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
            ctx.lineWidth = 1;
            for (let x = 0; x < w; x += 32) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, h);
                ctx.stroke();
            }
            for (let y = 0; y < h; y += 32) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }

            // Standby card (no rounded corners)
            const sbW = 260;
            const sbH = 56;
            const sbX = (w - sbW) / 2;
            const sbY = (h - sbH) / 2;
            drawRect(
                ctx,
                sbX,
                sbY,
                sbW,
                sbH,
                "rgba(18, 19, 22, 0.85)",
                "rgba(255, 255, 255, 0.06)",
                1
            );

            ctx.fillStyle = "#f59e0b";
            ctx.fillRect(sbX + 20, sbY + 18, 6, 6);

            ctx.fillStyle = "#d4d4d8";
            ctx.font = "bold 11px 'GeneralSans', sans-serif";
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.fillText("CAM 03 // MAIN TELEOP", sbX + 34, sbY + 21);

            ctx.fillStyle = "#71717a";
            ctx.font = "500 10px 'GeneralSans', sans-serif";
            ctx.fillText("Connecting to stream on port 8080...", sbX + 20, sbY + 40);
        }

        // 2. Minimal Center Reticle (Ultra clean crosshair, no clutter)
        ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(512 - 14, 288);
        ctx.lineTo(512 - 4, 288);
        ctx.moveTo(512 + 4, 288);
        ctx.lineTo(512 + 14, 288);
        ctx.moveTo(512, 288 - 14);
        ctx.lineTo(512, 288 - 4);
        ctx.moveTo(512, 288 + 4);
        ctx.lineTo(512, 288 + 14);
        ctx.stroke();

        // 3. Top-Left PIP (CAM 01 // LEFT AUX - No rounded corners)
        const pipX = 20,
            pipY = 20,
            pipW = 208,
            pipH = 138;
        drawRect(
            ctx,
            pipX,
            pipY,
            pipW,
            pipH,
            "rgba(18, 19, 22, 0.85)",
            "rgba(255, 255, 255, 0.08)",
            1
        );

        // PIP Header
        drawRect(ctx, pipX, pipY, pipW, 24, "rgba(255, 255, 255, 0.02)", undefined);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pipX, pipY + 24);
        ctx.lineTo(pipX + pipW, pipY + 24);
        ctx.stroke();

        const secImg = secImgElement || fallbackSecImg;
        let drawnSec = Boolean(secImg && secImg.naturalWidth > 0 && secImg.complete);

        ctx.beginPath();
        ctx.arc(pipX + 14, pipY + 12, 3, 0, Math.PI * 2);
        ctx.fillStyle = drawnSec ? "#34d399" : "#71717a";
        ctx.fill();

        ctx.fillStyle = "#d4d4d8";
        ctx.font = "bold 10px 'GeneralSans', sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("Base Camera", pipX + 24, pipY + 12);

        // PIP Body
        if (drawnSec && secImg) {
            try {
                ctx.drawImage(secImg, pipX, pipY + 24, pipW, pipH - 24);
            } catch (_) {}
        } else {
            ctx.fillStyle = "#090a0d";
            ctx.fillRect(pipX, pipY + 24, pipW, pipH - 24);
            ctx.fillStyle = "#52525b";
            ctx.font = "600 10px 'GeneralSans', sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("NO SIGNAL", pipX + pipW / 2, pipY + 24 + (pipH - 24) / 2);
        }

        // 4. Top-Right Quick Status Pill (No rounded corners)
        const trX = 744,
            trY = 20,
            trW = 260,
            trH = 26;
        drawRect(ctx, trX, trY, trW, trH, "rgba(18, 19, 22, 0.85)", "rgba(255, 255, 255, 0.08)", 1);
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.font = "bold 10px 'GeneralSans', sans-serif";
        ctx.fillStyle = "#38bdf8";
        ctx.fillText("RECENTER [B]", trX + 48, trY + trH / 2);
        ctx.fillStyle = "#3f3f46";
        ctx.fillText("│", trX + 98, trY + trH / 2);
        ctx.fillStyle = mirrorCamera ? "#f59e0b" : "#d4d4d8";
        ctx.fillText(mirrorCamera ? "MIRRORED [M]" : "NORMAL [M]", trX + 152, trY + trH / 2);
        ctx.fillStyle = "#3f3f46";
        ctx.fillText("│", trX + 206, trY + trH / 2);
        ctx.fillStyle = "#34d399";
        ctx.fillText("hi", trX + 234, trY + trH / 2);

        // --- Bottom Infotainment Bar ---

        // 5. Bottom-Left: Speedometer Component (Matches Speedometer.svelte directly)
        // Free-floating dual-arc gauge with generous radius and prominent GeneralSans typography
        const scx = 100;
        const scy = 508;
        const sr = 46;
        const strokeW = 7.5;

        // Angular ranges matching Speedometer.svelte
        const LEFT_MIN_DEG = 215;
        const LEFT_MAX_DEG = 330;
        const LEFT_SPAN = LEFT_MAX_DEG - LEFT_MIN_DEG; // 115

        const RIGHT_MIN_DEG = 30;
        const RIGHT_MAX_DEG = 145;
        const RIGHT_SPAN = RIGHT_MAX_DEG - RIGHT_MIN_DEG; // 115

        const leftActiveSpan = (Math.max(1, displayLoad) / 100) * LEFT_SPAN;
        const leftActiveEndDeg = LEFT_MIN_DEG + leftActiveSpan;

        const rightActiveSpan = (Math.max(1, displayTemp) / 100) * RIGHT_SPAN;
        const rightActiveEndDeg = RIGHT_MIN_DEG + rightActiveSpan;

        // Left Background Dark Track
        ctx.beginPath();
        ctx.arc(scx, scy, sr, (125 * Math.PI) / 180, (240 * Math.PI) / 180, false);
        ctx.strokeStyle = "#222226";
        ctx.lineWidth = strokeW;
        ctx.lineCap = "round";
        ctx.stroke();

        // Right Background Dark Track
        ctx.beginPath();
        ctx.arc(scx, scy, sr, (-60 * Math.PI) / 180, (55 * Math.PI) / 180, false);
        ctx.strokeStyle = "#222226";
        ctx.lineWidth = strokeW;
        ctx.lineCap = "round";
        ctx.stroke();

        // Left Active Blue Arc (Load)
        if (displayLoad > 0.5) {
            ctx.beginPath();
            ctx.arc(
                scx,
                scy,
                sr,
                (125 * Math.PI) / 180,
                ((leftActiveEndDeg - 90) * Math.PI) / 180,
                false
            );
            ctx.strokeStyle = "#1d75f2";
            ctx.lineWidth = strokeW;
            ctx.lineCap = "round";
            ctx.stroke();

            // White Indicator Pip (identical to Speedometer.svelte)
            const leftPip = polarToCartesian(scx, scy, sr, leftActiveEndDeg);
            ctx.beginPath();
            ctx.arc(leftPip.x, leftPip.y, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = "#ffffff";
            ctx.fill();
        }

        // Right Active Amber Arc (Temp)
        if (displayTemp > 0.5) {
            ctx.beginPath();
            ctx.arc(
                scx,
                scy,
                sr,
                (-60 * Math.PI) / 180,
                ((rightActiveEndDeg - 90) * Math.PI) / 180,
                false
            );
            ctx.strokeStyle = "#f59e0b";
            ctx.lineWidth = strokeW;
            ctx.lineCap = "round";
            ctx.stroke();

            // Amber Dot Pip with dark fill (identical to Speedometer.svelte)
            const rightPip = polarToCartesian(scx, scy, sr, rightActiveEndDeg);
            ctx.beginPath();
            ctx.arc(rightPip.x, rightPip.y, 4, 0, Math.PI * 2);
            ctx.fillStyle = "#18181b";
            ctx.fill();
            ctx.strokeStyle = "#f59e0b";
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Center Giant Numerals & Label in GeneralSans
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 32px 'GeneralSans', -apple-system, BlinkMacSystemFont, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${Math.round(displayLoad)}`, scx, scy - 4);

        ctx.fillStyle = "#d4d4d8";
        ctx.font = "500 11px 'GeneralSans', -apple-system, BlinkMacSystemFont, sans-serif";
        ctx.fillText("LOAD", scx, scy + 18);

        // 6. Bottom-Middle: Clutch & Teleoperation Status Bar (No rounded corners)
        const mx = 196,
            my = 460,
            mw = 568,
            mh = 96;
        drawRect(ctx, mx, my, mw, mh, "rgba(18, 19, 22, 0.85)", "rgba(255, 255, 255, 0.08)", 1);

        const isEngaged = isClutchEngaged || servoController.liveReplicate;

        // Left Teleoperation Clutch status
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("RIGHT TRIGGER CLUTCH", mx + 20, my + 16);

        ctx.beginPath();
        ctx.arc(mx + 25, my + 44, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = isEngaged ? "#34d399" : "#71717a";
        ctx.fill();

        ctx.fillStyle = isEngaged ? "#34d399" : "#a1a1aa";
        ctx.font = "bold 13px 'GeneralSans', sans-serif";
        ctx.fillText(isEngaged ? "be careful :(" : "im not moving", mx + 36, my + 38);

        ctx.fillStyle = "#52525b";
        ctx.font = "500 9px 'GeneralSans', sans-serif";
        ctx.fillText(
            isEngaged ? "engaged" : "press right trigger to engage motors",
            mx + 20,
            my + 64
        );

        // Middle-Left: Wrist Stick Trim Indicator
        const rotOff = Math.round(servoController.wristOffsets[0] ?? 0);
        const liftOff = Math.round(servoController.wristOffsets[2] ?? 0);
        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("WRIST TRIM", mx + 215, my + 16);

        ctx.fillStyle = rotOff !== 0 || liftOff !== 0 ? "#38bdf8" : "#a1a1aa";
        ctx.font = "bold 13px 'GeneralSans', sans-serif";
        ctx.fillText(
            `R:${rotOff > 0 ? "+" : ""}${rotOff}°  L:${liftOff > 0 ? "+" : ""}${liftOff}°`,
            mx + 215,
            my + 38
        );

        ctx.fillStyle = "#52525b";
        ctx.font = "500 9px 'GeneralSans', sans-serif";
        ctx.fillText("R-STICK X/Y", mx + 215, my + 64);

        // Vertical divider
        ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(mx + 340, my + 14);
        ctx.lineTo(mx + 340, my + mh - 14);
        ctx.stroke();

        // Right side: Gripper & IK Solver
        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("GRIPPER [A]", mx + 360, my + 18);

        ctx.fillStyle = isGripping ? "#34d399" : "#a1a1aa";
        ctx.font = "bold 13px 'GeneralSans', sans-serif";
        ctx.fillText(isGripping ? "gripping..." : "open", mx + 360, my + 38);

        ctx.fillStyle = "#52525b";
        ctx.font = "500 9px 'GeneralSans', sans-serif";
        ctx.fillText("HOLD [A] TO GRIP", mx + 360, my + 64);

        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("IK SOLVER", mx + 474, my + 18);

        ctx.fillStyle = servoController.ikSuccess ? "#34d399" : "#f87171";
        ctx.font = "bold 13px 'GeneralSans', sans-serif";
        ctx.fillText(servoController.ikSuccess ? "able" : ":(", mx + 474, my + 38);

        ctx.fillStyle = "#52525b";
        ctx.font = "500 9px 'GeneralSans', sans-serif";
        ctx.fillText(servoController.ikSuccess ? "calculatings" : "error", mx + 474, my + 64);

        // 7. Bottom-Right: Infotainment Telemetry Card (No rounded corners)
        const rx = 780,
            ry = 460,
            rw = 224,
            rh = 96;
        drawRect(ctx, rx, ry, rw, rh, "rgba(18, 19, 22, 0.85)", "rgba(255, 255, 255, 0.08)", 1);

        const isConn = servoController.connectionState === "connected";
        const onlineCount = safeJoints.filter((j) => j.o).length;

        ctx.beginPath();
        ctx.arc(rx + 20, ry + 25, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = isConn ? "#10b981" : "#f59e0b";
        ctx.fill();

        ctx.fillStyle = "#e4e4e7";
        ctx.font = "bold 12px 'GeneralSans', sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(isConn ? "ONLINE" : "CONNECTING", rx + 30, ry + 25);

        // Badge (No rounded corners)
        const bw = 64,
            bh = 20,
            bx = rx + rw - bw - 16,
            by = ry + 15;
        drawRect(ctx, bx, by, bw, bh, "rgba(6, 78, 59, 0.6)", "rgba(16, 185, 129, 0.3)", 1);
        ctx.fillStyle = "#34d399";
        ctx.font = "bold 11px 'GeneralSans', sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${onlineCount}/7 OK`, bx + bw / 2, by + bh / 2);

        // Divider
        ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(rx + 16, ry + 50);
        ctx.lineTo(rx + rw - 16, ry + 50);
        ctx.stroke();

        // Telemetry Row
        ctx.textAlign = "left";
        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("BUS", rx + 18, ry + 70);
        ctx.fillStyle = "#e4e4e7";
        ctx.font = "bold 12px 'GeneralSans', sans-serif";
        ctx.fillText(`${voltage6V}V`, rx + 48, ry + 70);

        ctx.fillStyle = "#71717a";
        ctx.font = "600 10px 'GeneralSans', sans-serif";
        ctx.fillText("LINK", rx + 118, ry + 70);
        ctx.fillStyle = "#e4e4e7";
        ctx.font = "bold 12px 'GeneralSans', sans-serif";
        ctx.fillText(`${servoController.rateHz || 20}Hz`, rx + 154, ry + 70);

        monitorTexture.needsUpdate = true;
    }

    let lastSolveTime = 0;
    const tempWorldPos = new THREE.Vector3();

    useTask((delta) => {
        const now = performance.now();

        if (now - lastTextureUpdate > 33) {
            lastTextureUpdate = now;
            renderVRMonitor();
        }

        const session = renderer.xr.getSession();
        if (session?.inputSources) {
            for (const source of session.inputSources) {
                const gp = source.gamepad;
                if (!gp?.buttons) continue;

                if (source.handedness === "right") {
                    const triggerBtn = gp.buttons[0];
                    const held = Boolean(
                        triggerBtn && (triggerBtn.pressed || triggerBtn.value > 0.3)
                    );
                    if (held !== isClutchEngaged) {
                        isClutchEngaged = held;
                        servoController.liveReplicate = held;
                        pulseController(held ? 0.35 : 0.15, 30);
                    }

                    const aBtn = gp.buttons[4];
                    const isAHeld = Boolean(aBtn && (aBtn.pressed || aBtn.value > 0.5));
                    if (isAHeld !== isGripping) {
                        if (isAHeld) {
                            startGripper();
                        } else {
                            stopGripper();
                        }
                    }

                    const bBtn = gp.buttons[5];
                    if (bBtn?.pressed) {
                        if (!lastBButtonPressed) {
                            lastBButtonPressed = true;
                            recenterTeleopRig();
                            pulseController(0.6, 80);
                        }
                    } else {
                        lastBButtonPressed = false;
                    }

                    const stickBtn = gp.buttons[3];
                    if (stickBtn?.pressed) {
                        if (!lastThumbstickPressed) {
                            lastThumbstickPressed = true;
                            mirrorCamera = !mirrorCamera;
                        }
                    } else {
                        lastThumbstickPressed = false;
                    }

                    // Thumbstick axes handling for wrist offsets:
                    // Primary thumbstick on xr-standard mapping uses axes[2] (X) and axes[3] (Y),
                    // with fallback to axes[0] and axes[1].
                    let stickX = 0;
                    let stickY = 0;
                    if (gp.axes) {
                        if (
                            gp.axes.length >= 4 &&
                            (Math.abs(gp.axes[2]) > 0.05 || Math.abs(gp.axes[3]) > 0.05)
                        ) {
                            stickX = gp.axes[2];
                            stickY = gp.axes[3];
                        } else if (gp.axes.length >= 2) {
                            stickX = gp.axes[0];
                            stickY = gp.axes[1];
                        }
                    }

                    // Apply deadzone to prevent drift
                    const DEADZONE = 0.15;
                    const activeX = Math.abs(stickX) > DEADZONE ? stickX : 0;
                    const activeY = Math.abs(stickY) > DEADZONE ? stickY : 0;

                    if (activeX !== 0 || activeY !== 0) {
                        const degPerSec = 25; // Slower speed (25 deg/sec at full deflection) for precision control
                        // Inverted X movement adds angle offset to wrist_rotate (motor 0)
                        if (activeX !== 0) {
                            servoController.addWristOffset(0, -activeX * degPerSec * delta);
                        }
                        // Y movement adds angle offset to wrist_lift (motor 2)
                        // Stick forward/up is negative Y in standard gamepads, so -activeY lifts the wrist
                        if (activeY !== 0) {
                            servoController.addWristOffset(2, -activeY * degPerSec * delta);
                        }

                        // When clutch is engaged, immediately update motor goals so response is instant!
                        if (isClutchEngaged) {
                            const rotBase = servoController.ikSolvedAngles["wrist_rotate"] ?? 0;
                            const rotServo = urdfToServoDeg(
                                0,
                                rotBase + (servoController.wristOffsets[0] ?? 0)
                            );
                            servoController.setJointGoal(0, rotServo);

                            const liftBase = servoController.ikSolvedAngles["wrist_lift"] ?? 0;
                            const liftServo = urdfToServoDeg(
                                2,
                                liftBase + (servoController.wristOffsets[2] ?? 0)
                            );
                            servoController.setJointGoal(2, liftServo);
                        }
                    }
                }

                if (source.handedness === "left") {
                    const yBtn = gp.buttons[5];
                    const xBtn = gp.buttons[4];
                    if (yBtn?.pressed || xBtn?.pressed) {
                        if (!lastLeftRecenterPressed) {
                            lastLeftRecenterPressed = true;
                            recenterTeleopRig();
                            pulseController(0.6, 80);
                        }
                    } else {
                        lastLeftRecenterPressed = false;
                    }
                }
            }
        }

        const rightCtrl = rightController.current;
        if (rightCtrl?.grip && robotModel) {
            rightCtrl.grip.getWorldPosition(tempWorldPos);

            if (targetGhost) {
                targetGhost.visible = true;
                targetGhost.position.copy(tempWorldPos);
                (targetGhost.material as THREE.MeshBasicMaterial).color.setHex(
                    isClutchEngaged ? 0x10b981 : 0x00e5ff
                );
            }

            if (now - lastSolveTime > 33) {
                lastSolveTime = now;
                lastSolvedTarget.copy(tempWorldPos);
                triggerIKSolve(tempWorldPos);
            }
        } else if (targetGhost) {
            targetGhost.visible = false;
        }

        updateRobotJoints();

        // Let tracking settle for 10 frames before auto-recentering once
        if (renderer.xr.isPresenting) {
            xrFrameCount++;
            if (xrFrameCount === 10) {
                recenterTeleopRig();
            }
        } else {
            xrFrameCount = 0;
        }
    });

    onMount(() => {
        servoController.ikMode = true;

        // Initialize target ghost sphere for 6-DOF teleop tracking
        const ghostGeo = new THREE.SphereGeometry(0.015, 16, 16);
        const ghostMat = new THREE.MeshBasicMaterial({
            color: 0x00e5ff,
            wireframe: true,
            transparent: true,
            opacity: 0.5
        });
        targetGhost = new THREE.Mesh(ghostGeo, ghostMat);
        targetGhost.visible = false;
        scene.add(targetGhost);

        // Load URDF Robot Models
        const manager = new THREE.LoadingManager();
        const loader = new URDFLoader(manager);
        loader.packages = { assets: "/assets" };

        manager.onLoad = () => {
            if (robotModel) applyToonAndOutlines(robotModel);
            if (ghostRobotModel) applyGhostMaterial(ghostRobotModel);
        };

        // 1. Commanded / Target Arm Model
        loader.load(
            "/robot.urdf",
            (robot) => {
                robot.scale.set(1, 1, 1);
                robot.rotation.x = -Math.PI / 2;
                robot.rotation.z = Math.PI;
                // Keep local origin centered so robotHolder controls world coordinates
                robot.position.set(0.35, 0, 1.55);
                robotModel = robot;

                if (robotHolder) {
                    robotHolder.add(robot);
                } else if (teleopRig) {
                    teleopRig.add(robot);
                } else {
                    scene.add(robot);
                }

                updateRobotJoints();
                applyToonAndOutlines(robot);
            },
            undefined,
            (err) => console.error("Error loading URDF in VR:", err)
        );

        // 2. Ghost Arm Model (Current Physical Telemetry State - Half Transparent)
        loader.load(
            "/robot.urdf",
            (ghostRobot) => {
                ghostRobot.scale.set(1, 1, 1);
                ghostRobot.rotation.x = -Math.PI / 2;
                ghostRobot.rotation.z = Math.PI;
                ghostRobot.position.set(0.35, 0, 1.55);
                ghostRobotModel = ghostRobot;

                applyGhostMaterial(ghostRobot);

                if (robotHolder) {
                    robotHolder.add(ghostRobot);
                } else if (teleopRig) {
                    teleopRig.add(ghostRobot);
                } else {
                    scene.add(ghostRobot);
                }

                updateRobotJoints();
            },
            undefined,
            (err) => console.error("Error loading ghost URDF in VR:", err)
        );
    });

    onDestroy(() => {
        if (isGripping) {
            stopGripper();
        }
        if (monitorTexture) monitorTexture.dispose();
        if (robotModel?.parent) robotModel.parent.remove(robotModel);
        if (ghostRobotModel?.parent) ghostRobotModel.parent.remove(ghostRobotModel);
        if (targetGhost) {
            targetGhost.geometry.dispose();
            (targetGhost.material as THREE.Material).dispose();
            if (targetGhost.parent) targetGhost.parent.remove(targetGhost);
        }
        servoController.ikMode = false;
        servoController.liveReplicate = false;
    });
</script>

<!-- Hidden DOM elements ensure continuous MJPEG frame decoding without canvas tainting -->
<div
    style="position: absolute; width: 0; height: 0; overflow: hidden; opacity: 0; pointer-events: none;"
>
    <img
        bind:this={fallbackMainImg}
        src={mainStreamUrl}
        crossorigin="anonymous"
        alt="main stream"
    />
    <img bind:this={fallbackSecImg} src={secStreamUrl} crossorigin="anonymous" alt="aux stream" />
</div>

<XR onsessionstart={() => onsessionstart?.()} onsessionend={() => onsessionend?.()} />

<Controller left />
<Controller
    right
    onselectstart={() => {
        isClutchEngaged = true;
        servoController.liveReplicate = true;
        pulseController(0.4, 30);
    }}
    onselectend={() => {
        isClutchEngaged = false;
        servoController.liveReplicate = false;
        pulseController(0.15, 25);
    }}
/>

<Hand left />
<Hand right />

<!-- Camera & Lighting -->
<T.PerspectiveCamera makeDefault position={[0, 1.45, 0.8]} />
<T.AmbientLight intensity={0.7} />
<T.DirectionalLight position={[3, 6, 4]} intensity={1.5} castShadow />
<T.PointLight position={[-1, 2, -1]} intensity={0.9} color={0x00d2ff} />

<!-- Teleoperation Rig -->
<T.Group bind:ref={teleopRig} position={[0, 0, 0]}>
    <!-- 1. Floating In-VR HUD Monitor: Placed comfortably at z = -1.4m -->
    <T.Group bind:ref={monitorGroup} position={[0, 1.45, -1.4]} rotation={[-0.04, 0, 0]}>
        <!-- Minimal outer bezel: placed 1.5cm behind display screen -->
        <T.Mesh position={[0, 0, -0.015]}>
            <T.BoxGeometry args={[1.82, 1.03, 0.02]} />
            <T.MeshStandardMaterial color={0x0b0d14} roughness={0.8} metalness={0.2} />
        </T.Mesh>

        <!-- Main Display Plane: Persistent CanvasTexture bound directly -->
        <T.Mesh position={[0, 0, 0.002]}>
            <T.PlaneGeometry args={[1.8, 1.0125]} />
            <T.MeshBasicMaterial map={monitorTexture} toneMapped={false} side={THREE.DoubleSide} />
        </T.Mesh>
    </T.Group>

    <!-- 2. Robot Desk/Holder: Placed in the foreground (z = -0.55m) -->
    <T.Group bind:ref={robotHolder} position={[0.22, 0.8, -0.55]} />

    <!-- 3. Reference Floor Grid -->
    <T.GridHelper args={[16, 16, 0x27272a, 0x14151a]} position={[0, 0.01, 0]} />
</T.Group>
