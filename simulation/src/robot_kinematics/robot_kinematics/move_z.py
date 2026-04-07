#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
from std_msgs.msg import Float64MultiArray

class MoveZNode(Node):
    def __init__(self):
        super().__init__("move_z")

        self.z_axis_service = self.create_service(SetBool, '/set_z_axis_state', self.set_z_state_callback)
        self.z_pub = self.create_publisher(Float64MultiArray, '/z_position_controller/commands', 10)

    def set_z_state_callback(self, request: SetBool.Request, response: SetBool.Response):
        msg = Float64MultiArray()
        if request.data:
            # values from yaml: [z_angular_axis_joint, z_linear_axis_joint]
            msg.data = [3.14, 0.005] 
            self.z_pub.publish(msg)
            response.message = "Mouse is up"
        else:
            # values from yaml: [z_angular_axis_joint, z_linear_axis_joint]
            msg.data = [0.0, -0.005]
            self.z_pub.publish(msg)
            response.message = "Mouse is down"
            
        response.success = True
        return response

def main(args=None):
    rclpy.init()
    node = MoveZNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()