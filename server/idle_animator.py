import asyncio
import math
import time
import random
from pythonosc import udp_client

# VMC target settings
VS_IP = "127.0.0.1"
VS_PORTS = [39539, 39540]

# UDP initialization
clients = [udp_client.SimpleUDPClient(VS_IP, port) for port in VS_PORTS]
_animator_task = None
is_speaking = False

def set_speaking(val: bool):
    """Updates the speaking state of the avatar to focus gaze on camera."""
    global is_speaking
    is_speaking = val
    print(f"[ANIMATOR] Speaking state updated: {is_speaking}")

def euler_to_quaternion(yaw, pitch, roll):
    """Converts Euler rotation angles (in radians) to a Unity-compliant Quaternion (YXZ order)."""
    t0 = math.cos(yaw * 0.5)
    t1 = math.sin(yaw * 0.5)
    t2 = math.cos(pitch * 0.5)
    t3 = math.sin(pitch * 0.5)
    t4 = math.cos(roll * 0.5)
    t5 = math.sin(roll * 0.5)

    qw = t0 * t2 * t4 + t1 * t3 * t5
    qx = t0 * t3 * t4 + t1 * t2 * t5
    qy = t1 * t2 * t4 - t0 * t3 * t5
    qz = t0 * t2 * t5 - t1 * t3 * t4

    return qx, qy, qz, qw

async def animation_loop():
    """Main VMC animator loop that sends head sways and shoulder poses at ~30 FPS."""
    print("[ANIMATOR] Virtual head animator loop started.")
    try: 
        # Resting arm stance (relaxed downward arm angle)
        left_shoulder_qx, left_shoulder_qy, left_shoulder_qz, left_shoulder_qw = euler_to_quaternion(0, 0.15, 1.35)
        right_shoulder_qx, right_shoulder_qy, right_shoulder_qz, right_shoulder_qw = euler_to_quaternion(0, 0.15, -1.35)

        # Current head Euler rotation state
        curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
        # Target head Euler rotation state
        target_yaw, target_pitch, target_roll = 0.0, 0.0, 0.0

        # Dynamics variables (dynamically modulated for normal vs. aggressive idles)
        current_max_speed = 0.18
        current_lerp_factor = 0.06

        gaze_timer = 0.0
        dt = 1.0 / 30.0  # 30 frames per second (33.3ms)

        while True:
            t = time.time()

            # --- Speaking State: Force camera focus with micro nodding/tilts ---
            if is_speaking:
                target_yaw = 0.0
                target_pitch = math.sin(t * 2.5) * 0.015  # Natural nodding
                target_roll = math.cos(t * 1.5) * 0.01    # Natural speaking head tilt
                current_max_speed = 0.18
                current_lerp_factor = 0.06
                gaze_timer = 1.0
            
            # --- Idle State: Random Gaze Shifts & Aggressive Variations ---
            else:
                gaze_timer -= dt
                if gaze_timer <= 0:
                    # Roll 20% chance for an "Aggressive/High-Energy" idle move
                    if random.random() < 0.20:
                        style = random.choice(["sassy_tilt", "double_take", "deep_nod"])
                        
                        if style == "sassy_tilt":
                            # Snappy head tilt to one side
                            target_yaw = random.uniform(-0.08, 0.08)
                            target_pitch = random.uniform(-0.04, 0.04)
                            target_roll = random.choice([-0.25, 0.25])
                            current_max_speed = 0.42
                            current_lerp_factor = 0.12
                            gaze_timer = random.uniform(1.2, 2.0)
                            
                        elif style == "double_take":
                            # Sharp side look with short duration
                            target_yaw = random.choice([-0.32, 0.32])
                            target_pitch = random.uniform(-0.05, 0.02)
                            target_roll = random.uniform(-0.02, 0.02)
                            current_max_speed = 0.50
                            current_lerp_factor = 0.18
                            gaze_timer = random.uniform(0.6, 1.2)
                            
                        elif style == "deep_nod":
                            # Deep stretch up or bow down
                            target_yaw = random.uniform(-0.05, 0.05)
                            target_pitch = random.choice([-0.18, 0.08])
                            target_roll = random.uniform(-0.02, 0.02)
                            current_max_speed = 0.22
                            current_lerp_factor = 0.08
                            gaze_timer = random.uniform(1.5, 2.5)
                            
                    else:
                        # 80% Chance: Standard gentle, natural head sways
                        target_yaw = random.uniform(-0.16, 0.16)
                        target_pitch = random.uniform(-0.08, 0.05)
                        target_roll = random.uniform(-0.04, 0.04)
                        current_max_speed = 0.18
                        current_lerp_factor = 0.06
                        gaze_timer = random.uniform(1.5, 4.5)

            # --- Interpolation and Speed Restrictions ---
            diff_yaw = target_yaw - curr_yaw
            diff_pitch = target_pitch - curr_pitch
            diff_roll = target_roll - curr_roll

            # Step calculated based on current lerp factor
            step_yaw = diff_yaw * current_lerp_factor
            step_pitch = diff_pitch * current_lerp_factor
            step_roll = diff_roll * current_lerp_factor

            # Clamp step sizes to stay within the maximum speed limit
            max_step = current_max_speed * dt
            step_yaw = max(-max_step, min(max_step, step_yaw))
            step_pitch = max(-max_step, min(max_step, step_pitch))
            step_roll = max(-max_step, min(max_step, step_roll))

            # Apply movements
            curr_yaw += step_yaw
            curr_pitch += step_pitch
            curr_roll += step_roll

            # --- Micro-Breathing Wave Layer ---
            final_yaw = curr_yaw + math.sin(t * 1.1) * 0.003
            final_pitch = curr_pitch + math.sin(t * 1.5) * 0.007
            final_roll = curr_roll + math.cos(t * 0.8) * 0.002

            # Convert final Euler state to Quaternion
            hqx, hqy, hqz, hqw = euler_to_quaternion(final_yaw, final_pitch, final_roll)

            # Spine / Body sway math (follows head sways at 25% scale)
            spine_yaw = final_yaw * 0.25
            spine_pitch = final_pitch * 0.25
            sqx, sqy, sqz, sqw = euler_to_quaternion(spine_yaw, spine_pitch, 0.0)
            
            # Broadcast VMC protocol packets to ports 39539 and 39540
            for client in clients:
                client.send_message("/VMC/Ext/Bone/Pos", ["LeftUpperArm", 0.0, 0.0, 0.0, left_shoulder_qx, left_shoulder_qy, left_shoulder_qz, left_shoulder_qw])
                client.send_message("/VMC/Ext/Bone/Pos", ["RightUpperArm", 0.0, 0.0, 0.0, right_shoulder_qx, right_shoulder_qy, right_shoulder_qz, right_shoulder_qw])
                client.send_message("/VMC/Ext/Bone/Pos", ["Spine", 0.0, 0.0, 0.0, sqx, sqy, sqz, sqw])
                client.send_message("/VMC/Ext/Bone/Pos", ["Head", 0.0, 0.0, 0.0, hqx, hqy, hqz, hqw])
                client.send_message("/VMC/Ext/Bone/Apply", [])

            await asyncio.sleep(dt)

    except asyncio.CancelledError:
        print("[ANIMATOR] Virtual head animator loop stopped.")

def start_animator(loop):
    """Hooks the loop into the running async loop of the FastAPI server."""
    global _animator_task
    if _animator_task is None:
        _animator_task = loop.create_task(animation_loop())

def stop_animator():
    """Stops the animator loop when server shuts down."""
    global _animator_task
    if _animator_task is not None:
        _animator_task.cancel()
        _animator_task = None
