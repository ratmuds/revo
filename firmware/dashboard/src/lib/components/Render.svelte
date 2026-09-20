<script lang="ts">
    import { onMount } from "svelte";
    import * as THREE from "three";
    import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
    import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
    import URDFLoader from "urdf-loader";
    import { servoController } from "$lib/stores/servoStore.svelte";
    import { MOTOR_CONFIG, servoToUrdfDeg } from "$lib/config/robotConfig";

    const manager = new THREE.LoadingManager();
    const loader = new URDFLoader(manager);
    loader.packages = {
        assets: "/assets"
    };

    let container: HTMLDivElement;
    let scene: THREE.Scene;
    let camera: THREE.PerspectiveCamera;
    let renderer: THREE.WebGLRenderer;
    let controls: OrbitControls;
    let transformControls: TransformControls | null = null;
    let targetCube: THREE.Mesh | null = null;
    let isDraggingGizmo = false;
    let ikAngles: Record<string, number> | null = null;

    let robotModel: any = null;

    let pointCloud: THREE.Points | null = null;
    let pointMaterial = new THREE.PointsMaterial({
        size: 0.1,
        vertexColors: true,
        sizeAttenuation: true
    });
    // Create placeholder camera cube (sized in local URDF coordinates)
    const geo = new THREE.BoxGeometry(0.06, 0.06, 0.06);
    const mat = new THREE.MeshStandardMaterial({
        color: 0xff0055,
        roughness: 0.3
    });
    const testCube = new THREE.Mesh(geo, mat);

    // Gradient map for toon thingy
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
    const outlineMaterial = new THREE.LineBasicMaterial({
        color: 0x111111,
        linewidth: 1
    });

    function applyToonAndOutlines(model: THREE.Object3D | null) {
        if (!model) return;
        model.traverse((child: any) => {
            if (child.isMesh && child.geometry && !child.userData.toonApplied) {
                child.userData.toonApplied = true;

                // Ensure smooth normals for organic/curved surfaces
                child.geometry.computeVertexNormals();

                const originalColor = child.material?.color
                    ? child.material.color.clone()
                    : new THREE.Color(0xd4d4d8);

                // Apply cel-shaded toon material with depth offset so outlines don't z-fight
                child.material = new THREE.MeshToonMaterial({
                    color: originalColor,
                    gradientMap: toonGradient,
                    polygonOffset: true,
                    polygonOffsetFactor: 1,
                    polygonOffsetUnits: 1
                });
                child.castShadow = true;
                child.receiveShadow = true;

                // CAD outlines
                const edges = new THREE.EdgesGeometry(child.geometry, 25);
                const line = new THREE.LineSegments(edges, outlineMaterial);
                child.add(line);
            }
        });
    }

    // Runs once all STL meshes are fully downloaded and added by URDFLoader
    manager.onLoad = () => {
        if (robotModel) {
            applyToonAndOutlines(robotModel);
        }
    };

    function createTargetCube(): THREE.Mesh {
        const geo = new THREE.BoxGeometry(1.2, 1.2, 1.2);
        const mat = new THREE.MeshStandardMaterial({
            color: 0x00e5ff,
            emissive: 0x004466,
            roughness: 0.2,
            metalness: 0.3,
            transparent: true,
            opacity: 0.75
        });
        const mesh = new THREE.Mesh(geo, mat);
        const edges = new THREE.EdgesGeometry(geo);
        const line = new THREE.LineSegments(
            edges,
            new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 1.5 })
        );
        mesh.add(line);
        mesh.visible = false;
        return mesh;
    }

    function snapTargetToRobot() {
        if (!robotModel || !robotModel.joints || !targetCube) return;
        robotModel.updateMatrixWorld(true);
        const eeJoint = robotModel.joints["end_rotate"] || robotModel.joints["wrist_rotate"];
        if (eeJoint) {
            const worldPos = new THREE.Vector3();
            eeJoint.getWorldPosition(worldPos);
            targetCube.position.copy(worldPos);
        }
    }

    let isSolving = false;
    let pendingSolve = false;

    async function triggerIKSolve() {
        if (isSolving) {
            pendingSolve = true;
            return;
        }
        if (!robotModel || !targetCube || !servoController.ikMode) return;

        isSolving = true;
        try {
            robotModel.updateMatrixWorld(true);
            const urdfTarget = robotModel.worldToLocal(targetCube.position.clone());
            const data = await servoController.solveIK(
                [urdfTarget.x, urdfTarget.y, urdfTarget.z],
                servoController.liveReplicate,
                "urdf"
            );
            if (data && data.angles_deg) {
                ikAngles = data.angles_deg;
            }
        } catch (e) {
            console.error("IK solve error:", e);
        } finally {
            isSolving = false;
            if (pendingSolve) {
                pendingSolve = false;
                triggerIKSolve();
            }
        }
    }

    $effect(() => {
        const active = servoController.ikMode;
        if (targetCube && transformControls) {
            targetCube.visible = active;
            transformControls.enabled = active;
            const helper = transformControls.getHelper();
            if (helper) helper.visible = active;

            if (active) {
                snapTargetToRobot();
                triggerIKSolve();
            } else {
                ikAngles = null;
            }
        }
    });

    function updateRobotJoints() {
        if (!robotModel || !robotModel.joints) return;

        if (servoController.ikMode && ikAngles) {
            for (const [jointName, deg] of Object.entries(ikAngles)) {
                const joint = robotModel.joints[jointName];
                if (joint && typeof joint.setJointValue === "function") {
                    joint.setJointValue((deg * Math.PI) / 180);
                }
            }
            return;
        }

        for (const [idStr, mapping] of Object.entries(MOTOR_CONFIG)) {
            const motorId = Number(idStr);
            if (!mapping.jointName) continue;

            const joint = robotModel.joints[mapping.jointName];
            if (!joint || typeof joint.setJointValue !== "function") continue;

            // Follow actual measured/commanded angles from telemetry
            const telemetry = servoController.joints.find((j) => j.id === motorId);
            const isContinuous = motorId < 4;

            let physicalServoDeg: number;
            if (telemetry && telemetry.o) {
                if (telemetry.ra !== undefined && telemetry.ra !== null) {
                    physicalServoDeg = isContinuous ? telemetry.ra / 10 : telemetry.ra;
                } else if (telemetry.a !== undefined && telemetry.a !== null) {
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
            const rad = (urdfDeg * Math.PI) / 180;
            joint.setJointValue(rad);
        }
    }

    async function fetchPointCloud() {
        try {
            const res = await fetch("http://localhost:8080/api/pointcloud");
            if (!res.ok) return;
            const data = await res.json();

            if (data.ok) {
                if (data.points && data.points.length > 0) {
                    updatePoints(data.points, data.colors);
                }
            }
        } catch (err) {
            console.error("PointCloud fetch error:", err);
        }
    }

    function updatePoints(pts: any[], cls: any[]) {
      const count = pts.length;
      const positions = new Float32Array(count * 3);
      const colors = new Float32Array(count * 3);

      for (let i = 0; i < count; i++) {
        // Invert Y axis
        positions[i * 3 + 0] = pts[i][0];
        positions[i * 3 + 1] = -pts[i][1];
        positions[i * 3 + 2] = pts[i][2];

        if (cls && cls[i]) {
          colors[i * 3 + 0] = cls[i][0] / 255.0;
          colors[i * 3 + 1] = cls[i][1] / 255.0;
          colors[i * 3 + 2] = cls[i][2] / 255.0;
        } else {
          colors[i * 3 + 0] = 0.3;
          colors[i * 3 + 1] = 0.7;
          colors[i * 3 + 2] = 1.0;
        }
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

      if (pointCloud) {
        if (pointCloud.parent) {
          pointCloud.parent.remove(pointCloud);
        }
        pointCloud.geometry.dispose();
      }

      pointCloud = new THREE.Points(geometry, pointMaterial);
      pointCloud.rotateX(Math.PI / 2);
      pointCloud.rotateY(Math.PI / 2);
      testCube.add(pointCloud);
    }

    onMount(() => {
        if (!container) return;

        // Scene & Fog
        scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0c0c0c);
        scene.fog = new THREE.FogExp2(0x0a0a0a, 0.015);

        // Camera setup with proper position and lookAt target
        const aspect = container.clientWidth / (container.clientHeight || 1);
        camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 500);
        camera.position.set(10, 7, 9);
        camera.lookAt(0, 3.5, 0);

        // WebGL Renderer
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        // Interactive Orbit Controls
        controls = new OrbitControls(camera, renderer.domElement);
        controls.target.set(0, 3.5, 0);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Draggable Target Cube for IK
        targetCube = createTargetCube();
        scene.add(targetCube);

        transformControls = new TransformControls(camera, renderer.domElement);
        transformControls.setSize(0.85);
        transformControls.setSpace("world");
        transformControls.attach(targetCube);

        transformControls.addEventListener("dragging-changed", (event: any) => {
            isDraggingGizmo = Boolean(event.value);
            controls.enabled = !event.value;
        });

        transformControls.addEventListener("change", () => {
            if (isDraggingGizmo && servoController.ikMode) {
                triggerIKSolve();
            }
        });

        const gizmoHelper = transformControls.getHelper();
        gizmoHelper.visible = false;
        transformControls.enabled = false;
        scene.add(gizmoHelper);

        // Lighting
        const ambient = new THREE.AmbientLight(0xffffff, 0.4);
        scene.add(ambient);

        const dirLight = new THREE.DirectionalLight(0xffffff, 1.4);
        dirLight.position.set(15, 30, 20);
        scene.add(dirLight);

        const blueLight = new THREE.PointLight(0x00d2ff, 1.2, 30);
        blueLight.position.set(-10, 10, -5);
        scene.add(blueLight);

        // Load URDF Robot
        loader.load(
            "/robot.urdf",
            (robot) => {
                robot.scale.set(10, 10, 10);
                robot.rotation.x = -Math.PI / 2;
                robot.position.set(-1.75, -4, -8);
                robotModel = robot;
                scene.add(robot);
                updateRobotJoints();
                applyToonAndOutlines(robot);
                if (servoController.ikMode) {
                    snapTargetToRobot();
                    triggerIKSolve();
                }

                // --- Camera spot parented directly to base_rot ---
                const baseJoint = robot.joints["base_rot"];
                if (baseJoint) {
                    // Add CAD outline to match the rest of the renderer
                    const edges = new THREE.EdgesGeometry(geo);
                    const line = new THREE.LineSegments(
                        edges,
                        new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 1.5 })
                    );
                    testCube.add(line);

                    // Offset slightly from joint center so rotation is clearly visible
                    testCube.position.set(0.075, -0.005, -0.02);

                    // Parent directly to base_rot!
                    baseJoint.add(testCube);
                }
            },
            undefined,
            (error) => {
                console.error("Error loading URDF:", error);
            }
        );

        // Responsive resize handling
        const resizeObserver = new ResizeObserver(() => {
            if (!container || !renderer || !camera) return;
            const w = container.clientWidth;
            const h = container.clientHeight;
            if (w === 0 || h === 0) return;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        });
        resizeObserver.observe(container);

        // Render loop
        let animationFrameId: number;
        function render() {
            animationFrameId = requestAnimationFrame(render);
            controls.update();
            updateRobotJoints();
            renderer.render(scene, camera);
        }
        render();

        // Pointcloud loop
        setInterval(() => {
            //fetchPointCloud();
        }, 200);

        return () => {
            cancelAnimationFrame(animationFrameId);
            resizeObserver.disconnect();
            controls.dispose();
            if (transformControls) {
                transformControls.dispose();
            }
            if (renderer && renderer.domElement && container) {
                container.removeChild(renderer.domElement);
                renderer.dispose();
            }
        };
    });
</script>

<div class="w-full h-full min-h-[300px]" bind:this={container}></div>

<style>
    :global(body) {
        overflow: hidden;
    }
</style>
