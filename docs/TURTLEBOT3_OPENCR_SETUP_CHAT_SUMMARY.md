# TurtleBot3 Burger + OpenCR + Jetson — setup notes (chat summary)

This file summarizes the Cursor conversation about wiring TurtleBot3 Burger (XL430-W250, OpenCR) into the `igvc_robot` workspace, flashing firmware, and resolving motor/serial issues.

## Robot and stack

- **Platform:** TurtleBot3 **Burger** (wheel motors: [XL430-W250](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/))
- **Controller:** OpenCR 1.0
- **Compute:** NVIDIA Jetson Orin (ARM64)
- **ROS:** ROS 2 Humble
- **Workspace:** `~/ros2_ws` — package `igvc_robot` (localization + optional legacy encoder bridge)

## What was configured in this repo (`igvc_robot`)

### New / updated pieces

1. **`launch/turtlebot3_base.launch.py`**  
   - Sets `TURTLEBOT3_MODEL=burger`  
   - Includes upstream `turtlebot3_state_publisher.launch.py`  
   - Runs `turtlebot3_node` (`turtlebot3_ros`) with `-i <opencr_port>`  
   - Default `opencr_port`: `/dev/ttyACM1` (see **Serial ports** below — after flash you may need `/dev/ttyACM0`)

2. **`config/turtlebot3_burger.yaml`**  
   - Matches upstream Burger params (OpenCR id 200, baud `1000000`, protocol 2.0, wheel separation/radius).  
   - **`diff_drive_controller.odometry.publish_tf: false`** so **robot_localization** remains the single publisher of `odom → base_*` (avoids double TF with TurtleBot3’s default).

3. **`launch/turtlebot3_localization.launch.py`**  
   - Chains `turtlebot3_base.launch.py` + `localization.launch.py`  
   - Passes `launch_encoder_bridge:=false`, `base_frame:=base_footprint` (aligned with TurtleBot3 URDF `base_footprint → base_link`).

4. **`launch/localization.launch.py`**  
   - `launch_encoder_bridge` default **`false`** (TurtleBot3 is the wheel source).  
   - `base_frame` launch arg feeds EKF `base_link_frame`.  
   - Legacy Arduino `encoder_bridge` only when `launch_encoder_bridge:=true`.

5. **`package.xml`**  
   - `exec_depend` on `turtlebot3_bringup`, `turtlebot3_node`, `turtlebot3_description`, `xacro`.

### Commands (after `colcon build` + `source install/setup.bash`)

```bash
# Base only (OpenCR + state publisher + turtlebot3_node)
ros2 launch igvc_robot turtlebot3_base.launch.py opencr_port:=/dev/ttyACM0

# Base + EKF + optional GPS (same as before, but TB3 odom, no encoder_bridge)
ros2 launch igvc_robot turtlebot3_localization.launch.py opencr_port:=/dev/ttyACM0

# Legacy: Arduino encoder bridge + localization
ros2 launch igvc_robot localization.launch.py launch_encoder_bridge:=true encoder_port:=/dev/ttyARDUINO
```

## OpenCR firmware flash (Jetson — succeeded in chat)

