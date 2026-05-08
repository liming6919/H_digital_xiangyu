#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手指映射器
Finger Mapper - 将手势语义映射到手指动作
"""

from typing import Dict, List, Optional
import math
import os


class FingerMapper:
    """手指映射器 - 根据手势语义生成手指动作"""
    
    def __init__(self):
        """初始化手指映射器"""
        # 手指配置：{手指名称: 舵机ID}
        # 实际配置：单手的6个舵机
        # 1号：小拇指, 2号：无名指, 3号：中指, 4号：食指, 5号：大拇指, 6号：虎口收张
        self.finger_config = {
            'pinky': 1,      # 小拇指
            'ring': 2,       # 无名指
            'middle': 3,     # 中指
            'index': 4,      # 食指
            'thumb': 5,      # 大拇指
            'thumb_gap': 6,  # 虎口收张
        }
        
        # 位置范围：由 ym_info 读取，未读到则用 600-2500 兜底
        self.position_min = 600
        self.position_max = 2500
        self.position_range = self.position_max - self.position_min
        # 每舵机 min/max（从 ym_info 解析），用于归一化。{servo_id: (min, max)}
        self._per_finger_limits: Dict[int, tuple] = {}
        # 手势明确指定驱动哪只手（来自 finger_gestures 的 hand 字段），优先于名称推断
        self.gesture_hand_overrides: Dict[str, str] = {}
        
        # 手势到手指动作的映射（使用0-100的百分比）
        # 0-50%: 600→2200（伸直到临界）
        # 50-100%: 2200→2500（弯曲）
        self.gesture_finger_map = {
            # 点赞手势 - 拇指伸直，其他手指弯曲
            'thumbs_up': {
                'thumb': 0,        # 拇指伸直/放松（800）
                'index': 80,       # 其他手指弯曲/握紧（800 + 80% * 1400 = 1920）
                'middle': 80,
                'ring': 80,
                'pinky': 80,
                'thumb_gap': 70,   # 虎口张开（800 + 70% * 1400 = 1780）
            },
            # OK手势 - 拇指和食指形成O形（弯曲）
            'ok_gesture': {
                'thumb': 50,       # 拇指弯曲（800 + 50% * 1400 = 1500）
                'index': 50,       # 食指弯曲（800 + 50% * 1400 = 1500）
                'middle': 90,      # 其他手指完全弯曲/握紧（800 + 90% * 1400 = 2060）
                'ring': 90,
                'pinky': 90,
                'thumb_gap': 40,   # 虎口半闭合（800 + 40% * 1400 = 1360）
            },
            # 握手手势 - 手指自然弯曲，准备握手
            'handshake': {
                'thumb': 30,       # 拇指稍微弯曲（800 + 30% * 1400 = 1220）
                'index': 40,       # 手指自然弯曲（800 + 40% * 1400 = 1360）
                'middle': 40,
                'ring': 40,
                'pinky': 40,
                'thumb_gap': 20,   # 虎口半张开（800 + 20% * 1400 = 1080）
            },
            'handshake_extend': {
                'thumb': 20,       # 手指稍微伸直，准备伸手（800 + 20% * 1400 = 1080）
                'index': 30,
                'middle': 30,
                'ring': 30,
                'pinky': 30,
                'thumb_gap': 40,   # 虎口稍微张开
            },
            'handshake_grip': {
                'thumb': 50,       # 手指弯曲，握住（800 + 50% * 1400 = 1500）
                'index': 60,       # 手指握紧（800 + 60% * 1400 = 1640）
                'middle': 60,
                'ring': 60,
                'pinky': 60,
                'thumb_gap': 30,   # 虎口闭合（800 + 30% * 1400 = 1220）
            },
            # 指向手势 - 食指伸直，其他手指弯曲
            'point': {
                'thumb': 50,       # 拇指弯曲（800 + 50% * 1400 = 1500）
                'index': 0,        # 食指完全伸直/放松（800）
                'middle': 80,      # 其他手指弯曲/握紧（800 + 80% * 1400 = 1920）
                'ring': 80,
                'pinky': 80,
                'thumb_gap': 40,   # 虎口稍微张开（800 + 40% * 1400 = 1360）
            },
            'point_right_casual': {
                'thumb': 50,
                'index': 0,        # 食指伸直
                'middle': 80,
                'ring': 80,
                'pinky': 80,
                'thumb_gap': 40,
            },
            'point_left_casual': {
                'thumb': 50,
                'index': 0,        # 食指伸直
                'middle': 80,
                'ring': 80,
                'pinky': 80,
                'thumb_gap': 40,
            },
            # 握拳 - 所有手指弯曲/握紧
            'fist': {
                'thumb': 80,       # 拇指弯曲（800 + 80% * 1400 = 1920）
                'index': 95,       # 其他手指完全弯曲/握紧（800 + 95% * 1400 = 2130）
                'middle': 95,
                'ring': 95,
                'pinky': 95,
                'thumb_gap': 10,   # 虎口闭合（800 + 10% * 1400 = 940）
            },
            # 张开手掌 - 所有手指伸直/放松
            'open_hand': {
                'thumb': 10,       # 拇指稍微弯曲（800 + 10% * 1400 = 940）
                'index': 0,        # 所有手指完全伸直/放松（800）
                'middle': 0,
                'ring': 0,
                'pinky': 0,
                'thumb_gap': 80,   # 虎口完全张开（800 + 80% * 1400 = 1920）
            },
            # 自然放松 - 手指轻微弯曲
            'rest': {
                'thumb': 30,       # 轻微弯曲（800 + 30% * 1400 = 1220）
                'index': 40,       # 稍微弯曲（800 + 40% * 1400 = 1360）
                'middle': 40,
                'ring': 40,
                'pinky': 40,
                'thumb_gap': 50,   # 虎口半张开（800 + 50% * 1400 = 1500）
            },
            'neutral': {
                'thumb': 30,
                'index': 40,
                'middle': 40,
                'ring': 40,
                'pinky': 40,
                'thumb_gap': 50,
            },
            # both_hands_* 语音手势的默认手指映射（幅度明显，可被 finger_gestures 覆盖）
            'explain': {
                'thumb': 45, 'index': 55, 'middle': 60, 'ring': 60, 'pinky': 60, 'thumb_gap': 55,
            },
            'emphasize': {
                'thumb': 55, 'index': 70, 'middle': 75, 'ring': 75, 'pinky': 75, 'thumb_gap': 45,
            },
            'present': {
                'thumb': 35, 'index': 25, 'middle': 40, 'ring': 45, 'pinky': 45, 'thumb_gap': 75,
            },
            'welcome': {
                'thumb': 35, 'index': 30, 'middle': 40, 'ring': 45, 'pinky': 45, 'thumb_gap': 80,
            },
            'wave': {
                'thumb': 35, 'index': 45, 'middle': 45, 'ring': 45, 'pinky': 45, 'thumb_gap': 65,
            },
        }
        
        # 手势名称匹配规则（支持部分匹配，both_hands_* 优先映射到语义键）
        self.gesture_patterns = {
            'thumbs_up': ['thumbs_up', 'thumb', '点赞', '赞'],
            'ok_gesture': ['ok', 'ok_gesture', '好的'],
            'handshake': ['handshake', '握手'],
            'point': ['point', '指向', '指'],
            'fist': ['fist', 'grip', '握拳', '拳头','抓一下'],
            'open_hand': ['open', 'spread', '张开', '打开','松手'],
            'rest': ['rest', 'neutral', 'idle', '休息', '待机','谢谢','再见'],
            # both_hands_* 语音手势 → 映射到 gesture_finger_map 语义键（可被 custom finger_gestures 覆盖）
            'explain': ['both_hands_explain', 'explain', '说明', '解释'],
            'emphasize': ['both_hands_emphasize', 'emphasize', '强调'],
            'present': ['both_hands_present', 'present', '展示'],
            'welcome': ['welcome', '欢迎'],
        }
        
        # 根据上下文语义的额外映射（让手指根据手势类型动一动）
        # 语音触发时 both_hands_explain / both_hands_emphasize 等会命中此处，需保证弯曲幅度明显
        # 0% = 600（伸直/放松），100% = 2500（弯曲/握紧）
        self.semantic_gesture_map = {
            # 挥手类手势 - 手指自然张开、适度弯曲
            'wave': {
                'thumb': 35,
                'index': 45,
                'middle': 45,
                'ring': 45,
                'pinky': 45,
                'thumb_gap': 65,
            },
            # 解释说明类 - 手指自然弯曲、便于表达（原 10/20 幅度过小，改为明显弯曲）
            'explain': {
                'thumb': 45,
                'index': 55,
                'middle': 60,
                'ring': 60,
                'pinky': 60,
                'thumb_gap': 55,
            },
            # 展示类 - 手指张开、略弯
            'present': {
                'thumb': 35,
                'index': 25,
                'middle': 40,
                'ring': 45,
                'pinky': 45,
                'thumb_gap': 75,
            },
            # 强调类 - 手指明显弯曲、有力
            'emphasize': {
                'thumb': 55,
                'index': 70,
                'middle': 75,
                'ring': 75,
                'pinky': 75,
                'thumb_gap': 45,
            },
            # 欢迎类 - 手指张开、明显
            'welcome': {
                'thumb': 35,
                'index': 30,
                'middle': 40,
                'ring': 45,
                'pinky': 45,
                'thumb_gap': 80,
            },
        }

        # 记录哪些手势的手指姿态来自 custom_gestures.json（用于区别“精确控制”与“语义默认”）
        self.custom_finger_gestures = set()

        # 从 custom_gestures.json 加载自定义手指映射（如果存在）
        self._load_custom_from_json()

    def _load_custom_from_json(self):
        """
        从 digital_human_system/custom_gestures.json 中加载自定义手指映射。
        期望结构:
        {
          "finger_gestures": {
            "手势名": {
              "thumb": 30,
              "index": 40,
              ...
            }
          }
        }
        """
        try:
            import os
            import json

            base_dir = os.path.dirname(os.path.abspath(__file__))
            custom_path = os.path.normpath(os.path.join(base_dir, "..", "custom_gestures.json"))
            if not os.path.exists(custom_path):
                return

            with open(custom_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return

            fg = data.get("finger_gestures", {})
            if not isinstance(fg, dict):
                return

            for gesture_name, pose in fg.items():
                if not isinstance(pose, dict):
                    continue
                # 解析 hand 字段：left/right/both，用于决定只驱动哪只手
                hand_val = pose.get("hand")
                if hand_val in ("left", "right", "both"):
                    self.gesture_hand_overrides[gesture_name] = str(hand_val)
                mapped: Dict[str, int] = {}
                for finger_name, percentage in pose.items():
                    if finger_name == "hand" or finger_name not in self.finger_config:
                        continue
                    try:
                        val = float(percentage)
                    except Exception:
                        continue
                    # 百分比限制在 0-100
                    if val < 0.0:
                        val = 0.0
                    elif val > 100.0:
                        val = 100.0
                    mapped[finger_name] = val

                if mapped:
                    # 自定义映射会覆盖内置映射，逻辑与上肢自定义手势类似
                    self.gesture_finger_map[gesture_name] = mapped
                    self.custom_finger_gestures.add(gesture_name)
            # 加载完成后打印，便于确认自定义手指已生效（可通过 DH_VERBOSE=1 查看）
            _loaded = len([k for k in self.gesture_finger_map if k in self.custom_finger_gestures])
            if _loaded > 0 and os.environ.get("DH_VERBOSE") == "1":
                print(f"[手指映射] 已加载 {_loaded} 个自定义手指手势 from {custom_path}")
        except Exception as e:
            if os.environ.get("DH_VERBOSE") == "1":
                import traceback
                print(f"[手指映射] 加载 custom_gestures.json 失败: {e}")
                traceback.print_exc()
    
    def get_finger_positions(self, gesture_name: str) -> Optional[Dict[str, int]]:
        """
        根据手势名称获取手指位置（百分比0-100）
        
        Args:
            gesture_name: 手势名称（支持复合名如 "both_hands_explain__with__head_natural_left"）
            
        Returns:
            手指位置字典 {finger_name: percentage (0-100)}
        """
        if not gesture_name:
            return self.gesture_finger_map.get('rest', {}).copy()
        gesture_name_lower = gesture_name.lower()
        
        # 复合手势：hand__with__head 格式，优先用 hand 部分查手指
        if "__with__" in gesture_name:
            base_gesture = gesture_name.split("__with__")[0].strip()
            if base_gesture and base_gesture in self.gesture_finger_map:
                return self.gesture_finger_map[base_gesture].copy()
        
        # 精确匹配
        if gesture_name in self.gesture_finger_map:
            return self.gesture_finger_map[gesture_name].copy()
        
        # 模式匹配
        for pattern_key, patterns in self.gesture_patterns.items():
            for pattern in patterns:
                if pattern in gesture_name_lower:
                    base_gesture = pattern_key
                    if base_gesture in self.gesture_finger_map:
                        return self.gesture_finger_map[base_gesture].copy()
        
        # 语义匹配 - 根据手势类型匹配（让手指根据上下文动一动）
        for semantic_key, finger_pos in self.semantic_gesture_map.items():
            if semantic_key in gesture_name_lower:
                return finger_pos.copy()
        
        # 默认返回rest状态
        return self.gesture_finger_map.get('rest', {}).copy()
    
    def set_per_finger_limits(self, limits: Dict[int, tuple]):
        """
        设置每舵机的 min/max，用于归一化。limits: {servo_id: (min, max)}
        配置格式：第二行=最大值，第三行=最小值。仅保留 1~6 号手指舵机。
        """
        self._per_finger_limits = {
            int(sid): (int(mn), int(mx))
            for sid, (mn, mx) in limits.items()
            if 1 <= int(sid) <= 6 and int(mx) > int(mn)
        }

    def _pct_to_position(self, pct: float, full_amplitude: bool = True, servo_id: Optional[int] = None) -> int:
        """
        将百分比(0-100)转为舵机位置。线性归一化，使用读取到的 min/max：
        0% = min（伸直），100% = max（握紧）。有 per_finger 时用该舵机范围，否则用全局。
        """
        pct = max(0.0, min(100.0, float(pct)))
        if servo_id is not None and servo_id in self._per_finger_limits:
            pos_min, pos_max = self._per_finger_limits[servo_id]
        else:
            pos_min, pos_max = self.position_min, self.position_max
        total = max(1, pos_max - pos_min)
        position = int(pos_min + (pct / 100.0) * total)
        return max(pos_min, min(pos_max, position))

    def _position_to_pct(self, position: int, servo_id: Optional[int] = None) -> float:
        """
        将舵机位置转为百分比(0-100)。使用读取到的 min/max 归一化。
        """
        if servo_id is not None and servo_id in self._per_finger_limits:
            pos_min, pos_max = self._per_finger_limits[servo_id]
        else:
            pos_min, pos_max = self.position_min, self.position_max
        total = max(1, pos_max - pos_min)
        p = max(pos_min, min(pos_max, int(position)))
        return 100.0 * (p - pos_min) / total

    def get_servo_positions(self, gesture_name: str) -> Dict[int, int]:
        """
        根据手势名称获取舵机位置（600-2500，零位600）
        待机/休息类手势限制在 2200 以内，避免手指过紧。
        """
        finger_positions = self.get_finger_positions(gesture_name)
        if not finger_positions:
            return {}
        
        g = (gesture_name or "").lower()
        is_gui_preview = (gesture_name or "").startswith("preview_gui")
        is_idle_or_rest = "idle" in g or g in ("rest", "neutral")
        is_custom = hasattr(self, "custom_finger_gestures") and (
            (gesture_name and gesture_name in self.custom_finger_gestures) or
            ("__with__" in (gesture_name or "") and
             (gesture_name or "").split("__with__")[0].strip() in self.custom_finger_gestures)
        )
        # GUI 预览：0%->配置 min，100%->配置 max，无额外计算
        # 非 GUI：说话时 < 1500；待机/休息 < 1800；JSON 自定义可到 2500
        if is_gui_preview:
            max_pos = None  # 表示使用 per-finger 配置 max
        elif is_idle_or_rest:
            max_pos = 1800
        elif is_custom:
            max_pos = 2500
        else:
            max_pos = 1700

        scale = 1.0
        invert = False
        if not is_gui_preview:
            try:
                scale = float(os.environ.get("FINGER_AMPLITUDE_SCALE", "1.0"))
            except Exception:
                pass
            try:
                invert = str(os.environ.get("FINGER_POSITION_INVERT", "0")).strip() in ("1", "true", "yes")
            except Exception:
                pass

        servo_positions = {}
        for finger_name, percentage in finger_positions.items():
            if finger_name not in self.finger_config:
                continue
            servo_id = self.finger_config[finger_name]
            pct = float(percentage)
            if not is_gui_preview and is_custom and scale != 1.0 and 0 <= pct <= 100:
                pct = min(100.0, pct + (100.0 - pct) * (scale - 1.0))
            position = self._pct_to_position(pct, full_amplitude=is_custom, servo_id=servo_id)
            if not is_gui_preview and invert:
                position = max(self.position_min, min(self.position_max, 3300 - position))
            # GUI 预览：用配置的 min/max 作为边界；否则用 max_pos 等
            if servo_id in self._per_finger_limits:
                cmin, cmax = self._per_finger_limits[servo_id]
                clamp_max = cmax if (is_gui_preview or max_pos is None) else min(cmax, max_pos)
            else:
                cmin, cmax = self.position_min, self.position_max
                clamp_max = self.position_max if (is_gui_preview or max_pos is None) else min(self.position_max, max_pos)
            servo_positions[self.finger_config[finger_name]] = max(cmin, min(clamp_max, position))
        
        return servo_positions
    
    def update_finger_config(self, config: Dict[str, int]):
        """
        更新手指配置
        
        Args:
            config: 手指配置字典 {finger_name: servo_id}
        """
        self.finger_config.update(config)
    
    def set_position_limits(self, min_pos: int, max_pos: int):
        """
        从外部设置手指位置范围（例如根据 ym_info.txt 读到的最小/最大值）。
        """
        try:
            min_pos = int(min_pos)
            max_pos = int(max_pos)
        except Exception:
            return
        if max_pos <= min_pos:
            return
        min_pos = max(0, min(min_pos, 4000))
        max_pos = max(min_pos + 10, min(max_pos, 4095))
        self.position_min = min_pos
        self.position_max = max_pos
        self.position_range = self.position_max - self.position_min
    
    def add_gesture_mapping(self, gesture_name: str, finger_positions: Dict[str, int]):
        """
        添加手势映射
        
        Args:
            gesture_name: 手势名称
            finger_positions: 手指位置字典 {finger_name: angle_deg}
        """
        self.gesture_finger_map[gesture_name] = finger_positions.copy()
        # 与 custom_gestures.json 的 finger_gestures 一致：视为「精确自定义」，
        # 使 get_servo_positions 使用满幅、update_gesture 不再叠加随机漂移。
        # gesture_designer_gui 的 preview_gui_* 依赖此行为。
        if hasattr(self, "custom_finger_gestures"):
            self.custom_finger_gestures.add(gesture_name)

