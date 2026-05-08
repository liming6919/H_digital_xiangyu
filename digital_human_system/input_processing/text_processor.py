#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理模块
负责文本预处理和基础分析
"""

import re
import os
import json
import jieba
from typing import List, Dict

class TextProcessor:
    def __init__(self):
        """初始化文本处理器"""
        # 初始化jieba分词
        jieba.initialize()
        
        # 情感关键词字典
        self.emotion_keywords = {
            "happy": ["高兴", "开心", "快乐", "兴奋", "愉快", "欢迎", "祝贺"],
            "sad": ["难过", "伤心", "失望", "沮丧", "悲伤"],
            "angry": ["生气", "愤怒", "不满", "抗议"],
            "surprised": ["惊讶", "意外", "震惊", "不敢相信"],
            "neutral": ["说明", "介绍", "描述", "讲解", "分析"]
        }
        
        # 意图关键词字典
        self.intent_keywords = {
            "greeting": ["你好", "欢迎", "见面", "问候", "早上好", "下午好", "晚上好"],
            "farewell": ["再见", "告别", "拜拜", "下次见", "回头见"],
            "explanation": ["解释", "说明", "介绍", "讲解", "描述", "展示"],
            "question": ["什么", "为什么", "怎么", "如何", "吗", "呢", "？"],
            "emphasis": ["重要", "关键", "注意", "特别", "强调", "必须"],
            "agreement": ["同意", "对", "是的", "没错", "正确", "好的"],
            "disagreement": ["不对", "错误", "不同意", "反对", "不是"]
        }
        
        # 🎯 动作词汇映射字典
        self.action_keywords = {
            # 挥手类动作
            "wave_right": [
                "挥手","右手挥手", "右手招手", "用右手挥手", "右手摆手", "右手挥挥"
            ],
            "wave_left": ["左手挥手", "左手招手", "用左手挥手", "左手摆手", "左手挥挥"],
            "wave_both": [
                # 明确的双手挥手
                "双手挥手", "两手挥手", "双手招手", "两手招手", "双手摆手", "两手摆手", "双手挥挥",
                # 🎯 通用挥手使用双手（避免与左手挥手冲突）
                 "招手", "摆手", "挥挥手", "招招手", "挥一挥", "招一招",
                # 问候语（通常用双手挥手）
                "大家好", "各位好", "你们好", "朋友们好", "同学们好", "欢迎大家", "欢迎各位",
                "hello大家", "hi大家", "大家hello", "大家hi"
            ],
            
            # 握手类动作
            "handshake": ["握手", "握握手", "伸手", "伸出手","握个手"],
            
            # 拥抱类动作
            "embrace": ["拥抱", "抱抱", "张开双臂", "张开手臂","这么大","抱一抱","非常大"],
            
            # 鼓掌类动作
            "clap": ["鼓掌", "拍手", "拍拍手", "掌声", "鼓鼓掌", "拍掌", "鼓掌吧", "给掌声"],
            
            # 指向类动作
            "point": ["指向", "指着", "指一下", "指指", "用手指"],
            "point_forward": ["指向前方", "向前指", "朝前指", "指前面", "往前指", "前方", "指着前面"],
            
            # 展示类动作
            "present": ["展示", "呈现", "显示", "介绍一下"],
            "show": ["给你看", "看这里", "看看这个","你看"],
            
            # 邀请类动作
            "invite": ["请", "邀请", "来吧", "过来"],
            
            # 停止类动作
            "stop": ["停", "停止", "等等", "慢着", "停下", "别动", "暂停"],
            
            # 同意类动作
            "nod": ["点头", "点点头", "嗯嗯"],
            "ok": ["好的", "OK", "没问题", "可以"],
            
            # 🎯 基于挥手动作的新手势关键词
            "thumbs_up": ["点赞", "赞", "棒", "好棒", "厉害", "给你点赞", "竖大拇指", "拇指向上"],
            "come_here": ["过来", "来这里", "到这边来", "过来一下", "招手过来", "叫过来"],
            "peace": ["胜利", "V字手势", "耶", "比V", "胜利手势", "和平手势"],
            "applaud": ["鼓掌准备", "准备鼓掌", "抬手鼓掌", "举手鼓掌"],
            
            # 否定类动作
            "shake_head": ["摇头", "摇摇头", "不不不"],
            
            # 思考类动作
            "think": ["想想", "思考", "让我想想", "考虑一下"],
            
            # 惊讶类动作
            "surprise": ["哇", "天哪", "不会吧", "真的吗"],
            
            # 看向类动作
            "look_left": ["向左看", "看左边", "左看", "往左看", "朝左看"],
            "look_right": ["向右看", "看右边", "右看", "往右看", "朝右看"],
            "look_up": ["向上看", "看上面", "抬头看", "往上看", "朝上看"],
            "look_down": ["向下看", "看下面", "低头看", "往下看", "朝下看"],
            "turn_left": ["转向左边", "大幅向左", "左转", "转左"],
            "turn_right": ["转向右边", "大幅向右", "右转", "转右"]
            ,
            # 舞蹈类（关键词触发）
            "dance": ["跳舞", "舞蹈", "来一段舞", "来段舞", "跳一段", "跳一个", "dance"],
            "dance_loop": ["循环跳舞", "一直跳", "反复跳", "循环舞", "repeat"],
            "dance_mech": ["机械舞", "机械风", "机械感", "robot dance"],
            "dance_short": ["短舞", "小段舞", "短一点舞", "简短一段舞"],
            "dance_isolation": ["isolation", "分离感舞", "分离风舞", "分离感"],
            
            # 肌肉展示类
            # "muscle_pose": ["秀肌肉", "修肌肉", "肌肉展示", "展示肌肉"]
        }
        
        # 记录自定义动作配置的修改时间，支持热加载
        self._custom_actions_mtime = None
        self._custom_gestures_mtime = None

        # 额外的正则匹配（覆盖“跳个舞/来一段跳舞”等变体）
        self.action_regex = {
            "dance_mech": [r"(机械|robot)\s*.{0,2}(舞|dance)"] ,
            "dance_short": [r"(短|小段|简短).{0,2}(舞|舞蹈)"],
            "dance_loop": [r"(循环|一直|反复).{0,2}(跳|舞)"],
            "dance_isolation": [r"(isolation|分离).{0,3}(舞|风)"],
            "dance": [r"跳.{0,2}舞", r"来.{0,2}段.{0,2}(舞|舞蹈)", r"dance"],
            # 肌肉展示
            # "muscle_pose": [r"(秀|修).{0,2}肌肉", r"肌肉.{0,2}(展示|show)"]
        }
        self._load_custom_actions()
        # 日志开关：默认关闭调试刷屏，export DH_VERBOSE=1 开启
        self._verbose = bool(int(os.environ.get("DH_VERBOSE", "0")))

    def _maybe_reload_custom_actions(self):
        """当 custom_actions/custom_gestures 变更时自动热加载（无需重启主程序）"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            custom_actions_path = os.path.normpath(os.path.join(base_dir, "..", "custom_actions.json"))
            custom_gestures_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            am = os.path.getmtime(custom_actions_path) if os.path.exists(custom_actions_path) else None
            gm = os.path.getmtime(custom_gestures_path) if os.path.exists(custom_gestures_path) else None
            if am != self._custom_actions_mtime or gm != self._custom_gestures_mtime:
                # 重新加载会增量合并到 action_keywords/action_regex/_custom_gesture_map
                self._load_custom_actions()
                self._custom_actions_mtime = am
                self._custom_gestures_mtime = gm
                if getattr(self, "_verbose", False):
                    print("🧩 [热加载] 已刷新 custom_actions.json / custom_gestures.json 动作关键词")
        except Exception:
            # 热加载失败不影响主流程
            return

    def _load_custom_actions(self):
        """加载自定义动作配置，包括从 custom_gestures.json 自动生成关键词映射"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 1. 加载 custom_actions.json（如果存在）
            custom_actions_path = os.path.normpath(os.path.join(base_dir, "..", "custom_actions.json"))
            if os.path.exists(custom_actions_path):
                try:
                    self._custom_actions_mtime = os.path.getmtime(custom_actions_path)
                except Exception:
                    pass
                with open(custom_actions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                aliases = data.get("action_aliases", {})
                for act, kws in aliases.items():
                    if not isinstance(kws, list):
                        continue
                    self.action_keywords.setdefault(act, [])
                    for w in kws:
                        if w not in self.action_keywords[act]:
                            self.action_keywords[act].append(w)
                regs = data.get("action_regex", {})
                for act, pats in regs.items():
                    if not isinstance(pats, list):
                        continue
                    self.action_regex.setdefault(act, [])
                    for p in pats:
                        if p not in self.action_regex[act]:
                            self.action_regex[act].append(p)
            
            # 2. 🎯 自动从 custom_gestures.json 的 base_gestures 生成关键词映射
            custom_gestures_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            if os.path.exists(custom_gestures_path):
                try:
                    self._custom_gestures_mtime = os.path.getmtime(custom_gestures_path)
                except Exception:
                    pass
                with open(custom_gestures_path, "r", encoding="utf-8") as f:
                    gestures_data = json.load(f)
                base_gestures = gestures_data.get("base_gestures", {})
                
                # 为每个 base_gesture 自动生成动作映射
                for gesture_name, angles in base_gestures.items():
                    if not isinstance(angles, list) or len(angles) != 12:
                        continue
                    
                    # 生成动作类型名（使用手势名本身，或转换为英文key）
                    # 如果手势名是中文，创建一个对应的英文action key
                    action_key = None
                    gesture_lower = gesture_name.lower()
                    
                    # 已知映射
                    if "点赞" in gesture_name or "赞" in gesture_name:
                        action_key = "thumbs_up"
                    # elif "肌肉" in gesture_name:
                    #     action_key = "muscle_pose"
                    else:
                        # 其他新动作：使用手势名作为action key（转换为snake_case）
                        # 如果是中文，直接使用手势名作为key
                        action_key = gesture_name
                    
                    if action_key:
                        # 自动生成关键词：手势名本身 + 常见变体
                        keywords = [gesture_name]
                        # 如果是中文手势，添加一些常见变体
                        if any('\u4e00' <= c <= '\u9fff' for c in gesture_name):
                            # 中文手势：添加"做XX"、"来一个XX"等变体
                            keywords.extend([
                                f"做{gesture_name}",
                                f"来一个{gesture_name}",
                                f"来一个{gesture_name}动作",
                                f"执行{gesture_name}",
                            ])
                        
                        # 添加到 action_keywords
                        self.action_keywords.setdefault(action_key, [])
                        for kw in keywords:
                            if kw not in self.action_keywords[action_key]:
                                self.action_keywords[action_key].append(kw)
                        
                        # 同时更新 map_action_to_gesture 的映射
                        if not hasattr(self, '_custom_gesture_map'):
                            self._custom_gesture_map = {}
                        self._custom_gesture_map[action_key] = gesture_name
        except Exception as e:
            if self._verbose:
                print(f"⚠️  加载自定义动作配置失败: {e}")
            pass
    
    def preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 去除多余空格和换行
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 去除特殊字符（保留中文、英文、数字、标点）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,!?;:，。！？；：]', '', text)
        
        return text
    
    def segment_text(self, text: str) -> List[str]:
        """文本分词"""
        return list(jieba.cut(text))
    
    def extract_emotion(self, text: str) -> str:
        """提取情感倾向"""
        words = self.segment_text(text)
        emotion_scores = {emotion: 0 for emotion in self.emotion_keywords}
        
        for word in words:
            for emotion, keywords in self.emotion_keywords.items():
                if word in keywords:
                    emotion_scores[emotion] += 1
        
        # 返回得分最高的情感，默认为neutral
        max_emotion = max(emotion_scores, key=emotion_scores.get)
        return max_emotion if emotion_scores[max_emotion] > 0 else "neutral"
    
    def extract_intent(self, text: str) -> str:
        """提取意图"""
        words = self.segment_text(text)
        intent_scores = {intent: 0 for intent in self.intent_keywords}
        
        for word in words:
            for intent, keywords in self.intent_keywords.items():
                if word in keywords:
                    intent_scores[intent] += 1
        
        # 返回得分最高的意图，默认为explanation
        max_intent = max(intent_scores, key=intent_scores.get)
        return max_intent if intent_scores[max_intent] > 0 else "explanation"
    
    def extract_actions(self, text: str) -> List[str]:
        """🎯 提取文本中的动作指令 - 修复优先级和重复问题"""
        # 支持热加载：运行中修改 JSON 也能立即生效
        self._maybe_reload_custom_actions()

        detected_actions = []
        
        # 🎯 关键修复：按关键词长度排序，优先匹配长关键词
        all_keywords = []
        for action_type, keywords in self.action_keywords.items():
            for keyword in keywords:
                all_keywords.append((keyword, action_type))
        
        # 按关键词长度降序排序，长的优先匹配
        all_keywords.sort(key=lambda x: len(x[0]), reverse=True)
        
        # 检查文本中是否包含关键词
        used_actions = set()
        matched_keywords = set()  # 记录已匹配的关键词
        
        if self._verbose:
            print(f"🔍 [调试] 开始检测文本: '{text}'")
        
        for keyword, action_type in all_keywords:
            if keyword in text and action_type not in used_actions:
                # 🎯 修复冲突检测逻辑：如果已匹配的关键词包含当前关键词，则跳过
                is_conflicted = False
                for matched_keyword in matched_keywords:
                    # 如果当前关键词是已匹配关键词的子串，则认为冲突
                    # 例如："挥手" in "左手挥手" -> 冲突
                    if keyword in matched_keyword:
                        is_conflicted = True
                        if self._verbose:
                            print(f"🔍 [调试] 关键词冲突: '{keyword}' 是 '{matched_keyword}' 的子串，跳过")
                        break
                    # 如果已匹配的关键词是当前关键词的子串，也认为冲突
                    # 例如："左手挥手" in "挥手" -> 不可能，但为了完整性
                    if matched_keyword in keyword:
                        is_conflicted = True
                        if self._verbose:
                            print(f"🔍 [调试] 关键词冲突: '{matched_keyword}' 是 '{keyword}' 的子串，跳过")
                        break
                
                if not is_conflicted:
                    detected_actions.append(action_type)
                    used_actions.add(action_type)
                    matched_keywords.add(keyword)
                    if self._verbose:
                        print(f"🎭 检测到动作: '{keyword}' -> {action_type}")
        
        # 使用正则进一步匹配
        for action_type, patterns in getattr(self, "action_regex", {}).items():
            if action_type in used_actions:
                continue
            for pat in patterns:
                if re.search(pat, text, flags=re.IGNORECASE):
                    detected_actions.append(action_type)
                    used_actions.add(action_type)
                    if self._verbose:
                        print(f"🎭 正则检测到动作: '{pat}' -> {action_type}")
                    break
        
        # 🎭 动态动作检测：如果没有找到已定义动作，尝试识别动作描述
        if not detected_actions:
            text_lower = text.lower()
            # 🎯 更严格的动作模式检测，避免误判普通对话
            action_patterns = [
                (r"(左手|右手|双手)(举|抬|放|指|伸|挥|摆)", "手部动作"),
                (r"(头|脖子)(向|往)?(左|右|上|下|点|摇)", "头部动作"), 
                (r"^(思考|沉思|想一想)$", "思考动作"),  # 更严格匹配
                (r"(鼓掌|拍手|拍拍手)", "鼓掌动作"),
                (r"(敬礼|致敬)", "敬礼动作"),
                (r"(张开|展开|合拢)(双手|手臂)", "展开动作"),
            ]
            
            # 🎯 只有文本很短且明确是动作指令时才触发动态生成
            if len(text.strip()) < 20:  # 只对短文本进行动作检测
                for pattern, action_type in action_patterns:
                    if re.search(pattern, text_lower):
                        # 使用原始文本作为动作描述
                        dynamic_action = f"dynamic_{text.strip()}"
                        detected_actions.append(dynamic_action)
                        if self._verbose:
                            print(f"🎭 检测到动态动作: {text.strip()}")
                        break
        
        if self._verbose:
            print(f"🔍 [调试] 最终检测结果: {detected_actions}")
        return detected_actions
    
    def map_action_to_gesture(self, action: str) -> str:
        """🎯 将动作映射到具体手势"""
        # 🎯 优先检查自定义手势映射（从 JSON 自动生成的）
        if hasattr(self, '_custom_gesture_map') and action in self._custom_gesture_map:
            return self._custom_gesture_map[action]
        
        action_gesture_map = {
            # 挥手类
            "wave_right": "wave_right_energetic",
            "wave_left": "wave_left_energetic", 
            "wave_both": "open_arms_wide",
            
            # 握手类
            "handshake": "invite_right_welcoming",
            
            # 拥抱类 - 使用静态手势，时长2.5秒
            "embrace": "embrace_warm",  # 🎯 使用简单的embrace_warm，时长在gesture_policy.py中设置为2.5秒
            
            # 鼓掌类
            "clap": "applaud_ready",
            
            # 指向类
            "point": "point_right_formal",                                                                       
            "point_forward": "point_forward_firm",
            
            # 展示类
            "present": "present_right_grand",
            "show": "present_right",
            
            # 邀请类
            "invite": "invite_right_welcoming",
            
            # 停止类
            "stop": "gesture_stop",
            
            # 同意类
            "nod": "nod_strong",
            "ok": "gesture_ok",
            
            # 否定类
            "shake_head": "shake_strong",
            
            # 思考类
            "think": "think_deep",
            
            # 惊讶类
            "surprise": "surprise_strong",
            
            # 🎯 看向类动作 - 修复缺失的映射！
            "look_left": "look_left_strong",
            "look_right": "look_right_strong", 
            "look_up": "look_up",
            "look_down": "look_down",
            "turn_left": "look_left_dramatic",
            "turn_right": "look_right_dramatic",
            
            # 🎯 补充其他缺失的动作映射
            "thumbs_up": "点赞",  # 🎯 映射到 JSON 中的中文手势名
            "come_here": "come_here", 
            "peace": "peace_sign",
            "applaud": "applaud_ready",
            # "muscle_pose": "肌肉",  # 🎯 映射到 JSON 中的中文手势名
            
            # 舞蹈类（仅作兜底占位，真正的舞蹈序列由 GesturePolicy 根据 detected_actions 调度）
            "dance": "open_arms_triumphant",
            "dance_loop": "open_arms_triumphant",
            "dance_mech": "open_arms_triumphant",
            "dance_short": "open_arms_triumphant",
            "dance_isolation": "open_arms_triumphant"
        }
        
        return action_gesture_map.get(action, "neutral")
    
    def find_emphasis_words(self, text: str) -> List[str]:
        """找出需要强调的词汇"""
        emphasis_words = []
        words = self.segment_text(text)
        
        # 查找强调关键词
        for word in words:
            if word in self.emotion_keywords.get("emphasis", []):
                emphasis_words.append(word)
        
        # 查找感叹号附近的词
        sentences = re.split(r'[!！]', text)
        for sentence in sentences:
            if sentence.strip():
                words_in_sentence = self.segment_text(sentence)
                if len(words_in_sentence) <= 3:  # 短句通常是强调
                    emphasis_words.extend(words_in_sentence)
        
        return list(set(emphasis_words))  # 去重
    
    def process(self, text: str) -> Dict:
        """完整的文本处理流程"""
        # 预处理
        clean_text = self.preprocess_text(text)
        
        # 分词
        words = self.segment_text(clean_text)
        
        # 提取信息
        emotion = self.extract_emotion(clean_text)
        intent = self.extract_intent(clean_text)
        emphasis_words = self.find_emphasis_words(clean_text)
        
        # 🎯 提取动作指令
        detected_actions = self.extract_actions(clean_text)
        
        return {
            "original_text": text,
            "clean_text": clean_text,
            "words": words,
            "emotion": emotion,
            "intent": intent,
            "emphasis_words": emphasis_words,
            "word_count": len(words),
            "detected_actions": detected_actions  # 新增动作列表
        }

if __name__ == "__main__":
    # 测试代码
    processor = TextProcessor()
    
    test_texts = [
        "你好，欢迎来到我们的展示！",
        "今天我要为大家介绍一个重要的技术",
        "这个方案有什么优势吗？",
        "非常感谢大家的参与，再见！"
    ]
    
    for text in test_texts:
        result = processor.process(text)
        print(f"文本: {text}")
        print(f"情感: {result['emotion']}")
        print(f"意图: {result['intent']}")
        print(f"强调词: {result['emphasis_words']}")
        print("-" * 50)
