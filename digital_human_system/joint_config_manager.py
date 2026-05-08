#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关节配置管理器
统一管理关节方向、范围、偏移等参数
"""

import os
import yaml
import numpy as np
from typing import Dict, List, Tuple, Optional


class JointConfigManager:
    """关节配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, '/home/pc/下载/digital2robot_12.30/digital2robot/digital_human_system/joint_config.yaml')
        
        self.config_path = config_path
        self.config = self._load_config()
        
        # 提取配置
        self.directions = self.config.get('joint_directions', {})
        self.limits = self.config.get('joint_limits', {})
        self.offsets = self.config.get('joint_offsets', {})
        self.name_mapping = self.config.get('joint_name_mapping', {})
        
        print(f"✅ 关节配置已加载: {len(self.directions)} 个关节")
        
        # 🔍 调试输出：显示非默认方向的关节
        non_default = {k: v for k, v in self.directions.items() if v != 1}
        if non_default:
            print(f"🔍 [DEBUG] 非默认方向的关节: {non_default}")
        else:
            print(f"🔍 [DEBUG] 所有关节都使用默认方向(1)")
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"⚠️  配置文件不存在: {self.config_path}")
            print("使用默认配置")
            return self._get_default_config()
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            print("使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'joint_directions': {
                'head_yaw': 1, 'head_pitch': 1,
                'left_shoulder_pitch': 1, 'left_shoulder_roll': 1, 'left_shoulder_yaw': 1,
                'left_elbow': 1, 'left_wrist': 1,
                'right_shoulder_pitch': 1, 'right_shoulder_roll': 1, 'right_shoulder_yaw': 1,
                'right_elbow': 1, 'right_wrist': 1
            },
            'joint_limits': {},
            'joint_offsets': {},
            'joint_name_mapping': {}
        }
    
    def apply_direction(self, joint_name: str, angle: float) -> float:
        """应用关节方向
        
        Args:
            joint_name: 关节名称
            angle: 原始角度
            
        Returns:
            应用方向后的角度
        """
        direction = self.directions.get(joint_name, 1)
        return angle * direction
    
    def apply_offset(self, joint_name: str, angle: float) -> float:
        """应用关节偏移
        
        Args:
            joint_name: 关节名称
            angle: 原始角度
            
        Returns:
            应用偏移后的角度
        """
        offset = self.offsets.get(joint_name, 0)
        return angle + offset
    
    def apply_limit(self, joint_name: str, angle: float) -> float:
        """应用关节限制
        
        Args:
            joint_name: 关节名称
            angle: 原始角度
            
        Returns:
            限制后的角度
        """
        if joint_name in self.limits:
            min_angle, max_angle = self.limits[joint_name]
            return np.clip(angle, min_angle, max_angle)
        return angle
    
    def transform_angle(self, joint_name: str, angle: float, 
                       apply_dir: bool = True, 
                       apply_off: bool = True, 
                       apply_lim: bool = True) -> float:
        """完整的角度转换
        
        Args:
            joint_name: 关节名称
            angle: 原始角度
            apply_dir: 是否应用方向
            apply_off: 是否应用偏移
            apply_lim: 是否应用限制
            
        Returns:
            转换后的角度
        """
        result = angle
        
        # 1. 应用方向
        if apply_dir:
            result = self.apply_direction(joint_name, result)
        
        # 2. 应用偏移
        if apply_off:
            result = self.apply_offset(joint_name, result)
        
        # 3. 应用限制
        if apply_lim:
            result = self.apply_limit(joint_name, result)
        
        return result
    
    def transform_joint_angles(self, joint_angles: Dict[str, float],
                              apply_dir: bool = True,
                              apply_off: bool = True,
                              apply_lim: bool = True) -> Dict[str, float]:
        """批量转换关节角度
        
        Args:
            joint_angles: 关节角度字典 {关节名: 角度}
            apply_dir: 是否应用方向
            apply_off: 是否应用偏移
            apply_lim: 是否应用限制
            
        Returns:
            转换后的关节角度字典
        """
        result = {}
        for joint_name, angle in joint_angles.items():
            result[joint_name] = self.transform_angle(
                joint_name, angle, apply_dir, apply_off, apply_lim
            )
        return result
    
    def get_direction(self, joint_name: str) -> int:
        """获取关节方向"""
        return self.directions.get(joint_name, 1)
    
    def set_direction(self, joint_name: str, direction: int):
        """设置关节方向
        
        Args:
            joint_name: 关节名称
            direction: 方向 (1 或 -1)
        """
        if direction not in [1, -1]:
            raise ValueError("方向必须是 1 或 -1")
        self.directions[joint_name] = direction
        print(f"✅ 已设置 {joint_name} 方向为 {direction}")
    
    def get_offset(self, joint_name: str) -> float:
        """获取关节偏移"""
        return self.offsets.get(joint_name, 0)
    
    def set_offset(self, joint_name: str, offset: float):
        """设置关节偏移"""
        self.offsets[joint_name] = offset
        print(f"✅ 已设置 {joint_name} 偏移为 {offset}°")
    
    def get_limit(self, joint_name: str) -> Optional[Tuple[float, float]]:
        """获取关节限制"""
        return self.limits.get(joint_name)
    
    def set_limit(self, joint_name: str, min_angle: float, max_angle: float):
        """设置关节限制"""
        self.limits[joint_name] = [min_angle, max_angle]
        print(f"✅ 已设置 {joint_name} 范围为 [{min_angle}, {max_angle}]°")
    
    def save_config(self, path: Optional[str] = None):
        """保存配置到文件
        
        Args:
            path: 保存路径，如果为None则保存到原路径
        """
        if path is None:
            path = self.config_path
        
        config = {
            'joint_directions': self.directions,
            'joint_limits': self.limits,
            'joint_offsets': self.offsets,
            'joint_name_mapping': self.name_mapping
        }
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            print(f"✅ 配置已保存到: {path}")
        except Exception as e:
            print(f"❌ 配置保存失败: {e}")
    
    def reload_config(self):
        """重新加载配置文件"""
        self.config = self._load_config()
        self.directions = self.config.get('joint_directions', {})
        self.limits = self.config.get('joint_limits', {})
        self.offsets = self.config.get('joint_offsets', {})
        self.name_mapping = self.config.get('joint_name_mapping', {})
        print("✅ 配置已重新加载")
    
    def print_config(self):
        """打印当前配置"""
        print("\n" + "="*60)
        print("关节配置")
        print("="*60)
        
        print("\n📐 关节方向:")
        for joint, direction in sorted(self.directions.items()):
            symbol = "→" if direction == 1 else "←"
            print(f"  {joint:25s}: {direction:2d} {symbol}")
        
        if self.offsets:
            print("\n📏 关节偏移:")
            for joint, offset in sorted(self.offsets.items()):
                if offset != 0:
                    print(f"  {joint:25s}: {offset:+.1f}°")
        
        if self.limits:
            print("\n🔒 关节限制:")
            for joint, (min_a, max_a) in sorted(self.limits.items()):
                print(f"  {joint:25s}: [{min_a:6.1f}, {max_a:6.1f}]°")
        
        print("="*60 + "\n")


# 全局单例
_joint_config_manager = None

def get_joint_config_manager(config_path: Optional[str] = None) -> JointConfigManager:
    """获取关节配置管理器单例"""
    global _joint_config_manager
    if _joint_config_manager is None:
        _joint_config_manager = JointConfigManager(config_path)
    return _joint_config_manager


if __name__ == "__main__":
    # 测试代码
    manager = JointConfigManager()
    manager.print_config()
    
    # 测试角度转换
    test_angles = {
        'head_yaw': 30,
        'left_shoulder_pitch': 45,
        'right_elbow': 90
    }
    
    print("原始角度:")
    for joint, angle in test_angles.items():
        print(f"  {joint}: {angle}°")
    
    print("\n转换后角度:")
    transformed = manager.transform_joint_angles(test_angles)
    for joint, angle in transformed.items():
        print(f"  {joint}: {angle}°")
