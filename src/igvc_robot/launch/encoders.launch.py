import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    encoder_config = os.path.join(
        get_package_share_directory("igvc_robot"), "config", "encoder_bridge.yaml"
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "encoder_port",
                default_value="/dev/ttyARDUINO",
                description="Serial device for the Arduino encoder bridge",
            ),
            Node(
                package="igvc_robot",
                executable="encoder_bridge",
                name="encoder_bridge",
                parameters=[
                    encoder_config,
                    {"port": LaunchConfiguration("encoder_port")},
                ],
                output="screen",
            ),
        ]
    )
