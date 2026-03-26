import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    igvc_share = get_package_share_directory("igvc_robot")

    turtlebot3_base_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(igvc_share, "launch", "turtlebot3_base.launch.py")
        ),
        launch_arguments={
            "opencr_port": LaunchConfiguration("opencr_port"),
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }.items(),
    )

    localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(igvc_share, "launch", "localization.launch.py")
        ),
        launch_arguments={
            "launch_encoder_bridge": "false",
            "gps_port": LaunchConfiguration("gps_port"),
            "enable_gps_fusion": LaunchConfiguration("enable_gps_fusion"),
            "base_frame": "base_footprint",
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "opencr_port",
                default_value="/dev/ttyACM1",
                description="Connected USB port for the OpenCR board",
            ),
            DeclareLaunchArgument(
                "gps_port",
                default_value="/dev/ttyNEO_F10N",
                description="Serial device for the u-blox GPS receiver",
            ),
            DeclareLaunchArgument(
                "enable_gps_fusion",
                default_value="true",
                description="Launch GPS + global fusion nodes when true",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="false",
                description="Use simulation clock if true",
            ),
            turtlebot3_base_launch,
            localization_launch,
        ]
    )
