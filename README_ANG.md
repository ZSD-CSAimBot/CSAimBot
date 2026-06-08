# CSAimBot [CSBot]

---

## Brief Project Description
The goal of the project is to create a physical AimBot for the game CS:GO. The program would read the game screen, mark enemies, and return the value by which the mouse must move. To execute the mouse movement, a Cartesian robot with an appropriate grip will be created. The robot would be able to adapt to different mice and DPI values. The robot will be capable of shooting and compensating for weapon recoil, ensuring greater accuracy. The player would control the movement using the WASD keys, so the robot must cooperate with them.

---

## Functional Scope
* Reading the screen and marking enemies.
* Calculating the robot's trajectory.
* Moving the mouse using the Cartesian robot and shooting via a button.
* Looking around if no enemies are detected.
* Cooperating with the player.

---

## System Architecture
* **Robot moving the mouse:** A Cartesian robot featuring stepper motors and encoders or servomechanisms for the XY axes, and a ball/trapezoidal lead screw for the Z axis, equipped with a proper grip capable of holding multiple types of mice. The robot would correct the steering if the crosshair fails to land on the enemy and would compensate for weapon recoil.
* **Screen capture system:** Screen capture will be handled using appropriate Python/C++ libraries, forwarding the captured frames to the enemy detection algorithm.
* **Enemy detection system:** A YOLO-based system will detect and mark enemies on the image, returning values that allow controlling the robot's motors in order to aim at and eliminate the target.

---

## Technology Stack

**Hardware - robot:**
* ESP32 microcontroller, motor drivers.
* NEMA 23 stepper motors, ball/trapezoidal lead screw.
* Power supply, step-down converters.
* 3D printed robot arm and gripper, servo to operate the gripper.

**Hardware - PC:**
* PC with a graphics card, monitor, mouse, keyboard.

**Software:**
* Python/C/C++ languages and relevant libraries, YOLO.
* PyCharm, Arduino IDE, VSC.
* Serial communication (e.g., UART, TCP/IP, USB).
* Inverse kinematics algorithms.

---

## Main Assumptions

### Hardware Assumptions
* The project will operate at room temperature in an enclosed room on a horizontal, flat surface that allows for the proper mounting of the robot (e.g., a desk) and the proper use of the keyboard.
* The mouse will move on a cloth mousepad.
* The mouse must use a laser or optical sensor and have at least 2 buttons (left and right); the remaining buttons will be ignored. 
* When changing the mouse or DPI values, a semi-automatic calibration procedure will be executed. The robot will check the distance it needs to move to transition between reference points on a dedicated map.
* PC-to-Microcontroller communication will be handled via UART (USB) at a baud rate of 115200.

### Software Assumptions
* The computer program will run on Windows 11 Pro build >=25H2 or equivalent. The program will not work on Linux or macOS.
* A PC with adequate computing power is required (a graphics card supporting CUDA, min. RTX 3060) along with a monitor; laptops are not supported.
* The program will detect enemy models in the game (it will distinguish CT models from T models).
* The program will detect whether the user is holding a pistol or a rifle using classic computer vision (template matching with OpenCV). If the player is holding a pistol or a sniper rifle, recoil compensation will be disabled. Otherwise, the program will correct the recoil for specific weapons (AK47/M4A1).

### Game Assumptions
* The program will only run during an active round, on any map.
* The game must run at a minimum of 60 FPS. Enabling the option for instant corpse removal after a kill in a local game is required.
* The reaction time, with the eDPI adjusted so that the robot does not need to lift the mouse, will be at most equal to the reaction time of a skilled player (<200ms).

---

## Project Team
* Tomasz Nazar
* Filip Pietrzak
* Patryk Polechoński
* Hubert Czarnecki
* Karol Puczyński
* Piotr Rokita
* Łukasz Mroczek
* Antoni Sulkowski
* Andrzej Placek
* Łukasz Orluk