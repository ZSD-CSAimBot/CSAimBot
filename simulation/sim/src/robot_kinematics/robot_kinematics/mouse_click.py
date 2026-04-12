#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, Float64MultiArray

class MouseClickNode(Node):
    def __init__(self):
        super().__init__("mouse_click")

        self.right_click_pos = 0.0
        self.left_click_pos = 0.0

        self.left_timer = None
        self.right_timer = None

        self.left_click_sub = self.create_subscription(Empty, '/click_left', self.left_click_callback, 10)
        self.right_click_sub = self.create_subscription(Empty, '/click_right', self.right_click_callback, 10)

        self.click_pub = self.create_publisher(Float64MultiArray, '/click_position_controller/commands', 10)
        

    def publish_click_state(self):
        cmd_msg = Float64MultiArray()
        cmd_msg.data = [self.right_click_pos, self.left_click_pos]
        self.click_pub.publish(cmd_msg)

    def left_click_callback(self, msg: Empty):
        self.left_click_pos = -0.009
        self.publish_click_state()
        
        if self.left_timer is not None:
            self.left_timer.cancel()
            
        self.left_timer = self.create_timer(0.1, self.release_left_click)

    def release_left_click(self):
        if self.left_timer is not None:
            self.left_timer.cancel()
            
        self.left_click_pos = 0.0
        self.publish_click_state()

    def right_click_callback(self, msg: Empty):
        self.right_click_pos = -0.009
        self.publish_click_state()
        
        if self.right_timer is not None:
            self.right_timer.cancel()
            
        self.right_timer = self.create_timer(0.05, self.release_right_click)

    def release_right_click(self):
        if self.right_timer is not None:
            self.right_timer.cancel()
            
        self.right_click_pos = 0.0
        self.publish_click_state()

def main(args=None):
    rclpy.init()
    node = MouseClickNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()