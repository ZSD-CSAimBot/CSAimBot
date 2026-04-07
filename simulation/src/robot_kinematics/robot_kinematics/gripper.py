#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
from std_msgs.msg import Float64MultiArray

class GripperNode(Node):
    def __init__(self):
        super().__init__("gripper")

        self.gripper_service = self.create_service(SetBool, '/set_gripper_state', self.set_gripper_state_callback)
        self.gripper_pub = self.create_publisher(Float64MultiArray, '/gripper_position_controller/commands', 10)

    def set_gripper_state_callback(self, request: SetBool.Request, response: SetBool.Response):
        msg = Float64MultiArray()
        if request.data:
            # values from yaml: servo, left gripper, right gripper
            msg.data = [0.5, 0.02, -0.02] 
            self.gripper_pub.publish(msg)
            response.message = "Gripper closed"
        else:
            # values from yaml: servo, left gripper, right gripper
            msg.data = [0.0, 0.0, 0.0]
            self.gripper_pub.publish(msg)
            response.message = "Gripper opened"
            
        response.success = True
        return response

def main(args=None):
    rclpy.init()
    node = GripperNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()