from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Declare the serial port argument
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='/dev/ttyNEO_F10N',
        description='Serial port for the NMEA GPS device'
    )

    # Create the NMEA node
    nmea_node = Node(
        package='nmea_navsat_driver',
        executable='nmea_serial_driver',
        name='nmea_serial_driver',
        parameters=[{
            'port': LaunchConfiguration('port'),
            'baud': 38400,
            'frame_id': 'gps',
            'use_GNSS_time': False,
            'time_ref_source': 'gps',
            'useRMEs': True,
            'useRMC': True,
            'useGGA': True,
            'useGLL': True,
            'useVTG': True,
            'useHDT': True,
            'useROT': True,
            'useZDA': True,
            'useGSV': True,
            'useGSA': True,
        }],
        remappings=[
            ('fix', '/gps/fix'),
            ('vel', '/gps/vel'),
            ('time_reference', '/gps/time_reference'),
        ],
        output='screen'
    )

    return LaunchDescription([
        port_arg,
        nmea_node
    ]) 