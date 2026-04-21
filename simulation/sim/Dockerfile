FROM ros:jazzy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Dodano instalację pakietu 'dos2unix' na końcu listy
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
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /sim_ws
COPY . /sim_ws

# Naprawa znaków końca linii i nadanie uprawnień w jednym kroku
RUN dos2unix /sim_ws/start_sim.sh && chmod +x /sim_ws/start_sim.sh

CMD ["/bin/bash", "/sim_ws/start_sim.sh"]