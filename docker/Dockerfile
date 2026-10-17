FROM docker.io/osrf/ros:humble-desktop-full

ENV DEBIAN_FRONTEND=noninteractive


RUN apt-get update && apt-get install -y --no-install-recommends \
    nano \
    git \
    python3-pip \
    ros-humble-ros-ign-bridge \
    ros-humble-ros-ign-gazebo \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    opencv-python \
    tqdm \
    numpy \
    networkx \
    pillow \
    moviepy \
    google-generativeai \
    pytubefix \
    matplotlib


RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "if [ -f /root/ros2_orin_ws/install/setup.bash ]; then source /root/ros2_orin_ws/install/setup.bash; fi" >> /root/.bashrc && \
    echo "source ~/ros2_orin_ws/.typerc">>~/.bashrc \
    echo "mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root" >> /root/.bashrc

WORKDIR /root/ros2_orin_ws

CMD ["/bin/bash"]