#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

class BeltNode(Node):
    def __init__(self):
        super().__init__("belt")

        self.belt_subscription = self.create_subscription(JointState, '/joint_states', self.joint_states_callback, 10)
        self.belt_publisher = self.create_publisher(Float64MultiArray, '/belt_position_controller/commands', 10)

    def joint_states_callback(self, msg: JointState):
        idx_a = msg.name.index("motorA_joint")
        idx_b = msg.name.index("motorB_joint")
        pos_a = msg.position[idx_a]
        pos_b = msg.position[idx_b]

        # motor A
        pos_a_minus_1 = -pos_a
        pos_a_1 = pos_a
        pos_a_2 = pos_a
        pos_a_3 = pos_a

        # motor B
        pos_b_minus_1 = -pos_b
        pos_b_1 = pos_b
        pos_b_2 = pos_b
        pos_b_3 = pos_b

        command_msg = Float64MultiArray()
        command_msg.data = [
            pos_a_minus_1,  # motorA_joint_-1
            pos_a_1,        # motorA_joint_1
            pos_a_2,        # motorA_joint_2
            pos_a_3,        # motorA_joint_3
            pos_b_minus_1,  # motorB_joint_-1
            pos_b_1,        # motorB_joint_1
            pos_b_2,        # motorB_joint_2
            pos_b_3         # motorB_joint_3
        ]

        self.belt_publisher.publish(command_msg)


def main(args=None):
    rclpy.init()
    node = BeltNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()