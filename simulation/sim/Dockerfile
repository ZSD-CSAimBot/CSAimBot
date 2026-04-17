FROM ros:jazzy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN apt-get update && apt-get dist-upgrade -y && apt-get install -y \
    python3-colcon-common-extensions \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-gz-ros2-control \
    ros-jazzy-xacro \
    ros-jazzy-joint-state-publisher \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-controller-manager \
    ros-jazzy-joint-state-broadcaster \
    ros-jazzy-position-controllers \
    ros-jazzy-rosbridge-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /sim_ws
COPY . /sim_ws

RUN chmod +x /sim_ws/start_sim.sh

CMD ["/bin/bash", "/sim_ws/start_sim.sh"]