#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState
import math

class MoveZNode(Node):
    def __init__(self):
        super().__init__("move_z")

        self.pitch = 0.002 
        
        self.current_z_linear = 0.0
        self.target_z_linear = 0.0
        self.cmd_z_linear = 0.0 
        
        self.is_moving = False
        
        self.timer_period = 0.02  
        self.linear_speed = 0.01 
        self.step_size = self.linear_speed * self.timer_period 

        self.z_axis_service = self.create_service(SetBool, '/set_z_axis_state', self.set_z_state_callback)
        self.z_pub = self.create_publisher(Float64MultiArray, '/z_position_controller/commands', 10)
        self.joint_sub = self.create_subscription(JointState, '/joint_states', self.joint_state_callback, 10)
        
        self.timer = self.create_timer(self.timer_period, self.control_loop)


    def joint_state_callback(self, msg: JointState):
        if 'z_linear_axis_joint' in msg.name:
            linear_idx = msg.name.index('z_linear_axis_joint')
            self.current_z_linear = msg.position[linear_idx]


    def calculate_angular_from_linear(self, linear_z: float) -> float:
        return (linear_z / self.pitch) * 2.0 * math.pi

    def set_z_state_callback(self, request: SetBool.Request, response: SetBool.Response):
        if request.data:
            self.target_z_linear = 0.0
            response.message = "Mouse is up"
        else:
            self.target_z_linear = -0.01
            response.message = "Mouse is down"
            
        self.cmd_z_linear = self.current_z_linear
        self.is_moving = True
            
        response.success = True
        return response

    def control_loop(self):
        if not self.is_moving:
            return

        diff = self.target_z_linear - self.cmd_z_linear

        if abs(diff) <= self.step_size:
            self.cmd_z_linear = self.target_z_linear
            self.is_moving = False
        else:
            direction = 1.0 if diff > 0 else -1.0
            self.cmd_z_linear += direction * self.step_size

        cmd_z_angular = self.calculate_angular_from_linear(self.cmd_z_linear)

        msg = Float64MultiArray()
        msg.data = [cmd_z_angular, self.cmd_z_linear]
        self.z_pub.publish(msg)
    
def main(args=None):
    rclpy.init()
    node = MoveZNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()