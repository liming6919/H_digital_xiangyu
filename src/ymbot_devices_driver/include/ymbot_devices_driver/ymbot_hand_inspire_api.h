#ifndef YMBOT_HAND_INSPIRE_API_H
#define YMBOT_HAND_INSPIRE_API_H

#include <cmath>
#include <fcntl.h>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <termios.h>
#include <unistd.h>
#include <vector>


using namespace std;

int ins_initialization(const char* serial_port_name, int& serial_port);
int ins_set_id(const int serial_port, const int hand_id, const vector<int>& send_info); // 1~254
int ins_get_id(const int serial_port, const int hand_id, vector<int>& receive_info);
int ins_set_baud_rate(const int serial_port,
                      const int hand_id,
                      const vector<int>& send_info); // 0: 115200  |  1: 57600  |  2: 19200
int ins_get_actual_baud_rate(const int serial_port, const int hand_id, vector<int>& receive_info);
int ins_clear_error(const int serial_port, const int hand_id, const vector<int>& send_info);              // 1
int ins_save_parameter(const int serial_port, const int hand_id, const vector<int>& send_info);           // 1
int ins_force_sensor_calibration(const int serial_port, const int hand_id, const vector<int>& send_info); // 1
int ins_set_current_limit(const int serial_port, const int hand_id, const vector<int>& send_info);        // 0~1500
int ins_get_current_limit(const int serial_port, const int hand_id, vector<int>& receive_info);
int ins_set_default_speed(const int serial_port, const int hand_id, const vector<int>& send_info); // 0~1000
int ins_get_default_speed(const int serial_port, const int hand_id, vector<int>& receive_info);
int ins_set_default_force(const int serial_port,
                          const int hand_id,
                          const vector<int>& send_info); // 1~4: 0~1000    |    5~6: 0~1500
int ins_get_default_force(const int serial_port, const int hand_id, vector<int>& receive_info);
int ins_set_position(int serial_port, const int hand_id, const vector<int>& send_info);           // 2000~0   |  -1
int ins_set_angle(const int serial_port, const int hand_id, const vector<int>& send_info);        // 0~1000   |   -1
int ins_set_force(int serial_port, const int hand_id, const vector<int>& send_info);              // 0~1000
int ins_set_speed(int serial_port, const int hand_id, const vector<int>& send_info);              // 0~1000
int ins_get_actual_position(const int serial_port, const int hand_id, vector<int>& receive_info); // 2000~0
int ins_get_actual_angle(const int serial_port, const int hand_id, vector<int>& receive_info);    // 0~1000
int ins_get_actual_force(const int serial_port, const int hand_id, vector<int>& receive_info);    // 0~1000
int ins_get_actual_current(const int serial_port, const int hand_id, vector<int>& receive_info);  // 0~1000
int ins_get_error_info(const int serial_port,
                       const int hand_id,
                       vector<int>& receive_info); // bit0:locked-rotor | bit1:excessive temperature | bit2:excessive
                                                   // current | bit3:motor anomaly | bit4:communication failure
int ins_get_state_info(const int serial_port,
                       const int hand_id,
                       vector<int>& receive_info); // 0:loosing | 1:grasping | 2:stop at target position | 3:stop at
                                                   // target position by force control | 5:stop at current protection |
                                                   // 6:stop at locked-rotor | 7:stop at motor fault
int ins_get_temperature(const int serial_port, const int hand_id, vector<int>& receive_info); // 0~100


#endif
