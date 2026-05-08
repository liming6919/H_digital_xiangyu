#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强手势策略 - 语言驱动的连续交流动作系统
整合语义分析、韵律感知和动作连贯性管理
"""

from typing import Dict, List, Tuple, Optional
import random
import os
import json
from .linguistic_analyzer import LinguisticAnalyzer
from .prosodic_gesture_planner import ProsodicGesturePlanner
from .gesture_coherence_manager import GestureCoherenceManager

class EnhancedGesturePolicy:
    def __init__(self):
        """初始化增强手势策略"""
        
        # 初始化各个分析器
        self.linguistic_analyzer = LinguisticAnalyzer()
        self.prosodic_planner = ProsodicGesturePlanner()
        self.coherence_manager = GestureCoherenceManager()
        
        # 加载基础手势库（从原有的gesture_policy.py继承）
        self._load_base_gestures()
        
        # 🎯 添加动作序列定义（从gesture_policy.py复制）
        self._load_action_sequences()

        # 🎯 与传统 GesturePolicy 对齐的幅度/左右交替参数
        # 用于“每个动作都带头动作”的左右交替
        self._forced_head_lr_sign = 1
        # 说话阶段手臂幅度增强目标（度），保持与 GesturePolicy 中的设置一致
        self._min_arm_amplitude_deg = 35.0
        
        # 语言驱动的手势映射策略
        self.linguistic_gesture_strategies = {
            "parallel": {
                "pattern": "alternating",
                "spatial_mapping": {"left": "first_concept", "right": "second_concept"},
                "rhythm": "balanced"
            },
            "contrastive": {
                "pattern": "opposing",
                "spatial_mapping": {"left": "old_idea", "right": "new_idea"},
                "rhythm": "contrasted"
            },
            "progressive": {
                "pattern": "escalating",
                "intensity_curve": "increasing",
                "rhythm": "building"
            },
            "enumeration": {
                "pattern": "sequential",
                "spatial_mapping": {"progression": "left_to_right"},
                "rhythm": "stepped"
            },
            "causal": {
                "pattern": "directional",
                "spatial_mapping": {"cause": "left", "effect": "right"},
                "rhythm": "flowing"
            }
        }
        
        # 话语功能到手势序列的映射
        self.discourse_gesture_sequences = {
            "introduction": {
                "opening": ["open_arms_moderate", "welcome_gesture"],
                "presentation": ["present_right", "both_hands_present"],
                "engagement": ["both_hands_explain", "head_slight_nod"]
            },
            "explanation": {
                "setup": ["explain_right_soft", "present_right"],
                "elaboration": ["both_hands_explain", "explain_right_emphatic"],
                "clarification": ["point_right_formal", "both_hands_frame"]
            },
            "emphasis": {
                "buildup": ["explain_right_emphatic", "both_hands_emphasize"],
                "climax": ["point_right_commanding", "nod_strong"],
                "reinforcement": ["both_hands_forward", "confident_assertive"]
            },
            "comparison": {
                "setup": ["both_hands_balance", "present_left"],
                "contrast": ["point_left_formal", "point_right_formal"],
                "synthesis": ["both_hands_gather", "both_hands_present"]
            },
            "conclusion": {
                "summary": ["both_hands_gather", "both_hands_present"],
                "finalization": ["nod_strong", "both_hands_down"],
                "closure": ["rest", "neutral"]
            }
        }
        
        print("✅ 增强手势策略初始化完成")
    
    def _load_action_sequences(self):
        """加载动作序列定义"""
        # 🎯 从gesture_policy.py复制动作序列定义
        self.action_sequences = {
            "wave_right_sequence": [
                {"gesture": "wave_right_prepare", "duration": 1.2},
                {"gesture": "wave_right_left", "duration": 1.2},
                {"gesture": "wave_right_right", "duration": 1.2},
                {"gesture": "wave_right_left", "duration": 1.2},
                {"gesture": "wave_right_right", "duration": 1.2},
                {"gesture": "wave_right_left", "duration": 1.2},
                {"gesture": "rest", "duration": 0.8},
            ],
            "wave_left_sequence": [
                {"gesture": "wave_left_prepare", "duration": 1.2},
                {"gesture": "wave_left_right", "duration": 1.2},
                {"gesture": "wave_left_left", "duration": 1.2},
                {"gesture": "wave_left_right", "duration": 1.2},
                {"gesture": "wave_left_left", "duration": 1.2},
                {"gesture": "wave_left_right", "duration": 1.2},
                {"gesture": "rest", "duration": 0.8},
            ],
            "wave_both_sequence": [
                {"gesture": "wave_both_prepare", "duration": 1.2},
                {"gesture": "wave_both_out", "duration": 1.2},
                {"gesture": "wave_both_in", "duration": 1.2},
                {"gesture": "wave_both_out", "duration": 1.2},
                {"gesture": "wave_both_in", "duration": 1.2},
                {"gesture": "wave_both_out", "duration": 1.2},
                {"gesture": "rest", "duration": 0.8},
            ],
            "handshake_sequence": [
                {"gesture": "handshake_extend", "duration": 0.9},
                {"gesture": "handshake_grip", "duration": 1.2},
                {"gesture": "handshake_shake", "duration": 0.9},
                {"gesture": "rest", "duration": 0.6},
            ],
            "embrace_sequence": [
                {"gesture": "embrace_gentle", "duration": 2.0},
                {"gesture": "embrace_warm", "duration": 4.0},
                {"gesture": "embrace_passionate", "duration": 3.0},
                {"gesture": "embrace_warm", "duration": 2.0},
            ],
            "clap_sequence": [
                {"gesture": "applaud_prepare", "duration": 0.9},
                {"gesture": "applaud_clap", "duration": 0.3},
                {"gesture": "applaud_prepare", "duration": 0.3},
                {"gesture": "applaud_clap", "duration": 0.3},
                {"gesture": "applaud_prepare", "duration": 0.3},
                {"gesture": "applaud_clap", "duration": 0.3},
                {"gesture": "rest", "duration": 0.75},
            ],
            "thumbs_up_sequence": [
                {"gesture": "thumbs_up", "duration": 2.25},
                {"gesture": "rest", "duration": 0.3},
            ],
            "ok_gesture_sequence": [
                {"gesture": "ok_gesture", "duration": 2.25},
                {"gesture": "rest", "duration": 0.3},
            ],
            "stop_sequence": [
                {"gesture": "stop_gesture", "duration": 2.7},
                {"gesture": "rest", "duration": 0.3},
            ]
        }
    
    def _load_base_gestures(self):
        """加载基础手势库"""
        # 🎯 从gesture_policy.py复制完整的手势定义
        self.base_gestures = {
            # 基础姿态
            "neutral": [0.0] * 12,
            "rest": [0, 0, -5, 5, 0, 10, 0, 5, 5, 0, 10, 0],
            "alert": [0, -2, 0, 8, 0, 15, 0, 0, 8, 0, 15, 0],
            
            # 右手手势系列
            "wave_right_gentle": [0, 0, 0, 0, 0, 0, 0, -10, 20, 0, 25, -10],
            "wave_right_energetic": [0, 0, 0, 0, 0, 0, 0, -20, 30, 0, 90, -60],
            "point_right_formal": [0, 0, 0, 0, 0, 0, 0, -40, 25, 0, 65, 0],
            "point_right_commanding": [0, 0, 0, 0, 0, 0, 0, -50, 35, 0, 85, 0],
            "explain_right_soft": [0, 0, 0, 0, 0, 0, 0, -15, 15, -3, 20, 0],
            "explain_right_emphatic": [0, 0, 0, 0, 0, 0, 0, -35, 35, -15, 50, 0],
            "present_right": [0, 0, 0, 0, 0, 0, 0, -15, 25, 0, 20, 5],
            "confident_assertive": [0, 0, 0, 0, 0, 0, 0, -30, 25, 0, 45, 0],
            
            # 左手手势系列
            "wave_left_gentle": [0, 0, -10, 20, 0, 25, -10, 0, 0, 0, 0, 0],
            "wave_left_energetic": [0, 0, -20, 30, 0, 90, 60, 0, 0, 0, 0, 0],
            "point_left_formal": [0, 0, -40, 25, 0, 65, 0, 0, 0, 0, 0, 0],
            "point_left_commanding": [0, 0, -50, 35, 0, 85, 0, 0, 0, 0, 0, 0],
            "explain_left_soft": [0, 0, -15, 15, -3, 20, 0, 0, 0, 0, 0, 0],
            "explain_left_emphatic": [0, 0, -35, 35, -15, 50, 0, 0, 0, 0, 0, 0],
            "present_left": [0, 0, -15, 25, 0, 20, 5, 0, 0, 0, 0, 0],
            
            # 双手协调手势
            "both_hands_explain": [0, 0, -20, 20, 0, 30, 0, -20, 20, 0, 30, 0],
            "both_hands_present": [0, 0, -30, 35, 10, 20, 0, -30, 35, -10, 20, 0],
            "both_hands_emphasize": [0, 0, -25, 30, 0, 40, 0, -25, 30, 0, 40, 0],
            "both_hands_frame": [0, 0, -40, 40, 15, 60, 0, -40, 40, -15, 60, 0],
            "both_hands_gather": [0, 0, -30, 25, 10, 50, 0, -30, 25, -10, 50, 0],
            "both_hands_balance": [0, 0, -20, 40, 0, 30, 0, -20, 40, 0, 30, 0],
            "both_hands_forward": [0, 0, -40, 10, 0, 60, 0, -40, 10, 0, 60, 0],
            "both_hands_down": [0, 0, 10, 15, 0, 20, 0, 10, 15, 0, 20, 0],
            "open_arms_moderate": [0, 0, -8, 25, 0, 15, 0, -8, 25, 0, 15, 0],
            "welcome_gesture": [0, 2, -12, 30, 5, 20, 8, -12, 30, -5, 20, -8],
            
            # 拥抱手势
            "embrace_gentle": [0, 0, -15, 25, -3, 30, 0, -15, 25, 3, 30, 0],
            "embrace_warm": [0, 0, -70, 60, 15, 60, 0, -70, 60, -15, 60, 0],
            "embrace_passionate": [0, 0, -40, 60, -15, 80, 0, -40, 60, 15, 80, 0],
            
            # 头部手势
            "head_micro_nod": [0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_slight_nod": [0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "nod_strong": [0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_shake": [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_tilt_left": [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_tilt_right": [-3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "think_deep": [0, -8, 0, 0, 0, 50, 0, 0, 0, 0, 0, 0],
            "attentive_listen": [0, 0, 0, 5, 0, 10, 0, 0, 5, 0, 10, 0],
            
            # 其他常用手势
            "thumbs_up": [0, 0, -20, 0, 0, 80, 0, -20, 0, 0, 80, 0],
            "ok_gesture": [0, 0, 0, 0, 0, 0, 0, -30, 10, 0, 45, 0],
            "stop_gesture": [0, 0, 0, 0, 0, 0, 0, -70, 0, 0, 90, 0],
            "applaud_prepare": [0, 0, -70, 20, 0, 90, 0, -70, 20, 0, 90, 0],
            "applaud_clap": [0, 0, -50, 30, 0, 90, 0, -50, 30, 0, 90, 0],
            
            # 更多头部手势
            "shake_strong": [20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_tilt_left": [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_look_left": [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            
            # 🎯 新增缺失的头部手势
            "head_natural_left": [8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_natural_right": [-8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_look_right": [-5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_up": [0, -3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "head_micro_down": [0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "think_light": [0, -5, 0, 0, 0, 30, 0, 0, 0, 0, 0, 0],
            "curious_lean": [5, -3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            
            # 其他手势
            "attentive_listen": [0, 0, 0, 5, 0, 10, 0, 0, 5, 0, 10, 0],
            "think_deep": [0, -8, 0, 0, 0, 50, 0, 0, 0, 0, 0, 0]
        }
    
    def plan_linguistic_gesture_sequence(self, semantic_info: Dict) -> List[Dict]:
        """基于语言学分析规划手势序列 - 改进版：融合原版成功经验
        
        Args:
            semantic_info: 语义信息，包含文本、时间戳等
            
        Returns:
            手势序列
        """
        # 提取基本信息
        text = semantic_info.get('utterance_text', '') or semantic_info.get('clean_text', '')
        timestamps = semantic_info.get('timestamps', [])
        total_duration = semantic_info.get('speech_duration', 3.0)
        intent = semantic_info.get('intent', 'explanation')
        emotion = semantic_info.get('emotion', 'neutral')
        detected_actions = semantic_info.get('detected_actions', [])
        
        # 🎯 检测到关键词动作（挥手、点赞、数字“一二三五”等）时，
        # 不再整句回退到传统模式，而是继续使用增强模式，
        # 仅将 detected_actions 作为附加信号交给内部逻辑处理。
        if detected_actions:
            print(f"🎭 检测到关键词动作: {detected_actions}，在增强模式下处理")
        
        print(f"🧠 语义驱动手势规划: {text[:50]}...")
        
        # 🎯 改进策略：使用原版的基础逻辑，添加语义增强
        gesture_data = self._generate_enhanced_sequence_with_original_logic(
            text, total_duration, intent, emotion, semantic_info
        )

        # 🎯 统一总时长：至少覆盖完整语音时长，缺口用随机动作补齐
        gesture_data = self._normalize_total_duration_with_padding(
            gesture_data, total_duration, intent=intent, emotion=emotion
        )

        # 🎯 去除长时间“刷同一个动作”（例如 both_hands_explain 连续过多，且所有变体都算在一起）
        gesture_data = self._limit_repetitive_gestures(gesture_data, max_consecutive=2)

        # 🎯 进一步限制某些大幅度手势族（如 both_hands_explain 家族）在整段中的占比，
        # 避免整段说话几乎都保持双手举着
        gesture_data = self._limit_family_ratio(
            gesture_data,
            base_name="both_hands_explain",
            max_ratio=0.15,   # 最多 ~35% 的手势来自这个家族
        )

        return gesture_data
    
    def _generate_structure_based_sequence(self, linguistic_constraints: Dict, 
                                         prosodic_features: Dict, total_duration: float,
                                         intent: str, emotion: str) -> List[Tuple[str, float]]:
        """基于语言结构生成手势序列"""
        
        structure_type = linguistic_constraints['structure_type']
        primary_function = linguistic_constraints['primary_function']
        prosodic_segments = linguistic_constraints['prosodic_segments']
        
        # 获取结构策略
        strategy = self.linguistic_gesture_strategies.get(structure_type, {})
        
        # 获取话语功能序列
        function_sequences = self.discourse_gesture_sequences.get(primary_function, {})
        
        sequence = []
        
        if prosodic_segments:
            # 基于韵律分段生成手势
            sequence = self._generate_segment_based_sequence(
                prosodic_segments, strategy, function_sequences, total_duration
            )
        else:
            # 基于话语功能生成手势
            sequence = self._generate_function_based_sequence(
                function_sequences, strategy, total_duration, intent, emotion
            )
        
        # 应用结构特定的调整
        if structure_type == "parallel":
            sequence = self._apply_parallel_pattern(sequence)
        elif structure_type == "contrastive":
            sequence = self._apply_contrastive_pattern(sequence)
        elif structure_type == "progressive":
            sequence = self._apply_progressive_pattern(sequence)
        elif structure_type == "enumeration":
            sequence = self._apply_enumeration_pattern(sequence)
        
        return sequence
    
    def _generate_enhanced_sequence_with_original_logic(self, text: str, total_duration: float, 
                                                      intent: str, emotion: str, semantic_info: Dict) -> List[Dict]:
        """使用原版逻辑生成手势序列，添加语义增强
        
        这个方法融合了原版gesture_policy.py的成功经验和语义驱动的智能
        """
        # 🎯 步骤1: 使用原版的基础参数
        from .gesture_policy import GesturePolicy
        original_policy = GesturePolicy()
        
        # 获取原版的手势组和基础时长
        gesture_groups = original_policy.intent_gesture_map.get(intent, original_policy.intent_gesture_map["neutral"])
        base_duration = original_policy._get_base_duration(emotion)
        
        print(f"🎯 使用原版基础参数: base_duration={base_duration:.2f}s, 手势组数={len(gesture_groups)}")
        
        # 🎯 步骤2: 语义分析（简化版）
        semantic_enhancements = self._analyze_text_semantics(text)
        print(f"📝 语义分析: {semantic_enhancements}")
        
        # 🎯 步骤3: 使用原版的时长分配逻辑
        sequence = self._generate_original_style_sequence(
            gesture_groups, total_duration, base_duration, emotion, intent, semantic_enhancements
        )
        
        # 🎯 步骤4: 应用语义增强（轻量级）
        enhanced_sequence = self._apply_semantic_enhancements(sequence, semantic_enhancements, text)
        
        # 🎯 步骤5: 转换为最终格式（使用原版逻辑）
        return self._convert_to_final_format_original_style(enhanced_sequence, emotion, original_policy)
    
    def _analyze_text_semantics(self, text: str) -> Dict:
        """简化的语义分析，只提取关键特征"""
        enhancements = {
            'has_question': any(word in text for word in ['什么', '怎么', '为什么', '如何', '吗', '呢']),
            'has_emphasis': any(word in text for word in ['重要', '关键', '特别', '非常', '最']),
            'has_contrast': any(word in text for word in ['但是', '然而', '相反', '而', '不过']),
            'has_enumeration': any(word in text for word in ['首先', '其次', '最后', '第一', '第二']),
            'sentence_length': len(text),
            'complexity': 'simple' if len(text) < 20 else 'medium' if len(text) < 50 else 'complex'
        }
        return enhancements
    
    def _generate_original_style_sequence(self, gesture_groups: List, total_duration: float, 
                                        base_duration: float, emotion: str, intent: str, 
                                        semantic_enhancements: Dict) -> List[Tuple[str, float]]:
        """使用原版风格生成手势序列"""
        sequence = []
        remaining_time = total_duration
        
        # 🎯 原版逻辑：开始手势
        start_gesture = self._select_start_gesture_enhanced(emotion, semantic_enhancements)
        start_duration = min(base_duration * 0.6, remaining_time * 0.1)
        sequence.append((start_gesture, start_duration))
        remaining_time -= start_duration
        
        # 🎯 原版逻辑：预留结束时间
        end_duration = min(base_duration * 0.8, remaining_time * 0.15)
        remaining_time -= end_duration
        
        # 🎯 原版逻辑：主要手势序列
        if remaining_time > 0:
            # 使用原版的估算逻辑
            avg_gesture_duration = base_duration * 1.5
            estimated_gestures = max(1, int(remaining_time / avg_gesture_duration))
            
            # 🎯 语义增强：根据文本复杂度调整手势数量
            if semantic_enhancements['complexity'] == 'complex':
                estimated_gestures = int(estimated_gestures * 1.2)  # 复杂文本多20%手势
            elif semantic_enhancements['complexity'] == 'simple':
                estimated_gestures = max(1, int(estimated_gestures * 0.8))  # 简单文本少20%手势
            
            print(f"🎯 估算手势数量: {estimated_gestures} (原版逻辑+语义调整)")
            
            # 生成主要手势
            used_gestures = set()
            for i in range(estimated_gestures):
                # 🎯 语义增强的手势选择
                gesture_name = self._select_gesture_with_semantics(
                    gesture_groups, used_gestures, i, semantic_enhancements
                )
                used_gestures.add(gesture_name)
                
                # 🎯 原版的时长分配逻辑
                if i == estimated_gestures - 1:
                    gesture_duration = remaining_time
                else:
                    avg_time_per_gesture = remaining_time / (estimated_gestures - i)
                    gesture_duration = avg_time_per_gesture * random.uniform(0.7, 1.3)  # 原版参数
                    gesture_duration = min(gesture_duration, remaining_time)
                
                sequence.append((gesture_name, gesture_duration))
                remaining_time -= gesture_duration
                
                if remaining_time <= 0:
                    break
        
        # 🎯 原版逻辑：结束处理
        if sequence:
            last_name, last_dur = sequence[-1]
            # 简化的流模式判断
            if "point" in last_name or "embrace" in last_name:
                sequence[-1] = (last_name, last_dur + end_duration)
            else:
                sequence.append(("neutral", end_duration))
        
        return sequence
    
    def _select_start_gesture_enhanced(self, emotion: str, semantic_enhancements: Dict) -> str:
        """语义增强的开始手势选择"""
        if semantic_enhancements['has_question']:
            return "head_micro_tilt_left"  # 疑问时微微歪头
        elif semantic_enhancements['has_emphasis']:
            return "confident_assertive"  # 强调时自信姿态
        else:
            # 使用原版的默认逻辑
            start_gestures = ["neutral", "attentive_listen", "head_micro_nod"]
            return random.choice(start_gestures)
    
    def _select_gesture_with_semantics(self, gesture_groups: List, used_gestures: set, 
                                     index: int, semantic_enhancements: Dict) -> str:
        """语义增强的手势选择"""
        # 🎯 原版的基础选择逻辑
        group_index = index % len(gesture_groups)
        gesture_group = gesture_groups[group_index]
        
        if isinstance(gesture_group, list):
            available_gestures = [g for g in gesture_group if g not in used_gestures]
            if not available_gestures:
                used_gestures.clear()
                available_gestures = gesture_group
            
            # 🎯 语义增强：根据语义特征调整选择
            if semantic_enhancements['has_emphasis'] and index < 2:
                # 强调句的前两个手势倾向于使用强调性手势
                emphasis_gestures = [g for g in available_gestures if 'emphatic' in g or 'strong' in g or 'assertive' in g]
                if emphasis_gestures:
                    return random.choice(emphasis_gestures)
            
            if semantic_enhancements['has_question']:
                # 疑问句倾向于使用头部手势
                head_gestures = [g for g in available_gestures if 'head' in g or 'tilt' in g or 'nod' in g]
                if head_gestures and random.random() < 0.4:  # 40%概率
                    return random.choice(head_gestures)
            
            # 默认使用原版的随机选择
            return random.choice(available_gestures)
        else:
            return gesture_group
    
    def _apply_semantic_enhancements(self, sequence: List[Tuple[str, float]], 
                                   semantic_enhancements: Dict, text: str) -> List[Tuple[str, float]]:
        """应用轻量级的语义增强"""
        enhanced_sequence = []
        
        for i, (gesture_name, duration) in enumerate(sequence):
            # 🎯 语义增强：对比句的空间映射
            if semantic_enhancements['has_contrast'] and len(sequence) > 2:
                mid_point = len(sequence) // 2
                if i < mid_point and 'right' in gesture_name:
                    # 前半部分用左手表示旧观点
                    gesture_name = gesture_name.replace('right', 'left')
                elif i >= mid_point and 'left' in gesture_name:
                    # 后半部分用右手表示新观点
                    gesture_name = gesture_name.replace('left', 'right')
            
            # 🎯 语义增强：强调句的时长调整
            if semantic_enhancements['has_emphasis'] and 'emphatic' in gesture_name:
                duration *= 1.2  # 强调手势稍微延长
            
            enhanced_sequence.append((gesture_name, duration))
        
        return enhanced_sequence
    
    def _convert_to_final_format_original_style(self, sequence: List[Tuple[str, float]], 
                                              emotion: str, original_policy) -> List[Dict]:
        """使用原版风格转换为最终格式"""
        final_sequence = []
        
        for gesture_name, duration in sequence:
            # 🎯 使用原版的角度获取逻辑
            if gesture_name in original_policy.base_gestures:
                base_angles = original_policy.base_gestures[gesture_name]
            else:
                # 如果手势不存在，使用我们的手势库
                base_angles = self.base_gestures.get(gesture_name, self.base_gestures["neutral"])
            
            # 🎯 使用原版的自然变化和情感调节
            varied_angles = original_policy.add_natural_variations(base_angles.copy())
            final_angles = original_policy._apply_emotion_intensity(varied_angles, emotion)
            
            # 🎯 使用原版的头部时长调整
            adjusted_duration = original_policy._adjust_head_gesture_duration(gesture_name, duration)
            
            final_sequence.append({
                'gesture_name': gesture_name,
                'joint_angles': final_angles,
                'duration': adjusted_duration
            })
        return final_sequence

    def _normalize_total_duration_with_padding(self, gesture_data: List[Dict], target_duration: float,
                                               intent: str = "explanation", emotion: str = "neutral") -> List[Dict]:
        """
        确保整段手势的总时长至少覆盖语音总时长：
        - 如果总时长 < target_duration：用随机“说话手势”补齐，并精确修正最后一个动作的duration；
        - 如果总时长略大于 target_duration：保留不动（由上游时间轴算法再做精细对齐）。
        """
        if not gesture_data or target_duration is None:
            return gesture_data

        try:
            current_total = sum(float(g.get("duration", 0.0) or 0.0) for g in gesture_data)
        except Exception:
            return gesture_data

        # 已经足够长（或更长）：不再强行压缩，避免破坏语义节奏
        if current_total >= float(target_duration) * 0.98:
            return gesture_data

        remaining = float(target_duration) - current_total
        if remaining <= 0.1:
            return gesture_data

        padded = list(gesture_data)

        # 从一组“说话时合理的手势”中随机补齐
        filler_candidates = [
            "explain_right_soft", "present_right",
            "both_hands_present", "both_hands_forward",
            "head_micro_tilt_left", "head_micro_tilt_right",
            "head_micro_nod", "head_slight_nod",
        ]
        filler_candidates = [g for g in filler_candidates if g in self.base_gestures]
        if not filler_candidates:
            filler_candidates = ["attentive_listen"]

        # 每个补齐手势 0.8–1.8 秒，直到覆盖 target_duration
        while remaining > 0.2:
            name = random.choice(filler_candidates)
            dur = random.uniform(0.8, 1.8)
            if dur > remaining:
                dur = remaining

            base_angles = self.base_gestures.get(name, self.base_gestures.get("neutral", [0.0] * 12))
            adjusted = self._apply_emotion_adjustment(base_angles.copy(), emotion)
            angles = self._add_head_coordination(adjusted, name)
            angles = self._add_natural_variation(angles)

            padded.append({
                "gesture_name": name,
                "joint_angles": angles,
                "duration": float(dur),
            })
            remaining -= dur

        # 精确修正最后一个动作时长，使 sum(durations) ≈ target_duration
        total_after = sum(float(g.get("duration", 0.0) or 0.0) for g in padded)
        if total_after > 0 and abs(total_after - float(target_duration)) > 0.05:
            diff = total_after - float(target_duration)
            last = padded[-1]
            last_dur = float(last.get("duration", 0.0) or 0.0)
            new_last_dur = max(0.4, last_dur - diff)
            last["duration"] = new_last_dur

        return padded

    def _limit_repetitive_gestures(self, gesture_data: List[Dict], max_consecutive: int = 2) -> List[Dict]:
        """
        限制连续重复同一手势的次数（例如 both_hands_explain），
        超过次数时自动替换成同类但不同名称的动作，避免“一直刷同一个动作”。
        """
        if not gesture_data or max_consecutive <= 0:
            return gesture_data

        out: List[Dict] = []
        last_name = None
        count = 0

        # 候选替代手势池：说话场景中比较自然的一批动作
        # 候选替代手势池：说话场景中“手可以放下一会儿”的动作，多用单手/下沉动作
        alt_pool = [
            "explain_right_soft", "present_right",
            "present_left", "both_hands_down",
            "open_hand", "rest",
            "head_micro_tilt_left", "head_micro_tilt_right",
            "head_natural_left", "head_natural_right",
            "head_micro_nod", "head_slight_nod",
        ]
        alt_pool = [g for g in alt_pool if g in self.base_gestures]

        for g in gesture_data:
            raw_name = g.get("gesture_name") or g.get("gesture")
            # 归一化名称：忽略 __with__ 后面的头部修饰，避免
            # both_hands_explain 与 both_hands_explain__with__head_xxx 被当成不同手势
            name = None
            if isinstance(raw_name, str):
                name = raw_name.split("__with__")[0]
            else:
                name = raw_name

            if name == last_name:
                count += 1
            else:
                last_name = name
                count = 1

            if count > max_consecutive and alt_pool:
                # 需要替换，选一个不同于当前“基础名称”的手势
                candidates = [n for n in alt_pool if n != name]
                if not candidates:
                    candidates = alt_pool
                new_name = random.choice(candidates)

                base_angles = self.base_gestures.get(new_name, self.base_gestures.get("neutral", [0.0] * 12))
                adjusted = self._apply_emotion_adjustment(base_angles.copy(), "neutral")
                angles = self._add_head_coordination(adjusted, new_name)
                angles = self._add_natural_variation(angles)

                new_g = dict(g)
                new_g["gesture_name"] = new_name
                new_g["joint_angles"] = angles
                out.append(new_g)

                last_name = new_name
                # 连续计数重置为 1（因为换了一个新手势）
                count = 1
            else:
                out.append(g)

        return out

    def _limit_family_ratio(
        self,
        gesture_data: List[Dict],
        base_name: str,
        max_ratio: float = 0.35,
    ) -> List[Dict]:
        """
        限制某个“手势家族”（按基础名称，如 both_hands_explain）的整体占比：
        - 例如 max_ratio=0.35，意味着最多 35% 的手势可以来自这个家族；
        - 超出部分会替换为单手/下沉/头部微动等更自然的替代动作。
        """
        if not gesture_data or max_ratio <= 0.0:
            return gesture_data

        total = len(gesture_data)
        if total <= 0:
            return gesture_data

        # 统计基础名称为 base_name 的总数
        def _family_name(raw: Optional[str]) -> Optional[str]:
            if not isinstance(raw, str):
                return raw
            return raw.split("__with__")[0]

        family_indices: List[int] = []
        for idx, g in enumerate(gesture_data):
            raw = g.get("gesture_name") or g.get("gesture")
            fam = _family_name(raw)
            if fam == base_name:
                family_indices.append(idx)

        if not family_indices:
            return gesture_data

        allowed = max(2, int(total * max_ratio))
        if len(family_indices) <= allowed:
            return gesture_data

        # 替代表池：与 _limit_repetitive_gestures 保持一致
        alt_pool = [
            "explain_right_soft", "present_right",
            "present_left", "both_hands_down",
            "open_hand", "rest",
            "head_micro_tilt_left", "head_micro_tilt_right",
            "head_natural_left", "head_natural_right",
            "head_micro_nod", "head_slight_nod",
        ]
        alt_pool = [g for g in alt_pool if g in self.base_gestures]
        if not alt_pool:
            return gesture_data

        # 从后往前遍历，尽量保留前面的 few 个家族手势，把后面多余的替换掉
        over = len(family_indices) - allowed
        out = list(gesture_data)
        replaced = 0

        for idx in reversed(family_indices):
            if replaced >= over:
                break
            g = out[idx]
            raw = g.get("gesture_name") or g.get("gesture")
            # 选一个不属于该家族的替代手势
            candidates = [n for n in alt_pool if n != base_name]
            if not candidates:
                candidates = alt_pool
            new_name = random.choice(candidates)

            base_angles = self.base_gestures.get(new_name, self.base_gestures.get("neutral", [0.0] * 12))
            adjusted = self._apply_emotion_adjustment(base_angles.copy(), semantic_info.get("emotion", "neutral") if isinstance(semantic_info := {}) else "neutral")
            angles = self._add_head_coordination(adjusted, new_name)
            angles = self._add_natural_variation(angles)

            new_g = dict(g)
            new_g["gesture_name"] = new_name
            new_g["joint_angles"] = angles
            out[idx] = new_g
            replaced += 1

        return out
        """生成自然的手势时长分布，参考原版逻辑"""
        if num_gestures <= 0:
            return []
        
        if num_gestures == 1:
            return [max(0.8, total_duration)]
        
        # 参考原版逻辑：平均分配时间，加上随机变化
        durations = []
        remaining_duration = total_duration
        
        for i in range(num_gestures):
            if i == num_gestures - 1:
                # 最后一个手势用完剩余时间
                duration = max(0.8, remaining_duration)
            else:
                # 平均分配时间，加上随机变化（原版使用0.7-1.3）
                avg_time_per_gesture = remaining_duration / (num_gestures - i)
                duration = avg_time_per_gesture * random.uniform(0.7, 1.3)
                duration = max(0.8, min(3.0, duration))
                remaining_duration -= duration
            
            durations.append(duration)
        
        print(f"🎲 生成自然时长分布: {[f'{d:.2f}s' for d in durations]} (总计: {sum(durations):.2f}s)")
        return durations
    
    def _generate_segment_based_sequence(self, segments: List[Dict], strategy: Dict,
                                       function_sequences: Dict, total_duration: float) -> List[Tuple[str, float]]:
        """基于韵律分段生成手势序列"""
        sequence = []
        
        for i, segment in enumerate(segments):
            segment_duration = segment.get('duration', 1.0)
            segment_text = segment.get('text', '')
            has_pause = segment.get('pause_after', False) or segment.get('has_pause', False)
            
            # 根据段落内容选择手势类型
            if self._contains_emphasis_words(segment_text):
                gesture_pool = function_sequences.get('emphasis', ['both_hands_emphasize', 'nod_strong'])
            elif self._contains_question_words(segment_text):
                gesture_pool = ['head_micro_tilt_left', 'think_deep', 'attentive_listen']
            else:
                gesture_pool = function_sequences.get('elaboration', ['explain_right_soft', 'both_hands_explain'])
            
            # 🎯 简化手势池，参考原版的合理配置
            head_micro_gestures = [
                'head_micro_tilt_left', 'head_micro_tilt_right',
                'head_micro_nod', 'head_slight_nod'
            ]
            
            # 🎯 简化手部手势选项（降低 both_hands_explain 权重，增加多样性）
            additional_hand_gestures = [
                'explain_right_soft', 'present_right',
                'both_hands_present', 'both_hands_forward'
            ]
            
            # 保持适度的手势池大小
            enhanced_pool = gesture_pool + head_micro_gestures + additional_hand_gestures
            
            # 🎯 调整手势密度：参考原版逻辑，每1.5秒一个手势（合理密度）
            num_gestures = max(1, int(segment_duration / 1.5))
            
            # 🎯 确保最小手势数量：每个段落至少1个手势
            min_gestures_per_segment = max(1, int(segment_duration / 3.0))  # 每3秒至少1个手势
            num_gestures = max(num_gestures, min_gestures_per_segment)
            
            # 🎯 使用自然时长分布，避免均分
            natural_durations = self._generate_natural_durations(segment_duration, num_gestures)
            
            for j in range(num_gestures):
                # 🎯 使用增强的手势池，包含更多头部微动
                selected_gesture = self.coherence_manager.select_coherent_gesture(
                    enhanced_pool,  # 使用增强池而不是原始池
                    {"intent": "explanation", "segment_index": i}
                )
                
                # 🎯 使用预计算的自然时长
                gesture_duration = natural_durations[j] if j < len(natural_durations) else 1.0
                
                sequence.append((selected_gesture, gesture_duration))
                print(f"🎭 段落{i+1}手势{j+1}: {selected_gesture} ({gesture_duration:.2f}s)")
            
            # 在停顿处添加头部微动（不要静止）
            if has_pause and i < len(segments) - 1:
                pause_duration = min(0.5, segment_duration * 0.2)
                # 🎯 停顿时使用简单的头部微动，保持自然
                transition_gestures = ['head_micro_tilt_left', 'head_micro_tilt_right', 
                                     'head_micro_nod', 'neutral']
                transition_gesture = random.choice(transition_gestures)
                sequence.append((transition_gesture, pause_duration))
        
        return sequence
    
    def _generate_function_based_sequence(self, function_sequences: Dict, strategy: Dict,
                                        total_duration: float, intent: str, emotion: str) -> List[Tuple[str, float]]:
        """基于话语功能生成手势序列"""
        sequence = []
        
        # 选择功能序列的阶段
        phases = list(function_sequences.keys())
        if not phases:
            phases = ['elaboration']  # 默认阶段
        
        # 分配时长
        phase_duration = total_duration / len(phases)
        
        # 🎯 头部微动手势池
        head_micro_gestures = [
            'head_micro_tilt_left', 'head_micro_tilt_right',
            'head_natural_left', 'head_natural_right',
            'head_micro_look_left', 'head_micro_look_right',
            'head_micro_nod', 'head_slight_nod'
        ]
        
        for phase in phases:
            gesture_pool = function_sequences.get(phase, ['explain_right_soft'])
            
            # 🎯 简化功能序列的手势池
            enhanced_function_pool = gesture_pool + [
                'head_micro_tilt_left', 'head_micro_tilt_right',
                'head_micro_nod', 'head_slight_nod',
                'explain_right_soft', 'present_right', 
                'both_hands_explain', 'both_hands_present'
            ]
            
            # 🎯 调整手势密度：参考原版逻辑，每1.8秒一个手势（合理密度）
            num_gestures = max(1, int(phase_duration / 1.8))
            
            # 🎯 确保最小手势数量：每个阶段至少1个手势
            min_gestures_per_phase = max(1, int(phase_duration / 3.5))  # 每3.5秒至少1个手势
            num_gestures = max(num_gestures, min_gestures_per_phase)
            
            phase_gestures = []
            
            # 从增强手势池中循环选择，增加多样性
            for i in range(num_gestures):
                gesture = enhanced_function_pool[i % len(enhanced_function_pool)]
                phase_gestures.append(gesture)
            
            # 🎯 使用自然时长分布，避免均分
            natural_durations = self._generate_natural_durations(phase_duration, len(phase_gestures))
            
            for i, gesture in enumerate(phase_gestures):
                # 🎯 传递整个增强池给coherence_manager，而不是单个手势
                selected_gesture = self.coherence_manager.select_coherent_gesture(
                    enhanced_function_pool,  # 使用整个增强池
                    {"intent": intent, "emotion": emotion, "phase": phase}
                )
                
                # 🎯 使用预计算的自然时长
                gesture_duration = natural_durations[i] if i < len(natural_durations) else 1.0
                
                sequence.append((selected_gesture, gesture_duration))
                print(f"🎪 阶段{phase}手势{i+1}: {selected_gesture} ({gesture_duration:.2f}s)")
        
        return sequence
    
    def _apply_parallel_pattern(self, sequence: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """应用并列模式"""
        # 左右手交替模式
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            if i % 2 == 0:
                # 偶数位置：优先左手
                if "right" in gesture:
                    left_version = gesture.replace("right", "left")
                    if left_version in self.base_gestures:
                        gesture = left_version
            else:
                # 奇数位置：优先右手
                if "left" in gesture:
                    right_version = gesture.replace("left", "right")
                    if right_version in self.base_gestures:
                        gesture = right_version
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_contrastive_pattern(self, sequence: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """应用对比模式"""
        # 前半部分左手，后半部分右手
        mid_point = len(sequence) // 2
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            if i < mid_point:
                # 前半部分：左手表示旧观点
                if "right" in gesture:
                    left_version = gesture.replace("right", "left")
                    if left_version in self.base_gestures:
                        gesture = left_version
            else:
                # 后半部分：右手表示新观点
                if "left" in gesture:
                    right_version = gesture.replace("left", "right")
                    if right_version in self.base_gestures:
                        gesture = right_version
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_progressive_pattern(self, sequence: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """应用递进模式"""
        # 逐渐增强的手势
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            progress = i / max(1, len(sequence) - 1)
            
            # 根据进度调整手势强度
            if progress > 0.7:
                # 后期：使用强调版本
                if "soft" in gesture:
                    gesture = gesture.replace("soft", "emphatic")
                elif "gentle" in gesture:
                    gesture = gesture.replace("gentle", "energetic")
                elif "moderate" in gesture:
                    gesture = gesture.replace("moderate", "wide")
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_enumeration_pattern(self, sequence: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """应用列举模式"""
        # 从左到右的空间映射
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            # 根据位置选择空间方向
            if i == 0:
                # 第一项：左侧
                if "right" in gesture:
                    left_version = gesture.replace("right", "left")
                    if left_version in self.base_gestures:
                        gesture = left_version
            elif i == len(sequence) - 1:
                # 最后一项：右侧
                if "left" in gesture:
                    right_version = gesture.replace("left", "right")
                    if right_version in self.base_gestures:
                        gesture = right_version
            else:
                # 中间项：双手或中性
                if "both_hands" not in gesture and random.random() < 0.5:
                    # 有50%概率使用双手手势
                    both_hands_options = [g for g in self.base_gestures.keys() if "both_hands" in g]
                    if both_hands_options:
                        gesture = random.choice(both_hands_options)
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _contains_emphasis_words(self, text: str) -> bool:
        """检查是否包含强调词汇"""
        emphasis_words = ["重要", "关键", "核心", "特别", "非常", "最", "极", "必须", "一定", "绝对"]
        return any(word in text for word in emphasis_words)
    
    def _contains_question_words(self, text: str) -> bool:
        """检查是否包含疑问词汇"""
        question_words = ["什么", "怎么", "为什么", "如何", "是否", "吗", "呢", "哪", "谁", "何时"]
        return any(word in text for word in question_words)
    
    def _adjust_sequence_duration(self, sequence: List[Tuple[str, float]], target_duration: float) -> List[Tuple[str, float]]:
        """调整手势序列的总时长，确保与目标时长匹配
        
        🎯 关键修改：保持自然时长变化，不使用均分调整
        """
        if not sequence:
            return sequence
        
        # 计算当前总时长
        current_duration = sum(duration for _, duration in sequence)
        
        # 如果时长差异小于0.2秒，认为已经匹配，保持自然变化
        if abs(current_duration - target_duration) < 0.2:
            return sequence
        
        # 🎯 检查是否有序列动作（挥手、拥抱、握手等）
        sequence_action_gestures = set()
        for seq_name, steps in self.action_sequences.items():
            for step in steps:
                sequence_action_gestures.add(step["gesture"])
        
        # 检查当前序列中是否包含序列动作
        has_sequence_action = any(gesture_name in sequence_action_gestures for gesture_name, _ in sequence)
        
        if has_sequence_action and current_duration > target_duration:
            # 🎯 如果包含序列动作且当前时长大于目标时长，允许溢出，不压缩
            overflow = current_duration - target_duration
            print(f"🎯 检测到序列动作，保持完整执行: {current_duration:.2f}s (语音: {target_duration:.2f}s, 溢出: {overflow:.2f}s)")
            return sequence
        
        # 🎯 不使用均分调整，而是通过调整最后一个手势来匹配总时长
        if len(sequence) > 0:
            adjusted_sequence = sequence[:-1]  # 保持前面手势的自然时长
            last_gesture, last_duration = sequence[-1]
            
            # 计算前面手势的总时长
            front_duration = sum(d for _, d in adjusted_sequence)
            remaining_duration = target_duration - front_duration
            
            # 调整最后一个手势的时长（参考原版的合理时长）
            final_last_duration = max(0.8, min(5.0, remaining_duration))
            adjusted_sequence.append((last_gesture, final_last_duration))
            
            print(f"🎵 保持自然时长变化: 前{len(sequence)-1}个手势保持原时长，最后手势调整为{final_last_duration:.2f}s")
            return adjusted_sequence
        
        return sequence
    
    def _convert_to_gesture_data(self, sequence: List[Tuple[str, float]], emotion: str) -> List[Dict]:
        """转换为最终的手势数据格式，并添加头部配合"""
        gesture_data = []
        
        for gesture_name, duration in sequence:
            # 获取基础关节角度
            base_angles = self.base_gestures.get(gesture_name, self.base_gestures["neutral"])
            
            # 应用情感调节
            adjusted_angles = self._apply_emotion_adjustment(base_angles.copy(), emotion)
            
            # 🎯 先做“头+手一体联动”的骨架注入逻辑（从 GesturePolicy 迁移过来）
            # 目标：说话时避免“只有头在动，手臂几乎不动”或“只有手在动，头完全不带动”的机械感
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

            final_angles = list(adjusted_angles)
            is_head = _is_head_gesture(gesture_name)
            is_hand = (not is_head) and (gesture_name not in ("neutral", "rest", "attentive_listen"))

            # 手臂动作必须带头：如果当前头部角度几乎为0，则注入一个左右头部动作（优先组合动作）
            if is_hand and (not _has_head_motion(final_angles)):
                head_pool = [
                    "head_left_up", "head_left_down", "head_right_up", "head_right_down",
                    "head_micro_tilt_left", "head_micro_tilt_right",
                    "head_micro_look_left", "head_micro_look_right",
                    "head_natural_left", "head_natural_right",
                    "head_moderate_left", "head_moderate_right",
                    "head_micro_up", "head_micro_down",
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
                if not strong_both_hands:
                    strong_both_hands = [k for k in self.base_gestures.keys() if str(k).startswith("both_hands_")]

                if strong_both_hands:
                    arms_name = random.choice(strong_both_hands)
                    arms_base = self.base_gestures.get(arms_name)
                    if isinstance(arms_base, list) and len(arms_base) == 12:
                        # 对手臂也应用情感强度，让“头+手”更像一体表达
                        try:
                            arms_varied = self._apply_emotion_adjustment(arms_base.copy(), emotion)
                        except Exception:
                            arms_varied = arms_base
                        for i in range(2, 12):
                            final_angles[i] = arms_varied[i]
                else:
                    # 兜底：仍然给一点点手臂支撑（避免完全静止）
                    aa = self.base_gestures.get("arms_micro_support")
                    if isinstance(aa, list) and len(aa) == 12:
                        for i in range(2, 12):
                            final_angles[i] = aa[i]

            # 对侧轻度配合：在强侧手势时为对侧注入小幅同步
            # （这里复用 GesturePolicy 中的思想，但简化为只对已经注入的 final_angles 做后处理）
            try:
                max_arm = 0.0
                for idx in range(2, 12):
                    max_arm = max(max_arm, abs(float(final_angles[idx])))
                if (
                    gesture_name not in ("rest", "neutral", "attentive_listen")
                    and max_arm < self._min_arm_amplitude_deg
                    and max_arm > 0.5
                ):
                    factor = self._min_arm_amplitude_deg / max_arm
                    factor = min(factor, 3.0)
                    boosted = list(final_angles)
                    for idx in range(2, 12):
                        boosted[idx] = boosted[idx] * factor
                    final_angles = boosted
            except Exception:
                pass

            # 🎯 再叠加头部配合：根据手部/双手动作微调头部方向和点头
            final_angles = self._add_head_coordination(final_angles, gesture_name)

            # 最后添加自然抖动，让动作更像“活人”而不是插值轨迹
            final_angles = self._add_natural_variation(final_angles)
            
            gesture_data.append({
                'gesture_name': gesture_name,
                'joint_angles': final_angles,
                'duration': duration
            })
        
        return gesture_data
    
    def _add_head_coordination(self, angles: List[float], gesture_name: str) -> List[float]:
        """添加头部配合：头部跟随手部动作微微转动"""
        # angles[0] = 头部左右转动 (yaw)
        # angles[1] = 头部上下点头 (pitch)
        
        # 🎯 右手动作 → 头部微微向右看
        if "right" in gesture_name and "both" not in gesture_name:
            # 右手动作时，头部向右转6-16度（增加一倍）
            head_turn = random.uniform(6, 16)
            angles[0] = -head_turn  # 负值是向右
            # 可能微微点头
            if random.random() < 0.3:
                angles[1] = random.uniform(4, 10)
        
        # 🎯 左手动作 → 头部微微向左看
        elif "left" in gesture_name and "both" not in gesture_name:
            # 左手动作时，头部向左转6-16度（增加一倍）
            head_turn = random.uniform(6, 16)
            angles[0] = head_turn  # 正值是向左
            # 可能微微点头
            if random.random() < 0.3:
                angles[1] = random.uniform(4, 10)
        
        # 🎯 双手动作 → 头部微微点头或保持中立
        elif "both" in gesture_name:
            # 双手动作时，头部可能点头或微微左右摆动
            if random.random() < 0.5:
                # 50%概率点头（增加一倍）
                angles[1] = random.uniform(6, 12)
            else:
                # 50%概率微微左右摆动（增加一倍）
                angles[0] = random.uniform(-8, 8)
        
        # 🎯 强调动作 → 头部配合点头
        elif "emphasize" in gesture_name or "nod" in gesture_name:
            angles[1] = random.uniform(10, 20)  # 明显点头（增加一倍）
        
        # 🎯 思考动作 → 头部微微歪
        elif "think" in gesture_name or "curious" in gesture_name:
            angles[0] = random.uniform(-12, 12)  # 微微歪头（增加一倍）
            angles[1] = random.uniform(-6, 6)
        
        # 🎯 其他动作 → 添加微小的头部微动
        else:
            # 20%概率添加微小的头部左右看（增加一倍）
            if random.random() < 0.2:
                angles[0] = random.uniform(-10, 10)
        
        return angles
    
    def _apply_emotion_adjustment(self, angles: List[float], emotion: str) -> List[float]:
        """应用情感调节"""
        emotion_factors = {
            "happy": 1.2,
            "excited": 1.4,
            "sad": 0.7,
            "angry": 1.3,
            "surprised": 1.1,
            "neutral": 1.0
        }
        
        factor = emotion_factors.get(emotion, 1.0)
        
        # 调整手臂关节的幅度（索引2-11）
        for i in range(2, 12):
            angles[i] *= factor
        
        return angles
    
    def _add_natural_variation(self, angles: List[float]) -> List[float]:
        """添加自然变化"""
        varied_angles = []
        
        for i, angle in enumerate(angles):
            if i < 2:  # 头部关节
                variation = random.uniform(-2, 2)
                candidate = angle + variation
            else:  # 手臂关节
                variation = random.uniform(-3, 3)
                candidate = angle + variation
                # 按你的要求：手臂动作至少约 5 度，避免“看不出在动”
                try:
                    if abs(float(candidate)) < 5.0:
                        if candidate >= 0:
                            candidate = 5.0
                        else:
                            candidate = -5.0
                except Exception:
                    pass
            
            varied_angles.append(candidate)
        
        return varied_angles
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "linguistic_analyzer": "ready",
            "prosodic_planner": "ready", 
            "coherence_manager": "ready",
            "base_gestures_count": len(self.base_gestures),
            "current_gesture": self.coherence_manager.last_gesture,
            "gesture_history": list(self.coherence_manager.gesture_history)
        }