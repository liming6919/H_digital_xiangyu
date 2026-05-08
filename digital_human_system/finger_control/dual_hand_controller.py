#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双手手指控制器
Dual Hand Finger Controller - 左右手分别对应不同串口

你的硬件约定：
- 右手：/dev/ttyUSB0
- 左手：/dev/ttyUSB2

舵机ID（每只手相同）：
1=小拇指, 2=无名指, 3=中指, 4=食指, 5=大拇指, 6=虎口收张

位置值安全范围：600(零位/放松) - 2500(握紧/弯曲)
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Callable
import random

from .servo_controller import ServoController, parse_ym_info_text
from .finger_mapper import FingerMapper


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, "0")).strip().lower() in ("1", "true", "yes")


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


class DualHandFingerController:
    """双手手指控制器：一个手势可同时驱动左右手（两路串口）。"""

    def __init__(
        self,
        right_port: str = "/dev/ttyUSB0",
        left_port: str = "/dev/ttyUSB2",
        baudrate: int = 115200,
        enable: bool = True,
        debug: bool = False,
    ):
        self.enable = enable
        self.debug = debug

        self.right_port = right_port
        self.left_port = left_port
        self.baudrate = baudrate

        self.mapper = FingerMapper()

        self.right = ServoController(port=right_port, baudrate=baudrate)
        self.left = ServoController(port=left_port, baudrate=baudrate)
        self.right.set_debug(debug)
        self.left.set_debug(debug)

        # 记录当前状态（每手一份），用于过滤抖动
        self._right_current: Dict[int, int] = {}
        self._left_current: Dict[int, int] = {}

        # 容差（适配600-2500范围）
        self.position_tolerance = 20

        # 左右手独立取反（舵机方向相反时：FINGER_LEFT_INVERT=1 / FINGER_RIGHT_INVERT=1）
        self.invert_left = _env_bool("FINGER_LEFT_INVERT", False)
        self.invert_right = _env_bool("FINGER_RIGHT_INVERT", False)
        # 左右手独立偏移（正=收紧，负=放松，如 FINGER_LEFT_OFFSET=200 收紧左手）
        self.offset_left = _env_int("FINGER_LEFT_OFFSET", 0)
        self.offset_right = _env_int("FINGER_RIGHT_OFFSET", 0)
        if self.invert_left or self.invert_right or self.offset_left or self.offset_right:
            print(f"[手指控制] 左右手调节: 左手 invert={self.invert_left} offset={self.offset_left}, "
                  f"右手 invert={self.invert_right} offset={self.offset_right}")

        # 从 ym_info.txt 读取到的“自然放松”位置（按舵机ID），用于 rest/idle，左右手各一份
        self._neutral_right: Dict[int, int] = {}
        self._neutral_left: Dict[int, int] = {}

        # 从 ym_info.txt 解析到的左右手全局范围（用于额外夹紧）
        self._r_min: Optional[int] = None
        self._r_max: Optional[int] = None
        self._l_min: Optional[int] = None
        self._l_max: Optional[int] = None
        # 每舵机 min/max（用于归一化），{servo_id: (min, max)}
        self._min_max_map: Dict[int, tuple] = {}

        if not self.enable:
            print("[手指控制] 已禁用（双手）")
            return

        # 连接两路串口（任一失败都不直接抛异常，避免影响上层）
        ok_r = self.right.connect()
        ok_l = self.left.connect()
        if ok_r:
            print(f"[手指控制] 右手串口连接成功: {right_port} @ {baudrate}")
        else:
            print(f"[手指控制] 警告: 右手串口连接失败: {right_port}")
        if ok_l:
            print(f"[手指控制] 左手串口连接成功: {left_port} @ {baudrate}")
        else:
            print(f"[手指控制] 警告: 左手串口连接失败: {left_port}")

        # 从舵机串口读取 ym_info.txt（或本地文件）获取手指最小/最大值，并同步到 Mapper 与串口控制器
        self._load_limits_from_ym_info()

    def _load_limits_from_ym_info(self):
        """
        获取舵机最小/最大位置，优先从「手指串口」读取 ym_info.txt，其次才读本地文件。
        获取到范围后，统一设置到 FingerMapper 和 两路 ServoController。
        """
        import re

        # 为左右手分别记录范围与自然位
        r_min: Optional[int] = None
        r_max: Optional[int] = None
        l_min: Optional[int] = None
        l_max: Optional[int] = None

        # 1) 优先：通过「手指串口」读取 ym_info.txt
        for ctrl in (self.right, self.left):
            try:
                info = ctrl.read_ym_info_limits()
            except Exception:
                info = None
            if not info or "min" not in info or "max" not in info:
                continue
            min_pos = int(info["min"])
            max_pos = int(info["max"])
            if max_pos <= min_pos:
                continue
            side = str(info.get("side") or "").upper()
            neutral = info.get("neutral")
            min_map = info.get("min_map") or {}
            max_map = info.get("max_map") or {}

            def _merge_min_max(m: Dict[int, tuple], mm: dict, mx: dict) -> None:
                for sid in set(mm.keys()) | set(mx.keys()):
                    if 1 <= int(sid) <= 6:
                        mn = int(mm.get(sid, min_pos))
                        mxv = int(mx.get(sid, max_pos))
                        if mxv > mn:
                            m[int(sid)] = (mn, mxv)

            if side == "R":
                r_min, r_max = min_pos, max_pos
                if isinstance(neutral, dict):
                    try:
                        self._neutral_right = {
                            int(k): int(v) for k, v in neutral.items() if 1 <= int(k) <= 6
                        }
                    except Exception:
                        self._neutral_right = {}
                _merge_min_max(self._min_max_map, min_map, max_map)
            elif side == "L":
                l_min, l_max = min_pos, max_pos
                if isinstance(neutral, dict):
                    try:
                        self._neutral_left = {
                            int(k): int(v) for k, v in neutral.items() if 1 <= int(k) <= 6
                        }
                    except Exception:
                        self._neutral_left = {}
                _merge_min_max(self._min_max_map, min_map, max_map)
            else:
                # 未标注 L/R 时，按控制器归属分配
                if ctrl is self.right:
                    r_min, r_max = min_pos, max_pos
                    if isinstance(neutral, dict):
                        try:
                            self._neutral_right = {
                                int(k): int(v) for k, v in neutral.items() if 1 <= int(k) <= 6
                            }
                        except Exception:
                            self._neutral_right = {}
                    _merge_min_max(self._min_max_map, min_map, max_map)
                else:
                    l_min, l_max = min_pos, max_pos
                    if isinstance(neutral, dict):
                        try:
                            self._neutral_left = {
                                int(k): int(v) for k, v in neutral.items() if 1 <= int(k) <= 6
                            }
                        except Exception:
                            self._neutral_left = {}
                    _merge_min_max(self._min_max_map, min_map, max_map)

        # 2) 兜底：如果串口没读到，再按 3 行格式解析本地 ym_info.txt（第二行=最大值，第三行=最小值）
        if r_min is None and l_min is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = []
            env_path = os.environ.get("FINGER_INFO_PATH")
            if env_path:
                candidates.append(env_path)
            candidates.append(os.path.join(base_dir, "ym_info.txt"))
            candidates.append(os.path.join(os.path.dirname(base_dir), "ym_info.txt"))

            path = None
            for p in candidates:
                if p and os.path.exists(p):
                    path = p
                    break
            if path:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    info = parse_ym_info_text(text)
                    if info and "min" in info and "max" in info:
                        shared_min = int(info["min"])
                        shared_max = int(info["max"])
                        r_min = r_min or shared_min
                        r_max = r_max or shared_max
                        l_min = l_min or shared_min
                        l_max = l_max or shared_max
                        min_map = info.get("min_map") or {}
                        max_map = info.get("max_map") or {}

                        def _merge_min_max(m: Dict[int, tuple], mm: dict, mx: dict) -> None:
                            for sid in set(mm.keys()) | set(mx.keys()):
                                if 1 <= int(sid) <= 6:
                                    mn = int(mm.get(sid, shared_min))
                                    mxv = int(mx.get(sid, shared_max))
                                    if mxv > mn:
                                        m[int(sid)] = (mn, mxv)

                        _merge_min_max(self._min_max_map, min_map, max_map)
                        if isinstance(info.get("neutral"), dict):
                            try:
                                n = {int(k): int(v) for k, v in info["neutral"].items() if 1 <= int(k) <= 6}
                                if not self._neutral_right and not self._neutral_left:
                                    self._neutral_right = self._neutral_left = n
                            except Exception:
                                pass
                        print(f"[手指控制] 从本地 ym_info 解析: min={shared_min}, max={shared_max}, {len(self._min_max_map)} 个舵机范围")
                    else:
                        # 无法按 3 行解析时，用正则提取数字（可能范围偏窄）
                        nums = [int(x) for x in re.findall(r"\d{3,4}", text)]
                        nums = [n for n in nums if 200 <= n <= 4095]
                        if len(nums) >= 2:
                            shared_min = min(nums)
                            shared_max = max(nums)
                            if shared_max > shared_min:
                                r_min = r_min or shared_min
                                r_max = r_max or shared_max
                                l_min = l_min or shared_min
                                l_max = l_max or shared_max
                                print(f"[手指控制] 从本地文件正则解析: min={shared_min}, max={shared_max} (无 per-finger)")
                except Exception as e:
                    print(f"[手指控制] 读取本地 ym_info 失败: {e}")

        # 如果仍没有有效范围，直接返回
        if r_min is None and l_min is None:
            return

        # 为 mapper 选择一个全局范围（左右手范围的并集）
        mins = [v for v in (r_min, l_min) if v is not None]
        maxs = [v for v in (r_max, l_max) if v is not None]
        g_min = min(mins)
        g_max = max(maxs)
        if g_max <= g_min:
            return

        self.mapper.set_position_limits(g_min, g_max)
        # 使用读取到的每舵机 min/max 做归一化（配置文件：第二行=最大值，第三行=最小值）
        if self._min_max_map:
            self.mapper.set_per_finger_limits(self._min_max_map)
            print(f"[手指控制] 已按 ym_info 每指 min/max 归一化: {len(self._min_max_map)} 个舵机 (GUI 100%%->配置最大值)")
        else:
            print(f"[手指控制] 无 per-finger 配置，使用全局 {g_min}-{g_max} (GUI 100%%->{g_max})")
        # 右手控制器范围
        if r_min is not None and r_max is not None and r_max > r_min:
            self.right.set_position_limits(r_min, r_max)
            self._r_min, self._r_max = r_min, r_max
            print(f"[手指控制] 右手 ym_info 范围: min={r_min}, max={r_max}")
        # 左手控制器范围
        if l_min is not None and l_max is not None and l_max > l_min:
            self.left.set_position_limits(l_min, l_max)
            self._l_min, self._l_max = l_min, l_max
            print(f"[手指控制] 左手 ym_info 范围: min={l_min}, max={l_max}")
        if self._neutral_right:
            print(f"[手指控制] 右手自然放松手指位置: {self._neutral_right}")
        if self._neutral_left:
            print(f"[手指控制] 左手自然放松手指位置: {self._neutral_left}")

    def get_neutral_percentages(self, hand: str = "both") -> Dict[str, float]:
        """
        返回每个手指的自然放松位置对应的归一化百分比(0-100)。
        基于 ym_info 的 neutral 位，用于 GUI「归零」按钮。
        hand: "left" | "right" | "both"（both 时优先用左手，右手兜底）
        """
        neutral = {}
        if hand == "left":
            neutral = self._neutral_left
        elif hand == "right":
            neutral = self._neutral_right
        else:
            neutral = self._neutral_left or self._neutral_right
        if not neutral:
            return {}
        # finger_config: finger_name -> servo_id
        result: Dict[str, float] = {}
        for fname, sid in self.mapper.finger_config.items():
            if sid in neutral:
                try:
                    pct = self.mapper._position_to_pct(int(neutral[sid]), servo_id=int(sid))
                    result[fname] = max(0.0, min(100.0, pct))
                except Exception:
                    result[fname] = 40.0
        return result

    def _hands_for_gesture(self, gesture_name: str) -> str:
        """根据手势名决定驱动哪只手：'left' | 'right' | 'both'"""
        # 优先使用 finger_gestures 中明确配置的 hand 字段（左手/右手/双手）
        override = getattr(self.mapper, "gesture_hand_overrides", {})
        if gesture_name and gesture_name in override:
            return override[gesture_name]

        g = (gesture_name or "").lower()
        # 明确双手
        if "both" in g or "双手" in g:
            return "both"
        # 明确左右：名称含「左」且不含「右」-> 左手；含「右」且不含「左」-> 右手
        left_hit = ("left" in g) or ("左" in g) or ("_l" in g)
        right_hit = ("right" in g) or ("右" in g) or ("_r" in g)
        if left_hit and not right_hit:
            return "left"
        if right_hit and not left_hit:
            return "right"
        # 默认：双手
        return "both"

    def _filter_small_changes(self, target: Dict[int, int], current: Dict[int, int]) -> Dict[int, int]:
        """过滤小变化，避免抖动/刷串口。"""
        out: Dict[int, int] = {}
        for sid, pos in target.items():
            last = current.get(sid)
            if last is None or abs(int(pos) - int(last)) >= self.position_tolerance:
                out[sid] = int(pos)
        return out

    def _apply_hand_transform(self, positions: Dict[int, int], invert: bool, offset: int) -> Dict[int, int]:
        """对手指位置做单手变换：取反（舵机方向相反）+ 偏移（正=收紧，负=放松）。"""
        if not positions:
            return positions
        out: Dict[int, int] = {}
        for sid, pos in positions.items():
            p = int(pos)
            if invert:
                p = 3300 - p
            p = p + offset
            out[sid] = max(600, min(2500, p))
        return out

    def update_gesture(self, gesture_name: str, duration: float = 0.5, transition_time_ms: Optional[int] = None):
        """根据手势名更新手指动作。"""
        if not self.enable:
            return

        g_lower = (gesture_name or "").lower()
        # 说话/待机时手指不要握太紧：限制到 2200 以内（自定义 finger_gestures 仍可到 2500）
        is_idle_or_rest = ("idle" in g_lower) or (g_lower in ("rest", "neutral"))
        is_speaking_semantic = ("both_hands" in g_lower) or any(
            k in g_lower for k in ("explain", "emphasize", "present", "welcome", "wave", "listen", "micro")
        )
        # 待机/回中更放松：≤2000；说话语义手势：≤2200；自定义 finger_gestures：仍可到 2500
        if is_idle_or_rest:
            max_pos_runtime = 1500
        elif is_speaking_semantic:
            max_pos_runtime = 1500
        else:
            max_pos_runtime = 2500

        # 1) 先根据语义或自定义配置获得一个“基础手指姿态”
        base_positions = self.mapper.get_servo_positions(gesture_name)

        # 如果映射表里也没有，就以中位 1500 作为基础
        if not base_positions:
            base_positions = {sid: 1500 for sid in range(1, 7)}  # 1~5手指, 6虎口

        def _neutral_jitter(neutral: Dict[int, int], clamp_max: int) -> Dict[int, int]:
            """以自然位为中心做±50抖动（每只手独立）。"""
            src = neutral or {sid: 1500 for sid in range(1, 7)}
            out: Dict[int, int] = {}
            for sid, base in src.items():
                try:
                    center = int(base)
                except Exception:
                    center = 1500
                offset = random.randint(-50, 50)
                target = center + offset
                out[int(sid)] = max(600, min(int(clamp_max), int(target)))
            return out

        # 2) 生成最终舵机位置：
        # - 对于来自 custom_gestures.json 的自定义 finger_gestures，严格按 JSON 百分比映射，不再叠加随机抖动；
        # - 对于“待机/说话随机小动作”，严格以 ym_info 里的自然姿态为中心做 ±50 范围轻微变化；
        # - 其它语义默认/内置手型，继续叠加小幅随机扰动，让手指“略微动起来”。
        servo_positions: Dict[int, int] = {}
        lookup_name = gesture_name
        if "__with__" in (gesture_name or ""):
            lookup_name = (gesture_name or "").split("__with__")[0].strip()
        is_custom_finger_pose = hasattr(self.mapper, "custom_finger_gestures") and (
            (lookup_name and lookup_name in self.mapper.custom_finger_gestures) or
            (gesture_name and gesture_name in self.mapper.custom_finger_gestures)
        )

        if is_custom_finger_pose:
            # 自定义 finger_gestures：严格按 JSON 百分比映射，不做额外抖动
            for sid, base in base_positions.items():
                try:
                    target = int(base)
                except Exception:
                    target = 1500
                servo_positions[sid] = max(600, min(2500, target))
        else:
            # 其它语义手势：以映射表手型为基础，叠加较大随机幅度
            drift = 150
            for sid, base in base_positions.items():
                base_clamped = max(600, min(2500, int(base)))
                offset = random.randint(-drift, drift)
                servo_positions[sid] = max(600, min(max_pos_runtime, base_clamped + offset))

        hands = self._hands_for_gesture(gesture_name)

        # 说话/待机：生成一个共用比例偏移（约±2.5%），用于“非待机/非说话”的语义手势过渡时的微调
        _idle_jitter_proportion = None
        if (not is_idle_or_rest) and (not is_speaking_semantic):
            _idle_jitter_proportion = random.uniform(-0.025, 0.025)  # 同一比例，保证各指动作一致

        # 过渡时间：跟随上层节奏，但限制在安全区间
        if transition_time_ms is None:
            transition_time_ms = int(float(duration) * 1000)
            transition_time_ms = max(200, min(2000, transition_time_ms))

        if self.debug:
            print(f"[手指控制][双手] gesture='{gesture_name}', hands='{hands}', "
                  f"duration={duration:.2f}s, T={transition_time_ms}ms, positions={servo_positions}")
        # 调试：点赞等关键手势时打印实际发送值（DH_VERBOSE=1）
        _dbg = (gesture_name in ("点赞", "thumbs_up", "左点赞", "right_thumbs_up") and
                __import__("os").environ.get("DH_VERBOSE") == "1")
        if _dbg and servo_positions:
            print(f"[手指调试] 点赞 gesture='{gesture_name}' is_custom={is_custom_finger_pose} "
                  f"positions={servo_positions}")

        if hands in ("right", "both"):
            # 右手非自定义姿态的额外偏置（默认 0，保持左右一致）。
            # 如需让右手更松/更紧，可通过环境变量 FINGER_RIGHT_NONCUSTOM_BIAS 调整；
            # 该偏置仅对“非自定义手型”生效，避免把自定义 2500 拉低。
            try:
                noncustom_bias_r = int(os.environ.get("FINGER_RIGHT_NONCUSTOM_BIAS", "0"))
            except Exception:
                noncustom_bias_r = 0
            r_offset = self.offset_right + (0 if is_custom_finger_pose else noncustom_bias_r)
            base_r = _neutral_jitter(self._neutral_right, max_pos_runtime) if (is_idle_or_rest or is_speaking_semantic) else servo_positions
            # 仅对“非待机/非说话”的语义手势做基于自然位的比例微调；自定义/GUI 预览直接用 mapper 输出
            if (not is_idle_or_rest) and (not is_speaking_semantic) and (not is_custom_finger_pose) and _idle_jitter_proportion is not None:
                neutral = self._neutral_right or self._neutral_left
                if neutral:
                    min_lim = self._r_min if self._r_min is not None else 600
                    max_lim = self._r_max if self._r_max is not None else 2500
                    finger_range = max(1, max_lim - min_lim)
                    base_r = {}
                    for sid, base in neutral.items():
                        nv = int(base)
                        # 该指在配置范围内的比例 [0,1]
                        proportion = (nv - min_lim) / finger_range
                        proportion = max(0.0, min(1.0, proportion + _idle_jitter_proportion))
                        val = int(round(min_lim + proportion * finger_range))
                        base_r[sid] = max(min_lim, min(max_lim, val))
            r_positions = self._apply_hand_transform(base_r, self.invert_right, r_offset)
            # GUI 实时预览：每次都要下发，避免容差过滤导致「拖滑块没反应」
            _gui_preview = (gesture_name or "").startswith("preview_gui")
            r_target = r_positions if _gui_preview else self._filter_small_changes(
                r_positions, self._right_current
            )
            if r_target:
                if _gui_preview and os.environ.get("FINGER_DEBUG") == "1":
                    print(f"[手指调试] GUI 预览右手发送: {r_target}")
                self.right.set_multiple_servos(r_target, transition_time_ms)
                self._right_current.update(r_target)

        if hands in ("left", "both"):
            base_l = _neutral_jitter(self._neutral_left, max_pos_runtime) if (is_idle_or_rest or is_speaking_semantic) else servo_positions
            # 仅对“非待机/非说话”的语义手势做基于自然位的比例微调；自定义/GUI 预览直接用 mapper 输出
            if (not is_idle_or_rest) and (not is_speaking_semantic) and (not is_custom_finger_pose) and _idle_jitter_proportion is not None:
                neutral = self._neutral_left or self._neutral_right
                if neutral:
                    min_lim = self._l_min if self._l_min is not None else 600
                    max_lim = self._l_max if self._l_max is not None else 2500
                    finger_range = max(1, max_lim - min_lim)
                    base_l = {}
                    for sid, base in neutral.items():
                        nv = int(base)
                        proportion = (nv - min_lim) / finger_range
                        proportion = max(0.0, min(1.0, proportion + _idle_jitter_proportion))
                        val = int(round(min_lim + proportion * finger_range))
                        base_l[sid] = max(min_lim, min(max_lim, val))
            l_positions = self._apply_hand_transform(base_l, self.invert_left, self.offset_left)
            _gui_preview = (gesture_name or "").startswith("preview_gui")
            l_target = l_positions if _gui_preview else self._filter_small_changes(
                l_positions, self._left_current
            )
            if l_target:
                if _gui_preview and os.environ.get("FINGER_DEBUG") == "1":
                    print(f"[手指调试] GUI 预览左手发送: {l_target}")
                self.left.set_multiple_servos(l_target, transition_time_ms)
                self._left_current.update(l_target)

    def update_gesture_sequence(
        self,
        gesture_sequence: List[Dict],
        sleep_between: bool = False,
        should_stop: Optional[Callable[[], bool]] = None,
    ):
        """
        序列更新：逐个手势更新手指。

        Args:
            gesture_sequence: 列表元素包含 gesture_name/gesture 与 duration(秒)
            sleep_between: True 时，严格按每步 duration 延时，便于手指跟随手臂分段时序
            should_stop: 可选中断函数；返回 True 则提前停止序列
        """
        if not self.enable:
            return
        for g in gesture_sequence or []:
            if should_stop is not None:
                try:
                    if should_stop():
                        return
                except Exception:
                    # 中断检查失败时仍继续执行，避免手指序列完全失效
                    pass
            name = g.get("gesture_name") or g.get("gesture", "rest")
            try:
                duration = float(g.get("duration", 0.5))
            except Exception:
                duration = 0.5
            self.update_gesture(name, duration)
            if sleep_between:
                try:
                    time.sleep(max(0.0, duration))
                except Exception:
                    pass

    def disconnect(self):
        if self.enable:
            self.right.disconnect()
            self.left.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


