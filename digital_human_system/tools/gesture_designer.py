#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from typing import List, Dict

# 允许从 digital_human_system 引用内部模块
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SYS_ROOT = os.path.normpath(os.path.join(THIS_DIR, ".."))
if SYS_ROOT not in sys.path:
    sys.path.append(SYS_ROOT)

try:
    from output_interface.ros_publisher import DigitalHumanROSPublisher
    ROS_AVAILABLE = True
except Exception as e:
    print(f"⚠️  无法导入ROS发布器: {e}\n    - 请确认已source ROS环境并在ROS环境中运行本程序\n    - 没有ROS也可先制作/保存手势，稍后再预览")
    ROS_AVAILABLE = False

try:
    from behavior_planner.gesture_policy import GesturePolicy
    POLICY_AVAILABLE = True
except Exception as e:
    print(f"⚠️  无法导入GesturePolicy: {e}\n    - 导入失败不影响保存到JSON，但无法解析内置手势用于预览")
    POLICY_AVAILABLE = False

CUSTOM_JSON_PATH = os.path.join(SYS_ROOT, "custom_gestures.json")
CUSTOM_ACTIONS_PATH = os.path.join(SYS_ROOT, "custom_actions.json")
JOINT_NAMES = [
    'head_yaw', 'head_pitch',
    'left_shoulder_pitch', 'left_shoulder_roll', 'left_shoulder_yaw',
    'left_elbow', 'left_wrist',
    'right_shoulder_pitch', 'right_shoulder_roll', 'right_shoulder_yaw',
    'right_elbow', 'right_wrist'
]

# 全局发布器缓存，避免多次init_node
_PUB = None

def get_publisher():
    global _PUB
    if not ROS_AVAILABLE:
        return None
    if _PUB is None:
        _PUB = DigitalHumanROSPublisher()
    return _PUB


def get_default_angles(policy_obj: "GesturePolicy" = None) -> List[float]:
    if policy_obj is not None and hasattr(policy_obj, 'base_gestures'):
        if 'neutral' in policy_obj.base_gestures:
            return list(policy_obj.base_gestures['neutral'])
        if 'rest' in policy_obj.base_gestures:
            return list(policy_obj.base_gestures['rest'])
    return [0.0] * len(JOINT_NAMES)


def interactive_jointwise_angles(policy_obj: "GesturePolicy" = None, hold_sec: float = 0.8) -> List[float]:
    angles = get_default_angles(policy_obj)
    print("逐关节设置: 回车保持当前值，输入数字设定角度，输入 done 提前结束。")
    for i, name in enumerate(JOINT_NAMES):
        while True:
            curr = angles[i]
            s = input(f"{i}. {name} 当前 {curr:.1f}° -> 新角度: ").strip()
            if s == '':
                break
            if s.lower() in ('done', 'd'):
                return angles
            try:
                val = float(s)
            except Exception:
                print("格式错误，请输入数字或回车跳过")
                continue
            prev = curr
            angles[i] = val
            preview_single(angles, hold_sec)
            confirm = input("接受该关节角度? (Y/n): ").strip().lower()
            if confirm == 'n':
                angles[i] = prev
                continue
            else:
                break
    print("已完成全部关节设置")
    # 结束前复核并支持按编号微调
    while True:
        try:
            print("当前角度:")
            for idx, nm in enumerate(JOINT_NAMES):
                print(f"  {idx}. {nm}: {angles[idx]:.1f}°")
            sel = input("是否修改某个关节? 输入编号或回车/done 完成: ").strip().lower()
            if sel in ('', 'done', 'd'):
                break
            j = int(sel)
            if j < 0 or j >= len(JOINT_NAMES):
                print("编号超出范围")
                continue
            curr = angles[j]
            s2 = input(f"{j}. {JOINT_NAMES[j]} 当前 {curr:.1f}° -> 新角度: ").strip()
            val = float(s2)
        except Exception:
            print("格式错误，请重试")
            continue
        prev = angles[j]
        angles[j] = val
        preview_single(angles, hold_sec)
        confirm = input("接受该关节角度? (Y/n): ").strip().lower()
        if confirm == 'n':
            angles[j] = prev
            continue
    return angles


