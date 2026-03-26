import math
import re
import time
from typing import Dict, Optional

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32MultiArray
from tf2_ros import TransformBroadcaster

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - handled at runtime on target
    serial = None
    SerialException = Exception


class EncoderBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("encoder_bridge")

        self.declare_parameter("port", "/dev/ttyARDUINO")
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("reconnect_interval_s", 2.0)
        self.declare_parameter("wheel_radius_m", 0.127)
        self.declare_parameter("track_width_m", 0.6)
        self.declare_parameter("counts_per_revolution", 8192.0)
        self.declare_parameter("gear_ratio", 1.0)
        self.declare_parameter("left_sign", 1)
        self.declare_parameter("right_sign", 1)
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("publish_tf", False)
        self.declare_parameter("legacy_single_encoder_is_left", True)

        self.port = self.get_parameter("port").value
        self.baudrate = int(self.get_parameter("baudrate").value)
        self.reconnect_interval_s = float(
            self.get_parameter("reconnect_interval_s").value
        )
        self.wheel_radius_m = float(self.get_parameter("wheel_radius_m").value)
        self.track_width_m = float(self.get_parameter("track_width_m").value)
        self.counts_per_revolution = float(
            self.get_parameter("counts_per_revolution").value
        )
        self.gear_ratio = float(self.get_parameter("gear_ratio").value)
        self.left_sign = int(self.get_parameter("left_sign").value)
        self.right_sign = int(self.get_parameter("right_sign").value)
        self.odom_frame = self.get_parameter("odom_frame").value
        self.base_frame = self.get_parameter("base_frame").value
        self.publish_tf = bool(self.get_parameter("publish_tf").value)
        self.legacy_single_encoder_is_left = bool(
            self.get_parameter("legacy_single_encoder_is_left").value
        )

        counts_per_wheel_turn = self.counts_per_revolution * self.gear_ratio
        self.meters_per_count = (2.0 * math.pi * self.wheel_radius_m) / counts_per_wheel_turn
        self.radians_per_count = (2.0 * math.pi) / counts_per_wheel_turn

        self.ticks_pub = self.create_publisher(Int32MultiArray, "wheel_ticks", 10)
        self.joint_pub = self.create_publisher(JointState, "wheel_joint_states", 10)
        self.odom_pub = self.create_publisher(Odometry, "odom", 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None

        self.serial_conn = None
        self.last_connect_attempt = 0.0
        self.rx_buffer = b""

        self.last_left_count: Optional[int] = None
        self.last_right_count: Optional[int] = None
        self.last_arduino_time_ms: Optional[int] = None
        self.last_ros_time_s: Optional[float] = None

        self.x_m = 0.0
        self.y_m = 0.0
        self.yaw_rad = 0.0
        self.last_warning_time = 0.0

        self.create_timer(0.02, self.poll_serial)
        self.get_logger().info(
            f"Encoder bridge ready on {self.port} @ {self.baudrate} baud"
        )

    def connect_serial(self) -> None:
        if serial is None:
            self.get_logger().error(
                "pyserial is not installed. Install python3-serial before running this node."
            )
            return

        now = time.time()
        if now - self.last_connect_attempt < self.reconnect_interval_s:
            return

        self.last_connect_attempt = now
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0.0)
            self.serial_conn.reset_input_buffer()
            self.rx_buffer = b""
            self.get_logger().info(f"Connected to Arduino encoder bridge on {self.port}")
        except SerialException as exc:
            self.serial_conn = None
            self.get_logger().warning(f"Failed to open {self.port}: {exc}")

    def close_serial(self) -> None:
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except SerialException:
                pass
        self.serial_conn = None
        self.rx_buffer = b""

    def poll_serial(self) -> None:
        if self.serial_conn is None:
            self.connect_serial()
            return

        try:
            bytes_waiting = self.serial_conn.in_waiting
            if bytes_waiting <= 0:
                return

            self.rx_buffer += self.serial_conn.read(bytes_waiting)
            while b"\n" in self.rx_buffer:
                line_bytes, self.rx_buffer = self.rx_buffer.split(b"\n", 1)
                line = line_bytes.decode(errors="ignore").strip()
                if line:
                    self.handle_line(line)
        except (SerialException, OSError) as exc:
            self.get_logger().error(f"Serial connection lost: {exc}")
            self.close_serial()

    def handle_line(self, line: str) -> None:
        data = self.parse_line(line)
        if data is None:
            if time.time() - self.last_warning_time > 5.0:
                self.get_logger().warning(f"Ignoring malformed encoder line: {line}")
                self.last_warning_time = time.time()
            return

        stamp = self.get_clock().now()
        stamp_msg = stamp.to_msg()
        now_s = stamp.nanoseconds / 1e9

        left_count = self.left_sign * data["left"]
        right_count = self.right_sign * data["right"]

        delta_left = 0
        delta_right = 0
        dt = 0.0

        if self.last_left_count is not None and self.last_right_count is not None:
            delta_left = left_count - self.last_left_count
            delta_right = right_count - self.last_right_count

            if self.last_arduino_time_ms is not None and data["t"] > self.last_arduino_time_ms:
                dt = (data["t"] - self.last_arduino_time_ms) / 1000.0
            elif self.last_ros_time_s is not None:
                dt = now_s - self.last_ros_time_s

        self.publish_ticks(left_count, right_count, delta_left, delta_right)
        self.publish_joint_state(stamp_msg, left_count, right_count, delta_left, delta_right, dt)
        self.publish_odometry(stamp_msg, left_count, right_count, delta_left, delta_right, dt)

        self.last_left_count = left_count
        self.last_right_count = right_count
        self.last_arduino_time_ms = data["t"]
        self.last_ros_time_s = now_s

    def publish_ticks(
        self, left_count: int, right_count: int, delta_left: int, delta_right: int
    ) -> None:
        msg = Int32MultiArray()
        msg.data = [left_count, right_count, delta_left, delta_right]
        self.ticks_pub.publish(msg)

    def publish_joint_state(
        self,
        stamp_msg,
        left_count: int,
        right_count: int,
        delta_left: int,
        delta_right: int,
        dt: float,
    ) -> None:
        joint_state = JointState()
        joint_state.header.stamp = stamp_msg
        joint_state.name = ["left_wheel", "right_wheel"]
        joint_state.position = [
            left_count * self.radians_per_count,
            right_count * self.radians_per_count,
        ]

        if dt > 0.0:
            joint_state.velocity = [
                delta_left * self.radians_per_count / dt,
                delta_right * self.radians_per_count / dt,
            ]
        else:
            joint_state.velocity = [0.0, 0.0]

        self.joint_pub.publish(joint_state)

    def publish_odometry(
        self,
        stamp_msg,
        left_count: int,
        right_count: int,
        delta_left: int,
        delta_right: int,
        dt: float,
    ) -> None:
        left_distance = delta_left * self.meters_per_count
        right_distance = delta_right * self.meters_per_count
        center_distance = 0.5 * (left_distance + right_distance)
        delta_yaw = (right_distance - left_distance) / self.track_width_m

        if dt > 0.0:
            heading_mid = self.yaw_rad + (0.5 * delta_yaw)
            self.x_m += center_distance * math.cos(heading_mid)
            self.y_m += center_distance * math.sin(heading_mid)
            self.yaw_rad += delta_yaw

        odom = Odometry()
        odom.header.stamp = stamp_msg
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame
        odom.pose.pose.position.x = self.x_m
        odom.pose.pose.position.y = self.y_m
        odom.pose.pose.orientation.z = math.sin(self.yaw_rad / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.yaw_rad / 2.0)

        odom.pose.covariance[0] = 0.05
        odom.pose.covariance[7] = 0.05
        odom.pose.covariance[35] = 0.1

        if dt > 0.0:
            odom.twist.twist.linear.x = center_distance / dt
            odom.twist.twist.angular.z = delta_yaw / dt

        odom.twist.covariance[0] = 0.05
        odom.twist.covariance[7] = 0.05
        odom.twist.covariance[35] = 0.1

        self.odom_pub.publish(odom)

        if self.tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = stamp_msg
            transform.header.frame_id = self.odom_frame
            transform.child_frame_id = self.base_frame
            transform.transform.translation.x = self.x_m
            transform.transform.translation.y = self.y_m
            transform.transform.rotation.z = odom.pose.pose.orientation.z
            transform.transform.rotation.w = odom.pose.pose.orientation.w
            self.tf_broadcaster.sendTransform(transform)

    def parse_line(self, line: str) -> Optional[Dict[str, int]]:
        match = re.search(r"t=(\d+),left=(-?\d+),right=(-?\d+)", line)
        if match:
            return {
                "t": int(match.group(1)),
                "left": int(match.group(2)),
                "right": int(match.group(3)),
            }

        fields: Dict[str, str] = {}
        for item in line.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            fields[key.strip()] = value.strip()

        if {"t", "left", "right"}.issubset(fields):
            try:
                return {
                    "t": int(fields["t"]),
                    "left": int(fields["left"]),
                    "right": int(fields["right"]),
                }
            except ValueError:
                return None

        if self.legacy_single_encoder_is_left and "count" in fields:
            try:
                legacy_count = int(fields["count"])
                return {
                    "t": self.last_arduino_time_ms + 20 if self.last_arduino_time_ms else 0,
                    "left": legacy_count,
                    "right": self.last_right_count if self.last_right_count is not None else 0,
                }
            except ValueError:
                return None

        return None

    def destroy_node(self) -> bool:
        self.close_serial()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EncoderBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
