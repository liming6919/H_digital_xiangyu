#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丰富的手势策略模块
根据语义信息规划自然、多样化的手势动作序列
"""

from typing import List, Dict, Tuple, Optional
import random
import os
import json
import re

class GesturePolicy:
    def __init__(self):
        """初始化手势策略"""
        
        # 🎯 加载头部动作速度因子（说话时加快：从35%改为80%，只加快说话时的头部动作）
        self.head_speed_factor = 0.80  # 🎯 默认值：80%速度（说话时加快头部动作）
        try:
            import yaml
            config_path = os.path.join(os.path.dirname(__file__), 'gesture_speed_config.yaml')
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.head_speed_factor = config.get('head_speed_factor', 0.80)  # 🎯 默认值改为0.80（说话时加快）
                    self.head_speed_factor = max(0.1, min(1.0, self.head_speed_factor))  # 限制在0.1-1.0之间
                    print(f"⚡ 说话时头部动作速度配置: {self.head_speed_factor*100:.0f}% (时长: {1/self.head_speed_factor:.1f}x)")
            else:
                print(f"⚠️  配置文件不存在，使用默认速度: 80%")
        except Exception as e:
            print(f"⚠️  加载速度配置失败: {e}，使用默认速度: 35%")
        
        # 头部相关的手势名称（用于识别需要调整速度的手势）
        self.head_gestures = {
            # 🎯 上下动作（需要减慢速度）
            "nod_slight", "nod_strong", "nod_emphatic", "head_micro_nod", "head_slight_nod","nod_up_return",
            "head_micro_up", "head_micro_down", "look_up", "look_down",
            "bow_respectful", "bow_deep", "bow_apologetic",
            # 左右动作（正常速度）
            "shake_head_slight", "shake_head_strong", "shake_head_emphatic", "head_micro_shake",
            "tilt_head_curious", "tilt_head_thoughtful", "tilt_head_confused",
            "look_left", "look_right", "head_natural_left", "head_natural_right",
            "head_micro_look_left", "head_micro_look_right", "head_micro_tilt_left", "head_micro_tilt_right",
            "head_moderate_left", "head_moderate_right", "head_moderate_tilt_left", "head_moderate_tilt_right",
            "look_left_slight", "look_left_strong", "look_right_slight", "look_right_strong",
            "head_forward", "head_back",
            "head_left_up", "head_left_down", "head_right_up", "head_right_down"  # 🎯 组合动作（左右+上下）
        }
        
        # 🎯 上下动作需要额外减速（在原有head_speed_factor基础上再减速50%）
        self.vertical_head_gestures = {
            "nod_slight", "nod_strong", "nod_emphatic", "head_micro_nod", "head_slight_nod",
            "head_micro_up", "head_micro_down", "look_up", "look_down",
            "bow_respectful", "bow_deep", "bow_apologetic"
        }
        
        # 丰富的5自由度手臂手势库
        # 关节索引: 0=头左右, 1=头上下, 2=左前后, 3=左外展, 4=左大臂转, 5=左肘, 6=左小臂转
        #          7=右前后, 8=右外展, 9=右大臂转, 10=右肘, 11=右小臂转
        
        # 🎭 动作序列定义 - 挥手等动态动作（减慢50%：所有时长×1.5）
        self.action_sequences = {
            "nod_sequence": [
                {"gesture": "nod_up_return", "duration": 0.5},   # 脖子向上10度
                {"gesture": "head_micro_nod", "duration": 0.5},
                {"gesture": "rest2", "duration": 0.5},            # 回到初始位置
            ],
            "wave_right_sequence": [
                {"gesture": "wave_right_prepare", "duration": 1.2},      # 🎯 抬手到位并稳定：合并为1.2秒
                {"gesture": "wave_right_left", "duration": 1.2},         # 🎯 向左挥：1.2秒
                {"gesture": "wave_right_right", "duration": 1.2},        # 🎯 向右挥：1.2秒
                {"gesture": "wave_right_left", "duration": 1.2},         # 🎯 向左挥：1.2秒
                {"gesture": "wave_right_right", "duration": 1.2},        # 🎯 向右挥：1.2秒
                {"gesture": "wave_right_left", "duration": 1.2},         # 🎯 向左挥：1.2秒
                {"gesture": "rest2", "duration": 0.8},                    # 🎯 放下：0.8秒
            ],
            "wave_left_sequence": [
                {"gesture": "wave_left_prepare", "duration": 1.2},       # 🎯 抬手到位并稳定：合并为1.2秒
                {"gesture": "wave_left_right", "duration": 1.2},         # 🎯 向右挥：1.2秒
                {"gesture": "wave_left_left", "duration": 1.2},          # 🎯 向左挥：1.2秒
                {"gesture": "wave_left_right", "duration": 1.2},         # 🎯 向右挥：1.2秒
                {"gesture": "wave_left_left", "duration": 1.2},          # 🎯 向左挥：1.2秒
                {"gesture": "wave_left_right", "duration": 1.2},         # 🎯 向右挥：1.2秒
                {"gesture": "rest2", "duration": 0.8},                    # 🎯 放下：0.8秒
            ],
            "wave_both_sequence": [
                {"gesture": "wave_both_prepare", "duration": 1.2},       # 🎯 双手抬起到位并稳定：合并为1.2秒
                {"gesture": "wave_both_out", "duration": 1.2},           # 🎯 双手向外挥：1.2秒
                {"gesture": "wave_both_in", "duration": 1.2},            # 🎯 双手向内挥：1.2秒
                {"gesture": "wave_both_out", "duration": 1.2},           # 🎯 双手向外挥：1.2秒
                {"gesture": "wave_both_in", "duration": 1.2},            # 🎯 双手向内挥：1.2秒
                {"gesture": "wave_both_out", "duration": 1.2},           # 🎯 双手向外挥：1.2秒
                {"gesture": "rest2", "duration": 0.8},                    # 🎯 放下：0.8秒
            ],
            "handshake_sequence": [
                {"gesture": "handshake_extend", "duration": 0.9},        # 伸手 (0.6→0.9)
                {"gesture": "handshake_grip", "duration": 1.2},          # 握手 (0.8→1.2)
                {"gesture": "handshake_shake", "duration": 0.9},         # 轻摇 (0.6→0.9)
                {"gesture": "rest2", "duration": 0.6},                    # 放下 (0.4→0.6)
            ],
            "embrace_sequence": [
                {"gesture": "embrace_gentle", "duration": 2.0},          # 🎯 轻柔张开双臂：增加到2秒
                {"gesture": "embrace_warm", "duration": 4.0},            # 🎯 温暖拥抱姿态：增加到4秒
                {"gesture": "embrace_passionate", "duration": 3.0},      # 🎯 激情拥抱：增加到3秒
                {"gesture": "embrace_warm", "duration": 2.0},            # 🎯 回到温暖拥抱：增加到2秒
            ],
            # 🎯 基于挥手动作的常用动作序列
            "clap_sequence": [
                {"gesture": "applaud_prepare", "duration": 0.9},         # 双手抬起 (0.6→0.9)
                {"gesture": "applaud_clap", "duration": 0.3},            # 鼓掌1 (0.2→0.3)
                {"gesture": "applaud_prepare", "duration": 0.3},         # 分开 (0.2→0.3)
                {"gesture": "applaud_clap", "duration": 0.3},            # 鼓掌2 (0.2→0.3)
                {"gesture": "applaud_prepare", "duration": 0.3},         # 分开 (0.2→0.3)
                {"gesture": "applaud_clap", "duration": 0.3},            # 鼓掌3 (0.2→0.3)
                {"gesture": "rest2", "duration": 0.75},                   # 放下 (0.5→0.75)
            ],
            "point_forward_sequence": [
                {"gesture": "point_forward", "duration": 1.2},           # 指向前方 (0.8→1.2)
            ],
            "thumbs_up_sequence": [
                {"gesture": "thumbs_up", "duration": 2.25},              # 点赞 (1.5→2.25)
                {"gesture": "rest2", "duration": 0.3},                    # 放下 (0.2→0.3)
            ],
            "ok_gesture_sequence": [
                {"gesture": "ok_gesture", "duration": 2.25},             # OK手势 (1.5→2.25)
                {"gesture": "rest2", "duration": 0.3},                    # 放下 (0.2→0.3)
            ],
            "stop_sequence": [
                {"gesture": "stop_gesture", "duration": 2.7},            # 停止手势 (1.8→2.7)
                {"gesture": "rest2", "duration": 0.3},                    # 放下 (0.2→0.3)
            ]
        }
        
        # 🎯 新增：序列动作的最小执行时长（不可压缩）- 也增加50%
        self.sequence_min_duration = {
            "wave_right_sequence": 8.0,    # 🎯 右手挥手总时长：1.2+1.2*5+0.8=8.0秒
            "wave_left_sequence": 8.0,     # 🎯 左手挥手总时长：1.2+1.2*5+0.8=8.0秒
            "wave_both_sequence": 8.0,     # 🎯 双手挥手总时长：1.2+1.2*5+0.8=8.0秒
            "handshake_sequence": 3.0,     # (2.0→3.0)
            "embrace_sequence": 11.0,      # 🎯 拥抱序列完整时长：2.0+4.0+3.0+2.0=11秒
            "clap_sequence": 2.7,          # (1.8→2.7)
            "thumbs_up_sequence": 1.8,     # (1.2→1.8)
            "ok_gesture_sequence": 1.8,    # (1.2→1.8)
            "stop_sequence": 2.25,         # (1.5→2.25)
        }
        
        # 🎯 头部微动配置
        self.enable_head_micro_movements = True  # 是否启用头部微动
        self.head_micro_movement_probability = 0.6  # 头部微动概率（0-1）
        
        # 🎯 双手动作配置
        self.prefer_both_hands = True  # 是否优先使用双手动作
        self.both_hands_probability = 0.6  # 🎯 双手动作概率提高到0.6（从0.4增加）
        
        # 🎯 从配置文件加载行为参数
        self._load_behavior_config()
        
    def _load_behavior_config(self):
        """从配置文件加载手势行为参数"""
        import yaml
        import os
        
        config_path = os.path.join(os.path.dirname(__file__), '..', 'gesture_behavior_config.yaml')
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                # 加载头部微动配置
                if 'head_micro_movements' in config:
                    self.enable_head_micro_movements = config['head_micro_movements'].get('enabled', True)
                    self.head_micro_movement_probability = config['head_micro_movements'].get('probability', 0.6)
                    print(f"✅ 头部微动配置: 启用={self.enable_head_micro_movements}, 概率={self.head_micro_movement_probability}")
                
                # 加载双手动作配置
                if 'both_hands_gestures' in config:
                    self.prefer_both_hands = config['both_hands_gestures'].get('prefer_both_hands', True)
                    self.both_hands_probability = config['both_hands_gestures'].get('probability', 0.4)
                    print(f"✅ 双手动作配置: 优先={self.prefer_both_hands}, 概率={self.both_hands_probability}")
                # 加载说话时手臂幅度限制
                if 'speech_arm_limits' in config:
                    sal = config['speech_arm_limits']
                    self._speech_arm_joint1_max = float(sal.get('joint1_max', 30.0))
                    self._speech_arm_joint2_min = float(sal.get('joint2_min', 10.0))
                    self._speech_arm_joint2_max = float(sal.get('joint2_max', 15.0))
                    print(f"✅ 说话手臂限制: 一号<={self._speech_arm_joint1_max}°, 二号{self._speech_arm_joint2_min}-{self._speech_arm_joint2_max}°")
                else:
                    self._speech_arm_joint1_max = 30.0
                    self._speech_arm_joint2_min = 10.0
                    self._speech_arm_joint2_max = 15.0
            else:
                print(f"⚠️  配置文件不存在: {config_path}，使用默认配置")
                self._speech_arm_joint1_max = 30.0
                self._speech_arm_joint2_min = 10.0
                self._speech_arm_joint2_max = 15.0
        except Exception as e:
            print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
            if not hasattr(self, '_speech_arm_joint1_max'):
                self._speech_arm_joint1_max = 30.0
                self._speech_arm_joint2_min = 10.0
                self._speech_arm_joint2_max = 15.0
        
        self.base_gestures = {
            # 基础姿态
            "neutral": [0.0] * 12,  # 中性姿态
            "rest": [0, 0, -5, 5, 0, 10, 0, 5, 5, 0, 10, 0],         # 自然休息姿态
            "alert": [0, 1, 0, 8, 0, 15, 0, 0, 8, 0, 15, 0],        # 警觉姿态（修复：从-2改为1，避免向上看）
            # 🎯 头手一体：给“纯头部动作”提供一个小幅双臂配合（避免出现“脖子动、手不动”）
            "arms_micro_support": [0, 0, -6, 8, 0, 12, 0, -6, 8, 0, 12, 0],  # 双臂微动支撑（小幅、稳定）
            
            # 右手挥手动作序列姿态 - 大幅度挥手
            "wave_right_prepare": [0, 0, 0, 0, 0, 0, 0, -70, 20, 0, 90, 0],     # 🎯 挥手准备：抬手到位
            "wave_right_left": [0, 0, 0, 0, 0, 0, 0, -70, 20, 40, 90, -30],       # 🎯 向左挥：大臂转+60度
            "wave_right_right": [0, 0, 0, 0, 0, 0, 0, -70, 20, -60, 90, -30],     # 🎯 向右挥：大臂转-60度
           
            # 右手手势系列 - 5自由度优化
            "wave_right_gentle": [0, 0, 0, 0, 0, 0, 0, -10, 20, 0, 25, -10],  # 轻柔挥手
            "wave_right_energetic": [0, 0, 0, 0, 0, 0, 0, -20, 30, 0, 90, -60], # 🎯 5DOF挥手：肘弯曲90°+小臂转动-60°
            "wave_right_dramatic": [0, 0, 0, 0, 0, 0, 0, -25, 35, 0, 100, -80], # 🎯 戏剧性挥手：更大弯曲+转动
            "point_right_casual": [0, 0, 0, 0, 0, 0, 0, -20, 12, 0, 35, 0],   # 随意指向
            "point_right_formal": [0, 0, 0, 0, 0, 0, 0, -40, 25, 0, 65, 0],   # 正式指向(增强)
            "point_right_commanding": [0, 0, 0, 0, 0, 0, 0, -50, 35, 0, 85, 0], # 指挥性指向(新增)
            "point_forward": [0, 0, 0, 0, 0, 0, 0, -70, 0, 0, 0, 0],          # 🎯 指向前方：基于挥手准备姿态，伸直手臂
            "explain_right_soft": [0, 0, 0, 0, 0, 0, 0, -15, 15, -3, 20, 0],  # 温和解释
            "explain_right_emphatic": [0, 0, 0, 0, 0, 0, 0, -35, 35, -15, 50, 0], # 强调解释(增强)
            "explain_right_passionate": [0, 0, 0, 0, 0, 0, 0, -45, 50, -20, 70, 0], # 激情解释(新增)
            "present_right": [0, 0, 0, 0, 0, 0, 0, -15, 25, 0, 20, 5],       # 展示手势
            "present_right_grand": [0, 0, 0, 0, 0, 0, 0, -25, 45, 0, 40, 15], # 盛大展示(新增)
            "invite_right": [0, 0, 0, 0, 0, 0, 0, -10, 20, 5, 15, 10],       # 邀请手势
            "invite_right_welcoming": [0, 0, 0, 0, 0, 0, 0, -30, 25, 10, 70, 20], # 🎯 5DOF握手：减少外展，增加肘弯曲
            
            # 左手挥手动作序列姿态 - 大幅度挥手
            "wave_left_prepare": [0, 0, -70, 20, 0, 90, 0, 0, 0, 0, 0, 0],     # 🎯 左手挥手准备：按右手范围
            "wave_left_left": [0, 0, -70, 20, -40, 90, -40, 0, 0, 0, 0, 0],     # 🎯 向左大幅挥动：按右手范围
            "wave_left_right": [0, 0, -70, 20, 60, 90, -40, 0, 0, 0, 0, 0],    # 🎯 向右大幅挥动：按右手范围
            
            # 双手挥手动作序列姿态 - 按右手范围设计
            "wave_both_prepare": [0, 0, -70, 20, 0, 90, 0, -70, 20, 0, 90, 0], # 🎯 双手挥手准备：两手都按右手范围
            "wave_both_out": [0, 0, -70, 20, -40, 90, 60, -70, 20, 40, 90, -60], # 🎯 双手向外挥：左手向左，右手向右
            "wave_both_in": [0, 0, -70, 20, 40, 90, -60, -70, 20, -40, 90, 60], # 🎯 双手向内挥：左手向右，右手向左
            
            # 握手动作序列姿态 - 温和礼貌
            "handshake_extend": [0, 0, 0, 0, 0, 0, 0, -25, 15, 0, 45, 0],      # 🎯 温和伸手准备
            "handshake_grip": [0, 0, 0, 0, 0, 0, 0, -25, 15, 0, 80, 10],       # 🎯 轻柔握手姿态
            "handshake_shake": [0, 0, 0, 0, 0, 0, 0, -25, 15, 0, 50, 10],      # 🎯 轻微摇动
            
            # 左手手势系列 - 从小幅度到大幅度 (2号关节现在是反向映射，需要调整符号)
            "wave_left_gentle": [0, 0, -10, 20, 0, 25, -10, 0, 0, 0, 0, 0],   # 轻柔挥手
            "wave_left_energetic": [0, 0, -20, 30, 0, 90, 60, 0, 0, 0, 0, 0], # 🎯 5DOF左手挥手：肘弯曲90°+小臂转动60°
            "wave_left_dramatic": [0, 0, -25, 35, 0, 100, 80, 0, 0, 0, 0, 0], # 🎯 戏剧性左手挥手：更大弯曲+转动
            "point_left_casual": [0, 0, -20, 12, 0, 35, 0, 0, 0, 0, 0, 0],    # 随意指向
            "point_left_formal": [0, 0, -40, 25, 0, 65, 0, 0, 0, 0, 0, 0],    # 正式指向(增强)
            "point_left_commanding": [0, 0, -50, 35, 0, 85, 0, 0, 0, 0, 0, 0], # 指挥性指向(新增)
            "point_left_forward": [0, 0, -70, 0, 0, 90, 0, 0, 0, 0, 0, 0],    # 🎯 左手指向前方：基于左手挥手准备姿态
            "explain_left_soft": [-8, 0, -15, 15, -3, 20, 0, 0, 0, 0, 0, 0],   # 温和解释+头部配合（增加头部左右-8度）
            "explain_left_emphatic": [-12, 0, -35, 35, -15, 50, 0, 0, 0, 0, 0, 0], # 强调解释+头部配合（增加头部左右-12度）
            "explain_left_passionate": [0, 0, -45, 50, -20, 70, 0, 0, 0, 0, 0, 0], # 激情解释(新增)
            "present_left": [0, 0, -15, 25, 0, 20, 5, 0, 0, 0, 0, 0],         # 展示手势
            "present_left_grand": [0, 0, -25, 45, 0, 40, 15, 0, 0, 0, 0, 0],  # 盛大展示(新增)
            "invite_left": [0, 0, -10, 20, 5, 15, 10, 0, 0, 0, 0, 0],         # 邀请手势
            "invite_left_welcoming": [0, 0, -20, 40, 15, 35, 25, 0, 0, 0, 0, 0], # 热情邀请(新增)
            
            # 🎯 左手常用手势系列
            "left_thumbs_up": [0, 0, -20, 0, 0, 80, 0, -20, 0, 0, 80, 0],      # 左手点赞
            "left_ok_gesture": [0, 0, -30, 10, 0, 45, 0, 0, 0, 0, 0, 0],       # 左手OK手势
            "left_peace_sign": [0, 0, -60, 15, 0, 75, -45, 0, 0, 0, 0, 0],     # 左手V字手势
            "left_stop_gesture": [0, 0, -70, 0, 0, 90, 0, 0, 0, 0, 0, 0],      # 左手停止手势
            "left_come_here": [0, 0, -70, 20, 0, 45, 0, 0, 0, 0, 0, 0],        # 左手过来手势
            
            # 双手协调手势 - 从适度到大幅度 (左臂2号关节现在是反向映射，调整符号)
            "open_arms_moderate": [0, 0, -8, 25, 0, 15, 0, -8, 25, 0, 15, 0], # 适度张开
            "open_arms_wide": [0, 0, -25, 50, 0, 35, 0, -25, 50, 0, 35, 0],   # 大幅张开(增强)
            "open_arms_triumphant": [0, 0, -35, 70, 0, 50, 0, -35, 70, 0, 50, 0], # 胜利张开(新增)
            "welcome_gesture": [0, 2, -12, 30, 5, 20, 8, -12, 30, -5, 20, -8], # 欢迎手势
            "welcome_grand": [0, 5, -25, 50, 15, 40, 20, -25, 50, -15, 40, -20], # 盛大欢迎(新增)
            "embrace_gentle": [0, 0, -15, 25, -3, 30, 0, -15, 25, 3, 30, 0],  # 轻柔拥抱
            "embrace_warm": [0, 0, -60, 60, 15, 50, 0, -60, 60, -15, 50, 0],    # 🤗 拥抱：双臂向前张开（减小幅度）
            "embrace_passionate": [0, 0, -40, 60, -15, 80, 0, -40, 60, 15, 80, 0], # 激情拥抱(新增)
            "clap_ready_high": [0, 0, -15, 15, 0, 25, 0, -15, 15, 0, 25, 0],  # 高位鼓掌
            "clap_ready_energetic": [0, 0, -30, 30, 0, 45, 0, -30, 30, 0, 45, 0], # 活力鼓掌(新增)
            "hands_together": [0, 0, -10, 10, 0, 30, 0, -10, 10, 0, 30, 0],   # 双手合十
            "celebration": [0, 0, -40, 60, 0, 70, 0, -40, 60, 0, 70, 0],      # 庆祝手势(新增)
            "肌肉": [0, 0, -35, 60, -15, 90, 10, -35, 60, 15, 90, 10],        # 肌肉展示：双臂外展抬起，肘屈90°
            
            # 🎯 新增：更多双手协调动作
             "both_hands_explain": [0, 0, -30, 15, 0, 45, 0, -30, 15, 0, 45, 0],
            "both_hands_present": [0, 0, -45, 15, 15, 30, 0, -45, 15, -15, 30, 0],  # 外展降到15
            "both_hands_emphasize": [0, 0, -40, 15, 0, 60, 0, -40, 15, 0, 60, 0],   # 外展降到15
            "both_hands_frame": [0, 0, -60, 20, 25, 90, 0, -60, 20, -25, 90, 0],    # 外展降到20
            "both_hands_gather": [0, 0, -45, 15, 15, 75, 0, -45, 15, -15, 75, 0],   # 外展降到15
            "both_hands_spread": [0, 0, -50, 20, -25, 45, 0, -50, 20, 25, 45, 0],   # 外展降到20
            "both_hands_up": [0, 0, -75, 15, 0, 120, 0, -75, 15, 0, 120, 0],        # 外展降到15
            "both_hands_forward": [0, 0, -60, 15, 0, 90, 0, -60, 15, 0, 90, 0],
            "both_hands_down": [0, 0, 15, 15, 0, 30, 0, 15, 15, 0, 30, 0],          # 外展降到15
            "both_hands_side": [0, 0, -30, 20, 0, 30, 0, -30, 20, 0, 30, 0],        # 外展降到20
            "both_hands_count": [0, 0, -50, 15, 0, 105, 0, -50, 15, 0, 105, 0],     # 外展降到15
            "both_hands_measure": [0, 0, -40, 15, 30, 60, 0, -40, 15, -30, 60, 0],  # 外展降到15
            "both_hands_balance": [0, 0, -30, 20, 0, 45, 0, -30, 20, 0, 45, 0],     # 外展降到20
            "both_hands_push": [0, 0, -70, 15, 0, 105, 0, -70, 15, 0, 105, 0],      # 外展降到15
            "both_hands_pull": [0, 0, -45, 15, 0, 120, 0, -45, 15, 0, 120, 0],      # 外展降到15

            # 🎯 自然对话动作：以前后（31/41）为主，外展（32/42）≤20°
            "talk_both_low":    [0, 0, -20, 10, 0, 35, 0, -20, 10, 0, 35, 0],   # 双臂微抬，自然低位
            "talk_both_mid":    [0, 0, -35, 12, 0, 55, 0, -35, 12, 0, 55, 0],   # 双臂中位，肘弯曲
            "talk_both_fwd":    [0, 0, -50, 10, 0, 80, 0, -50, 10, 0, 80, 0],   # 双臂向前伸，肘弯
            "talk_right_low":   [0, 0,   0,  0, 0,  0, 0, -20, 10, 0, 35, 0],   # 右臂低位微抬
            "talk_right_mid":   [0, 0,   0,  0, 0,  0, 0, -35, 12, 0, 55, 0],   # 右臂中位
            "talk_right_fwd":   [0, 0,   0,  0, 0,  0, 0, -50, 10, 0, 75, 0],   # 右臂向前
            "talk_right_open":  [0, 0,   0,  0, 0,  0, 0, -40, 15, 0, 65, 0],   # 右臂前伸稍展
            "talk_left_low":    [0, 0, -20, 10, 0, 35, 0,   0,  0, 0,  0, 0],   # 左臂低位微抬
            "talk_left_mid":    [0, 0, -35, 12, 0, 55, 0,   0,  0, 0,  0, 0],   # 左臂中位
            "talk_left_fwd":    [0, 0, -50, 10, 0, 75, 0,   0,  0, 0,  0, 0],   # 左臂向前
            "talk_left_open":   [0, 0, -40, 15, 0, 65, 0,   0,  0, 0,  0, 0],   # 左臂前伸稍展
            "talk_alt_rl":      [0, 0, -30, 10, 0, 50, 0, -20, 10, 0, 35, 0],   # 左高右低交替
            "talk_alt_lr":      [0, 0, -20, 10, 0, 35, 0, -30, 10, 0, 50, 0],   # 右高左低交替
            "talk_both_chest":  [0, 0, -25,  8, 0, 70, 0, -25,  8, 0, 70, 0],   # 双臂胸前，肘弯大
            "talk_both_open_low":[0, 0,-30, 18, 0, 50, 0, -30, 18, 0, 50, 0],   # 双臂微展低位

             # 🎯 脖子微转 + 手臂组合（头转向一侧，对侧手臂配合）
            "neck_left_right_arm":  [12, 0,   0,  0, 0,  0, 0, -35, 12, 0, 55, 0],  # 头左转+右臂中位
            "neck_right_left_arm":  [-12, 0, -35, 12, 0, 55, 0,   0,  0, 0,  0, 0], # 头右转+左臂中位
            "neck_left_both_fwd":   [10, 0, -25, 10, 0, 45, 0, -40, 10, 0, 65, 0],  # 头微左+双臂前伸
            "neck_right_both_fwd":  [-10, 0, -40, 10, 0, 65, 0, -25, 10, 0, 45, 0], # 头微右+双臂前伸
            "neck_left_right_low":  [15, 0,   0,  0, 0,  0, 0, -20, 10, 0, 35, 0],  # 头左转+右臂低位
            "neck_right_left_low":  [-15, 0, -20, 10, 0, 35, 0,   0,  0, 0,  0, 0], # 头右转+左臂低位
            "neck_tilt_both_mid":   [12, 0, -30, 12, 0, 50, 0, -30, 12, 0, 50, 0],  # 头歪+双臂中位
            "neck_left_explain":    [10, 0, -30, 12, 0, 50, 0, -20, 10, 0, 35, 0],  # 头微左+双臂解释
            "neck_right_explain":   [-10, 0, -20, 10, 0, 35, 0, -30, 12, 0, 50, 0], # 头微右+双臂解释

            # 🎯 摇头动作（左右摇头，幅度自然）
            "shake_head_talk":      [12, 0, -20, 10, 0, 35, 0, -20, 10, 0, 35, 0],  # 摇头位置A（配双臂）
            "shake_head_talk_b":    [-12, 0, -20, 10, 0, 35, 0, -20, 10, 0, 35, 0], # 摇头位置B（配双臂）
            "shake_head_idle":      [10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],          # 摇头待机A
            "shake_head_idle_b":    [-10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 摇头待机B
            
            
            # 🎯 新增：头部微动作（说话时的自然动作）- 减小幅度以匹配待机，增加动作多样性
            "nod_up_return": [0, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],            # 点头：脖子向上10度
            "head_micro_nod": [0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 微点头
            "head_micro_shake": [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],            # 微摇头
            "head_micro_tilt_left": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时向左歪：30度
            "head_micro_tilt_right": [-15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时向右歪：30度
            "head_micro_look_left": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时向左看：30度
            "head_micro_look_right": [-15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时向右看：30度
            "head_micro_up": [0, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 微抬头：上5度
            "head_micro_down": [0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 微低头：下10度
            "head_slight_nod": [0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 轻点头：下10度
            "head_slight_shake": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 轻摇头：左右30度
            "head_slight_tilt": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时轻歪头：30度
            "head_natural_left": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时自然向左：30度
            "head_natural_right": [-15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 说话时自然向右：30度
            # 🎯 新增：中等幅度的头部动作，增加多样性
            "head_moderate_left": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 中等向左：30度
            "head_moderate_right": [-15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 中等向右：30度
            "head_moderate_tilt_left": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 中等向左歪：30度
            "head_moderate_tilt_right": [-15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 🎯 中等向右歪：30度
            # 🎯 新增：头部组合动作（左右+上下组合）
            "head_left_up": [15, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 向左上：左右30度+上5度
            "head_left_down": [15, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 向左下：左右30度+下10度
            "head_right_up": [-15, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 向右上：左右30度+上5度
            "head_right_down": [-15, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 向右下：左右30度+下10度
            "head_thinking_pose": [5, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 思考姿态（修复：从-2改为1，避免向上看）
            "head_listening_pose": [-5, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],        # 倾听姿态
            
            # 🎯 基于挥手动作的常用手势系列
            "applaud_prepare": [0, 0, -70, 20, 0, 90, 0, -70, 20, 0, 90, 0],   # 鼓掌准备：双手抬起
            "applaud_clap": [0, 0, -50, 30, 0, 90, 0, -50, 30, 0, 90, 0],      # 鼓掌动作：双手靠近
            "stop_gesture": [0, 0, 0, 0, 0, 0, 0, -70, 0, 0, 90, -90],           # 停止手势：右手伸直
            "come_here": [0, 0, 0, 0, 0, 0, 0, -70, 20, 0, 45, 0],             # 过来手势：手掌向下
            "thumbs_up": [0, 0, -20, 0, 0, 80, 0, -20, 0, 0, 80, 0],            # 点赞手势：拇指向上
            "ok_gesture": [0, 0, 0, 0, 0, 0, 0, -30, 10, 0, 45, 0],            # OK手势：手指圈
            "peace_sign": [0, 0, 0, 0, 0, 0, 0, -60, 15, 0, 75, 45],           # V字手势：胜利手势
            
            # 头部表情手势 - 从轻微到强烈
            "nod_slight": [0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 轻微点头
            "nod_strong": [0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],             # 强烈点头(增强)
            "nod_emphatic": [0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强调点头(新增)
            "shake_slight": [8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],            # 轻微摇头
            "shake_strong": [10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强烈摇头(增强)
            "shake_dramatic": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 戏剧性摇头(新增)
            "tilt_curious": [12, -3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],          # 好奇歪头
            "tilt_dramatic": [20, -8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 戏剧性歪头(新增)
            "tilt_thoughtful": [-8, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 思考歪头
            "bow_respectful": [0, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 尊敬鞠躬
            "bow_deep": [0, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],               # 深度鞠躬(新增)
            "bow_apologetic": [0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 道歉鞠躬
            
            # 左右看动作
            "look_left_slight": [25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 轻微向左看（增加幅度：40→45）
            "look_left_strong": [25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 明显向左看（增加幅度：55→60）
            "look_left_dramatic": [25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 大幅向左看（增加幅度：55→60）
            "look_right_slight": [-25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 轻微向右看（增加幅度：40→45）
            "look_right_strong": [-25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 明显向右看（增加幅度：55→60）
            "look_right_dramatic": [-25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],   # 大幅向右看（增加幅度：55→60）
            "look_up": [0, -15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],               # 向上看
            "look_down": [0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 向下看：下10度
            
            # 情感表达手势 - 从轻微到强烈 (左臂2号关节调整符号)
            "think_light": [0, -3, 0, 0, 0, 35, 0, 0, 0, 0, 0, 0],           # 轻度思考
            "think_deep": [0, -12, 0, 0, 0, 70, 0, 0, 0, 0, 0, 0],           # 深度思考(增强)
            "think_profound": [0, -18, -5, 5, 0, 90, 0, 0, 0, 0, 0, 0],       # 深邃思考(新增)
            "surprise_mild": [0, -2, -3, 12, 0, 15, 0, -3, 12, 0, 15, 0],     # 轻微惊讶
            "surprise_strong": [0, -8, -15, 35, 0, 40, 0, -15, 35, 0, 40, 0], # 强烈惊讶(增强)
            "surprise_shocked": [0, -12, -25, 50, 0, 60, 0, -25, 50, 0, 60, 0], # 震惊(新增)
            "confident_relaxed": [0, 0, 0, 0, 0, 0, 0, -10, 8, 0, 15, 0],    # 放松自信
            "confident_assertive": [0, 0, 0, 0, 0, 0, 0, -30, 25, 0, 45, 0], # 坚定自信(增强)
            "confident_commanding": [0, 0, 0, 0, 0, 0, 0, -45, 40, 0, 65, 0], # 指挥性自信(新增)
            "curious_lean": [5, -3, -5, 8, 0, 20, 0, 0, 0, 0, 0, 0],          # 好奇前倾
            "curious_intense": [15, -8, -15, 25, 0, 40, 0, 0, 0, 0, 0, 0],    # 强烈好奇(新增)
            "attentive_listen": [0, 0, 0, 5, 0, 10, 0, 0, 5, 0, 10, 0],      # 专注倾听
            "attentive_focused": [0, 0, 0, 15, 0, 25, 0, 0, 15, 0, 25, 0],   # 高度专注(新增)
            
            # 交互手势
            "point_forward_soft": [0, 0, 0, 0, 0, 0, 0, -20, 12, 0, 35, 0],  # 温和指向前方
            "point_forward_firm": [0, 0, 0, 0, 0, 0, 0, -30, 18, 0, 45, 0],  # 坚定指向前方
            "gesture_come": [0, 0, 0, 0, 0, 0, 0, -15, 20, 0, 30, 15],       # 招手过来
            "gesture_stop": [0, 0, 0, 0, 0, 0, 0, -25, 0, 0, 0, 0],          # 停止手势
            "gesture_ok": [0, 0, 0, 0, 0, 0, 0, -12, 15, 0, 25, 20],         # OK手势
            "applaud_ready": [0, 0, -18, 18, 0, 28, 0, -18, 18, 0, 28, 0],   # 准备鼓掌
            
            # 头部表情手势
            "nod_slight": [0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 轻微点头
            "nod_strong": [0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],             # 强烈点头
            "shake_slight": [10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],            # 轻微摇头
            "shake_strong": [15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强烈摇头
            "tilt_curious": [12, -3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],          # 好奇歪头
            "tilt_thoughtful": [-8, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 思考歪头
            "bow_respectful": [0, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 尊敬鞠躬
            "bow_apologetic": [0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 道歉鞠躬
            
            # 情感表达手势
            "think_deep": [0, -8, 0, 0, 0, 50, 0, 0, 0, 0, 0, 0],            # 深度思考
            "think_light": [0, -3, 0, 0, 0, 35, 0, 0, 0, 0, 0, 0],           # 轻度思考
            "curious_lean": [5, -3, 5, 8, 0, 20, 0, 0, 0, 0, 0, 0],          # 好奇前倾
            "attentive_listen": [0, 0, 0, 5, 0, 10, 0, 0, 5, 0, 10, 0],      # 专注倾听
            "confident_relaxed": [0, 0, 0, 0, 0, 0, 0, -10, 8, 0, 15, 0],    # 放松自信
            "confident_assertive": [0, 0, 0, 0, 0, 0, 0, -20, 15, 0, 25, 0], # 坚定自信
            
            # 交互手势
            "point_forward_firm": [0, 0, 0, 0, 0, 0, 0, -30, 18, 0, 45, 0],  # 坚定指向前方
            "gesture_come": [0, 0, 0, 0, 0, 0, 0, -15, 20, 0, 30, 15],       # 招手过来
            "gesture_stop": [0, 0, 0, 0, 0, 0, 0, -25, 0, 0, 0, 0],          # 停止手势
            "gesture_ok": [0, 0, 0, 0, 0, 0, 0, -12, 15, 0, 25, 20],         # OK手势
        }
        # 🎯 用于“每个动作都带头动作”的左右交替
        self._forced_head_lr_sign = 1
        # 🎯 说话阶段手臂幅度增强目标（度）
        # 按你的要求：手臂动作至少约 5 度，避免肉眼看不出动静
        self._min_arm_amplitude_deg = 5.0
        # 说话时手臂幅度上限由 _load_behavior_config 从 yaml 加载（默认一号约30度，二号10-15度）
        
        # 丰富的意图到手势映射规则 - 增加双手动作和头部微动
        self.intent_gesture_map = {
            "greeting": [
                ["wave_right_gentle", "wave_left_gentle", "wave_right_energetic", "wave_right_dramatic", "both_hands_up"],
                ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "welcome_grand", "both_hands_present"],
                ["head_natural_left", "head_natural_right", "head_micro_up", "head_left_up", "head_right_up"],
                ["rest", "neutral", "head_micro_tilt_left", "head_micro_tilt_right"]
            ],
            "farewell": [
                ["wave_right_gentle", "wave_left_gentle", "wave_right_energetic", "wave_left_dramatic", "both_hands_side"],
                ["both_hands_down", "head_natural_left", "head_natural_right", "head_micro_up"],
                ["hands_together", "open_arms_moderate", "rest", "head_natural_left", "head_natural_right"],
                ["neutral", "head_micro_tilt_left", "head_micro_tilt_right"]
            ],
            "explanation": [
                ["explain_right_soft", "explain_left_soft", "present_right", "present_left", "both_hands_explain"],
                ["explain_right_emphatic", "explain_left_emphatic", "both_hands_present", "both_hands_emphasize"],
                ["point_right_casual", "point_left_casual", "both_hands_forward", "both_hands_measure"],
                # 🎯 减少上下动作，增加左右动作 - 移除上下动作
                ["curious_lean", "attentive_listen", "head_natural_left", "head_natural_right", "head_micro_look_left", "head_micro_look_right"],
                ["rest", "neutral", "head_micro_tilt_left", "head_micro_tilt_right", "head_micro_shake", "head_moderate_left", "head_moderate_right", "head_moderate_tilt_left", "head_moderate_tilt_right", "look_left_slight", "look_right_slight"]
            ],
            "question": [
                ["think_light", "think_deep", "think_profound", "tilt_thoughtful", "head_thinking_pose"],
                ["curious_lean", "curious_intense", "tilt_curious", "tilt_dramatic", "head_slight_tilt"],
                ["attentive_listen", "attentive_focused", "head_listening_pose"],
                ["invite_right", "invite_left", "invite_right_welcoming", "both_hands_gather"],
                ["rest", "neutral", "head_micro_tilt_right", "head_micro_look_left", "head_natural_left"]
            ],
            "emphasis": [
                ["point_forward_firm", "point_right_commanding", "point_left_commanding", "both_hands_emphasize"],
                ["explain_right_passionate", "explain_left_passionate", "confident_commanding", "both_hands_push"],
                ["gesture_ok", "both_hands_forward", "head_natural_left", "head_natural_right"],
                ["present_right_grand", "present_left_grand", "both_hands_frame"],
                ["rest", "neutral", "head_natural_left", "head_natural_right", "head_micro_look_left", "head_micro_look_right", "head_moderate_left", "head_moderate_right", "head_moderate_tilt_left", "head_moderate_tilt_right"]
            ],
            "excitement": [
                ["wave_right_dramatic", "wave_left_dramatic", "celebration", "both_hands_up"],
                ["open_arms_triumphant", "embrace_passionate", "welcome_grand", "both_hands_spread"],
                ["clap_ready_energetic", "surprise_strong", "both_hands_side"],
                ["confident_commanding", "head_natural_left", "head_natural_right", "head_micro_up"],
                ["rest", "neutral", "head_micro_tilt_left", "head_micro_tilt_right"]
            ],
            "agreement": [
                ["gesture_ok", "head_natural_left", "head_natural_right", "head_micro_up", "head_left_up", "head_right_up"],
                ["wave_right_gentle", "wave_left_gentle", "applaud_ready", "clap_ready_energetic", "both_hands_present"],
                ["confident_relaxed", "confident_assertive", "attentive_listen", "both_hands_balance"],
                ["rest", "neutral", "head_micro_shake", "head_micro_tilt_left", "head_micro_tilt_right", "head_moderate_left", "head_moderate_right", "head_moderate_tilt_left", "head_moderate_tilt_right"]
            ],
            "disagreement": [
                ["shake_strong", "shake_dramatic", "shake_slight", "gesture_stop", "head_slight_shake"],
                ["tilt_thoughtful", "tilt_dramatic", "think_light", "think_deep", "head_thinking_pose"],
                ["confident_assertive", "confident_commanding", "attentive_listen", "both_hands_down"],
                ["rest", "neutral", "head_micro_shake", "head_micro_tilt_left", "head_natural_right"]
            ],
            "surprise": [
                ["surprise_mild", "surprise_strong", "surprise_shocked", "both_hands_up"],
                ["open_arms_wide", "open_arms_triumphant", "both_hands_spread"],
                ["tilt_dramatic", "curious_intense", "head_slight_tilt"],
                ["rest", "neutral", "head_micro_tilt_left", "head_natural_right"]
            ],
            "presentation": [
                ["present_right", "present_left", "both_hands_present", "both_hands_frame"],
                ["explain_right_emphatic", "explain_left_emphatic", "both_hands_explain"],
                ["point_forward_firm", "both_hands_forward", "both_hands_measure"],
                ["open_arms_moderate", "both_hands_side", "head_natural_left", "head_micro_look_right"],
                ["rest", "neutral", "head_micro_tilt_right", "head_natural_right"]
            ],
            "thinking": [
                ["think_deep", "think_profound", "head_thinking_pose"],
                ["tilt_thoughtful", "curious_lean", "head_slight_tilt"],
                ["attentive_listen", "head_listening_pose", "head_natural_right", "head_micro_look_left"],
                ["rest", "neutral", "head_micro_tilt_right", "head_natural_left"]
            ],
            "neutral": [
                # 🎯 优先左右动作，减少上下动作
                ["rest", "neutral", "head_micro_tilt_left", "head_micro_tilt_right", "head_moderate_left", "head_moderate_right"],
                ["head_micro_shake", "head_micro_look_left", "head_micro_look_right", "head_moderate_tilt_left", "head_moderate_tilt_right"],
                ["head_natural_left", "head_natural_right", "head_moderate_left", "head_moderate_right", "look_left_slight", "look_right_slight"],
                ["attentive_listen", "head_listening_pose"]
            ]
        }
        
        # 情感到手势强度的映射
        self.emotion_intensity_map = {
            "happy": 1.2,      # 动作幅度增加20%
            "excited": 1.4,    # 动作幅度增加40%
            "sad": 0.7,        # 动作幅度减少30%
            "angry": 1.3,      # 动作幅度增加30%
            "surprised": 1.1,  # 动作幅度增加10%
            "neutral": 1.0     # 正常幅度
        }
        
        # 合并外部自定义手势和序列
        self._load_custom_definitions()
        self._load_custom_action_config()
    def _generate_dynamic_gesture(self, action_description: str) -> tuple:
        """根据动作描述动态生成手势
        
        Args:
            action_description: 动作描述，如"左手举高", "右手指向左边", "低头思考"等
            
        Returns:
            tuple: (gesture_name, joint_angles, duration)
        """
        import re
        import random
        
        # 初始化关节角度（12个关节）
        angles = [0.0] * 12
        duration = 2.0  # 默认2秒
        
        desc = action_description.lower()
        
        # 🎯 更严格的头部动作检测 - 避免误判普通文本
        head_patterns = [
            r"(头|脖子)(向|往)?(左|右|上|下)",
            r"(点头|摇头|抬头|低头)",
            r"(看|望)(向|往)?(左|右|上|下)",
        ]
        
        head_detected = False
        for pattern in head_patterns:
            if re.search(pattern, desc):
                head_detected = True
                if any(word in desc for word in ["左", "向左"]):
                    angles[0] = 30  # 头向左
                elif any(word in desc for word in ["右", "向右"]):
                    angles[0] = -30  # 头向右
                elif any(word in desc for word in ["上", "向上", "抬头"]):
                    angles[1] = -20  # 头向上
                # 🎯 不要任何低头动作：下/低头/点头 不设正 pitch，保持 0
                elif any(word in desc for word in ["下", "向下", "低头", "点头"]):
                    angles[1] = 0.0  # 禁止低头
                elif any(word in desc for word in ["摇头"]):
                    angles[0] = 25  # 摇头
                break
        
        # 🎯 如果不是明确的动作描述，生成手部+头部配合的自然姿态
        if not head_detected and not any(word in desc for word in ["左手", "右手", "双手", "左臂", "右臂"]):
            # 生成自然的解释姿态：右手轻微手势 + 头部微动
            angles[7] = -20   # 右前后
            angles[8] = 15    # 右外展  
            angles[10] = 30   # 右肘
            angles[0] = random.choice([-8, 0, 8])  # 头部轻微左右
            duration = 3.0
            
            print(f"🎭 生成自然解释姿态（非特定动作）")
            return f"natural_explanation", angles, duration
        
        # 🎯 左手动作检测
        if any(word in desc for word in ["左手", "左臂"]):
            if any(word in desc for word in ["举", "抬", "向上"]):
                angles[2] = -60  # 左前后
                angles[3] = 30   # 左外展
                angles[5] = 80   # 左肘弯曲
            elif any(word in desc for word in ["放下", "向下"]):
                angles[2] = 20   # 左前后
                angles[3] = 10   # 左外展
                angles[5] = 20   # 左肘
            elif any(word in desc for word in ["伸直", "前伸"]):
                angles[2] = -70  # 左前后
                angles[3] = 0    # 左外展
                angles[5] = 0    # 左肘伸直
            elif any(word in desc for word in ["外展", "张开"]):
                angles[2] = -30  # 左前后
                angles[3] = 60   # 左外展
                angles[5] = 30   # 左肘
            elif any(word in desc for word in ["指向", "指着"]):
                angles[2] = -50  # 左前后
                angles[3] = 20   # 左外展
                angles[5] = 45   # 左肘
                if any(word in desc for word in ["左", "向左"]):
                    angles[4] = 30  # 左大臂转
                elif any(word in desc for word in ["右", "向右"]):
                    angles[4] = -30  # 左大臂转
        
        # 🎯 右手动作检测
        if any(word in desc for word in ["右手", "右臂"]):
            if any(word in desc for word in ["举", "抬", "向上"]):
                angles[7] = -60  # 右前后
                angles[8] = 30   # 右外展
                angles[10] = 80  # 右肘弯曲
            elif any(word in desc for word in ["放下", "向下"]):
                angles[7] = 20   # 右前后
                angles[8] = 10   # 右外展
                angles[10] = 20  # 右肘
            elif any(word in desc for word in ["伸直", "前伸"]):
                angles[7] = -70  # 右前后
                angles[8] = 0    # 右外展
                angles[10] = 0   # 右肘伸直
            elif any(word in desc for word in ["外展", "张开"]):
                angles[7] = -30  # 右前后
                angles[8] = 60   # 右外展
                angles[10] = 30  # 右肘
            elif any(word in desc for word in ["指向", "指着"]):
                angles[7] = -50  # 右前后
                angles[8] = 20   # 右外展
                angles[10] = 45  # 右肘
                if any(word in desc for word in ["左", "向左"]):
                    angles[9] = 30  # 右大臂转
                elif any(word in desc for word in ["右", "向右"]):
                    angles[9] = -30  # 右大臂转
        
        # 🎯 双手动作检测
        if any(word in desc for word in ["双手", "两手", "双臂"]):
            if any(word in desc for word in ["举", "抬", "向上"]):
                # 双手举起
                angles[2] = -50; angles[3] = 30; angles[5] = 60  # 左手
                angles[7] = -50; angles[8] = 30; angles[10] = 60  # 右手
            elif any(word in desc for word in ["张开", "展开"]):
                # 双手张开
                angles[2] = -20; angles[3] = 50; angles[5] = 20  # 左手
                angles[7] = -20; angles[8] = 50; angles[10] = 20  # 右手
            elif any(word in desc for word in ["合拢", "合十"]):
                # 双手合十
                angles[2] = -40; angles[3] = 10; angles[5] = 60  # 左手
                angles[7] = -40; angles[8] = 10; angles[10] = 60  # 右手
        
        # 🎯 特殊动作检测
        if any(word in desc for word in ["思考", "沉思"]):
            # 思考姿态：右手托腮（不低头，头保持水平或微抬）
            angles[0] = 5    # 头微右
            angles[1] = 0    # 不低头
            angles[7] = -35  # 右前后
            angles[8] = 15   # 右外展
            angles[10] = 70  # 右肘
            duration = 3.0
        
        elif any(word in desc for word in ["鼓掌", "拍手"]):
            # 鼓掌准备
            angles[2] = -40; angles[3] = 20; angles[5] = 60  # 左手
            angles[7] = -40; angles[8] = 20; angles[10] = 60  # 右手
            duration = 1.5
        
        elif any(word in desc for word in ["敬礼", "致敬"]):
            # 敬礼姿态
            angles[7] = -60  # 右前后
            angles[8] = 20   # 右外展
            angles[10] = 90  # 右肘
            duration = 2.5
        
        # 生成手势名称
        gesture_name = f"dynamic_{action_description.replace(' ', '_')}"
        
        print(f"🎭 动态生成手势: {gesture_name}")
        print(f"   描述: {action_description}")
        print(f"   关节角度: {angles}")
        print(f"   时长: {duration}s")
        
        return gesture_name, angles, duration
    
    def _adjust_head_gesture_duration(self, gesture_name: str, duration: float) -> float:
        """调整头部手势的时长
        
        Args:
            gesture_name: 手势名称
            duration: 原始时长
            
        Returns:
            调整后的时长
        """
        # 如果是头部手势，应用速度缩放因子
        if gesture_name in self.head_gestures:
            adjusted_duration = duration / self.head_speed_factor
            
            # 🎯 上下动作额外减速50%
            if gesture_name in self.vertical_head_gestures:
                adjusted_duration = adjusted_duration * 1.5  # 再减速50%
                print(f"🐢 [头部上下动作额外减速] {gesture_name}: {duration:.2f}s → {adjusted_duration:.2f}s (速度: {self.head_speed_factor*100/1.5:.0f}%)")
            else:
                print(f"🐢 [头部左右动作] {gesture_name}: {duration:.2f}s → {adjusted_duration:.2f}s (速度: {self.head_speed_factor*100:.0f}%)")
            
            return adjusted_duration
        return duration
    
    def _adjust_sequence_head_duration(self, sequence: List[tuple]) -> List[tuple]:
        """调整序列中所有头部手势的时长
        
        Args:
            sequence: 手势序列 [(gesture_name, duration), ...]
            
        Returns:
            调整后的序列
        """
        adjusted_sequence = []
        for gesture_name, duration in sequence:
            adjusted_duration = self._adjust_head_gesture_duration(gesture_name, duration)
            adjusted_sequence.append((gesture_name, adjusted_duration))
        return adjusted_sequence
    
    def plan_gesture_sequence(self, semantic_info: Dict) -> List[Dict]:
        """
        基于语音时长规划手势序列 - 主要接口
        
        Args:
            semantic_info: 包含以下字段的字典
                - intent: 意图 (如 'explanation', 'greeting')
                - emotion: 情感 (如 'neutral', 'happy')
                - speech_duration: 语音时长(秒) - 关键参数
                - word_count: 字数 (用于估算时长，如果没有speech_duration)
                - detected_actions: 检测到的动作列表 (新增)
                - enable_linguistic_mode: 是否启用语言驱动模式 (新增)
        
        Returns:
            手势序列列表，每个元素包含gesture_name, joint_angles, duration
        """
        
        # 🎯 按你的要求：统一使用传统模式，不再启用增强语言驱动策略
        # 无论 enable_linguistic_mode 是否为 True，始终走下面这套原有逻辑。
        intent = semantic_info.get('intent', 'explanation')
        emotion = semantic_info.get('emotion', 'neutral')
        detected_actions = semantic_info.get('detected_actions', [])
        
        # 🎯 关键改进：优先使用语音时长
        speech_duration = semantic_info.get("speech_duration", None)
        text_length = semantic_info.get("word_count", 10)
        
        # 确定实际语音时长
        if speech_duration is not None:
            total_duration = speech_duration
            print(f"🎤 使用提供的语音时长: {total_duration:.1f}秒")
        else:
            # 根据字数估算语音时长（中文约2-3字/秒）
            total_duration = text_length * 0.4  # 稍慢一些，2.5字/秒
            print(f"⚠️  根据{text_length}字估算语音时长: {total_duration:.1f}秒")
        
        # � 舞蹈关键词触发且无语音时长：使用默认舞蹈时长下限，避免仅播放一个极短片段
        # 仅当未提供 speech_duration（即使用字数估算）时生效
        if speech_duration is None and detected_actions:
            dance_min_map = {
                "dance_short": 15.0,
                "dance_isolation": 16.0,
                "dance": 30.0,
                "dance_loop": 30.0,
                "dance_mech": 30.0,
            }
            min_floor = 0.0
            for a in detected_actions:
                if a in dance_min_map:
                    min_floor = max(min_floor, dance_min_map[a])
                elif a.startswith("dance"):
                    min_floor = max(min_floor, 30.0)
            if min_floor > 0.0 and total_duration < min_floor:
                print(f"🎵 舞蹈触发且无语音时长，使用默认舞蹈时长: {min_floor:.1f}秒")
                total_duration = min_floor

        # ✊ 动作性手势（点赞/握手等）需完整执行：为单一动作设置最小时长下限
        if detected_actions and len(detected_actions) == 1:
            full_min_map = {
                "thumbs_up": 1.5,   # 点赞完整动作时长（覆盖短文本）
                "handshake": 3.4,   # 握手序列(去掉末尾rest)约3.4s
                "muscle_pose": 2.0, # 秀肌肉/肌肉展示
            }
            # 合并自定义 full_min 配置
            try:
                if hasattr(self, "_custom_action_full_min") and self._custom_action_full_min:
                    for k, v in self._custom_action_full_min.items():
                        full_min_map[k] = float(v)
            except Exception:
                pass
            a0 = detected_actions[0]
            if a0 in full_min_map and total_duration < full_min_map[a0]:
                print(f"✊ 动作性手势，确保完整执行: 调整总时长为 {full_min_map[a0]:.1f}秒")
                total_duration = full_min_map[a0]
        
        # 🎯 检查是否有具体动作指令
        # 🎯 关键修复：强制启用flow_mode，避免插入不必要的rest过渡
        flow_mode = True  # 强制启用流畅模式
        print(f"🎯 强制启用flow_mode，避免插入不必要的rest过渡")
        # 🎯 修复：对于动作序列，强制启用flow_mode避免插入不必要的rest过渡
        if detected_actions:
            flow_mode = True  # 强制启用流畅模式，避免在动作间插入rest
            print(f"🎯 检测到动作序列，强制启用flow_mode: {detected_actions}")
        
        # 优先处理带时间轴的语义时间片
        action_timeline = semantic_info.get('action_timeline', None)
        # 兼容上游未提供 utterance_text 的情况，回退到 clean_text / original_text
        utterance_text = (
            semantic_info.get('utterance_text')
            or semantic_info.get('clean_text')
            or semantic_info.get('original_text')
        )
        timeline_based = False
        sequence_gesture_count = 0  # 🎯 默认没有序列动作
        if action_timeline:
            print("🧭 使用显式时间轴对齐")
            sequence, sequence_gesture_count = self._generate_timeline_aligned_sequence(action_timeline, total_duration, emotion, flow_mode, intent, semantic_info)
            timeline_based = True
        elif utterance_text:
            # 基于文本构建时间轴，按语义落点触发动作，避免所有动作在开头一次性播放
            print("🧭 使用文本分句时间轴对齐")
            built_timeline = self._build_action_timeline_from_text(str(utterance_text), total_duration)
            sequence, sequence_gesture_count = self._generate_timeline_aligned_sequence(built_timeline, total_duration, emotion, flow_mode, intent, semantic_info)
            timeline_based = True
        elif detected_actions:
            print(f"🧭 无文本，仅有多动作 -> 按总时长均分时间轴: {detected_actions}")
            even_timeline = self._build_even_action_timeline(detected_actions, total_duration)
            sequence, sequence_gesture_count = self._generate_timeline_aligned_sequence(even_timeline, total_duration, emotion, flow_mode, intent, semantic_info)
            timeline_based = True
        else:
            # 获取手势组和基础参数
            gesture_groups = self.intent_gesture_map.get(intent, self.intent_gesture_map["neutral"])
            base_duration = self._get_base_duration(emotion)
            sequence = self._generate_timed_gesture_sequence(gesture_groups, total_duration, base_duration, emotion, intent, flow_mode)
        
        # 将时间轴路径中出现的长时间 attentive_listen 替换为语义填充，避免“长时间听”现象
        if timeline_based:
            sequence = self._replace_long_listen_with_filler(sequence, emotion, intent, flow_mode, max_single=1.2)
        
        end_settle = semantic_info.get('end_settle', 'auto')
        sequence = self._post_process_sequence(sequence, total_duration, intent, emotion, flow_mode, end_settle)
        
        # 生成最终的手势数据
        final_sequence = []
        for seq_idx, (gesture_name, duration) in enumerate(sequence):
            # 🎯 调试：打印embrace相关的时长信息
            if "embrace" in gesture_name.lower():
                print(f"🔍 [调试] embrace手势时长: {gesture_name} = {duration}秒")
                # 🎯 确保embrace动作至少有2.5秒的时长
                if duration < 2.5:
                    print(f"🔍 [修正] embrace时长过短，从{duration}秒调整为2.5秒")
                    duration = 2.5
            
            # 🐢 调整头部手势的时长
            adjusted_duration = self._adjust_head_gesture_duration(gesture_name, duration)
            
            # 🎯 调试：如果是embrace，再次打印调整后的时长
            if "embrace" in gesture_name.lower():
                print(f"🔍 [调试] embrace调整后时长: {gesture_name} = {adjusted_duration}秒")
            
            # 🎯 获取基础手势角度，如果不存在则动态生成
            if gesture_name in self.base_gestures:
                base_angles = self.base_gestures[gesture_name]
            else:
                # 🎭 动态生成未定义的手势
                print(f"🎭 未找到手势 '{gesture_name}'，尝试动态生成...")
                try:
                    dynamic_name, dynamic_angles, dynamic_duration = self._generate_dynamic_gesture(gesture_name)
                    # 将动态生成的手势添加到手势库
                    self.base_gestures[gesture_name] = dynamic_angles
                    base_angles = dynamic_angles
                    # 使用动态生成的时长
                    adjusted_duration = dynamic_duration
                    print(f"✅ 成功生成动态手势: {gesture_name}")
                except Exception as e:
                    print(f"❌ 动态生成手势失败: {e}")
                    base_angles = self.base_gestures["neutral"]
            
            # 🎯 对于拥抱等关键动作，不添加随机变化，保持精确角度
            if gesture_name in ["embrace_warm", "embrace_gentle", "embrace_passionate", "rest", "neutral"]:
                # 关键动作使用精确角度，不添加随机变化
                final_angles = self._apply_emotion_intensity(base_angles.copy(), emotion)
            else:
                # 其他动作添加自然变化和情感调节
                varied_angles = self.add_natural_variations(base_angles.copy())
                final_angles = self._apply_emotion_intensity(varied_angles, emotion)

            # 🎯 强制“头+手一体联动”：
            # - 手臂/双手动作：必须带头部(0/1)
            # - 头部动作：必须带双臂(2-11)微动
            def _is_head_gesture(n: str) -> bool:
                try:
                    nn = str(n)
                except Exception:
                    return False
                return (
                    nn.startswith("head_")
                    or nn.startswith("nod_")
                    or nn.startswith("look_")
                    or ("shake_head" in nn)
                    or ("tilt_head" in nn)
                )

            def _has_head_motion(a: List[float]) -> bool:
                try:
                    return (abs(float(a[0])) + abs(float(a[1]))) >= 1.0
                except Exception:
                    return False

            def _has_arm_motion(a: List[float]) -> bool:
                try:
                    s = 0.0
                    for i in range(2, 12):
                        s += abs(float(a[i]))
                    return s >= 1.0
                except Exception:
                    return False

            is_head = _is_head_gesture(gesture_name)
            is_hand = (not is_head) and (gesture_name not in ("neutral", "rest", "attentive_listen"))

            # 手臂动作必须带头：如果当前头部角度几乎为0，则注入一个左右头部动作（优先组合动作）
            if is_hand and (not _has_head_motion(final_angles)):
                # 🎯 不选任何低头动作，只保留左右、抬头、微动
                head_pool = [
                    "head_left_up", "head_right_up",  # 左右+上（无 head_*_down）
                    "head_micro_tilt_left", "head_micro_tilt_right",
                    "head_micro_look_left", "head_micro_look_right",
                    "head_natural_left", "head_natural_right",
                    "head_moderate_left", "head_moderate_right",
                    "head_micro_up",  # 仅抬头微动，无 head_micro_down
                ]
                head_pool = [h for h in head_pool if h in self.base_gestures]
                if head_pool:
                    hname = random.choice(head_pool)
                    ha = self.base_gestures[hname]
                    final_angles[0] = ha[0]
                    final_angles[1] = ha[1]

            # 头部动作必须带手：如果当前手臂角度几乎全0，则注入“真实双手动作”（不是微动）
            # 目标：说话时头和手臂一体联动，避免出现“脖子动、手不动/只微动”的观感
            if is_head and (not _has_arm_motion(final_angles)):
                # 优先更大幅度、更像“说话配合”的双手动作
                strong_both_hands = [
                    "both_hands_frame",
                    "both_hands_spread",
                    "both_hands_push",
                    "both_hands_pull",
                    "both_hands_forward",
                    "both_hands_present",
                    "both_hands_emphasize",
                    "both_hands_explain",
                    "both_hands_side",
                    "both_hands_gather",
                    "both_hands_up",
                    "open_arms_wide",
                    "welcome_grand",
                    "celebration",
                ]
                strong_both_hands = [g for g in strong_both_hands if g in self.base_gestures]
                # 兜底：任意 both_hands_*
                if not strong_both_hands:
                    strong_both_hands = [k for k in self.base_gestures.keys() if str(k).startswith("both_hands_")]

                if strong_both_hands:
                    arms_name = random.choice(strong_both_hands)
                    arms_base = self.base_gestures.get(arms_name)
                    if isinstance(arms_base, list) and len(arms_base) == 12:
                        # 对手臂也应用情感强度 + 自然变化，让“头+手”更像一体表达
                        try:
                            arms_varied = self.add_natural_variations(arms_base.copy())
                            arms_final = self._apply_emotion_intensity(arms_varied, emotion)
                        except Exception:
                            arms_final = arms_base
                        for i in range(2, 12):
                            final_angles[i] = arms_final[i]
                else:
                    # 最后兜底：仍然给一点点手臂支撑（避免完全静止）
                    aa = self.base_gestures.get("arms_micro_support")
                    if isinstance(aa, list) and len(aa) == 12:
                        for i in range(2, 12):
                            final_angles[i] = aa[i]
            
            # 对侧轻度配合：在强侧手势时为对侧注入小幅同步
            final_angles = self._apply_contralateral_support(final_angles, gesture_name, emotion)

            # 🎯 终极强制：说话阶段“每个动作都要有头动作” 
            # 规则：除 rest/neutral/attentive_listen/interrupt_* 以及 idle_* 外，若头(0/1)几乎为0，则强制注入左右头动作（左右交替）
            try:
                gname = str(gesture_name)
            except Exception:
                gname = ""

            def _is_exempt_from_forced_head(n: str) -> bool:
                if not n:
                    return True
                if n in ("rest", "neutral", "attentive_listen"):
                    return True
                if n.startswith("interrupt_"):
                    return True
                if n.startswith("idle_"):
                    return True
                return False

            if (not _is_exempt_from_forced_head(gname)) and (not _has_head_motion(final_angles)):
                # 左右交替选头动作（仅左右/抬头，不要任何低头）
                left_pool = ["head_left_up", "head_micro_look_left", "head_micro_tilt_left", "head_natural_left", "head_moderate_left"]
                right_pool = ["head_right_up", "head_micro_look_right", "head_micro_tilt_right", "head_natural_right", "head_moderate_right"]
                if getattr(self, "_forced_head_lr_sign", 1) >= 0:
                    pool = [h for h in left_pool if h in self.base_gestures]
                    self._forced_head_lr_sign = -1
                else:
                    pool = [h for h in right_pool if h in self.base_gestures]
                    self._forced_head_lr_sign = 1
                if not pool:
                    pool = [h for h in (left_pool + right_pool) if h in self.base_gestures]
                if pool:
                    hname = random.choice(pool)
                    ha = self.base_gestures[hname]
                    final_angles[0] = ha[0]
                    final_angles[1] = ha[1]

            # 🎯 说话时手臂幅度限制：一号(肩前后)约30度，二号(肩外展)10-15度，更像人、无大开感
            # 仅对填充动作生效，序列动作（挥手/点赞等）保持原幅度
            try:
                is_sequence = timeline_based and seq_idx < sequence_gesture_count
                if (not is_sequence and gesture_name not in ("rest", "neutral") and
                        hasattr(self, '_speech_arm_joint1_max')):
                    j1_max = float(self._speech_arm_joint1_max)
                    j2_min, j2_max = float(self._speech_arm_joint2_min), float(self._speech_arm_joint2_max)
                    limited = list(final_angles)
                    for idx in (2, 7):  # 一号关节：肩前后
                        v = float(limited[idx])
                        limited[idx] = max(-j1_max, min(j1_max, v))
                    for idx in (3, 8):  # 二号关节：肩外展
                        v = float(limited[idx])
                        if abs(v) < 0.5:
                            limited[idx] = (j2_min + j2_max) / 2.0 if v >= 0 else -(j2_min + j2_max) / 2.0
                        elif abs(v) > j2_max:
                            limited[idx] = j2_max if v > 0 else -j2_max
                        elif abs(v) < j2_min:
                            limited[idx] = j2_min if v > 0 else -j2_min
                        # else: 已在10-15范围内，保持
                    final_angles = limited
            except Exception:
                pass
            
            # 🎯 进一步：若手臂幅度太小，按比例放大（避免肉眼看不出动静）
            try:
                max_arm = 0.0
                for idx in range(2, 12):
                    max_arm = max(max_arm, abs(float(final_angles[idx])))
                if (gesture_name not in ("rest", "neutral")
                        and max_arm < self._min_arm_amplitude_deg
                        and max_arm > 0.5):
                    factor = self._min_arm_amplitude_deg / max_arm
                    factor = min(factor, 3.0)
                    boosted = list(final_angles)
                    for idx in range(2, 12):
                        boosted[idx] = boosted[idx] * factor
                    final_angles = boosted
            except Exception:
                pass
            
            # 🎯 禁止任何低头动作：头部 pitch（关节1）只允许≤0，不允许向下
            try:
                if float(final_angles[1]) > 0:
                    final_angles = list(final_angles)
                    final_angles[1] = 0.0
            except Exception:
                pass
            
            # 🎯 说话/待机时：手臂内外展(肩外展 joint 3,8) 不能有负值，必须 >= 0
            try:
                is_seq = timeline_based and seq_idx < sequence_gesture_count
                if not is_seq:  # 非序列动作（说话随机、待机、填充）均限制
                    fa = list(final_angles)
                    for idx in (3, 8):  # left_shoulder_roll, right_shoulder_roll
                        if idx < len(fa) and float(fa[idx]) < 0:
                            fa[idx] = 0.0
                    final_angles = fa
            except Exception:
                pass
            
            final_sequence.append({
                'gesture_name': gesture_name,
                'joint_angles': final_angles,
                'duration': adjusted_duration,  # 使用调整后的时长
                'is_sequence_action': False  # 🎯 默认为非序列动作，后续会更新
            })
        
        print(f"✅ 生成{len(final_sequence)}个手势，总时长{sum(g['duration'] for g in final_sequence):.1f}秒")
        
        # 🎯 标记序列动作（前sequence_gesture_count个手势）
        if sequence_gesture_count > 0:
            for i in range(min(sequence_gesture_count, len(final_sequence))):
                final_sequence[i]['is_sequence_action'] = True
            print(f"🎯 已标记前{min(sequence_gesture_count, len(final_sequence))}个手势为序列动作（对话结束时继续完成）")
        
        return final_sequence

    def _load_custom_definitions(self):
        """从同目录上级 custom_gestures.json 加载自定义手势/序列并合并"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            custom_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            if not os.path.exists(custom_path):
                return
            with open(custom_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            added_gestures = 0
            added_sequences = 0
            if isinstance(data, dict):
                bg = data.get("base_gestures", {})
                if isinstance(bg, dict):
                    for name, angles in bg.items():
                        if isinstance(angles, list) and len(angles) == 12:
                            self.base_gestures[name] = angles
                            added_gestures += 1
                seqs = data.get("action_sequences", {})
                if isinstance(seqs, dict):
                    for name, steps in seqs.items():
                        if isinstance(steps, list):
                            # 仅接受包含 gesture/duration 的步骤
                            valid_steps = []
                            for step in steps:
                                if isinstance(step, dict) and "gesture" in step and "duration" in step:
                                    valid_steps.append({"gesture": step["gesture"], "duration": float(step["duration"])})
                            if valid_steps:
                                self.action_sequences[name] = valid_steps
                                added_sequences += 1
            if added_gestures or added_sequences:
                print(f"🧩 已加载自定义手势: {added_gestures} 个，自定义序列: {added_sequences} 个")
        except Exception as e:
            print(f"⚠️  加载自定义手势失败: {e}")
    
    def _load_custom_action_config(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cfg_path = os.path.normpath(os.path.join(base_dir, "..", "custom_actions.json"))
            if not os.path.exists(cfg_path):
                self._custom_action_mappings = {}
                self._custom_action_durations = {}
                self._custom_action_full_min = {}
                self._quick_hold_gestures = set()
                return
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._custom_action_mappings = dict(data.get("action_mappings", {}))
            self._custom_action_durations = {k: float(v) for k, v in dict(data.get("action_durations", {})).items()}
            self._custom_action_full_min = {k: float(v) for k, v in dict(data.get("action_full_min", {})).items()}
            self._quick_hold_gestures = set(data.get("quick_hold_gestures", []))
            if self._custom_action_mappings or self._custom_action_durations:
                print("🧩 已加载自定义动作配置")
        except Exception as e:
            print(f"⚠️  加载自定义动作配置失败: {e}")
    
    def _generate_action_based_sequence(self, detected_actions: List[str], 
                                      total_duration: float, emotion: str, flow_mode: bool, intent: str = "explanation") -> List[tuple]:
        """🎯 基于检测到的动作生成手势序列"""
        
        # 🎭 动作到序列的映射 - 优先使用动态序列
        action_sequence_map = {
            # 挥手类 - 使用动态序列
            "wave_right": "wave_right_sequence",
            "wave_left": "wave_left_sequence", 
            "wave_both": "wave_both_sequence",  # 🎯 使用新的双手挥手序列
            
            # 握手类 - 使用动态序列
            "handshake": "handshake_sequence",
            
            # 舞蹈类 - 使用自定义舞蹈序列
            "dance": "mech_dance_loop_30s",
            "dance_loop": "mech_dance_loop_30s",
            "dance_mech": "mech_dance_loop_30s",
            "dance_short": "mech_dance_short_15s",
            "dance_isolation": "mech_dance_isolation_16s",
            
            # 拥抱类 - 注释掉，使用静态手势
            # "embrace": "embrace_sequence",  # 🎯 注释掉，使用简单的embrace_warm
        }
        
        # 动作到静态手势的映射 - 作为备选
        action_gesture_map = {
            # 拥抱类 - 使用静态手势，时长至少2秒
            "embrace": "embrace_warm",  # 🎯 使用简单的embrace_warm，时长在action_durations中设置
            
            # 鼓掌类
            "clap": "applaud_ready",
            
            # 指向类
            "point": "point_right_formal",
            "point_forward": "point_forward",
            
            # 展示类
            "present": "present_right_grand",
            "show": "present_right",
            
            # 停止类
            "stop": "stop_gesture",
            
            # 同意类
            "nod": "nod_strong",
            "ok": "ok_gesture",
            
            # 否定类
            "shake_head": "shake_strong",
            
            # 思考类
            "think": "think_deep",
            
            # 惊讶类
            "surprise": "surprise_strong",
            
            # 看向类
            "look_left": "look_left_strong",
            "look_right": "look_right_strong",
            "look_up": "look_up",
            "look_down": "look_down",
            "turn_left": "look_left_dramatic",
            "turn_right": "look_right_dramatic",
            
            # 🎯 基于挥手动作的常用手势
            "point_forward": "point_forward",
            "thumbs_up": "点赞",
            "muscle_pose": "肌肉",
            "ok": "ok_gesture",
            "stop": "stop_gesture",
            "come_here": "come_here",
            "peace": "peace_sign",
            "applaud": "applaud_prepare",
            "clap": "applaud_clap"
        }
        
        # 🎯 为每个动作定义标准执行时长（秒）- 全面加快
        action_durations = {
            # 挥手类 - 加快挥手动作
            "wave_right": 2.0,      # 挥手加快 (从3.0->2.0)
            "wave_left": 2.0,       # 挥手加快 (从3.0->2.0)
            "wave_both": 2.5,       # 双手挥手加快 (从4.0->2.5)
            
            # 握手类 - 加快握手动作
            "handshake": 2.6,       # 握手加快 (从4.0->2.6)
            
            # 拥抱类 - 增加时长让动作做到位
            "embrace": 2.5,         # 拥抱至少2.5秒（从5.0->2.5秒，但比原来的0.5秒长很多）

            
            # 鼓掌类 - 加快鼓掌动作
            "clap": 2.0,            # 鼓掌加快 (从3.0->2.0)
            
            # 指向类 - 加快指向动作
            "point": 0.8,           # 指向更快
            "point_forward": 0.8,   # 指向更快
            
            # 展示类 - 加快展示动作
            "present": 2.0,         # 展示加快 (从3.5->2.0)
            "show": 1.8,            # 展示加快 (从3.0->1.8)
            
            # 邀请类 - 加快邀请动作
            "invite": 1.8,          # 邀请加快 (从3.0->1.8)
            
            # 停止类 - 加快停止手势
            "stop": 1.2,            # 停止加快 (从2.0->1.2)
            
            # 同意类 - 加快同意动作
            "nod": 1.2,             # 点头加快 (从2.0->1.2)
            "ok": 1.5,              # OK手势加快 (从2.5->1.5)
            
            # 🎯 基于挥手动作的新手势类
            "thumbs_up": 1.5,       # 点赞手势
            "come_here": 1.6,       # 过来手势
            "peace": 1.4,           # V字手势
            "applaud": 1.8,         # 鼓掌准备
            
            # 否定类 - 加快否定动作
            "shake_head": 1.5,      # 摇头加快 (从2.5->1.5)
            
            # 思考类 - 加快思考姿态
            "think": 1.8,           # 思考加快 (从3.0->1.8)
            # 肌肉展示
            "muscle_pose": 2.0,
            
            # 惊讶类 - 需要夸张的惊讶表情
            "surprise": 2.5,        # 惊讶动作要夸张
            
            # 看向类 - 头部转动动作
            "look_left": 1.5,       # 向左看
            "look_right": 1.5,      # 向右看
            "look_up": 1.5,         # 向上看
            "look_down": 1.5,       # 向下看
            "turn_left": 2.0,       # 大幅向左转
            "turn_right": 2.0       # 大幅向右转
        }
        try:
            if hasattr(self, "_custom_action_mappings") and self._custom_action_mappings:
                action_gesture_map.update(self._custom_action_mappings)
            if hasattr(self, "_custom_action_durations") and self._custom_action_durations:
                action_durations.update(self._custom_action_durations)
        except Exception:
            pass
        
        sequence = []
        
        # 🎭 处理动作序列，优先使用动态序列
        if len(detected_actions) == 1:
            action = detected_actions[0]
            
            # 🎯 优先检查是否有动态序列
            if action in action_sequence_map:
                sequence_name = action_sequence_map[action]
                if sequence_name in self.action_sequences:
                    # 使用预定义的动作序列
                    action_sequence = self.action_sequences[sequence_name]
                    if flow_mode:
                        trimmed = list(action_sequence)
                        while trimmed and trimmed[-1].get("gesture") in ("rest", "neutral"):
                            trimmed.pop()
                        action_sequence = trimmed
                    sequence = [(step["gesture"], step["duration"]) for step in action_sequence]
                    sequence_duration = sum(step["duration"] for step in action_sequence)
                    print(f"🎭 动态序列: {action} -> {sequence_name} (序列时长: {sequence_duration:.1f}s)")
                    
                    # 🎯 舞蹈类：按总时长循环铺满
                    if action.startswith("dance"):
                        sequence = self._loop_sequence_to_duration(sequence, total_duration, flow_mode)
                    # 其他序列过短：做一般扩展
                    elif sequence_duration < total_duration * 0.3:  # 序列时长小于总时长的30%
                        print(f"⚠️  序列时长({sequence_duration:.1f}s)远小于语音时长({total_duration:.1f}s)，扩展序列")
                        sequence = self._extend_action_sequence(sequence, total_duration, emotion, action)
                else:
                    # 尝试热加载自定义文件后再检查
                    self._load_custom_definitions()
                    if sequence_name in self.action_sequences:
                        action_sequence = self.action_sequences[sequence_name]
                        if flow_mode:
                            trimmed = list(action_sequence)
                            while trimmed and trimmed[-1].get("gesture") in ("rest", "neutral"):
                                trimmed.pop()
                            action_sequence = trimmed
                        sequence = [(step["gesture"], step["duration"]) for step in action_sequence]
                        sequence_duration = sum(step["duration"] for step in action_sequence)
                        if action.startswith("dance"):
                            sequence = self._loop_sequence_to_duration(sequence, total_duration, flow_mode)
                        elif sequence_duration < total_duration * 0.3:
                            sequence = self._extend_action_sequence(sequence, total_duration, emotion, action)
                    else:
                        print(f"⚠️  序列 {sequence_name} 未定义，生成扩展手势序列")
                        sequence = self._generate_extended_gesture_sequence(action, total_duration, emotion, action_gesture_map, flow_mode)
            else:
                # 🎯 尝试将动作名直接当作自定义序列（来自 custom_gestures.json action_sequences，如 GUI 保存的序列）
                if action not in self.action_sequences:
                    # 支持运行中热加载：如果 JSON 更新过，这里重新加载一次定义
                    self._load_custom_definitions()
                if action in self.action_sequences:
                    action_sequence = self.action_sequences[action]
                    # ⚠️ 关键：对显式 JSON 自定义序列，不再裁剪末尾的 rest/neutral，
                    # 必须严格按 JSON 中的步骤和时长完整执行
                    sequence = [(step["gesture"], step["duration"]) for step in action_sequence]
                    seq_dur = sum(step["duration"] for step in action_sequence)
                    print(f"🎭 自定义序列: {action} ({len(sequence)}个手势，总时长: {seq_dur:.2f}s)")
                else:
                    # 🎯 修复：不再使用简单的3个手势，而是生成扩展序列
                    print(f"🎭 生成扩展手势序列: {action} (总时长: {total_duration:.1f}s)")
                    sequence = self._generate_extended_gesture_sequence(action, total_duration, emotion, action_gesture_map, flow_mode)
            
        # 如果有多个动作，依次执行
        else:
            sequence = []
            
            for i, action in enumerate(detected_actions):
                # 检查是否有动态序列
                if action in action_sequence_map:
                    sequence_name = action_sequence_map[action]
                    if sequence_name in self.action_sequences:
                        action_sequence = self.action_sequences[sequence_name]
                        # 流模式下修剪子序列末尾的 rest/neutral，保持连贯
                        if flow_mode:
                            trimmed = list(action_sequence)
                            while trimmed and trimmed[-1].get("gesture") in ("rest", "neutral"):
                                trimmed.pop()
                            action_sequence = trimmed
                        for step in action_sequence:
                            sequence.append((step["gesture"], step["duration"]))
                    else:
                        # 热加载后再尝试
                        self._load_custom_definitions()
                        if sequence_name in self.action_sequences:
                            action_sequence = self.action_sequences[sequence_name]
                            if flow_mode:
                                trimmed = list(action_sequence)
                                while trimmed and trimmed[-1].get("gesture") in ("rest", "neutral"):
                                    trimmed.pop()
                                action_sequence = trimmed
                            for step in action_sequence:
                                sequence.append((step["gesture"], step["duration"]))
                        else:
                            # 回退到静态手势（避免以 rest 开头）
                            # 🎯 说话时不要使用 neutral，用有动作的手势替代
                            gesture_name = action_gesture_map.get(action, "both_hands_explain")
                            standard_duration = action_durations.get(action, 3.0)
                            # 🎯 说话时不要添加 neutral，保持动作连贯
                            # if not flow_mode and sequence:  # 非首个动作，添加过渡
                            #     # 🎯 避免在连续手部动作之间添加过渡，防止抖动
                            #     last_gesture = sequence[-1][0] if sequence else ""
                            #     if not (any(k in last_gesture for k in ("handshake", "ok", "point", "embrace")) and 
                            #            any(k in action for k in ("handshake", "ok", "point", "embrace"))):
                            #         sequence.append(("neutral", 0.3))
                            sequence.append((gesture_name, standard_duration))
                            # 🎯 说话时不要添加 neutral，保持动作连贯
                            # 指向动作不追加回中立
                            # if not flow_mode and ("point" not in gesture_name and "embrace" not in gesture_name and "handshake" not in gesture_name and "ok" not in gesture_name):
                            #     sequence.append(("neutral", 0.3))
                else:
                    # 使用静态手势（避免以 rest 开头）
                    # 🎯 说话时不要使用 neutral，用有动作的手势替代
                    gesture_name = action_gesture_map.get(action, "both_hands_explain")
                    standard_duration = action_durations.get(action, 3.0)
                    # 🎯 说话时不要添加 neutral，保持动作连贯
                    # if not flow_mode and sequence:  # 非首个动作，添加过渡
                    #     # 🎯 避免在连续手部动作之间添加过渡，防止抖动
                    #     last_gesture = sequence[-1][0] if sequence else ""
                    #     if not (any(k in last_gesture for k in ("handshake", "ok", "point", "embrace")) and 
                    #            any(k in action for k in ("handshake", "ok", "point", "embrace"))):
                    #         sequence.append(("neutral", 0.3))
                    sequence.append((gesture_name, standard_duration))
                    # 🎯 说话时不要添加 neutral，保持动作连贯
                    # 指向动作不追加回中立
                    # if not flow_mode and ("point" not in gesture_name and "embrace" not in gesture_name and "handshake" not in gesture_name and "ok" not in gesture_name):
                    #     sequence.append(("neutral", 0.3))
                
                # 🎯 说话时不要添加 neutral，保持动作连贯
                # 在动作之间添加间隔（若上一步是指向、握手、OK等则不加中立间隔）
                # if not flow_mode and i < len(detected_actions) - 1:
                #     if not (sequence and ("point" in sequence[-1][0] or "embrace" in sequence[-1][0] or "handshake" in sequence[-1][0] or "ok" in sequence[-1][0])):
                #         sequence.append(("neutral", 0.5))
            
            # 若总时长不足，使用通用手势填充到接近总时长
            seq_dur = sum(d for _, d in sequence)
            if seq_dur < total_duration * 0.98:
                sequence = self._extend_sequence_to_duration(sequence, total_duration, emotion, flow_mode)
            
            print(f"🎭 多动作序列: {len(detected_actions)}个动作")
        
        print(f"🎭 生成动作序列: {[f'{name}({dur:.1f}s)' for name, dur in sequence]}")
        return sequence

    def _replace_long_listen_with_filler(self, seq: List[tuple], emotion: str, intent: str, flow_mode: bool, max_single: float = 1.2) -> List[tuple]:
        """将超出上限的 attentive_listen 片段替换为语义填充序列，保持总时长不变。"""
        out: List[tuple] = []
        for name, dur in seq:
            if name == "attentive_listen" and dur > max_single:
                filler = self._generate_semantic_filler(dur, emotion, intent, flow_mode)
                filler = self._fit_sequence_to_duration(filler, dur, flow_mode)
                out.extend(filler)
            else:
                out.append((name, dur))
        return out

    def _build_action_timeline_from_text(self, utterance_text: str, total_duration: float) -> List[Dict]:
        """将整段文本按标点分句，按字数占比分配每个分句的时间段，
        并在每个分句内用 TextProcessor.extract_actions 检测动作，
        构建形如[{start, duration, action}]的时间轴列表。
        """
        text = str(utterance_text or "")
        from input_processing.text_processor import TextProcessor
        tp = TextProcessor()
        # 1) 在整段文本中定位所有动作关键词/正则匹配的位置
        raw_matches: List[tuple] = []  # (start, end, action)
        # 关键词直接匹配（支持多次出现）
        for act, kws in getattr(tp, "action_keywords", {}).items():
            for kw in kws:
                if not kw:
                    continue
                for m in re.finditer(re.escape(kw), text):
                    raw_matches.append((m.start(), m.end(), act))
        # 正则匹配
        for act, pats in getattr(tp, "action_regex", {}).items():
            for pat in pats:
                try:
                    for m in re.finditer(pat, text, flags=re.IGNORECASE):
                        raw_matches.append((m.start(), m.end(), act))
                except re.error:
                    continue
        # 额外启发式：'指向前'/'向前'/'朝前' 归为 point_forward（覆盖只匹配到 '指向' 的情况）
        for m in re.finditer(r"(指向前|向前指|朝前指|指向前方|向前|朝前)", text):
            raw_matches.append((m.start(), m.end(), "point_forward"))
        if raw_matches:
            # 2) 去重/消除重叠：优先保留更长匹配
            raw_matches.sort(key=lambda x: (-(x[1]-x[0]), x[0]))
            kept: List[tuple] = []
            used_ranges: List[tuple] = []
            for s, e, a in raw_matches:
                overlap = False
                for us, ue in used_ranges:
                    if not (e <= us or s >= ue):
                        overlap = True
                        break
                if not overlap:
                    kept.append((s, e, a))
                    used_ranges.append((s, e))
            kept.sort(key=lambda x: x[0])
            
            # 🎯 检查时间是否足够执行所有动作
            action_floor_map = {
                "wave_right": 5.3, "wave_left": 5.3, "wave_both": 5.3,
                "handshake": 2.0, "embrace": 7.3, "clap": 1.8, "applaud": 1.8,
                "thumbs_up": 1.2, "ok": 1.2, "point_forward": 0.8,
                "point": 0.7, "present": 1.0, "nod": 0.6, "shake_head": 0.6,
            }
            total_required = sum(action_floor_map.get(a, 0.5) for _, _, a in kept)
            
            # 🎯 旧逻辑会在“时间不足”时只保留前1~2个动作，导致每句只有极少动作。
            # 现在改为：保留所有匹配到的动作，后续交给时长缩放和裁剪逻辑统一处理，
            # 避免简单粗暴地丢弃后面的动作。
            # if total_required > total_duration * 1.5:
            #     print(f"⚠️  [时间轴] 时间不足！需要{total_required:.1f}秒，只有{total_duration:.1f}秒")
            #     print(f"  策略：只保留前{min(2, len(kept))}个动作，确保动作有效果")
            #     kept = kept[:min(2, len(kept))]  # 最多保留2个动作
            
            # 若仅有一个动作：JSON 自定义动作必须按 action_durations 的时长；其余在 [floor, 3.0] 内
            if len(kept) == 1:
                act = kept[0][2]
                mapped = getattr(self, "_custom_action_mappings", {}).get(act, act)
                # JSON 自定义动作：严格按配置时长，不设 3s 上限
                if getattr(self, "_custom_action_durations", None) and (
                    act in self._custom_action_durations or mapped in self._custom_action_durations
                ):
                    user_dur = float(
                        self._custom_action_durations.get(mapped)
                        or self._custom_action_durations.get(act, 1.5)
                    )
                    return [{"start": 0.0, "duration": user_dur, "action": act}]
                floor = 1.0
                # 1) 序列动作：使用序列总时长作为 floor
                if act in getattr(self, "action_sequences", {}):
                    steps = self.action_sequences[act]
                    if isinstance(steps, list):
                        floor = sum(float(s.get("duration", 0)) for s in steps if isinstance(s, dict))
                else:
                    floor = {"handshake": 1.5, "wave_right": 1.5, "embrace": 2.5}.get(act, 1.5)
                max_cap = 3.0
                if total_duration <= floor:
                    dur = float(floor)
                elif total_duration <= max_cap:
                    dur = float(total_duration)
                else:
                    dur = max(float(floor), max_cap)
                return [{"start": 0.0, "duration": dur, "action": act}]
            # 3) 按位置构建时间片：空白片段(None) + 动作片段(action)
            char_total = max(1, len(text))
            segments: List[tuple] = []  # (char_len, action_or_none)
            cursor = 0
            for s, e, a in kept:
                if s > cursor:
                    segments.append((s - cursor, None))  # 前导空白
                segments.append((max(1, e - s), a))       # 动作匹配片段
                cursor = e
            if cursor < len(text):
                segments.append((len(text) - cursor, None))
            # 4) 先按字符比例计算基础时长，确保动作开始时间≈文本位置
            char_time = total_duration / max(1.0, float(char_total))
            base_durations: List[float] = [max(0.08, c * char_time) for (c, _) in segments]
            # 为动作片段设置合理的最小时长，仅通过“向后借时”扩展，不减少之前的空白片段
            # 🎯 动作 floor 时长整体下调，让每个动作更短、更贴近语音节奏
            action_floor = {
                "thumbs_up": 0.8,    # 原1.2 → 0.8
                "handshake": 1.2,    # 原2.0 → 1.2
                "muscle_pose": 1.0,  # 原1.6 → 1.0
                "embrace": 3.5,      # 原7.3 → 3.5
                "point": 0.5,        # 原0.7 → 0.5
                "point_forward": 0.6,# 原0.8 → 0.6
                "present": 1.0,      # 原1.6 → 1.0
                "show": 1.0,         # 原1.6 → 1.0
                "clap": 1.0,         # 原1.8 → 1.0
                "applaud": 1.0,      # 原1.8 → 1.0
                "wave_right": 3.0,   # 原5.3 → 3.0
                "wave_left": 3.0,    # 原5.3 → 3.0
                "wave_both": 3.0,    # 原5.3 → 3.0
                "ok": 0.8,           # 原1.2 → 0.8
                "nod": 0.6,          # 原0.9 → 0.6
                "shake_head": 0.7,   # 原1.0 → 0.7
                "think": 0.9,        # 原1.3 → 0.9
                "surprise": 0.9,     # 原1.3 → 0.9
                "look_left": 0.5,    # 原0.8 → 0.5
                "look_right": 0.5,   # 原0.8 → 0.5
                "look_up": 0.5,      # 原0.8 → 0.5
                "look_down": 0.5,    # 原0.8 → 0.5
                "turn_left": 0.8,    # 原1.2 → 0.8
                "turn_right": 0.8,   # 原1.2 → 0.8
                "come_here": 0.8,    # 原1.2 → 0.8
                "peace": 0.7,        # 原1.0 → 0.7
            }
            def min_floor(act: str) -> float:
                if not act:
                    return 0.0
                if act.startswith("dance"):
                    return 6.0
                # 序列动作（如测试、你好）：使用完整序列时长，否则时间片太短只播第一个手势
                if act in getattr(self, "action_sequences", {}):
                    steps = self.action_sequences[act]
                    if isinstance(steps, list):
                        return float(sum(float(s.get("duration", 0)) for s in steps if isinstance(s, dict)))
                if hasattr(self, "_custom_action_durations") and self._custom_action_durations and act in self._custom_action_durations:
                    return float(self._custom_action_durations[act])
                return float(action_floor.get(act, 1.0))
            durations = list(base_durations)
            # 4.1) 为每个动作片段扩展到 floor，仅从其后的片段中“借时”（先借后续空白，再借后续动作的冗余）
            for i, (_, act) in enumerate(segments):
                if not act:
                    continue
                need = max(0.0, min_floor(act) - durations[i])
                if need <= 1e-6:
                    continue
                # 先向后续空白片段借
                j = i + 1
                while need > 1e-6 and j < len(segments):
                    _, a2 = segments[j]
                    if a2 is None and durations[j] > 0.08:
                        give = min(need, max(0.0, durations[j] - 0.08))
                        if give > 0:
                            durations[j] -= give
                            need -= give
                    j += 1
                # 再向后续动作借它们超过 floor 的冗余
                j = i + 1
                while need > 1e-6 and j < len(segments):
                    _, a2 = segments[j]
                    if a2 is not None:
                        floor2 = min_floor(a2)
                        extra2 = max(0.0, durations[j] - max(0.08, floor2))
                        give = min(need, extra2)
                        if give > 0:
                            durations[j] -= give
                            need -= give
                    j += 1
                # 仍不足: 作为最后手段，向前面的空白片段借(会略微提前后续动作，但尽量少借)
                if need > 1e-6:
                    j = i - 1
                    while need > 1e-6 and j >= 0:
                        _, a2 = segments[j]
                        if a2 is None and durations[j] > 0.12:  # 前段空白预留更大下限
                            give = min(need, max(0.0, durations[j] - 0.12))
                            if give > 0:
                                durations[j] -= give
                                need -= give
                        j -= 1
                # 将获得的时间加到当前动作片段
                gain = max(0.0, min_floor(act) - durations[i])
                durations[i] += gain
            # 最后对齐误差
            total_now = sum(durations)
            if abs(total_now - total_duration) > 1e-6 and durations:
                durations[-1] = max(0.08, durations[-1] + (total_duration - total_now))
            # 生成时间轴
            timeline: List[Dict] = []
            t_cursor = 0.0
            for i, (_, act) in enumerate(segments):
                dur = durations[i]
                timeline.append({"start": t_cursor, "duration": dur, "action": act})
                t_cursor += dur
            return timeline
        # 无任何动作匹配时，退回到按标点分句的平均时间分配
        parts = [p for p in re.split(r"[。！？!?；;：:,，、]\s*", text) if p]
        if not parts:
            parts = [text]
        lengths = [max(1, len(p)) for p in parts]
        total_len = sum(lengths)
        timeline: List[Dict] = []
        start_cursor = 0.0
        for i, part in enumerate(parts):
            seg_duration = total_duration * (lengths[i] / max(1, total_len))
            # 这里不做动作检测，保持为背景片段(None)
            timeline.append({"start": start_cursor, "duration": seg_duration, "action": None})
            start_cursor += seg_duration
        return timeline

    def _build_even_action_timeline(self, actions: List[str], total_duration: float) -> List[Dict]:
        """当没有可用的原始文本但检测到了多个动作时，
        将总时长按动作个数均分，构建一个均匀分布的时间轴，
        以避免所有动作在序列开始处连续播放。"""
        n = max(1, len(actions))
        seg = total_duration / n
        timeline: List[Dict] = []
        start = 0.0
        for a in actions:
            timeline.append({"start": start, "duration": seg, "action": a})
            start += seg
        return timeline

    def _generate_timeline_aligned_sequence(self, action_timeline: List[Dict], total_duration: float, emotion: str, flow_mode: bool, intent: str = "explanation", semantic_info: Dict = None) -> List[tuple]:
        """🎯 修复版时间轴对齐：保留丰富手势生成，但使用精确的一次性缩放
        
        根据显式时间轴对齐手势，生成丰富的手势序列，最后统一缩放到精确时长
        """
        print(f"🎯 [精确对齐] 开始处理时间轴，目标时长: {total_duration:.2f}s")
        print(f"🎯 [精确对齐] 时间轴片段数: {len(action_timeline)}")
        
        # 🔍 调试：打印时间轴详情
        for i, seg in enumerate(action_timeline):
            print(f"🔍 时间片 {i+1}: start={seg.get('start', 0):.2f}s, dur={seg.get('duration', 0):.2f}s, action={seg.get('action', 'None')}")
        
        # 动作映射
        action_sequence_map = {
            "wave_right": "wave_right_sequence",
            "wave_left": "wave_left_sequence", 
            "wave_both": "wave_both_sequence",
            "handshake": "handshake_sequence",
            # "thumbs_up": "thumbs_up_sequence",  # 🎯 JSON 中只有 base_gesture "点赞"，没有序列，使用手势映射
            # "ok": "ok_gesture_sequence",  # 🎯 改为单独动作，不使用序列
            "stop": "stop_sequence",
            "clap": "clap_sequence",
            "applaud": "clap_sequence",
            "point_forward": "point_forward_sequence",
        }
        
        action_gesture_map = {
            "embrace": "embrace_warm",
            "clap": "applaud_ready",
            "point": "point_right_formal",
            "point_forward": "point_forward",
            "present": "present_right_grand",
            "show": "present_right",
            "stop": "stop_gesture",
            "ok": "ok_gesture",  # 🎯 ok作为单独动作
            "nod": "nod_strong",
            "shake_head": "shake_strong",
            "think": "think_deep",
            "surprise": "surprise_strong",
            "look_left": "look_left_strong",
            "look_right": "look_right_strong",
            "look_up": "look_up",
            "look_down": "look_down",
            "turn_left": "look_left_dramatic",
            "turn_right": "look_right_dramatic",
            "thumbs_up": "点赞",  # 🎯 映射到 JSON 中的中文手势名
            "muscle_pose": "肌肉",  # 🎯 映射到 JSON 中的中文手势名
            "come_here": "come_here",
            "peace": "peace_sign",
            "applaud": "applaud_prepare",
        }
        
        # 🎯 自动从 custom_gestures.json 的 base_gestures 添加映射
        # 这样用户添加新动作时就不需要手动修改代码了
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            custom_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            if os.path.exists(custom_path):
                with open(custom_path, "r", encoding="utf-8") as f:
                    gestures_data = json.load(f)
                base_gestures = gestures_data.get("base_gestures", {})
                
                for gesture_name, angles in base_gestures.items():
                    if not isinstance(angles, list) or len(angles) != 12:
                        continue
                    
                    # 生成动作类型名（与 text_processor.py 中的逻辑一致）
                    gesture_lower = gesture_name.lower()
                    if "点赞" in gesture_name or "赞" in gesture_name:
                        action_key = "thumbs_up"
                    elif "肌肉" in gesture_name:
                        action_key = "muscle_pose"
                    else:
                        # 其他新动作：使用手势名本身作为action key
                        action_key = gesture_name
                    
                    if action_key and action_key not in action_gesture_map:
                        action_gesture_map[action_key] = gesture_name
        except Exception:
            pass  # 如果加载失败，使用默认映射
        
        # 🎯 custom_actions.json 的 action_mappings 优先覆盖，确保 JSON 动作优先级
        try:
            if hasattr(self, "_custom_action_mappings") and self._custom_action_mappings:
                action_gesture_map.update(self._custom_action_mappings)
        except Exception:
            pass
        
        # 🎯 步骤1：规范化时间片
        norm = []
        cursor = 0.0
        for item in action_timeline:
            a = dict(item)
            start = a.get("start", cursor)
            end = a.get("end")
            dur = a.get("duration")
            
            if dur is None and end is not None:
                dur = max(0.0, float(end) - float(start))
            if dur is None:
                dur = 0.0
                
            action = a.get("action") or a.get("gesture")
            seq_name = a.get("sequence") or a.get("sequence_name")
            norm.append((float(start), float(dur), action, seq_name))
            cursor = start + dur
        
        norm = [(s, d, act, seqn) for (s, d, act, seqn) in norm if d > 0]
        norm.sort(key=lambda x: x[0])
        
        print(f"🎯 [精确对齐] 规范化后有 {len(norm)} 个时间片")
        
        # 🔍 调试：打印规范化后的时间片
        timeline_total = sum(d for _, d, _, _ in norm)
        print(f"🔍 时间片总时长: {timeline_total:.2f}s (目标: {total_duration:.2f}s)")
        
        # 🎯 步骤2：为每个时间片生成手势，区分序列动作和填充动作
        sequence_gestures: List[tuple] = []  # 序列动作（必须完整执行）
        filler_gestures: List[tuple] = []    # 填充动作（可以缩放）
        sequence_duration = 0.0
        filler_duration = 0.0
        
        # 🎯 构建 JSON 自定义手势集合（用于判断优先级）
        custom_base_gestures = set()
        custom_action_sequences = set()
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            custom_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            if os.path.exists(custom_path):
                with open(custom_path, "r", encoding="utf-8") as f:
                    gestures_data = json.load(f)
                custom_base_gestures = set(gestures_data.get("base_gestures", {}).keys())
                custom_action_sequences = set(gestures_data.get("action_sequences", {}).keys())
        except Exception:
            pass
        
        for i, (start, duration, action, seq_name) in enumerate(norm):
            print(f"🎯 [处理时间片] {i+1}/{len(norm)}: {action or 'filler'} ({duration:.2f}s)")
            
            seg_seq: List[tuple] = []
            is_sequence_action = False
            
            # 🎯 判断是否为序列动作
            if seq_name and seq_name in self.action_sequences:
                steps = self.action_sequences[seq_name]
                seg_seq = [(st["gesture"], float(st["duration"])) for st in steps]
                is_sequence_action = True
                print(f"  ✅ 序列动作: {seq_name} ({len(seg_seq)}个手势)")
            elif action in action_sequence_map and action_sequence_map[action] in self.action_sequences:
                sequence_name = action_sequence_map[action]
                steps = self.action_sequences[sequence_name]
                seg_seq = [(st["gesture"], float(st["duration"])) for st in steps]
                is_sequence_action = True
                print(f"  ✅ 序列动作: {sequence_name} ({len(seg_seq)}个手势)")
            elif action is not None:
                # 🎯 检查是否为 JSON 自定义动作序列
                if action in custom_action_sequences or action in self.action_sequences:
                    # 优先检查 action_sequences
                    if action in self.action_sequences:
                        steps = self.action_sequences[action]
                        seg_seq = [(st["gesture"], float(st["duration"])) for st in steps]
                        is_sequence_action = True
                        print(f"  ✅ JSON序列动作: {action} ({len(seg_seq)}个手势)")
                    else:
                        # 回退到扩展序列
                        seg_seq = self._generate_extended_gesture_sequence(action, duration, emotion, action_gesture_map, flow_mode)
                        print(f"  ✅ 单个动作: {action} ({len(seg_seq)}个手势)")
                else:
                    # 🎯 检查是否映射到 JSON 自定义手势（base_gestures）
                    mapped_gesture = action_gesture_map.get(action)
                    if mapped_gesture and mapped_gesture in custom_base_gestures:
                        # JSON 自定义手势：标记为序列动作，确保完整执行
                        is_sequence_action = True
                        # 使用标准时长或配置的时长
                        action_durations_map = {
                            "thumbs_up": 1.5,
                            "muscle_pose": 2.0,
                        }
                        # 尝试从配置获取时长
                        try:
                            if hasattr(self, "_custom_action_durations") and self._custom_action_durations:
                                standard_duration = self._custom_action_durations.get(action, action_durations_map.get(action, duration))
                            else:
                                standard_duration = action_durations_map.get(action, duration)
                        except Exception:
                            standard_duration = action_durations_map.get(action, duration)
                        # 确保至少使用配置的最小时长
                        try:
                            if hasattr(self, "_custom_action_full_min") and self._custom_action_full_min:
                                min_duration = self._custom_action_full_min.get(action, 0.0)
                                if min_duration > 0:
                                    standard_duration = max(standard_duration, min_duration)
                        except Exception:
                            pass
                        # 使用实际时间片时长和标准时长的较大值
                        final_duration = max(duration, standard_duration)
                        seg_seq = [(mapped_gesture, final_duration)]
                        print(f"  ✅ JSON自定义手势（序列优先级）: {action} -> {mapped_gesture} ({final_duration:.2f}s)")
                    else:
                        # 单个动作手势（非 JSON 自定义）
                        seg_seq = self._generate_extended_gesture_sequence(action, duration, emotion, action_gesture_map, flow_mode)
                        print(f"  ✅ 单个动作: {action} ({len(seg_seq)}个手势)")
            else:
                # � 使用语义确填充生成丰富的随机手势
                seg_seq = self._generate_semantic_filler(duration, emotion, intent, flow_mode)
                print(f"  ✅ 填充手势: ({len(seg_seq)}个手势)")
            
            seg_duration = sum(d for _, d in seg_seq)
            
            # 🎯 分类存储：序列动作 vs 填充动作
            if is_sequence_action:
                sequence_gestures.extend(seg_seq)
                sequence_duration += seg_duration
                print(f"  📊 序列动作时长: {seg_duration:.2f}s (累计: {sequence_duration:.2f}s) - 必须完整执行")
            else:
                filler_gestures.extend(seg_seq)
                filler_duration += seg_duration
                print(f"  📊 填充动作时长: {seg_duration:.2f}s (累计: {filler_duration:.2f}s) - 可缩放")
        
        # 🎯 步骤3：先计算序列动作总时长，再决定填充动作时长
        print(f"\n🔍 统计:")
        print(f"  序列动作总时长: {sequence_duration:.2f}s (完整执行)")
        print(f"  序列动作手势数: {len(sequence_gestures)}个")
        print(f"  填充动作原始时长: {filler_duration:.2f}s")
        print(f"  填充动作手势数: {len(filler_gestures)}个")
        print(f"  目标总时长: {total_duration:.2f}s")
        
        # 🎯 关键：先对比总时长和序列动作时长
        remaining_time = total_duration - sequence_duration
        print(f"  剩余时间: {remaining_time:.2f}s")
        
        # ✅ 借鉴口型算法：确保动作时长始终等于语音时长
        # 核心思想：只要剩余时间 > 0.1秒，就填充（小于0.1秒忽略）
        if remaining_time > 0.1:  # 只填充剩余时间 > 0.1秒的情况
            if filler_gestures and filler_duration > 0:
                # 有填充动作，缩放到剩余时间
                scale_factor = remaining_time / filler_duration
                scaled_fillers = [(name, dur * scale_factor) for name, dur in filler_gestures]
                sequence = sequence_gestures + scaled_fillers
                print(f"🎯 填充动作缩放: {filler_duration:.2f}s -> {remaining_time:.2f}s (x{scale_factor:.3f})")
            else:
                # 没有填充动作，生成新的填充
                print(f"🎯 生成新填充: {remaining_time:.2f}s")
                new_filler = self._generate_semantic_filler(remaining_time, emotion, intent, flow_mode)
                sequence = sequence_gestures + new_filler
                print(f"   新填充手势数: {len(new_filler)}个")
        else:
            # 剩余时间太少（≤0.1秒），不填充
            sequence = sequence_gestures
            print(f"✅ 剩余时间很少({remaining_time:.2f}s)，不填充")
        
        # ✅ 步骤1：去重（合并连续相同手势）
        print(f"[去重] 去重前手势数: {len(sequence)}个")
        sequence = self._merge_consecutive_gestures(sequence)
        print(f"[去重] 去重后手势数: {len(sequence)}个")
        
        # 重新计算最终时长
        final_duration = sum(d for _, d in sequence)
        print(f"✅ [初步完成] 最终时长: {final_duration:.2f}s，目标: {total_duration:.2f}s，误差: {abs(final_duration - total_duration):.3f}s")
        
        # ✅ 步骤2：如果时长不足，用随机多样动作填补（不保持，保证动作多样性）
        if final_duration < total_duration - 0.3:  # 如果差距 > 0.3秒
            shortage = total_duration - final_duration
            print(f"⚠️  时长不足 {shortage:.2f}s，插入随机多样动作填补")
            
            # 分块生成多样填充，避免连续重复、类型单一
            diverse_filler = self._generate_diverse_filler_for_shortage(
                shortage, sequence, emotion, intent, flow_mode
            )
            sequence.extend(diverse_filler)
            print(f"   填补手势数: {len(diverse_filler)}个（保证多样性）")
            
            # 重新计算最终时长
            final_duration = sum(d for _, d in sequence)
            print(f"✅ [修正后] 最终时长: {final_duration:.2f}s，目标: {total_duration:.2f}s，误差: {abs(final_duration - total_duration):.3f}s")
        
        # 🎯 返回序列和序列动作的数量（用于标记）
        sequence_gesture_count = len(sequence_gestures)
        print(f"🎯 [调试] sequence_gesture_count = {sequence_gesture_count}")
        
        # ✅ 最终验证：打印完整的手势序列时间轴
        print(f"\n📊 [时间轴验证] 手势序列详情:")
        cumulative_time = 0.0
        # 🎯 后处理：确保自定义动作（如你好、右边、左边、三/一等）时长落在 [min, max] 区间：
        # - 下限：action_durations 中配置的最小时长（如 1.5s）
        # - 上限：默认 3.0s，避免单个动作被拉长到十几秒
        if hasattr(self, "_custom_action_durations") and self._custom_action_durations:
            new_seq = []
            for name, dur in sequence:
                min_dur = self._custom_action_durations.get(name)
                if min_dur is not None and min_dur > 0:
                    min_dur = float(min_dur)
                    if dur < min_dur:
                        dur = min_dur
                        print(f"  [时长修正] {name}: 提升至 {dur:.2f}s (action_durations)")
                    # 仅当时长被拉长（> 配置值）时才应用上限，配置的时长严格按用户设置不截断
                    elif dur > min_dur:
                        max_cap = max(3.0, min_dur * 2.0)
                        if dur > max_cap:
                            print(f"  [时长上限] {name}: 从 {dur:.2f}s 限制为 {max_cap:.2f}s")
                            dur = max_cap
                new_seq.append((name, dur))
            sequence = new_seq

        for i, (gesture_name, duration) in enumerate(sequence):
            cumulative_time += duration
            is_seq = "🔵序列" if i < sequence_gesture_count else "🟢填充"
            print(f"  {i+1:2d}. {is_seq} {gesture_name:30s} 时长:{duration:5.2f}s  累计:{cumulative_time:6.2f}s")
        print(f"📊 [时间轴验证] 总计: {len(sequence)}个手势, 总时长: {cumulative_time:.2f}s, 目标: {total_duration:.2f}s")
        
        return sequence, sequence_gesture_count

    def _generate_diverse_filler_for_shortage(self, shortage: float, existing_sequence: List[tuple], emotion: str, intent: str, flow_mode: bool) -> List[tuple]:
        """为时长缺口生成多样化的随机填充动作。
        
        分块生成，每块使用不同手势类型（头/手交替），排除最近使用的手势，保证动作多样性。
        """
        if shortage <= 0.08:
            return []
        
        # 每块约 0.8~1.2 秒，确保多段不同动作
        chunk_min, chunk_max = 0.8, 1.2
        result: List[tuple] = []
        used_names: List[str] = list(name for name, _ in existing_sequence[-8:])  # 排除序列末尾8个
        
        remaining = shortage
        while remaining > 0.12:
            chunk_dur = min(remaining, random.uniform(chunk_min, chunk_max))
            if remaining < chunk_min:
                chunk_dur = remaining
            
            exclude = used_names[-8:] if len(used_names) >= 5 else used_names
            filler = self._generate_semantic_filler(chunk_dur, emotion, intent, flow_mode, exclude_recent=exclude)
            
            for name, dur in filler:
                result.append((name, dur))
                used_names.append(name)
            
            remaining -= sum(d for _, d in filler)
        
        return result

    def _generate_semantic_filler(self, target_duration: float, emotion: str, intent: str, flow_mode: bool, exclude_recent: Optional[List[str]] = None) -> List[tuple]:
        """为非动作时间片生成语义相关的随机手势序列（增强多样性，避免重复）。
        
        Args:
            exclude_recent: 需要避免重复的最近手势名列表，用于填补时与现有序列保持多样性。
        """
        if target_duration <= 0.08:
            return [("attentive_listen", max(0.08, target_duration))]
        
        gesture_groups = self.intent_gesture_map.get(intent, self.intent_gesture_map.get("explanation", []))
        candidates: List[str] = []
        head_micro_gestures: List[str] = []  # 🎯 头部微动手势
        both_hands_gestures: List[str] = []  # 🎯 双手动作
        
        for g in gesture_groups:
            if isinstance(g, list):
                for name in g:
                    if name not in ("rest", "neutral", "attentive_listen"):
                        candidates.append(name)
                        # 🎯 识别头部微动
                        if name.startswith("head_micro_") or name.startswith("head_slight_") or name.startswith("head_natural_"):
                            head_micro_gestures.append(name)
                        # 🎯 识别双手动作
                        if name.startswith("both_hands_") or name in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"]:
                            both_hands_gestures.append(name)
            else:
                if g not in ("rest", "neutral", "attentive_listen"):
                    candidates.append(g)
                    if g.startswith("head_micro_") or g.startswith("head_slight_") or g.startswith("head_natural_"):
                        head_micro_gestures.append(g)
                    if g.startswith("both_hands_") or g in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"]:
                        both_hands_gestures.append(g)
        
        # ✅ 调试：打印候选手势统计
        print(f"[手势选择] 候选总数: {len(candidates)}, 头部: {len(head_micro_gestures)}, 双手: {len(both_hands_gestures)}, 单手: {len(candidates) - len(head_micro_gestures) - len(both_hands_gestures)}")
        
        if not candidates:
            # 🎯 禁止低头：排除 look_down, nod_*, head_micro_down, head_*_down, bow_*
            no_head_down = frozenset((
                "look_down", "nod_slight", "nod_strong", "nod_emphatic", "head_slight_nod",
                "head_micro_down", "head_left_down", "head_right_down",
                "bow_respectful", "bow_deep", "bow_apologetic",
            ))
            candidates = [k for k in self.base_gestures.keys()
                         if k not in ("rest", "neutral", "attentive_listen")
                         and k not in no_head_down
                         and not (k.startswith("nod_") or k.startswith("bow_"))]
        if not candidates:
            return [("attentive_listen", max(0.08, target_duration))]
        
        base_d = self._get_base_duration(emotion)
        current = 0.0
        target = max(0.08, target_duration)
        seq: List[tuple] = []
        last_name = None
        
        # ✅ 新增：记录最近使用的手势，避免重复
        recent_gestures = list(exclude_recent) if exclude_recent else []  # 外部传入需避免的手势
        max_recent = 10  # ✅ 改为10（原来3）

        # 🎯 关键：真正做到“头+手同时动”——把头部关节(0/1)融合进手势角度，生成复合手势
        # 这样不会额外增加一个“头部手势”的时长，从而保证动作与语音对齐。
        def _compose_hand_with_head(hand_gesture: str, head_gesture: str) -> str:
            try:
                hand_angles = self.base_gestures.get(hand_gesture)
                head_angles = self.base_gestures.get(head_gesture)
                if not hand_angles or not head_angles:
                    return hand_gesture
                key = f"{hand_gesture}__with__{head_gesture}"
                if key not in self.base_gestures:
                    merged = list(hand_angles)
                    # 0: head yaw, 1: head pitch
                    merged[0] = head_angles[0]
                    merged[1] = head_angles[1]
                    self.base_gestures[key] = merged
                return key
            except Exception:
                return hand_gesture
        
        while current < target - 1e-6:
            # 🎯 确保头部和手部配合，但允许适当的头部动作
            is_last_head = last_name and (last_name.startswith("head_") or last_name.startswith("nod_") or last_name.startswith("look_"))
            
            # 🎯 关键修复：使用配置文件中的头部微动概率，而不是硬编码的0.25
            # 如果上一个是头部动作，降低头部动作概率（避免连续头部），否则使用配置的概率
            head_prob = self.head_micro_movement_probability if not is_last_head else (self.head_micro_movement_probability * 0.5)
            # 🎯 说话时“基本都用双手+头部”：当双手动作库可用时，降低“纯头部微动”占比
            # （因为手部动作分支里会 100% 叠加头部动作，头部不会少）
            if both_hands_gestures:
                head_prob *= 0.15
            use_head_micro = (self.enable_head_micro_movements and head_micro_gestures and 
                             random.random() < head_prob)  # 🎯 使用配置的概率（默认0.6，即60%）
            
            # 🎯 大幅增加双手动作概率：说话动作“基本都用双手+头部”
            use_both_hands_with_head = (self.prefer_both_hands and both_hands_gestures and head_micro_gestures and 
                                       random.random() < 0.15)  # ✅ 降低到15%（原来99%）
            use_both_hands = (self.prefer_both_hands and both_hands_gestures and 
                             random.random() < 0.10)  # ✅ 降低到10%（原来85%）
            
            # 🎯 调整选择逻辑：优先头部+双手组合，减少单手动作
            if is_last_head:
                # 如果上一个是头部动作，优先选择手部动作（但不是强制）
                hand_gestures = [g for g in candidates if not g.startswith("head_") and not g.startswith("nod_") and not g.startswith("look_")]
                # ✅ 增加单手动作，减少双手动作
                single_hand_gestures = [g for g in hand_gestures if not g.startswith("both_hands_") and g not in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"]]
                both_hand_gestures = [g for g in hand_gestures if g.startswith("both_hands_") or g in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"]]
                
                if single_hand_gestures and random.random() < 0.70:  # ✅ 70%概率选择单手动作（原来30%）
                    pool = [g for g in single_hand_gestures if g != last_name]
                    if not pool:
                        pool = single_hand_gestures
                elif both_hand_gestures and random.random() < 0.20:  # ✅ 20%概率选择双手动作（原来98%）
                    pool = [g for g in both_hand_gestures if g != last_name]
                    if not pool:
                        pool = both_hand_gestures
                else:
                    # 选择头部动作
                    pool = [c for c in candidates if c != last_name]
                    if not pool:
                        pool = candidates
                
                # ✅ 过滤掉最近使用的手势
                filtered_pool = [g for g in pool if g not in recent_gestures]
                if len(filtered_pool) > 0:
                    pool = filtered_pool
                elif len(recent_gestures) >= 5:
                    # 只保留最近5个
                    recent_gestures = recent_gestures[-5:]
                    filtered_pool = [g for g in pool if g not in recent_gestures]
                    if filtered_pool:
                        pool = filtered_pool
            elif use_both_hands_with_head:
                # 🎯 优先：头部+双手组合动作（几乎必选）
                # 先选择双手动作
                both_pool = [g for g in both_hands_gestures if g != last_name]
                if not both_pool:
                    both_pool = both_hands_gestures
                if both_pool:
                    name = random.choice(both_pool)
                    # 🎯 计算双手动作时长
                    # 与全局“加快说话动作节奏”的配置一致：双手动作不要太拖沓
                    dur = base_d * random.uniform(0.6, 1.0)
                    if current + dur > target:
                        dur = max(0.08, target - current)
                    # 🎯 选择一个头部动作，并融合进双手动作（不增加时长）
                    # 扩大头部动作选择范围，包括所有头部相关动作
                    all_head_gestures = [g for g in candidates if g.startswith("head_") or g.startswith("nod_") or g.startswith("look_")]
                    if not all_head_gestures:
                        all_head_gestures = head_micro_gestures if head_micro_gestures else []
                    
                    if all_head_gestures:
                        head_pool = [g for g in all_head_gestures if g != last_name]
                        if not head_pool:
                            head_pool = all_head_gestures
                        if head_pool:
                            # 🎯 优先选择左右动作（left/right/tilt_left/tilt_right）
                            left_right_gestures = [g for g in head_pool if "left" in g or "right" in g or "tilt_left" in g or "tilt_right" in g or "look_left" in g or "look_right" in g]
                            if left_right_gestures and random.random() < 0.8:  # 🎯 80%概率选择左右动作
                                head_name = random.choice(left_right_gestures)
                            else:
                                head_name = random.choice(head_pool)
                            name = _compose_hand_with_head(name, head_name)
                    seq.append((name, dur))
                    current += dur
                    last_name = name
                    continue  # 跳过后续选择逻辑
            elif use_both_hands:
                # 🎯 使用双手动作，同时添加头部动作（100%概率）
                pool = [g for g in both_hands_gestures if g != last_name]
                if not pool:
                    pool = both_hands_gestures
                # 标记需要添加头部动作，后续会在添加序列时处理
            elif use_head_micro:
                # 🎯 使用头部微动，优先选择左右动作
                pool = [g for g in head_micro_gestures if g != last_name]
                if not pool:
                    pool = head_micro_gestures
                # 🎯 优先选择左右动作（left/right/tilt_left/tilt_right）
                left_right_micro = [g for g in pool if "left" in g or "right" in g or "tilt_left" in g or "tilt_right" in g or "look_left" in g or "look_right" in g]
                if left_right_micro and random.random() < 0.8:  # 🎯 80%概率选择左右动作
                    pool = left_right_micro
            else:
                # 🎯 平衡选择：当双手动作可用时，优先手部（并强制偏向双手）
                hand_gestures = [g for g in candidates if not g.startswith("head_") and not g.startswith("nod_") and not g.startswith("look_")]
                head_gestures = [g for g in candidates if g.startswith("head_") or g.startswith("nod_") or g.startswith("look_")]
                
                # 🎯 说话时：尽量用“双手+头部”，所以显著提高手部动作比例
                if hand_gestures and head_gestures:
                    # 🎯 在手部动作中优先选择双手动作
                    both_hand_gestures_in_pool = [g for g in hand_gestures if g.startswith("both_hands_") or g in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"]]
                    single_hand_gestures_in_pool = [g for g in hand_gestures if g not in both_hand_gestures_in_pool]
                    
                    if random.random() < 0.60:  # ✅ 60%概率选择手部动作（降低，原来85%）
                        # ✅ 在手部动作中，70%概率选择单手动作（原来97%双手）
                        if single_hand_gestures_in_pool and random.random() < 0.70:
                            pool = [g for g in single_hand_gestures_in_pool if g != last_name]
                            if not pool:
                                pool = single_hand_gestures_in_pool
                        elif both_hand_gestures_in_pool:
                            pool = [g for g in both_hand_gestures_in_pool if g != last_name]
                            if not pool:
                                pool = both_hand_gestures_in_pool
                        else:
                            pool = [g for g in hand_gestures if g != last_name]
                            if not pool:
                                pool = hand_gestures
                    else:  # ✅ 40%概率选择头部动作（增加，原来15%）
                        pool = [g for g in head_gestures if g != last_name]
                        if not pool:
                            pool = head_gestures
                        # 🎯 优先选择左右动作（left/right/tilt_left/tilt_right）
                        left_right_head = [g for g in pool if "left" in g or "right" in g or "tilt_left" in g or "tilt_right" in g or "look_left" in g or "look_right" in g]
                        if left_right_head and random.random() < 0.85:  # 🎯 85%概率选择左右动作（进一步提高）
                            pool = left_right_head
                elif hand_gestures:
                    pool = [g for g in hand_gestures if g != last_name]
                    if not pool:
                        pool = hand_gestures
                else:
                    pool = [c for c in candidates if c != last_name]
                    if not pool:
                        pool = candidates
            
            # 🎯 关键修复：优先选择左右头部动作，然后按幅度选择
            # 首先筛选左右头部动作
            left_right_gestures = [g for g in pool if ("left" in g or "right" in g or "tilt_left" in g or "tilt_right" in g or "look_left" in g or "look_right" in g) and (g.startswith("head_") or g.startswith("look_"))]
            
            # 🎯 80%概率优先选择左右头部动作
            if left_right_gestures and random.random() < 0.8:
                pool = left_right_gestures
            
            # 对手势进行分级：大幅度 > 中等幅度 > 小幅度
            large_amplitude_keywords = ["energetic", "dramatic", "emphatic", "passionate", "commanding", "strong", "grand", "wide", "welcoming"]
            medium_amplitude_keywords = ["moderate", "formal", "present", "invite"]
            small_amplitude_keywords = ["gentle", "soft", "casual", "slight", "light", "micro"]
            
            # ✅ 在分级之前，先过滤掉最近使用的手势
            filtered_pool = [g for g in pool if g not in recent_gestures]
            
            if len(filtered_pool) > 0:
                # 有可用手势，使用过滤后的
                pool = filtered_pool
            elif len(recent_gestures) >= 5:
                # 如果最近使用的手势太多（>=5个），只保留最近5个，释放更早的
                recent_gestures = recent_gestures[-5:]
                filtered_pool = [g for g in pool if g not in recent_gestures]
                if filtered_pool:
                    pool = filtered_pool
                # 如果还是没有，就用原始pool（允许重复）
            # 否则使用原始pool（允许重复，但这种情况很少）
            
            # 将手势按幅度分类
            large_gestures = [g for g in pool if any(kw in g for kw in large_amplitude_keywords)]
            medium_gestures = [g for g in pool if any(kw in g for kw in medium_amplitude_keywords)]
            small_gestures = [g for g in pool if any(kw in g for kw in small_amplitude_keywords)]
            other_gestures = [g for g in pool if g not in large_gestures + medium_gestures + small_gestures]
            
            # 🎯 优先选择：70%概率选择大幅度手势，20%概率选择中等幅度，10%概率选择小幅度或其他
            rand = random.random()
            if large_gestures and rand < 0.7:
                name = random.choice(large_gestures)
            elif medium_gestures and rand < 0.9:
                name = random.choice(medium_gestures)
            elif other_gestures:
                name = random.choice(other_gestures)
            elif small_gestures:
                name = random.choice(small_gestures)
            else:
                # 如果分类后没有手势，直接随机选择
                name = random.choice(pool)
            
            # ✅ 调试：打印选择的手势类型
            gesture_type = "双手" if name.startswith("both_hands_") else ("头部" if name.startswith("head_") or name.startswith("look_") or name.startswith("nod_") else "单手")
            print(f"[手势选择] 选择: {name} ({gesture_type})")
            
            # ✅ 添加到最近使用记录
            recent_gestures.append(name)
            if len(recent_gestures) > max_recent:
                recent_gestures.pop(0)  # 移除最旧的记录
            
            # 🎯 放慢动作速度，让每个动作更有“停顿感”，避免 <1 秒就切换
            if name.startswith("head_micro_"):
                # 头部微动：适度延长到约 0.6-0.9 秒
                dur = base_d * random.uniform(0.6, 0.9)
            elif name.startswith("head_slight_") or name.startswith("head_natural_") or name.startswith("head_moderate_"):
                # 头部普通动作：约 0.8-1.2 秒
                dur = base_d * random.uniform(0.8, 1.2)
            elif name.startswith("both_hands_"):
                # 双手动作：约 1.0-1.6 秒
                dur = base_d * random.uniform(1.0, 1.6)
            else:
                # 其他普通手势：约 0.9-1.4 秒
                dur = base_d * random.uniform(0.9, 1.4)
            
            if current + dur > target:
                dur = max(0.08, target - current)  # 🎯 允许更短的动作，避免总时长超过语音
            
            # 🎯 移除过渡动作，加快动作节奏，增加动作数量
            # if not flow_mode and seq:
            #     seq.append(("neutral", 0.2))
            
            # 🎯 检查是否是手部动作（双手或单手）
            is_hand_gesture = (not name.startswith("head_") and not name.startswith("nod_") and not name.startswith("look_"))
            is_single_hand = (is_hand_gesture and 
                             not name.startswith("both_hands_") and 
                             name not in ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "hands_together"])
            
            # 🎯 单手动作极少出现：只有5%概率执行（其余跳过）
            if is_single_hand and random.random() > 0.05:
                continue  # 跳过单手动作，重新选择
            
            seq.append((name, dur))
            current += dur
            last_name = name
            
            # 🎯 关键修复：每次选择手部动作时，都自动添加头部动作（提高到100%概率，确保头部动作）
            # 扩大头部动作选择范围，包括所有头部相关动作
            all_head_gestures = [g for g in candidates if g.startswith("head_") or g.startswith("nod_") or g.startswith("look_")]
            if not all_head_gestures:
                all_head_gestures = head_micro_gestures if head_micro_gestures else []
            
            if is_hand_gesture and all_head_gestures:  # 🎯 100%概率添加头部动作
                # 🎯 优先选择左右头部动作，增加左右动头频率
                head_pool = [g for g in all_head_gestures if g != last_name]
                if not head_pool:
                    head_pool = all_head_gestures
                if head_pool:
                    # 🎯 优先选择左右动作（left/right/tilt_left/tilt_right）
                    left_right_gestures = [g for g in head_pool if "left" in g or "right" in g or "tilt_left" in g or "tilt_right" in g or "look_left" in g or "look_right" in g]
                    if left_right_gestures and random.random() < 0.8:  # 🎯 80%概率选择左右动作
                        head_name = random.choice(left_right_gestures)
                    else:
                        head_name = random.choice(head_pool)
                    # 🎯 把头部动作融合进刚加入的手势（不增加时长）
                    composite = _compose_hand_with_head(name, head_name)
                    seq[-1] = (composite, dur)
                    last_name = composite
            
            if target - current < 0.15:  # 🎯 减小阈值，允许更多动作：0.25 → 0.15秒
                break
        
        # 若仍有微小剩余，由最后一步吃掉
        if seq:
            last_name, last_dur = seq[-1]
            remain = max(0.0, target - current)
            if remain > 0:
                seq[-1] = (last_name, last_dur + remain)
        
        return seq

    def _generate_filler_gestures(self, target_duration: float, emotion: str, intent: str, flow_mode: bool) -> List[tuple]:
        """生成填充手势，用于在关键动作序列后填充剩余时间
        
        这是 _generate_semantic_filler 的别名，用于更清晰的语义表达
        
        Args:
            target_duration: 目标填充时长(秒)
            emotion: 情感状态
            intent: 意图类型
            flow_mode: 是否流畅模式
            
        Returns:
            填充手势序列 [(gesture_name, duration), ...]
        """
        return self._generate_semantic_filler(target_duration, emotion, intent, flow_mode)

    def _fit_sequence_to_duration(self, seq: List[tuple], target_duration: float, flow_mode: bool) -> List[tuple]:
        """按比例缩放/裁剪序列时长到目标，保留相对节奏；不足时最后一步吃掉差值。"""
        if target_duration <= 0:
            return []
        if not seq:
            return [("attentive_listen", target_duration)]
        total = sum(d for _, d in seq)
        if total <= 0:
            return [(seq[-1][0], target_duration)]
        factor = target_duration / total
        out: List[tuple] = []
        accum = 0.0
        for i, (name, dur) in enumerate(seq):
            nd = max(0.08, dur * factor)
            # 非流模式可保留轻微过渡（此处不新增，仅缩放已有）
            out.append((name, nd))
            accum += nd
        # 调整最后一步以匹配精确时长
        if out:
            last_name, last_dur = out[-1]
            delta = target_duration - accum
            out[-1] = (last_name, max(0.08, last_dur + delta))
        return out

    def _loop_sequence_to_duration(self, base_seq: List[tuple], total_duration: float, flow_mode: bool) -> List[tuple]:
        """循环重复基础序列直至接近目标时长，最后一步截断以贴合。
        会尽量避免连续两个完全相同手势名的相邻步。
        """
        if not base_seq:
            return []
        target = max(total_duration * 0.98, total_duration - 1.0)
        result: List[tuple] = []
        current = 0.0
        idx = 0
        last_name = None
        # 先复制一轮
        while current < target:
            name, dur = base_seq[idx % len(base_seq)]
            # 避免重复相邻手势：如果和上一步同名，尝试跳到下一步
            if last_name == name and len(base_seq) > 1:
                idx += 1
                name, dur = base_seq[idx % len(base_seq)]
            # 若将超出目标，则截断
            if current + dur > target:
                dur = max(0.08, target - current)
            result.append((name, dur))
            current += dur
            last_name = name
            idx += 1
            if dur <= 0.09 and current >= target:
                break
        return result

    def _extend_sequence_to_duration(self, base_sequence: List[tuple], total_duration: float, emotion: str, flow_mode: bool) -> List[tuple]:
        """将已生成的序列扩展接近总时长，保持连贯。
        采用 explanation 手势组做轻量填充，避免频繁 rest/neutral。
        """
        seq = list(base_sequence)
        current = sum(d for _, d in seq)
        target = max(total_duration * 0.98, total_duration - 1.0)  # 预留少量给结尾收尾
        if current >= target:
            return seq
        base_d = self._get_base_duration(emotion)
        # 准备候选手势（不含 rest/neutral）
        gesture_groups = self.intent_gesture_map.get("explanation", self.intent_gesture_map["neutral"])
        candidates: List[str] = []
        for g in gesture_groups:
            if isinstance(g, list):
                for name in g:
                    if name not in ("rest", "neutral"):
                        candidates.append(name)
            else:
                if g not in ("rest", "neutral"):
                    candidates.append(g)
        if not candidates:
            no_head_down = frozenset((
                "look_down", "nod_slight", "nod_strong", "nod_emphatic", "head_slight_nod",
                "head_micro_down", "head_left_down", "head_right_down",
                "bow_respectful", "bow_deep", "bow_apologetic",
            ))
            candidates = [k for k in self.base_gestures.keys()
                          if k not in ("rest", "neutral") and k not in no_head_down
                          and not (k.startswith("nod_") or k.startswith("bow_"))]
        last_name = seq[-1][0] if seq else None
        while current < target and candidates:
            # 避免与上一个完全相同
            next_choices = [c for c in candidates if c != last_name]
            if not next_choices:
                next_choices = candidates
            name = random.choice(next_choices)
            # 时长略大于基础时长，避免太碎
            dur = base_d * random.uniform(1.2, 1.8)
            if current + dur > target:
                dur = max(0.5, target - current)
            # 🎯 说话时不要添加 neutral，直接用有动作的手势
            # if not flow_mode and seq:
            #     seq.append(("neutral", 0.3))
            seq.append((name, dur))
            current += dur + (0.3 if (not flow_mode and len(seq) > 1 and seq[-2][0] == "neutral") else 0.0)
            last_name = name
        return seq

    def _infer_action_from_text(self, text: str) -> str:
        t = str(text)
        # 舞蹈（优先匹配更具体的）
        if re.search(r"(机械舞|robot\s*dance|机械风|机械感)", t, re.IGNORECASE):
            return "dance_mech"
        if re.search(r"(短舞|小段|短一点|简短一段)", t):
            return "dance_short"
        if re.search(r"(isolation|分离感|分离风)", t, re.IGNORECASE):
            return "dance_isolation"
        if re.search(r"(循环|一直跳|反复跳|repeat)", t, re.IGNORECASE):
            return "dance_loop"
        if re.search(r"(跳舞|舞蹈|来一段舞|来段舞|跳一段|跳一个)", t):
            return "dance"
        # 问候/挥手
        if re.search(r"(大家好|各位好|你好|你们好|欢迎|问候)", t):
            return "wave_both"
        # 握手
        if re.search(r"(握手|见面礼)", t):
            return "handshake"
        # 停止/制止
        if re.search(r"(停止|别动|停下|停)", t):
            return "stop"
        # 指向/展示
        if re.search(r"(看|请看|这里|那边|这边|指出|指向)", t):
            return "point"
        if re.search(r"(介绍|展示|呈现|说明)", t):
            return "present"
        # 鼓掌/感谢
        if re.search(r"(鼓掌|掌声|感谢|谢谢)", t):
            return "clap"
        # 拥抱/欢迎
        if re.search(r"(拥抱|欢迎大家|热烈欢迎)", t):
            return "embrace"
        # 赞/OK
        if re.search(r"(点赞|赞|棒|太好|OK|好的|行)", t, re.IGNORECASE):
            return "thumbs_up"
        if re.search(r"(OK|可以|没问题)", t, re.IGNORECASE):
            return "ok"
        # 看向方向
        if re.search(r"(左边|向左)", t):
            return "look_left"
        if re.search(r"(右边|向右)", t):
            return "look_right"
        if re.search(r"(上面|向上)", t):
            return "look_up"
        if re.search(r"(下面|向下)", t):
            return "look_down"
        # 招手/过来
        if re.search(r"(过来|到这边|请来)", t):
            return "come_here"
        # 默认无匹配
        return ""
    
    def _post_process_sequence(self, sequence: List[tuple], total_duration: float, intent: str, emotion: str, flow_mode: bool, end_settle: str) -> List[tuple]:
        seq = list(sequence)
        seq = self._balance_bilateral(seq)
        
        # 🎯 在timestamps模式下（end_settle='never'），严格按照时间轴对齐，不添加rest
        if end_settle == 'never':
            return seq
            
        if total_duration < 2.0:
            settle_dur = 0.4
        elif total_duration < 6.0:
            settle_dur = 0.6
        else:
            settle_dur = 0.9
        if not seq:
            return [("rest", settle_dur)]
        # 保持短指令的“动作性”手势作为最后一步：
        # 若总时长很短，且序列末尾是极短的非休止填充(<=0.25s)，而倒数第二步是快速保持类动作，
        # 则将填充并入该动作，保证最后一步是该动作，从而避免后续追加rest。
        if total_duration < 2.0 and len(seq) >= 2:
            last1_name, last1_dur = seq[-1]
            last2_name, last2_dur = seq[-2]
            def _is_quick_action(n: str) -> bool:
                if not n:
                    return False
                if n in ("肌肉", "thumbs_up", "left_thumbs_up", "点赞"):
                    return True
                if any(k in n for k in ("point", "handshake")):
                    return True
                if "embrace" in n:
                    return True
                return False
            if last1_name not in ("rest", "neutral") and last1_dur <= 0.25 and _is_quick_action(last2_name):
                seq[-2] = (last2_name, last2_dur + last1_dur)
                seq.pop()
        last_name, last_dur = seq[-1]
        # 优先：用户配置的 quick-hold 手势，任何时长均不回中
        try:
            if hasattr(self, "_quick_hold_gestures") and last_name in self._quick_hold_gestures:
                return seq
        except Exception:
            pass
        # 特例：肌肉动作无论时长均不回中
        if last_name in ("肌肉",):
            return seq
        # 特例：拥抱类无论时长均不回中
        if "embrace" in last_name:
            return seq
        # 短指令的“动作性”手势，默认最后不回中（如 点赞/指向/OK 等），长语音仍回中
        # 🎯 按你的要求：挥手、握手结束后如果语音结束，应回到 rest，
        # 因此这里不再把 handshake 视为“永久保持”动作。
        quick_hold_exact = ("thumbs_up", "left_thumbs_up", "点赞", "ok_gesture")
        quick_hold_keys = ("point", "ok")  # 从原来的 ("point", "handshake", "ok") 中去掉 handshake
        
        # 🎯 对于点赞/OK/指向等动作，短句结尾可以保持在动作姿态，不强制回中
        if last_name in quick_hold_exact or any(k in last_name for k in quick_hold_keys):
            return seq
        
        # 🎯 对于短时长的其他动作，保持原有逻辑
        if total_duration < 2.0:
            # 这里可以添加其他短时长的特殊处理
            pass
        if last_name in ("rest", "neutral"):
            if last_dur < settle_dur:
                seq[-1] = (last_name, settle_dur)
        else:
            seq.append(("rest", settle_dur))
        return seq
    
    def _balance_bilateral(self, sequence: List[tuple]) -> List[tuple]:
        left = 0
        right = 0
        for name, _ in sequence:
            side = self._guess_side(name)
            if side == 'left':
                left += 1
            elif side == 'right':
                right += 1
        if abs(right - left) <= 1:
            return sequence
        if left == 0 or right == 0:
            return sequence
        target = 'left' if left < right else 'right'
        need = max(0, abs(right - left) - 1)
        seq = list(sequence)
        changed = 0
        for i, (name, dur) in enumerate(seq):
            if changed >= need:
                break
            side = self._guess_side(name)
            if target == 'left' and side == 'right':
                cand = self._to_side(name, 'left')
                if cand != name and cand in self.base_gestures:
                    seq[i] = (cand, dur)
                    changed += 1
                    right -= 1
                    left += 1
            elif target == 'right' and side == 'left':
                cand = self._to_side(name, 'right')
                if cand != name and cand in self.base_gestures:
                    seq[i] = (cand, dur)
                    changed += 1
                    left -= 1
                    right += 1
            if abs(right - left) <= 1:
                break
        return seq
    
    def _guess_side(self, name: str) -> str:
        n = name
        if 'left' in n:
            return 'left'
        if 'right' in n:
            return 'right'
        both_keys = ("both", "open_arms", "applaud", "embrace", "welcome", "hands_together", "clap")
        for k in both_keys:
            if k in n:
                return 'both'
        head_keys = ("nod", "shake", "tilt", "look", "bow", "think", "attentive")
        for k in head_keys:
            if k in n:
                return 'neutral'
        if n.startswith("point_forward") or n == "point_forward":
            return 'right'
        return 'neutral'
    
    def _to_side(self, name: str, target: str) -> str:
        n = name
        bg = self.base_gestures
        if target == 'left':
            if 'right' in n:
                cand = n.replace('right', 'left')
                if cand in bg:
                    return cand
            m = {
                'thumbs_up': 'left_thumbs_up',
                'ok_gesture': 'left_ok_gesture',
                'peace_sign': 'left_peace_sign',
                'stop_gesture': 'left_stop_gesture',
                'come_here': 'left_come_here',
                'point_forward': 'point_left_forward',
                'point_forward_firm': 'point_left_forward',
                'point_forward_soft': 'point_left_forward',
            }
            return m.get(n, n)
        else:
            if 'left' in n:
                cand = n.replace('left', 'right')
                if cand in bg:
                    return cand
            m = {
                'left_thumbs_up': 'thumbs_up',
                'left_ok_gesture': 'ok_gesture',
                'left_peace_sign': 'peace_sign',
                'left_stop_gesture': 'stop_gesture',
                'left_come_here': 'come_here',
                'point_left_forward': 'point_forward',
            }
            return m.get(n, n)
    
    def _generate_timed_gesture_sequence(self, gesture_groups: List[List[str]], 
                                       total_duration: float, base_duration: float, 
                                       emotion: str, intent: str, flow_mode: bool) -> List[tuple]:
        """
        基于总时长生成手势序列
        
        Args:
            gesture_groups: 手势组列表
            total_duration: 总语音时长(秒)
            base_duration: 基础手势时长
            emotion: 情感
            intent: 意图
        
        Returns:
            手势序列 [(gesture_name, duration), ...]
        """
        sequence = []
        remaining_time = total_duration
        
        # 开始手势 - 较短
        start_gesture = self._select_start_gesture(emotion)
        start_duration = min(base_duration * 0.6, remaining_time * 0.1)  # 不超过总时长的10%
        sequence.append((start_gesture, start_duration))
        remaining_time -= start_duration
        
        # 结束手势预留时间 - 回零位
        end_duration = min(base_duration * 0.8, remaining_time * 0.15)  # 预留15%时间回零
        remaining_time -= end_duration
        
        # 主要手势序列 - 填满剩余时间
        if remaining_time > 0:
            # 计算需要多少个手势来填满时间
            avg_gesture_duration = base_duration * 1.5  # 平均手势时长
            estimated_gestures = max(1, int(remaining_time / avg_gesture_duration))
            
            # 生成主要手势
            used_gestures = set()
            for i in range(estimated_gestures):
                # 循环选择手势组
                group_index = i % len(gesture_groups)
                gesture_group = gesture_groups[group_index]
                
                # 从组中选择手势
                if isinstance(gesture_group, list):
                    available_gestures = [g for g in gesture_group if g not in used_gestures]
                    if not available_gestures:
                        used_gestures.clear()
                        available_gestures = gesture_group
                    
                    gesture_name = random.choice(available_gestures)
                    used_gestures.add(gesture_name)
                else:
                    gesture_name = gesture_group
                
                # 计算这个手势的时长
                if i == estimated_gestures - 1:
                    # 最后一个手势用完剩余时间
                    gesture_duration = remaining_time
                else:
                    # 平均分配时间，加上随机变化
                    avg_time_per_gesture = remaining_time / (estimated_gestures - i)
                    gesture_duration = avg_time_per_gesture * random.uniform(0.7, 1.3)
                    gesture_duration = min(gesture_duration, remaining_time)
                
                sequence.append((gesture_name, gesture_duration))
                remaining_time -= gesture_duration
                
                if remaining_time <= 0:
                    break
        
        # 🎯 结束手势 - 说话时不要添加 neutral，保持动作连贯，将预留时间并入最后一步
        if sequence:
            last_name, last_dur = sequence[-1]
            # 无论是否 flow_mode，都不添加 neutral，而是延长最后一个动作
            sequence[-1] = (last_name, last_dur + end_duration)
            # if flow_mode or ("point" in last_name or "embrace" in last_name):
            #     sequence[-1] = (last_name, last_dur + end_duration)
            # else:
            #     sequence.append(("neutral", end_duration))
        
        return sequence
    
    def _apply_emotion_intensity(self, angles, emotion):
        """根据情感调节手势强度"""
        intensity = self.emotion_intensity_map.get(emotion, 1.0)
        
        # 只调节非零角度，保持零位不变
        adjusted_angles = []
        for angle in angles:
            if abs(angle) > 0.1:  # 非零角度
                adjusted_angles.append(angle * intensity)
            else:
                adjusted_angles.append(angle)
        
        return adjusted_angles

    def _support_gain_by_emotion(self, emotion: str) -> float:
        if emotion in ("excited", "enthusiastic"):
            return 0.15
        if emotion in ("angry",):
            return 0.14
        if emotion in ("happy",):
            return 0.13
        if emotion in ("sad", "calm"):
            return 0.08
        return 0.12

    def _apply_contralateral_support(self, angles: List[float], gesture_name: str, emotion: str) -> List[float]:
        """为单侧主导手势添加对侧轻度配合（10~15%幅度）。"""
        side = self._guess_side(gesture_name)
        if side not in ("left", "right"):
            return angles
        # 双手手势不做对侧配合
        if side == 'both':
            return angles
        res = list(angles)
        gain = self._support_gain_by_emotion(emotion)
        free_thresh = 2.0  # 对侧若已显著参与则不覆盖
        left_ids = [2, 3, 4, 5, 6]
        right_ids = [7, 8, 9, 10, 11]
        pairs = list(zip(left_ids, right_ids))
        if side == "right":
            for li, ri in pairs:
                primary = angles[ri]
                other = angles[li]
                if abs(other) <= free_thresh and abs(primary) > 0.1:
                    res[li] = other + primary * gain
        else:  # left
            for li, ri in pairs:
                primary = angles[li]
                other = angles[ri]
                if abs(other) <= free_thresh and abs(primary) > 0.1:
                    res[ri] = other + primary * gain
        return res
    
    def _merge_consecutive_gestures(self, sequence: List[tuple]) -> List[tuple]:
        """合并连续相同的手势
        
        Args:
            sequence: 手势序列 [(gesture_name, duration), ...]
        
        Returns:
            合并后的序列
        """
        if not sequence:
            return []
        
        merged = []
        current_gesture = list(sequence[0])  # [gesture_name, duration]
        
        for i in range(1, len(sequence)):
            next_gesture = sequence[i]
            
            # 如果手势名称相同，合并时长
            if next_gesture[0] == current_gesture[0]:
                current_gesture[1] += next_gesture[1]
                print(f"[去重] 合并重复手势: {current_gesture[0]}, 新时长: {current_gesture[1]:.2f}s")
            else:
                # 不同手势，保存当前手势，开始新的
                merged.append(tuple(current_gesture))
                current_gesture = list(next_gesture)
        
        # 添加最后一个手势
        merged.append(tuple(current_gesture))
        
        return merged
    
    def _get_base_duration(self, emotion: str) -> float:
        """根据情感获取基础时长 - 减小30%以增加动作数量"""
        duration_map = {
            "excited": 0.56,      # 🎯 兴奋时动作更快：0.8 → 0.56（减少30%）
            "happy": 0.7,         # 🎯 快乐时正常速度：1.0 → 0.7（减少30%）
            "sad": 1.26,          # 🎯 悲伤时动作较慢：1.8 → 1.26（减少30%）
            "angry": 0.49,        # 🎯 愤怒时动作急促：0.7 → 0.49（减少30%）
            "surprised": 0.63,    # 🎯 惊讶时动作稍快：0.9 → 0.63（减少30%）
            "calm": 0.98,         # 🎯 平静时动作较慢：1.4 → 0.98（减少30%）
            "confident": 0.77,    # 🎯 自信时稍慢：1.1 → 0.77（减少30%）
            "enthusiastic": 0.63, # 🎯 热情时较快：0.9 → 0.63（减少30%）
            "neutral": 0.7        # 🎯 中性时正常：1.0 → 0.7（减少30%）
        }
        return duration_map.get(emotion, 0.7)  # 🎯 默认值也减少30%
    
    def _calculate_gesture_count(self, text_length: int, emotion: str) -> int:
        """根据文本长度和情感计算手势数量 - 改进版，支持更多手势"""
        # 🎯 增加手势数量，让每句话有更多动作
        if text_length <= 2:
            base_count = 2  # 🎯 很短文本：1 → 2（增加）
        elif text_length <= 5:
            base_count = 3  # 🎯 短文本：2 → 3（增加）
        elif text_length <= 10:
            base_count = 6  # 🎯 中短文本：4 → 6（增加50%）
        elif text_length <= 20:
            base_count = 9  # 🎯 中等文本：6 → 9（增加50%）
        elif text_length <= 35:
            base_count = 12  # 🎯 较长文本：8 → 12（增加50%）
        elif text_length <= 50:
            base_count = 15  # 🎯 长文本：10 → 15（增加50%）
        elif text_length <= 80:
            base_count = 18  # 🎯 很长文本：12 → 18（增加50%）
        else:
            base_count = min(text_length // 4, 20)  # 🎯 超长文本，每4字一个手势，最多20个（加快）
        
        # 情感调节 - 更积极的调整
        if emotion in ["excited", "enthusiastic"]:
            base_count += 2  # 兴奋情感增加更多手势
        elif emotion in ["sad", "calm"]:
            base_count = max(base_count - 1, 2)  # 平静情感减少但至少2个
        elif emotion in ["angry"]:
            base_count = max(base_count, 3)  # 愤怒至少3个手势表达强度
        
        return min(base_count, 15)  # 最多15个手势
    
    def _select_start_gesture(self, emotion: str) -> str:
        """根据情感选择起始手势"""
        start_gestures = {
            "excited": ["alert", "confident_relaxed"],
            "happy": ["neutral", "alert"],
            "sad": ["neutral"],
            "angry": ["alert", "confident_assertive"],
            "surprised": ["neutral", "alert"],
            "calm": ["neutral", "attentive_listen"],
            "neutral": ["neutral"]
        }
        candidates = [g for g in start_gestures.get(emotion, ["neutral", "alert"]) if g != "rest"]
        if not candidates:
            candidates = ["neutral", "alert"]
        return random.choice(candidates)
    
    def _select_transition_gesture(self, emotion: str) -> str:
        """选择过渡手势"""
        transition_gestures = ["rest", "neutral", "attentive_listen", "alert"]
        return random.choice(transition_gestures)
    
    def _select_end_gesture(self, emotion: str, intent: str) -> str:
        """根据情感和意图选择结束手势"""
        if intent == "greeting":
            return random.choice(["rest", "attentive_listen", "alert"])
        elif intent == "farewell":
            # 🎯 说话时不要使用 neutral，用有动作的手势替代
            return random.choice(["rest", "both_hands_explain", "bow_respectful"])
        elif intent == "question":
            return random.choice(["attentive_listen", "curious_lean", "rest"])
        else:
            # 🎯 说话时不要使用 neutral，用有动作的手势替代
            return random.choice(["rest", "both_hands_explain", "attentive_listen"])
    
    def _select_emphasis_gesture(self, intent: str, emotion: str) -> str:
        """选择强调手势"""
        emphasis_gestures = {
            "explanation": ["point_right_formal", "point_left_formal", "explain_right_emphatic", "explain_left_emphatic"],
            "emphasis": ["point_forward_firm", "confident_assertive", "nod_strong"],
            "greeting": ["wave_right_energetic", "wave_left_energetic", "open_arms_wide"],
            "question": ["tilt_curious", "curious_lean", "think_deep"],
            "agreement": ["nod_strong", "gesture_ok", "applaud_ready"],
            "disagreement": ["shake_strong", "gesture_stop", "confident_assertive"]
        }
        
        candidates = emphasis_gestures.get(intent, ["nod_strong", "confident_assertive", "point_forward_firm"])
        return random.choice(candidates)
    
    def add_natural_variations(self, gesture_angles: List[float]) -> List[float]:
        """为手势添加自然的微小变化"""
        varied_angles = []
        for angle in gesture_angles:
            if abs(angle) > 0.1:  # 只对非零角度添加变化
                # 添加±2度的随机变化
                variation = random.uniform(-2.0, 2.0)
                varied_angles.append(angle + variation)
            else:
                # 零角度保持不变或添加很小的变化
                if random.random() < 0.1:  # 10%概率添加微小变化
                    varied_angles.append(random.uniform(-1.0, 1.0))
                else:
                    varied_angles.append(angle)
        return varied_angles
    
    def create_gesture_blend(self, gesture1: str, gesture2: str, blend_ratio: float = 0.5) -> List[float]:
        """混合两个手势创建新的变化"""
        if gesture1 not in self.base_gestures or gesture2 not in self.base_gestures:
            return self.base_gestures.get(gesture1, self.base_gestures["neutral"])
        
        angles1 = self.base_gestures[gesture1]
        angles2 = self.base_gestures[gesture2]
        
        blended_angles = []
        for a1, a2 in zip(angles1, angles2):
            blended = a1 * (1 - blend_ratio) + a2 * blend_ratio
            blended_angles.append(blended)
        
        return blended_angles
    
    def _extend_action_sequence(self, base_sequence: List[tuple], total_duration: float, 
                               emotion: str, action: str) -> List[tuple]:
        """扩展动作序列以匹配总时长"""
        current_duration = sum(duration for _, duration in base_sequence)
        remaining_time = total_duration - current_duration
        
        if remaining_time <= 0:
            return base_sequence
        
        print(f"🔄 扩展序列: 当前{current_duration:.1f}s，需要扩展{remaining_time:.1f}s")
        
        # 获取适合的手势组
        gesture_groups = self.intent_gesture_map.get("explanation", self.intent_gesture_map["neutral"])
        
        # 计算需要添加的手势数量
        avg_gesture_duration = 2.5  # 平均手势时长
        additional_gestures = max(1, int(remaining_time / avg_gesture_duration))
        
        # 生成扩展序列
        extended_sequence = list(base_sequence)  # 复制原序列
        
        # 添加过渡和补充手势
        used_gestures = set()
        for i in range(additional_gestures):
            # 选择手势组
            group_index = i % len(gesture_groups)
            gesture_group = gesture_groups[group_index]
            
            if isinstance(gesture_group, list):
                available_gestures = [g for g in gesture_group if g not in used_gestures]
                if not available_gestures:
                    used_gestures.clear()
                    available_gestures = gesture_group
                gesture_name = random.choice(available_gestures)
                used_gestures.add(gesture_name)
            else:
                gesture_name = gesture_group
            
            # 计算手势时长
            if i == additional_gestures - 1:
                # 最后一个手势用完剩余时间
                gesture_duration = remaining_time
            else:
                gesture_duration = min(avg_gesture_duration, remaining_time)
            
            extended_sequence.append((gesture_name, gesture_duration))
            remaining_time -= gesture_duration
            
            if remaining_time <= 0:
                break
        
        return extended_sequence
    
    def _generate_extended_gesture_sequence(self, action: str, total_duration: float, 
                                          emotion: str, action_gesture_map: dict, flow_mode: bool) -> List[tuple]:
        """为单个动作生成扩展的手势序列"""
        sequence = []

        # 🎯 特例：语音片段本身就很短（<=1.5s）时，默认走语义填充，让这一小段里也能拆成多个更短的动作，
        # 避免“一个长动作压整句”且动作显得比语音慢。
        # 但对于挥手/握手/拥抱/点赞/OK等“关键大动作”，仍然保留专门的手势，而不是完全被语义填充替代。
        important_actions = {
            "wave_right", "wave_left", "wave_both",
            "handshake", "embrace", "clap", "applaud",
            "thumbs_up", "ok", "point", "point_forward",
            "present", "show",
        }
        if total_duration <= 1.5 and action not in important_actions:
            return self._generate_semantic_filler(total_duration, emotion, "explanation", flow_mode)
        
        # 🎯 获取主要动作手势 - 说话时不要使用 neutral，用有动作的手势替代
        main_gesture = action_gesture_map.get(action, "both_hands_explain")
        
        # 🎯 特殊处理头部动作 - 直接使用简单序列
        head_actions = ["look_left", "look_right", "look_up", "look_down", "nod", "shake_head"]
        if action in head_actions:
            print(f"🎭 头部动作'{action}' -> 使用简单序列: {main_gesture}")
            # 头部动作使用简单的3步序列
            action_duration = min(total_duration * 0.8, 2.0)  # 主要动作时长
            rest_duration = (total_duration - action_duration) / 2
            
            sequence = [
                (main_gesture, action_duration + rest_duration)
            ]
            # 🎯 说话时不要添加 neutral，保持动作连贯
            # if not flow_mode:
            #     sequence.append(("neutral", rest_duration))
            return sequence
        
        # 🎯 其他有明确手势映射的动作，根据时长决定序列复杂度
        if main_gesture != "neutral" and main_gesture in self.base_gestures:
            print(f"🎭 动作'{action}' -> 使用映射手势: {main_gesture}")
            
            # 🎯 对于中等长度（<3秒），使用简单序列；>=3秒的片段走“多手势复杂序列”，增加动作数量
            if total_duration < 3.0:
                # 主要动作尽量短一些，避免一个手势压满整段
                action_duration = min(total_duration * 0.7, 1.5)  # 主要动作最多1.5s
                rest_duration = max(0.0, total_duration - action_duration)

                # 指向/拥抱：快速或持续，不回 neutral
                if "point" in main_gesture:
                    fast_duration = min(0.8, total_duration)
                    sequence = [
                        (main_gesture, fast_duration)
                    ]
                elif "embrace" in main_gesture:
                    sequence = [
                        (main_gesture, action_duration + rest_duration)
                    ]
                else:
                    sequence = [
                        (main_gesture, action_duration + rest_duration)
                    ]
                    if not flow_mode:
                        sequence.append(("neutral", rest_duration))
                return sequence
            
            # 🎯 对于长文字（>=10秒），生成复杂序列，但重点突出主要动作
            # 继续使用下面的复杂序列生成逻辑，但会优先使用main_gesture
        
        # 其他动作使用原来的复杂序列生成逻辑
        action_duration = 2.0  # 主要动作时长略缩短
        
        # 计算需要的总手势数：减小分母，让每段时间内有更多手势
        # 例如：5秒语音 -> int(5/1.2)≈4~5个手势，而不是原来的2个
        gesture_count = max(3, min(12, int(total_duration / 1.2)))  # 至少3个，最多12个手势
        
        print(f"🎭 为动作'{action}'生成{gesture_count}个手势，总时长{total_duration:.1f}s")
        
        # 开始手势（避免以 rest 开头）
        start_time = min(total_duration * 0.1, 1.0)
        start_name = main_gesture if main_gesture != "neutral" else self._select_start_gesture(emotion)
        if start_name == "rest":
            start_name = "alert"
        sequence.append((start_name, start_time))
        
        # 主要动作手势 (重复出现)
        main_gesture_count = max(1, gesture_count // 3)  # 主要手势出现次数
        
        # 获取适合的手势组用于填充
        gesture_groups = self.intent_gesture_map.get("explanation", self.intent_gesture_map["neutral"])
        all_gestures = []
        for group in gesture_groups:
            if isinstance(group, list):
                all_gestures.extend(group)
            else:
                all_gestures.append(group)
        
        # 移除重复并添加主要手势
        all_gestures = list(set(all_gestures))
        if main_gesture not in all_gestures:
            all_gestures.append(main_gesture)
        
        # 生成主体手势序列
        remaining_time = total_duration - sequence[0][1]  # 减去开始手势时间
        end_time = min(remaining_time * 0.1, 1.0)  # 结束手势时间
        main_time = remaining_time - end_time
        
        if gesture_count > 2:  # 除了开始和结束手势
            avg_time = main_time / (gesture_count - 2)
            
            used_gestures = set()
            for i in range(gesture_count - 2):
                # 每隔几个手势使用主要动作
                if i % 3 == 1:  # 每3个手势中有1个是主要动作
                    gesture_name = main_gesture
                else:
                    # 选择其他手势
                    available = [g for g in all_gestures if g not in used_gestures and g != main_gesture]
                    if not available:
                        used_gestures.clear()
                        available = [g for g in all_gestures if g != main_gesture]
                    
                    # 🎯 说话时不要使用 neutral，用有动作的手势替代
                    gesture_name = random.choice(available) if available else "both_hands_explain"
                    used_gestures.add(gesture_name)
                
                # 时长变化
                gesture_duration = avg_time * random.uniform(0.8, 1.2)
                sequence.append((gesture_name, gesture_duration))
        
        # 🎯 说话时不要添加 neutral，保持动作连贯
        # 结束手势：流模式下或特定动作不回 neutral
        # if not flow_mode and action not in ("point", "point_forward", "embrace", "handshake", "ok_gesture", "thumbs_up"):
        #     sequence.append(("neutral", end_time))
        
        return sequence
    
    def apply_emotion_modulation(self, gesture_angles: List[float], emotion: str) -> List[float]:
        """根据情感调节手势幅度"""
        intensity = self.emotion_intensity_map.get(emotion, 1.0)
        
        # 调节非零角度的幅度
        modulated_angles = []
        for angle in gesture_angles:
            if abs(angle) > 0.1:  # 非零角度
                modulated_angles.append(angle * intensity)
            else:
                modulated_angles.append(angle)
        
        # 确保角度在安全范围内
        safe_angles = []
        for angle in modulated_angles:
            safe_angles.append(max(-50, min(50, angle)))  # 限制在±50度
        
        return safe_angles
    
    def get_gesture_info(self) -> Dict:
        """获取手势库信息"""
        return {
            "available_gestures": list(self.base_gestures.keys()),
            "supported_intents": list(self.intent_gesture_map.keys()),
            "total_gestures": len(self.base_gestures)
        }
