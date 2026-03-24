#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


class DistanceToRadiansNode(Node):
    def __init__(self):
        super().__init__("distance_to_radians")

        self.radians_publisher = self.create_publisher(Float64MultiArray, "/motor_delta_commands", 10)
        
        
        #TODO self.actual_position_subscriber = self.create_subscription(

        self.create_subscription(Float64MultiArray, "/distance_topic", self.to_radians, 10)


    def to_radians(self, msg: Float64MultiArray):
        if len(msg.data) < 2:
            self.get_logger().error("Wrong data")
            return
        
        delta_x = float(msg.data[0])
        delta_y = float(msg.data[1])

        delta_A = delta_x + delta_y
        delta_B = delta_x - delta_y

        radians = Float64MultiArray()
        radians.data = [delta_A, delta_B]
        self.radians_publisher.publish(radians)


def main():
    rclpy.init()
    node = DistanceToRadiansNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