def load_custom() -> Dict:
    if not os.path.exists(CUSTOM_JSON_PATH):
        return {"base_gestures": {}, "action_sequences": {}}
    try:
        with open(CUSTOM_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"base_gestures": {}, "action_sequences": {}}
        data.setdefault("base_gestures", {})
        data.setdefault("action_sequences", {})
        return data
    except Exception as e:
        print(f"⚠️  读取 {CUSTOM_JSON_PATH} 失败: {e}")
        return {"base_gestures": {}, "action_sequences": {}}


def save_custom(data: Dict):
    try:
        with open(CUSTOM_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {CUSTOM_JSON_PATH}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")


def load_custom_actions_cfg() -> Dict:
    if not os.path.exists(CUSTOM_ACTIONS_PATH):
        return {
            "action_aliases": {},
            "action_regex": {},
            "action_mappings": {},
            "action_durations": {},
            "action_full_min": {},
            "quick_hold_gestures": []
        }
    try:
        with open(CUSTOM_ACTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {
                "action_aliases": {},
                "action_regex": {},
                "action_mappings": {},
                "action_durations": {},
                "action_full_min": {},
                "quick_hold_gestures": []
            }
        data.setdefault("action_aliases", {})
        data.setdefault("action_regex", {})
        data.setdefault("action_mappings", {})
        data.setdefault("action_durations", {})
        data.setdefault("action_full_min", {})
        data.setdefault("quick_hold_gestures", [])
        return data
    except Exception:
        return {
            "action_aliases": {},
            "action_regex": {},
            "action_mappings": {},
            "action_durations": {},
            "action_full_min": {},
            "quick_hold_gestures": []
        }


def save_custom_actions_cfg(data: Dict):
    try:
        with open(CUSTOM_ACTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {CUSTOM_ACTIONS_PATH}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")


def maybe_add_aliases(name: str, angles: List[float], base: Dict[str, List[float]]) -> bool:
    """根据常见中文名称，自动添加策略使用的英文/规范别名，避免触发不到。"""
    alias_map = {
        # 点赞/肌肉
        "点赞": ["thumbs_up"],
        "肌肉": ["muscle_pose"],
        "秀肌肉": ["muscle_pose"],
        "修肌肉": ["muscle_pose"],
        # OK/胜利/停止/过来
        "OK": ["ok_gesture"],
        "Ok": ["ok_gesture"],
        "ok": ["ok_gesture"],
        "好的": ["ok_gesture"],
        "胜利": ["peace_sign"],
        "耶": ["peace_sign"],
        "停止": ["stop_gesture"],
        "停": ["stop_gesture"],
        "过来": ["come_here"],
        "来这里": ["come_here"],
        "招手过来": ["come_here"],
        # 指向/欢迎/鼓掌
        "指向前方": ["point_forward"],
        "前方": ["point_forward"],
        "欢迎": ["welcome_gesture"],
        "鼓掌准备": ["applaud_prepare"],
        "鼓掌": ["applaud_clap"],
        "拍手": ["applaud_clap"],
    }
    added = False
    if name in alias_map:
        for alias in alias_map[name]:
            if alias not in base:
                base[alias] = list(angles)
                print(f"✅ 已添加别名: {alias}")
                added = True
    return added


def update_actions_for_gesture(name: str, angles: List[float]) -> bool:
    cfg = load_custom_actions_cfg()
    aliases: Dict[str, List[str]] = cfg.get("action_aliases", {})
    mappings: Dict[str, str] = cfg.get("action_mappings", {})
    full_min: Dict[str, float] = cfg.get("action_full_min", {})
    quick: List[str] = cfg.get("quick_hold_gestures", [])
    durations: Dict[str, float] = cfg.get("action_durations", {})
    # 依据常见中文名推断动作类型
    name_to_actions = {
        "点赞": ["thumbs_up"],
        "肌肉": ["muscle_pose"],
        "秀肌肉": ["muscle_pose"],
        "修肌肉": ["muscle_pose"],
        "握手": ["handshake"],
        "OK": ["ok"],
        "Ok": ["ok"],
        "ok": ["ok"],
        "好的": ["ok"],
        "胜利": ["peace"],
        "耶": ["peace"],
        "停止": ["stop"],
        "停": ["stop"],
        "过来": ["come_here"],
        "来这里": ["come_here"],
        "招手过来": ["come_here"],
        "指向前方": ["point_forward"],
        "前方": ["point_forward"],
    }
    action_full_defaults = {
        "thumbs_up": 1.5,
        "muscle_pose": 2.0,
        "handshake": 3.4,
        "ok": 1.5,
        "peace": 1.2,
        "stop": 1.2,
        "come_here": 1.4,
        "point_forward": 0.8,
    }
    action_duration_defaults = {
        "thumbs_up": 1.5,
        "muscle_pose": 2.0,
        "handshake": 2.6,
        "ok": 1.5,
        "peace": 1.4,
        "stop": 1.2,
        "come_here": 1.6,
        "point_forward": 0.8,
    }
    quick_actions = set(["thumbs_up", "muscle_pose", "ok", "peace", "stop", "come_here", "point_forward", "handshake"])
    acts = name_to_actions.get(name, [])
    updated = False
    for act in acts:
        # 映射到当前保存的手势名
        if mappings.get(act) != name:
            mappings[act] = name
            updated = True
        # 将该中文名加入动作的提示词
        lst = aliases.setdefault(act, [])
        if name not in lst:
            lst.append(name)
            updated = True
        # 快速保持类
        if act in quick_actions and name not in quick:
            quick.append(name)
            updated = True
        # 完整最小时长
        if act in action_full_defaults and str(act) not in full_min:
            full_min[act] = action_full_defaults[act]
            updated = True
        # 标准时长
        if act in action_duration_defaults and str(act) not in durations:
            durations[act] = action_duration_defaults[act]
            updated = True
    if updated:
        cfg["action_aliases"] = aliases
        cfg["action_mappings"] = mappings
        cfg["action_full_min"] = full_min
        cfg["quick_hold_gestures"] = quick
        cfg["action_durations"] = durations
        save_custom_actions_cfg(cfg)
    return updated


def ensure_action_binding(name: str):
    """若未能自动推断该中文名对应的动作，则引导绑定一个动作以保证可触发。"""
    cfg = load_custom_actions_cfg()
    mappings: Dict[str, str] = cfg.get("action_mappings", {})
    # 若已由某个动作指向该手势名，则无需处理
    if name in mappings.values():
        return
    print("是否为该手势绑定一个触发动作? 常用: thumbs_up/ok/peace/stop/come_here/point_forward/handshake/muscle_pose")
    act = input("输入动作代号(或回车跳过): ").strip()
    if not act:
        return
    aliases: Dict[str, List[str]] = cfg.get("action_aliases", {})
    full_min: Dict[str, float] = cfg.get("action_full_min", {})
    quick: List[str] = cfg.get("quick_hold_gestures", [])
    durations: Dict[str, float] = cfg.get("action_durations", {})
    # 默认参数
    duration_defaults = {
        "thumbs_up": 1.5, "ok": 1.5, "peace": 1.4, "stop": 1.2,
        "come_here": 1.6, "point_forward": 0.8, "handshake": 2.6, "muscle_pose": 2.0,
    }
    full_min_defaults = {
        "thumbs_up": 1.5, "ok": 1.5, "peace": 1.2, "stop": 1.2,
        "come_here": 1.4, "point_forward": 0.8, "handshake": 3.4, "muscle_pose": 2.0,
    }
    quick_actions = set(["thumbs_up", "muscle_pose", "ok", "peace", "stop", "come_here", "point_forward", "handshake"])
    mappings[act] = name
    lst = aliases.setdefault(act, [])
    if name not in lst:
        lst.append(name)
    if act in quick_actions and name not in quick:
        quick.append(name)
    if act in full_min_defaults and str(act) not in full_min:
        full_min[act] = full_min_defaults[act]
    if act in duration_defaults and str(act) not in durations:
        durations[act] = duration_defaults[act]
    cfg["action_mappings"] = mappings
    cfg["action_aliases"] = aliases
    cfg["quick_hold_gestures"] = quick
    cfg["action_full_min"] = full_min
    cfg["action_durations"] = durations
    save_custom_actions_cfg(cfg)


def prompt_angles() -> List[float]:
    print("请输入12个关节角度(度)，用空格分隔。关节顺序为:")
    print("\n".join([f"  {i}. {name}" for i, name in enumerate(JOINT_NAMES)]))
    while True:
        s = input("角度(12个数): ").strip()
        try:
            vals = [float(x) for x in s.replace(',', ' ').split()]
            if len(vals) != 12:
                print("请输入正好12个角度")
                continue
            return vals
        except Exception:
            print("格式错误，请重新输入")


def resolve_angles_by_name(name: str, custom_map: Dict[str, List[float]], policy_obj: "GesturePolicy" = None) -> List[float]:
    if name in custom_map:
        return list(custom_map[name])
    if policy_obj is not None and hasattr(policy_obj, 'base_gestures') and name in policy_obj.base_gestures:
        return list(policy_obj.base_gestures[name])
    raise KeyError(f"未找到手势: {name}")


def preview_single(angles_deg: List[float], hold_sec: float = 1.0):
    pub = get_publisher()
    if pub is None:
        print("⚠️  ROS不可用，跳过预览")
        return
    ok = pub.publish_gesture_sequence([
        {"gesture_name": "custom_preview", "joint_angles": angles_deg, "duration": max(hold_sec, 0.1)}
    ], fps=10, verbose=True)
    if ok:
        print("✅ 预览完成")
    else:
        print("❌ 预览失败")


def preview_sequence(steps: List[Dict], custom_map: Dict[str, List[float]], policy_obj: "GesturePolicy" = None):
    pub = get_publisher()
    if pub is None:
        print("⚠️  ROS不可用，跳过预览")
        return
    seq = []
    for st in steps:
        g = st.get("gesture")
        d = float(st.get("duration", 1.0))
        try:
            angles = resolve_angles_by_name(g, custom_map, policy_obj)
        except Exception as e:
            print(f"❌ 解析手势'{g}'失败: {e}")
            return
        seq.append({"gesture_name": g, "joint_angles": angles, "duration": max(d, 0.1)})
    ok = pub.publish_enhanced_sequence(seq, fps=10, smooth_transitions=True, verbose=True)
    if ok:
        print("✅ 序列预览完成")
    else:
        print("❌ 序列预览失败")


def create_single():
    data = load_custom()
    base = data["base_gestures"]
    name = input("单一手势名称: ").strip()
    if not name:
        print("名称不能为空")
        return
    if name in base:
        ans = input(f"'{name}' 已存在，是否覆盖? (y/N): ").strip().lower()
        if ans != 'y':
            return
    policy_obj = GesturePolicy() if POLICY_AVAILABLE else None
    angles = interactive_jointwise_angles(policy_obj=policy_obj, hold_sec=0.8)
    ans = input("是否最终预览并确认保存? (Y/n): ").strip().lower()
    if ans == 'n':
        print("已取消保存")
        return
    preview_single(angles, 1.0)
    base[name] = angles
    if maybe_add_aliases(name, angles, base):
        pass
    if not update_actions_for_gesture(name, angles):
        ensure_action_binding(name)
    save_custom(data)
    print("提示: GesturePolicy 在下次实例化时会自动加载该手势")


def create_sequence():
    data = load_custom()
    base = data["base_gestures"]
    seqs = data["action_sequences"]

    seq_name = input("序列名称: ").strip()
    if not seq_name:
        print("名称不能为空")
        return
    if seq_name in seqs:
        ans = input(f"'{seq_name}' 已存在，是否覆盖? (y/N): ").strip().lower()
        if ans != 'y':
            return

    steps: List[Dict] = []
    policy_obj = GesturePolicy() if POLICY_AVAILABLE else None

    print("添加步骤: 可输入已有手势名，或输入 'new' 创建新手势，输入 'done' 结束")
    while True:
        g = input("步骤手势名(或 new/done): ").strip()
        if g == 'done':
            break
        if g == 'new':
            new_name = input("新手势名称: ").strip()
            if not new_name:
                print("名称不能为空")
                continue
            if new_name in base:
                print("已存在，直接使用该名称")
            else:
                angles = interactive_jointwise_angles(policy_obj=policy_obj, hold_sec=0.8)
                ans = input("是否最终预览该新手势? (Y/n): ").strip().lower()
                if ans != 'n':
                    preview_single(angles, 1.0)
                base[new_name] = angles
                if maybe_add_aliases(new_name, angles, base):
                    pass
                if not update_actions_for_gesture(new_name, angles):
                    ensure_action_binding(new_name)
                save_custom(data)
            g = new_name
        # 校验手势是否可解析
        try:
            _ = resolve_angles_by_name(g, base, policy_obj)
        except Exception as e:
            print(f"未找到手势'{g}'，请先创建。详情: {e}")
            continue
        # 输入持续时间
        while True:
            ds = input("该步骤持续时间(秒): ").strip()
            try:
                d = float(ds)
                if d <= 0:
                    print("请输入正数")
                    continue
                break
            except Exception:
                print("格式错误，请重新输入")
        steps.append({"gesture": g, "duration": d})
        print(f"已添加步骤: {g} ({d}s)")

    if not steps:
        print("未添加任何步骤")
        return

    # 预览整个序列
    ans = input("预览整个序列? (y/N): ").strip().lower()
    if ans == 'y':
        preview_sequence(steps, base, policy_obj)

    # 是否在结尾添加 rest
    add_rest = input("是否在结尾添加 rest? (y/N): ").strip().lower()
    if add_rest == 'y':
        ds = input("rest 持续时间(秒, 默认0.6): ").strip()
        try:
            rd = float(ds) if ds else 0.6
            if rd <= 0:
                rd = 0.6
        except Exception:
            rd = 0.6
        if steps:
            last = steps[-1]
            if last.get("gesture") in ("rest", "neutral"):
                if float(last.get("duration", 0.0)) < rd:
                    last["duration"] = rd
            else:
                steps.append({"gesture": "rest", "duration": rd})

    # 保存
    seqs[seq_name] = steps
    save_custom(data)
    print("提示: GesturePolicy 在下次实例化时会自动加载该序列")


def list_saved():
    data = load_custom()
    base = data.get("base_gestures", {})
    seqs = data.get("action_sequences", {})
    print(f"自定义手势({len(base)}): {', '.join(sorted(base.keys())) if base else '(空)'}")
    print(f"自定义序列({len(seqs)}): {', '.join(sorted(seqs.keys())) if seqs else '(空)'}")


def delete_saved():
    data = load_custom()
    base = data.get("base_gestures", {})
    seqs = data.get("action_sequences", {})
    which = input("删除类型 (gesture/sequence): ").strip().lower()
    if which not in ("gesture", "sequence"):
        print("无效类型")
        return
    name = input("名称: ").strip()
    if which == "gesture":
        if name in base:
            base.pop(name)
            save_custom(data)
            print("已删除自定义手势")
        else:
            print("未找到该手势")
    else:
        if name in seqs:
            seqs.pop(name)
            save_custom(data)
            print("已删除自定义序列")
        else:
            print("未找到该序列")


def import_to_policy():
    # 由于GesturePolicy会在实例化时载入custom_gestures.json，这里只做一次快速校验
    try:
        gp = GesturePolicy()
        info = gp.get_gesture_info() if hasattr(gp, 'get_gesture_info') else None
        if info:
            print("✅ 已可被策略加载:")
            print(f"  手势总数: {info.get('total_gestures')}")
            print(f"  可用手势样例: {', '.join(list(info.get('available_gestures', [])[:10]))}")
        else:
            print("✅ 自定义文件已保存。下次策略初始化时会加载。")
    except Exception as e:
        print(f"⚠️  导入校验失败，但文件已保存。请在运行策略时检查: {e}")


def main():
    print("\n=== 手势设计器 Gesture Designer ===")
    print(f"自定义文件: {CUSTOM_JSON_PATH}")
    while True:
        print("\n请选择: \n 1) 新建/预览 单一手势\n 2) 新建/预览 序列动作\n 3) 列出已保存\n 4) 删除已保存\n 5) 一键导入到策略(校验)\n 6) 退出")
        choice = input("输入编号: ").strip()
        if choice == '1':
            create_single()
        elif choice == '2':
            create_sequence()
        elif choice == '3':
            list_saved()
        elif choice == '4':
            delete_saved()
        elif choice == '5':
            import_to_policy()
        elif choice == '6':
            print("再见")
            break
        else:
            print("无效选择")


if __name__ == "__main__":
    main()