ROBOTIS flow: [OpenCR setup](https://emanual.robotis.com/docs/en/platform/turtlebot3/opencr_setup/)

```bash
sudo dpkg --add-architecture armhf
sudo apt-get update
sudo apt-get install -y libc6:armhf

export OPENCR_PORT=/dev/ttyACM1   # use whatever device exists when you flash
export OPENCR_MODEL=burger

cd ~
rm -rf opencr_update opencr_update.tar.bz2
wget https://github.com/ROBOTIS-GIT/OpenCR-Binaries/raw/master/turtlebot3/ROS2/latest/opencr_update.tar.bz2
tar -xvf opencr_update.tar.bz2
cd opencr_update
./update.sh "$OPENCR_PORT" "$OPENCR_MODEL.opencr"
```

Example success: `fw_name: burger`, `fw_ver: V230127R1`, `[OK] Download`, `[OK] jump_to_fw`.

Recovery if upload fails: hold **SW2**, press **RESET**, release **RESET**, release **SW2**, then retry.

## Serial ports: ACM0 vs ACM1

- After replug/reset, the OpenCR may appear as **`/dev/ttyACM0`** or **`/dev/ttyACM1`** — always check:

  ```bash
  ls -l /dev/ttyACM*
  python3 -m serial.tools.list_ports -v
  ```

- **`arduino-cli board list` mis-identifying OpenCR as “Arduino UNO”** is a known quirk; trust `udev`/VID:PID and which device appears when only OpenCR is plugged in.

## Symptoms observed

| Symptom | Meaning |
|--------|---------|
| `Failed to open the port(/dev/ttyACM1)` | Wrong device node (e.g. only ACM0 exists). |
| Port opens, baud changes OK, then `Failed connection with Devices` | USB to OpenCR works; **DYNAMIXEL bus** (motors, power, IDs, wiring) not OK for TurtleBot3 firmware. |
| SW1 / SW2 long-press does **not** move wheels | Same: motors not provisioned or no motor power / bad daisy-chain. |
| `terminate ... RCLError ... rcl node's context is invalid` after the above | Follow-on crash after `turtlebot3_node` fails initialization; fix motor connection first. |

## Motor setup (required when SW test and ROS both fail)

Official procedure: [TurtleBot3 FAQ — Setup DYNAMIXELs](https://emanual.robotis.com/docs/en/platform/turtlebot3/faq/#setup-dynamixels-for-turtlebot3)

**Rule:** connect **only one** XL430 at a time while running `turtlebot3_setup_motor`.

### Why not Arduino CLI on Jetson?

On Jetson, `arduino-cli core install OpenCR:OpenCR` failed with **platform not available for your OS**. The OpenCR package index only lists host tools for **x86_64 / i686 Linux**, Windows, and Intel macOS — not **aarch64**. So the **supported** way to upload `turtlebot3_setup_motor` is an **x86 PC + Arduino IDE** (or x86 with Arduino CLI if you install the core there). Jetson remains ideal for the **shell `.opencr` flasher** you already used.

### Short PC checklist (Arduino IDE)

1. Preferences → Additional Boards Manager URL:  
   `https://raw.githubusercontent.com/ROBOTIS-GIT/OpenCR/master/arduino/opencr_release/package_opencr_index.json`
2. Boards Manager → install **OpenCR**.
3. Board: **OpenCR Board**; select correct **Port**.
4. Examples → **turtlebot3** → **turtlebot3_setup** → **turtlebot3_setup_motor** → Upload.
5. **Left motor:** power off, only one XL430 connected, Serial Monitor → left setup → confirm → test.
6. **Right motor:** power off, swap to other XL430 only → right setup → test.
7. Reconnect both motors; reflash **Burger** ROS 2 firmware (shell script on Jetson or Burger sketch on PC).
8. **Hardware test:** long-press SW1 / SW2 — robot should move.
9. **ROS test on Jetson:**  
   `ros2 launch igvc_robot turtlebot3_base.launch.py opencr_port:=/dev/ttyACM0`  
   Expect `/joint_states`, `/odom`, `/imu` without `Failed connection with Devices`.

### Repo scripts (`ros2_ws/scripts/`)

Run **laptop** steps in a terminal **on the laptop** (not only an SSH session to the Jetson) while OpenCR USB is on the laptop. After that, move OpenCR USB to the Jetson for flash + ROS.

| Script | Where to run | Purpose |
|--------|----------------|--------|
| `opencr_laptop_setup_helper.sh` | **Laptop** (`x86_64`) | Checks arch / `dialout` / `ttyACM*`, prints Arduino + motor-setup checklist |
| `opencr_jetson_flash_burger.sh` | **Jetson** | `libc6:armhf`, download ROS 2 Burger `.opencr`, run `update.sh` |
| `verify_turtlebot3_base.sh` | **Jetson** | Sources `install/setup.bash`, launches `turtlebot3_base` briefly, checks `/joint_states`, `/odom`, `/imu` |

Example on Jetson (OpenCR plugged into Jetson):  
`~/ros2_ws/scripts/opencr_jetson_flash_burger.sh`  
`~/ros2_ws/scripts/verify_turtlebot3_base.sh`

## References

- [TurtleBot3 OpenCR setup](https://emanual.robotis.com/docs/en/platform/turtlebot3/opencr_setup/)
- [TurtleBot3 DYNAMIXEL appendix (Burger = XL430)](https://emanual.robotis.com/docs/en/platform/turtlebot3/appendix_dynamixel/)
- [XL430-W250 e-Manual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)
- [OpenCR-Binaries (ROS2 burger.opencr)](https://github.com/ROBOTIS-GIT/OpenCR-Binaries)

## Note on “whole chat”

This file is a **structured summary** of the conversation (decisions, commands, errors, next steps). For a **verbatim** export of the chat UI, use Cursor’s chat export/copy feature and save alongside this file if needed.

---

*Generated from project setup discussion; keep in version control if useful for the team.*
