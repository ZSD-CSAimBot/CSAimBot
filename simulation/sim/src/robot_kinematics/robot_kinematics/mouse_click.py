#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, Float64MultiArray

class MouseClickNode(Node):
    def __init__(self):
        super().__init__("mouse_click")

        # Keep the click command slightly inside the joint limits to avoid
        # pressing the simulated plungers into their hard stops.
        self.click_press_pos = -0.0035
        self.left_release_delay = 0.1
        self.right_release_delay = 0.05

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

    def _reset_timer(self, timer):
        if timer is not None:
            timer.cancel()
            self.destroy_timer(timer)
        return None

    def left_click_callback(self, msg: Empty):
        self.left_click_pos = self.click_press_pos
        self.publish_click_state()

        self.left_timer = self._reset_timer(self.left_timer)
        self.left_timer = self.create_timer(self.left_release_delay, self.release_left_click)

    def release_left_click(self):
        self.left_timer = self._reset_timer(self.left_timer)
        self.left_click_pos = 0.0
        self.publish_click_state()

    def right_click_callback(self, msg: Empty):
        self.right_click_pos = self.click_press_pos
        self.publish_click_state()

        self.right_timer = self._reset_timer(self.right_timer)
        self.right_timer = self.create_timer(self.right_release_delay, self.release_right_click)

    def release_right_click(self):
        self.right_timer = self._reset_timer(self.right_timer)
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
