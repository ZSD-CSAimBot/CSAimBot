#!/usr/bin/env python3

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
import math


class MotorToCorexyNode(Node):
    def __init__(self):
        super().__init__("motor_to_corexy")

        self.declare_parameter("radians_topic", "/delta_radians")
        self.declare_parameter("motor_command_topic", "/motor_position_controller/commands")
        self.declare_parameter("xy_command_topic", "/xy_position_controller/commands")

        self.declare_parameter("initial_motor_positions", [0.0, 0.0])
        self.declare_parameter("initial_xy_positions", [0.0, 0.0])
        self.declare_parameter("pulley_radius", 0.00637)
        self.declare_parameter("x_limits", [-0.1475, 0.1475])
        self.declare_parameter("y_limits", [-0.13, 0.13])
        self.declare_parameter("control_rate_hz", 100.0)
        self.declare_parameter("xy_max_velocity", 0.25)

        self.radians_topic = self.get_parameter("radians_topic").value
        self.motor_command_topic = self.get_parameter("motor_command_topic").value
        self.xy_command_topic = self.get_parameter("xy_command_topic").value
        
        self.control_rate = self.get_parameter("control_rate_hz").value
        self.max_velocity = self.get_parameter("xy_max_velocity").value
        
        initial_motor_positions = self.get_parameter("initial_motor_positions").value
        initial_xy_positions = self.get_parameter("initial_xy_positions").value
   
        self.target_xy_positions = [initial_xy_positions[0], initial_xy_positions[1]]
        
        self.current_motor_positions = [initial_motor_positions[0], initial_motor_positions[1]]
        self.current_xy_positions = [initial_xy_positions[0], initial_xy_positions[1]]

        self.pulley_radius = self.get_parameter("pulley_radius").value
        self.x_limits = self.parse_limits("x_limits")
        self.y_limits = self.parse_limits("y_limits")

        self.motor_command_publisher = self.create_publisher(Float64MultiArray, self.motor_command_topic, 10)
        self.xy_command_publisher = self.create_publisher(Float64MultiArray, self.xy_command_topic, 10)
        self.create_subscription(Float64MultiArray, self.radians_topic, self.on_delta_command, 10)

        self.timer = self.create_timer(1.0 / self.control_rate, self.control_loop)

    def on_delta_command(self, msg: Float64MultiArray):
        if len(msg.data) < 2:
            self.get_logger().error("Wrong data")
            return

        delta_a = float(msg.data[0])
        delta_b = float(msg.data[1])

        belt_a = self.pulley_radius * delta_a
        belt_b = self.pulley_radius * delta_b

        delta_x = 0.5 * (belt_a + belt_b)
        delta_y = 0.5 * (belt_a - belt_b)

        self.target_xy_positions[0] = self.clamp(self.target_xy_positions[0] + delta_x, self.x_limits)
        self.target_xy_positions[1] = self.clamp(self.target_xy_positions[1] + delta_y, self.y_limits)

    def parse_limits(self, parameter_name: str):
        limits = list(self.get_parameter(parameter_name).value)
        lower = float(limits[0])
        upper = float(limits[1])
        return (lower, upper)

    def clamp(self, value, limits):
        return min(max(value, limits[0]), limits[1])

    def control_loop(self):
        dt = 1.0 / self.control_rate

        dx = self.target_xy_positions[0] - self.current_xy_positions[0]
        dy = self.target_xy_positions[1] - self.current_xy_positions[1]
        dist = math.hypot(dx, dy)

        step_x = 0.0
        step_y = 0.0

        if dist > 0.0001:
            max_step = self.max_velocity * dt
            if dist > max_step:
                step_x = (dx / dist) * max_step
                step_y = (dy / dist) * max_step
            else:
                step_x = dx
                step_y = dy

            self.current_xy_positions[0] += step_x
            self.current_xy_positions[1] += step_y

        if abs(step_x) > 0.0 or abs(step_y) > 0.0:
            step_belt_a = step_x + step_y
            step_belt_b = step_x - step_y

            step_motor_a = step_belt_a / self.pulley_radius
            step_motor_b = step_belt_b / self.pulley_radius

            self.current_motor_positions[0] += step_motor_a
            self.current_motor_positions[1] += step_motor_b

        self.publish_commands()

    def publish_commands(self):
        motor_command = Float64MultiArray()
        motor_command.data = list(self.current_motor_positions)
        self.motor_command_publisher.publish(motor_command)

        xy_command = Float64MultiArray()
        xy_command.data = list(self.current_xy_positions)
        self.xy_command_publisher.publish(xy_command)


def main():
    rclpy.init()
    node = MotorToCorexyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
