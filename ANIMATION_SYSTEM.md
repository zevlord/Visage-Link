# VSeeFace Programmatic Animation & Sway System Documentation

This document explains the architecture, mathematical formulas, and tuning parameters of the programmatic head sway and body posing system implemented in [`server/idle_animator.py`](file:///D:/Project%20ideas%202.1/server/idle_animator.py).

---

## 1. System Overview

Instead of capturing video from a physical webcam, this system simulates lifelike head movements, breathing, and body posture by broadcasting bone rotation packets directly to VSeeFace using the **VMC Protocol** over UDP loopback.

```
+--------------------------------------------------------+
|                      Python Server                     |
|                                                        |
|  [ Gaze Targets ] -> [ Lerp & Speed Clamp ]            |
|                              |                         |
|                              v                         |
|  [ UDP Port 39539 ] -> [ VMC Protocol Packet ]         |
+---------------------------|----------------------------+
                            | (UDP Broadcast)
                            v
+--------------------------------------------------------+
|                        VSeeFace                        |
|                                                        |
|  [ Bone Receiver ] -> [ VRM Spring Bone Physics ]      |
|                              |                         |
|                              v                         |
|                 [ Butter-smooth Avatar Sway ]          |
+--------------------------------------------------------+
```

---

## 2. Mathematical Algorithms

The system combines three concepts to create natural, non-monotone animations:

### A. Target-Based Gaze Shifts
To simulate how humans look around and focus on objects, the animator selects a random direction (Yaw, Pitch, Roll) and holds it for a random duration (between 2.0 and 4.5 seconds).
* **Yaw (Left/Right)**: range `-0.16` to `0.16` radians.
* **Pitch (Up/Down)**: range `-0.08` to `0.05` radians.
* **Roll (Tilt)**: range `-0.04` to `0.04` radians.

### B. Speed-Restricted Interpolation (Lerp)
To prevent the head from "snapping" or moving too quickly when a new target is chosen, the current angle moves toward the target using a Linear Interpolation (`LERP_FACTOR = 0.06`), clamped by a maximum speed limit (`MAX_SPEED = 0.18` radians per second):
$$\text{step} = (\text{target} - \text{current}) \times \text{LERP\_FACTOR}$$
$$\text{step\_clamped} = \text{clamp}(\text{step}, -\text{max\_step}, \text{max\_step})$$

### C. Micro-Breathing Overlay
To keep the avatar from looking completely frozen while holding a gaze, a multi-frequency sine wave is added on top of the positions:
* $\text{Yaw}_{\text{breath}} = \sin(t \times 1.1) \times 0.003$
* $\text{Pitch}_{\text{breath}} = \sin(t \times 1.5) \times 0.007$
* $\text{Roll}_{\text{breath}} = \cos(t \times 0.8) \times 0.002$

---

## 3. Unity / VRM Bone Mappings

For the rotations to register correctly in VSeeFace, the Euler angles are converted into Unity-compliant quaternions `(qx, qy, qz, qw)` using the **YXZ rotation order** (Yaw $\rightarrow$ Pitch $\rightarrow$ Roll):

* **`qx`**: Pitch (vertical axis rotation)
* **`qy`**: Yaw (horizontal axis rotation)
* **`qz`**: Roll (head-tilt axis rotation)

### Relaxed Body Pose (Anti-T-Pose)
To keep the avatar's arms hanging down naturally rather than sticking straight out in a T-pose, the following static rotations are broadcasted:
* **`LeftUpperArm`**: Rotation around the Z-axis (roll) by `1.35` radians, and X-axis (pitch) by `0.15` radians.
* **`RightUpperArm`**: Rotation around the Z-axis (roll) by `-1.35` radians, and X-axis (pitch) by `0.15` radians.

---

## 4. How to Tune the Animation

You can modify these variables directly in [`server/idle_animator.py`](file:///D:/Project%20ideas%202.1/server/idle_animator.py) to change the behavior:

* **Sway Speed**: Change `MAX_SPEED` (e.g., set to `0.3` for quicker gaze shifts, or `0.1` for slower, sleepier sways).
* **Gaze Frequency**: Change `gaze_timer = random.uniform(2.0, 4.5)` (lower numbers will make her shift her gaze more frequently).
* **Arm Hang Angle**: Change the `1.35` and `-1.35` roll values in the shoulder setup to adjust how close her arms are to her sides.
