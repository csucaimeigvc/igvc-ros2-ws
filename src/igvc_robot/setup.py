from glob import glob
from setuptools import find_packages, setup


package_name = "igvc_robot"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="IGVC Team",
    maintainer_email="igvc@example.com",
    description="IGVC robot TurtleBot3/OpenCR bringup and localization package.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "encoder_bridge = igvc_robot.encoder_bridge:main",
        ],
    },
)
