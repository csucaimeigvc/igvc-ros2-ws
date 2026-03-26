import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    igvc_share = get_package_share_directory("igvc_robot")
    ublox_share = get_package_share_directory("ublox_gps")

    encoder_config = os.path.join(igvc_share, "config", "encoder_bridge.yaml")
    base_frame = LaunchConfiguration("base_frame")

    local_ekf_params = {
        "frequency": 30.0,
        "sensor_timeout": 0.5,
        "two_d_mode": True,
        "publish_tf": True,
        "publish_acceleration": False,
        "map_frame": "map",
        "odom_frame": "odom",
        "base_link_frame": base_frame,
        "world_frame": "odom",
        "odom0": "/odom",
        "odom0_config": [
            False, False, False,
            False, False, False,
            True, False, False,
            False, False, True,
            False, False, False,
        ],
    }

    global_ekf_params = {
        "frequency": 30.0,
        "sensor_timeout": 0.5,
        "two_d_mode": True,
        "publish_tf": True,
        "publish_acceleration": False,
        "map_frame": "map",
        "odom_frame": "odom",
        "base_link_frame": base_frame,
        "world_frame": "map",
        "odom0": "/odometry/local",
        "odom0_config": [
            True, True, False,
            False, False, True,
            True, False, False,
            False, False, True,
            False, False, False,
        ],
        "odom1": "/odometry/gps",
        "odom1_config": [
            True, True, False,
            False, False, False,
            False, False, False,
            False, False, False,
            False, False, False,
        ],
    }

    navsat_params = {
        "frequency": 10.0,
        "delay": 0.0,
        "magnetic_declination_radians": 0.0,
        "yaw_offset": 0.0,
        "zero_altitude": True,
        "publish_filtered_gps": False,
        "broadcast_utm_transform": False,
        "use_odometry_yaw": True,
        "wait_for_datum": False,
    }

    gps_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ublox_share, "launch", "neo_f10n.launch.py")
        ),
        launch_arguments={"port": LaunchConfiguration("gps_port")}.items(),
        condition=IfCondition(LaunchConfiguration("enable_gps_fusion")),
    )

    encoder_node = Node(
        package="igvc_robot",
        executable="encoder_bridge",
        name="encoder_bridge",
        parameters=[encoder_config, {"port": LaunchConfiguration("encoder_port")}],
        output="screen",
        condition=IfCondition(LaunchConfiguration("launch_encoder_bridge")),
    )

    local_ekf_node = Node(
        package="robot_localization",
        executable="ekf_node",
        name="ekf_local_filter_node",
        parameters=[local_ekf_params],
        remappings=[("odometry/filtered", "/odometry/local")],
        output="screen",
    )

    navsat_node = Node(
        package="robot_localization",
        executable="navsat_transform_node",
        name="navsat_transform",
        parameters=[navsat_params],
        remappings=[
            ("gps/fix", "/gps/fix"),
            ("odometry/filtered", "/odometry/local"),
            ("odometry/gps", "/odometry/gps"),
        ],
        output="screen",
        condition=IfCondition(LaunchConfiguration("enable_gps_fusion")),
    )

    global_ekf_node = Node(
        package="robot_localization",
        executable="ekf_node",
        name="ekf_global_filter_node",
        parameters=[global_ekf_params],
        remappings=[("odometry/filtered", "/odometry/filtered")],
        output="screen",
        condition=IfCondition(LaunchConfiguration("enable_gps_fusion")),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "encoder_port",
                default_value="/dev/ttyARDUINO",
                description="Serial device for the Arduino encoder bridge",
            ),
            DeclareLaunchArgument(
                "launch_encoder_bridge",
                default_value="false",
                description="Launch the legacy Arduino encoder bridge when true",
            ),
            DeclareLaunchArgument(
                "gps_port",
                default_value="/dev/ttyNEO_F10N",
                description="Serial device for the u-blox GPS receiver",
            ),
            DeclareLaunchArgument(
                "base_frame",
                default_value="base_link",
                description="Base frame published by localization",
            ),
            DeclareLaunchArgument(
                "enable_gps_fusion",
                default_value="true",
                description="Launch GPS + global fusion nodes when true",
            ),
            gps_launch,
            encoder_node,
            local_ekf_node,
            navsat_node,
            global_ekf_node,
        ]
    )
