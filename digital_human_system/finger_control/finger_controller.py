#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手指控制器
Finger Controller - 集成到数字人系统，同步控制手指动作
"""

import time
import threading
from typing import Dict, List, Optional
import random
from .servo_controller import ServoController
from .finger_mapper import FingerMapper


class FingerController:
    """手指控制器 - 与数字人系统集成（支持左右手多串口）"""
    
    def __init__(self,
                 serial_port: str = "/dev/ttyUSB1",
                 right_port: Optional[str] = None,
                 left_port: Optional[str] = None,
                 baudrate: int = 115200,
                 enable: bool = True,
                 debug: bool = False):
        """
        初始化手指控制器
        
        Args:
            serial_port: 默认串口（若未指定左右手单独端口，则使用该口）
            right_port: 右手串口（例如 /dev/ttyUSB0）
            left_port: 左手串口（例如 /dev/ttyUSB2）
            baudrate: 波特率
            enable: 是否启用手指控制
            debug: 是否启用调试输出
        """
        self.enable = enable
        self.debug = debug
        
        if not enable:
            print("[手指控制] 已禁用")
            return
        
        # 初始化舵机控制器和映射器
        self.controllers: List[ServoController] = []
        ports = []
        # 优先使用左右手端口；若未提供则使用默认串口
        if right_port:
            ports.append(("右手", right_port))
        if left_port:
            # 避免与右手端口重复
            if not right_port or left_port != right_port:
                ports.append(("左手", left_port))
        if not ports:
            ports.append(("默认", serial_port))
        
        for label, port in ports:
            ctrl = ServoController(port=port, baudrate=baudrate)
            ctrl.set_debug(debug)
            ok = ctrl.connect()
            self.controllers.append(ctrl)
            if ok:
                print(f"[手指控制] {label} 串口初始化成功: {port} @ {baudrate}")
            else:
                print(f"[手指控制] 警告: {label} 串口 {port} 连接失败，手指控制可能无法工作")
        
        self.finger_mapper = FingerMapper()
        
        # 当前手指状态
        self.current_finger_positions: Dict[int, int] = {}
        self.last_gesture_name: Optional[str] = None
        
        # 平滑控制参数
        self.smoothing_enabled = True
        self.smoothing_factor = 0.3
        self.position_tolerance = 20  # 位置容差（适配600-2500范围）
        # 速度/刷新控制：避免过快抖动
        self.max_step = 120          # 单次发送的最大步进（位置值）
        self.min_update_interval = 0.30  # 同一手势的最小刷新间隔（秒）
        self.last_update_ts = 0.0
    
    def update_gesture(self, gesture_name: str, duration: float = 0.5, 
                      transition_time_ms: Optional[int] = None):
        """
        更新手势，控制手指动作
        
        Args:
            gesture_name: 手势名称
            duration: 手势持续时间（秒）
            transition_time_ms: 过渡时间（毫秒），如果为None则根据duration计算
        """
        if not self.enable:
            return
        
        # 获取手指位置
        servo_positions = self.finger_mapper.get_servo_positions(gesture_name)
        
        if not servo_positions:
            if self.debug:
                print(f"[手指控制] 未找到手势 '{gesture_name}' 的手指映射")
            return
        
        # 平滑处理
        if self.smoothing_enabled:
            servo_positions = self._apply_smoothing(servo_positions)
        
        # 过滤微小变化
        servo_positions = self._filter_small_changes(servo_positions)
        
        now_ts = time.time()
        if not servo_positions:
            return

        # 同一手势长时间保持时，定期加入微小漂移，让手指“轻微动起来”
        if gesture_name == self.last_gesture_name and (now_ts - self.last_update_ts) >= self.min_update_interval:
            servo_positions = self._add_micro_drift(servo_positions)
        
        # 限制单次步进，避免过快
        servo_positions = self._limit_step(servo_positions)
        
        # 计算过渡时间
        if transition_time_ms is None:
            transition_time_ms = int(duration * 1000)
            transition_time_ms = max(300, min(1200, transition_time_ms))  # 更保守，避免过快
        
        # 发送指令
        success = True
        for ctrl in self.controllers:
            ok = ctrl.set_multiple_servos(servo_positions, transition_time_ms)
            success = success and ok
        
        if success:
            self.current_finger_positions.update(servo_positions)
            self.last_gesture_name = gesture_name
            self.last_update_ts = now_ts
            
            if self.debug:
                print(f"[手指控制] 手势 '{gesture_name}': {len(servo_positions)}个手指, "
                      f"时间 {transition_time_ms}ms")
        else:
            if self.debug:
                print(f"[手指控制] 发送失败: {gesture_name}")
    
    def update_gesture_sequence(self, gesture_sequence: List[Dict]):
        """
        更新手势序列
        
        Args:
            gesture_sequence: 手势序列，每个元素包含 'gesture_name' 和 'duration'
        """
        if not self.enable:
            return
        
        for gesture in gesture_sequence:
            gesture_name = gesture.get('gesture_name') or gesture.get('gesture', 'rest')
            duration = gesture.get('duration', 0.5)
            
            self.update_gesture(gesture_name, duration)
            
            # 等待手势完成（可选，如果需要在序列中同步）
            # time.sleep(duration)
    
    def _apply_smoothing(self, target_positions: Dict[int, int]) -> Dict[int, int]:
        """
        应用平滑处理
        
        Args:
            target_positions: 目标位置字典
            
        Returns:
            平滑后的位置字典
        """
        smoothed = {}
        
        for servo_id, target_pos in target_positions.items():
            if servo_id in self.current_finger_positions:
                current_pos = self.current_finger_positions[servo_id]
                # 线性插值
                smoothed_pos = int(
                    current_pos * (1.0 - self.smoothing_factor) + 
                    target_pos * self.smoothing_factor
                )
                smoothed[servo_id] = smoothed_pos
            else:
                smoothed[servo_id] = target_pos
        
        return smoothed
    
    def _filter_small_changes(self, positions: Dict[int, int]) -> Dict[int, int]:
        """
        过滤微小变化
        
        Args:
            positions: 位置字典
            
        Returns:
            过滤后的位置字典
        """
        filtered = {}
        
        for servo_id, target_pos in positions.items():
            if servo_id in self.current_finger_positions:
                current_pos = self.current_finger_positions[servo_id]
                diff = abs(target_pos - current_pos)
                
                if diff >= self.position_tolerance:
                    filtered[servo_id] = target_pos
            else:
                filtered[servo_id] = target_pos
        
        return filtered

    def _add_micro_drift(self, positions: Dict[int, int]) -> Dict[int, int]:
        """
        为长时间同一手势添加微小随机漂移，让手指“轻微动起来”。
        漂移幅度控制在 ±position_tolerance 之内。
        """
        drifted = {}
        for sid, target in positions.items():
            delta = random.randint(-self.position_tolerance, self.position_tolerance)
            drifted[sid] = max(600, min(2500, target + delta))
        return drifted

    def _limit_step(self, positions: Dict[int, int]) -> Dict[int, int]:
        """
        限制单次步进，避免过快变化。
        """
        limited = {}
        for sid, target in positions.items():
            if sid in self.current_finger_positions:
                cur = self.current_finger_positions[sid]
                delta = target - cur
                if abs(delta) > self.max_step:
                    delta = self.max_step if delta > 0 else -self.max_step
                limited[sid] = cur + delta
            else:
                limited[sid] = target
        return limited
    
    def reset_to_rest(self):
        """重置到休息状态"""
        self.update_gesture('rest', duration=1.0)
    
    def disconnect(self):
        """断开连接"""
        if self.enable and self.servo_controller:
            self.servo_controller.disconnect()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

