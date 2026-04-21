#!/bin/bash
set -e

cd /sim_ws

source /opt/ros/jazzy/setup.bash

colcon build

source /sim_ws/install/setup.bash

ros2 launch robot_bringup docker.launch.xml
