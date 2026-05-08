// ymbot_c_motor.hpp

#ifndef YMBOT_JOINT_EU_H
#define YMBOT_JOINT_EU_H

#include "eu_planet.h" //motors
#include <atomic>
#include <iostream>
#include <sys/time.h>
#include <thread>

class YmbotJointEu {
  public:
    int dev_index;
    int motor_id;
    int motor_mode; // 1:轮廓位置模式-速度     2:轮廓位置模式-时间    3:轮廓速度模式    4:电流模式    5:周期同步位置模式
    bool flag_enable;

    float rated_torque;

    float present_position;
    float target_position;
    float record_position;

    float present_velocity;
    float target_velocity;

    float present_current;
    float target_current;

    float joint_offset_angle;
    float joint_offset_radian;
    float present_joint_radian;
    float target_joint_radian;

    float joint_limit_max;
    float joint_limit_min;

    // 拖动保持模式相关变量
    bool drag_hold_mode;
    float last_position;
    float position_threshold;  // 位置变化阈值，用于检测外力
    float current_threshold;   // 电流阈值，用于检测外力
    float hold_stiffness;      // 保持刚度
    float hold_damping;        // 保持阻尼

    YmbotJointEu();
    bool motor_initialization_CSP();
    bool motor_initialization_PV();
    bool motor_initialization_DragHold();  // 新增拖动保持初始化
    float comput_current(double torque);
    void set_zero_current();
    bool motor_disabled();
    
    // 拖动保持相关函数
    bool detect_external_force();  // 检测外力
    void update_drag_hold_position();  // 更新拖动保持位置
    void enable_drag_hold_mode();  // 启用拖动保持模式
    void disable_drag_hold_mode(); // 禁用拖动保持模式
};

#endif