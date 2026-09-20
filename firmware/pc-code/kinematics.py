import math
import numpy as np

JOINT_TO_MOTOR_MAP = {
    "base_rot": 5,        # Motor 5: Base Rotate (PWM)
    "shoulder_lift": 4,   # Motor 4: Shoulder Lift (PWM)
    "elbow_lift": 6,      # Motor 6: Elbow Lift (PWM)
    "wrist_lift": 2,      # Motor 2: Wrist Lift (MG996R)
    "wrist_rotate": 0,    # Motor 0: Wrist Rotate (MG996R)
    "end_rotate": 1,      # Motor 1: End Rotate (MG996R)
}

JOINTS = [
    {
        "name": "base_rot",
        "servo_id": JOINT_TO_MOTOR_MAP["base_rot"],
        "parent": "table_mount_lid",
        "child": "dsservo_150kg_80kg_60kg_v1",
        "xyz": [0.163647, -0.755532, 0.462096],
        "rpy": [-3.14159, 0.0, 0.0241335],
        "axis": [0.0, 0.0, 1.0],
        "limits": [-math.pi, math.pi],
        "default": 0.0,
    },
    {
        "name": "shoulder_lift",
        "servo_id": JOINT_TO_MOTOR_MAP["shoulder_lift"],
        "parent": "dsservo_150kg_80kg_60kg_v1",
        "child": "40x40x10_dc_fan_f3d__v1",
        "xyz": [0.0214454, -0.0382546, -0.0205],
        "rpy": [-1.5708, 0.771565, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "limits": [-math.pi / 3, math.pi / 2],
        "default": 0.0,
    },
    {
        "name": "elbow_lift",
        "servo_id": JOINT_TO_MOTOR_MAP["elbow_lift"],
        "parent": "40x40x10_dc_fan_f3d__v1",
        "child": "40x40x10_dc_fan_f3d__v1_2",
        "xyz": [0.216, 2.7539e-05, 0.0254306],
        "rpy": [3.14159, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "limits": [-math.pi * 2, math.pi],
        "default": 0.0,
    },
    {
        "name": "wrist_lift",
        "servo_id": JOINT_TO_MOTOR_MAP["wrist_lift"],
        "parent": "40x40x10_dc_fan_f3d__v1_2",
        "child": "component1",
        "xyz": [0.215846, 0.000124007, 0.013976],
        "rpy": [3.14159, 0.0, 0.13456],
        "axis": [0.0, 0.0, 1.0],
        "limits": [-math.pi / 3, math.pi],
        "default": 0.0,
    },
    {
        "name": "wrist_rotate",
        "servo_id": JOINT_TO_MOTOR_MAP["wrist_rotate"],
        "parent": "component1",
        "child": "component1_2",
        "xyz": [0.000124007, -0.026476, -0.0415956],
        "rpy": [-1.5708, 1.23129, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "limits": [0, math.pi / 10],
        "default": 0.0,
    },
    {
        "name": "end_rotate",
        "servo_id": JOINT_TO_MOTOR_MAP["end_rotate"],
        "parent": "component1_2",
        "child": "component1_3",
        "xyz": [0.000124007, -0.025476, -0.0415956],
        "rpy": [-1.5708, -0.354302, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "limits": [-math.pi, math.pi],
        "default": math.pi / 8,
    },
]

# End effector offset from last link
EE_OFFSET = np.array([0.0, 0.0, -0.10, 1.0])


def rpy_to_matrix(r, p, y):
    """Compute 3x3 rotation matrix from roll, pitch, yaw."""
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)

    R_x = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    R_y = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    R_z = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])

    return R_z @ R_y @ R_x


def axis_angle_to_matrix(axis, angle):
    """Compute 3x3 rotation matrix for rotation around an axis vector."""
    axis = np.array(axis, dtype=np.float64)
    norm = np.linalg.norm(axis)
    if norm < 1e-9:
        return np.eye(3)
    axis = axis / norm
    x, y, z = axis
    c = math.cos(angle)
    s = math.sin(angle)
    C = 1.0 - c
    return np.array(
        [
            [x * x * C + c, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
        ]
    )


def make_transform(xyz, rpy):
    """Create 4x4 homogeneous transformation matrix."""
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = rpy_to_matrix(rpy[0], rpy[1], rpy[2])
    T[:3, 3] = xyz
    return T


# Pre-computed static joint origin transforms
JOINT_ORIGIN_TRANSFORMS = [make_transform(j["xyz"], j["rpy"]) for j in JOINTS]


def forward_kinematics(joint_angles):
    """
    Computes Forward Kinematics for joint angles [rad] (length 6).
    Returns:
      T_ee: 4x4 matrix of end-effector in base frame.
      joint_origins: list of 3D positions of joint axes in base frame.
      joint_axes: list of 3D unit vectors of joint axes in base frame.
    """
    T = np.eye(4, dtype=np.float64)
    joint_origins = []
    joint_axes = []

    for i, joint in enumerate(JOINTS):
        angle = joint_angles[i]
        T_origin = JOINT_ORIGIN_TRANSFORMS[i]
        T_before_joint = T @ T_origin

        # Axis and origin in base frame
        axis_world = T_before_joint[:3, :3] @ np.array(joint["axis"])
        axis_world = axis_world / np.linalg.norm(axis_world)
        origin_world = T_before_joint[:3, 3]

        joint_origins.append(origin_world)
        joint_axes.append(axis_world)

        # Apply joint rotation
        R_joint = axis_angle_to_matrix(joint["axis"], angle)
        T_joint = np.eye(4, dtype=np.float64)
        T_joint[:3, :3] = R_joint

        T = T_before_joint @ T_joint

    # End-effector in base frame
    T_ee = T.copy()
    T_ee[:3, 3] = (T @ EE_OFFSET)[:3]

    return T_ee, joint_origins, joint_axes


def compute_jacobian(joint_origins, joint_axes, ee_pos):
    """Compute 3xN position Jacobian matrix."""
    n = len(joint_origins)
    J = np.zeros((3, n), dtype=np.float64)
    for i in range(n):
        J[:, i] = np.cross(joint_axes[i], ee_pos - joint_origins[i])
    return J


def solve_ik(
    target_pos, initial_angles=None, max_iterations=40, tolerance=0.002, damping=0.03
):
    target = np.array(target_pos, dtype=np.float64)
    n = len(JOINTS)

    if initial_angles is None or len(initial_angles) != n:
        q = np.array([j["default"] for j in JOINTS], dtype=np.float64)
    else:
        q = np.array(initial_angles, dtype=np.float64)

    # Enforce initial limits
    for i in range(n):
        q[i] = np.clip(q[i], JOINTS[i]["limits"][0], JOINTS[i]["limits"][1])

    best_q = q.copy()
    best_err = float("inf")

    for _ in range(max_iterations):
        T_ee, joint_origins, joint_axes = forward_kinematics(q)
        ee_pos = T_ee[:3, 3]
        error_vec = target - ee_pos
        err = np.linalg.norm(error_vec)

        if err < best_err:
            best_err = err
            best_q = q.copy()

        if err < tolerance:
            break

        # Compute Jacobian
        J = compute_jacobian(joint_origins, joint_axes, ee_pos)

        # Damped Least Squares: dq = J^T (J J^T + lambda^2 I)^(-1) dx
        JJT = J @ J.T + (damping**2) * np.eye(3)
        try:
            inv_JJT = np.linalg.inv(JJT)
            dq = J.T @ (inv_JJT @ error_vec)
        except np.linalg.LinAlgError:
            # Fallback to transposed Jacobian
            dq = 0.1 * J.T @ error_vec

        # Step limit for stability
        max_step = 0.3
        dq_norm = np.linalg.norm(dq)
        if dq_norm > max_step:
            dq = dq * (max_step / dq_norm)

        q += dq

        # Clamp to joint limits
        for i in range(n):
            q[i] = np.clip(q[i], JOINTS[i]["limits"][0], JOINTS[i]["limits"][1])

    # Final FK with best angles
    T_ee_final, _, _ = forward_kinematics(best_q)
    achieved_pos = T_ee_final[:3, 3]
    final_err = float(np.linalg.norm(achieved_pos - target))

    angles_deg = {}
    servo_angles = {}
    for i, joint in enumerate(JOINTS):
        deg = float(np.rad2deg(best_q[i]))
        angles_deg[joint["name"]] = round(deg, 2)
        servo_angles[joint["servo_id"]] = round(deg, 2)

    return {
        "success": final_err < 0.05,
        "error_m": round(final_err, 5),
        "angles_rad": [round(float(a), 4) for a in best_q],
        "angles_deg": angles_deg,
        "servo_angles": servo_angles,
        "achieved_pos": [round(float(p), 4) for p in achieved_pos],
        "target_pos": [round(float(p), 4) for p in target],
    }


if __name__ == "__main__":
    T_zero, _, _ = forward_kinematics([0.0] * 6)
    pos_zero = T_zero[:3, 3]
    print(f"EE pos at zeros: {pos_zero}", flush=True)

    target = pos_zero + np.array([0.05, 0.02, 0.03])
    sol = solve_ik(target)
    print(
        f"IK Result: success={sol['success']}, error={sol['error_m']}m",
        flush=True,
    )
    print(f"Solved servo angles: {sol['servo_angles']}", flush=True)
    print(f"Achieved pos: {sol['achieved_pos']}", flush=True)
