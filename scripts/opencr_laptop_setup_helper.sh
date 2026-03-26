#!/usr/bin/env bash
# Run on your x86_64 Ubuntu laptop in a LOCAL terminal (not inside SSH to the Jetson)
# while the OpenCR micro-USB is plugged into the laptop — for turtlebot3_setup_motor.
set -euo pipefail

arch=$(uname -m)
if [[ "$arch" != "x86_64" ]]; then
  echo "ERROR: OpenCR Arduino core is not available for arch=$arch."
  echo "Run this script on an x86_64 PC with OpenCR connected via USB."
  exit 1
fi

echo "=== OpenCR laptop prerequisites ==="
echo "Architecture: OK ($arch)"
if groups | grep -qw dialout; then
  echo "dialout group: OK"
else
  echo "WARN: add serial access:  sudo usermod -aG dialout \"\$USER\""
  echo "      Then log out and back in (or reboot)."
fi

echo ""
echo "=== USB serial devices (unplug/replug OpenCR to spot the right node) ==="
shopt -s nullglob
acms=(/dev/ttyACM*)
if ((${#acms[@]})); then
  ls -la "${acms[@]}"
else
  echo "(none) — connect OpenCR micro-USB to this laptop."
fi
shopt -u nullglob

echo ""
echo "=== Arduino IDE — Phase A (motor setup) ==="
echo "1) File → Preferences → Additional boards manager URLs:"
echo "   https://raw.githubusercontent.com/ROBOTIS-GIT/OpenCR/master/arduino/opencr_release/package_opencr_index.json"
echo "2) Tools → Board → Boards Manager → install \"OpenCR\"."
echo "3) Tools → Board → OpenCR Board; Tools → Port → pick the ttyACM* above."
echo "4) File → Examples → turtlebot3 → turtlebot3_setup → turtlebot3_setup_motor → Upload."
echo "5) Tools → Serial Monitor — follow prompts: LEFT motor (only that XL430 on bus), then RIGHT."
echo "   Official guide: https://emanual.robotis.com/docs/en/platform/turtlebot3/faq/#setup-dynamixels-for-turtlebot3"
echo ""
echo "After both motors are configured, reconnect both, then on the JETSON run:"
echo "  ~/ros2_ws/scripts/opencr_jetson_flash_burger.sh"
echo "Then:  ~/ros2_ws/scripts/verify_turtlebot3_base.sh"
