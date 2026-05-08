#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
韵律驱动手势规划器
基于语音韵律信息（停顿、重音、语速）规划动作节奏和时机
"""

from typing import Dict, List, Tuple, Optional
import numpy as np

class ProsodicGesturePlanner:
    def __init__(self):
        """初始化韵律手势规划器"""
        
        # 韵律特征阈值
        self.pause_thresholds = {
            "micro": 0.1,    # 微停顿 100ms
            "short": 0.3,    # 短停顿 300ms
            "medium": 0.6,   # 中停顿 600ms
            "long": 1.0      # 长停顿 1000ms
        }
        
        # 语速分类阈值（字/秒）
        self.speech_rate_thresholds = {
            "very_slow": 1.5,
            "slow": 2.0,
            "normal": 3.0,
            "fast": 4.0,
            "very_fast": 5.0
        }
        
        # 韵律到手势映射
        self.prosody_gesture_map = {
            "pause_micro": {
                "action": "hold_current",
                "duration_factor": 1.0
            },
            "pause_short": {
                "action": "micro_adjustment",
                "gestures": ["head_micro_nod", "head_micro_tilt_left", "head_micro_look_left"]
            },
            "pause_medium": {
                "action": "transition_gesture",
                "gestures": ["head_slight_nod", "neutral", "attentive_listen"]
            },
            "pause_long": {
                "action": "return_to_rest",
                "gestures": ["rest", "neutral"]
            }
        }
        
        # 语速到手势节奏映射
        self.speech_rate_gesture_map = {
            "very_slow": {
                "gesture_frequency": 0.3,  # 每秒0.3个手势
                "amplitude_factor": 1.4,   # 幅度增加40%
                "duration_factor": 1.6     # 时长增加60%
            },
            "slow": {
                "gesture_frequency": 0.5,
                "amplitude_factor": 1.2,
                "duration_factor": 1.3
            },
            "normal": {
                "gesture_frequency": 0.7,
                "amplitude_factor": 1.0,
                "duration_factor": 1.0
            },
            "fast": {
                "gesture_frequency": 1.0,
                "amplitude_factor": 0.8,
                "duration_factor": 0.8
            },
            "very_fast": {
                "gesture_frequency": 1.3,
                "amplitude_factor": 0.6,
                "duration_factor": 0.6
            }
        }
    
    def analyze_prosodic_features(self, timestamps: List[Dict]) -> Dict:
        """分析韵律特征
        
        Args:
            timestamps: 时间戳数据
            
        Returns:
            韵律特征分析结果
        """
        if not timestamps:
            return self._get_default_prosodic_features()
        
        # 提取停顿信息
        pauses = self._extract_pauses(timestamps)
        
        # 计算语速
        speech_rate = self._calculate_speech_rate(timestamps)
        
        # 识别重音位置
        stress_positions = self._identify_stress_positions(timestamps)
        
        # 分析节奏模式
        rhythm_pattern = self._analyze_rhythm_pattern(timestamps, pauses)
        
        return {
            "pauses": pauses,
            "speech_rate": speech_rate,
            "stress_positions": stress_positions,
            "rhythm_pattern": rhythm_pattern,
            "total_duration": self._get_total_duration(timestamps)
        }
    
    def _extract_pauses(self, timestamps: List[Dict]) -> List[Dict]:
        """提取停顿信息"""
        pauses = []
        
        for i in range(len(timestamps) - 1):
            current_end = timestamps[i].get('end_time', 0)
            next_start = timestamps[i + 1].get('start_time', 0)
            gap = next_start - current_end
            
            if gap > self.pause_thresholds["micro"]:
                pause_type = self._classify_pause_duration(gap)
                pauses.append({
                    'position': i,
                    'start_time': current_end,
                    'duration': gap,
                    'type': pause_type,
                    'before_word': timestamps[i].get('word', ''),
                    'after_word': timestamps[i + 1].get('word', '')
                })
        
        return pauses
    
    def _classify_pause_duration(self, duration: float) -> str:
        """分类停顿时长"""
        if duration >= self.pause_thresholds["long"]:
            return "long"
        elif duration >= self.pause_thresholds["medium"]:
            return "medium"
        elif duration >= self.pause_thresholds["short"]:
            return "short"
        else:
            return "micro"
    
    def _calculate_speech_rate(self, timestamps: List[Dict]) -> Dict:
        """计算语速"""
        if len(timestamps) < 2:
            return {"rate": 2.5, "category": "normal"}
        
        # 计算总字数和总时长
        total_chars = sum(len(item.get('word', '')) for item in timestamps)
        total_duration = timestamps[-1].get('end_time', 0) - timestamps[0].get('start_time', 0)
        
        if total_duration <= 0:
            return {"rate": 2.5, "category": "normal"}
        
        rate = total_chars / total_duration
        
        # 分类语速
        category = "normal"
        for cat, threshold in sorted(self.speech_rate_thresholds.items(), key=lambda x: x[1]):
            if rate <= threshold:
                category = cat
                break
        else:
            category = "very_fast"
        
        # 计算局部语速变化
        local_rates = self._calculate_local_speech_rates(timestamps)
        
        return {
            "rate": rate,
            "category": category,
            "local_rates": local_rates,
            "variation": np.std(local_rates) if local_rates else 0
        }
    
    def _calculate_local_speech_rates(self, timestamps: List[Dict], window_size: int = 3) -> List[float]:
        """计算局部语速"""
        local_rates = []
        
        for i in range(len(timestamps) - window_size + 1):
            window = timestamps[i:i + window_size]
            chars = sum(len(item.get('word', '')) for item in window)
            duration = window[-1].get('end_time', 0) - window[0].get('start_time', 0)
            
            if duration > 0:
                local_rates.append(chars / duration)
        
        return local_rates
    
    def _identify_stress_positions(self, timestamps: List[Dict]) -> List[Dict]:
        """识别重音位置"""
        stress_positions = []
        
        # 基于时长的重音检测
        durations = [item.get('end_time', 0) - item.get('start_time', 0) for item in timestamps]
        if durations:
            mean_duration = np.mean(durations)
            std_duration = np.std(durations)
            
            for i, (item, duration) in enumerate(zip(timestamps, durations)):
                # 时长明显长于平均值的词可能是重音
                if duration > mean_duration + std_duration:
                    stress_positions.append({
                        'position': i,
                        'word': item.get('word', ''),
                        'start_time': item.get('start_time', 0),
                        'duration': duration,
                        'stress_level': min(3.0, (duration - mean_duration) / std_duration)
                    })
        
        # 基于语义的重音检测
        stress_keywords = ["重要", "关键", "核心", "特别", "非常", "最", "极", "必须", "一定"]
        for i, item in enumerate(timestamps):
            word = item.get('word', '')
            if any(keyword in word for keyword in stress_keywords):
                # 避免重复添加
                if not any(sp['position'] == i for sp in stress_positions):
                    stress_positions.append({
                        'position': i,
                        'word': word,
                        'start_time': item.get('start_time', 0),
                        'duration': item.get('end_time', 0) - item.get('start_time', 0),
                        'stress_level': 2.0,
                        'type': 'semantic'
                    })
        
        return sorted(stress_positions, key=lambda x: x['start_time'])
    
    def _analyze_rhythm_pattern(self, timestamps: List[Dict], pauses: List[Dict]) -> Dict:
        """分析节奏模式"""
        if not timestamps:
            return {"type": "steady", "regularity": 0.5}
        
        # 计算词间间隔
        intervals = []
        for i in range(len(timestamps) - 1):
            interval = timestamps[i + 1].get('start_time', 0) - timestamps[i].get('end_time', 0)
            intervals.append(max(0, interval))
        
        if not intervals:
            return {"type": "steady", "regularity": 0.5}
        
        # 分析节奏规律性
        regularity = 1.0 - (np.std(intervals) / (np.mean(intervals) + 1e-6))
        regularity = max(0, min(1, regularity))
        
        # 确定节奏类型
        rhythm_type = "steady"
        if len(pauses) > len(timestamps) * 0.3:
            rhythm_type = "choppy"  # 断续的
        elif regularity > 0.7:
            rhythm_type = "regular"  # 规律的
        elif regularity < 0.3:
            rhythm_type = "irregular"  # 不规律的
        
        return {
            "type": rhythm_type,
            "regularity": regularity,
            "average_interval": np.mean(intervals),
            "interval_variation": np.std(intervals)
        }
    
    def _get_total_duration(self, timestamps: List[Dict]) -> float:
        """获取总时长"""
        if not timestamps:
            return 0.0
        return timestamps[-1].get('end_time', 0) - timestamps[0].get('start_time', 0)
    
    def _get_default_prosodic_features(self) -> Dict:
        """获取默认韵律特征"""
        return {
            "pauses": [],
            "speech_rate": {"rate": 2.5, "category": "normal", "local_rates": [], "variation": 0},
            "stress_positions": [],
            "rhythm_pattern": {"type": "steady", "regularity": 0.5},
            "total_duration": 0.0
        }
    
    def plan_prosodic_gestures(self, prosodic_features: Dict, base_gestures: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """基于韵律特征规划手势
        
        Args:
            prosodic_features: 韵律特征
            base_gestures: 基础手势序列
            
        Returns:
            韵律调整后的手势序列
        """
        if not base_gestures:
            return []
        
        # 获取韵律参数
        speech_rate_info = prosodic_features.get("speech_rate", {})
        pauses = prosodic_features.get("pauses", [])
        stress_positions = prosodic_features.get("stress_positions", [])
        rhythm_pattern = prosodic_features.get("rhythm_pattern", {})
        
        # 应用语速调整
        adjusted_gestures = self._apply_speech_rate_adjustment(base_gestures, speech_rate_info)
        
        # 插入停顿处理
        adjusted_gestures = self._insert_pause_gestures(adjusted_gestures, pauses)
        
        # 应用重音强化
        adjusted_gestures = self._apply_stress_emphasis(adjusted_gestures, stress_positions)
        
        # 应用节奏调整
        adjusted_gestures = self._apply_rhythm_adjustment(adjusted_gestures, rhythm_pattern)
        
        return adjusted_gestures
    
    def _apply_speech_rate_adjustment(self, gestures: List[Tuple[str, float]], speech_rate_info: Dict) -> List[Tuple[str, float]]:
        """应用语速调整"""
        category = speech_rate_info.get("category", "normal")
        rate_params = self.speech_rate_gesture_map.get(category, self.speech_rate_gesture_map["normal"])
        
        duration_factor = rate_params["duration_factor"]
        
        adjusted_gestures = []
        for gesture_name, duration in gestures:
            # 调整手势时长
            new_duration = duration * duration_factor
            adjusted_gestures.append((gesture_name, new_duration))
        
        return adjusted_gestures
    
    def _insert_pause_gestures(self, gestures: List[Tuple[str, float]], pauses: List[Dict]) -> List[Tuple[str, float]]:
        """在停顿处插入手势"""
        if not pauses:
            return gestures
        
        # 为每个停顿生成对应的手势
        pause_gestures = []
        for pause in pauses:
            pause_type = pause["type"]
            pause_duration = pause["duration"]
            
            if pause_type == "micro":
                # 微停顿：保持当前姿态
                pause_gestures.append(("hold_current", pause_duration))
            elif pause_type == "short":
                # 短停顿：微调整
                gesture_options = self.prosody_gesture_map["pause_short"]["gestures"]
                selected_gesture = gesture_options[0]  # 简化选择逻辑
                pause_gestures.append((selected_gesture, pause_duration))
            elif pause_type == "medium":
                # 中停顿：过渡手势
                gesture_options = self.prosody_gesture_map["pause_medium"]["gestures"]
                selected_gesture = gesture_options[0]
                pause_gestures.append((selected_gesture, pause_duration))
            elif pause_type == "long":
                # 长停顿：回到休息姿态
                pause_gestures.append(("rest", pause_duration))
        
        # 简化实现：在手势序列末尾添加停顿手势
        # 实际应用中需要根据时间戳精确插入
        return gestures + pause_gestures
    
    def _apply_stress_emphasis(self, gestures: List[Tuple[str, float]], stress_positions: List[Dict]) -> List[Tuple[str, float]]:
        """应用重音强化"""
        if not stress_positions:
            return gestures
        
        # 简化实现：为有重音的时间段增加手势强度
        # 实际应用中需要根据时间戳精确匹配
        emphasized_gestures = []
        
        for gesture_name, duration in gestures:
            # 检查是否需要强化
            needs_emphasis = len(stress_positions) > 0  # 简化判断
            
            if needs_emphasis:
                # 选择更强烈的手势变体
                emphasized_name = self._get_emphasized_gesture(gesture_name)
                emphasized_gestures.append((emphasized_name, duration))
            else:
                emphasized_gestures.append((gesture_name, duration))
        
        return emphasized_gestures
    
    def _get_emphasized_gesture(self, gesture_name: str) -> str:
        """获取强化版本的手势"""
        emphasis_map = {
            "nod_slight": "nod_strong",
            "explain_right_soft": "explain_right_emphatic",
            "explain_left_soft": "explain_left_emphatic",
            "present_right": "present_right_grand",
            "present_left": "present_left_grand",
            "wave_right_gentle": "wave_right_energetic",
            "wave_left_gentle": "wave_left_energetic",
            "head_micro_nod": "head_slight_nod",
            "both_hands_explain": "both_hands_emphasize"
        }
        
        return emphasis_map.get(gesture_name, gesture_name)
    
    def _apply_rhythm_adjustment(self, gestures: List[Tuple[str, float]], rhythm_pattern: Dict) -> List[Tuple[str, float]]:
        """应用节奏调整"""
        rhythm_type = rhythm_pattern.get("type", "steady")
        regularity = rhythm_pattern.get("regularity", 0.5)
        
        if rhythm_type == "choppy":
            # 断续节奏：在手势间插入短暂停顿
            adjusted_gestures = []
            for i, (gesture_name, duration) in enumerate(gestures):
                adjusted_gestures.append((gesture_name, duration))
                if i < len(gestures) - 1:  # 不在最后一个手势后添加停顿
                    adjusted_gestures.append(("neutral", 0.2))
            return adjusted_gestures
        
        elif rhythm_type == "irregular":
            # 不规律节奏：随机调整手势时长
            adjusted_gestures = []
            for gesture_name, duration in gestures:
                # 根据不规律程度调整时长
                variation_factor = 1.0 + (1.0 - regularity) * 0.3  # 最多30%变化
                new_duration = duration * variation_factor
                adjusted_gestures.append((gesture_name, new_duration))
            return adjusted_gestures
        
        else:
            # 规律或稳定节奏：保持原有时长
            return gestures
    
    def create_prosodic_timeline(self, timestamps: List[Dict], total_duration: float) -> List[Dict]:
        """创建韵律时间轴
        
        Args:
            timestamps: 时间戳数据
            total_duration: 总时长
            
        Returns:
            韵律时间轴
        """
        prosodic_features = self.analyze_prosodic_features(timestamps)
        
        timeline = []
        current_time = 0.0
        
        # 基于停顿分段
        pauses = prosodic_features["pauses"]
        segments = []
        
        if pauses:
            # 有停顿信息，按停顿分段
            segment_start = 0
            for pause in pauses:
                # 添加停顿前的段落
                if pause["position"] > segment_start:
                    segment_words = timestamps[segment_start:pause["position"] + 1]
                    segments.append({
                        "words": segment_words,
                        "start_time": segment_words[0].get("start_time", 0),
                        "end_time": segment_words[-1].get("end_time", 0),
                        "pause_after": pause
                    })
                segment_start = pause["position"] + 1
            
            # 添加最后一段
            if segment_start < len(timestamps):
                segment_words = timestamps[segment_start:]
                segments.append({
                    "words": segment_words,
                    "start_time": segment_words[0].get("start_time", 0),
                    "end_time": segment_words[-1].get("end_time", 0),
                    "pause_after": None
                })
        else:
            # 无停顿信息，整体作为一段
            segments.append({
                "words": timestamps,
                "start_time": timestamps[0].get("start_time", 0) if timestamps else 0,
                "end_time": timestamps[-1].get("end_time", 0) if timestamps else total_duration,
                "pause_after": None
            })
        
        # 为每个段落创建时间轴条目
        for segment in segments:
            segment_duration = segment["end_time"] - segment["start_time"]
            
            timeline.append({
                "start": segment["start_time"],
                "duration": segment_duration,
                "type": "speech_segment",
                "words": segment["words"],
                "prosodic_features": {
                    "speech_rate": self._calculate_segment_speech_rate(segment["words"]),
                    "has_stress": any(
                        pos["start_time"] >= segment["start_time"] and 
                        pos["start_time"] <= segment["end_time"]
                        for pos in prosodic_features["stress_positions"]
                    )
                }
            })
            
            # 添加停顿
            if segment["pause_after"]:
                pause = segment["pause_after"]
                timeline.append({
                    "start": segment["end_time"],
                    "duration": pause["duration"],
                    "type": "pause",
                    "pause_type": pause["type"]
                })
        
        return timeline
    
    def _calculate_segment_speech_rate(self, words: List[Dict]) -> Dict:
        """计算段落语速"""
        if not words or len(words) < 2:
            return {"rate": 2.5, "category": "normal"}
        
        total_chars = sum(len(word.get('word', '')) for word in words)
        duration = words[-1].get('end_time', 0) - words[0].get('start_time', 0)
        
        if duration <= 0:
            return {"rate": 2.5, "category": "normal"}
        
        rate = total_chars / duration
        
        # 分类语速
        category = "normal"
        for cat, threshold in sorted(self.speech_rate_thresholds.items(), key=lambda x: x[1]):
            if rate <= threshold:
                category = cat
                break
        else:
            category = "very_fast"
        
        return {"rate": rate, "category": category}