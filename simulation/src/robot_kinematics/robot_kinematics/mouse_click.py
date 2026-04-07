#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import time
from std_msgs.msg import Empty, Float64MultiArray

class MouseClickNode(Node):
    def __init__(self):
        super().__init__("mouse_click")

        self.left_click_sub = self.create_subscription(Empty, '/click_left', self.left_click_callback, 10)
        self.right_click_sub = self.create_subscription(Empty, '/click_right', self.right_click_callback, 10)

        self.click_pub = self.create_publisher(Float64MultiArray, '/click_position_controller/commands', 10)


    def left_click_callback(self, msg: Empty):
        cmd_msg = Float64MultiArray()
        cmd_msg.data = [0.0, -0.009]
        self.click_pub.publish(cmd_msg)
        
        time.sleep(0.05)
        
        cmd_msg.data = [0.0, 0.0]
        self.click_pub.publish(cmd_msg)

    def right_click_callback(self, msg: Empty):
        cmd_msg = Float64MultiArray()
        cmd_msg.data = [-0.009, 0.0]
        self.click_pub.publish(cmd_msg)
        
        time.sleep(0.05)
        
        cmd_msg.data = [0.0, 0.0]
        self.click_pub.publish(cmd_msg)

def main(args=None):
    rclpy.init()
    node = MouseClickNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()