#!/usr/bin/env python3

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


class MotorToCorexyNode(Node):
    def __init__(self):
        super().__init__("motor_to_corexy")

        self.declare_parameter("delta_topic", "/motor_delta_commands")
        self.declare_parameter("motor_command_topic", "/motor_position_controller/commands")
        self.declare_parameter("xy_command_topic", "/xy_position_controller/commands")
        self.declare_parameter("initial_motor_positions", [0.0, 0.0])
        self.declare_parameter("initial_xy_positions", [0.0, 0.0])
        self.declare_parameter("pulley_radius", 0.03)
        self.declare_parameter("x_sign", 1.0)
        self.declare_parameter("y_sign", 1.0)
        self.declare_parameter("x_limits", [-0.18, 0.24])
        self.declare_parameter("y_limits", [-0.17, 0.17])

        self.delta_topic = self.get_parameter("delta_topic").value
        self.motor_command_topic = self.get_parameter("motor_command_topic").value
        self.xy_command_topic = self.get_parameter("xy_command_topic").value
        initial_motor_positions = self.get_parameter("initial_motor_positions").value
    
        initial_xy_positions = self.get_parameter("initial_xy_positions").value
   
        self.motor_positions = [initial_motor_positions[0], initial_motor_positions[1]]
        self.xy_positions = [initial_xy_positions[0], initial_xy_positions[1]]

        self.pulley_radius = self.get_parameter("pulley_radius").value
        self.x_sign = self.get_parameter("x_sign").value
        self.y_sign = self.get_parameter("y_sign").value
        self.x_limits = self.parse_limits("x_limits")
        self.y_limits = self.parse_limits("y_limits")

        self.motor_command_publisher = self.create_publisher(Float64MultiArray, self.motor_command_topic, 10)
        self.xy_command_publisher = self.create_publisher(Float64MultiArray, self.xy_command_topic, 10)
        self.create_subscription(Float64MultiArray, self.delta_topic, self.on_delta_command, 10)

    def on_delta_command(self, msg: Float64MultiArray):
        if len(msg.data) < 2:
            self.get_logger().error("Wrong data")
            return

        delta_a = float(msg.data[0])
        delta_b = float(msg.data[1])

        self.motor_positions[0] += delta_a
        self.motor_positions[1] += delta_b

        belt_a = self.pulley_radius * delta_a
        belt_b = self.pulley_radius * delta_b

        delta_x = self.x_sign * 0.5 * (belt_a + belt_b)
        delta_y = self.y_sign * 0.5 * (belt_a - belt_b)

        self.xy_positions[0] = self.clamp(self.xy_positions[0] + delta_x, self.x_limits)
        self.xy_positions[1] = self.clamp(self.xy_positions[1] + delta_y, self.y_limits)

        self.publish_commands()

    def parse_limits(self, parameter_name: str):
        limits = list(self.get_parameter(parameter_name).value)
        lower = float(limits[0])
        upper = float(limits[1])
        return (lower, upper)

    def clamp(self, value: float, limits: tuple[float, float]):
        return min(max(value, limits[0]), limits[1])

    def publish_commands(self):
        motor_command = Float64MultiArray()
        motor_command.data = list(self.motor_positions)
        self.motor_command_publisher.publish(motor_command)

        xy_command = Float64MultiArray()
        xy_command.data = list(self.xy_positions)
        self.xy_command_publisher.publish(xy_command)


def main():
    rclpy.init()
    node = MotorToCorexyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
