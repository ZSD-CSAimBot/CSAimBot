#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
from std_msgs.msg import Float64MultiArray
from math import pi

class GripperNode(Node):
    def __init__(self):
        super().__init__("gripper")

        self.gear_radius = 0.0075  
        
        self.servo_angle_opened = 0.0
        self.servo_angle_closed = -pi/2.0 
        
        self.current_servo_angle = self.servo_angle_opened
        self.target_servo_angle = self.servo_angle_opened
        
        self.timer_period = 0.02  
        self.closing_time = 1.0  
        
        total_distance = abs(self.servo_angle_closed - self.servo_angle_opened)
        self.step_size = (total_distance / self.closing_time) * self.timer_period

        self.gripper_service = self.create_service(SetBool, '/set_gripper_state', self.set_gripper_state_callback)
        self.gripper_pub = self.create_publisher(Float64MultiArray, '/gripper_position_controller/commands', 10)
        self.timer = self.create_timer(self.timer_period, self.control_loop)
        

    def set_gripper_state_callback(self, request: SetBool.Request, response: SetBool.Response):
        epsilon = 0.001 

        if request.data:
            self.target_servo_angle = self.servo_angle_closed
            
            if abs(self.current_servo_angle - self.servo_angle_closed) <= epsilon:
                response.message = "Gripper is closed"
            else:
                response.message = "Gripper is closing"
        else:
            self.target_servo_angle = self.servo_angle_opened
            
            if abs(self.current_servo_angle - self.servo_angle_opened) <= epsilon:
                response.message = "Gripper is open"
            else:
                response.message = "Gripper is opening"
            
        response.success = True
        return response

    def control_loop(self):
        if abs(self.target_servo_angle - self.current_servo_angle) > 0.001:
            if self.current_servo_angle < self.target_servo_angle:
                self.current_servo_angle = min(self.current_servo_angle + self.step_size, self.target_servo_angle)
            else:
                self.current_servo_angle = max(self.current_servo_angle - self.step_size, self.target_servo_angle)

        gripper_right_pos = -self.current_servo_angle * self.gear_radius
        gripper_left_pos = self.current_servo_angle * self.gear_radius

        msg = Float64MultiArray()
        msg.data = [self.current_servo_angle, gripper_right_pos, gripper_left_pos]
        self.gripper_pub.publish(msg)

def main(args=None):
    rclpy.init()
    node = GripperNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()