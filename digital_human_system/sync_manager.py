#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动作与语音同步管理器
确保动作只在对应语音开始播放时才执行
支持ROS1和ROS2
"""

import threading
import queue
from typing import Dict, List, Optional, Callable
import time

# ROS版本检测和导入
try:
    # 尝试导入ROS2
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from std_msgs.msg import Int32
    ROS_VERSION = 2
except ImportError:
    try:
        # 回退到ROS1
        import rospy
        from std_msgs.msg import Int32
        ROS_VERSION = 1
    except ImportError:
        raise ImportError("未找到ROS1或ROS2环境，请确保已正确安装ROS")

class ActionSyncManager:
    """动作与语音同步管理器
    
    功能：
    1. 订阅 /playid 话题
    2. 管理动作队列
    3. 确保动作与语音同步执行
    """
    
    def __init__(self, node=None):
        """初始化同步管理器
        
        Args:
            node: ROS2节点实例（ROS2需要，ROS1忽略）
        """
        self.ros_version = ROS_VERSION
        self.node = node
        self.current_play_id = None
        self.play_id_sub = None
        self.action_queue = queue.Queue()
        self.is_initialized = False
        self.lock = threading.Lock()
        
        # 动作执行回调
        self.action_executor = None
        
        # 等待队列：{play_id: action_data}
        self.waiting_actions = {}
        
        print(f"🎭 动作同步管理器初始化完成 (ROS{self.ros_version})")
    
    def initialize(self):
        """初始化ROS订阅"""
        if not self.is_initialized:
            try:
                if self.ros_version == 2:
                    # ROS2订阅
                    if self.node is None:
                        raise ValueError("ROS2需要提供node参数")
                    
                    qos_profile = QoSProfile(
                        depth=10,
                        reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.VOLATILE
                    )
                    self.play_id_sub = self.node.create_subscription(
                        Int32, '/playid', self._handle_play_id, qos_profile
                    )
                else:
                    # ROS1订阅
                    self.play_id_sub = rospy.Subscriber('/playid', Int32, self._handle_play_id, queue_size=10)
                
                self.is_initialized = True
                print(f"✅ 已订阅 /playid 话题 (ROS{self.ros_version})")
            except Exception as e:
                print(f"❌ 初始化失败: {e}")
                import traceback
                traceback.print_exc()
                return False
        return True
    
    def _handle_play_id(self, msg):
        """处理接收到的play_id"""
        play_id = msg.data
        
        with self.lock:
            self.current_play_id = play_id
            print(f"🎵 收到播放ID: {play_id}")
            
            # 检查是否有等待该play_id的动作
            if play_id in self.waiting_actions:
                action_data = self.waiting_actions.pop(play_id)
                print(f"✅ 触发动作执行 (play_id: {play_id})")
                
                # 在新线程中执行动作，避免阻塞回调
                threading.Thread(
                    target=self._execute_action,
                    args=(action_data,),
                    daemon=True
                ).start()
    
    def _execute_action(self, action_data):
        """执行动作"""
        if self.action_executor:
            try:
                self.action_executor(action_data)
            except Exception as e:
                print(f"❌ 动作执行失败: {e}")
    
    def register_action(self, play_id: int, action_data: Dict):
        """注册一个动作，等待对应的play_id触发
        
        Args:
            play_id: 语音播放ID
            action_data: 动作数据（包含手势序列等）
        """
        with self.lock:
            self.waiting_actions[play_id] = action_data
            print(f"📝 注册动作 (play_id: {play_id})，等待语音播放...")
    
    def wait_for_play_id(self, expected_play_id: Optional[int] = None, timeout: float = 10.0) -> bool:
        """等待指定的play_id
        
        Args:
            expected_play_id: 期望的play_id，如果为None则等待任意新的play_id
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否成功收到期望的play_id
        """
        start_time = time.time()
        
        # 检查ROS是否关闭的函数
        def is_shutdown():
            if self.ros_version == 2:
                return not rclpy.ok()
            else:
                return rospy.is_shutdown()
        
        if expected_play_id is None:
            # 等待任意新的play_id
            initial_play_id = self.current_play_id
            while not is_shutdown():
                with self.lock:
                    if self.current_play_id is not None and self.current_play_id != initial_play_id:
                        print(f"✅ 收到新的play_id: {self.current_play_id}")
                        return True
                
                if time.time() - start_time > timeout:
                    print(f"⏰ 等待play_id超时 ({timeout}秒)")
                    return False
                
                time.sleep(0.05)
        else:
            # 等待指定的play_id
            while not is_shutdown():
                with self.lock:
                    if self.current_play_id == expected_play_id:
                        print(f"✅ 收到期望的play_id: {expected_play_id}")
                        return True
                
                if time.time() - start_time > timeout:
                    print(f"⏰ 等待play_id {expected_play_id} 超时 ({timeout}秒)，当前: {self.current_play_id}")
                    return False
                
                time.sleep(0.05)
        
        return False
    
    def set_action_executor(self, executor: Callable):
        """设置动作执行回调函数
        
        Args:
            executor: 动作执行函数，接收action_data作为参数
        """
        self.action_executor = executor
        print("✅ 已设置动作执行器")
    
    def get_current_play_id(self) -> Optional[int]:
        """获取当前的play_id"""
        with self.lock:
            return self.current_play_id
    
    def clear_waiting_actions(self):
        """清除所有等待中的动作"""
        with self.lock:
            count = len(self.waiting_actions)
            self.waiting_actions.clear()
            print(f"🗑️  已清除 {count} 个等待中的动作")
    
    def get_waiting_count(self) -> int:
        """获取等待中的动作数量"""
        with self.lock:
            return len(self.waiting_actions)


class SyncedActionPublisher:
    """同步的动作发布器（集成了同步管理器）"""
    
    def __init__(self, ros_publisher):
        """初始化
        
        Args:
            ros_publisher: DigitalHumanROSPublisher实例
        """
        self.ros_publisher = ros_publisher
        # 传递ROS2节点（如果存在）
        node = getattr(ros_publisher, 'node', None)
        self.sync_manager = ActionSyncManager(node=node)
        self.sync_manager.initialize()
        
        # 设置动作执行器
        self.sync_manager.set_action_executor(self._execute_gesture_sequence)
        
        print("🎬 同步动作发布器初始化完成")
    
    def _execute_gesture_sequence(self, action_data: Dict):
        """执行手势序列"""
        gesture_sequence = action_data.get('gesture_sequence', [])
        fps = action_data.get('fps', 50)
        verbose = action_data.get('verbose', True)
        
        if verbose:
            print(f"🎭 开始执行手势序列 (共{len(gesture_sequence)}个动作)")
        
        # 直接发布，不再等待play_id（因为已经在注册时等待了）
        self.ros_publisher.publish_gesture_sequence(
            gesture_sequence=gesture_sequence,
            fps=fps,
            verbose=verbose,
            wait_for_play_id=False  # 关键：不再等待
        )
    
    def publish_with_sync(self, gesture_sequence: List[Dict], play_id: int, 
                         fps: int = 50, verbose: bool = True, timeout: float = 10.0) -> bool:
        """发布手势序列（同步模式）
        
        Args:
            gesture_sequence: 手势序列
            play_id: 对应的语音播放ID
            fps: 发布频率
            verbose: 是否打印详细信息
            timeout: 等待超时时间
        
        Returns:
            bool: 是否成功注册
        """
        action_data = {
            'gesture_sequence': gesture_sequence,
            'fps': fps,
            'verbose': verbose
        }
        
        # 注册动作，等待play_id触发
        self.sync_manager.register_action(play_id, action_data)
        
        if verbose:
            print(f"📝 动作已注册 (play_id: {play_id})，等待语音播放...")
        
        return True
    
    def publish_immediate(self, gesture_sequence: List[Dict], fps: int = 50, 
                         verbose: bool = True, wait_for_any_play_id: bool = False,
                         timeout: float = 10.0) -> bool:
        """立即发布手势序列（可选等待任意play_id）
        
        Args:
            gesture_sequence: 手势序列
            fps: 发布频率
            verbose: 是否打印详细信息
            wait_for_any_play_id: 是否等待任意新的play_id
            timeout: 等待超时时间
        
        Returns:
            bool: 是否成功发布
        """
        if wait_for_any_play_id:
            if verbose:
                print("⏳ 等待语音播放开始...")
            
            if not self.sync_manager.wait_for_play_id(timeout=timeout):
                if verbose:
                    print("❌ 未收到play_id，取消动作发布")
                return False
        
        # 直接发布
        return self.ros_publisher.publish_gesture_sequence(
            gesture_sequence=gesture_sequence,
            fps=fps,
            verbose=verbose,
            wait_for_play_id=False
        )
    
    def get_current_play_id(self) -> Optional[int]:
        """获取当前的play_id"""
        return self.sync_manager.get_current_play_id()
    
    def clear_waiting_actions(self):
        """清除所有等待中的动作"""
        self.sync_manager.clear_waiting_actions()


# 使用示例
if __name__ == "__main__":
    import sys
    sys.path.append('..')
    
    from output_interface.ros_publisher import DigitalHumanROSPublisher
    
    # 初始化ROS
    if ROS_VERSION == 2:
        rclpy.init()
        node = Node('sync_test')
        ros_pub = DigitalHumanROSPublisher(node=node)
    else:
        rospy.init_node('sync_test', anonymous=True)
        ros_pub = DigitalHumanROSPublisher()
    
    ros_pub.initialize_ros()
    
    # 创建同步发布器
    synced_pub = SyncedActionPublisher(ros_pub)
    
    # 测试手势序列
    test_sequence = [
        {
            "gesture_name": "wave_right",
            "joint_angles": [0, 0, 0, 0, 0, 0, 0, -20, 30, 0, 90, -60],
            "duration": 2.0
        },
        {
            "gesture_name": "rest",
            "joint_angles": [0, 0, -5, 5, 0, 10, 0, 5, 5, 0, 10, 0],
            "duration": 1.0
        }
    ]
    
    print("=" * 60)
    print("测试1: 注册动作，等待play_id=100")
    print("=" * 60)
    synced_pub.publish_with_sync(test_sequence, play_id=100)
    
    print("\n请在另一个终端发布play_id:")
    if ROS_VERSION == 2:
        print("ros2 topic pub /playid std_msgs/msg/Int32 \"{data: 100}\"")
    else:
        print("rostopic pub -1 /playid std_msgs/Int32 \"data: 100\"")
    
    # 保持运行
    if ROS_VERSION == 2:
        rclpy.spin(node)
        node.destroy_node()
        rclpy.shutdown()
    else:
        rospy.spin()
