from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Declare the serial port argument
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='/dev/ttyNEO_F10N',
        description='Serial port for the GPS device'
    )

    # Create the GPS node
    gps_node = Node(
        package='ublox_gps',
        executable='ublox_gps_node',
        name='ublox_gps_node',
        parameters=[{
            'device': LaunchConfiguration('port'),
            'frame_id': 'gps',
            'uart1.baudrate': 38400,
            'uart1.in': 1,  # UBX only
            'uart1.out': 1,  # UBX only
            'rate': 10.0,  # Must be float
            'nav_rate': 1,
            'config_on_startup': False,
            'publish.nav': True,
            'publish.nav_pvt': True,
            'publish.nav_sat': True,
            'publish.nav_status': True,
            'publish.nav_velned': True,
        }],
        remappings=[
            ('fix', '/gps/fix'),
            ('fix_velocity', '/gps/fix_velocity'),
            ('navsat', '/gps/navsat'),
            ('navsatfix', '/gps/navsatfix'),
            ('navpvt', '/gps/navpvt'),
            ('navsat', '/gps/navsat'),
            ('navstatus', '/gps/navstatus'),
            ('navvelned', '/gps/navvelned'),
        ],
        output='screen'
    )

    return LaunchDescription([
        port_arg,
        gps_node
    ])
