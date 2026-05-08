#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丰富的手势策略模块
根据语义信息规划自然、多样化的手势动作序列
"""

from typing import List, Dict, Tuple
import random

class GesturePolicy:
    def __init__(self):
        """初始化手势策略"""
        
        # 丰富的5自由度手臂手势库
        # 关节索引: 0=头左右, 1=头上下, 2=左前后, 3=左外展, 4=左大臂转, 5=左肘, 6=左小臂转
        #          7=右前后, 8=右外展, 9=右大臂转, 10=右肘, 11=右小臂转
        
        # 🎭 动作序列定义 - 挥手等动态动作
        self.action_sequences = {
            "wave_right_sequence": [
                {"gesture": "wave_right_prepare", "duration": 4},      # 🎯 抬手到位 - 再加快
                {"gesture": "wave_right_prepare", "duration": 0.15},     # 🎯 到位稳定 - 再加快
                {"gesture": "wave_right_left", "duration": 0.1},        # 向左挥 - 再加快
                {"gesture": "wave_right_right", "duration": 0.1},       # 向右挥 - 再加快
                {"gesture": "wave_right_left", "duration": 0.1},        # 向左挥 - 再加快
                {"gesture": "wave_right_right", "duration": 0.1},       # 向右挥 - 再加快
                {"gesture": "wave_right_left", "duration": 0.1},        # 向左挥 - 再加快
                {"gesture": "rest", "duration": 0.3},                    # 放下 - 再加快
            ],
            "wave_left_sequence": [
                {"gesture": "wave_left_prepare", "duration": 4},       # 🎯 抬手到位 - 再加快
                {"gesture": "wave_left_prepare", "duration": 0.15},      # 🎯 到位稳定 - 再加快
                {"gesture": "wave_left_right", "duration": 0.1},        # 向右挥 - 再加快
                {"gesture": "wave_left_left", "duration": 0.1},         # 向左挥 - 再加快
                {"gesture": "wave_left_right", "duration": 0.1},        # 向右挥 - 再加快
                {"gesture": "wave_left_left", "duration": 0.1},         # 向左挥 - 再加快
                {"gesture": "wave_left_right", "duration": 0.1},        # 向右挥 - 再加快
                {"gesture": "rest", "duration": 0.3},                    # 放下 - 再加快
            ],
            "wave_both_sequence": [
                {"gesture": "wave_both_prepare", "duration": 4},       # 🎯 双手抬起到位 - 再加快
                {"gesture": "wave_both_prepare", "duration": 0.15},      # 🎯 到位稳定 - 再加快
                {"gesture": "wave_both_out", "duration": 0.1},           # 双手向外挥 - 再加快
                {"gesture": "wave_both_in", "duration": 0.1},            # 双手向内挥 - 再加快
                {"gesture": "wave_both_out", "duration": 0.1},           # 双手向外挥 - 再加快
                {"gesture": "wave_both_in", "duration": 0.1},            # 双手向内挥 - 再加快
                {"gesture": "wave_both_out", "duration": 0.1},           # 双手向外挥 - 再加快
                {"gesture": "rest", "duration": 0.3},                    # 放下 - 再加快
            ],
            "handshake_sequence": [
                {"gesture": "handshake_extend", "duration": 2},        # 伸手 - 加快
                {"gesture": "handshake_grip", "duration": 0.8},          # 握手 - 加快
                {"gesture": "handshake_shake", "duration": 0.6},         # 轻摇 - 加快
                {"gesture": "rest", "duration": 0.4},                    # 放下 - 加快
            ],
            "embrace_sequence": [
                {"gesture": "embrace_gentle", "duration": 1.0},          # 轻柔张开双臂
                {"gesture": "embrace_warm", "duration": 2.0},            # 温暖拥抱姿态
                {"gesture": "embrace_passionate", "duration": 1.5},      # 激情拥抱
                {"gesture": "embrace_warm", "duration": 0.8},            # 回到温暖拥抱
            ],
            # 🎯 基于挥手动作的常用动作序列
            "clap_sequence": [
                {"gesture": "applaud_prepare", "duration": 1.0},         # 双手抬起
                {"gesture": "applaud_clap", "duration": 0.2},            # 鼓掌1
                {"gesture": "applaud_prepare", "duration": 0.2},         # 分开
                {"gesture": "applaud_clap", "duration": 0.2},            # 鼓掌2
                {"gesture": "applaud_prepare", "duration": 0.2},         # 分开
                {"gesture": "applaud_clap", "duration": 0.2},            # 鼓掌3
                {"gesture": "rest", "duration": 0.5},                    # 放下
            ],
            "point_forward_sequence": [
                {"gesture": "point_forward", "duration": 0.8},           # 指向前方（更快）
            ],
            "thumbs_up_sequence": [
                {"gesture": "thumbs_up", "duration": 1.5},               # 点赞
                {"gesture": "rest", "duration": 0.2},                    # 放下
            ],
            "ok_gesture_sequence": [
                {"gesture": "ok_gesture", "duration": 1.5},              # OK手势
                {"gesture": "rest", "duration": 0.2},                    # 放下
            ],
            "stop_sequence": [
                {"gesture": "stop_gesture", "duration": 1.8},            # 停止手势
                {"gesture": "rest", "duration": 0.2},                    # 放下
            ]
        }
        
        self.base_gestures = {
            # 基础姿态
            "neutral": [0.0] * 12,  # 中性姿态
            "rest": [0, 0, -5, 5, 0, 10, 0, 5, 5, 0, 10, 0],         # 自然休息姿态
            "alert": [0, -2, 0, 8, 0, 15, 0, 0, 8, 0, 15, 0],        # 警觉姿态
            
            # 右手挥手动作序列姿态 - 大幅度挥手
            "wave_right_prepare": [0, 0, 0, 0, 0, 0, 0, -70, 20, 0, 90, 0],     # 🎯 挥手准备：大幅抬手
            "wave_right_left": [0, 0, 0, 0, 0, 0, 0, -70, 20, 30, 90, -60],      # 🎯 向左大幅挥动
            "wave_right_right": [0, 0, 0, 0, 0, 0, 0, -70, 20, -30, 90, 60],      # 🎯 向右大幅挥动
            
            # 右手手势系列 - 5自由度优化
            "wave_right_gentle": [0, 0, 0, 0, 0, 0, 0, -10, 20, 0, 25, -10],  # 轻柔挥手
            "wave_right_energetic": [0, 0, 0, 0, 0, 0, 0, -20, 30, 0, 90, -60], # 🎯 5DOF挥手：肘弯曲90°+小臂转动-60°
            "wave_right_dramatic": [0, 0, 0, 0, 0, 0, 0, -25, 35, 0, 100, -80], # 🎯 戏剧性挥手：更大弯曲+转动
            "point_right_casual": [0, 0, 0, 0, 0, 0, 0, -20, 12, 0, 35, 0],   # 随意指向
            "point_right_formal": [0, 0, 0, 0, 0, 0, 0, -40, 25, 0, 65, 0],   # 正式指向(增强)
            "point_right_commanding": [0, 0, 0, 0, 0, 0, 0, -50, 35, 0, 85, 0], # 指挥性指向(新增)
            "point_forward": [0, 0, 0, 0, 0, 0, 0, -70, 0, 0, 90, 0],          # 🎯 指向前方：基于挥手准备姿态，伸直手臂
            "explain_right_soft": [0, 0, 0, 0, 0, 0, 0, -15, 15, -3, 20, 0],  # 温和解释
            "explain_right_emphatic": [0, 0, 0, 0, 0, 0, 0, -35, 35, -15, 50, 0], # 强调解释(增强)
            "explain_right_passionate": [0, 0, 0, 0, 0, 0, 0, -45, 50, -20, 70, 0], # 激情解释(新增)
            "present_right": [0, 0, 0, 0, 0, 0, 0, -15, 25, 0, 20, 5],       # 展示手势
            "present_right_grand": [0, 0, 0, 0, 0, 0, 0, -25, 45, 0, 40, 15], # 盛大展示(新增)
            "invite_right": [0, 0, 0, 0, 0, 0, 0, -10, 20, 5, 15, 10],       # 邀请手势
            "invite_right_welcoming": [0, 0, 0, 0, 0, 0, 0, -30, 25, 10, 70, 20], # 🎯 5DOF握手：减少外展，增加肘弯曲
            
            # 左手挥手动作序列姿态 - 大幅度挥手
            "wave_left_prepare": [0, 0, -70, 20, 0, 90, 0, 0, 0, 0, 0, 0],     # 🎯 左手挥手准备：按右手范围
            "wave_left_left": [0, 0, -70, 20, -30, 90, 60, 0, 0, 0, 0, 0],     # 🎯 向左大幅挥动：按右手范围
            "wave_left_right": [0, 0, -70, 20, 30, 90, -60, 0, 0, 0, 0, 0],    # 🎯 向右大幅挥动：按右手范围
            
            # 双手挥手动作序列姿态 - 按右手范围设计
            "wave_both_prepare": [0, 0, -70, 20, 0, 90, 0, -70, 20, 0, 90, 0], # 🎯 双手挥手准备：两手都按右手范围
            "wave_both_out": [0, 0, -70, 20, -30, 90, 60, -70, 20, 30, 90, -60], # 🎯 双手向外挥：左手向左，右手向右
            "wave_both_in": [0, 0, -70, 20, 30, 90, -60, -70, 20, -30, 90, 60], # 🎯 双手向内挥：左手向右，右手向左
            
            # 握手动作序列姿态 - 温和礼貌
            "handshake_extend": [0, 0, 0, 0, 0, 0, 0, -15, 15, 0, 45, 0],      # 🎯 温和伸手准备
            "handshake_grip": [0, 0, 0, 0, 0, 0, 0, -15, 15, 0, 80, 10],       # 🎯 轻柔握手姿态
            "handshake_shake": [0, 0, 0, 0, 0, 0, 0, -15, 15, 0, 50, 10],      # 🎯 轻微摇动
            
            # 左手手势系列 - 从小幅度到大幅度 (2号关节现在是反向映射，需要调整符号)
            "wave_left_gentle": [0, 0, -10, 20, 0, 25, -10, 0, 0, 0, 0, 0],   # 轻柔挥手
            "wave_left_energetic": [0, 0, -20, 30, 0, 90, 60, 0, 0, 0, 0, 0], # 🎯 5DOF左手挥手：肘弯曲90°+小臂转动60°
            "wave_left_dramatic": [0, 0, -25, 35, 0, 100, 80, 0, 0, 0, 0, 0], # 🎯 戏剧性左手挥手：更大弯曲+转动
            "point_left_casual": [0, 0, -20, 12, 0, 35, 0, 0, 0, 0, 0, 0],    # 随意指向
            "point_left_formal": [0, 0, -40, 25, 0, 65, 0, 0, 0, 0, 0, 0],    # 正式指向(增强)
            "point_left_commanding": [0, 0, -50, 35, 0, 85, 0, 0, 0, 0, 0, 0], # 指挥性指向(新增)
            "point_left_forward": [0, 0, -70, 0, 0, 90, 0, 0, 0, 0, 0, 0],    # 🎯 左手指向前方：基于左手挥手准备姿态
            "explain_left_soft": [0, 0, -15, 15, -3, 20, 0, 0, 0, 0, 0, 0],   # 温和解释
            "explain_left_emphatic": [0, 0, -35, 35, -15, 50, 0, 0, 0, 0, 0, 0], # 强调解释(增强)
            "explain_left_passionate": [0, 0, -45, 50, -20, 70, 0, 0, 0, 0, 0, 0], # 激情解释(新增)
            "present_left": [0, 0, -15, 25, 0, 20, 5, 0, 0, 0, 0, 0],         # 展示手势
            "present_left_grand": [0, 0, -25, 45, 0, 40, 15, 0, 0, 0, 0, 0],  # 盛大展示(新增)
            "invite_left": [0, 0, -10, 20, 5, 15, 10, 0, 0, 0, 0, 0],         # 邀请手势
            "invite_left_welcoming": [0, 0, -20, 40, 15, 35, 25, 0, 0, 0, 0, 0], # 热情邀请(新增)
            
            # 🎯 左手常用手势系列
            "left_thumbs_up": [0, 0, -45, 15, 0, 60, -30, 0, 0, 0, 0, 0],      # 左手点赞
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
            "embrace_warm": [0, 0, -60, 40, 10, 45, 0, -60, 40, 10, 45, 0],    # 🤗 拥抱：基于挥手动作，双臂向前张开
            "embrace_passionate": [0, 0, -40, 60, -15, 80, 0, -40, 60, 15, 80, 0], # 激情拥抱(新增)
            "clap_ready_high": [0, 0, -15, 15, 0, 25, 0, -15, 15, 0, 25, 0],  # 高位鼓掌
            "clap_ready_energetic": [0, 0, -30, 30, 0, 45, 0, -30, 30, 0, 45, 0], # 活力鼓掌(新增)
            "hands_together": [0, 0, -10, 10, 0, 30, 0, -10, 10, 0, 30, 0],   # 双手合十
            "celebration": [0, 0, -40, 60, 0, 70, 0, -40, 60, 0, 70, 0],      # 庆祝手势(新增)
            
            # 🎯 基于挥手动作的常用手势系列
            "applaud_prepare": [0, 0, -70, 20, 0, 90, 0, -70, 20, 0, 90, 0],   # 鼓掌准备：双手抬起
            "applaud_clap": [0, 0, -50, 30, 0, 90, 0, -50, 30, 0, 90, 0],      # 鼓掌动作：双手靠近
            "stop_gesture": [0, 0, 0, 0, 0, 0, 0, -70, 0, 0, 90, 0],           # 停止手势：右手伸直
            "come_here": [0, 0, 0, 0, 0, 0, 0, -70, 20, 0, 45, 0],             # 过来手势：手掌向下
            "thumbs_up": [0, 0, 0, 0, 0, 0, 0, -45, 15, 0, 60, 30],            # 点赞手势：拇指向上
            "ok_gesture": [0, 0, 0, 0, 0, 0, 0, -30, 10, 0, 45, 0],            # OK手势：手指圈
            "peace_sign": [0, 0, 0, 0, 0, 0, 0, -60, 15, 0, 75, 45],           # V字手势：胜利手势
            
            # 头部表情手势 - 从轻微到强烈
            "nod_slight": [0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 轻微点头
            "nod_strong": [0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],             # 强烈点头(增强)
            "nod_emphatic": [0, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强调点头(新增)
            "shake_slight": [8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],            # 轻微摇头
            "shake_strong": [30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强烈摇头(增强)
            "shake_dramatic": [45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 戏剧性摇头(新增)
            "tilt_curious": [12, -3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],          # 好奇歪头
            "tilt_dramatic": [25, -8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 戏剧性歪头(新增)
            "tilt_thoughtful": [-8, -5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 思考歪头
            "bow_respectful": [0, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 尊敬鞠躬
            "bow_deep": [0, 35, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],               # 深度鞠躬(新增)
            "bow_apologetic": [0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # 道歉鞠躬
            
            # 左右看动作
            "look_left_slight": [30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 轻微向左看
            "look_left_strong": [45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],       # 明显向左看
            "look_left_dramatic": [45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 大幅向左看
            "look_right_slight": [-30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 轻微向右看
            "look_right_strong": [-45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],     # 明显向右看
            "look_right_dramatic": [-45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],   # 大幅向右看
            "look_up": [0, -40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],               # 向上看
            "look_down": [0, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],              # 向下看
            
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
            "shake_strong": [30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],           # 强烈摇头
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
        
        # 丰富的意图到手势映射规则 - 包含大幅度手势
        self.intent_gesture_map = {
            "greeting": [
                ["wave_right_gentle", "wave_left_gentle", "wave_right_energetic", "wave_right_dramatic"],
                ["open_arms_moderate", "open_arms_wide", "welcome_gesture", "welcome_grand"],
                ["nod_slight", "nod_strong", "bow_respectful"],
                ["rest", "neutral"]
            ],
            "farewell": [
                ["wave_right_gentle", "wave_left_gentle", "wave_right_energetic", "wave_left_dramatic"],
                ["bow_respectful", "bow_deep", "nod_slight"],
                ["hands_together", "open_arms_moderate", "rest"],
                ["neutral"]
            ],
            "explanation": [
                ["explain_right_soft", "explain_left_soft", "present_right", "present_left"],
                ["explain_right_emphatic", "explain_left_emphatic", "explain_right_passionate", "explain_left_passionate"],
                ["point_right_casual", "point_left_casual", "point_right_formal", "point_left_formal"],
                ["curious_lean", "attentive_listen", "attentive_focused"],
                ["rest", "neutral"]
            ],
            "question": [
                ["think_light", "think_deep", "think_profound", "tilt_thoughtful"],
                ["curious_lean", "curious_intense", "tilt_curious", "tilt_dramatic"],
                ["attentive_listen", "attentive_focused"],
                ["invite_right", "invite_left", "invite_right_welcoming"],
                ["rest", "neutral"]
            ],
            "emphasis": [
                ["point_forward_firm", "point_right_commanding", "point_left_commanding"],
                ["explain_right_passionate", "explain_left_passionate", "confident_commanding"],
                ["nod_strong", "nod_emphatic", "gesture_ok"],
                ["present_right_grand", "present_left_grand"],
                ["rest", "neutral"]
            ],
            "excitement": [
                ["wave_right_dramatic", "wave_left_dramatic", "celebration"],
                ["open_arms_triumphant", "embrace_passionate", "welcome_grand"],
                ["clap_ready_energetic", "surprise_strong"],
                ["nod_emphatic", "confident_commanding"],
                ["rest", "neutral"]
            ],
            "agreement": [
                ["nod_strong", "nod_emphatic", "nod_slight", "gesture_ok"],
                ["wave_right_gentle", "wave_left_gentle", "applaud_ready", "clap_ready_energetic"],
                ["confident_relaxed", "confident_assertive", "attentive_listen"],
                ["rest", "neutral"]
            ],
            "disagreement": [
                ["shake_strong", "shake_dramatic", "shake_slight", "gesture_stop"],
                ["tilt_thoughtful", "tilt_dramatic", "think_light", "think_deep"],
                ["confident_assertive", "confident_commanding", "attentive_listen"],
                ["rest", "neutral"]
            ],
            "surprise": [
                ["surprise_mild", "surprise_strong", "surprise_shocked"],
                ["open_arms_wide", "open_arms_triumphant"],
                ["tilt_dramatic", "curious_intense"],
                ["rest", "neutral"]
            ],
            "neutral": [
                ["rest", "neutral", "attentive_listen"],
                ["alert", "neutral"],
                ["neutral"]
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
        
        Returns:
            手势序列列表，每个元素包含gesture_name, joint_angles, duration
        """
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
        
        # 🎯 检查是否有具体动作指令
        if detected_actions:
            print(f"🎭 检测到动作指令: {detected_actions}")
            sequence = self._generate_action_based_sequence(detected_actions, total_duration, emotion)
        else:
            # 获取手势组和基础参数
            gesture_groups = self.intent_gesture_map.get(intent, self.intent_gesture_map["neutral"])
            base_duration = self._get_base_duration(emotion)
            
            # 🎯 基于总时长计算手势序列
            sequence = self._generate_timed_gesture_sequence(
                gesture_groups, total_duration, base_duration, emotion, intent
            )
        
        # 生成最终的手势数据
        final_sequence = []
        for gesture_name, duration in sequence:
            # 获取基础手势角度
            base_angles = self.base_gestures.get(gesture_name, self.base_gestures["neutral"])
            
            # 🎯 对于拥抱等关键动作，不添加随机变化，保持精确角度
            if gesture_name in ["embrace_warm", "embrace_gentle", "embrace_passionate", "rest", "neutral"]:
                # 关键动作使用精确角度，不添加随机变化
                final_angles = self._apply_emotion_intensity(base_angles.copy(), emotion)
            else:
                # 其他动作添加自然变化和情感调节
                varied_angles = self.add_natural_variations(base_angles.copy())
                final_angles = self._apply_emotion_intensity(varied_angles, emotion)
            
            final_sequence.append({
                'gesture_name': gesture_name,
                'joint_angles': final_angles,
                'duration': duration
            })
        
        print(f"✅ 生成{len(final_sequence)}个手势，总时长{sum(g['duration'] for g in final_sequence):.1f}秒")
        return final_sequence
    
    def _generate_action_based_sequence(self, detected_actions: List[str], 
                                      total_duration: float, emotion: str) -> List[tuple]:
        """🎯 基于检测到的动作生成手势序列"""
        
        # 🎭 动作到序列的映射 - 优先使用动态序列
        action_sequence_map = {
            # 挥手类 - 使用动态序列
            "wave_right": "wave_right_sequence",
            "wave_left": "wave_left_sequence", 
            "wave_both": "wave_both_sequence",  # 🎯 使用新的双手挥手序列
            
            # 握手类 - 使用动态序列
            "handshake": "handshake_sequence",
            
            # 拥抱类 - 不使用序列，直接用静态手势
            # "embrace": "embrace_sequence",  # 注释掉，让拥抱使用静态手势
        }
        
        # 动作到静态手势的映射 - 作为备选
        action_gesture_map = {
            # 拥抱类
            "embrace": "embrace_warm",
            
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
            "thumbs_up": "thumbs_up",
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
            
            # 拥抱类 - 加快拥抱动作
            "embrace": 3.0,         # 拥抱加快 (从5.0->3.0)
            
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
                    sequence = [(step["gesture"], step["duration"]) for step in action_sequence]
                    sequence_duration = sum(step["duration"] for step in action_sequence)
                    print(f"🎭 动态序列: {action} -> {sequence_name} (序列时长: {sequence_duration:.1f}s)")
                    
                    # 🎯 关键修复：如果序列时长远小于总时长，需要扩展
                    if sequence_duration < total_duration * 0.3:  # 序列时长小于总时长的30%
                        print(f"⚠️  序列时长({sequence_duration:.1f}s)远小于语音时长({total_duration:.1f}s)，扩展序列")
                        sequence = self._extend_action_sequence(sequence, total_duration, emotion, action)
                else:
                    print(f"⚠️  序列 {sequence_name} 未定义，生成扩展手势序列")
                    sequence = self._generate_extended_gesture_sequence(action, total_duration, emotion, action_gesture_map)
            else:
                # 🎯 修复：不再使用简单的3个手势，而是生成扩展序列
                print(f"🎭 生成扩展手势序列: {action} (总时长: {total_duration:.1f}s)")
                sequence = self._generate_extended_gesture_sequence(action, total_duration, emotion, action_gesture_map)
            
        # 如果有多个动作，依次执行
        else:
            sequence = []
            
            for i, action in enumerate(detected_actions):
                # 检查是否有动态序列
                if action in action_sequence_map:
                    sequence_name = action_sequence_map[action]
                    if sequence_name in self.action_sequences:
                        action_sequence = self.action_sequences[sequence_name]
                        for step in action_sequence:
                            sequence.append((step["gesture"], step["duration"]))
                    else:
                        # 回退到静态手势（避免以 rest 开头）
                        gesture_name = action_gesture_map.get(action, "neutral")
                        standard_duration = action_durations.get(action, 3.0)
                        if sequence:  # 非首个动作，添加过渡
                            sequence.append(("neutral", 0.3))
                        sequence.append((gesture_name, standard_duration))
                        # 指向动作不追加回中立
                        if "point" not in gesture_name and "embrace" not in gesture_name:
                            sequence.append(("neutral", 0.3))
                else:
                    # 使用静态手势（避免以 rest 开头）
                    gesture_name = action_gesture_map.get(action, "neutral")
                    standard_duration = action_durations.get(action, 3.0)
                    if sequence:  # 非首个动作，添加过渡
                        sequence.append(("neutral", 0.3))
                    sequence.append((gesture_name, standard_duration))
                    # 指向动作不追加回中立
                    if "point" not in gesture_name and "embrace" not in gesture_name:
                        sequence.append(("neutral", 0.3))
                
                # 在动作之间添加间隔（若上一步是指向则不加中立间隔）
                if i < len(detected_actions) - 1:
                    if not (sequence and ("point" in sequence[-1][0] or "embrace" in sequence[-1][0])):
                        sequence.append(("neutral", 0.5))
            
            print(f"🎭 多动作序列: {len(detected_actions)}个动作")
        
        print(f"🎭 生成动作序列: {[f'{name}({dur:.1f}s)' for name, dur in sequence]}")
        return sequence
    
    def _generate_timed_gesture_sequence(self, gesture_groups: List[List[str]], 
                                       total_duration: float, base_duration: float, 
                                       emotion: str, intent: str) -> List[tuple]:
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
        
        # 结束手势 - 回零位；若最后一个是指向手势，则不回中立，将预留时间加到最后一步
        if sequence and ("point" in sequence[-1][0] or "embrace" in sequence[-1][0]):
            last_name, last_dur = sequence[-1]
            sequence[-1] = (last_name, last_dur + end_duration)
        else:
            sequence.append(("neutral", end_duration))
        
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
    
    def _get_base_duration(self, emotion: str) -> float:
        """根据情感获取基础时长"""
        duration_map = {
            "excited": 0.8,      # 兴奋时动作更快
            "happy": 1.0,        # 快乐时正常速度
            "sad": 1.8,          # 悲伤时动作较慢
            "angry": 0.7,        # 愤怒时动作急促
            "surprised": 0.9,    # 惊讶时动作稍快
            "calm": 1.4,         # 平静时动作较慢
            "confident": 1.1,    # 自信时稍慢
            "enthusiastic": 0.9, # 热情时较快
            "neutral": 1.0       # 中性时正常
        }
        return duration_map.get(emotion, 1.0)
    
    def _calculate_gesture_count(self, text_length: int, emotion: str) -> int:
        """根据文本长度和情感计算手势数量 - 改进版，支持更多手势"""
        # 🎯 新的计算逻辑：更多手势，更细腻的表达
        if text_length <= 2:
            base_count = 1  # 很短文本(如"你好")
        elif text_length <= 5:
            base_count = 2  # 短文本
        elif text_length <= 10:
            base_count = 4  # 中短文本 - 增加手势数
        elif text_length <= 20:
            base_count = 6  # 中等文本 - 增加手势数
        elif text_length <= 35:
            base_count = 8  # 较长文本 - 增加手势数
        elif text_length <= 50:
            base_count = 10  # 长文本 - 增加手势数
        elif text_length <= 80:
            base_count = 12  # 很长文本 - 大幅增加
        else:
            base_count = min(text_length // 6, 15)  # 超长文本，每6字一个手势，最多15个
        
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
            return random.choice(["rest", "neutral", "bow_respectful"])
        elif intent == "question":
            return random.choice(["attentive_listen", "curious_lean", "rest"])
        else:
            return random.choice(["rest", "neutral", "attentive_listen"])
    
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
                                          emotion: str, action_gesture_map: dict) -> List[tuple]:
        """为单个动作生成扩展的手势序列"""
        sequence = []
        
        # 获取主要动作手势
        main_gesture = action_gesture_map.get(action, "neutral")
        
        # 🎯 特殊处理头部动作 - 直接使用简单序列
        head_actions = ["look_left", "look_right", "look_up", "look_down", "nod", "shake_head"]
        if action in head_actions:
            print(f"🎭 头部动作'{action}' -> 使用简单序列: {main_gesture}")
            # 头部动作使用简单的3步序列
            action_duration = min(total_duration * 0.8, 2.0)  # 主要动作时长
            rest_duration = (total_duration - action_duration) / 2
            
            sequence = [
                (main_gesture, action_duration + rest_duration),
                ("neutral", rest_duration)
            ]
            return sequence
        
        # 🎯 其他有明确手势映射的动作，根据时长决定序列复杂度
        if main_gesture != "neutral" and main_gesture in self.base_gestures:
            print(f"🎭 动作'{action}' -> 使用映射手势: {main_gesture}")
            
            # 🎯 对于短文字（<10秒），使用简单序列
            if total_duration < 10.0:
                action_duration = min(total_duration * 0.8, 3.0)  # 主要动作时长
                rest_duration = (total_duration - action_duration) / 2

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
                        (main_gesture, action_duration + rest_duration),
                        ("neutral", rest_duration)
                    ]
                return sequence
            
            # 🎯 对于长文字（>=10秒），生成复杂序列，但重点突出主要动作
            # 继续使用下面的复杂序列生成逻辑，但会优先使用main_gesture
        
        # 其他动作使用原来的复杂序列生成逻辑
        action_duration = 3.0  # 主要动作时长
        
        # 计算需要的总手势数
        gesture_count = max(3, int(total_duration / 2.5))  # 至少3个手势
        
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
                    
                    gesture_name = random.choice(available) if available else "neutral"
                    used_gestures.add(gesture_name)
                
                # 时长变化
                gesture_duration = avg_time * random.uniform(0.8, 1.2)
                sequence.append((gesture_name, gesture_duration))
        
        # 结束手势：指向/拥抱动作不回 neutral
        if action not in ("point", "point_forward", "embrace"):
            sequence.append(("neutral", end_time))
        
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
