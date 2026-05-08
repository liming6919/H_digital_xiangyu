#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势连贯性管理器
管理动作序列的逻辑连贯性、状态转换和平滑过渡
"""

from typing import Dict, List, Tuple, Optional, Set
import random
import numpy as np
from collections import deque

class GestureCoherenceManager:
    def __init__(self):
        """初始化手势连贯性管理器"""
        
        # 手势状态定义
        self.gesture_states = {
            "neutral": {"hand": "neutral", "height": "mid", "energy": "low"},
            "rest": {"hand": "neutral", "height": "low", "energy": "low"},
            
            # 右手手势状态
            "wave_right_gentle": {"hand": "right", "height": "mid", "energy": "medium"},
            "wave_right_energetic": {"hand": "right", "height": "high", "energy": "high"},
            "point_right_formal": {"hand": "right", "height": "mid", "energy": "medium"},
            "explain_right_soft": {"hand": "right", "height": "mid", "energy": "low"},
            "explain_right_emphatic": {"hand": "right", "height": "high", "energy": "high"},
            "present_right": {"hand": "right", "height": "mid", "energy": "medium"},
            
            # 左手手势状态
            "wave_left_gentle": {"hand": "left", "height": "mid", "energy": "medium"},
            "wave_left_energetic": {"hand": "left", "height": "high", "energy": "high"},
            "point_left_formal": {"hand": "left", "height": "mid", "energy": "medium"},
            "explain_left_soft": {"hand": "left", "height": "mid", "energy": "low"},
            "explain_left_emphatic": {"hand": "left", "height": "high", "energy": "high"},
            "present_left": {"hand": "left", "height": "mid", "energy": "medium"},
            
            # 双手手势状态
            "both_hands_explain": {"hand": "both", "height": "mid", "energy": "medium"},
            "both_hands_present": {"hand": "both", "height": "mid", "energy": "medium"},
            "both_hands_emphasize": {"hand": "both", "height": "high", "energy": "high"},
            "open_arms_moderate": {"hand": "both", "height": "mid", "energy": "medium"},
            "open_arms_wide": {"hand": "both", "height": "high", "energy": "high"},
            "welcome_gesture": {"hand": "both", "height": "mid", "energy": "medium"},
            
            # 头部手势状态
            "head_micro_nod": {"hand": "neutral", "height": "mid", "energy": "low"},
            "head_slight_nod": {"hand": "neutral", "height": "mid", "energy": "low"},
            "nod_strong": {"hand": "neutral", "height": "mid", "energy": "medium"},
            "head_micro_shake": {"hand": "neutral", "height": "mid", "energy": "low"},
            "shake_strong": {"hand": "neutral", "height": "mid", "energy": "medium"},
            "tilt_curious": {"hand": "neutral", "height": "mid", "energy": "low"},
            
            # 思考和情感手势
            "think_deep": {"hand": "left", "height": "high", "energy": "low"},
            "attentive_listen": {"hand": "neutral", "height": "mid", "energy": "low"},
            "confident_relaxed": {"hand": "right", "height": "low", "energy": "low"},
            "confident_assertive": {"hand": "right", "height": "mid", "energy": "medium"}
        }
        
        # 手势转换兼容性矩阵
        self.transition_compatibility = {
            # 从中性状态的转换
            "neutral": {
                "right": 0.9, "left": 0.9, "both": 0.8, "neutral": 1.0
            },
            "rest": {
                "right": 0.7, "left": 0.7, "both": 0.6, "neutral": 0.9
            },
            
            # 从右手状态的转换
            "right": {
                "right": 0.8,    # 右手继续
                "left": 0.4,     # 切换到左手（较难）
                "both": 0.7,     # 扩展到双手
                "neutral": 0.6   # 回到中性
            },
            
            # 从左手状态的转换
            "left": {
                "right": 0.4,    # 切换到右手（较难）
                "left": 0.8,     # 左手继续
                "both": 0.7,     # 扩展到双手
                "neutral": 0.6   # 回到中性
            },
            
            # 从双手状态的转换
            "both": {
                "right": 0.5,    # 收缩到右手
                "left": 0.5,     # 收缩到左手
                "both": 0.9,     # 双手继续
                "neutral": 0.7   # 回到中性
            }
        }
        
        # 能量级别转换平滑度
        self.energy_transition_smoothness = {
            ("low", "low"): 1.0,
            ("low", "medium"): 0.8,
            ("low", "high"): 0.4,
            ("medium", "low"): 0.7,
            ("medium", "medium"): 1.0,
            ("medium", "high"): 0.8,
            ("high", "low"): 0.3,
            ("high", "medium"): 0.7,
            ("high", "high"): 1.0
        }
        
        # 高度转换平滑度
        self.height_transition_smoothness = {
            ("low", "low"): 1.0,
            ("low", "mid"): 0.8,
            ("low", "high"): 0.5,
            ("mid", "low"): 0.7,
            ("mid", "mid"): 1.0,
            ("mid", "high"): 0.8,
            ("high", "low"): 0.4,
            ("high", "mid"): 0.7,
            ("high", "high"): 1.0
        }
        
        # 手势记忆窗口
        self.memory_window = 3
        self.gesture_history = deque(maxlen=self.memory_window)
        
        # 动作链定义
        self.gesture_chains = {
            "introduction_chain": [
                ("open_arms_moderate", "both_hands_present", "welcome_gesture"),
                ("present_right", "explain_right_soft", "both_hands_explain")
            ],
            "explanation_chain": [
                ("explain_right_soft", "present_right", "both_hands_explain"),
                ("point_right_formal", "explain_right_emphatic", "both_hands_emphasize")
            ],
            "emphasis_chain": [
                ("explain_right_emphatic", "both_hands_emphasize", "nod_strong"),
                ("point_right_formal", "both_hands_present", "confident_assertive")
            ],
            "comparison_chain": [
                ("present_left", "present_right", "both_hands_balance"),
                ("point_left_formal", "point_right_formal", "both_hands_compare")
            ],
            "conclusion_chain": [
                ("both_hands_gather", "both_hands_present", "nod_strong"),
                ("explain_right_soft", "both_hands_down", "rest")
            ]
        }
        
        # 当前状态
        self.current_state = self.gesture_states.get("neutral", {})
        self.last_gesture = "neutral"
    
    def calculate_transition_score(self, from_gesture: str, to_gesture: str) -> float:
        """计算手势转换的平滑度分数
        
        Args:
            from_gesture: 起始手势
            to_gesture: 目标手势
            
        Returns:
            转换平滑度分数 (0-1)
        """
        from_state = self.gesture_states.get(from_gesture, self.gesture_states["neutral"])
        to_state = self.gesture_states.get(to_gesture, self.gesture_states["neutral"])
        
        # 计算各维度的转换分数
        hand_score = self.transition_compatibility.get(from_state["hand"], {}).get(to_state["hand"], 0.5)
        
        energy_key = (from_state["energy"], to_state["energy"])
        energy_score = self.energy_transition_smoothness.get(energy_key, 0.5)
        
        height_key = (from_state["height"], to_state["height"])
        height_score = self.height_transition_smoothness.get(height_key, 0.5)
        
        # 综合分数（加权平均）
        total_score = (hand_score * 0.5 + energy_score * 0.3 + height_score * 0.2)
        
        # 考虑重复惩罚
        repetition_penalty = self._calculate_repetition_penalty(to_gesture)
        
        return total_score * repetition_penalty
    
    def _calculate_repetition_penalty(self, gesture: str) -> float:
        """计算重复惩罚 - 加强重复惩罚，避免连续相同手势"""
        if not self.gesture_history:
            return 1.0
        
        # 检查最近的手势历史
        recent_count = sum(1 for g in self.gesture_history if g == gesture)
        
        # 特别检查最近一个手势是否相同
        last_gesture_same = len(self.gesture_history) > 0 and self.gesture_history[-1] == gesture
        
        if recent_count == 0:
            return 1.0  # 没有重复，无惩罚
        elif last_gesture_same:
            return 0.1  # 连续相同手势，严重惩罚
        elif recent_count == 1:
            return 0.7  # 轻微惩罚
        elif recent_count == 2:
            return 0.4  # 中等惩罚
        else:
            return 0.1  # 严重惩罚
    
    def select_coherent_gesture(self, candidates: List[str], context: Dict = None) -> str:
        """选择连贯的手势
        
        Args:
            candidates: 候选手势列表
            context: 上下文信息（可选）
            
        Returns:
            选择的手势名称
        """
        if not candidates:
            return "neutral"
        
        if len(candidates) == 1:
            selected = candidates[0]
        else:
            # 计算每个候选手势的分数
            scores = []
            for candidate in candidates:
                transition_score = self.calculate_transition_score(self.last_gesture, candidate)
                
                # 考虑上下文加分
                context_bonus = self._calculate_context_bonus(candidate, context)
                
                total_score = transition_score + context_bonus
                scores.append((candidate, total_score))
            
            # 选择分数最高的手势
            scores.sort(key=lambda x: x[1], reverse=True)
            selected = scores[0][0]
        
        # 更新状态
        self._update_state(selected)
        
        return selected
    
    def _calculate_context_bonus(self, gesture: str, context: Dict) -> float:
        """计算上下文加分"""
        if not context:
            return 0.0
        
        bonus = 0.0
        
        # 根据意图给予加分
        intent = context.get("intent", "")
        if intent == "emphasis" and "emphatic" in gesture:
            bonus += 0.2
        elif intent == "explanation" and "explain" in gesture:
            bonus += 0.2
        elif intent == "presentation" and "present" in gesture:
            bonus += 0.2
        
        # 根据情感给予加分
        emotion = context.get("emotion", "")
        if emotion == "excited" and "energetic" in gesture:
            bonus += 0.15
        elif emotion == "calm" and "soft" in gesture:
            bonus += 0.15
        
        # 根据语义角色给予加分
        semantic_roles = context.get("semantic_roles", {})
        if "agent" in semantic_roles and ("point" in gesture or "present" in gesture):
            bonus += 0.1
        
        return bonus
    
    def _update_state(self, gesture: str):
        """更新当前状态"""
        self.last_gesture = gesture
        self.current_state = self.gesture_states.get(gesture, self.gesture_states["neutral"])
        self.gesture_history.append(gesture)
    
    def plan_gesture_chain(self, discourse_function: str, duration: float) -> List[Tuple[str, float]]:
        """规划手势链
        
        Args:
            discourse_function: 话语功能
            duration: 总时长
            
        Returns:
            手势链序列
        """
        # 选择合适的手势链
        chain_key = f"{discourse_function}_chain"
        if chain_key not in self.gesture_chains:
            chain_key = "explanation_chain"  # 默认链
        
        chains = self.gesture_chains[chain_key]
        selected_chain = random.choice(chains)
        
        # 分配时长
        gesture_count = len(selected_chain)
        base_duration = duration / gesture_count
        
        gesture_sequence = []
        for i, gesture in enumerate(selected_chain):
            # 为每个手势分配时长，最后一个手势吸收剩余时间
            if i == gesture_count - 1:
                remaining_time = duration - sum(d for _, d in gesture_sequence)
                gesture_duration = max(0.5, remaining_time)
            else:
                gesture_duration = base_duration * random.uniform(0.8, 1.2)
            
            gesture_sequence.append((gesture, gesture_duration))
        
        return gesture_sequence
    
    def ensure_smooth_transitions(self, gesture_sequence: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """确保手势序列的平滑转换
        
        Args:
            gesture_sequence: 原始手势序列
            
        Returns:
            平滑化后的手势序列
        """
        if len(gesture_sequence) <= 1:
            return gesture_sequence
        
        smoothed_sequence = []
        
        for i in range(len(gesture_sequence)):
            current_gesture, current_duration = gesture_sequence[i]
            
            # 添加当前手势
            smoothed_sequence.append((current_gesture, current_duration))
            
            # 检查是否需要插入过渡手势
            if i < len(gesture_sequence) - 1:
                next_gesture, _ = gesture_sequence[i + 1]
                transition_score = self.calculate_transition_score(current_gesture, next_gesture)
                
                # 如果转换分数过低，插入过渡手势
                if transition_score < 0.4:
                    bridge_gesture = self._find_bridge_gesture(current_gesture, next_gesture)
                    if bridge_gesture:
                        smoothed_sequence.append((bridge_gesture, 0.3))
        
        return smoothed_sequence
    
    def _find_bridge_gesture(self, from_gesture: str, to_gesture: str) -> Optional[str]:
        """寻找桥接手势"""
        from_state = self.gesture_states.get(from_gesture, {})
        to_state = self.gesture_states.get(to_gesture, {})
        
        # 寻找中间状态的手势
        bridge_candidates = []
        
        for gesture, state in self.gesture_states.items():
            # 跳过起始和目标手势
            if gesture in [from_gesture, to_gesture]:
                continue
            
            # 计算到起始和目标的转换分数
            from_score = self.calculate_transition_score(from_gesture, gesture)
            to_score = self.calculate_transition_score(gesture, to_gesture)
            
            # 如果都有较好的转换分数，则作为候选
            if from_score > 0.6 and to_score > 0.6:
                bridge_candidates.append((gesture, from_score + to_score))
        
        if bridge_candidates:
            # 选择分数最高的桥接手势
            bridge_candidates.sort(key=lambda x: x[1], reverse=True)
            return bridge_candidates[0][0]
        
        # 如果找不到好的桥接手势，使用neutral作为默认
        return "neutral"
    
    def apply_contextual_coherence(self, gesture_sequence: List[Tuple[str, float]], 
                                 linguistic_context: Dict) -> List[Tuple[str, float]]:
        """应用上下文连贯性
        
        Args:
            gesture_sequence: 手势序列
            linguistic_context: 语言学上下文
            
        Returns:
            上下文优化后的手势序列
        """
        structure_type = linguistic_context.get("structure_type", "simple")
        gesture_strategy = linguistic_context.get("gesture_strategy", {})
        
        # 根据句子结构调整手势序列
        if structure_type == "parallel":
            return self._apply_parallel_structure(gesture_sequence, gesture_strategy)
        elif structure_type == "contrastive":
            return self._apply_contrastive_structure(gesture_sequence, gesture_strategy)
        elif structure_type == "enumeration":
            return self._apply_enumeration_structure(gesture_sequence, gesture_strategy)
        elif structure_type == "progressive":
            return self._apply_progressive_structure(gesture_sequence, gesture_strategy)
        else:
            return gesture_sequence
    
    def _apply_parallel_structure(self, sequence: List[Tuple[str, float]], strategy: Dict) -> List[Tuple[str, float]]:
        """应用并列结构的手势模式"""
        if len(sequence) < 2:
            return sequence
        
        # 并列结构：左右手交替或对称
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            if i % 2 == 0:
                # 偶数位置使用左手或左侧手势
                if "left" not in gesture and "both" not in gesture:
                    # 尝试转换为左手版本
                    left_version = gesture.replace("right", "left")
                    if left_version in self.gesture_states:
                        gesture = left_version
            else:
                # 奇数位置使用右手或右侧手势
                if "right" not in gesture and "both" not in gesture:
                    # 尝试转换为右手版本
                    right_version = gesture.replace("left", "right")
                    if right_version in self.gesture_states:
                        gesture = right_version
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_contrastive_structure(self, sequence: List[Tuple[str, float]], strategy: Dict) -> List[Tuple[str, float]]:
        """应用对比结构的手势模式"""
        if len(sequence) < 2:
            return sequence
        
        # 对比结构：前半部分左手，后半部分右手
        mid_point = len(sequence) // 2
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            if i < mid_point:
                # 前半部分：左手或左侧
                if "right" in gesture:
                    left_version = gesture.replace("right", "left")
                    if left_version in self.gesture_states:
                        gesture = left_version
            else:
                # 后半部分：右手或右侧
                if "left" in gesture:
                    right_version = gesture.replace("left", "right")
                    if right_version in self.gesture_states:
                        gesture = right_version
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_enumeration_structure(self, sequence: List[Tuple[str, float]], strategy: Dict) -> List[Tuple[str, float]]:
        """应用列举结构的手势模式"""
        # 列举结构：递进式手势，逐渐增强
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            # 根据位置调整手势强度
            progress = i / max(1, len(sequence) - 1)
            
            if progress < 0.3:
                # 开始：温和手势
                if "emphatic" in gesture:
                    gesture = gesture.replace("emphatic", "soft")
                elif "energetic" in gesture:
                    gesture = gesture.replace("energetic", "gentle")
            elif progress > 0.7:
                # 结尾：强调手势
                if "soft" in gesture:
                    gesture = gesture.replace("soft", "emphatic")
                elif "gentle" in gesture:
                    gesture = gesture.replace("gentle", "energetic")
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def _apply_progressive_structure(self, sequence: List[Tuple[str, float]], strategy: Dict) -> List[Tuple[str, float]]:
        """应用递进结构的手势模式"""
        # 递进结构：逐步增强，最后达到高潮
        modified_sequence = []
        
        for i, (gesture, duration) in enumerate(sequence):
            # 计算递进程度
            intensity = (i + 1) / len(sequence)
            
            # 根据递进程度调整手势
            if intensity > 0.8:
                # 高潮部分：使用最强手势
                if "soft" in gesture:
                    gesture = gesture.replace("soft", "emphatic")
                elif "gentle" in gesture:
                    gesture = gesture.replace("gentle", "dramatic")
                elif "moderate" in gesture:
                    gesture = gesture.replace("moderate", "wide")
            elif intensity > 0.5:
                # 中间部分：中等强度
                if "soft" in gesture:
                    gesture = gesture.replace("soft", "emphatic")
                elif "gentle" in gesture:
                    gesture = gesture.replace("gentle", "energetic")
            
            modified_sequence.append((gesture, duration))
        
        return modified_sequence
    
    def reset_state(self):
        """重置状态"""
        self.current_state = self.gesture_states.get("neutral", {})
        self.last_gesture = "neutral"
        self.gesture_history.clear()
    
    def get_coherence_metrics(self, gesture_sequence: List[Tuple[str, float]]) -> Dict:
        """获取连贯性指标
        
        Args:
            gesture_sequence: 手势序列
            
        Returns:
            连贯性指标
        """
        if len(gesture_sequence) <= 1:
            return {"smoothness": 1.0, "diversity": 0.0, "coherence": 1.0}
        
        # 计算平滑度
        transition_scores = []
        for i in range(len(gesture_sequence) - 1):
            from_gesture = gesture_sequence[i][0]
            to_gesture = gesture_sequence[i + 1][0]
            score = self.calculate_transition_score(from_gesture, to_gesture)
            transition_scores.append(score)
        
        smoothness = np.mean(transition_scores) if transition_scores else 1.0
        
        # 计算多样性
        unique_gestures = set(gesture for gesture, _ in gesture_sequence)
        diversity = len(unique_gestures) / len(gesture_sequence)
        
        # 计算整体连贯性
        coherence = (smoothness + diversity) / 2
        
        return {
            "smoothness": smoothness,
            "diversity": diversity,
            "coherence": coherence,
            "transition_scores": transition_scores
        }