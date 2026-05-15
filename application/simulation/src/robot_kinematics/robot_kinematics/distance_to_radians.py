#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState


class DistanceToRadiansNode(Node):
    def __init__(self):
        super().__init__("distance_to_radians")

        self.declare_parameter("pulley_radius", 0.00637)
        self.declare_parameter("x_limits", [-0.1475, 0.1475])
        self.declare_parameter("y_limits", [-0.13, 0.13])

        self.pulley_radius = self.get_parameter("pulley_radius").value
        self.x_limits = self.parse_limits("x_limits")
        self.y_limits = self.parse_limits("y_limits")

        self.radians_publisher = self.create_publisher(Float64MultiArray, "/delta_radians", 10)
        
        self.current_x = 0.0
        self.current_y = 0.0
        self.position_initialized = False
        
        self.actual_position_subscriber = self.create_subscription(JointState, "/joint_states", self.joint_states_callback, 10)
        self.create_subscription(Float64MultiArray, "/delta_distance", self.to_radians, 10)

    def parse_limits(self, parameter_name: str):
        limits = list(self.get_parameter(parameter_name).value)
        return (float(limits[0]), float(limits[1]))

    def joint_states_callback(self, msg: JointState):
        idx_a = msg.name.index("motorA_joint")
        idx_b = msg.name.index("motorB_joint")
        
        motor_a_pos = msg.position[idx_a]
        motor_b_pos = msg.position[idx_b]

        belt_a = motor_a_pos * self.pulley_radius
        belt_b = motor_b_pos * self.pulley_radius

        self.current_x = 0.5 * (belt_a + belt_b)
        self.current_y = 0.5 * (belt_a - belt_b)
        self.position_initialized = True

    def to_radians(self, msg: Float64MultiArray):
        if len(msg.data) < 2:
            self.get_logger().error("Wrong data")
            return
        
        delta_x = float(msg.data[0])
        delta_y = float(msg.data[1])

        requested_x = self.current_x + delta_x
        requested_y = self.current_y + delta_y

        if requested_x < self.x_limits[0] or requested_x > self.x_limits[1] or \
           requested_y < self.y_limits[0] or requested_y > self.y_limits[1]:
            self.get_logger().error(f"ruch poza zakres")
            return

        delta_belt_a = delta_x + delta_y
        delta_belt_b = delta_x - delta_y

        delta_a_rad = delta_belt_a / self.pulley_radius
        delta_b_rad = delta_belt_b / self.pulley_radius

        radians = Float64MultiArray()
        radians.data = [delta_a_rad, delta_b_rad]
        self.radians_publisher.publish(radians)


def main():
    rclpy.init()
    node = DistanceToRadiansNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
