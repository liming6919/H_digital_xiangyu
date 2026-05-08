#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROS输出接口模块
负责将手势序列发布到ROS话题，与现有映射器集成
支持ROS1和ROS2
"""

import os
import math
import time
import threading
from typing import List, Dict, Optional

# ROS版本检测和导入
try:
    # 尝试导入ROS2
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Int32
    ROS_VERSION = 2
    print("[OK] 检测到ROS2环境")
except ImportError:
    try:
        # 回退到ROS1
        import rospy
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Int32
        ROS_VERSION = 1
        print("[OK] 检测到ROS1环境")
    except ImportError:
        raise ImportError("未找到ROS1或ROS2环境，请确保已正确安装ROS")

class DigitalHumanROSPublisher:
    def __init__(self, topic_name='/digital_human/joint_states', gesture_mapper=None, node=None):
        """初始化ROS发布器
        
        Args:
            topic_name: ROS话题名称
            gesture_mapper: 手势映射器实例，用于将手势名称映射到关节角度
            node: ROS2节点实例（ROS2需要，ROS1忽略）
        """
        self.ros_version = ROS_VERSION
        env_topic = os.environ.get('DIGITAL_HUMAN_JOINT_TOPIC')
        self.topic_name = env_topic if env_topic else topic_name
        self.pub = None
        self.is_initialized = False
        self.play_id_sub = None
        self.current_play_id = None
        self.play_id_callback = None
        self._last_joint_angles = None
        #  发布互斥：避免待机线程与说话线程交错发布导致抖动
        self._publish_lock = threading.RLock()
        #  模式跟踪：用于检测“待机 -> 说话”切换并触发一次软启动
        self._last_sequence_mode = None  # 'idle' | 'active' | None
        self._soft_start_next_gesture = False
        
        # ROS2节点管理
        if self.ros_version == 2:
            self.node = node
            self._own_node = False
            if self.node is None:
                # 如果没有提供节点，创建一个
                if not rclpy.ok():
                    rclpy.init()
                self.node = Node('digital_human_system')
                self._own_node = True
        
        # 设置手势映射器
        self.gesture_mapper = gesture_mapper
        if self.gesture_mapper is None:
            # 如果没有提供gesture_mapper，创建一个默认的
            # 兼容两种导入方式：相对导入（当作为包的一部分）或绝对导入（当直接运行时）
            try:
                from .gesture_mapper import GestureMapper
            except ImportError:
                try:
                    from output_interface.gesture_mapper import GestureMapper
                except ImportError:
                    from digital_human_system.output_interface.gesture_mapper import GestureMapper
            self.gesture_mapper = GestureMapper()
        
        # 关节名称（与你的映射器兼容）
        self.joint_names = [
            'head_yaw', 'head_pitch',
            'left_shoulder_pitch', 'left_shoulder_roll', 'left_shoulder_yaw',
            'left_elbow', 'left_wrist',
            'right_shoulder_pitch', 'right_shoulder_roll', 'right_shoulder_yaw',
            'right_elbow', 'right_wrist'
        ]
        print(f"数字人ROS{self.ros_version}发布器初始化完成，话题: {self.topic_name}")
    
    def initialize_ros(self):
        """初始化ROS节点和发布器"""
        if not self.is_initialized:
            try:
                if self.ros_version == 2:
                    # ROS2初始化
                    if not rclpy.ok():
                        rclpy.init()
                    
                    if self.node is None:
                        self.node = Node('digital_human_system')
                        self._own_node = True
                    
                    # 创建QoS配置
                    qos_profile = QoSProfile(
                        depth=10,
                        reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.VOLATILE
                    )
                    
                    # 创建发布器
                    self.pub = self.node.create_publisher(JointState, self.topic_name, qos_profile)
                    
                    # 初始化play_id订阅者
                    self.play_id_sub = self.node.create_subscription(
                        Int32, '/playid', self._handle_play_id, qos_profile
                    )
                    
                    # ROS2需要spin_once来接收消息
                    if self._own_node:
                        # 在后台线程中spin
                        import threading
                        def spin_thread():
                            while rclpy.ok() and self.is_initialized:
                                rclpy.spin_once(self.node, timeout_sec=0.1)
                        self._spin_thread = threading.Thread(target=spin_thread, daemon=True)
                        self._spin_thread.start()
                    
                else:
                    # ROS1初始化
                    already_inited = True
                    try:
                        rospy.get_name()
                    except Exception:
                        already_inited = False
                    if not already_inited:
                        rospy.init_node('digital_human_system', anonymous=True)
                    self.pub = rospy.Publisher(self.topic_name, JointState, queue_size=10)
                    # 初始化play_id订阅者
                    self.play_id_sub = rospy.Subscriber('/playid', Int32, self._handle_play_id)
                
                # 等待发布器准备好（使用壁钟时间，避免sim_time未就绪导致异常）
                time.sleep(1.0)
                self.is_initialized = True
                print(f"ROS{self.ros_version}节点和发布器初始化成功，等待play_id...")
                
            except Exception as e:
                print(f"ROS初始化失败: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        return True
    
    def create_joint_state_msg(self, joint_angles_deg: List[float], timestamp=None) -> JointState:
        """创建JointState消息"""
        if timestamp is None:
            if self.ros_version == 2:
                # ROS2时间处理
                try:
                    if self.node is not None:
                        timestamp = self.node.get_clock().now()
                    else:
                        from rclpy.clock import Clock
                        clock = Clock()
                        timestamp = clock.now()
                except Exception:
                    # 回退到壁钟时间
                    import rclpy.time
                    timestamp = rclpy.time.Time.from_msg(rclpy.time.Time(seconds=int(time.time()), nanoseconds=int((time.time() % 1) * 1e9)))
            else:
                # ROS1时间处理
                try:
                    timestamp = rospy.Time.now()
                    # 某些情况下（use_sim_time但未发布/clock）now()可能未初始化
                    if hasattr(timestamp, 'to_sec') and timestamp.to_sec() == 0.0:
                        raise Exception("ros time zero")
                except Exception:
                    # 回退到壁钟时间
                    timestamp = rospy.Time.from_sec(time.time())
        
        # 转换为弧度
        positions_rad = [math.radians(angle) for angle in joint_angles_deg] # 创建消息
        joint_state = JointState()
        if self.ros_version == 2:
            # ROS2使用不同的时间戳设置方式
            if hasattr(joint_state.header, 'stamp'):
                joint_state.header.stamp = timestamp.to_msg() if hasattr(timestamp, 'to_msg') else timestamp
        else:
            joint_state.header.stamp = timestamp
        joint_state.name = self.joint_names
        joint_state.position = positions_rad
        joint_state.velocity = [0.0] * len(positions_rad)
        joint_state.effort = [0.0] * len(positions_rad)
        
        return joint_state
    
    def publish_single_frame(self, joint_angles_deg: List[float], verbose=False):
        """发布单帧关节数据"""
        if not self.is_initialized:
            if not self.initialize_ros():
                return False
        
        try:
            joint_state = self.create_joint_state_msg(joint_angles_deg)
            self.pub.publish(joint_state)
            
            if verbose:
                print(f"发布关节角度: {joint_angles_deg}")
            
            return True
            
        except Exception as e:
            msg = str(e)
            if self.ros_version == 1 and ("init_node" in msg or "not been initialized" in msg):
                try:
                    try:
                        rospy.get_name()
                    except Exception:
                        rospy.init_node('digital_human_system', anonymous=True)
                    if self.pub is None:
                        self.pub = rospy.Publisher(self.topic_name, JointState, queue_size=10)
                        time.sleep(0.2)
                    joint_state = self.create_joint_state_msg(joint_angles_deg)
                    if self.ros_version == 2:
                        self.pub.publish(joint_state)
                    else:
                        self.pub.publish(joint_state)
                    if verbose:
                        print(f"发布关节角度: {joint_angles_deg}")
                    return True
                except Exception as ee:
                    print(f"发布失败: {ee}")
                    return False
            print(f"发布失败: {e}")
            return False
    
    def _safe_rate(self, fps: float):
        """返回一个拥有 sleep() 的对象。若ROS时间不可用，使用壁钟time.sleep。"""
        period = 1.0 / max(1e-6, float(fps))
        if self.ros_version == 2:
            # ROS2 中没有 rclpy.rate，使用 time.sleep() 实现速率控制
            class _RateWrapper:
                def __init__(self, per):
                    self._p = per
                def sleep(self):
                    time.sleep(self._p)
            return _RateWrapper(period)
        else:
            # ROS1使用rospy.Rate
            try:
                r = rospy.Rate(fps)
                class _RateWrapper:
                    def __init__(self, rr, per):
                        self._r = rr
                        self._p = per
                    def sleep(self):
                        try:
                            self._r.sleep()
                        except Exception:
                            time.sleep(self._p)
                return _RateWrapper(r, period)
            except Exception:
                pass
        
        # 回退到壁钟时间
        class _WallRate:
            def __init__(self, p):
                self.p = p
            def sleep(self):
                time.sleep(self.p)
        return _WallRate(period)

    def _handle_play_id(self, msg):
        """处理从/playid话题接收到的播放ID"""
        prev_play_id = self.current_play_id
        self.current_play_id = msg.data
        log_msg = f"[播放] 收到播放ID: {self.current_play_id} (前一个ID: {prev_play_id})"
        if self.ros_version == 2:
            if self.node is not None:
                self.node.get_logger().info(log_msg)
            else:
                print(log_msg)
        else:
            rospy.loginfo(log_msg)
        if self.play_id_callback:
            self.play_id_callback(self.current_play_id)
    
    def wait_for_play_id(self, expected_play_id=None, timeout=10.0):
        """等待直到收到指定的play_id或超时
        
        Args:
            expected_play_id: 期望的play_id，如果为None则等待任意新的play_id
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否成功收到期望的play_id
        """
        start_time = time.time()
        
        if expected_play_id is not None and self.current_play_id is not None and self.current_play_id >= expected_play_id:
            log_msg = f"[OK] 已收到期望的play_id: {self.current_play_id}"
            if self.ros_version == 2 and self.node is not None:
                self.node.get_logger().info(log_msg)
            else:
                print(log_msg)
            return True
        
        # 检查ROS是否关闭的函数
        def is_shutdown():
            if self.ros_version == 2:
                return not rclpy.ok()
            else:
                return rospy.is_shutdown()
        
        # 日志函数
        def log_info(msg):
            if self.ros_version == 2 and self.node is not None:
                self.node.get_logger().info(msg)
            else:
                print(msg)
        
        def log_warn(msg):
            if self.ros_version == 2 and self.node is not None:
                self.node.get_logger().warn(msg)
            else:
                print(msg)
        
        if expected_play_id is None:
            # 等待任意新的play_id
            initial_play_id = self.current_play_id
            while not is_shutdown():
                if self.current_play_id is not None and self.current_play_id != initial_play_id:
                    log_info(f"[OK] 收到新的play_id: {self.current_play_id}")
                    return True
                    
                if timeout is not None and (time.time() - start_time) > timeout:
                    log_warn(f"[时间] 等待play_id超时 ({timeout}秒)，当前play_id: {self.current_play_id}")
                    return False
                    
                time.sleep(0.05)
        else:
            # 等待指定的play_id
            while not is_shutdown():
                if self.current_play_id is not None and self.current_play_id >= expected_play_id:
                    log_info(f"[OK] 收到期望的play_id: {self.current_play_id}")
                    return True
                    
                if timeout is not None and (time.time() - start_time) > timeout:
                    log_warn(f"[时间] 等待play_id {expected_play_id} 超时 ({timeout}秒)，当前play_id: {self.current_play_id}")
                    return False
                    
                time.sleep(0.05)
        
        return False

    def publish_gesture_sequence(self, gesture_sequence: List[Dict], fps: float = 10, verbose: bool = False, 
                              wait_for_play_id: bool = False, expected_play_id: Optional[int] = None, 
                              timeout: float = 5.0, speech_duration: float = None, interrupt_flag=None):
        """发布手势序列
        
        Args:
            gesture_sequence: 手势序列
            fps: 发布频率
            verbose: 是否打印详细信息
            wait_for_play_id: 是否等待play_id（默认False，不等待）
            expected_play_id: 期望的play_id
            timeout: 等待超时时间(秒)
            speech_duration: 语音总时长 - 已在gesture_policy中处理，这里不再使用
            interrupt_flag: 中断检查函数，返回True时立即停止发布
        """
        if not self.initialize_ros():
            return False

        if not gesture_sequence:
            return True

        total_steps = len(gesture_sequence)
        if verbose:
            print(f"开始发布手势序列，共{total_steps}个动作")

        #  关键修复：完全禁用时间缩放，直接使用gesture_policy生成的精确时长
        # gesture_policy.py 已经根据speech_duration精确规划了手势序列，这里不应该再次调整
        if verbose and speech_duration:
            total_gesture_duration = sum(max(0.1, float(g.get('duration', 0.5))) for g in gesture_sequence)
            print(f" 使用精确时长（无缩放）:")
            print(f"   手势序列总时长: {total_gesture_duration:.2f}秒")
            print(f"   目标语音时长: {speech_duration:.2f}秒")
            print(f"   差异: {abs(total_gesture_duration - speech_duration):.2f}秒")

        # 如果需要等待play_id
        play_id_received = False
        if wait_for_play_id:
            if expected_play_id is not None and self.current_play_id is not None and self.current_play_id >= expected_play_id:
                if verbose:
                    print(f"[OK] 已收到play_id {self.current_play_id}，无需等待")
                play_id_received = True
            else:
                if verbose:
                    print(f"[等待] 等待语音播放开始...")
                
                # 使用更长的超时时间，并记录开始时间
                wait_start_time = time.time()
                play_id_received = self.wait_for_play_id(expected_play_id=expected_play_id, timeout=timeout)
                
                # 如果超时但收到了任何play_id，仍然继续
                if not play_id_received and self.current_play_id is not None:
                    if verbose:
                        print(f"[警告] 超时但已收到play_id {self.current_play_id}，继续执行")
                    play_id_received = True
                elif not play_id_received:
                    if verbose:
                        print(f"[错误] 未收到play_id，取消动作发布")
                    return False
                    
                if verbose:
                    print(f"[OK] 语音已开始播放 (ID: {self.current_play_id})，开始执行动作")
        
        rate = self._safe_rate(fps)
        
        for step_idx, gesture in enumerate(gesture_sequence, 1):
            #  检查中断标志
            if interrupt_flag and interrupt_flag():
                if verbose:
                    print(f"[警告] 检测到中断标志，停止发布 (已完成 {step_idx-1}/{total_steps} 个手势)")
                return False
            
            # 检查ROS是否关闭
            if self.ros_version == 2:
                if not rclpy.ok():
                    return False
            else:
                if rospy.is_shutdown():
                    return False
                
            #  修复：兼容 'gesture' 和 'gesture_name' 两种字段名
            gesture_name = gesture.get('gesture_name') or gesture.get('gesture', 'rest')
            #  关键修复：直接使用原始时长，不进行任何缩放
            duration = max(0.1, float(gesture.get('duration', 0.5)))
            
            if verbose:
                print(f"步骤 {step_idx}/{total_steps}: {gesture_name} ({duration:.2f}s)")

            # 获取当前手势的关节角度
            #  优先使用序列中已有的joint_angles，如果没有则通过mapper查找
            joint_angles = gesture.get('joint_angles')
            if joint_angles is None:
                joint_angles = self.gesture_mapper.map_gesture(gesture_name)
                if joint_angles is None:
                    print(f"警告: 未找到手势 '{gesture_name}' 的映射，使用默认姿势")
                    joint_angles = self.gesture_mapper.get_default_pose()

            # 计算每帧的插值步长
            num_frames = max(1, int(duration * fps))
            
            # 获取上一帧的关节角度（用于插值）
            if hasattr(self, '_last_joint_angles') and self._last_joint_angles is not None:
                start_angles = self._last_joint_angles
            else:
                start_angles = joint_angles  # 如果没有上一帧，直接使用目标角度

            # 插值发布
            for frame in range(num_frames):
                #  每帧都检查中断标志，确保能及时响应抢占
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 检测到中断标志，立即停止发布")
                    return False
                
                #  关键修复：在发布前再次检查，避免发布后立即被中断导致动作冲突
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 发布前检测到中断标志，立即停止")
                    return False
                
                # 检查ROS是否关闭
                if self.ros_version == 2:
                    if not rclpy.ok():
                        return False
                else:
                    if rospy.is_shutdown():
                        return False
                    
                # 计算插值系数 (0.0 到 1.0)
                alpha = (frame + 1) / num_frames
                
                # 线性插值
                current_angles = [
                    start + (target - start) * alpha
                    for start, target in zip(start_angles, joint_angles)
                ] # 发布当前帧
                self.publish_single_frame(current_angles)
                
                # 控制发布频率
                rate.sleep()
                
                # 更新上一帧角度
                self._last_joint_angles = current_angles


            if verbose:
                print(f"  完成 {gesture_name}")
        
        if verbose:
            print("手势序列发布完成")
        return True
    
    def publish_smooth_transition(self, start_angles: List[float], end_angles: List[float], 
                                duration: float, fps=10, verbose=False, interrupt_flag=None):
        """发布平滑过渡动作
        
        Args:
            start_angles: 起始关节角度
            end_angles: 结束关节角度
            duration: 过渡时长（秒）
            fps: 发布频率
            verbose: 是否打印详细信息
            interrupt_flag: 中断检查函数，返回True时立即停止发布
        """
        with self._publish_lock:
            if not self.is_initialized:
                if not self.initialize_ros():
                    return False
            
            #  关键修复：确保至少有一定数量的帧，避免过渡过快
            num_frames = max(10, int(duration * fps))  # 至少10帧，确保过渡平滑
            rate = self._safe_rate(fps)
            
            if verbose:
                print(f"平滑过渡: {duration}s, {num_frames}帧, {fps}fps")
            
            for frame in range(num_frames):
                #  检查中断标志
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 过渡被中断")
                    return False
                
                # 检查ROS是否关闭
                if self.ros_version == 2:
                    if not rclpy.ok():
                        return False
                else:
                    if rospy.is_shutdown():
                        return False
                
                #  优化：使用缓动函数（ease-in-out）代替线性插值，让过渡更平滑自然
                # 线性插值参数 t: 0.0 -> 1.0
                t_linear = frame / (num_frames - 1) if num_frames > 1 else 1.0
                # 应用 ease-in-out 缓动函数：t^2 * (3 - 2*t)，让开始和结束更平滑
                t_smooth = t_linear * t_linear * (3.0 - 2.0 * t_linear)
                
                current_angles = []
                for start_angle, end_angle in zip(start_angles, end_angles):
                    # 使用缓动函数插值，避免突然改变方向
                    current_angle = start_angle + (end_angle - start_angle) * t_smooth
                    current_angles.append(current_angle)
                
                # 发布当前帧
                self.publish_single_frame(current_angles, verbose=False)
                rate.sleep()
                
                #  关键修复：每帧都更新_last_joint_angles，确保过渡结束时位置正确，避免抖动
                self._last_joint_angles = current_angles.copy() if isinstance(current_angles, list) else list(current_angles)
            
            return True
    
    def publish_enhanced_sequence(self, gesture_sequence: List[Dict], fps=50, 
                                smooth_transitions=True, verbose=True, speech_duration=None,
                                interrupt_flag=None):
        """发布增强的手势序列（带平滑过渡）
        
        Args:
            gesture_sequence: 手势序列
            fps: 发布频率
            smooth_transitions: 是否启用平滑过渡
            verbose: 是否打印详细信息
            speech_duration: 语音时长（秒），用于调整手势时长 - 已在gesture_policy中处理，这里不再使用
            interrupt_flag: 中断检查函数，返回True时立即停止发布
        """
        if not gesture_sequence:
            print("手势序列为空")
            return False
        
        #  判定是否待机序列：main.py 中待机手势会以 idle_ 前缀命名
        try:
            names = [(g.get('gesture_name') or g.get('gesture', '') or '') for g in gesture_sequence]
            is_idle_seq = all(isinstance(n, str) and n.startswith('idle_') for n in names if n)
        except Exception:
            is_idle_seq = False

        #  仅在“待机 -> 说话(非待机序列)”切换时，对第一条手势启用一次软启动
        self._soft_start_next_gesture = (self._last_sequence_mode == 'idle' and not is_idle_seq)

        with self._publish_lock:
            if not self.is_initialized:
                if not self.initialize_ros():
                    return False

            if verbose:
                print(f"开始发布增强手势序列，共{len(gesture_sequence)}个动作")
            
            #  关键修复：不再进行任何时间缩放，直接使用gesture_policy生成的精确时长
            # gesture_policy.py 已经根据speech_duration精确规划了手势序列，这里不应该再次调整
            durations = [g.get('duration', 0.5) for g in gesture_sequence]
            total_duration = sum(durations)
            
            if verbose:
                print(f" 使用精确时长（无缩放）:")
                print(f"   手势序列总时长: {total_duration:.2f}秒")
                print(f"   帧率: {fps}fps，预计帧数: {int(total_duration * fps)}")
            
            #  修复：统一发布逻辑，完全不处理speech_duration
            # 如果没有启用手势过渡或只有一个手势，逐个发布（支持中断）
            if not smooth_transitions or len(gesture_sequence) <= 1:
                for i, gesture in enumerate(gesture_sequence):
                    #  在每个手势前检查中断标志
                    if interrupt_flag and interrupt_flag():
                        if verbose:
                            print(f"[警告] 检测到中断标志，停止发布 (已完成 {i}/{len(gesture_sequence)} 个手势)")
                        return False
                    
                    if verbose:
                        print(f"处理第 {i+1}/{len(gesture_sequence)} 个手势: {gesture.get('gesture_name', 'unknown')}")
                    
                    #  修复：直接发布单个手势，使用原始时长
                    success = self._publish_single_gesture_direct(gesture, fps, verbose, interrupt_flag)
                    if not success:
                        return False
                
                #  更新模式（用于下次检测待机->说话）
                self._last_sequence_mode = 'idle' if is_idle_seq else 'active'
                if verbose:
                    print("手势序列发布完成")
                return True
            
            # 启用手势过渡
            for i in range(len(gesture_sequence)):
                #  检查中断标志
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 检测到中断标志，停止发布 (已完成 {i}/{len(gesture_sequence)} 个手势)")
                    return False
                
                current_gesture = gesture_sequence[i]
                if verbose:
                    print(f"处理第 {i+1}/{len(gesture_sequence)} 个手势: {current_gesture.get('gesture_name', 'unknown')}")
                
                #  关键修复：在发布手势前再次检查中断标志，确保不会与另一个动作冲突
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 发布手势前检测到中断标志，立即停止")
                    return False
                
                if i > 0:  # 不是第一个手势
                    #  再次检查中断标志
                    if interrupt_flag and interrupt_flag():
                        if verbose:
                            print(f"[警告] 检测到中断标志，停止发布")
                        return False
                    
                    #  用户要求：不要增加过渡，直接切换，避免抖动
                    # 不添加过渡，直接执行下一个手势
                    # 保持原始duration，不减去过渡时间
                    current_gesture = current_gesture.copy()
                    # current_gesture['duration'] 保持不变，不调整
                
                #  修复：直接发布当前手势，不传递speech_duration避免双重缩放
                if current_gesture['duration'] > 0:
                    success = self._publish_single_gesture_direct(current_gesture, fps, verbose, interrupt_flag)
                    if not success:
                        return False
            
            #  更新模式（用于下次检测待机->说话）
            self._last_sequence_mode = 'idle' if is_idle_seq else 'active'
            if verbose:
                print("增强手势序列发布完成")
            return True
    
    def _publish_single_gesture_direct(self, gesture: Dict, fps: float, verbose: bool, interrupt_flag=None):
        """直接发布单个手势，不进行时间缩放处理
        
        Args:
            gesture: 单个手势字典
            fps: 发布频率
            verbose: 是否打印详细信息
            interrupt_flag: 中断检查函数
        """
        with self._publish_lock:
            # 检查ROS是否关闭
            if self.ros_version == 2:
                if not rclpy.ok():
                    return False
            else:
                if rospy.is_shutdown():
                    return False
            
            #  修复：兼容 'gesture' 和 'gesture_name' 两种字段名
            gesture_name = gesture.get('gesture_name') or gesture.get('gesture', 'rest')
            duration = max(0.1, float(gesture.get('duration', 0.5)))
            
            if verbose:
                print(f"步骤 1/1: {gesture_name} ({duration:.2f}s)")

            # 获取当前手势的关节角度
            #  优先使用序列中已有的joint_angles，如果没有则通过mapper查找
            joint_angles = gesture.get('joint_angles')
            if joint_angles is None:
                joint_angles = self.gesture_mapper.map_gesture(gesture_name)
                if joint_angles is None:
                    print(f"警告: 未找到手势 '{gesture_name}' 的映射，使用默认姿势")
                    joint_angles = self.gesture_mapper.get_default_pose()

            #  关键保护：防止“待机->说话”时因为 neutral(全0) / rest 导致机器人被映射到初始安全位(180°)抖一下
            # 如果上一帧存在（说明机器人当前就在某个待机姿态），且当前手势是 neutral/rest，则改为“保持当前姿态”发布，不再回到初始位
            try:
                if (hasattr(self, '_last_joint_angles') and self._last_joint_angles is not None and
                    isinstance(gesture_name, str) and gesture_name in ('neutral', 'rest')):
                    joint_angles = self._last_joint_angles
            except Exception:
                pass

            #  待机->说话的第一条手势：软启动（更强缓动 + 可选更高fps但总时长不变）
            is_idle_gesture = isinstance(gesture_name, str) and gesture_name.startswith('idle_')
            use_soft_start = (self._soft_start_next_gesture and (not is_idle_gesture))
            if use_soft_start:
                # 消费一次
                self._soft_start_next_gesture = False
            local_fps = max(fps, 100) if use_soft_start else fps

            # 计算每帧的插值步长（总时长不变，只是帧更密集更丝滑）
            num_frames = max(1, int(duration * local_fps))
            
            #  关键修复：获取上一帧的关节角度（用于插值）
            # 确保从待机位置平滑过渡到说话动作，而不是突然拉回初始位置
            #  移除平滑过渡逻辑，直接使用_last_joint_angles，避免待机动作之间的抖动
            if hasattr(self, '_last_joint_angles') and self._last_joint_angles is not None:
                start_angles = self._last_joint_angles  #  使用待机的当前位置，而不是初始位置
                
                #  关键修复：待机->说话时，如果head_pitch差异较大（>2度），确保平滑过渡
                # 避免head_pitch突然跳回0度导致抖动
                if use_soft_start and len(start_angles) > 1 and len(joint_angles) > 1:
                    head_pitch_diff = abs(start_angles[1] - joint_angles[1])
                    if head_pitch_diff > 2.0:  # 如果head_pitch差异超过2度
                        # 确保有足够的插值时间（至少0.3秒）来平滑过渡head_pitch
                        if duration < 0.3:
                            duration = 0.6
                            num_frames = max(1, int(duration * local_fps))
                            if verbose:
                                print(f"  [平滑过渡] head_pitch差异{head_pitch_diff:.1f}度，延长过渡时间至{duration:.2f}s")
            else:
                #  如果没有上一帧（首次启动），使用目标角度，但后续会保持_last_joint_angles
                start_angles = joint_angles

            rate = self._safe_rate(local_fps)
            
            # 插值发布
            for frame in range(num_frames):
                #  每帧都检查中断标志
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 检测到中断标志，立即停止发布")
                    return False
                
                # 检查ROS是否关闭
                if self.ros_version == 2:
                    if not rclpy.ok():
                        return False
                else:
                    if rospy.is_shutdown():
                        return False
                
                #  缓动：待机->说话第一条手势用更强的 smootherstep，启动更“稳/丝滑”
                alpha_linear = (frame + 1) / num_frames
                t = alpha_linear
                if use_soft_start:
                    # smootherstep: 6t^5 - 15t^4 + 10t^3
                    alpha = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
                else:
                    # ease-in-out: t^2 * (3 - 2t)
                    alpha = t * t * (3.0 - 2.0 * t)
                
                # 使用缓动函数插值，让动作更丝滑
                current_angles = [
                    start + (target - start) * alpha
                    for start, target in zip(start_angles, joint_angles)
                ]
                #  关键修复：发布前再次检查中断标志，避免两个动作同时发布导致冲突
                if interrupt_flag and interrupt_flag():
                    if verbose:
                        print(f"[警告] 发布帧前检测到中断标志，立即停止")
                    return False
                
                # 发布当前帧
                self.publish_single_frame(current_angles)
                
                #  关键修复：发布后立即更新_last_joint_angles，避免下一个动作从错误位置开始
                self._last_joint_angles = current_angles.copy() if isinstance(current_angles, list) else list(current_angles)
                
                # 控制发布频率
                rate.sleep()

            if verbose:
                print(f"完成 {gesture_name}")
            
            return True
    
    def test_connection(self):
        """测试与映射器的连接"""
        if not self.initialize_ros():
            return False
        
        print("测试与数字人映射器的连接...")
        
        # 发布一个简单的测试手势
        test_angles = [0.0] * 12  # 全零位置
        
        for i in range(5):
            success = self.publish_single_frame(test_angles, verbose=True)
            if success:
                print(f"测试帧 {i+1}/5 发布成功")
            else:
                print(f"测试帧 {i+1}/5 发布失败")
                return False
            
            time.sleep(0.5)
        
        print("连接测试完成")
        return True

if __name__ == "__main__":
    # 测试代码
    publisher = DigitalHumanROSPublisher()
    
    # 测试连接
    if publisher.test_connection():
        print("ROS发布器测试成功")
        
        # 测试手势序列
        test_sequence = [
            {
                "gesture_name": "neutral",
                "joint_angles": [0.0] * 12,
                "duration": 1.0,
                "emotion": "neutral",
                "intent": "test"
            },
            {
                "gesture_name": "wave_right",
                "joint_angles": [0, 0, 0, 0, 0, 0, 0, 20, -30, 0, -30, 15],
                "duration": 2.0,
                "emotion": "happy",
                "intent": "greeting"
            },
            {
                "gesture_name": "neutral",
                "joint_angles": [0.0] * 12,
                "duration": 1.0,
                "emotion": "neutral",
                "intent": "test"
            }
        ]
        
        print("测试手势序列发布...")
        publisher.publish_enhanced_sequence(test_sequence, fps=10, verbose=True)
        
    else:
        print("ROS发布器测试失败，请检查ROS环境和映射器是否运行")
