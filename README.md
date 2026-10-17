# # EyeCode Tech AI Research Intern — Technical Evaluation

This repository contains the implementation and technical deliverables for the EyeCode Research Intern Evaluation. The project comprises two primary milestones:
* **Part 1:** System Bringup, Sensor Visualization, SLAM Mapping, and Nav2 Autonomous Navigation on the Hiwonder ROSOrin Pro platform (Ignition Gazebo).
* **Part 2:** Academic Literature Review, Comparative Architecture Analysis, and Reproduction of Embodied AI Models (*Mobility VLA* & *NaVILA*).

---

## Deliverables Summary

* **Technical Report:** [docs/report.pdf](docs/report.pdf)
* **Part 1 Video Demo:** [YouTube Video Link (Unlisted)](#)

---

## Hardware & System Configurations

* **Host System:** Ubuntu 24.04 LTS
* **GPU:** NVIDIA GPU with `nvidia-container-toolkit` installed

---

## Quickstart & Reproduction Guide

### Step 1: Environment Docker

1. Grant X11 access permissions on host:

```
xhost +local:root
```
2. Clone this repository into your workspace
3. Spin up the hardware-accelerated ROS 2 Humble container:
   
```
chmod +x docker/run_container.sh
./docker/run_container.sh
```
4. Inside the container, build the workspace:
   
```
cd /root/ros2_orin_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```
   
### Step 2: Execution Instructions

1. Launch Simulation World & Sensor
   
```
source /root/ros2_orin_ws/install/setup.bash
ros2 launch robot_gazebo room_worlds.launch.py
```
2. SLAM Mapping (2nd terminal)
   
```
source /root/ros2_orin_ws/install/setup.bash
ros2 launch robot_gazebo slam.launch.py
```
3. Terminal 3: Teleoperate the robot to build the map

```
source /opt/ros/humble/setup.bash
ros2 run robot_gazebo teleop_key_control.py
```
Note: Limit linear velocity to 0.2m/s to prevent Mecanum wheel slip in Gazebo physics.
Once the full map is observed in RViz2, save it:

```
cd ~/ros2_orin_ws/src/simulations/robot_gazebo/maps && ros2 run nav2_map_server map_saver_cli -f "map_01" --ros-args -p map_subscribe_transient_local:=true
```
4. Autonomous Single-Goal & Multi-Point Navigation

Close SLAM nodes, keep Gazebo running in Terminal 1

Terminal 2: Launch Nav2 Navigation Stack

```
source /root/ros2_orin_ws/install/setup.bash
ros2 launch robot_gazebo navigation.launch.py \
  map:=/root/ros2_orin_ws/src/simulations/robot_gazebo/maps/map_01.yaml \
  use_sim_time:=true
```
Single Goal: Use the 2D Pose Estimate tool in RViz to set initial AMCL particles, then click 2D goal Pose to dispatch destinations.

Autonomous Multi-Point: first click the button shown in the lower-left corner (Navigation 2). Then click Nav2 Goal and drag the left mouse button at a point on the map to set the target direction and create a target point. To set multiple target points, repeat the above steps.
Then click Start Waypoint Following to run autonomously.
