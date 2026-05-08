#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字人系统主程序
整合所有模块，实现文本到手势的完整流水线
"""

import sys
import os
import argparse
import time
import json
import re
import threading
from typing import Optional

# ROS版本检测和导入
try:
    # 尝试导入ROS2
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from std_msgs.msg import String as RosString
    from std_msgs.msg import Int32 as RosInt32
    from ymrobot_msgs.srv import UpLimb
    ROS_VERSION = 2
    print("[OK] 检测到ROS2环境")
except ImportError:
    try:
        # 回退到ROS1
        import rospy
        from std_msgs.msg import String as RosString
        from std_msgs.msg import Int32 as RosInt32
        from ymrobot_msgs.srv import UpLimb
        ROS_VERSION = 1
        print("[OK] 检测到ROS1环境")
    except ImportError:
        raise ImportError("未找到ROS1或ROS2环境，请确保已正确安装ROS")

# 添加模块路径
# 添加当前目录
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# 添加父目录（digital2robot目录），以便导入digital_human_system模块
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from input_processing.text_processor import TextProcessor
from behavior_planner.gesture_policy import GesturePolicy
from output_interface.ros_publisher import DigitalHumanROSPublisher
from sync_manager import SyncedActionPublisher

# 手指控制模块（可选）- 仅双手
try:
    from finger_control.dual_hand_controller import DualHandFingerController
    FINGER_CONTROL_AVAILABLE = True
except ImportError:
    FINGER_CONTROL_AVAILABLE = False
    print("[警告] 双手手指控制模块未找到，手指控制功能已禁用")

class DigitalHumanSystem:
    def __init__(
        self,
        enable_sync=False,
        enable_finger_control=False,
        # 兼容旧参数：单口（已不使用，保留参数不破坏旧调用）
        finger_serial_port="/dev/ttyUSB1",
        finger_baudrate=115200,
        # 新增：左右手双口（默认按你的硬件约定）
        right_finger_port="/dev/ttyUSB0",
        left_finger_port="/dev/ttyUSB2",
    ):
        """初始化数字人系统
        
        Args:
            enable_sync: 是否启用play_id同步机制
            enable_finger_control: 是否启用手指控制
            finger_serial_port: 手指舵机串口设备路径（兼容旧用法）
            finger_baudrate: 手指舵机串口波特率
            right_finger_port: 右手串口（默认 /dev/ttyUSB0)
            left_finger_port: 左手串口（默认 /dev/ttyUSB2)
        """
        print("初始化数字人系统...")
        
        # 初始化各个模块
        self.text_processor = TextProcessor()
        self.gesture_policy = GesturePolicy()
        self.ros_publisher = DigitalHumanROSPublisher()
        
        #  同步管理器（可选）
        self.enable_sync = enable_sync
        self.synced_publisher = None
        if enable_sync:
            self.synced_publisher = SyncedActionPublisher(self.ros_publisher)
            print("[OK] 已启用play_id同步机制")
        
        # 手指控制器（可选）- 仅双手
        self.finger_controller = None
        if enable_finger_control and FINGER_CONTROL_AVAILABLE:
            try:
                self.finger_controller = DualHandFingerController(
                    right_port=right_finger_port,
                    left_port=left_finger_port,
                    baudrate=finger_baudrate,
                    enable=True,
                    debug=True,   # 打开手指调试日志，便于观察是否在发指令
                )
                print("[OK] 已启用手指控制（双手）")
            except Exception as ee:
                print(f"[警告] 双手手指控制器初始化失败: {ee}")
                self.finger_controller = None
        elif enable_finger_control and not FINGER_CONTROL_AVAILABLE:
            print("[警告] 双手手指控制模块不可用，已禁用手指控制")
        
        #  新增：手势序列缓存，按play_id存储
        self.gesture_cache = {}  # {play_id: gesture_sequence}
        self._last_cached_gesture = None  # (gesture_seq, speech_duration, speech_start_wall_guess) 最近一次 timestamps 缓存的序列
        self._last_cached_gesture_time = 0.0  # 缓存时间，用于判断兜底是否过期
        self._timestamp_batch_seq = 0
        self._latest_cache_key_by_play_id = {}  # 外部 play_id 可能恒为999，这里映射到最新内部cache_key
        self._cache_key_to_play_id = {}  # {cache_key: external_play_id}
        self.current_play_id = None
        self.pending_play_ids = set()  #  新增：记录已到达但缓存未准备好的play_id
        self.playid_recv_time = {}  # {play_id: wall_time} 记录/playid到达时刻，用于对齐“追帧”
        #  以“整段话的第一个playid到达时刻”作为语音时间轴基准（解决跨多句的系统延迟）
        self.conversation_start_playid = None
        self.conversation_start_wall = None
        self.last_playid_wall = 0.0
        self.last_timestamps_time = 0  #  新增：记录最后一次收到timestamps的时间
        #  对话超时：用于区分“新段落/新对话”。默认放宽，避免连续语音里被误判成新对话导致不执行。
        # export DH_CONVERSATION_TIMEOUT=15 可调
        self.conversation_timeout = float(os.environ.get("DH_CONVERSATION_TIMEOUT", "15.0"))
        self.executed_gesture_ids = set()  #  记录已执行的手势序列ID
        self._executed_batch_play_ids = set()  #  同一批 timestamps 的 play_id，只执行一次
        self.current_gesture_end_time = 0  #  当前正在执行的手势的预计结束时间
        #  执行抢占：避免“发布动作阻塞回调 -> 中间有语音没动作”
        self._exec_token = 0
        self._exec_lock = threading.Lock()
        self._gesture_execution_running = False
        self._active_exec_token = None
        self._service_replay_play_ids = set()
        
        #  新增：中断标志，用于立即停止当前动作
        self.interrupt_current = False  # 填充动作的中断标志
        self.interrupt_all = False  # 所有动作（包括序列动作）的中断标志
        self.conversation_ended = False  #  新增：对话是否已结束（收到clear消息）
        
        # service 动作执行中标志：期间 /playid 回调只缓存不执行，等 service 动作完成后再触发
        self._service_action_running = False
        self._block_timestamps_until_next_start = False
        
        #  新增：待机动作相关
        self.last_text_time = time.time()  # 最后一次收到文本的时间
        self.last_action_finish_time = time.time()  #  最后一次动作/语音播放结束的时间
        self.idle_threshold = 5.0  #  语音播放结束后5秒无新语音则进入待机
        self.is_idle = False  # 是否处于待机状态
        self.idle_thread = None  # 待机动作线程
        
        print("所有模块初始化完成")
        
        # 辅助函数：更新手指控制
        def _update_finger_control(gesture_name, duration=0.5):
            """更新手指控制（如果启用）"""
            if self.finger_controller:
                try:
                    self.finger_controller.update_gesture(gesture_name, duration)
                except Exception as e:
                    if self.verbose:
                        print(f"[手指控制] 更新失败: {e}")
        
        self._update_finger_control = _update_finger_control

        #  日志开关：默认尽量安静，避免刷屏影响实时性
        # export DH_VERBOSE=1 可打开更多日志
        self.verbose = bool(int(os.environ.get("DH_VERBOSE", "0")))
        # 回中：每句结束后回中；若与下一句间隔短或已溢出则跳过；回中中若来新动作则从中断处平滑到新目标
        self.return_to_center_delay = float(os.environ.get("DH_RETURN_TO_CENTER_DELAY", "0.15"))
        self.return_to_center_min_gap = float(os.environ.get("DH_RETURN_TO_CENTER_MIN_GAP", "0.5"))

        # /command 话题映射：从 custom_actions.json 的 command_mappings 加载
        self._command_mappings = self._load_command_mappings()

    def _load_command_mappings(self):
        """从 custom_actions.json 加载 command_mappings，未配置则使用默认"""
        default = {
            "HUG": "embrace",
            "HAND_WAVE": "wave_right",
            "HANDSHAKE": "你好",
            "HANDE_SHAKE": "你好",
            "HAND_SHAKE": "你好",
        }
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_actions.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                m = data.get("command_mappings", {})
                if isinstance(m, dict) and m:
                    loaded = {str(k).strip().upper(): str(v).strip() for k, v in m.items()}
                    # 未配置的指令使用默认兜底
                    merged = dict(default)
                    merged.update(loaded)
                    return merged
        except Exception as e:
            print(f"[command] 加载 command_mappings 失败: {e}")
        return default

    def _execute_command_action(self, action_name: str):
        """根据动作名执行手势序列（从 gesture_policy / custom_gestures.json 获取）"""
        action_name = (action_name or "").strip()
        if not action_name:
            return
        gp = self.gesture_policy
        # 动作 -> 序列名映射（挥手用右手，握手用 JSON 里的你好）
        action_to_seq = {
            "wave_right": "wave_right_sequence",
            "wave_both": "wave_both_sequence",
            "handshake": "handshake_sequence",
            "embrace": "embrace_sequence",
        }
        steps = None
        if action_name in (getattr(gp, "base_gestures", {}) or {}):
            # base_gestures 单手势：时长以 custom_actions.json 的 action_durations 为准（支持 action_name 或 action_mappings 中的 key）
            dur = 1.5
            try:
                cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_actions.json")
                if os.path.exists(cfg_path):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    ad = cfg.get("action_durations", {})
                    mappings = cfg.get("action_mappings", {})
                    if action_name in ad:
                        dur = float(ad[action_name])
                    else:
                        for action_key, gesture_name in (mappings or {}).items():
                            if gesture_name == action_name and action_key in ad:
                                dur = float(ad[action_key])
                                break
                        else:
                            dur = float(ad.get(action_name, dur))
            except Exception:
                pass
            if action_name == "你好":
                dur = max(1.5, dur)
            steps = [{"gesture": action_name, "duration": dur}]
        else:
            seq_name = action_to_seq.get(action_name, action_name)
            if hasattr(gp, "action_sequences") and seq_name in gp.action_sequences:
                steps = gp.action_sequences[seq_name]
            elif hasattr(gp, "action_sequences") and action_name in gp.action_sequences:
                steps = gp.action_sequences[action_name]
        if not steps or not isinstance(steps, list):
            print(f"[command] 未找到动作序列: {action_name}")
            return
        gesture_seq = [
            {"gesture_name": s.get("gesture", "rest"), "gesture": s.get("gesture", "rest"), "duration": float(s.get("duration", 0.8))}
            for s in steps
        ]
        self._stop_idle_mode()
        self.last_text_time = time.time()
        self.interrupt_all = True
        self.interrupt_current = True
        time.sleep(0.02)
        self.interrupt_all = False
        self.interrupt_current = False
        if self.finger_controller:
            def _finger_worker():
                try:
                    self.finger_controller.update_gesture_sequence(
                        gesture_seq,
                        sleep_between=True,
                        should_stop=lambda: self.interrupt_current or self.interrupt_all,
                    )
                except Exception:
                    pass
            threading.Thread(target=_finger_worker, daemon=True).start()
        self.ros_publisher.publish_enhanced_sequence(
            gesture_seq, fps=100, smooth_transitions=True, verbose=True,
            speech_duration=None, interrupt_flag=lambda: self.interrupt_current or self.interrupt_all,
        )
        print(f"[command] 已执行动作: {action_name}")

    def _start_gesture_execution(self, play_id, gesture_seq, speech_start_wall=None, speech_duration=None):
        """后台启动一次动作执行，并抢占停止上一句的执行（不阻塞回调线程）。
        
        Args:
            speech_duration: 语音总时长（秒），用于执行时校验和兜底补齐。
        """
        try:
            #  关键修复：先设置中断标志，再增加token，确保旧线程能及时退出
            # 触发中断（兼容 publish_enhanced_sequence 的 interrupt_flag）
            self.interrupt_all = True
            self.interrupt_current = True

            with self._exec_lock:
                self._exec_token += 1
                token = self._exec_token
                self._gesture_execution_running = True
                self._active_exec_token = token
            
            #  关键修复：在启动新线程之前就重置中断标志，避免新线程立即被中断
            # 新线程会通过 token 检查来防止冲突，不需要依赖中断标志
            self.interrupt_all = False
            self.interrupt_current = False

            th = threading.Thread(
                target=self._execute_gesture_sequence,
                args=(play_id, gesture_seq, speech_start_wall, token, speech_duration),
                daemon=True
            )
            th.start()
        except Exception as e:
            print(f"[playid] [错误] 启动后台执行失败: {e}")
    
    def process_text_to_gesture(self, text: str, speech_duration: Optional[float] = None, 
                               play_id: Optional[int] = None, wait_for_play_id: bool = None,
                               verbose=True) -> bool:
        """完整的文本到手势处理流程
        
        Args:
            text: 输入文本
            speech_duration: 语音时长（秒）
            play_id: 语音播放ID（如果指定，则等待该ID触发动作）
            wait_for_play_id: 是否等待play_id（如果为None，则根据enable_sync决定）
            verbose: 是否打印详细信息
        
        Returns:
            bool: 是否成功
        """
        if verbose:
            print(f"\n{'='*50}")
            print(f"处理文本: {text}")
            if play_id is not None:
                print(f"语音播放ID: {play_id}")
            print(f"{'='*50}")
        
        try:
            # 步骤1: 文本处理和语义分析
            if verbose:
                print("\n步骤1: 文本处理和语义分析")
            
            semantic_info = self.text_processor.process(text)
            # 为时间轴构建提供原始文本
            semantic_info['utterance_text'] = text
            # 若提供真实语音时长，则用于全局时间对齐
            if speech_duration is not None:
                semantic_info['speech_duration'] = float(speech_duration)
            
            if verbose:
                print(f"  原始文本: {semantic_info['original_text']}")
                print(f"  清理文本: {semantic_info['clean_text']}")
                print(f"  分词结果: {semantic_info['words']}")
                print(f"  检测情感: {semantic_info['emotion']}")
                print(f"  检测意图: {semantic_info['intent']}")
                print(f"  强调词汇: {semantic_info['emphasis_words']}")
                print(f"  词汇数量: {semantic_info['word_count']}")
            
            # 步骤2: 行为规划
            if verbose:
                print("\n步骤2: 行为规划")
            
            gesture_sequence = self.gesture_policy.plan_gesture_sequence(semantic_info)
            # 文本说话（非 /timestamps JSON）：全序列肩前后、外展限幅
            self._apply_speech_arm_pose_limits(gesture_sequence)
            
            if verbose:
                print(f"  规划手势数量: {len(gesture_sequence)}")
                for i, gesture in enumerate(gesture_sequence):
                    print(f"    {i+1}. {gesture['gesture_name']} ({gesture['duration']}s)")
            
            # 步骤3: ROS输出（支持同步）
            if verbose:
                print("\n步骤3: ROS输出")
            
            #  决定是否使用同步机制
            use_sync = wait_for_play_id if wait_for_play_id is not None else self.enable_sync
            
            if use_sync and play_id is not None and self.synced_publisher:
                # 使用同步发布器
                if verbose:
                    print(f"[播放] 使用同步模式 (play_id: {play_id})")
                success = self.synced_publisher.publish_with_sync(
                    gesture_sequence=gesture_sequence,
                    play_id=play_id,
                    fps=100,
                    verbose=verbose
                )
            elif use_sync and self.synced_publisher:
                # 等待任意play_id
                if verbose:
                    print("[播放] 等待任意语音播放...")
                success = self.synced_publisher.publish_immediate(
                    gesture_sequence=gesture_sequence,
                    fps=100,
                    verbose=verbose,
                    wait_for_any_play_id=True
                )
            else:
                # 直接发布（不等待）
                if verbose:
                    print("������ 直接发布模式")
                
                # 更新手指控制（整个序列）
                if self.finger_controller:
                    def _finger_worker2():
                        try:
                            self.finger_controller.update_gesture_sequence(
                                gesture_sequence,
                                sleep_between=True,
                                should_stop=lambda: self.interrupt_current or self.interrupt_all,
                            )
                        except Exception:
                            pass
                    threading.Thread(target=_finger_worker2, daemon=True).start()
                
                success = self.ros_publisher.publish_enhanced_sequence(
                    gesture_sequence, 
                    fps=100, 
                    smooth_transitions=True, 
                    verbose=verbose,
                    speech_duration=speech_duration  #  传递语音时长
                )
            
            if success:
                if verbose:
                    print("\n[OK] 文本处理完成！")
                return True
            else:
                print("\n[错误] ROS发布失败")
                return False
                
        except Exception as e:
            print(f"\n[错误] 处理过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def interactive_mode(self):
        """交互模式"""
        print("\n" + "="*60)
        print("数字人系统 - 交互模式")
        print("="*60)
        print("输入文本，系统将生成对应的手势动作")
        print("输入 'quit' 或 'exit' 退出")
        print("输入 'test' 运行测试序列")
        print("输入 'info' 查看系统信息")
        print("-"*60)
        
        while True:
            try:
                user_input = input("\n请输入文本: ").strip()
                
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print("退出数字人系统")
                    break
                
                elif user_input.lower() == 'test':
                    self.run_test_sequence()
                
                elif user_input.lower() == 'info':
                    self.show_system_info()
                
                elif user_input:
                    self.process_text_to_gesture(user_input, verbose=True)
                
                else:
                    print("请输入有效的文本")
                    
            except KeyboardInterrupt:
                print("\n\n收到中断信号，退出系统")
                break
            except Exception as e:
                print(f"处理输入时出错: {e}")
    
    def run_test_sequence(self):
        """运行测试序列"""
        print("\n运行测试序列...")
        
        test_texts = [
            "你好，欢迎来到我们的展示！",
            "今天我要为大家介绍一个重要的技术方案",
            "这个系统有什么特别的优势吗？",
            "非常感谢大家的参与，再见！"
        ]
        for i, text in enumerate(test_texts):
            print(f"\n测试 {i+1}/{len(test_texts)}")
            success = self.process_text_to_gesture(text, verbose=True)
            
            if not success:
                print(f"测试 {i+1} 失败")
                return False
            
            # 测试间隔
            if i < len(test_texts) - 1:
                print("等待3秒后继续下一个测试...")
                time.sleep(3)
        
        print("\n[OK] 所有测试完成！")
        return True
    
    def show_system_info(self):
        """显示系统信息"""
        print("\n" + "="*50)
        print("数字人系统信息")
        print("="*50)
        
        # 手势库信息
        gesture_info = self.gesture_policy.get_gesture_info()
        print(f"可用手势: {len(gesture_info['available_gestures'])}个")
        print(f"  {', '.join(gesture_info['available_gestures'])}")
        
        print(f"\n支持意图: {len(gesture_info['supported_intents'])}种")
        print(f"  {', '.join(gesture_info['supported_intents'])}")
        
        print(f"\n支持情感: {len(gesture_info['supported_emotions'])}种")
        print(f"  {', '.join(gesture_info['supported_emotions'])}")
        
        # ROS连接状态
        print(f"\nROS话题: {self.ros_publisher.topic_name}")
        print(f"ROS状态: {'已连接' if self.ros_publisher.is_initialized else '未连接'}")
        
        print("="*50)
    
    def test_connection(self):
        """测试系统连接"""
        print("测试系统连接...")
        return self.ros_publisher.test_connection()
    
    def _get_sequence_action_duration(self, action_name):
        """获取序列动作的时长（含 custom_actions.json 与 GUI 保存的自定义序列）"""
        action_name = (action_name or "").strip()
        if not action_name:
            return 0.0
        # 1. 优先从 gesture_policy 的 custom_actions 配置取（含 GUI 保存的 action_durations）
        try:
            if hasattr(self, "gesture_policy") and self.gesture_policy is not None:
                dur = getattr(self.gesture_policy, "_custom_action_durations", None)
                if isinstance(dur, dict) and action_name in dur:
                    return float(dur[action_name])
                # 2. 若在 action_sequences 中，用各步骤 duration 之和
                seqs = getattr(self.gesture_policy, "action_sequences", None)
                if isinstance(seqs, dict) and action_name in seqs:
                    steps = seqs[action_name]
                    if isinstance(steps, list):
                        return sum(float(s.get("duration", 0)) for s in steps if isinstance(s, dict))
        except Exception:
            pass
        # 3. 从 custom_actions.json 的 action_durations 取（覆盖中文动作名如"左边"/"右边"/"您"等）
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_actions.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                ad = cfg.get("action_durations", {})
                if action_name in ad:
                    return float(ad[action_name])
                # 也检查 action_mappings：action_key -> gesture_name，若 gesture_name 匹配则用 action_key 的时长
                mappings = cfg.get("action_mappings", {})
                for action_key, gesture_name in (mappings or {}).items():
                    if gesture_name == action_name and action_key in ad:
                        return float(ad[action_key])
                # 若 action_name 在 action_aliases 中（作为 key），也视为有效动作，返回默认时长
                aliases = cfg.get("action_aliases", {})
                if action_name in aliases:
                    return float(ad.get(action_name, 1.5))
        except Exception:
            pass
        # 4. 若在 base_gestures 中，视为单帧动作，返回默认时长 1.5s
        try:
            if hasattr(self, "gesture_policy") and self.gesture_policy is not None:
                bg = getattr(self.gesture_policy, "base_gestures", None)
                if isinstance(bg, dict) and action_name in bg:
                    return 1.5
        except Exception:
            pass
        # 5. 内置序列时长
        sequence_durations = {
            "nod_sequence": 1.0,
            "wave_both": 8.0,
            "wave_right": 3.0,
            "wave_left": 3.0,
            "handshake": 3.6,
            "hug": 5.0,
            "embrace": 5.0,
            "clap": 4.0,
            "thumbs_up": 2.0,
        }
        return sequence_durations.get(action_name, 0.0)
    
    def _is_important_action(self, gesture_name):
        """判断是否是重要动作（不应该被删减）
        
        包含：英文关键词 + JSON 自定义动作（custom_actions quick_hold + custom_gestures base_gestures）
        """
        # 1. 英文关键词
        important_keywords = [
            'wave', 'handshake', 'hug', 'embrace', 'clap', 'thumbs_up',
            'look_left', 'look_right', 'look_up', 'look_down',
            'point', 'ok', 'nod', 'shake_head',
        ]
        gesture_lower = (gesture_name or "").lower()
        for keyword in important_keywords:
            if keyword in gesture_lower:
                return True
        # 2. JSON 自定义动作：custom_actions quick_hold_gestures + custom_gestures base_gestures
        try:
            if hasattr(self, 'gesture_policy') and self.gesture_policy:
                gp = self.gesture_policy
                if getattr(gp, '_quick_hold_gestures', None) and gesture_name in gp._quick_hold_gestures:
                    return True
                if getattr(gp, 'base_gestures', None) and gesture_name in gp.base_gestures:
                    return True
        except Exception:
            pass
        # 3. �� 修复：custom_actions.json 的 action_aliases key 也视为重要动作
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_actions.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if gesture_name in cfg.get("action_aliases", {}):
                    return True
                if gesture_name in cfg.get("action_mappings", {}):
                    return True
        except Exception:
            pass
        return False

    def _apply_first_gesture_velocity_cap(self, gesture_seq, v_max_deg_per_s=100.0):
        """第一动作速度封顶：若从当前姿态到目标姿态的最大关节速度超过 v_max，延长首段时长。

        减少大动作突变感。v_max_deg_per_s 单位：度/秒，默认 100。
        """
        if not gesture_seq or v_max_deg_per_s <= 0:
            return
        first = None
        min_offset = float("inf")
        for g in gesture_seq:
            if not isinstance(g, dict):
                continue
            so = float(g.get("start_offset", 0.0) or 0.0)
            if so < min_offset:
                min_offset = so
                first = g
        if first is None:
            return
        name = first.get("gesture_name") or first.get("gesture") or "rest"
        target = first.get("joint_angles")
        if target is None and hasattr(self, "gesture_policy") and self.gesture_policy and getattr(self.gesture_policy, "base_gestures", None):
            target = self.gesture_policy.base_gestures.get(name)
        if target is None and hasattr(self, "ros_publisher") and self.ros_publisher and getattr(self.ros_publisher, "gesture_mapper", None):
            target = self.ros_publisher.gesture_mapper.map_gesture(name)
        if target is None:
            return
        try:
            target = list(target)
        except Exception:
            return
        current = getattr(self.ros_publisher, "_last_joint_angles", None) if hasattr(self, "ros_publisher") and self.ros_publisher else None
        if current is None:
            return
        try:
            current = list(current)
        except Exception:
            return
        n = min(len(current), len(target))
        if n == 0:
            return
        max_delta = max(abs(float(target[i]) - float(current[i])) for i in range(n))
        if max_delta < 1e-6:
            return
        t_min = max_delta / float(v_max_deg_per_s)
        old_dur = float(first.get("duration", 0.5) or 0.5)
        if old_dur >= t_min:
            return
        delta = t_min - old_dur
        first["duration"] = t_min
        if delta > 0.01 and self.verbose:
            print(f"[速度封顶] 首动作 {name}: {old_dur:.2f}s -> {t_min:.2f}s (maxΔ={max_delta:.1f}° @ {v_max_deg_per_s}°/s)")
        for g in gesture_seq:
            if g is first:
                continue
            if not isinstance(g, dict) or "start_offset" not in g:
                continue
            try:
                so = float(g.get("start_offset", 0.0) or 0.0)
                if so > min_offset:
                    g["start_offset"] = so + delta
            except Exception:
                pass

    def _apply_first_gesture_arm_swing_limit(self, gesture_seq, max_deg=25.0):
        """
        限制首个动作的手臂前后摆幅（肩关节 pitch）：
        - 左臂前后: 关节索引 2
        - 右臂前后: 关节索引 7
        """
        if not gesture_seq:
            return
        first = None
        min_offset = float("inf")
        for g in gesture_seq:
            if not isinstance(g, dict):
                continue
            so = float(g.get("start_offset", 0.0) or 0.0)
            if so < min_offset:
                min_offset = so
                first = g
        if first is None:
            return

        name = first.get("gesture_name") or first.get("gesture") or "rest"
        target = first.get("joint_angles")
        if target is None and hasattr(self, "gesture_policy") and self.gesture_policy and getattr(self.gesture_policy, "base_gestures", None):
            target = self.gesture_policy.base_gestures.get(name)
        if target is None and hasattr(self, "ros_publisher") and self.ros_publisher and getattr(self.ros_publisher, "gesture_mapper", None):
            target = self.ros_publisher.gesture_mapper.map_gesture(name)
        if target is None:
            return
        try:
            angles = list(target)
        except Exception:
            return
        if len(angles) < 8:
            return

        lim = abs(float(max_deg))
        angles[2] = max(-lim, min(lim, float(angles[2])))
        angles[7] = max(-lim, min(lim, float(angles[7])))
        first["joint_angles"] = angles
        if self.verbose:
            print(f"[限幅] 首动作前后摆限制: {name}, left={angles[2]:.1f}°, right={angles[7]:.1f}°, lim=±{lim:.1f}°")

    def _is_timestamps_json_timeline(self, gesture_seq, speech_start_wall) -> bool:
        """/timestamps + /playid 的 JSON 时间轴路径（带 start_offset 排程），此类不套「非 JSON 说话限幅」。"""
        if speech_start_wall is None or not gesture_seq:
            return False
        return any(isinstance(g, dict) and ("start_offset" in g) for g in gesture_seq)

    def _apply_speech_arm_pose_limits(self, gesture_seq, pitch_max: float = None, abduction_max: float = None):
        """
        说话动作（非 timestamps JSON 时间轴）：逐帧限制肩「前后摆」(2,7)、「外展」(3,8)。
        关节索引与 gesture_policy 一致：2/7=左右前后，3/8=左右外展。
        """
        if not gesture_seq:
            return
        try:
            pm = float(os.environ.get("DH_SPEECH_ARM_PITCH_MAX", "60.0") if pitch_max is None else pitch_max)
            am = float(os.environ.get("DH_SPEECH_ARM_ABDUCTION_MAX", "30.0") if abduction_max is None else abduction_max)
        except Exception:
            pm, am = 60.0, 30.0
        pm, am = abs(pm), abs(am)
        gp = getattr(self, "gesture_policy", None)
        bg = getattr(gp, "base_gestures", None) if gp else None
        gm = getattr(getattr(self, "ros_publisher", None), "gesture_mapper", None)

        for g in gesture_seq:
            if not isinstance(g, dict):
                continue
            name = g.get("gesture_name") or g.get("gesture") or ""
            angles = g.get("joint_angles")
            if angles is None and bg is not None:
                base = bg.get(name)
                if base is not None:
                    try:
                        angles = list(base)
                    except Exception:
                        angles = None
            if angles is None and gm is not None:
                try:
                    angles = gm.map_gesture(name)
                except Exception:
                    angles = None
            if angles is None:
                continue
            try:
                a = list(angles)
            except Exception:
                continue
            if len(a) < 9:
                continue
            a[2] = max(-pm, min(pm, float(a[2])))
            a[7] = max(-pm, min(pm, float(a[7])))
            a[3] = max(-am, min(am, float(a[3])))
            a[8] = max(-am, min(am, float(a[8])))
            g["joint_angles"] = a
        if self.verbose:
            print(f"[限幅] 说话手臂(非JSON时间轴): 前后(2,7)±{pm:.0f}°, 外展(3,8)±{am:.0f}°")

    def _speech_stop_margin_sec(self) -> float:
        """语音结束后，动作允许略超出的时间（秒）；也用于时间轴裁剪与「不再开新填充」判断。"""
        try:
            return max(0.0, float(os.environ.get("DH_SPEECH_STOP_MARGIN", "0.05")))
        except Exception:
            return 0.05

    def _speech_plan_grace_sec(self) -> float:
        """规划上「仍算在语音段内」的余量（秒），用于裁剪填充 start_offset/duration。"""
        try:
            return max(0.0, float(os.environ.get("DH_SPEECH_PLAN_GRACE", "0.05")))
        except Exception:
            return 0.05

    def _clip_gesture_sequence_to_speech_cap(self, gesture_seq, cap_sec: float, clip_fillers_only: bool = True):
        """
        将时间轴手势裁在 cap_sec 内：丢弃/截短 start_offset+duration 超出 cap 的项。
        默认只裁填充（is_sequence_action=False），序列动作保留原条（完整 JSON 序列）。
        """
        if not gesture_seq or cap_sec is None:
            return gesture_seq
        try:
            cap = float(cap_sec)
        except Exception:
            return gesture_seq
        if cap <= 0.0:
            return gesture_seq
        eps = 1e-3
        out = []
        trimmed = 0
        for g in gesture_seq:
            if not isinstance(g, dict):
                continue
            is_seq = bool(g.get("is_sequence_action"))
            if clip_fillers_only and is_seq:
                out.append(g)
                continue
            so = float(g.get("start_offset", 0.0) or 0.0)
            dur = float(g.get("duration", 0.5) or 0.5)
            end = so + dur
            if so >= cap - eps:
                trimmed += 1
                continue
            if end > cap + eps:
                gg = dict(g)
                nd = max(0.08, cap - so)
                if nd + 1e-6 < dur:
                    gg["duration"] = nd
                    trimmed += 1
                out.append(gg)
            else:
                out.append(g)
        if trimmed and getattr(self, "verbose", False):
            print(f"[timestamps] [裁剪] 按 cap={cap:.2f}s 裁掉/截短 {trimmed} 条手势（fillers_only={clip_fillers_only}）")
        if not out:
            return gesture_seq
        return out

    def _effective_speech_duration_for_exec(self, total_duration: float, merged_timestamps) -> float:
        """
        用于执行的语音时长上界：取「最后词结束时间」与 total_duration 较小者，再减去尾裁（抵消尾静音/时间戳偏长）。
        """
        try:
            td = max(0.0, float(total_duration or 0.0))
        except Exception:
            td = 0.0
        tw_end = td
        try:
            ts = [w for w in (merged_timestamps or []) if isinstance(w, dict)]
            if ts:
                tw_end = max(float(w.get("end_time", 0.0) or 0.0) for w in ts)
        except Exception:
            tw_end = td
        try:
            tail = max(0.0, float(os.environ.get("DH_SPEECH_END_TRIM", "0.2")))
        except Exception:
            tail = 0.2
        cap = max(0.05, min(td, tw_end) - tail)
        return cap

    def _speech_deadline_interrupt_factory(self, base_wall: float, speech_duration):
        """
        返回 interrupt_flag：抢占标志为真，或当前时间已超过 base_wall + speech_duration + margin。
        用于 publish_enhanced_sequence 帧循环内截断，避免语音停了很久仍播完多个填充。
        """
        base_intr = lambda: bool(self.interrupt_current or self.interrupt_all)
        if speech_duration is None:
            return base_intr
        try:
            sd = float(speech_duration)
            if sd <= 0.0:
                return base_intr
        except Exception:
            return base_intr
        deadline = float(base_wall) + sd + self._speech_stop_margin_sec()

        def _intr():
            if self.interrupt_current or self.interrupt_all:
                return True
            return time.time() >= deadline
        return _intr

    def _trim_timeline_fillers_to_speech(self, seq_sorted, speech_duration):
        """
        按语音时长裁掉/截短填充动作（is_sequence_action=False）；序列动作不裁。
        解决：规划里若干填充的 start_offset 仍在 speech_duration 附近，导致真实语音结束后又多播 2～3 个。
        """
        if not seq_sorted or speech_duration is None:
            return seq_sorted
        try:
            sd = float(speech_duration)
        except Exception:
            return seq_sorted
        if sd <= 0.0:
            return seq_sorted
        limit_end = sd + self._speech_plan_grace_sec()
        out = []
        dropped = 0
        for g in seq_sorted:
            if not isinstance(g, dict):
                continue
            if g.get("is_sequence_action"):
                out.append(g)
                continue
            so = float(g.get("start_offset", 0.0) or 0.0)
            dur = float(g.get("duration", 0.5) or 0.5)
            if so >= limit_end:
                dropped += 1
                continue
            end = so + dur
            if end > limit_end:
                gg = dict(g)
                new_dur = max(0.08, limit_end - so)
                if new_dur + 1e-6 < dur:
                    gg["duration"] = new_dur
                out.append(gg)
            else:
                out.append(g)
        if dropped and getattr(self, "verbose", False):
            print(f"[playid] [裁剪] 丢弃语音段外填充 {dropped} 个 (limit_end={limit_end:.2f}s)")
        return out

    def _execute_gesture_sequence(self, play_id, gesture_seq, speech_start_wall=None, _exec_token=None, speech_duration=None):
        """执行手势序列（从playid回调或缓存生成后调用）
        
         整段处理模式：
        - 所有句子共享同一个手势序列
        - 只在第一个playid到达时执行一次
        - 后续playid检查：如果前面的序列动作还在执行，跳过所有动作
        """
        try:
            import time

            def _cleanup_batch_cache(done_play_id: int):
                """
                清理本批已执行缓存，避免 gesture_cache 长期非空导致无法进入待机。
                - 若 _executed_batch_play_ids 非空：优先按该集合整批清理
                - 否则仅清理当前 done_play_id（兼容旧路径）
                """
                try:
                    batch_ids = set(getattr(self, "_executed_batch_play_ids", set()) or set())
                    if batch_ids:
                        for pid in list(batch_ids):
                            try:
                                self.gesture_cache.pop(pid, None)
                            except Exception:
                                pass
                        # 本批清理完成后重置，避免误伤后续新批次
                        self._executed_batch_play_ids = set()
                    else:
                        self.gesture_cache.pop(done_play_id, None)
                except Exception:
                    # 保底：至少清理当前 id
                    try:
                        self.gesture_cache.pop(done_play_id, None)
                    except Exception:
                        pass

            def _start_finger_sequence_sync(seq, allow_interrupt=True):
                """让手指按序列 duration 分段执行，避免一次性提前执行完。"""
                if not self.finger_controller or not seq:
                    return
                try:
                    def _should_stop():
                        if not allow_interrupt:
                            return False
                        return bool(self.interrupt_current or self.interrupt_all)

                    th = threading.Thread(
                        target=self.finger_controller.update_gesture_sequence,
                        args=(seq,),
                        kwargs={
                            "sleep_between": True,
                            "should_stop": _should_stop,
                        },
                        daemon=True,
                    )
                    th.start()
                except Exception:
                    pass

            # 统一保证「你好」至少 1.5s（command / timestamps / 其它入口均生效，不影响其它动作）
            if gesture_seq:
                for g in gesture_seq:
                    if not isinstance(g, dict):
                        continue
                    name = g.get("gesture_name") or g.get("gesture") or ""
                    if name == "你好":
                        d = float(g.get("duration") or 0.0)
                        if d < 1.5:
                            g["duration"] = 1.5

            # 第一动作速度封顶（100°/s）：仅对“无语音时间轴”的路径生效，避免破坏 timestamps 对齐
            # - 有 speech_start_wall（timestamps 驱动）时，gesture_policy 已精确规划时间轴，这里不再改动
            if speech_start_wall is None:
                self._apply_first_gesture_velocity_cap(gesture_seq, v_max_deg_per_s=100.0)

            is_json_tl = self._is_timestamps_json_timeline(gesture_seq, speech_start_wall)
            # JSON 时间轴：仅保留首动作前后摆 ±25°（与原先一致），不套全序列 60/30 限幅
            if is_json_tl:
                self._apply_first_gesture_arm_swing_limit(gesture_seq, max_deg=25.0)
            else:
                # 其它说话路径（文本规划、无 start_offset 的 playid 等）：全序列前后摆≤60°、外展≤30°
                self._apply_speech_arm_pose_limits(gesture_seq)

            #  若手势已带时间轴排程(start_offset)，则按语音时间轴逐个发布
            # 语音0点 = /playid 到达时刻（speech_start_wall）
            if is_json_tl:
                my_token = _exec_token
                #  关键修复：开始新的排程执行前，先检查token是否仍然有效
                # 如果token已经失效（被新句子抢占），立即退出，避免两个动作互相抢
                if my_token is not None and my_token != getattr(self, "_exec_token", my_token):
                    if self.verbose:
                        print("[playid] [停止] 执行开始前检测到token失效，立即退出（避免动作冲突）")
                    return
                # 开始新的排程执行前，重置中断标志，避免继承上一句/上一段的中断状态导致立刻停止
                self.interrupt_current = False
                self.interrupt_all = False

                base = float(speech_start_wall)
                #  关键修复：分离序列动作和填充动作，确保序列动作连续执行，避免填充动作插入导致抖动
                sequence_gestures = [
                    g for g in gesture_seq
                    if isinstance(g, dict) and g.get('is_sequence_action', False)
                ]
                filler_gestures = [
                    g for g in gesture_seq
                    if isinstance(g, dict) and not g.get('is_sequence_action', False)
                ]
                # 序列动作按 start_offset 排序（确保连续执行）
                sequence_gestures.sort(key=lambda x: float(x.get('start_offset', 0.0) or 0.0))
                # 填充动作按 start_offset 排序
                filler_gestures.sort(key=lambda x: float(x.get('start_offset', 0.0) or 0.0))
                
                #  重新组合：序列动作在前（连续执行），填充动作在后（如果有剩余时间）
                # 这样避免填充动作插入到序列动作之间导致抖动
                seq_sorted = sequence_gestures + filler_gestures

                # ✅ 追帧对齐（时间轴序列版）：如果触发晚到（elapsed较大），跳过已经错过的前段动作
                try:
                    elapsed = max(0.0, time.time() - base)
                except Exception:
                    elapsed = 0.0
                if elapsed > 0.1 and seq_sorted:
                    original = list(seq_sorted)
                    trimmed = []
                    for g in original:
                        try:
                            st = float(g.get('start_offset', 0.0) or 0.0)
                            dur = float(g.get('duration', 0.0) or 0.0)
                        except Exception:
                            st, dur = 0.0, 0.0
                        et = st + dur
                        if et <= elapsed:
                            continue
                        if st < elapsed < et:
                            gg = dict(g)
                            gg['start_offset'] = float(elapsed)
                            gg['duration'] = max(0.3, et - elapsed)  # 至少0.3秒，让动作能看见
                            trimmed.append(gg)
                        else:
                            trimmed.append(g)
                    if trimmed:
                        if self.verbose:
                            print(f"[playid] ⏩ 时间轴追帧: 已过去{elapsed:.2f}s，{len(original)} -> {len(trimmed)}")
                        seq_sorted = trimmed
                    else:
                        # 全部错过：仍执行最后一个动作（缩短时长）
                        last_g = dict(original[-1])
                        last_g['start_offset'] = float(elapsed)
                        last_g['duration'] = max(0.3, min(1.0, float(last_g.get('duration', 0.5) or 0.5)))
                        seq_sorted = [last_g]
                
                # ✅ 借鉴口型算法：验证动作时长是否匹配语音时长
                try:
                    gesture_total_duration = max(float(g.get("start_offset", 0.0) or 0.0) + float(g.get("duration", 0.0) or 0.0) for g in seq_sorted)
                except Exception:
                    gesture_total_duration = sum(float(g.get("duration", 0.0) or 0.0) for g in seq_sorted)
                
                # speech_duration 由调用方传入（timestamps 缓存时写入，用于执行时校验和兜底补齐）
                
                print(f"[时间轴验证] 手势总时长: {gesture_total_duration:.2f}s")
                if speech_duration:
                    print(f"[时间轴验证] 语音总时长: {speech_duration:.2f}s")
                    time_diff = speech_duration - gesture_total_duration
                    print(f"[时间轴验证] 时间差异: {time_diff:.2f}s")
                    
                    # 执行阶段「再塞一批填充」会导致语音已结束仍多播；默认关闭（DH_DISABLE_EXEC_TIMEGAP_FILL=0 可打开）
                    _allow_exec_gap_fill = not bool(int(os.environ.get("DH_DISABLE_EXEC_TIMEGAP_FILL", "1")))
                    # ✅ 方案2（可选）：若动作时长明显短于语音（差距>0.5秒），兜底补齐
                    if _allow_exec_gap_fill and time_diff > 0.5:
                        print(f"⚠️  [时间轴修复] 动作时长不足 {time_diff:.2f}s，兜底添加多样填充")
                        if seq_sorted:
                            last_end_offset = float(seq_sorted[-1].get('start_offset', 0.0) or 0.0) + float(seq_sorted[-1].get('duration', 0.0) or 0.0)
                            # 多样填充列表（头/手交替，保证不连续重复）
                            diverse_fillers = [
                                'attentive_listen', 'head_natural_left', 'head_natural_right',
                                'both_hands_explain', 'head_micro_look_left', 'head_micro_look_right',
                                'both_hands_balance', 'curious_lean'
                            ]
                            import random as _rand
                            remaining = time_diff - 0.2
                            current_offset = last_end_offset
                            filler_count = 0
                            last_filler = None
                            
                            while remaining > 0.5:
                                # 轮换选择，避免连续相同
                                pool = [g for g in diverse_fillers if g != last_filler]
                                gesture_name = _rand.choice(pool if pool else diverse_fillers)
                                filler_dur = min(1.0, remaining)
                                
                                filler_gesture = {
                                    'gesture_name': gesture_name,
                                    'start_offset': current_offset,
                                    'duration': filler_dur,
                                    'is_sequence_action': False
                                }
                                seq_sorted.append(filler_gesture)
                                print(f"   [时间轴修复] 兜底填充 {filler_count+1}: {gesture_name} ({filler_dur:.2f}s)")
                                
                                current_offset += filler_dur
                                remaining -= filler_dur
                                filler_count += 1
                                last_filler = gesture_name
                            
                            gesture_total_duration = current_offset

                # 按真实语音时长裁掉/截短「语音已结束后」仍排队的填充，避免再多播 2～3 个
                if speech_duration:
                    _n0 = len(seq_sorted)
                    seq_sorted = self._trim_timeline_fillers_to_speech(seq_sorted, speech_duration)
                    if self.verbose and len(seq_sorted) != _n0:
                        print(f"[playid] [裁剪] 时间轴条目 {_n0} -> {len(seq_sorted)}（按 speech_duration 裁填充）")
                try:
                    gesture_total_duration = max(
                        float(g.get("start_offset", 0.0) or 0.0) + float(g.get("duration", 0.0) or 0.0)
                        for g in seq_sorted
                    )
                except Exception:
                    gesture_total_duration = sum(float(g.get("duration", 0.0) or 0.0) for g in seq_sorted)
                
                # 结束点（用于状态显示/避免旧逻辑跳过），不再作为强制停止条件
                # 但执行时会根据 speech_duration 对“填充动作”做保护，避免语音结束后还额外多播多个动作
                end_t = gesture_total_duration
                if end_t is not None:
                    self.current_gesture_end_time = base + float(end_t)
                    #  语音/动作预计结束时间，用于待机计时
                    self.last_action_finish_time = self.current_gesture_end_time
                print(f"[playid] [计时] 时间轴排程执行: {len(seq_sorted)}个手势（按 start_offset）")
                now = time.time()
                elapsed = max(0.0, now - base)
                if elapsed > 0.05:  # 如果语音已经开始超过0.05秒
                    print(f"[playid] [快速] 语音已开始{elapsed:.2f}s，立即执行（跳过等待）")
                
                #  记录前一个手势的实际结束时间（用于计算相对延迟）
                prev_actual_end = base + elapsed  # 从当前时刻开始
                
                #  使用 while 循环，支持跳过已合并的手势
                # 序列动作（is_sequence_action）必须完整执行，不被新 play_id 抢占
                i = 0
                while i < len(seq_sorted):
                    g = seq_sorted[i]
                    is_seq_gesture = isinstance(g, dict) and g.get('is_sequence_action', False)
                    # clear 优先级最高，所有动作（含序列动作）立即停
                    if self.conversation_ended:
                        return
                    # 仅对填充动作响应普通抢占；序列动作不被新 play_id 打断
                    if not is_seq_gesture:
                        if my_token is not None and my_token != getattr(self, "_exec_token", my_token):
                            if self.verbose:
                                print("[playid] [停止] 被新句子抢占，停止时间轴执行")
                            return
                        if self.interrupt_all:
                            return
                    
                    start_off = float(g.get('start_offset', 0.0) or 0.0)
                    gesture_duration = float(g.get('duration', 0.5) or 0.5)
                    now = time.time()
                    elapsed = max(0.0, now - base)
                    # 若有语音时长信息：避免语音结束后仍播放过多填充动作（余量由 DH_SPEECH_STOP_MARGIN 控制）
                    _sp_m = self._speech_stop_margin_sec()
                    if speech_duration and not is_seq_gesture:
                        if start_off >= float(speech_duration) + _sp_m:
                            if self.verbose:
                                print(f"[playid] [停止] 规划起点已超过语音+余量，停止后续填充 (start_off={start_off:.2f}, speech={float(speech_duration):.2f}, m={_sp_m:.2f})")
                            break
                        if elapsed >= float(speech_duration) + _sp_m:
                            if self.verbose:
                                print(f"[playid] [停止] 实际时间已超过语音+余量，停止后续填充 (elapsed={elapsed:.2f}, speech={float(speech_duration):.2f}, m={_sp_m:.2f})")
                            break
                    
                    # 严格按 start_offset 对齐，避免首个手势提前触发
                    desired_start = base + start_off
                    wait = max(0.0, desired_start - time.time())
                    if wait <= 0.05:
                        wait = 0.0
                        if self.verbose:
                            print(f"[playid] [快速] 手势{i+1}立即执行（已到/接近时间点）")
                    else:
                        if self.verbose:
                            print(f"[playid] [等待] 手势{i+1}等待{wait:.2f}s（对齐 start_offset={start_off:.2f}s）")
                    
                    if wait > 0:
                        remain = float(wait)
                        while remain > 0:
                            # clear 优先级最高，所有动作立即停
                            if self.conversation_ended:
                                return
                            if not is_seq_gesture:
                                if my_token is not None and my_token != getattr(self, "_exec_token", my_token):
                                    if self.verbose:
                                        print("[playid] [停止] 等待阶段被抢占，停止时间轴执行")
                                    return
                                if self.interrupt_all:
                                    return
                                if speech_duration and time.time() >= float(base) + float(speech_duration) + self._speech_stop_margin_sec():
                                    if self.verbose:
                                        print("[playid] [停止] 等待对齐时语音已结束，停止时间轴填充")
                                    return
                            step = min(0.05, remain)
                            time.sleep(step)
                            remain -= step
                    
                    # 记录手势开始执行的实际时间
                    gesture_start_time = time.time()
                    # 不再按语音结束点强制停止（你要求序列动作必须完整执行）
                    #  关键修复：对于连续的手势，合并发布并启用平滑过渡，避免逐个发布导致抖动
                    # 检查是否可以与下一个手势合并发布
                    should_merge = False
                    if i < len(seq_sorted) - 1:
                        next_g = seq_sorted[i + 1]
                        next_start = float(next_g.get('start_offset', 0.0) or 0.0)
                        gap = next_start - (start_off + gesture_duration)
                        next_is_seq = bool(next_g.get("is_sequence_action", False))
                        # 间隔很小才合并；且「序列+填充」不合并，避免语音截止中断截断未播完的序列段
                        if gap < 0.2 and is_seq_gesture == next_is_seq:
                            should_merge = True
                    
                    if should_merge:
                        # 合并发布当前手势和下一个手势，启用平滑过渡
                        merged_seq = [g, next_g]
                        if self.verbose:
                            print(f"[playid] ������ 合并发布手势{i+1}和{i+2}（间隔{gap:.2f}s < 0.2s）")
                        # 手指按 merged_seq 分段执行，避免第二个手势提前下发
                        any_seq = any(gg.get('is_sequence_action') for gg in merged_seq)
                        all_seq = all(bool(gg.get('is_sequence_action')) for gg in merged_seq)
                        _start_finger_sequence_sync(merged_seq, allow_interrupt=(not any_seq))
                        
                        # 仅当整段都是序列动作时用 conversation_ended 截止；含填充时用「语音硬截止」在帧循环内截断
                        if all_seq:
                            _intr_merge = lambda: self.conversation_ended
                        else:
                            _intr_merge = self._speech_deadline_interrupt_factory(base, speech_duration)
                        self.ros_publisher.publish_enhanced_sequence(
                            merged_seq,
                            fps=100,
                            smooth_transitions=True,
                            verbose=True,
                            speech_duration=None,
                            interrupt_flag=_intr_merge
                        )
                        # 跳过下一个手势（已经合并发布了）
                        i += 2  # 跳过当前和下一个
                        prev_actual_end = time.time()
                    else:
                        # 单独发布当前手势
                        #  检测是否需要平滑过渡（相邻手势间隔很小且当前手势很短）
                        use_smooth = False
                        if i > 0 and gesture_duration < 0.5:
                            # 检查与前一个手势的间隔
                            prev_g = seq_sorted[i - 1]
                            prev_start = float(prev_g.get('start_offset', 0.0) or 0.0)
                            prev_duration = float(prev_g.get('duration', 0.5) or 0.5)
                            gap = start_off - (prev_start + prev_duration)
                            # 如果间隔很小（<0.1秒），启用平滑过渡
                            if gap < 0.1:
                                use_smooth = True
                                if self.verbose:
                                    print(f"[playid] 手势{i+1}与前一个间隔{gap:.2f}s，启用平滑过渡")
                        
                        # 更新手指控制
                        gesture_name = g.get('gesture_name') or g.get('gesture', 'rest')
                        duration = g.get('duration', 0.5)
                        self._update_finger_control(gesture_name, duration)
                        
                        is_seq = g.get('is_sequence_action', False)
                        # clear 时序列动作也必须立即停止（conversation_ended 优先级最高）
                        if is_seq:
                            _intr_one = lambda: self.conversation_ended
                        else:
                            _intr_one = self._speech_deadline_interrupt_factory(base, speech_duration)
                        self.ros_publisher.publish_enhanced_sequence(
                            [g],
                            fps=100,
                            smooth_transitions=use_smooth,
                            verbose=True,
                            speech_duration=None,
                            interrupt_flag=_intr_one
                        )
                        i += 1
                    
                    # 更新前一个手势的实际结束时间（用于下一个手势的相对延迟计算）
                    gesture_end_time = time.time()
                    prev_actual_end = gesture_end_time
                
                # 时间轴排程执行完毕：等待短暂时间，若无新句子到来则归位
                _need_rest = True  # 标记需要归位，统一在函数末尾处理
                if self.conversation_ended or self.interrupt_all or self.interrupt_current:
                    _need_rest = False
                else:
                    # 等待最多 0.4s，检查是否有下一句 play_id 到来
                    next_id = play_id + 1
                    for _ in range(20):  # 20 * 20ms = 400ms
                        if self.interrupt_all or self.interrupt_current or self.conversation_ended:
                            _need_rest = False
                            break
                        if next_id in self.playid_recv_time:
                            _need_rest = False
                            break
                        time.sleep(0.02)
                if _need_rest:
                    rest_angles = self.gesture_policy.base_gestures.get(
                        'rest2', self.gesture_policy.base_gestures.get('rest', [0.0] * 12))
                    self.ros_publisher.publish_enhanced_sequence(
                        [{'gesture_name': 'rest2', 'duration': 0.8, 'joint_angles': rest_angles}],
                        fps=100, smooth_transitions=True, verbose=False,
                        speech_duration=None,
                        interrupt_flag=lambda: self.interrupt_all or self.interrupt_current or self.conversation_ended
                    )
                    print("[playid] [归位] 时间轴对话结束，已回到初始位置")
                self.last_text_time = time.time()
                self.last_action_finish_time = time.time()
                _cleanup_batch_cache(play_id)
                return
            
            #  如果有/playid的到达时间，则根据已经过去的时间“追帧”，避免整体越补越晚
            #  关键修复：即使语音已经开始，也要执行动作，不要完全跳过
            # 这是解决“补偿很大仍然晚”的关键：消息往往在语音播放后才到达，必须跳过已经错过的前段动作
            if speech_start_wall is not None:
                try:
                    elapsed = max(0.0, time.time() - float(speech_start_wall))
                except Exception:
                    elapsed = 0.0
                if elapsed > 0.0:
                    trimmed = []
                    acc = 0.0
                    total_duration = sum(float(g.get('duration', 0.0) or 0.0) for g in gesture_seq)

                    for g in gesture_seq:
                        d = float(g.get('duration', 0.0) or 0.0)
                        # 跳过已经“过去”的前缀
                        if acc + d <= elapsed:
                            acc += d
                            continue
                        # 若部分跨过边界，则缩短该动作剩余时长（不为负）
                        if acc < elapsed and (acc + d) > elapsed:
                            remain = max(0.05, (acc + d) - elapsed)  #  最小0.05秒，确保动作能执行
                            gg = dict(g)
                            gg['duration'] = remain
                            trimmed.append(gg)
                            acc += d
                            continue
                        trimmed.append(g)
                        acc += d
                    if trimmed:
                        print(f"[playid] ⏩ 追帧对齐: 已过去{elapsed:.2f}s，丢弃/缩短前段动作，{len(gesture_seq)} -> {len(trimmed)}")
                        gesture_seq = trimmed
                    else:
                        #  关键修复：即使所有动作都错过了，也要执行最后一个动作（缩短时长）
                        if gesture_seq:
                            last_g = dict(gesture_seq[-1])
                            last_g['duration'] = max(0.3, min(1.0, total_duration - elapsed))  # 至少0.3秒，最多1秒
                            gesture_seq = [last_g]
                            print(f"[playid] ⏩ 追帧对齐: 已过去{elapsed:.2f}s，执行最后一个动作（缩短为{last_g['duration']:.2f}s）")
                        else:
                            print(f"[playid] ⏩ 追帧对齐: 已过去{elapsed:.2f}s，无动作可执行")
                            return

            #  分离序列动作和非序列动作
            sequence_actions = [g for g in gesture_seq if g.get('is_sequence_action', False)]
            filler_actions = [g for g in gesture_seq if not g.get('is_sequence_action', False)]
            print(f"[playid] [统计] 序列动作: {len(sequence_actions)}个, 填充动作: {len(filler_actions)}个")
            
            #  检查前面的动作是否还在执行
            current_time = time.time()
            if current_time < self.current_gesture_end_time:
                # 连续语音场景：不要“直接跳过”，而是抢占中断前一段，执行当前句
                self.interrupt_all = True
                self.interrupt_current = True
                self.current_gesture_end_time = 0
            
            # 连续语音：不做“只执行一次”的去重（否则会出现“有语音没动作”）
            
            #  重置中断标志（开始新的手势序列）
            self.interrupt_current = False
            self.interrupt_all = False
            
            if sequence_actions:
                # 有序列动作时：除了原序列动作，还要把“重要JSON动作”并入完整执行队列，
                # 避免出现“只看到最后一个动作/中间动作被打断”的问题。
                promoted_fillers = []
                for g in filler_actions:
                    try:
                        gname = g.get('gesture_name') or g.get('gesture', '')
                        if self._is_important_action(gname):
                            gg = dict(g)
                            gg['is_sequence_action'] = True
                            promoted_fillers.append(gg)
                    except Exception:
                        pass

                execution_actions = list(sequence_actions) + promoted_fillers
                # 按时间轴顺序执行；没有 start_offset 的保持稳定顺序
                try:
                    execution_actions.sort(key=lambda x: float(x.get('start_offset', 0.0) or 0.0))
                except Exception:
                    pass

                seq_duration = sum(g.get('duration', 0) for g in execution_actions)
                
                # 手指与手臂同节奏执行（完整序列不可打断）
                _start_finger_sequence_sync(execution_actions, allow_interrupt=False)
                
                # 更新结束时间（只基于序列动作）
                self.current_gesture_end_time = current_time + seq_duration
                self.last_action_finish_time = self.current_gesture_end_time
                
                if promoted_fillers:
                    print(f"[playid] [提升] 将 {len(promoted_fillers)} 个重要JSON动作并入完整执行队列")
                print(f"[playid] 发布完整动作队列 ({len(execution_actions)}个) - 序列动作与重要JSON动作完整执行")
                # 序列动作必须完整执行，不响应中断（避免新 play_id 打断导致只播第一个手势）
                seq_ok = self.ros_publisher.publish_enhanced_sequence(
                    execution_actions, 
                    fps=100,
                    smooth_transitions=False, 
                    verbose=True,
                    speech_duration=None,
                    interrupt_flag=lambda: self.conversation_ended
                )
                self._maybe_return_to_center_after_sentence(play_id, execution_completed=seq_ok)
                if filler_actions:
                    skipped = max(0, len(filler_actions) - len(promoted_fillers))
                    if skipped > 0:
                        print(f"[playid] [跳过] 跳过普通填充动作 ({skipped}个)")
                
                print(f"[playid] [OK] 完整动作队列发布成功 (ID={play_id}, 时长: {seq_duration:.2f}s)")
                print(f"[playid] [时间] 预计结束时间: {self.current_gesture_end_time:.2f} (当前: {current_time:.2f})")
                
            elif filler_actions:
                #  检查对话是否已结束
                if self.conversation_ended:
                    print(f"[playid] [跳过] 跳过填充动作 - 对话已结束")
                    return
                
                #  没有序列动作：执行填充动作
                filler_duration = sum(g.get('duration', 0) for g in filler_actions)
                
                # 手指与手臂同节奏执行（填充动作允许被中断）
                _start_finger_sequence_sync(filler_actions, allow_interrupt=True)
                
                # 更新结束时间（基于填充动作）
                self.current_gesture_end_time = current_time + filler_duration
                self.last_action_finish_time = self.current_gesture_end_time
                
                print(f"[playid] 发布填充动作 ({len(filler_actions)}个) - 无序列动作时执行填充动作")
                filler_ok = self.ros_publisher.publish_enhanced_sequence(
                    filler_actions, 
                    fps=100,
                    smooth_transitions=False, 
                    verbose=True,
                    speech_duration=None,
                    interrupt_flag=lambda: self.interrupt_current or self.interrupt_all
                )
                self._maybe_return_to_center_after_sentence(play_id, execution_completed=filler_ok)
                print(f"[playid] [OK] 填充动作发布成功 (ID={play_id}, 时长: {filler_duration:.2f}s)")
                print(f"[playid] [时间] 预计结束时间: {self.current_gesture_end_time:.2f} (当前: {current_time:.2f})")
                
            else:
                print(f"[playid] ℹ️  无任何动作，跳过发布")
                # 无动作时，视为当前时间结束
                self.last_action_finish_time = time.time()
            
            #  手势播放完成后，更新时间线（文本时间不变；动作结束时间已在上方设置）
            self.last_text_time = time.time()
            
            # 发布后从缓存中删除，避免重复播放
            _cleanup_batch_cache(play_id)
        except Exception as e:
            print(f"[playid] [错误] 执行手势序列时异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                with self._exec_lock:
                    if _exec_token is None or _exec_token == getattr(self, "_active_exec_token", None):
                        self._gesture_execution_running = False
                        self._active_exec_token = None
                replay_ids = set(getattr(self, "_service_replay_play_ids", set()) or set())
                if replay_ids and (play_id in replay_ids or not self._gesture_execution_running):
                    self._service_replay_play_ids = set()
            except Exception:
                pass
            # 时间轴中途 return / 异常时若未走到 _cleanup_batch_cache，gesture_cache 会残留，
            # _gesture_cache_waiting_for_playid 长期为 True → 永远无法进入待机。
            try:
                batch = set(getattr(self, "_executed_batch_play_ids", set()) or set())
                stale = [pid for pid in batch if pid in self.gesture_cache]
                if stale:
                    now = time.time()
                    for pid in list(stale):
                        self.gesture_cache.pop(pid, None)
                    self._executed_batch_play_ids = set()
                    self.last_action_finish_time = now
                    self.current_gesture_end_time = now
                    if getattr(self, "verbose", False):
                        print(f"[playid] [清理] finally: 已清除残留 gesture_cache，play_ids={sorted(stale)}，并刷新动作结束时间")
            except Exception:
                pass
    
    def run_timestamps_bridge(self, topic: str = "/timestamps"):
        """订阅/timestamps话题，解析时间戳并驱动手势发布。
        
        新逻辑：
        1. 收到timestamps后，解析所有句子并生成手势序列
        2. 按play_id缓存手势序列
        3. 监听/play_id话题，收到play_id时发布对应的手势
        """
        # 确保节点已初始化
        if ROS_VERSION == 2:
            if not rclpy.ok():
                rclpy.init()
            # 创建节点（如果ros_publisher没有节点，创建一个新的）
            if self.ros_publisher.node is None:
                self.ros_publisher.node = Node('digital_human_timestamps_bridge')
                self.ros_publisher._own_node = True
            node = self.ros_publisher.node
        else:
            try:
                rospy.init_node('digital_human_timestamps_bridge', anonymous=True)
            except Exception:
                pass
            node = None

        # ========== 双模式状态机初始化 ==========
        # 模式优先级: TIMESTAMP > SOUND_DETECTED > IDLE
        self._mode_state = "IDLE"  # 当前模式: TIMESTAMP / SOUND / IDLE
        self._last_timestamp_recv_time = 0.0  # 上次收到timestamps的时间
        self._sound_detected_flag = False      # 当前sound_detected状态
        self._last_sound_true_time = 0.0       # 上次sound_detected=true的时间
        self._last_sound_false_time = 0.0      # 上次sound_detected=false的时间
        self._sound_action_executing = False   # 是否正在执行sound_detected动作
        self._sound_action_thread = None       # sound_detected动作执行线程
        
        # 时间阈值（秒，可通过环境变量调整）
        self._timestamp_timeout = float(os.environ.get("DH_TIMESTAMP_TIMEOUT", "2.0"))
        self._sound_to_idle_delay = float(os.environ.get("DH_SOUND_TO_IDLE_DELAY", "10.0"))
        self._sound_action_interval = float(os.environ.get("DH_SOUND_ACTION_INTERVAL", "1.0"))
        self._last_sound_action_time = 0.0
        
        # 随机动作候选列表（对话模式，以手臂动作为主）
        self._sound_action_candidates = [
             # ── 双臂自然对话动作（外展≤20°）──
            {"gesture": "talk_both_low",       "duration": 1.5},
            {"gesture": "talk_both_mid",       "duration": 1.5},
            {"gesture": "talk_both_fwd",       "duration": 1.5},
            {"gesture": "talk_both_chest",     "duration": 1.5},
            {"gesture": "talk_both_open_low",  "duration": 1.5},
            {"gesture": "talk_alt_rl",         "duration": 1.5},
            {"gesture": "talk_alt_lr",         "duration": 1.5},
            # ── 单臂自然对话动作 ──
            {"gesture": "talk_right_low",      "duration": 1.5},
            {"gesture": "talk_right_mid",      "duration": 1.5},
            {"gesture": "talk_right_fwd",      "duration": 1.5},
            {"gesture": "talk_right_open",     "duration": 1.5},
            {"gesture": "talk_left_low",       "duration": 1.5},
            {"gesture": "talk_left_mid",       "duration": 1.5},
            {"gesture": "talk_left_fwd",       "duration": 1.5},
            {"gesture": "talk_left_open",      "duration": 1.5},
            # ── 脖子+手臂组合 ──
            {"gesture": "neck_left_right_arm", "duration": 1.5},
            {"gesture": "neck_right_left_arm", "duration": 1.5},
            {"gesture": "neck_left_both_fwd",  "duration": 1.5},
            {"gesture": "neck_right_both_fwd", "duration": 1.5},
            {"gesture": "neck_left_right_low", "duration": 1.5},
            {"gesture": "neck_right_left_low", "duration": 1.5},
            {"gesture": "neck_tilt_both_mid",  "duration": 1.5},
            {"gesture": "neck_left_explain",   "duration": 1.5},
            {"gesture": "neck_right_explain",  "duration": 1.5},
            # ── 摇头（配手臂）──
            {"gesture": "shake_head_talk",     "duration": 1.2},
            {"gesture": "shake_head_talk_b",   "duration": 1.2},
            # ── 现有动作（外展已修正≤20°）──
            {"gesture": "both_hands_explain",  "duration": 1.5},
            {"gesture": "both_hands_forward",  "duration": 1.5},
            {"gesture": "both_hands_gather",   "duration": 1.5},
            {"gesture": "both_hands_count",    "duration": 1.5},
            {"gesture": "both_hands_measure",  "duration": 1.5},
            {"gesture": "both_hands_push",     "duration": 1.5},
            {"gesture": "both_hands_pull",     "duration": 1.5},
            {"gesture": "both_hands_emphasize","duration": 1.5},
            {"gesture": "explain_right_soft",  "duration": 1.5},
            {"gesture": "explain_right_emphatic","duration": 1.5},
            {"gesture": "explain_left_soft",   "duration": 1.5},
            {"gesture": "explain_left_emphatic","duration": 1.5},
            {"gesture": "confident_assertive", "duration": 1.5},
            # ── 头部动作（约20%）──
            {"gesture": "head_natural_left",      "duration": 1.2},
            {"gesture": "head_natural_right",     "duration": 1.2},
            {"gesture": "head_micro_tilt_left",   "duration": 1.0},
            {"gesture": "head_micro_tilt_right",  "duration": 1.0},
            {"gesture": "head_micro_look_left",   "duration": 1.0},
            {"gesture": "head_micro_look_right",  "duration": 1.0},
            {"gesture": "head_micro_nod",         "duration": 0.8},
            {"gesture": "attentive_listen",       "duration": 1.2},
            {"gesture": "curious_lean",           "duration": 1.2},
        ]
        # ======================================

        def _to_float(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        def _build_action_timeline_from_words(words):
            """✅ 借鉴口型算法思想，但适配手势特点：
            - 口型：每个词一个动作（50-200ms）
            - 手势：智能合并多个词，确保每个手势 0.8-2秒
            - 核心：总时长 = 语音时长（归一化）
            """
            timeline = []
            
            # 过滤掉标点符号，只保留文本词
            text_words = [w for w in words if isinstance(w, dict) and str(w.get('unit_type', 'text')) != 'mark']
            
            if not text_words:
                return timeline
            
            # 计算总时长
            total_duration = _to_float(text_words[-1].get('end_time', 0.0)) - _to_float(text_words[0].get('start_time', 0.0))
            
            if total_duration <= 0:
                return timeline
            
            # ✅ 智能分组：将词合并成手势片段，每个片段 0.8-2秒
            MIN_GESTURE_DURATION = 0.8
            MAX_GESTURE_DURATION = 2.0
            
            gesture_segments = []
            current_segment = []
            current_duration = 0.0
            
            for i, w in enumerate(text_words):
                word_start = _to_float(w.get('start_time', 0.0))
                word_end = _to_float(w.get('end_time', word_start))
                word_duration = word_end - word_start
                
                if not current_segment:
                    # 开始新片段
                    current_segment = [w]
                    current_duration = word_duration
                else:
                    # 检查是否可以添加到当前片段
                    if current_duration + word_duration <= MAX_GESTURE_DURATION:
                        # 可以添加
                        current_segment.append(w)
                        current_duration += word_duration
                    else:
                        # 当前片段已满，保存并开始新片段
                        if current_duration >= MIN_GESTURE_DURATION or i == len(text_words) - 1:
                            # 片段时长足够，或者是最后一个词
                            gesture_segments.append(current_segment)
                        else:
                            # 片段时长不足，继续添加
                            current_segment.append(w)
                            current_duration += word_duration
                            continue
                        
                        # 开始新片段
                        current_segment = [w]
                        current_duration = word_duration
            
            # 添加最后一个片段
            if current_segment:
                gesture_segments.append(current_segment)
            
            # ✅ 为每个片段生成手势
            for segment in gesture_segments:
                if not segment:
                    continue
                
                # 计算片段的时间范围
                seg_start = _to_float(segment[0].get('start_time', 0.0))
                seg_end = _to_float(segment[-1].get('end_time', seg_start))
                seg_duration = seg_end - seg_start
                
                # 提取片段文本
                seg_text = ''.join(str(w.get('word', '')) for w in segment)
                
                # 提取动作（如果有）
                acts = self.text_processor.extract_actions(seg_text)
                act = acts[0] if acts else None
                
                # 添加到时间轴
                timeline.append({
                    "start": seg_start,
                    "duration": seg_duration,
                    "action": act,
                    "words": seg_text  # 保留文本，方便调试
                })
            
            if self.verbose:
                print(f"[时间轴] 智能分组: {len(text_words)}个词 → {len(gesture_segments)}个手势片段")
                for i, seg in enumerate(timeline):
                    print(f"  片段{i+1}: {seg['words'][:20]}... ({seg['duration']:.2f}s)")
            
            return timeline

        def _build_action_timeline_precise(words):
            tokens = []
            for w in words:
                if not isinstance(w, dict):
                    continue
                tok = str(w.get('word', ''))
                s = _to_float(w.get('start_time', 0.0))
                e = _to_float(w.get('end_time', s))
                unit = str(w.get('unit_type', 'text'))
                tokens.append((tok, s, e, unit))
            if not tokens:
                return []
            base = min((s for (_, s, _, _) in tokens), default=0.0)
            text = ""
            c_starts = []
            c_ends = []
            for tok, s, e, unit in tokens:
                t = str(tok)
                for _ in t:
                    text += _
                    c_starts.append(s)
                    c_ends.append(e)
            matches = []
            used = []
            kw_list = []
            try:
                for act, kws in getattr(self.text_processor, 'action_keywords', {}).items():
                    if isinstance(kws, list):
                        for kw in kws:
                            kw_list.append((str(kw), act))
            except Exception:
                pass
            kw_list.sort(key=lambda x: len(x[0]), reverse=True)
            for kw, act in kw_list:
                if not kw:
                    continue
                for m in re.finditer(re.escape(kw), text):
                    si, ei = m.start(), m.end() - 1
                    if si >= len(c_starts) or ei >= len(c_ends):
                        continue
                    overlap = False
                    for l, r in used:
                        if not (ei < l or si > r):
                            overlap = True
                            break
                    if overlap:
                        continue
                    s = c_starts[si]
                    e = c_ends[ei]
                    if e <= s:
                        continue
                    matches.append((s - base, max(0.0, e - s), act, si, ei))
                    used.append((si, ei))
            try:
                regs = getattr(self.text_processor, 'action_regex', {})
                for act, pats in regs.items():
                    if not isinstance(pats, list):
                        continue
                    for pat in pats:
                        try:
                            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                                si, ei = m.start(), m.end() - 1
                                if si >= len(c_starts) or ei >= len(c_ends):
                                    continue
                                overlap = False
                                for l, r in used:
                                    if not (ei < l or si > r):
                                        overlap = True
                                        break
                                if overlap:
                                    continue
                                s = c_starts[si]
                                e = c_ends[ei]
                                if e <= s:
                                    continue
                                matches.append((s - base, max(0.0, e - s), act, si, ei))
                                used.append((si, ei))
                        except Exception:
                            continue
            except Exception:
                pass
            matches.sort(key=lambda x: (x[0], -x[1]))
            # 生成全覆盖时间轴：在动作匹配之间插入背景片段(None)
            full: list = []
            t_cursor = 0.0
            end_total = max((e for e in c_ends), default=base) - base
            for s, d, act, _, _ in matches:
                if s > t_cursor:
                    full.append({"start": t_cursor, "duration": max(0.0, s - t_cursor), "action": None})
                    t_cursor = s
                if d > 0:
                    full.append({"start": s, "duration": d, "action": act})
                    t_cursor = max(t_cursor, s + d)
            if end_total > t_cursor:
                full.append({"start": t_cursor, "duration": max(0.0, end_total - t_cursor), "action": None})
            return full

        #  新增：监听playid话题的回调（使用Int32类型）
        def _play_id_callback(msg):
            """当收到playid时，发布对应的手势序列"""
            try:
                play_id = int(msg.data)  # msg.data 已经是整数
                print(f"\n[playid] [播放] 收到播放ID: {play_id}")

                # 记录该play_id到达的壁钟时间，用于后续根据“已过去多久”追帧对齐
                now_wall = time.time()
                self.playid_recv_time[play_id] = now_wall
                self.current_play_id = play_id
                self._block_timestamps_until_next_start = False

                #  判定是否进入新对话：playid间隔过长则重置基准
                if self.last_playid_wall > 0 and (now_wall - self.last_playid_wall) > self.conversation_timeout:
                    self.conversation_start_playid = None
                    self.conversation_start_wall = None
                self.last_playid_wall = now_wall

                #  若尚未设置整段话起点，则以第一个playid作为起点
                if self.conversation_start_wall is None:
                    self.conversation_start_playid = play_id
                    self.conversation_start_wall = now_wall
                
                #  立即停止待机模式
                self._stop_idle_mode()
                
                #  更新最后文本时间，防止立即重新进入待机
                self.last_text_time = time.time()

                # service 动作优先。此时只记录 play_id，不能用旧 cache/fallback 命中；
                # 现场 play_id 可能固定为 999，旧缓存会导致 service 后恢复 40 多秒前的动作。
                if self._service_action_running:
                    print(f"[playid] [等待] service动作执行中，ID={play_id} 加入等待队列")
                    self.pending_play_ids.add(play_id)
                    return
                
                # 检查缓存中是否有对应的手势序列
                gesture_seq = None
                speech_duration = None
                speech_start_guess = None
                latest_cache_key = self._latest_cache_key_by_play_id.get(play_id)
                cache_key = latest_cache_key if latest_cache_key is not None else play_id
                def _cache_is_recent(cache_time):
                    try:
                        max_age = float(os.environ.get(
                            "DH_PLAYID_CACHE_MAX_AGE",
                            str(max(10.0, self.conversation_timeout))
                        ))
                    except Exception:
                        max_age = max(10.0, self.conversation_timeout)
                    try:
                        ct = float(cache_time or 0.0)
                    except Exception:
                        ct = 0.0
                    return ct > 0.0 and (now_wall - ct) <= max_age

                if cache_key in self.gesture_cache:
                    cached = self.gesture_cache[cache_key]
                    if isinstance(cached, dict):
                        if _cache_is_recent(cached.get('cache_time', 0.0)):
                            gesture_seq = cached.get('gestures', [])
                            speech_duration = cached.get('speech_duration')
                            speech_start_guess = cached.get('speech_start_wall_guess')
                        else:
                            print(f"[playid] [等待] ID={play_id} 命中旧缓存，忽略并等待新的/timestamps")
                    else:
                        if _cache_is_recent(getattr(self, "_last_cached_gesture_time", 0.0)):
                            gesture_seq = cached
                        else:
                            print(f"[playid] [等待] ID={play_id} 命中无时间缓存，忽略并等待新的/timestamps")
                    if gesture_seq is not None:
                        print(f"[playid] [OK] 找到缓存的手势序列 (ID={play_id}, key={cache_key}, {len(gesture_seq)}个手势)")
                elif latest_cache_key is not None:
                    print(f"[playid] [等待] ID={play_id} 的最新内部key={latest_cache_key}已执行/清理，等待新的/timestamps")
                
                # 兜底：新 id 到达时应直接执行。未命中缓存时用最近 timestamps 缓存的序列立即执行
                if gesture_seq is None and latest_cache_key is None and getattr(self, '_last_cached_gesture', None):
                    fallback_seq, fallback_dur, fallback_guess = self._last_cached_gesture
                    if fallback_seq and _cache_is_recent(getattr(self, "_last_cached_gesture_time", 0.0)):
                        gesture_seq = fallback_seq
                        speech_duration = fallback_dur
                        speech_start_guess = fallback_guess
                        print(f"[playid] [兜底] ID={play_id} 未命中缓存，使用最近序列立即执行 ({len(gesture_seq)}个手势)")
                    elif fallback_seq:
                        print(f"[playid] [等待] 最近序列缓存已过期，ID={play_id} 等待新的/timestamps")
                
                if gesture_seq is not None:
                    self.pending_play_ids.discard(play_id)
                    if cache_key in getattr(self, "_service_replay_play_ids", set()):
                        self.last_text_time = time.time()
                        if self.verbose:
                            print(f"[playid] [跳过] ID={play_id}, key={cache_key} 正在执行service后的恢复动作，不重复触发")
                        return
                    #  同一批 timestamps 只执行一次：若已执行过，则直接跳过，不再清理该批缓存，
                    #  让这一句话的缓存动作保留到执行线程结束时再删除
                    if cache_key in getattr(self, "_executed_batch_play_ids", set()):
                        self.last_text_time = time.time()
                        if self.verbose:
                            print(f"[playid] [跳过] ID={play_id}, key={cache_key} 已在本批执行过，不重复执行")
                        return
                    # 后台执行（不阻塞回调）。
                    # 时间基准以 /playid 到达为准，避免使用更早的估计值导致动作“提前于语音”。
                    base_wall = self.playid_recv_time.get(play_id)
                    # 可选补偿：若现场链路存在固定延迟，可通过环境变量整体后移动作起点（秒）
                    try:
                        sync_delay = float(os.environ.get("DH_GESTURE_SYNC_DELAY", "0.0"))
                    except Exception:
                        sync_delay = 0.0
                    if base_wall is None:
                        base_wall = time.time()
                    base_wall = float(base_wall) + sync_delay
                    current_batch_keys = getattr(self, '_current_batch_play_ids', set())
                    if cache_key in current_batch_keys:
                        self._executed_batch_play_ids = set(current_batch_keys)
                    else:
                        self._executed_batch_play_ids = {cache_key}
                    self._start_gesture_execution(
                        play_id, gesture_seq,
                        speech_start_wall=base_wall,
                        speech_duration=speech_duration
                    )
                else:
                    if self.verbose:
                        print(f"[playid] [警告] 未找到ID={play_id}的手势序列缓存，加入等待队列")
                        print(f"[playid] 当前缓存的ID: {list(self.gesture_cache.keys())}")
                    self.pending_play_ids.add(play_id)
                    
            except Exception as e:
                print(f"[playid] [错误] 处理playid时出错: {e}")
                import traceback
                traceback.print_exc()
                traceback.print_exc()
        
        #  订阅playid话题（注意：使用Int32类型，不是String）
        if ROS_VERSION == 2:
            qos_profile = QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE
            )
            node.create_subscription(RosInt32, "/playid", _play_id_callback, qos_profile)
            
            # 创建上肢动作服务
            def service_callback_wrapper(request, response):
                """服务回调包装器"""
                up_climb_request_type = request.up_limb_task_type
                all_success = True
                
                self._stop_idle_mode()
                self.last_text_time = time.time()
                # clear 后 conversation_ended=True 会导致 interrupt_flag 立即触发，service 动作被吞
                # service 进来时无条件重置，让动作能正常执行
                self.conversation_ended = False
                
                try:
                    if up_climb_request_type == 0:
                        node.get_logger().info("执行笛卡尔坐标系变化动作")
                        response.success = False
                        response.message = "笛卡尔坐标系变化动作未实现"
                        
                    elif up_climb_request_type == 1:
                        node.get_logger().info("执行关节变化动作")
                        response.success = False
                        response.message = "关节变化动作未实现"
                        
                    elif up_climb_request_type == 2:
                        node.get_logger().info("执行上肢预设动作变化")
                        
                        action_fixed = request.action_fixed
                        
                        # �� 动作0：回到初始位置。
                        # 默认不抢占已经启动的 timestamps 动作；确需强制归位时设置 DH_SERVICE_REST_FORCE=1。
                        if action_fixed == 0:
                            service_rest_force = bool(int(os.environ.get("DH_SERVICE_REST_FORCE", "0")))
                            if self._timestamp_pipeline_active() and not service_rest_force:
                                print("[service] [跳过] 时间戳动作正在执行/等待恢复，忽略 service 初始位置，避免打断后续时间戳动作")
                                response.success = True
                                response.message = "时间戳动作执行中，已忽略自动初始位置"
                                return response
                            # 1. 清空所有缓存和队列，抢占当前执行
                            self.conversation_ended = True
                            with self._exec_lock:
                                self._exec_token += 1
                            self.interrupt_all = True
                            self.interrupt_current = True
                            self.gesture_cache.clear()
                            self._latest_cache_key_by_play_id.clear()
                            self._cache_key_to_play_id.clear()
                            self.pending_play_ids.clear()
                            self._stop_idle_mode()
                            # 2. 等对话线程释放锁（最多 150ms）
                            time.sleep(0.15)
                            self.interrupt_all = False
                            self.interrupt_current = False
                            # 3. 执行 rest
                            rest_angles = self.gesture_policy.base_gestures.get(
                                'rest2', self.gesture_policy.base_gestures.get('rest', [0.0] * 12))
                            success = self.ros_publisher.publish_enhanced_sequence(
                                [{'gesture_name': 'rest2', 'duration': 1.0, 'joint_angles': rest_angles}],
                                fps=100, smooth_transitions=True, verbose=False,
                                speech_duration=None, interrupt_flag=None
                            )
                            # 4. 重置状态，立刻回复
                            self.conversation_ended = False
                            now = time.time()
                            self.last_text_time = now
                            self.last_action_finish_time = now
                            response.success = True if success else False
                            response.message = "初始位置执行成功" if success else "初始位置执行失败"
                            return response
                        
                        # 动作映射：从动作库中选择对应的手势序列
                        action_gesture_map = {
                            0: {  # 初始位置（兜底，正常走上面的快速路径）
                                "name": "初始位置",
                                "gestures": [{"gesture": "rest2", "duration": 1.0}]
                            },
                            1: {  # 左挥手动作序列
                                "name": "左挥手动作序列",
                                "gestures": [
                                    {"gesture": "wave_left_prepare", "duration": 1.2},       # �� 抬手到位并稳定：合并为1.2秒
                                    {"gesture": "wave_left_right", "duration": 1.2},         # �� 向右挥：1.2秒
                                    {"gesture": "wave_left_left", "duration": 1.2},          # �� 向左挥：1.2秒
                                    {"gesture": "wave_left_right", "duration": 1.2},         # �� 向右挥：1.2秒
                                    {"gesture": "wave_left_left", "duration": 1.2},          # �� 向左挥：1.2秒
                                    {"gesture": "wave_left_right", "duration": 1.2},         # �� 向右挥：1.2秒
                                    {"gesture": "rest2", "duration": 0.8},                    # �� 放下：0.8秒
                                    ]
                            },
                            2: {  # 右挥手动作序列
                                "name": "右挥手动作序列",
                                "gestures": [
                                    {"gesture": "wave_right_prepare", "duration": 1.2},      # �� 抬手到位并稳定：合并为1.2秒
                                    {"gesture": "wave_right_left", "duration": 1.2},         # �� 向左挥：1.2秒
                                    {"gesture": "wave_right_right", "duration": 1.2},        # �� 向右挥：1.2秒
                                    {"gesture": "wave_right_left", "duration": 1.2},         # �� 向左挥：1.2秒
                                    {"gesture": "wave_right_right", "duration": 1.2},        # �� 向右挥：1.2秒
                                    {"gesture": "wave_right_left", "duration": 1.2},         # �� 向左挥：1.2秒
                                    {"gesture": "rest2", "duration": 0.8},                    # �� 放下：0.8秒
                                    ]
                            },
                            3: {  # 左指引姿势
                                "name": "左指引姿势",
                                "gestures": [
                                    {"gesture": "present_left_grand", "duration": 1.0},
                                    {"gesture": "present_left_grand", "duration": 1.0},
                                    {"gesture": "present_left_grand", "duration": 1.0},
                                    {"gesture": "present_left_grand", "duration": 1.0},
                                    {"gesture": "rest2", "duration": 1.0}
                                ]
                            },
                            4: {  # 右指引姿势
                                "name": "右指引姿势",
                                "gestures": [
                                    {"gesture": "present_right_grand", "duration": 1.0},
                                    {"gesture": "present_right_grand", "duration": 1.0},
                                    {"gesture": "present_right_grand", "duration": 1.0},
                                    {"gesture": "present_right_grand", "duration": 1.0},
                                    {"gesture": "rest2", "duration": 1.0}
                                ]
                            },
                            5: {  # 左手握手姿势 - 创建左手镜像序列
                                "name": "左手握手姿势",
                                "gestures": [
                                    {"gesture": "handsshake_left", "duration": 3.0},                     # 放下
                                    {"gesture": "rest2", "duration": 0.6}                     # 放下
                                ]
                            },
                            6: {  # 右手握手姿势
                                "name": "右手握手姿势",
                                "gestures": [
                                    {"gesture": "handshake_extend", "duration": 1},        # 伸手 (0.6→0.9)
                                    {"gesture": "handshake_grip", "duration": 1.2},          # 握手 (0.8→1.2)
                                    {"gesture": "handshake_shake", "duration": 1.2},         # 轻摇 (0.6→0.9)
                                    {"gesture": "handshake_shake", "duration": 1.2},
                                    {"gesture": "handshake_shake", "duration": 1.2},
                                    {"gesture": "handshake_shake", "duration": 1.2},
                                    {"gesture": "rest2", "duration": 0.6},                    # 放下 (0.4→0.6)
                                ]

                            },
                        }
                        
                        action_info = action_gesture_map.get(action_fixed)
                        if action_info:
                            action_name = action_info["name"]
                            gestures = action_info["gestures"]
                            
                            node.get_logger().info(f"执行预设动作 {action_fixed}: {action_name}")
                            
                            if gestures:
                                service_can_interrupt = bool(int(os.environ.get("DH_SERVICE_CAN_INTERRUPT_TIMELINE", "0")))
                                if self._timestamp_pipeline_active() and not service_can_interrupt:
                                    print(f"[service] [跳过] 时间戳动作正在执行/等待恢复，忽略预设动作 {action_fixed}: {action_name}")
                                    response.success = True
                                    response.message = f"时间戳动作执行中，已忽略{action_name}"
                                    return response

                                # 从这一刻起，/playid 和 /timestamps 只能入队，不能抢跑。
                                self._service_action_running = True

                                # 标记为序列动作
                                for g in gestures:
                                    g['is_sequence_action'] = True

                                # 若 service 插入时已经有时间戳动作在播，先把当前 play_id 放回等待队列。
                                # 否则下面的抢占会停掉当前动作，但 service 完成后没有 pending 可恢复。
                                now_before_service = time.time()
                                active_play_id = getattr(self, "current_play_id", None)
                                active_cache_key = self._latest_cache_key_by_play_id.get(active_play_id)
                                if (
                                    active_play_id is not None
                                    and getattr(self, "_gesture_execution_running", False)
                                    and (
                                        active_cache_key in self.gesture_cache
                                        or getattr(self, "_last_cached_gesture", None)
                                    )
                                ):
                                    self.pending_play_ids.add(int(active_play_id))
                                    print(f"[service] 检测到时间戳动作正在执行，ID={active_play_id} 已重新加入等待队列")
                                
                                # 抢占当前正在执行的对话动作，避免卡在锁上等
                                with self._exec_lock:
                                    self._exec_token += 1
                                self.interrupt_all = True
                                self.interrupt_current = True
                                # 等对话线程检测到中断并释放锁（最多 150ms）
                                time.sleep(0.15)
                                self.interrupt_all = False
                                self.interrupt_current = False
                                
                                # 更新手指控制
                                if self.finger_controller:
                                    for g in gestures:
                                        try:
                                            self.finger_controller.update_gesture(
                                                g.get('gesture_name') or g.get('gesture', 'rest'),
                                                g.get('duration', 0.5)
                                            )
                                        except Exception:
                                            pass
                                
                                # 同步执行，完成后立刻回复；异常也必须清标志，否则后续 /playid 会永久等待
                                try:
                                    success = self.ros_publisher.publish_enhanced_sequence(
                                        gestures,
                                        fps=100,
                                        smooth_transitions=False,
                                        verbose=False,
                                        speech_duration=None,
                                        interrupt_flag=lambda: self.conversation_ended
                                    )
                                finally:
                                    self._service_action_running = False

                                # service 动作完成，用当前时刻作为新的语音基准触发 pending playid
                                now = time.time()
                                self.last_action_finish_time = now
                                self.last_text_time = now

                                def _fresh_pending_cache(pid, cached_obj):
                                    """play_id 可能复用，service 后只能用近期 timestamps 缓存。"""
                                    if cached_obj is None:
                                        return None
                                    try:
                                        max_age = float(os.environ.get(
                                            "DH_SERVICE_PENDING_CACHE_MAX_AGE",
                                            str(max(10.0, self.conversation_timeout))
                                        ))
                                    except Exception:
                                        max_age = max(10.0, self.conversation_timeout)
                                    cache_time = 0.0
                                    if isinstance(cached_obj, dict):
                                        cache_time = float(cached_obj.get("cache_time", 0.0) or 0.0)
                                    else:
                                        cache_time = float(getattr(self, "_last_cached_gesture_time", 0.0) or 0.0)
                                    if cache_time <= 0.0 or (now - cache_time) > max_age:
                                        print(
                                            f"[service] ID={pid} 的缓存过旧或缺少时间戳，继续等待新的/timestamps "
                                            f"(cache_age={now - cache_time if cache_time else -1:.2f}s, max={max_age:.1f}s)"
                                        )
                                        return None
                                    return cached_obj
                                
                                # 触发 service 执行期间积压的 playid（以当前时刻为语音基准，追帧对齐）
                                if self.pending_play_ids:
                                    pending = sorted(self.pending_play_ids)
                                    print(f"[service] service动作完成，触发积压的playid: {pending}")
                                    
                                    # 修复：同一批 timestamps 的 play_ids 共享相同手势序列，只需执行一次
                                    # 收集所有 pending 中属于当前批次的 play_ids
                                    current_batch_ids = getattr(self, '_current_batch_play_ids', set())
                                    pending_pairs = []
                                    for pid in pending:
                                        ck = self._latest_cache_key_by_play_id.get(pid, pid)
                                        pending_pairs.append((pid, ck))
                                    batch_pending = [(pid, ck) for pid, ck in pending_pairs if ck in current_batch_ids]
                                    other_pending = [(pid, ck) for pid, ck in pending_pairs if ck not in current_batch_ids]
                                    
                                    if batch_pending:
                                        # 使用批次中最小的 play_id 执行一次，整批都会被执行
                                        first_pid, first_key = sorted(batch_pending, key=lambda x: str(x[1]))[0]
                                        cached = self.gesture_cache.get(first_key)
                                        if cached is None and first_key == first_pid and getattr(self, '_last_cached_gesture', None):
                                            fallback_seq, fallback_dur, _ = self._last_cached_gesture
                                            cached = {
                                                'gestures': fallback_seq,
                                                'speech_duration': fallback_dur,
                                                'cache_time': getattr(self, "_last_cached_gesture_time", 0.0)
                                            }
                                        cached = _fresh_pending_cache(first_pid, cached)
                                        if cached is not None:
                                            gs = cached.get('gestures', cached) if isinstance(cached, dict) else cached
                                            sd = cached.get('speech_duration') if isinstance(cached, dict) else None
                                            
                                            # 标记整批已执行
                                            for pid, _ in batch_pending:
                                                self.pending_play_ids.discard(pid)
                                            batch_pending_keys = {ck for _, ck in batch_pending}
                                            self._executed_batch_play_ids = set(current_batch_ids) | batch_pending_keys
                                            self._service_replay_play_ids = set(batch_pending_keys)
                                            
                                            # 修复：service 完成后，清空所有动作的 start_offset，让它们从当前时刻开始依次执行
                                            # 根据 service 占用时间计算压缩比例，动态调整动作时长
                                            gs_copy = [dict(g) if isinstance(g, dict) else g for g in gs]
                                            
                                            # 计算 service 占用时间（从第一个 play_id 到达到现在）
                                            first_recv_time = min(self.playid_recv_time.get(pid, now) for pid, _ in batch_pending)
                                            service_delay = max(0, now - first_recv_time)
                                            
                                            # 计算原动作总时长
                                            orig_total_duration = sum(float(g.get('duration', 1.0) or 1.0) for g in gs_copy if isinstance(g, dict))
                                            
                                            # 计算压缩比例：如果 service 占用时间长，就多压缩一些
                                            # 目标：在剩余语音时间内完成所有动作
                                            remaining_speech = max(0, (sd or orig_total_duration) - service_delay)
                                            if remaining_speech > 0 and orig_total_duration > 0:
                                                # 压缩比例 = 剩余时间 / 原总时长，但至少保留 50% 时长避免动作太快
                                                compress_ratio = max(0.5, remaining_speech / orig_total_duration)
                                            else:
                                                compress_ratio = 0.7  # 默认压缩到 70%
                                            
                                            for g in gs_copy:
                                                if isinstance(g, dict):
                                                    g.pop('start_offset', None)  # 移除 start_offset，从当前开始
                                                    orig_dur = float(g.get('duration', 1.0) or 1.0)
                                                    # 根据 service 延迟动态压缩，但最少 0.4 秒保证动作可见
                                                    g['duration'] = max(0.4, orig_dur * compress_ratio)
                                            
                                            new_total = sum(g.get('duration', 0) for g in gs_copy if isinstance(g, dict))
                                            print(f"[service] 执行批次手势（动态压缩），覆盖 play_ids: {batch_pending}, "
                                                  f"service延迟={service_delay:.2f}s, 压缩比例={compress_ratio:.2f}, "
                                                  f"原总时长={orig_total_duration:.2f}s, 新总时长={new_total:.2f}s, 动作数={len(gs_copy)}")
                                            self._start_gesture_execution(first_pid, gs_copy, speech_start_wall=now, speech_duration=sd)
                                    
                                    # 处理不属于当前批次的孤立 pending（使用 fallback）
                                    # 注意：为了避免多个 _start_gesture_execution 互相中断，只执行第一个
                                    if other_pending:
                                        first_other, first_other_key = other_pending[0]
                                        cached = self.gesture_cache.get(first_other_key)
                                        if cached is None and first_other_key == first_other and getattr(self, '_last_cached_gesture', None):
                                            fallback_seq, fallback_dur, _ = self._last_cached_gesture
                                            cached = {
                                                'gestures': fallback_seq,
                                                'speech_duration': fallback_dur,
                                                'cache_time': getattr(self, "_last_cached_gesture_time", 0.0)
                                            }
                                        cached = _fresh_pending_cache(first_other, cached)
                                        if cached is not None:
                                            gs = cached.get('gestures', cached) if isinstance(cached, dict) else cached
                                            sd = cached.get('speech_duration') if isinstance(cached, dict) else None
                                            
                                            # 清空所有 other_pending（避免重复执行）
                                            for pid, _ in other_pending:
                                                self.pending_play_ids.discard(pid)
                                            other_pending_keys = {ck for _, ck in other_pending}
                                            self._executed_batch_play_ids = set(getattr(self, '_current_batch_play_ids', set())) | other_pending_keys
                                            self._service_replay_play_ids = set(other_pending_keys)
                                            
                                            # 同样修复：根据 service 延迟动态压缩
                                            gs_copy = [dict(g) if isinstance(g, dict) else g for g in gs]
                                            
                                            # 计算 service 占用时间
                                            other_recv_time = self.playid_recv_time.get(first_other, now)
                                            service_delay = max(0, now - other_recv_time)
                                            
                                            orig_total_duration = sum(float(g.get('duration', 1.0) or 1.0) for g in gs_copy if isinstance(g, dict))
                                            remaining_speech = max(0, (sd or orig_total_duration) - service_delay)
                                            if remaining_speech > 0 and orig_total_duration > 0:
                                                compress_ratio = max(0.5, remaining_speech / orig_total_duration)
                                            else:
                                                compress_ratio = 0.7
                                            
                                            for g in gs_copy:
                                                if isinstance(g, dict):
                                                    g.pop('start_offset', None)
                                                    orig_dur = float(g.get('duration', 1.0) or 1.0)
                                                    g['duration'] = max(0.4, orig_dur * compress_ratio)
                                            
                                            new_total = sum(g.get('duration', 0) for g in gs_copy if isinstance(g, dict))
                                            print(f"[service] 执行孤立手势（动态压缩），覆盖 play_ids: {other_pending}, "
                                                  f"service延迟={service_delay:.2f}s, 压缩比例={compress_ratio:.2f}, "
                                                  f"原总时长={orig_total_duration:.2f}s, 新总时长={new_total:.2f}s, 动作数={len(gs_copy)}")
                                            self._start_gesture_execution(first_other, gs_copy, speech_start_wall=now, speech_duration=sd)

                                response.success = True if success else False
                                response.message = f"{action_name}执行成功" if success else f"{action_name}执行失败"
                                return response
                            else:
                                response.success = False
                                response.message = f"{action_name}手势序列为空"
                        else:
                            node.get_logger().warn(f"无效的预设动作类型: {action_fixed}")
                            response.success = False
                            response.message = "无效的预设动作类型"
                            
                    else:
                        node.get_logger().warn(f"无效的任务类型: {up_climb_request_type}")
                        response.success = False
                        response.message = "无效的任务类型"
                        
                except Exception as e:
                    self._service_action_running = False
                    node.get_logger().error(f"服务回调异常: {e}")
                    import traceback
                    traceback.print_exc()
                    response.success = False
                    response.message = f"执行失败: {str(e)}"
                    
                return response
            
            node.create_service(UpLimb, 'up_climb_srv', service_callback_wrapper)
            print("[service] [OK] 已创建 up_climb_srv 服务 (ROS2)")
            
        else:
            rospy.Subscriber("/playid", RosInt32, _play_id_callback, queue_size=10)
        print(f"[playid] [订阅] 已订阅 /playid 话题 (Int32类型, ROS{ROS_VERSION})")
        
        # ========== 双模式状态机：辅助方法 ==========
        def _update_mode_state():
            """更新当前模式状态（优先级：TIMESTAMP > SOUND > IDLE）"""
            now = time.time()
            
            # 检查是否仍在时间戳模式（最近收到过timestamps）
            if now - self._last_timestamp_recv_time < self._timestamp_timeout:
                if self._mode_state != "TIMESTAMP":
                    print(f"[mode] 切换到 TIMESTAMP 模式 (最近收到timestamps)")
                    self._mode_state = "TIMESTAMP"
                    # 停止sound_detected动作
                    self._stop_sound_action()
                    self._stop_idle_mode()
                return "TIMESTAMP"
            
            # 检查是否进入sound_detected模式
            if self._sound_detected_flag:
                self._last_sound_true_time = now
                if self._mode_state != "SOUND":
                    print(f"[mode] 切换到 SOUND 模式 (sound_detected=True)")
                    self._mode_state = "SOUND"
                    # 从待机模式唤醒
                    self._stop_idle_mode()
                    # 立即执行一次随机动作
                    self._trigger_sound_action()
                return "SOUND"
            
            # 检查是否保持在SOUND模式（sound_detected刚变false，等待一段时间）
            if self._mode_state == "SOUND":
                time_since_sound = now - self._last_sound_true_time
                if time_since_sound < self._sound_to_idle_delay:
                    return "SOUND"
                else:
                    if self._timestamp_pipeline_active():
                        return self._mode_state
                    print(f"[mode] 从 SOUND 切换到 IDLE (sound_detected=false已{time_since_sound:.1f}s)")
                    self._mode_state = "IDLE"
                    # 回到初始位置
                    self._return_to_rest_position()
                    return "IDLE"
            
            # 默认进入IDLE模式
            if self._mode_state != "IDLE":
                if self._timestamp_pipeline_active():
                    return self._mode_state
                print(f"[mode] 切换到 IDLE 模式")
                self._mode_state = "IDLE"
                # 回到初始位置
                self._return_to_rest_position()
            return "IDLE"
        
        def _stop_sound_action():
            """停止sound_detected模式的随机动作"""
            if self._sound_action_executing:
                # print("[sound] 停止sound_detected随机动作")
                self.interrupt_all = True
                self.interrupt_current = True
                self._sound_action_executing = False
        
        def _trigger_sound_action(force=False):
            """触发一次sound_detected模式的随机动作
            
            Args:
                force: 为True时跳过间隔和执行中检查，立即触发（用于false->true转换）
            """
            import threading
            import random
            
            now = time.time()
            # 检查动作间隔（force模式跳过）
            elapsed = now - self._last_sound_action_time
            if not force and elapsed < self._sound_action_interval:
                print(f"[sound] [{now:.3f}] 跳过触发，间隔{elapsed:.2f}s < {self._sound_action_interval}s")
                return
            
            if not force and self._sound_action_executing:
                print(f"[sound] [{now:.3f}] 跳过触发，当前有动作正在执行")
                return
            
            # �� 修复：force模式下，先中断旧动作再启动新的
            if force and self._sound_action_executing:
                # print(f"[sound] [{now:.3f}] 强制触发：中断旧动作，立即启动新动作")
                self.interrupt_all = True
                self.interrupt_current = True
                self._sound_action_executing = False
                # 不sleep，直接继续，新线程启动时旧线程会在下一帧检测到中断
            
            # print(f"[sound] [{now:.3f}] 触发新动作 (间隔{elapsed:.2f}s, force={force})")
            
            self._last_sound_action_time = now
            self._sound_action_executing = True
            self.interrupt_all = False
            self.interrupt_current = False
            
            def _execute_random_action():
                try:
                    start_time = time.time()
                    # 关键：更新last_text_time，防止被idle检测误判为空闲
                    self.last_text_time = start_time
                    
                    # 选择随机动作
                    action = random.choice(self._sound_action_candidates)
                    gesture_name = action["gesture"]
                    duration = action["duration"]
                    
                    # ⏱️ 打印从收到true到动作开始执行的耗时
                    # t0 = getattr(self, "_sound_true_recv_time", None)
                    # if t0:
                    #     elapsed_since_true = start_time - t0
                    #     # print(f"[sound] ⏱️  [T+{elapsed_since_true:.3f}s] 动作开始执行: {gesture_name} ({duration}s)")
                    # else:
                    #     print(f"[sound] [{start_time:.3f}] 开始执行随机动作: {gesture_name} ({duration}s)")
                    
                    # 获取关节角度
                    angles = self.gesture_policy.base_gestures.get(gesture_name, [0.0] * 12)
                    gesture = {
                        "gesture_name": gesture_name,
                        "gesture": gesture_name,
                        "duration": duration,
                        "joint_angles": angles
                    }
                    
                    # 执行动作（可中断）
                    self.ros_publisher.publish_enhanced_sequence(
                        [gesture],
                        fps=100,
                        smooth_transitions=True,
                        verbose=False,
                        speech_duration=None,
                        interrupt_flag=lambda: not self._sound_action_executing or self.interrupt_all
                    )
                        
                except Exception as e:
                    print(f"[sound] 执行随机动作失败: {e}")
                finally:
                    self._sound_action_executing = False
                    # 关键：如果仍在SOUND模式且sound=true，立即触发下一个动作
                    # 不依赖主循环的1Hz检测，实现连续动作
                    if self._mode_state == "SOUND" and self._sound_detected_flag:
                        # 检查间隔是否满足
                        elapsed = time.time() - self._last_sound_action_time
                        if elapsed >= self._sound_action_interval:
                            # print(f"[sound] [{time.time():.3f}] 动作完成，立即触发下一个 (间隔{elapsed:.2f}s)")
                            _trigger_sound_action()
            
            self._sound_action_thread = threading.Thread(target=_execute_random_action, daemon=True)
            self._sound_action_thread.start()
        
        def _end_timestamp_conversation_from_sound_false(false_time=None):
            """sound_detected 持续 false 后，结束本轮 timestamps 会话并清理固定 play_id 的旧时间基准。"""
            # 若期间又收到过 true，说明声音又来了，不结束本轮会话
            if false_time is not None:
                last_true = getattr(self, '_last_sound_true_time', 0.0)
                if last_true > false_time:
                    return False
            if self._sound_detected_flag:
                return False

            had_timestamp_state = (
                self._mode_state == "TIMESTAMP"
                or self._timestamp_pipeline_active()
                or bool(self.playid_recv_time)
                or bool(self.gesture_cache)
            )

            self.conversation_ended = True
            with self._exec_lock:
                self._exec_token += 1
            self.interrupt_all = True
            self.interrupt_current = True
            self._service_replay_play_ids = set()
            self._executed_batch_play_ids = set()
            self._current_batch_play_ids = set()
            self.gesture_cache.clear()
            self._latest_cache_key_by_play_id.clear()
            self._cache_key_to_play_id.clear()
            self.pending_play_ids.clear()
            self.playid_recv_time.clear()
            self.current_play_id = None
            self.conversation_start_playid = None
            self.conversation_start_wall = None
            self.last_playid_wall = 0.0
            self._last_cached_gesture = None
            self._last_cached_gesture_time = 0.0
            self._block_timestamps_until_next_start = True
            self.current_gesture_end_time = 0
            self._mode_state = "IDLE"
            self._return_to_rest_position(from_clear=True, force=True)
            if had_timestamp_state:
                print("[sound] 连续false超时，已结束时间戳会话并清理旧play_id基准")
            return True

        def _sound_detected_callback(msg):
            """处理sound_detected消息 - 回调触发，实时响应"""
            try:
                new_flag = bool(msg.data)
                prev_flag = self._sound_detected_flag
                self._sound_detected_flag = new_flag
                
                # true -> false 转换：记录 false 时刻，持续 false 后结束本轮 timestamps 会话
                if prev_flag and not new_flag:
                    # print("[sound] 检测到声音结束，准备回到初始位置...")
                    false_time = time.time()
                    self._last_sound_false_time = false_time  # 记录本次 false 时刻
                    try:
                        false_delay = max(0.1, float(os.environ.get("DH_SOUND_FALSE_END_DELAY", "1.5")))
                    except Exception:
                        false_delay = 1.5
                    # 启动定时器，持续 false 后检查：若期间又收到 true 则取消
                    def _make_timeout(ft):
                        def _cb():
                            _on_sound_false_timeout(ft)
                        return _cb
                    threading.Timer(false_delay, _make_timeout(false_time)).start()
                    return
                
                # true 状态：立即停止待机，进入对话（不限于边沿，只要收到true且在idle就响应）
                if new_flag:
                    recv_time = time.time()
                    self._block_timestamps_until_next_start = False
                    self._last_sound_true_time = recv_time
                    self.last_text_time = recv_time
                    # �� 关键修复：不管是边沿还是持续true，只要在idle模式就立刻停止
                    if self.is_idle:
                        # print(f"[sound] ⏱️  [T+0.000s] 收到true，立即停止待机模式 (wall={recv_time:.3f})")
                        self._stop_idle_mode()
                        self._sound_true_recv_time = recv_time  # 记录用于后续计时
                    # if not prev_flag:
                    #     print(f"[sound] [{recv_time:.3f}] 检测到声音开始 (false->true)")
                    # 立即进入SOUND模式并执行动作
                    if self._mode_state != "TIMESTAMP":
                        self._mode_state = "SOUND"
                        if not prev_flag:
                            # false->true 边沿：强制立即触发
                            self._last_sound_action_time = 0.0
                            _trigger_sound_action(force=True)
                        
            except Exception as e:
                print(f"[sound] 处理sound_detected失败: {e}")
        
        def _on_sound_false_timeout(false_time=None):
            """sound_detected=false持续一段时间后执行：若期间又收到 true 则取消，否则结束会话并回初始位置。"""
            try:
                _end_timestamp_conversation_from_sound_false(false_time)
            except Exception as e:
                print(f"[sound] 回到初始位置失败: {e}")
        
        # 订阅 /sound_detected 话题
        try:
            from std_msgs.msg import Bool as RosBool
            if ROS_VERSION == 2:
                sound_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
                node.create_subscription(RosBool, "/sound_detected", _sound_detected_callback, sound_qos)
            else:
                rospy.Subscriber("/sound_detected", RosBool, _sound_detected_callback, queue_size=10)
            print("[sound] [订阅] 已订阅 /sound_detected 话题")
        except Exception as e:
            print(f"[sound] [警告] 订阅 /sound_detected 失败: {e}")
        # ======================================
        
        def _cb(msg: RosString):
            """处理timestamps消息，生成并缓存手势序列"""
            try:
                raw = getattr(msg, "data", None)
                if raw is None:
                    return
                if not isinstance(raw, str):
                    raw = str(raw)
                raw = raw.strip()
                if not raw:
                    return
                
                # 先检查纯字符串 clear（上游直接发 "clear" 而不是 JSON）
                if raw.lower() == "clear":
                    print("[clear] 收到清除指令")
                    self.conversation_ended = True
                    with self._exec_lock:
                        self._exec_token += 1
                    self.interrupt_all = True
                    self.interrupt_current = True
                    self.gesture_cache.clear()
                    self._latest_cache_key_by_play_id.clear()
                    self._cache_key_to_play_id.clear()
                    self.pending_play_ids.clear()
                    self._return_to_rest_position(from_clear=True)
                    return
                
                payload = json.loads(raw)
                if isinstance(payload, str):
                    payload = json.loads(payload)
            except Exception as e:
                # 避免刷屏：仅在 verbose 时打印截断内容
                if self.verbose:
                    trunc = ""
                    try:
                        trunc = raw[:60] + ("..." if len(raw) > 60 else "")
                    except Exception:
                        trunc = ""
                    print(f"[timestamps] [错误] JSON解析失败: {e}, raw='{trunc}'")
                else:
                    print(f"[timestamps] [错误] JSON解析失败: {e}")
                return

            payload_has_clear = False
            try:
                if isinstance(payload, dict):
                    payload_has_clear = payload.get('clear') is True
                elif isinstance(payload, list):
                    payload_has_clear = any(isinstance(x, dict) and x.get('clear') is True for x in payload)
            except Exception:
                payload_has_clear = False

            if getattr(self, "_block_timestamps_until_next_start", False) and not payload_has_clear:
                if self.verbose:
                    print("[timestamps] [忽略] sound_detected=false已结束上一轮，会话未重新开始，丢弃迟到timestamps")
                return
            
            # ========== 双模式状态机：更新时间戳接收时间，切换到 TIMESTAMP 模式 ==========
            self._last_timestamp_recv_time = time.time()
            if self._mode_state != "TIMESTAMP":
                self._mode_state = "TIMESTAMP"
            # ======================================================
            
            # 检查是否是清除消息
            if isinstance(payload, dict) and payload.get('clear') is True:
                print("[timestamps] [清除] 收到清除指令，对话结束")
                self.conversation_ended = True
                with self._exec_lock:
                    self._exec_token += 1
                self.interrupt_all = True
                self.interrupt_current = True
                self.gesture_cache.clear()
                self._latest_cache_key_by_play_id.clear()
                self._cache_key_to_play_id.clear()
                self.pending_play_ids.clear()
                self._return_to_rest_position(from_clear=True)
                return
                
            items = payload if isinstance(payload, list) else [payload]
            if not items:
                print("[timestamps] [警告] 收到空消息或结构不符")
                return
                
            # 检查items中是否有clear标记
            for item in items[:]:
                if isinstance(item, dict) and item.get('clear') is True:
                    print("[timestamps] [清除] 检测到清除标记，对话结束")
                    #  设置对话结束标志，不再执行填充动作
                    self.conversation_ended = True
                    with self._exec_lock:
                        self._exec_token += 1
                    self.interrupt_all = True
                    self.interrupt_current = True
                    self.gesture_cache.clear()
                    self._latest_cache_key_by_play_id.clear()
                    self._cache_key_to_play_id.clear()
                    self.pending_play_ids.clear()
                    items.remove(item)
                    self._return_to_rest_position(from_clear=True)
                    
            if not items:
                return
            
            #  处理每个句子，生成并缓存手势序列
            if self.verbose:
                print(f"\n[timestamps] [接收] 收到 {len(items)} 个句子的timestamps数据")
            
            #  检测是否是新的一段话（距离上次timestamps超过conversation_timeout秒）
            current_time = time.time()
            time_since_last = current_time - self.last_timestamps_time
            
            if self.last_timestamps_time > 0 and time_since_last > self.conversation_timeout:
                #  新的一段话到来，这是真正的新对话
                print(f"[timestamps] [停止] 检测到新对话（距上次{time_since_last:.1f}s）")
                
                # ⚠️ 按你的要求：除非收到 clear 指令，否则不要清除缓存的动作序列。
                # 因此这里不再根据时间间隔去删除或裁剪 self.gesture_cache，
                # 仅更新对话状态标记，由 /clear 消息负责真正的清理。
                if time_since_last > 30.0:
                    self.current_gesture_end_time = 0
                    # 若最近有 play_id 到达（用户一直在说），说明是慢 timestamps 而非真正新会话，不清空 pending
                    time_since_last_playid = current_time - getattr(self, 'last_playid_wall', 0.0)
                    if time_since_last_playid < 30.0 and self.pending_play_ids:
                        print(f"[timestamps] [新] 距上次>30s，但最近{time_since_last_playid:.1f}s内有play_id，视为同一会话，保留pending: {sorted(self.pending_play_ids)}")
                    elif self.pending_play_ids:
                        cleared = sorted(self.pending_play_ids)
                        self.pending_play_ids.clear()
                        print(f"[timestamps] [新] 新会话开始（距上次>30s且无近期play_id），清空过期pending: {cleared}，保留历史缓存，仅重置对话状态")
                    else:
                        print("[timestamps] [新] 新会话开始（距上次>30s），保留历史缓存，仅重置对话状态")
                else:
                    print(f"[timestamps] [新] 新对话开始（距上次{time_since_last:.1f}s），保留缓存和动作")
                
                #  新对话开始，重置标志（但不断中断动作，除非是全新会话）
                self.conversation_ended = False
                self.executed_gesture_ids.clear()  # 清空已执行标记
            else:
                print(f"[timestamps] ->  同一段话的句子（距上次{time_since_last:.1f}s）")
                #  如果对话已结束，不处理后续句子的填充动作
                if self.conversation_ended:
                    print("[timestamps] [警告] 对话已结束，但仍在处理同一段话的句子")
            
            #  更新最后timestamps时间
            self.last_timestamps_time = current_time
            
            #  收到文本，更新时间并停止待机模式
            # 注意：不在这里重置 conversation_ended，clear 处理已在上方 return，
            # 若走到这里说明本条消息不是 clear，但也不能无条件覆盖（防止 clear 与
            # 下一条 timestamps 竞争时被抹掉）。只有确认是正常内容消息才重置。
            if not self.conversation_ended:
                pass  # 已经是 False，无需操作
            else:
                # 走到这里说明 clear 之后又来了新的正常 timestamps，视为新对话开始
                self.conversation_ended = False
            self.last_text_time = time.time()
            self._stop_idle_mode()
            
            #  新架构：基于时间轴的智能对齐
            if self.verbose:
                print("[timestamps] 使用时间轴智能对齐：考虑动作溢出")
            
            # 第一步：收集所有句子信息
            all_sentences = []
            total_duration = 0.0
            current_ts_play_ids = set()

            for idx, utt in enumerate(items):
                if not isinstance(utt, dict):
                    continue

                # 提取play_id
                play_id = utt.get('id') or utt.get('play_id') or utt.get('sentence_id')
                if play_id is None:
                    print(f"[timestamps] [警告] 第{idx+1}个句子缺少ID，跳过")
                    continue

                try:
                    play_id = int(play_id)
                except:
                    print(f"[timestamps] [警告] 第{idx+1}个句子ID格式错误: {play_id}")
                    continue

                current_ts_play_ids.add(play_id)

                # 兼容多种timestamps格式：
                # 1) 顶层直接包含 words: [{word, start_time, end_time, ...}, ...] # 2) 顶层包含 timestamps: {words: [...], phonemes: [...]}
                words = utt.get('words')
                if not words:
                    ts = utt.get('timestamps')
                    if isinstance(ts, dict):
                        words = ts.get('words', [])
                if not isinstance(words, list):
                    words = []
                if not words:
                    print(f"[timestamps] [警告] ID={play_id} 未找到words字段或为空，跳过")
                    continue

                # 统一字段名称：兼容你当前 /timestamps 新格式（text/begin_time/end_time，且begin/end是毫秒）
                norm_words = []
                has_begin_time = False
                try:
                    has_begin_time = any(isinstance(w, dict) and ('begin_time' in w) for w in words)
                except Exception:
                    has_begin_time = False
                for w in words:
                    if not isinstance(w, dict):
                        continue
                    ww = dict(w)
                    # 文本字段兼容：新格式用 text，旧格式用 word
                    if 'word' not in ww and 'text' in ww:
                        ww['word'] = ww.get('text', '')
                    if 'start_time' not in ww and 'startTime' in ww:
                        ww['start_time'] = ww.get('startTime')
                    if 'end_time' not in ww and 'endTime' in ww:
                        ww['end_time'] = ww.get('endTime')
                    # 新格式：begin_time/end_time（毫秒） -> start_time/end_time（秒）
                    if has_begin_time:
                        if 'start_time' not in ww and 'begin_time' in ww:
                            try:
                                ww['start_time'] = float(ww.get('begin_time', 0.0)) / 1000.0
                            except Exception:
                                ww['start_time'] = 0.0
                        if 'end_time' in ww:
                            try:
                                ww['end_time'] = float(ww.get('end_time', 0.0)) / 1000.0
                            except Exception:
                                ww['end_time'] = 0.0
                    norm_words.append(ww)

                # 提取文本和时长（使用规范化后的字段）
                utter_text = ''.join(str(w.get('word', '')) for w in norm_words)
                starts = [_to_float(w.get('start_time', 0.0)) for w in norm_words]
                ends = [_to_float(w.get('end_time', 0.0)) for w in norm_words]
                if not ends:
                    print(f"[timestamps] [警告] ID={play_id} 未提供end_time，跳过")
                    continue

                sentence_dur = max(0.0, max(ends) - (min(starts) if starts else 0.0))

                all_sentences.append({
                    'play_id': play_id,
                    'text': utter_text,
                    'duration': sentence_dur,
                    'words_ts': norm_words,
                    'start_time': total_duration,
                    'end_time': total_duration + sentence_dur
                })

                total_duration += sentence_dur
                if self.verbose:
                    print(f"[timestamps] [日志] 句子{idx+1} ID={play_id}: {utter_text[:30]}... (时长: {sentence_dur:.2f}s)")

            if not all_sentences:
                print("[timestamps] [警告] 没有有效的句子数据")
                for pid in current_ts_play_ids:
                    self.pending_play_ids.discard(pid)
                self.interrupt_all = False
                self.interrupt_current = False
                if self._sound_detected_flag:
                    if self._mode_state != "SOUND":
                        print("[mode] 时间戳无有效数据，切换到 SOUND 模式")
                        self._mode_state = "SOUND"
                else:
                    if self._mode_state != "IDLE":
                        print("[mode] 时间戳无有效数据且无声音，切换到 IDLE 模式")
                        self._mode_state = "IDLE"
                return
            
            if self.verbose:
                print(f"[timestamps] [计时] 总时长: {total_duration:.2f}s")
            
            # 第二步：检测所有序列动作
            sequence_actions_info = []
            for idx, sentence in enumerate(all_sentences):
                detected_actions = self.text_processor.extract_actions(sentence['text'])
                if detected_actions:
                    print(f"[timestamps] [动作] 句子{idx+1} 检测到动作: {detected_actions}")
                    for action in detected_actions:
                        action_dur = self._get_sequence_action_duration(action)
                        if action_dur > 0:
                            sequence_actions_info.append({
                                'action': action,
                                'duration': action_dur,
                                'sentence_idx': idx
                            })
                            print(f"[timestamps] → 序列动作 '{action}' 时长: {action_dur:.2f}s")
            
            sequence_total_duration = sum(a['duration'] for a in sequence_actions_info)
            remaining_time = total_duration - sequence_total_duration
            if self.verbose:
                print(f"[timestamps] [统计] 序列动作总时长: {sequence_total_duration:.2f}s")
                print(f"[timestamps] [计时] 剩余时间: {remaining_time:.2f}s")
            
            # 第三步：生成完整手势序列
            full_text = ''.join(s['text'] for s in all_sentences)
            # 将每句的 word-level 时间戳拼到同一条时间轴上（用于韵律/对齐）
            # 注意：当 /timestamps 会晚到时，系统主要通过“追帧对齐”(playid基准)来补偿延迟；
            #  优化：增大默认 LEAD_OFFSET，让动作更快响应，减少"动作比语音慢"的问题
            # ROS2 相比 ROS1 可能有额外的延迟，需要更大的提前量
            # 支持环境变量动态调参：export DH_LEAD_OFFSET=0.30
            LEAD_OFFSET = float(os.environ.get("DH_LEAD_OFFSET", "0.20"))  # 恢复为0.20，与ROS1对齐
            merged_timestamps = []
            for s in all_sentences:
                base = float(s.get('start_time', 0.0) or 0.0)
                for w in (s.get('words_ts') or []):
                    if not isinstance(w, dict):
                        continue
                    ww = dict(w)
                    try:
                        st = base + _to_float(ww.get('start_time', 0.0)) - LEAD_OFFSET
                        et = base + _to_float(ww.get('end_time', 0.0)) - LEAD_OFFSET
                        # 不允许出现负时间
                        ww['start_time'] = max(0.0, st)
                        ww['end_time'] = max(ww['start_time'], et)
                    except Exception:
                        # 保底：不做偏移
                        pass
                    merged_timestamps.append(ww)
            
            try:
                sem = self.text_processor.process(full_text)
                sem['utterance_text'] = full_text
                sem['speech_duration'] = total_duration
                sem['end_settle'] = 'never'
                sem['flow_mode'] = True
                # timestamps 模式：让手势规划使用 word-level 时间戳做对齐
                sem['timestamps_mode'] = True
                sem['timestamps'] = merged_timestamps
                # timestamps 输入下，启用语言驱动模式，让 EnhancedGesturePolicy 使用 sem['timestamps'] 做韵律/时间轴对齐
                sem['enable_linguistic_mode'] = True
                
                full_gesture_seq = self.gesture_policy.plan_gesture_sequence(sem)
                if self.verbose:
                    print(f"[timestamps] [动作] 生成手势总数: {len(full_gesture_seq)}")
                
                # 第四步：分离并删减
                sequence_gestures = [g for g in full_gesture_seq if g.get('is_sequence_action', False)]
                filler_gestures = [g for g in full_gesture_seq if not g.get('is_sequence_action', False)]
                
                # 关键修复：对填充动作去重，避免连续相同的动作
                # 同时检查 gesture_name 和 gesture 字段
                deduplicated_fillers = []
                last_gesture_name = None
                consecutive_count = 0
                # 连续相同动作限制（可调）。值越大，动作“存在感”越强。
                try:
                    max_consecutive = max(1, int(os.environ.get("DH_FILLER_MAX_CONSECUTIVE", "4")))
                except Exception:
                    max_consecutive = 4
                
                for g in filler_gestures:
                    gesture_name = g.get('gesture_name') or g.get('gesture', '')
                    
                    # 如果与上一个动作相同，检查连续次数
                    if gesture_name == last_gesture_name:
                        consecutive_count += 1
                        # 如果连续次数超过限制，跳过这个动作
                        if consecutive_count >= max_consecutive:
                            if self.verbose:
                                print(f"[timestamps] [跳过] 跳过连续第{consecutive_count+1}个相同动作: {gesture_name}")
                            continue
                    else:
                        consecutive_count = 0
                    
                    deduplicated_fillers.append(g)
                    last_gesture_name = gesture_name
                
                # 统计去重效果
                removed_count = len(filler_gestures) - len(deduplicated_fillers)
                if removed_count > 0:
                    print(f"[timestamps] [去重] 填充动作去重: {len(filler_gestures)} -> {len(deduplicated_fillers)}个 (移除{removed_count}个重复)")
                
                # 如果去重后动作太少（<3个），且原始列表>=10个，说明重复太多，需要重新生成
                if len(deduplicated_fillers) < 3 and len(filler_gestures) >= 10:
                    print(f"[timestamps] [警告] 去重后动作太少({len(deduplicated_fillers)}个)，原始有{len(filler_gestures)}个，说明重复严重")
                    # 保留去重后的结果，不要用重复的
                    filler_gestures = deduplicated_fillers
                else:
                    filler_gestures = deduplicated_fillers
                
                if self.verbose:
                    print(f"[timestamps] [统计] 序列动作: {len(sequence_gestures)}个")
                    print(f"[timestamps] [统计] 填充动作: {len(filler_gestures)}个")
                
                final_gesture_seq = []
                seq_duration = sum(g.get('duration', 0) for g in sequence_gestures)
                filler_duration = sum(g.get('duration', 0) for g in filler_gestures)
                
                print(f"[timestamps] [统计] 序列动作: {len(sequence_gestures)}个 (时长: {seq_duration:.2f}s)")
                print(f"[timestamps] [统计] 填充动作: {len(filler_gestures)}个 (时长: {filler_duration:.2f}s)")
                print(f"[timestamps] [对比] 语音总时长: {total_duration:.2f}s, 填充动作总时长: {filler_duration:.2f}s, 差值: {total_duration - filler_duration:.2f}s")
                
                if sequence_gestures:
                    # [OK] 按你的要求：序列动作必须完整执行（即使会超过单句语音时长）
                    print(f"[timestamps] [OK] 检测到序列动作，必须完整执行")
                    final_gesture_seq = sequence_gestures.copy()
                    # 只在序列动作放得下时才添加填充，避免"超时还塞填充"进一步拖尾
                    remaining_time = float(total_duration or 0.0) - float(seq_duration or 0.0)
                    if remaining_time > 0 and filler_gestures:
                        acc_time = 0.0
                        for g in filler_gestures:
                            g_dur = float(g.get('duration', 0.0) or 0.0)
                            #  恢复ROS1逻辑：不过滤，保留所有动作，确保动作丰富
                            # 不过滤短动作，让手势规划系统决定动作数量
                            # if g_dur < 0.6:
                            #     continue
                            if acc_time + g_dur <= remaining_time:
                                final_gesture_seq.append(g)
                                acc_time += g_dur
                            else:
                                break
                else:
                    #  没有序列动作：优先保留重要动作，然后填充其他动作
                    print(f"[timestamps] [日志] 无序列动作，执行填充动作")
                    
                    # 分离重要动作和普通填充动作
                    important_fillers = []
                    normal_fillers = []
                    
                    for g in filler_gestures:
                        if self._is_important_action(g.get('gesture_name', '')):
                            important_fillers.append(g)
                        else:
                            normal_fillers.append(g)
                    
                    print(f"[timestamps] 重要动作: {len(important_fillers)}个, 普通填充: {len(normal_fillers)}个")
                    
                    # 优先添加重要动作
                    acc_time = 0.0
                    for g in important_fillers:
                        g_dur = float(g.get('duration', 0) or 0.0)
                        #  恢复ROS1逻辑：不过滤重要动作，保留所有动作
                        # 不过滤短动作，让手势规划系统决定动作数量
                        # if g_dur < 0.5:
                        #     continue
                        if acc_time + g_dur <= total_duration:
                            final_gesture_seq.append(g)
                            acc_time += g_dur
                        else:
                            # 即使超时，也至少保留一个重要动作（但必须是够长的动作）
                            # 最低保留时长阈值可调，降低后可避免“重要动作被过度削弱”
                            try:
                                important_min_keep = float(os.environ.get("DH_IMPORTANT_MIN_KEEP", "0.25"))
                            except Exception:
                                important_min_keep = 0.25
                            if len(final_gesture_seq) == 0 and g_dur >= important_min_keep:
                                final_gesture_seq.append(g)
                                acc_time += g_dur
                                print(f"[timestamps] [警告] 重要动作超时，但仍保留: {g.get('gesture_name')}")
                            break
                    
                    # 剩余时间添加普通填充动作
                    #  恢复ROS1逻辑：尽量填满语音时长，不过度过滤，确保动作丰富
                    for g in normal_fillers:
                        g_dur = float(g.get('duration', 0) or 0.0)
                        #  恢复ROS1逻辑：不过滤短动作，让所有动作都参与排程
                        # 只检查是否超时，如果超时但剩余时间还很多，也添加
                        if acc_time + g_dur <= total_duration:
                            final_gesture_seq.append(g)
                            acc_time += g_dur
                        else:
                            # 不得为「填满名义时长」再追加已超时的手势（真实语音已结束却仍多播 2～3 个的主因之一）
                            break
                    
                    #  关键修复：如果所有动作都被过滤掉了，至少保留一个最长的动作（避免0个手势导致抖动）
                    if len(final_gesture_seq) == 0 and (important_fillers or normal_fillers):
                        # 从所有填充动作中选择最长的（但至少0.6秒）
                        all_candidates = important_fillers + normal_fillers
                        if all_candidates:
                            # 按时长排序，选择最长的
                            all_candidates.sort(key=lambda x: float(x.get('duration', 0) or 0.0), reverse=True)
                            for candidate in all_candidates:
                                cand_dur = float(candidate.get('duration', 0) or 0.0)
                                try:
                                    fallback_min_keep = float(os.environ.get("DH_FALLBACK_MIN_KEEP", "0.25"))
                                except Exception:
                                    fallback_min_keep = 0.25
                                if cand_dur >= fallback_min_keep:  # 阈值可调，默认更宽松
                                    final_gesture_seq.append(candidate)
                                    print(f"[timestamps] [警告] 所有动作被过滤，保留最长动作: {candidate.get('gesture_name', 'unknown')} ({cand_dur:.2f}s)")
                                    break
                            # 如果还是没有，至少保留第一个（即使<0.5秒，但至少有个动作）
                            if len(final_gesture_seq) == 0 and all_candidates:
                                final_gesture_seq.append(all_candidates[0])
                                print(f"[timestamps] [警告] 所有动作都太短，强制保留第一个: {all_candidates[0].get('gesture_name', 'unknown')}")
                    
                    if important_fillers:
                        print(f"[timestamps] ✂️  重要动作: {len(important_fillers)} -> {len([g for g in final_gesture_seq if self._is_important_action(g.get('gesture_name', ''))])}个")
                    if normal_fillers:
                        print(f"[timestamps] ✂️  普通填充: {len(normal_fillers)} -> {len([g for g in final_gesture_seq if not self._is_important_action(g.get('gesture_name', ''))])}个")
                #  关键修复：优化手势序列，避免相邻手势之间角度差异过大
                final_gesture_seq = self._optimize_gesture_sequence_angles(final_gesture_seq)
                
                #  关键：最终要执行的是 final_gesture_seq，必须对它做时间轴排程（而不是对 full_gesture_seq）
                final_gesture_seq = self._schedule_by_word_timestamps(final_gesture_seq, merged_timestamps, total_duration)
                
                # 时间轴排程后二次短动作过滤（可调，默认更宽松，减少“触发等级被削弱”体感）
                filtered_seq = []
                try:
                    min_after_schedule = float(os.environ.get("DH_MIN_AFTER_SCHEDULE", "0.25"))
                except Exception:
                    min_after_schedule = 0.25
                for g in final_gesture_seq:
                    g_dur = float(g.get('duration', 0.5) or 0.5)
                    if g_dur >= min_after_schedule:
                        filtered_seq.append(g)
                    else:
                        if self.verbose:
                            print(f"[timestamps] [跳过] 时间轴排程后过滤短动作: {g.get('gesture_name', 'unknown')} ({g_dur:.2f}s < {min_after_schedule:.2f}s)")
                
                if len(filtered_seq) > 0:
                    final_gesture_seq = filtered_seq
                elif len(final_gesture_seq) > 0:
                    longest_g = max(final_gesture_seq, key=lambda x: float(x.get('duration', 0) or 0.0))
                    final_gesture_seq = [longest_g]
                    print(f"[timestamps] [警告] 所有动作都太短，保留最长的: {longest_g.get('gesture_name', 'unknown')} ({float(longest_g.get('duration', 0) or 0.0):.2f}s)")
                
                # 执行用语音上界：取最后词结束与名义时长较小值并扣尾裁（DH_SPEECH_END_TRIM），只裁填充手势
                speech_exec_dur = self._effective_speech_duration_for_exec(total_duration, merged_timestamps)
                final_gesture_seq = self._clip_gesture_sequence_to_speech_cap(
                    final_gesture_seq, speech_exec_dur, clip_fillers_only=True
                )
                
                final_duration = sum(g.get('duration', 0) for g in final_gesture_seq)
                print(f"[timestamps] [OK] 最终: {len(final_gesture_seq)}个手势, 累加时长: {final_duration:.2f}s；执行 speech_duration={speech_exec_dur:.2f}s（名义 {total_duration:.2f}s）")
                
                # 第五步：缓存（含 speech_duration，用于执行时校验与截断）
                # timestamps 往往比 /playid 早到：记录一个“预计语音起点 wall time”，供 /playid 晚到时追帧对齐
                # 可调：export DH_TS_START_GUESS=0.15
                ts_start_guess = time.time() + float(os.environ.get("DH_TS_START_GUESS", "0.15"))
                self._last_cached_gesture = (final_gesture_seq, speech_exec_dur, ts_start_guess)
                self._last_cached_gesture_time = time.time()
                self._timestamp_batch_seq += 1
                batch_id = self._timestamp_batch_seq
                batch_play_ids = {(batch_id, s['play_id']) for s in all_sentences}
                self._current_batch_play_ids = batch_play_ids
                self._executed_batch_play_ids = set()  #  新批次到达，重置
                executed_from_ts = False  #  本批在 timestamps 内只执行一次
                for sentence in all_sentences:
                    play_id = sentence['play_id']
                    cache_key = (batch_id, play_id)
                    self._latest_cache_key_by_play_id[play_id] = cache_key
                    self._cache_key_to_play_id[cache_key] = play_id
                    self.gesture_cache[cache_key] = {
                        'gestures': final_gesture_seq,
                        'speech_duration': speech_exec_dur,
                        'speech_start_wall_guess': ts_start_guess,
                        'cache_time': time.time()
                    }

                    #  关键修复：如果该play_id 早已收到/playid，缓存就绪后立刻执行一次（整批只执行一次）
                    if not executed_from_ts and play_id in self.playid_recv_time:
                        if play_id in self.pending_play_ids:
                            speech_start = time.time()
                            print(f"[timestamps] [恢复] ID={play_id} 曾在service期间等待，使用当前时刻作为动作起点")
                        else:
                            speech_start = self.playid_recv_time.get(play_id)
                        if cache_key in getattr(self, "_service_replay_play_ids", set()):
                            executed_from_ts = True
                            print(f"[timestamps] [跳过] ID={play_id}, key={cache_key} 正在执行service后的恢复动作，仅更新缓存，不重复抢占")
                            continue
                        # service 预设动作优先级更高。若此时抢跑时间戳动作，会与 service 同时发布；
                        # service 结束时 pending 已被清掉，就会表现为“service 后没有时间戳动作”。
                        if self._service_action_running:
                            self.pending_play_ids.add(play_id)
                            executed_from_ts = True
                            print(f"[timestamps] [等待] service动作执行中，ID={play_id} 缓存就绪，等待service完成后执行")
                            continue

                        self.pending_play_ids.discard(play_id)
                        print(f"[timestamps] [快速] ID={play_id}的/playid已到达，缓存就绪后立即执行（语音开始于{time.time() - speech_start:.2f}s前）")
                        # 仅标记本批已执行的 play_id，具体缓存删除交由执行线程结束时处理，
                        # 这样一句话的缓存动作会一直保留，直到下一句话真正开始播放
                        self._executed_batch_play_ids = batch_play_ids
                        self._start_gesture_execution(
                            play_id,
                            final_gesture_seq,
                            speech_start_wall=speech_start,
                            speech_duration=speech_exec_dur
                        )
                        executed_from_ts = True

                # ������ 不在 timestamps 回调里抢跑执行！
                # 原因：你这条链路里 /timestamps 往往比 /playid 更晚或不同步（日志中就出现“先收到timestamps，后收到playid”）。
                # 若在此处执行，会导致 speech_start_wall 基准错乱，出现“已过去1.00s，整段动作已错过”这种现象。
                # 正确做法：仅缓存，等待 /playid 回调触发执行（以 /playid 到达时刻作为语音0点）。
                
            except Exception as e:
                print(f"[timestamps] [错误] 生成手势失败: {e}")
                import traceback
                traceback.print_exc()
            
            if self.verbose:
                print(f"[timestamps] [缓存] 缓存: {len(self.gesture_cache)} 个 (IDs: {sorted(self.gesture_cache.keys())})")
                if self.pending_play_ids:
                    print(f"[timestamps] [等待] 等待: {sorted(self.pending_play_ids)}")

        if ROS_VERSION == 2:
            qos_profile = QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE
            )
            node.create_subscription(RosString, topic, _cb, qos_profile)
        else:
            rospy.Subscriber(topic, RosString, _cb, queue_size=10)
        print(f"[timestamps] [订阅] 已订阅 {topic} 话题 (ROS{ROS_VERSION})")

        # 订阅 /command 话题：HUG/HAND_WAVE/HANDSHAKE 等指令直接触发对应动作
        def _command_cb(msg):
            raw = getattr(msg, "data", None) or str(msg)
            cmd = (raw if isinstance(raw, str) else "").strip().upper()
            if not cmd:
                return
            # 处理 clear 指令（与 /timestamps 路径保持一致）
            if cmd == "CLEAR":
                print("[command] [clear] 收到清除指令")
                self.conversation_ended = True
                with self._exec_lock:
                    self._exec_token += 1
                self.interrupt_all = True
                self.interrupt_current = True
                self.gesture_cache.clear()
                self._latest_cache_key_by_play_id.clear()
                self._cache_key_to_play_id.clear()
                self.pending_play_ids.clear()
                self._return_to_rest_position(from_clear=True)
                return
            action = getattr(self, "_command_mappings", {}).get(cmd)
            if not action:
                action = {
                    "HUG": "embrace",
                    "HAND_WAVE": "wave_right",
                    "HANDSHAKE": "你好",
                    "HANDE_SHAKE": "你好",
                    "HAND_SHAKE": "你好",
                }.get(cmd)
            if action:
                print(f"[command] 收到指令: {cmd} -> 执行 {action}")
                self._execute_command_action(action)

        if ROS_VERSION == 2:
            cmd_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            node.create_subscription(RosString, "/command", _command_cb, cmd_qos)
        else:
            rospy.Subscriber("/command", RosString, _command_cb, queue_size=10)
        print("[command] 已订阅 /command 话题 (HUG/HAND_WAVE/HANDSHAKE 等)")

        print(f"[timestamps] 工作模式: 双模式状态机 (TIMESTAMP > SOUND_DETECTED > IDLE)")
        print(f"[timestamps] - TIMESTAMP模式: 收到/timestamps时，按时间戳精确对齐动作")
        print(f"[timestamps] - SOUND模式: 无时间戳但sound_detected=true时，执行随机动作")
        print(f"[timestamps] - IDLE模式: 无时间戳且sound_detected=false超过{self._sound_to_idle_delay}s时，回到初始位置并待机")
        print(f"[timestamps] [待机] 待机模式阈值: {self.idle_threshold}秒无语音后开始待机动作")
        
        #  启动待机检测循环
        if ROS_VERSION == 2:
            # ROS2：用 MultiThreadedExecutor + 独立 spin 线程，确保回调不被主循环 sleep 阻塞
            import threading as _threading
            from rclpy.executors import MultiThreadedExecutor
            executor = MultiThreadedExecutor(num_threads=4)
            executor.add_node(node)

            def _spin_thread():
                try:
                    executor.spin()
                except Exception:
                    pass

            spin_th = _threading.Thread(target=_spin_thread, daemon=True)
            spin_th.start()

            rate_period = 1.0  # 主循环 1Hz，只做状态检测
            while rclpy.ok():
                # 简化的状态检测：只更新基础状态，动作触发由回调处理
                # 但如果在SOUND模式且动作已结束，需要触发下一个随机动作
                if self._mode_state == "SOUND" and self._sound_detected_flag:
                    if not self._sound_action_executing and not self.is_idle:
                        _trigger_sound_action()
                
                # 清理过期 pending，防止误判"仍在会话中"而无法进入待机
                self._prune_stale_pending_playids()
                self._idle_prune_orphan_gesture_cache()
                # 检查是否需要进入待机模式（基于"最近文本/动作结束"时间）
                idle_base = max(
                    self.last_text_time,
                    getattr(self, "last_action_finish_time", self.last_text_time),
                )
                idle_time = time.time() - idle_base
                
                if idle_time > self.idle_threshold and not self.is_idle:
                    # 仅当仍在等 /playid 或 pending 时阻塞待机。勿在阻塞时刷新 last_text_time，
                    # 否则每秒把 idle_base 推到“现在”，idle_time 永远达不到阈值（说完也进不了待机）。
                    if self._idle_blocked_by_play_queue():
                        pass
                    else:
                        # print(f"[idle] [时间] 空闲{idle_time:.1f}秒（阈值{self.idle_threshold:.1f}秒），进入待机模式...")
                        self._start_idle_mode()
                
                # TIMESTAMP 模式：sound 和 timestamps 都超过 1 秒没收到，对话结束，归位
                if self._mode_state == "TIMESTAMP":
                    _now = time.time()
                    if (_now - self._last_sound_true_time > 1.0 and
                            _now - self._last_timestamp_recv_time > 1.0 and
                            not self.is_idle):
                        if self._timestamp_pipeline_active():
                            if self.verbose:
                                print("[mode] 时间戳动作正在执行/等待恢复，跳过自动归位")
                        else:
                            self._mode_state = "IDLE"
                            self._return_to_rest_position()
                
                time.sleep(rate_period)
                # spin 已由独立线程处理，主循环不再调用 spin_once
        else:
            rate = rospy.Rate(1)  # 1Hz检查
            while not rospy.is_shutdown():
                # 简化的状态检测：只更新基础状态，动作触发由回调处理
                # 但如果在SOUND模式且动作已结束，需要触发下一个随机动作
                if self._mode_state == "SOUND" and self._sound_detected_flag:
                    if not self._sound_action_executing and not self.is_idle:
                        _trigger_sound_action()
                
                # 清理过期 pending，防止误判"仍在会话中"而无法进入待机
                self._prune_stale_pending_playids()
                self._idle_prune_orphan_gesture_cache()
                # 检查是否需要进入待机模式（基于"最近文本/动作结束"时间）
                idle_base = max(
                    self.last_text_time,
                    getattr(self, "last_action_finish_time", self.last_text_time),
                )
                idle_time = time.time() - idle_base
                
                if idle_time > self.idle_threshold and not self.is_idle:
                    if self._idle_blocked_by_play_queue():
                        pass
                    else:
                        # print(f"[idle] [时间] 空闲{idle_time:.1f}秒（阈值{self.idle_threshold:.1f}秒），进入待机模式...")
                        self._start_idle_mode()
                
                # TIMESTAMP 模式：sound 和 timestamps 都超过 1 秒没收到，对话结束，归位
                if self._mode_state == "TIMESTAMP":
                    _now = time.time()
                    if (_now - self._last_sound_true_time > 1.0 and
                            _now - self._last_timestamp_recv_time > 1.0 and
                            not self.is_idle):
                        if self._timestamp_pipeline_active():
                            if self.verbose:
                                print("[mode] 时间戳动作正在执行/等待恢复，跳过自动归位")
                        else:
                            self._mode_state = "IDLE"
                            self._return_to_rest_position()
                
                rate.sleep()
    
    def _maybe_return_to_center_after_sentence(self, play_id: int, execution_completed: bool):
        """
        每句结束后尝试回中（rest）。
        条件：若与下一句间隔很短则跳过；若执行已被新动作中断则跳过；回中过程中若来新动作则中断并平滑到新目标。
        """
        # 对话结束时也希望最后一句执行一次回中，因此只在执行未完成时跳过
        if not execution_completed:
            return
        # 1. 短暂可中断等待：若期间来了新 play_id，说明下一句很近，不回中
        steps = max(1, int(self.return_to_center_delay / 0.02))
        for _ in range(steps):
            if self.interrupt_all or self.interrupt_current:
                if self.verbose:
                    print("[回中] 检测到新动作，跳过回中")
                return
            time.sleep(0.02)
        # 2. 下一句 play_id 已到达且间隔很短？
        next_id = play_id + 1
        try:
            my_arrival = self.playid_recv_time.get(play_id)
            next_arrival = self.playid_recv_time.get(next_id)
            if my_arrival and next_arrival:
                gap = float(next_arrival) - float(my_arrival)
                if 0 < gap < self.return_to_center_min_gap:
                    if self.verbose:
                        print(f"[回中] 与下一句间隔{gap:.2f}s < {self.return_to_center_min_gap}s，跳过回中")
                    return
        except Exception:
            pass
        # 3. 当前动作是否已溢出到下一句？若 next 已在执行中，则已被抢占，通常不会走到这里
        if self.interrupt_all or self.interrupt_current:
            return
        # 4. 执行回中（可被 interrupt 打断；若被打断，新动作会从当前位置平滑过渡）
        rest_gesture = {
            'gesture_name': 'rest2',
            'duration': 0.8,
        }
        rest_angles = self.gesture_policy.base_gestures.get('rest2', [0.0] * 12)
        rest_gesture['joint_angles'] = rest_angles
        if self.finger_controller:
            try:
                self._update_finger_control('rest', 0.8)
            except Exception:
                pass
        if self.verbose:
            print("[回中] 执行回中动作 (可被新动作中断)")
        self.ros_publisher.publish_enhanced_sequence(
            [rest_gesture],
            fps=100,
            smooth_transitions=True,
            verbose=False,
            speech_duration=None,
            interrupt_flag=lambda: self.interrupt_all or self.interrupt_current,
        )
        self.last_action_finish_time = time.time()

    def _gesture_cache_waiting_for_playid(self) -> bool:
        """timestamps 已写入 gesture_cache，但对应 /playid 尚未到达的句子仍会阻塞待机。"""
        try:
            if not self.gesture_cache:
                return False
            for pid in self.gesture_cache:
                external_pid = self._cache_key_to_play_id.get(pid, pid)
                rt = self.playid_recv_time.get(external_pid)
                if rt is None or float(rt) <= 0.0:
                    return True
            return False
        except Exception:
            return bool(self.gesture_cache)

    def _idle_blocked_by_play_queue(self) -> bool:
        """是否因「还在等 playid / pending」而不应进入待机（不依赖 gesture_cache 是否非空）。"""
        if self._timestamp_pipeline_active():
            return True
        if self.pending_play_ids:
            return True
        return self._gesture_cache_waiting_for_playid()

    def _idle_prune_orphan_gesture_cache(self):
        """
        无 pending、且距上次写入 timestamps 缓存已超过 TTL 时，清空 gesture_cache。
        防止：同批多句写入多个 play_id，但上游只发一次 /playid，部分 id 永远没有 recv，
        _gesture_cache_waiting_for_playid 长期为 True 而无法待机。
        """
        if not self.gesture_cache:
            return
        if self.pending_play_ids:
            return
        try:
            ttl = float(os.environ.get("DH_GESTURE_CACHE_IDLE_TTL", "45.0"))
        except Exception:
            ttl = 45.0
        if ttl <= 0:
            return
        last_ts = float(getattr(self, "_last_cached_gesture_time", 0.0) or 0.0)
        if last_ts <= 0.0 or (time.time() - last_ts) < ttl:
            return
        keys = list(self.gesture_cache.keys())
        self.gesture_cache.clear()
        self._latest_cache_key_by_play_id.clear()
        self._cache_key_to_play_id.clear()
        # if getattr(self, "verbose", False):
        #     print(f"[idle] [清理] 无 pending 且距上次缓存>{ttl:.0f}s，已清空 gesture_cache: {keys}")

    def _prune_stale_pending_playids(self):
        """
        清理长时间未命中 timestamps 的 pending_play_ids。
        避免 pending 残留导致待机判断长期被阻塞。
        """
        try:
            # service 预设动作可能持续 5s 以上；此时 pending 是有意等待，不能按普通超时清掉。
            if getattr(self, "_service_action_running", False):
                return
            now = time.time()
            ttl = float(os.environ.get("DH_PENDING_PLAYID_TTL", str(max(10.0, self.conversation_timeout))))
            if ttl <= 0:
                ttl = max(10.0, self.conversation_timeout)
            stale = []
            for pid in list(self.pending_play_ids):
                recv_t = self.playid_recv_time.get(pid, 0.0)
                if (recv_t <= 0.0) or ((now - float(recv_t)) > ttl):
                    stale.append(pid)
            if stale:
                for pid in stale:
                    self.pending_play_ids.discard(pid)
                    try:
                        self.playid_recv_time.pop(pid, None)
                    except Exception:
                        pass
                    try:
                        ck = self._latest_cache_key_by_play_id.get(pid, pid)
                        self.gesture_cache.pop(ck, None)
                    except Exception:
                        pass
                if self.verbose:
                    print(f"[idle] [清理] 移除过期 pending_play_ids: {sorted(stale)} (ttl={ttl:.1f}s)")
        except Exception:
            pass

    def _timestamp_execution_active(self) -> bool:
        """timestamps/playid 驱动的动作线程正在发布时，普通 service/待机/自动归位不能抢占。"""
        try:
            return bool(getattr(self, "_gesture_execution_running", False)) and not bool(getattr(self, "conversation_ended", False))
        except Exception:
            return False

    def _timestamp_pipeline_active(self) -> bool:
        """timestamps 动作已在执行，或 /playid 已到、正在等 timestamps 缓存恢复。"""
        try:
            return self._timestamp_execution_active() or bool(getattr(self, "pending_play_ids", set()))
        except Exception:
            return self._timestamp_execution_active()

    def _return_to_rest_position(self, blocking=False, from_clear=False, force=False):
        """回到初始位置
        
        Args:
            blocking: 为 True 时同步执行（service 动作0场景）
            from_clear: 为 True 时来自 clear 指令，需要检查 conversation_ended；
                        为 False 时来自对话结束/模式切换，直接执行不检查
            force: 为 True 时强制归位；普通自动归位不应打断 timestamps 动作。
        """
        def _do_rest():
            try:
                # 等执行线程检测到中断并退出
                time.sleep(0.15)

                # 仅 clear 路径需要检查 service 0 是否已接管
                if from_clear and not self.conversation_ended:
                    return  # service 0 已接管，退出不抢

                if not force and self._timestamp_pipeline_active():
                    if self.verbose:
                        print("[归位] 时间戳动作正在执行/等待恢复，跳过自动归位")
                    return

                self.interrupt_all = False
                self.interrupt_current = False
                rest_angles = self.gesture_policy.base_gestures.get(
                    'rest2', self.gesture_policy.base_gestures.get('rest', [0.0] * 12))
                success = self.ros_publisher.publish_enhanced_sequence(
                    [{'gesture_name': 'rest2', 'duration': 1.0, 'joint_angles': rest_angles}],
                    fps=100, smooth_transitions=True, verbose=False,
                    speech_duration=None, interrupt_flag=None
                )
                if not success:
                    print("[归位] 回到初始位置失败")
                else:
                    print("[归位] 已回到初始位置")
                self.last_action_finish_time = time.time()
            except Exception as e:
                print(f"[归位] 回到初始位置出错: {e}")
        if blocking:
            _do_rest()
        else:
            threading.Thread(target=_do_rest, daemon=True).start()

    def _optimize_gesture_sequence_angles(self, gesture_seq):
        """
        优化手势序列，避免相邻手势之间角度差异过大（>90度）
        如果发现大角度跳变，尝试替换为角度更接近的手势
        """
        if not gesture_seq or len(gesture_seq) <= 1:
            return gesture_seq
        
        try:
            optimized_seq = []
            prev_angles = None
            
            for i, g in enumerate(gesture_seq):
                g_name = g.get('gesture_name') or g.get('gesture', 'rest')
                g_angles = g.get('joint_angles')
                
                # 如果没有joint_angles，通过mapper获取
                if g_angles is None:
                    if hasattr(self, 'ros_publisher') and self.ros_publisher and self.ros_publisher.gesture_mapper:
                        g_angles = self.ros_publisher.gesture_mapper.map_gesture(g_name)
                    if g_angles is None:
                        # 如果找不到，使用默认姿势
                        optimized_seq.append(g)
                        continue
                
                # 如果是第一个手势，直接添加
                if prev_angles is None:
                    optimized_seq.append(g)
                    prev_angles = g_angles
                    continue
                
                # 序列动作（你好、右边、左边等）不得替换，必须按 JSON 原样执行
                if g.get('is_sequence_action', False):
                    optimized_seq.append(g)
                    prev_angles = g_angles
                    continue
                
                # 计算角度差异
                angle_diff = sum(abs(a - b) for a, b in zip(prev_angles, g_angles))
                
                # 如果角度差异过大（>90度），尝试替换为角度更接近的手势
                if angle_diff > 90:
                    if self.verbose:
                        print(f"[优化] [警告] 手势{i+1} ({g_name}) 与上一个手势角度差异过大: {angle_diff:.1f}度")
                    
                    # 尝试找一个角度更接近的替代手势
                    alternative = self._find_closer_gesture(prev_angles, g_name, g)
                    if alternative:
                        if self.verbose:
                            print(f"[优化] [OK] 替换为角度更接近的手势: {alternative.get('gesture_name', 'unknown')}")
                        optimized_seq.append(alternative)
                        # 更新prev_angles为替代手势的角度
                        alt_angles = alternative.get('joint_angles')
                        if alt_angles is None:
                            alt_name = alternative.get('gesture_name') or alternative.get('gesture', 'rest')
                            if hasattr(self, 'ros_publisher') and self.ros_publisher and self.ros_publisher.gesture_mapper:
                                alt_angles = self.ros_publisher.gesture_mapper.map_gesture(alt_name)
                        if alt_angles:
                            prev_angles = alt_angles
                        else:
                            prev_angles = g_angles
                    else:
                        # 如果找不到替代，保持原手势，但会使用更长的过渡时间
                        optimized_seq.append(g)
                        prev_angles = g_angles
                else:
                    # 角度差异合理，直接添加
                    optimized_seq.append(g)
                    prev_angles = g_angles
            
            return optimized_seq
        except Exception as e:
            if self.verbose:
                print(f"[优化] [警告] 优化手势序列时出错: {e}")
            return gesture_seq
    
    def _find_closer_gesture(self, target_angles, original_name, original_gesture):
        """
        找一个角度更接近target_angles的手势，替代original_gesture
        优先选择neutral、rest等中性手势
        """
        if not hasattr(self, 'ros_publisher') or not self.ros_publisher or not self.ros_publisher.gesture_mapper:
            return None
        
        mapper = self.ros_publisher.gesture_mapper
        
        #  候选替代手势（按优先级排序）- 说话时不要使用neutral，用有动作的手势替代
        candidates = [
            'both_hands_explain',
            'head_natural_left',
            'head_natural_right',
            'head_micro_nod',
            'head_micro_look_left',
            'head_micro_look_right',
            'attentive_listen',
        ]
        best_gesture = None
        best_diff = float('inf')
        
        for candidate_name in candidates:
            candidate_angles = mapper.map_gesture(candidate_name)
            if candidate_angles is None:
                continue
            
            # 计算角度差异
            diff = sum(abs(a - b) for a, b in zip(target_angles, candidate_angles))
            
            # 如果这个候选手势的角度差异更小，且小于90度，就选择它
            if diff < best_diff and diff < 90:
                best_diff = diff
                best_gesture = {
                    'gesture_name': candidate_name,
                    'joint_angles': candidate_angles,
                    'duration': original_gesture.get('duration', 0.5),  # 保持原手势的时长
                    'is_sequence_action': original_gesture.get('is_sequence_action', False)
                }
        
        return best_gesture

    def _schedule_by_word_timestamps(self, gesture_seq, merged_timestamps, total_duration):
        """
        将手势序列映射到语音时间轴：给每个手势添加 start_offset，并重写 duration，使其严格覆盖 [0, total_duration]。
        这是“动作与语音时间轴匹配”的关键（不再只是顺序播一串）。
        """
        try:
            seq = [g for g in (gesture_seq or []) if isinstance(g, dict)]
            if not seq:
                return gesture_seq
            ts = [w for w in (merged_timestamps or []) if isinstance(w, dict)]
            if not ts:
                return gesture_seq
            # 语音参考时长（用于安排 start_offset），但不强制把“序列动作”压缩进语音时长
            try:
                speech_end = max(float(w.get('end_time', 0.0) or 0.0) for w in ts)
            except Exception:
                speech_end = float(total_duration or 0.0)
            if total_duration is not None:
                speech_end = float(max(speech_end, float(total_duration)))
            if speech_end <= 0:
                return gesture_seq

            #  关键修复：分离序列动作和填充动作，确保序列动作连续执行，避免填充动作插入导致抖动
            sequence_gestures = [g for g in seq if g.get("is_sequence_action", False)]
            filler_gestures = [g for g in seq if not g.get("is_sequence_action", False)]
            has_sequence = len(sequence_gestures) > 0
            
            out = []
            
            if has_sequence:
                #  有序列动作：序列动作连续执行（start_offset 连续），填充动作放在后面
                # 序列动作的 start_offset：从 0.0 开始，按序列动作的原始顺序连续分配
                seq_duration = sum(float(g.get('duration', 0.5) or 0.5) for g in sequence_gestures)
                current_offset = 0.0
                
                for g in sequence_gestures:
                    gg = dict(g)
                    gg['start_offset'] = float(current_offset)
                    # duration 保持原始值（不压缩）
                    out.append(gg)
                    current_offset += float(gg.get('duration', 0.5) or 0.5)
                
                # 填充动作：放在序列动作之后（如果有剩余时间）
                remaining_time = float(speech_end) - float(current_offset)
                if remaining_time > 0.5 and filler_gestures:  # 至少0.5秒才添加填充
                    # 关键修复：保持填充动作的原始时长，不压缩，让动作自然延续到语音结束
                    # 计算填充动作的原始总时长
                    filler_original_duration = sum(float(g.get('duration', 0.5) or 0.5) for g in filler_gestures)
                    
                    if filler_original_duration <= remaining_time:
                        # 如果填充动作的原始时长不超过剩余时间，保持原始时长
                        for g in filler_gestures:
                            gg = dict(g)
                            gg['start_offset'] = float(current_offset)
                            # 保持原始 duration
                            out.append(gg)
                            current_offset += float(gg.get('duration', 0.5) or 0.5)
                    else:
                        # 如果填充动作的原始时长超过剩余时间，按比例缩放（但保持最小0.5秒）
                        scale_factor = remaining_time / filler_original_duration
                        for g in filler_gestures:
                            gg = dict(g)
                            original_duration = float(g.get('duration', 0.5) or 0.5)
                            scaled_duration = max(0.5, original_duration * scale_factor)
                            
                            # 检查是否还有足够的剩余时间
                            if current_offset + scaled_duration <= speech_end:
                                gg['start_offset'] = float(current_offset)
                                gg['duration'] = float(scaled_duration)
                                out.append(gg)
                                current_offset += scaled_duration
                            else:
                                # 剩余时间不足，跳过后续动作
                                if self.verbose:
                                    print(f"[时间轴] [跳过] 剩余时间不足，跳过后续填充动作")
                                break
            else:
                # 无序列动作：所有填充动作均匀分布在 [0, speech_end]
                n = len(filler_gestures)
                if n <= 0:
                    return gesture_seq
                
                # 关键修复：确保动作能填满整个语音时长
                # 计算所有动作的原始总时长
                total_original_duration = sum(float(g.get('duration', 0.5) or 0.5) for g in filler_gestures)
                
                # ✅ 借鉴口型算法：归一化分配时间，确保总时长精确匹配
                # 核心思想：无论动作多少，都要填满整个语音时长
                if total_original_duration < speech_end * 0.5:
                    # 如果动作总时长太短（<50%），先循环重复动作，再归一化
                    print(f"[时间轴] [循环+归一化] 动作总时长({total_original_duration:.2f}s)太短，先循环重复")
                    
                    # 计算需要循环多少次才能接近语音时长
                    repeat_times = int(speech_end / total_original_duration) + 1
                    repeated_gestures = filler_gestures * repeat_times
                    
                    # 重新计算总时长
                    total_repeated_duration = sum(float(g.get('duration', 0.5) or 0.5) for g in repeated_gestures)
                    
                    # 归一化：按比例分配时间，确保总时长 = speech_end
                    scale_factor = speech_end / total_repeated_duration
                    print(f"[时间轴] [归一化] 循环后总时长{total_repeated_duration:.2f}s，归一化系数{scale_factor:.3f}")
                    
                    current_offset = 0.0
                    for g in repeated_gestures:
                        gg = dict(g)
                        original_duration = float(g.get('duration', 0.5) or 0.5)
                        # 归一化时长
                        normalized_duration = original_duration * scale_factor
                        
                        gg['start_offset'] = float(current_offset)
                        gg['duration'] = float(normalized_duration)
                        out.append(gg)
                        current_offset += normalized_duration
                        
                        # 如果已经填满，停止
                        if current_offset >= speech_end - 0.01:
                            break
                
                else:
                    # ✅ 借鉴口型算法：归一化分配时间
                    scale_factor = speech_end / total_original_duration
                    print(f"[时间轴] [归一化] 动作总时长{total_original_duration:.2f}s，语音时长{speech_end:.2f}s，归一化系数{scale_factor:.3f}")
                    
                    current_offset = 0.0
                    for i, g in enumerate(filler_gestures):
                        gg = dict(g)
                        original_duration = float(g.get('duration', 0.5) or 0.5)
                        normalized_duration = original_duration * scale_factor
                        if i == len(filler_gestures) - 1:
                            normalized_duration = speech_end - current_offset
                        gg['start_offset'] = float(current_offset)
                        gg['duration'] = float(normalized_duration)
                        out.append(gg)
                        current_offset += normalized_duration
            
            return out
        except Exception:
            return gesture_seq
    
    def _generate_idle_gesture(self):
        """生成一个待机动作（更自然的人类待机姿态）
        
        返回值：
        - 普通动作：单个 dict，包含 gesture_name / joint_angles / duration
        - 点头序列：list of dict，包含两帧（向上 + 回位），loop 需判断类型后完整发布
        """
        import random
        
        #  待机动作池：头部左右看为主（90%），手臂微微动（10%）- 头部动作要多
        idle_gesture_pool = [
            #  头部左右看（90%概率）- 只保留确认安全的手势
            {
                'type': 'head_look',
                'gestures': [
                    'head_natural_left',
                    'head_natural_left',
                    'head_natural_right',
                    'head_natural_right',
                    'look_left_slight',
                    'look_right_slight',
                    'head_micro_tilt_left',
                    'head_micro_tilt_right',
                    'head_micro_look_left',
                    'head_micro_look_right',
                    'head_slight_tilt',
                    'head_micro_up',
                    'head_micro_up',
                    'head_micro_up',
                    'shake_head_idle',   # 摇头A
                    'shake_head_idle_b', # 摇头B
                    'nod_sequence',      # 点头（向上再回位，两帧序列）
                    'nod_sequence',      # 适当提高权重，与摇头出现频率相近
                ],
                'weight': 0.8  #  90%概率头部动作
            },
            # 手臂微微动（10%概率）- 手臂动作要少
            {
                'type': 'arms_micro',
                'gestures': [
                    'rest',                  # 休息姿态
                    'neutral',               # 中性姿态
                    'both_hands_down',       # 双手自然下垂
                ],
                'weight': 0.2  #  10%概率手臂动作
            }
        ]
        
        # 根据权重随机选择类型
        rand = random.random()
        if rand < 0.8:  #  90%概率头部动作
            gesture_type = idle_gesture_pool[0]
        else:
            gesture_type = idle_gesture_pool[1]

        gesture_name = random.choice(gesture_type['gestures'])

        # ── 点头序列：直接返回两帧列表，loop 负责完整发布 ──
        if gesture_name == 'nod_sequence':
            nod_angles = list(self.gesture_policy.base_gestures.get(
                'nod_up_return', [0, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
            rest2_angles = list(self.gesture_policy.base_gestures.get(
                'rest2', self.gesture_policy.base_gestures.get('rest', [0.0] * 12)))
            return [
                {'gesture_name': 'idle_nod_up',     'joint_angles': nod_angles,   'duration': 0.5},
                {'gesture_name': 'idle_nod_return',  'joint_angles': rest2_angles, 'duration': 0.5},
            ]

        #  待机动作时长：2-3秒（比语音动作快）
        duration = random.uniform(2.0, 3.0)
        
        # 获取手势角度
        base_angles = self.gesture_policy.base_gestures.get(gesture_name, None)
        
        #  检查动作是否存在
        if base_angles is None:
            # 打印可用的动作列表（仅第一次）
            if not hasattr(self, '_printed_available_gestures'):
                available = list(self.gesture_policy.base_gestures.keys())
                print(f"[idle] [列表] 可用的base_gestures: {available[:10]}... (共{len(available)}个)")
                self._printed_available_gestures = True
            
            print(f"[idle] [警告] 动作 '{gesture_name}' 未在base_gestures中定义，使用rest姿态")
            base_angles = self.gesture_policy.base_gestures.get('rest', [0.0] * 12)
        
        #  调整随机变化：左右幅度大，上下幅度小；手臂各关节微扰 ±0.3°。
        #  待机时左/右外展(3,8)：本工程为「角度增大≈更外展」；只允许多外展侧微动到上限 cap，不向更内收侧动
        #  （夹紧区间 [min(base,cap), cap]，勿用对称 ±cap 以免出现内收）。
        _idle_arm_abduction_max = float(os.environ.get("DH_IDLE_ARM_ABDUCTION_MAX", "5.0"))
        varied_angles = []
        is_head_gesture = gesture_type['type'] == 'head_look'

        for i, angle in enumerate(base_angles):
            b = float(angle)
            if i == 0:  # 头部左右（索引0）
                if is_head_gesture:
                    variation = random.uniform(-30, 30)
                else:
                    variation = random.uniform(-0.5, 0.5)
            elif i == 1:  # 头部上下（索引1）
                if is_head_gesture:
                    variation = random.uniform(-3, 2)
                else:
                    variation = random.uniform(-1, 1)
            else:  # 手臂关节（索引2-11，含 3/8 外展）：与其它臂关节相同微扰
                variation = random.uniform(-0.3, 0.3)
            varied_angles.append(b + variation)

        # 待机头部限制：左右最大 30 度，低头不超过 2 度
        if len(varied_angles) >= 2:
            varied_angles[0] = max(-30.0, min(30.0, float(varied_angles[0])))
            varied_angles[1] = min(2.0, float(varied_angles[1]))
            if varied_angles[1] < -45:
                varied_angles[1] = max(-45.0, varied_angles[1])

        # 待机外展：关节 3=左外展, 8=右外展；仅外展方向（随机可到 cap），不低于 min(base,cap)（不内收）
        if len(varied_angles) > 8 and len(base_angles) > 8:
            cap = max(0.0, _idle_arm_abduction_max)
            for idx in (3, 8):
                b = float(base_angles[idx])
                v = float(varied_angles[idx])
                lo = min(b, cap)
                varied_angles[idx] = max(lo, min(cap, v))
        
        return {
            'gesture_name': f'idle_{gesture_name}',
            'joint_angles': varied_angles,
            'duration': duration
        }
    
    def _idle_gesture_loop(self):
        """待机动作循环（在后台线程中运行）"""
        import threading
        
        print("[idle] [待机] 开始待机动作循环...")
        
        # 检查ROS是否关闭的函数
        def is_shutdown():
            if ROS_VERSION == 2:
                return not rclpy.ok()
            else:
                return rospy.is_shutdown()
        
        while self.is_idle and not is_shutdown():
            # 检查是否收到新文本
            idle_base = max(self.last_text_time, getattr(self, "last_action_finish_time", self.last_text_time))
            if time.time() - idle_base < self.idle_threshold:
                # 有新文本/动作结束，退出待机
                print("[idle] [日志] 收到新文本/动作，退出待机模式")
                self.is_idle = False
                break
            
            # 生成并执行一个待机动作
            idle_gesture = self._generate_idle_gesture()
            
            try:
                # 同步更新手指（待机时也让手指轻微运动）
                if hasattr(self, "_update_finger_control"):
                    try:
                        first_g = idle_gesture[0] if isinstance(idle_gesture, list) else idle_gesture
                        self._update_finger_control(
                            first_g.get("gesture_name", "rest"),
                            first_g.get("duration", 0.5),
                        )
                    except Exception as e:
                        if getattr(self, "verbose", False):
                            print(f"[idle] [手指控制] 更新失败: {e}")
                
                # 待机动作使用更快的速度（fps=100）
                # 点头序列返回 list，其余返回单个 dict；统一包装成列表传给 publish
                frames = idle_gesture if isinstance(idle_gesture, list) else [idle_gesture]
                total_dur = sum(f.get('duration', 0.5) for f in frames)
                name_log = frames[0].get('gesture_name', '?') + (f'+{len(frames)-1}帧' if len(frames) > 1 else '')

                success = self.ros_publisher.publish_enhanced_sequence(
                    frames,
                    fps=100,
                    smooth_transitions=True,
                    verbose=False,
                    speech_duration=None,
                    interrupt_flag=lambda: not self.is_idle
                )
                
                if not success:
                    print(f"[idle] [错误] 待机动作发布失败: {name_log}")
                else:
                    print(f"[idle] [OK] 待机动作发布成功: {name_log} ({total_dur:.1f}s)")
                    
            except Exception as e:
                print(f"[idle] [错误] 待机动作执行失败: {e}")
            
            # 等待到3秒后再执行下一个动作
            wait_time = 3.0 - total_dur
            if wait_time > 0:
                # �� 修复：分段sleep，每50ms检查一次is_idle，确保收到true后立即退出
                elapsed_wait = 0.0
                while elapsed_wait < wait_time and self.is_idle:
                    time.sleep(0.05)
                    elapsed_wait += 0.05
            else:
                time.sleep(0.1)  # 短暂等待，避免CPU占用过高
        
        print("[idle] [退出] 退出待机模式")
    
    def _start_idle_mode(self):
        """启动待机模式
        
         对话结束时，清空所有缓存的非序列动作
        """
        import threading
        
        if self.is_idle:
            return  # 已经在待机模式

        if self._timestamp_pipeline_active():
            if self.verbose:
                print("[idle] [跳过] 时间戳动作正在执行/等待恢复，不进入待机")
            return
        
        print("[idle] [时间] 对话结束，进入待机模式")
        
        #  清空所有缓存中只有填充动作的手势序列
        removed_ids = []
        for play_id, cached in list(self.gesture_cache.items()):
            gesture_seq = cached.get('gestures', cached) if isinstance(cached, dict) else cached
            has_sequence = any((isinstance(g, dict) and g.get('is_sequence_action', False)) for g in (gesture_seq or []))
            if not has_sequence:
                # 只有填充动作，清空
                del self.gesture_cache[play_id]
                removed_ids.append(play_id)
        
        if removed_ids:
            print(f"[idle] [清除] 清空非序列动作缓存: {removed_ids}")
        
        #  清空pending队列中的非序列动作
        self.pending_play_ids.clear()
        print(f"[idle] [清除] 清空pending队列")
        
        self.is_idle = True
        self.idle_thread = threading.Thread(target=self._idle_gesture_loop, daemon=True)
        self.idle_thread.start()
    
    def _stop_idle_mode(self):
        """停止待机模式 - 立即中断待机动作"""
        if not self.is_idle:
            return
        
        stop_time = time.time()
        print(f"[idle] [{stop_time:.3f}] 立即停止待机模式...")
        self.is_idle = False
        
        # 关键：立即设置中断标志，让待机动作的interrupt_flag立即生效
        self.interrupt_all = True
        self.interrupt_current = True
        
        if self.idle_thread and self.idle_thread.is_alive():
            elapsed = time.time() - stop_time
            print(f"[idle] ⏱️  _stop_idle_mode 耗时 {elapsed*1000:.1f}ms，待机线程将在下一帧退出")

def main():
    """主函数"""
    
    # Service 回调函数
    def up_climb_action_service_callback(request, response, system):
        """上肢动作服务回调"""
        up_climb_request_type = request.up_limb_task_type
        all_success = True
        
        try:
            if up_climb_request_type == 0:
                system.ros_publisher.node.get_logger().info("执行笛卡尔坐标系变化动作")
                response.success = False
                response.message = "笛卡尔坐标系变化动作未实现"
                
            elif up_climb_request_type == 1:
                system.ros_publisher.node.get_logger().info("执行关节变化动作")
                response.success = False
                response.message = "关节变化动作未实现"
                
            elif up_climb_request_type == 2:
                system.ros_publisher.node.get_logger().info("执行上肢预设动作变化")
                
                action_fixed = request.action_fixed
                action_names = {
                    0: "初始位置",
                    1: "左挥手动作序列",
                    2: "右挥手动作序列",
                    3: "左指引姿势",
                    4: "右指引姿势",
                    5: "左手握手姿势",
                    6: "右手握手姿势",
                }
                
                action_name = action_names.get(action_fixed, f"未知动作{action_fixed}")
                system.ros_publisher.node.get_logger().info(f"执行预设动作: {action_name}")
                
                # 这里可以根据 action_fixed 调用相应的手势生成逻辑
                # 例如：system.process_text_to_gesture(action_text, verbose=False)
                
                response.success = True
                response.message = f"{action_name}执行成功"
                
            else:
                system.ros_publisher.node.get_logger().warn(f"无效的任务类型: {up_climb_request_type}")
                response.success = False
                response.message = "无效的任务类型"
                
        except Exception as e:
            system.ros_publisher.node.get_logger().error(f"服务回调异常: {e}")
            response.success = False
            response.message = f"执行失败: {str(e)}"
            
        return response
    
    parser = argparse.ArgumentParser(description='数字人系统 - 文本到手势生成')
    parser.add_argument('text', nargs='?', help='要处理的文本')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互模式')
    parser.add_argument('-t', '--test', action='store_true', help='运行测试序列')
    parser.add_argument('--test-connection', action='store_true', help='测试ROS连接')
    parser.add_argument('-v', '--verbose', action='store_true', default=True, help='详细输出')
    parser.add_argument('--duration', type=float, default=None, help='提供语音时长(秒)，用于测试手势与语音时间轴对齐')
    parser.add_argument('--from-timestamps', action='store_true', help='订阅/timestamps 话题并驱动数字人')
    parser.add_argument('--timestamps-topic', type=str, default='/timestamps', help='timestamps 话题名')
    
    #  新增：同步相关参数
    parser.add_argument('--enable-sync', action='store_true', help='启用play_id同步机制')
    parser.add_argument('--play-id', type=int, default=None, help='指定语音播放ID')
    parser.add_argument('--wait-play-id', action='store_true', help='等待play_id触发动作')
    
    # 手指控制参数（双手）
    parser.add_argument('--enable-finger', action='store_true', default=False, help='启用手指控制（默认禁用）')
    parser.add_argument('--disable-finger', action='store_true', help='禁用手指控制')
    # 兼容旧参数：单口（不再使用，仅保留兼容，不建议配置）
    parser.add_argument('--finger-port', type=str, default='/dev/ttyUSB1', help='[已弃用] 单口手指舵机串口（仅兼容保留）')
    # 新参数：左右手双口（默认按你的硬件约定）
    parser.add_argument('--right-finger-port', type=str, default='/dev/ttyUSB0', help='右手手指舵机串口（默认/dev/ttyUSB0）')
    parser.add_argument('--left-finger-port', type=str, default='/dev/ttyUSB2', help='左手手指舵机串口（默认/dev/ttyUSB2）')
    parser.add_argument('--finger-baudrate', type=int, default=115200, help='手指舵机串口波特率')
    
    args = parser.parse_args()
    
    # 手指控制参数处理
    enable_finger = args.enable_finger and not args.disable_finger
    
    # 创建系统实例（支持同步和手指控制）
    system = DigitalHumanSystem(
        enable_sync=args.enable_sync or args.wait_play_id,
        enable_finger_control=enable_finger,
        finger_serial_port=args.finger_port,
        finger_baudrate=args.finger_baudrate,
        right_finger_port=args.right_finger_port,
        left_finger_port=args.left_finger_port,
    )
    
    # 根据参数执行不同操作
    if args.test_connection:
        success = system.test_connection()
        sys.exit(0 if success else 1)
    
    elif args.test:
        success = system.run_test_sequence()
        sys.exit(0 if success else 1)
    
    elif args.from_timestamps:
        system.run_timestamps_bridge(topic=args.timestamps_topic)
    elif args.interactive:
        system.interactive_mode()
    
    elif args.text:
        success = system.process_text_to_gesture(
            text=args.text, 
            speech_duration=args.duration, 
            play_id=args.play_id,
            wait_for_play_id=args.wait_play_id,
            verbose=args.verbose
        )
        sys.exit(0 if success else 1)
    
    else:
        # 默认进入交互模式
        system.interactive_mode()

if __name__ == "__main__":
    main()
