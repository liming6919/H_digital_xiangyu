#ifndef YMBOT_NECK_DYNAMIXEL_API
#define YMBOT_NECK_DYNAMIXEL_API

#include <bitset>
#include <cmath>
#include <fcntl.h>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <termios.h>
#include <unistd.h>
#include <vector>

using namespace std;

bool dynamixel_initialization(int& serial_port);
bool dynamixel_get_firware_version(const int serial_port, const int dxl_id, int& receive_info);
bool dynamixel_get_id(const int serial_port, const int dxl_id, int& receive_info);
bool dynamixel_get_baud_rate(const int serial_port, const int dxl_id, int& receive_info);
bool dynamixel_get_cw_angle_limit(const int serial_port, const int dxl_id, double& receive_info);  // 0~359.913645
bool dynamixel_get_ccw_angle_limit(const int serial_port, const int dxl_id, double& receive_info); // 0~359.913645
bool dynamixel_get_temperature_limit(const int serial_port, const int dxl_id, int& receive_info);
bool dynamixel_get_min_voltage_limit(const int serial_port, const int dxl_id, double& receive_info);
bool dynamixel_get_max_voltage_limit(const int serial_port, const int dxl_id, double& receive_info);
bool dynamixel_get_max_torque(const int serial_port, const int dxl_id, double& receive_info); // 0~100
bool dynamixel_get_status_return_level(const int serial_port,
                                       const int dxl_id,
                                       int& receive_info); // 0: no return  | 1: return for read  | 2: return for all
bool dynamixel_get_alarm_led(const int serial_port,
                             const int dxl_id,
                             int& receive_info); /*| instruction error | overload error | checksum error | range error |
                                                    overheating error | angle limit error | input voltage error*/
bool dynamixel_get_shutdown(const int serial_port,
                            const int dxl_id,
                            int& receive_info); /*| instruction error | overload error | checksum error | range error |
                                                   overheating error | angle limit error | input voltage error*/
bool dynamixel_set_torque_enable(const int serial_port, const int dxl_id, int& send_info);
bool dynamixel_set_led(const int serial_port, const int dxl_id, int& send_info);
bool dynamixel_set_d_gain(const int serial_port, const int dxl_id, int& send_info);
bool dynamixel_set_i_gain(const int serial_port, const int dxl_id, int& send_info);
bool dynamixel_set_p_gain(const int serial_port, const int dxl_id, int& send_info);
bool dynamixel_set_angle(const int serial_port, const int dxl_id, double send_info);             // 0~359.913645
bool dynamixel_set_speed(const int serial_port, const int dxl_id, double& send_info);            // 0~116.622
bool dynamixel_set_torque_limit(const int serial_port, const int dxl_id, double& send_info);     // 0~100
bool dynamixel_get_angle(const int serial_port, const int dxl_id, double& receive_info);         // 0~359.913645
bool dynamixel_get_speed(const int serial_port, const int dxl_id, double& receive_info);         // 0~116.622
bool dynamixel_get_load(const int serial_port, const int dxl_id, double& receive_info);          // 0~200.098344
bool dynamixel_get_voltage(const int serial_port, const int dxl_id, double& receive_info);       // 6~16
bool dynamixel_get_temperature(const int serial_port, const int dxl_id, int& receive_info);      // 0~80
bool dynamixel_get_moving(const int serial_port, const int dxl_id, int& receive_info);           // 0: ldle | 1: moving
bool dynamixel_get_current(const int serial_port, const int dxl_id, int& receive_info);          // 0~18,427.5
bool dynamixel_set_torque_control_mode(const int serial_port, const int dxl_id, int& send_info); // 0: off | 1:on
bool dynamixel_set_torque(const int serial_port, const int dxl_id, double& send_info);           // 0~4603.5
bool dynamixel_set_acceleration(const int serial_port, const int dxl_id, double& send_info);     // 0~2180


#endif
