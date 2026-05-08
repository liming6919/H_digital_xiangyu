#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语言学分析模块
分析句子结构、语义角色、话语功能，为动作生成提供语言学依据
"""

import re
from typing import Dict, List, Tuple, Optional
import jieba
import jieba.posseg as pseg

class LinguisticAnalyzer:
    def __init__(self):
        """初始化语言学分析器"""
        
        # 句子结构模式
        self.sentence_patterns = {
            "parallel": [  # 并列句
                r"不仅.*而且",
                r"既.*又",
                r"一方面.*另一方面",
                r".*，.*也",
                r".*和.*都",
                r".*以及.*"
            ],
            "progressive": [  # 递进句
                r"不但.*而且",
                r"不仅.*更",
                r".*甚至.*",
                r".*尤其.*",
                r".*特别.*"
            ],
            "contrastive": [  # 对比句
                r".*但是.*",
                r".*然而.*",
                r".*相反.*",
                r".*而.*",
                r"虽然.*但",
                r"尽管.*却"
            ],
            "causal": [  # 因果句
                r"因为.*所以",
                r"由于.*因此",
                r".*导致.*",
                r".*造成.*"
            ],
            "conditional": [  # 条件句
                r"如果.*就",
                r"假如.*那么",
                r"只要.*就",
                r"除非.*否则"
            ],
            "enumeration": [  # 列举句
                r"第一.*第二",
                r"首先.*其次",
                r"一是.*二是",
                r".*、.*、.*"
            ]
        }
        
        # 语义角色关键词
        self.semantic_roles = {
            "agent": ["我", "我们", "大家", "用户", "客户", "团队"],
            "patient": ["产品", "服务", "系统", "方案", "技术", "问题"],
            "instrument": ["通过", "利用", "使用", "借助", "依靠"],
            "goal": ["目标", "目的", "为了", "达到", "实现"],
            "location": ["这里", "那里", "前面", "后面", "左边", "右边"],
            "time": ["现在", "今天", "明天", "以前", "将来", "接下来"]
        }
        
        # 话语功能标记词
        self.discourse_functions = {
            "introduction": ["介绍", "展示", "呈现", "让我", "给大家"],
            "explanation": ["解释", "说明", "阐述", "详细", "具体"],
            "emphasis": ["重要", "关键", "核心", "特别", "尤其", "必须"],
            "comparison": ["比较", "对比", "相比", "不同", "区别"],
            "summary": ["总结", "总之", "综上", "最后", "结论"],
            "transition": ["接下来", "然后", "另外", "此外", "同时"],
            "question": ["什么", "怎么", "为什么", "如何", "是否", "吗", "呢"]
        }
        
        # 强调程度词
        self.emphasis_levels = {
            "weak": ["有点", "稍微", "略微", "一些"],
            "medium": ["比较", "相当", "挺", "还"],
            "strong": ["很", "非常", "特别", "极其", "十分"],
            "extreme": ["最", "极", "超", "绝对", "完全"]
        }
    
    def analyze_sentence_structure(self, text: str) -> Dict:
        """分析句子结构类型
        
        Args:
            text: 输入文本
            
        Returns:
            句子结构分析结果
        """
        structure_info = {
            "type": "simple",  # 默认简单句
            "patterns": [],
            "complexity": "low"
        }
        
        # 检测句子结构模式
        for pattern_type, patterns in self.sentence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    structure_info["type"] = pattern_type
                    structure_info["patterns"].append(pattern)
                    break
        
        # 评估句子复杂度
        clause_count = len(re.findall(r'[，。！？；：]', text)) + 1
        if clause_count >= 3:
            structure_info["complexity"] = "high"
        elif clause_count == 2:
            structure_info["complexity"] = "medium"
        
        return structure_info
    
    def extract_semantic_roles(self, text: str) -> Dict:
        """提取语义角色
        
        Args:
            text: 输入文本
            
        Returns:
            语义角色信息
        """
        roles = {}
        
        for role, keywords in self.semantic_roles.items():
            found_keywords = []
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)
            
            if found_keywords:
                roles[role] = found_keywords
        
        return roles
    
    def identify_discourse_function(self, text: str) -> Dict:
        """识别话语功能
        
        Args:
            text: 输入文本
            
        Returns:
            话语功能信息
        """
        functions = []
        function_scores = {}
        
        for function, keywords in self.discourse_functions.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 1
            
            if score > 0:
                functions.append(function)
                function_scores[function] = score
        
        # 确定主要功能
        primary_function = "explanation"  # 默认
        if function_scores:
            primary_function = max(function_scores.items(), key=lambda x: x[1])[0]
        
        return {
            "primary": primary_function,
            "all_functions": functions,
            "scores": function_scores
        }
    
    def analyze_emphasis_level(self, text: str) -> Dict:
        """分析强调程度
        
        Args:
            text: 输入文本
            
        Returns:
            强调程度信息
        """
        emphasis_info = {
            "level": "medium",  # 默认中等
            "markers": [],
            "intensity": 1.0
        }
        
        max_level = "weak"
        intensity_map = {"weak": 0.8, "medium": 1.0, "strong": 1.3, "extreme": 1.6}
        
        for level, markers in self.emphasis_levels.items():
            found_markers = [m for m in markers if m in text]
            if found_markers:
                emphasis_info["markers"].extend(found_markers)
                if intensity_map[level] > intensity_map[max_level]:
                    max_level = level
        
        emphasis_info["level"] = max_level
        emphasis_info["intensity"] = intensity_map[max_level]
        
        return emphasis_info
    
    def segment_by_prosody(self, text: str, timestamps: Optional[List[Dict]] = None) -> List[Dict]:
        """基于韵律信息分段
        
        Args:
            text: 输入文本
            timestamps: 时间戳信息（可选）
            
        Returns:
            韵律分段结果
        """
        segments = []
        
        if timestamps:
            # 基于时间戳的韵律分析
            segments = self._analyze_prosodic_segments_with_timestamps(text, timestamps)
        else:
            # 基于标点的简单分段
            segments = self._analyze_prosodic_segments_simple(text)
        
        return segments
    
    def _analyze_prosodic_segments_with_timestamps(self, text: str, timestamps: List[Dict]) -> List[Dict]:
        """基于时间戳分析韵律分段"""
        segments = []
        
        # 计算停顿
        pauses = []
        for i in range(len(timestamps) - 1):
            current_end = timestamps[i].get('end_time', 0)
            next_start = timestamps[i + 1].get('start_time', 0)
            gap = next_start - current_end
            
            if gap > 0.2:  # 200ms以上视为停顿
                pauses.append({
                    'position': i,
                    'duration': gap,
                    'type': 'long' if gap > 0.5 else 'short'
                })
        
        # 基于停顿分段
        current_segment = []
        segment_start = 0
        
        for i, word_info in enumerate(timestamps):
            current_segment.append(word_info)
            
            # 检查是否在停顿位置
            is_pause_point = any(p['position'] == i for p in pauses)
            
            if is_pause_point or i == len(timestamps) - 1:
                # 创建分段
                segment_text = ''.join([w.get('word', '') for w in current_segment])
                segment_duration = current_segment[-1].get('end_time', 0) - current_segment[0].get('start_time', 0)
                
                segments.append({
                    'text': segment_text,
                    'start_time': current_segment[0].get('start_time', 0),
                    'duration': segment_duration,
                    'words': current_segment.copy(),
                    'pause_after': is_pause_point
                })
                
                current_segment = []
        
        return segments
    
    def _analyze_prosodic_segments_simple(self, text: str) -> List[Dict]:
        """基于标点的简单韵律分段"""
        # 按标点分段
        segments_text = re.split(r'([，。！？；：])', text)
        segments = []
        
        current_pos = 0
        for i in range(0, len(segments_text), 2):
            if i < len(segments_text):
                segment_text = segments_text[i]
                punctuation = segments_text[i + 1] if i + 1 < len(segments_text) else ""
                
                if segment_text.strip():
                    segments.append({
                        'text': segment_text + punctuation,
                        'start_pos': current_pos,
                        'length': len(segment_text + punctuation),
                        'has_pause': punctuation in '。！？；：'
                    })
                    current_pos += len(segment_text + punctuation)
        
        return segments
    
    def generate_gesture_constraints(self, text: str, timestamps: Optional[List[Dict]] = None) -> Dict:
        """生成手势约束条件
        
        Args:
            text: 输入文本
            timestamps: 时间戳信息（可选）
            
        Returns:
            手势约束信息
        """
        # 综合分析
        structure = self.analyze_sentence_structure(text)
        roles = self.extract_semantic_roles(text)
        discourse = self.identify_discourse_function(text)
        emphasis = self.analyze_emphasis_level(text)
        segments = self.segment_by_prosody(text, timestamps)
        
        # 生成约束条件
        constraints = {
            "structure_type": structure["type"],
            "complexity": structure["complexity"],
            "primary_function": discourse["primary"],
            "emphasis_intensity": emphasis["intensity"],
            "semantic_roles": roles,
            "prosodic_segments": segments,
            "gesture_strategy": self._determine_gesture_strategy(structure, discourse, emphasis, roles)
        }
        
        return constraints
    
    def _determine_gesture_strategy(self, structure: Dict, discourse: Dict, emphasis: Dict, roles: Dict) -> Dict:
        """确定手势策略"""
        strategy = {
            "primary_hand": "right",  # 默认右手主导
            "use_both_hands": False,
            "gesture_intensity": 1.0,
            "rhythm_pattern": "steady",
            "spatial_mapping": {}
        }
        
        # 根据句子结构调整策略
        if structure["type"] == "parallel":
            strategy["use_both_hands"] = True
            strategy["spatial_mapping"] = {"left": "first_item", "right": "second_item"}
        elif structure["type"] == "contrastive":
            strategy["use_both_hands"] = True
            strategy["spatial_mapping"] = {"left": "old_concept", "right": "new_concept"}
        elif structure["type"] == "enumeration":
            strategy["rhythm_pattern"] = "sequential"
            strategy["spatial_mapping"] = {"progression": "left_to_right"}
        
        # 根据话语功能调整
        if discourse["primary"] == "emphasis":
            strategy["gesture_intensity"] = emphasis["intensity"]
        elif discourse["primary"] == "introduction":
            strategy["use_both_hands"] = True
        elif discourse["primary"] == "explanation":
            strategy["primary_hand"] = "right"
        
        # 根据语义角色调整
        if "agent" in roles:
            strategy["self_reference"] = True
        if "patient" in roles:
            strategy["object_reference"] = True
        
        return strategy