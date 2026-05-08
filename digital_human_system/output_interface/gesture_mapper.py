#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gesture Mapper Module
Maps gesture names to joint angles using the GesturePolicy
"""
from typing import List, Optional, Dict

# 兼容两种导入方式：相对导入（当作为包的一部分）或绝对导入（当直接运行时）
try:
    from ..behavior_planner.gesture_policy import GesturePolicy
except ImportError:
    try:
        from behavior_planner.gesture_policy import GesturePolicy
    except ImportError:
        from digital_human_system.behavior_planner.gesture_policy import GesturePolicy

# joint_config_manager 是可选的，如果不存在就忽略
try:
    from digital_human_system.joint_config_manager import get_joint_config_manager
except ImportError:
    get_joint_config_manager = None

class GestureMapper:
    def __init__(self, use_joint_config: bool = True):
        """Initialize the gesture mapper with a GesturePolicy instance
        
        Args:
            use_joint_config: 是否使用关节配置管理器（方向、偏移、限制）
        """
        self.gesture_policy = GesturePolicy()
        
        # 关节名称（与DigitalHumanROSPublisher中的joint_names对应）
        self.joint_names = [
            'head_yaw', 'head_pitch',
            'left_shoulder_pitch', 'left_shoulder_roll', 'left_shoulder_yaw',
            'left_elbow', 'left_wrist',
            'right_shoulder_pitch', 'right_shoulder_roll', 'right_shoulder_yaw',
            'right_elbow', 'right_wrist'
        ]
        
        # 默认姿势（所有关节为0）
        self.default_pose = [0.0] * len(self.joint_names)
        
        # 🎯 关节配置管理器
        self.use_joint_config = use_joint_config
        if self.use_joint_config and get_joint_config_manager is not None:
            try:
                self.joint_config = get_joint_config_manager()
                print("✅ GestureMapper: 已启用关节配置管理器")
            except Exception as e:
                print(f"⚠️  GestureMapper: 关节配置管理器加载失败: {e}")
                self.use_joint_config = False
                self.joint_config = None
        else:
            self.joint_config = None
            if self.use_joint_config and get_joint_config_manager is None:
                print("⚠️  GestureMapper: joint_config_manager 模块不可用，已禁用关节配置")
                self.use_joint_config = False
        self._joint_config_warned = False  # 仅打印一次“未启用”提示
    
    def _apply_joint_config(self, joint_angles: List[float]) -> List[float]:
        """应用关节配置（方向、偏移、限制）
        
        Args:
            joint_angles: 原始关节角度列表
            
        Returns:
            应用配置后的关节角度列表
        """
        if not self.use_joint_config or self.joint_config is None:
            if not getattr(self, "_joint_config_warned", False):
                self._joint_config_warned = True
                # print("⚠️  [DEBUG] 关节配置未启用或未加载（后续不再提示）")
            return joint_angles
        
        # 转换为字典
        joint_dict = {name: angle for name, angle in zip(self.joint_names, joint_angles)}
        
        # 🔍 调试输出：显示原始角度
        # print(f"🔍 [DEBUG] 原始角度: {joint_dict}")
        
        # 🔍 调试输出：显示配置的方向
        # print(f"🔍 [DEBUG] 关节方向配置:")
        for name in self.joint_names:
            if name in joint_dict and joint_dict[name] != 0:
                direction = self.joint_config.get_direction(name)
                # print(f"    {name}: 方向={direction}, 原始={joint_dict[name]:.1f}°")
        
        # 应用配置
        transformed_dict = self.joint_config.transform_joint_angles(joint_dict)
        
        # 🔍 调试输出：显示转换后的角度
        # print(f"🔍 [DEBUG] 转换后角度: {transformed_dict}")
        
        # 转换回列表
        return [transformed_dict.get(name, 0.0) for name in self.joint_names]
    
    def map_gesture(self, gesture_name: str) -> Optional[List[float]]:
        """
        Map a gesture name to joint angles
        
        Args:
            gesture_name: Name of the gesture to map
            
        Returns:
            List of joint angles in degrees, or None if gesture not found
        """
        # 🎯 修复：使用正确的属性名 base_gestures
        joint_angles = None
        
        if hasattr(self.gesture_policy, 'base_gestures') and gesture_name in self.gesture_policy.base_gestures:
            joint_angles = self.gesture_policy.base_gestures[gesture_name]
        
        # 兼容旧的属性名（如果存在）
        elif hasattr(self.gesture_policy, 'gesture_library') and gesture_name in self.gesture_policy.gesture_library:
            joint_angles = self.gesture_policy.gesture_library[gesture_name]
        
        elif hasattr(self.gesture_policy, 'gestures') and gesture_name in self.gesture_policy.gestures:
            joint_angles = self.gesture_policy.gestures[gesture_name]
        
        # 如果找到了手势，应用关节配置
        if joint_angles is not None:
            return self._apply_joint_config(joint_angles)
            
        # 如果是rest或neutral，返回默认姿势
        if gesture_name in ['rest', 'neutral']:
            return self.default_pose
            
        # 如果找不到手势，返回None
        return None
    
    def get_default_pose(self) -> List[float]:
        """Get the default joint angles"""
        return self.default_pose
