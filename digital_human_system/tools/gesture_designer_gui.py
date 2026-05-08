#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势设计器 GUI版本
使用滑块调整关节角度，实时预览，一键保存到JSON
"""

import os
import sys
import json
import time
import threading
from typing import List, Dict, Optional
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# 允许从 digital_human_system 引用内部模块
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SYS_ROOT = os.path.normpath(os.path.join(THIS_DIR, ".."))
if SYS_ROOT not in sys.path:
    sys.path.append(SYS_ROOT)

try:
    from output_interface.ros_publisher import DigitalHumanROSPublisher
    ROS_AVAILABLE = True
except Exception as e:
    print(f"⚠️  无法导入ROS发布器: {e}\n    - 请确认已source ROS环境\n    - 没有ROS也可制作/保存手势，稍后再预览")
    ROS_AVAILABLE = False

try:
    from behavior_planner.gesture_policy import GesturePolicy
    POLICY_AVAILABLE = True
except Exception as e:
    print(f"⚠️  无法导入GesturePolicy: {e}")
    POLICY_AVAILABLE = False

try:
    from finger_control.dual_hand_controller import DualHandFingerController
    FINGER_CTRL_AVAILABLE = True
except Exception as e:
    print(f"⚠️  无法导入手指控制模块: {e}\n    - 手指硬件预览将不可用")
    FINGER_CTRL_AVAILABLE = False

CUSTOM_JSON_PATH = os.path.join(SYS_ROOT, "custom_gestures.json")
CUSTOM_ACTIONS_PATH = os.path.join(SYS_ROOT, "custom_actions.json")

JOINT_NAMES = [
    'head_yaw', 'head_pitch',
    'left_shoulder_pitch', 'left_shoulder_roll', 'left_shoulder_yaw',
    'left_elbow', 'left_wrist',
    'right_shoulder_pitch', 'right_shoulder_roll', 'right_shoulder_yaw',
    'right_elbow', 'right_wrist'
]

# 关节角度范围（度）
JOINT_RANGES = {
    'head_yaw': (-90, 90),
    'head_pitch': (-45, 45),
    'left_shoulder_pitch': (-180, 180),
    'left_shoulder_roll': (-90, 90),
    'left_shoulder_yaw': (-90, 90),
    'left_elbow': (0, 180),
    'left_wrist': (-90, 90),
    'right_shoulder_pitch': (-180, 180),
    'right_shoulder_roll': (-90, 90),
    'right_shoulder_yaw': (-90, 90),
    'right_elbow': (0, 180),
    'right_wrist': (-90, 90),
}

# 手指名称（与 finger_control.FingerMapper 中的 finger_config 对应）
FINGER_NAMES = [
    'thumb',      # 大拇指
    'index',      # 食指
    'middle',     # 中指
    'ring',       # 无名指
    'pinky',      # 小拇指
    'thumb_gap',  # 虎口开合
]

# 手指默认百分比（0=完全伸直/放松，100=完全握紧），尽量对齐 FingerMapper 中的 rest/neutral 配置
FINGER_DEFAULT_PERCENT = {
    'thumb': 30.0,
    'index': 40.0,
    'middle': 40.0,
    'ring': 40.0,
    'pinky': 40.0,
    'thumb_gap': 50.0,
}


class GestureDesignerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("动作编辑器 - Gesture Designer")
        self.root.geometry("1024x820")
        self.root.minsize(920, 680)

        # ttk 样式（尽量现代一点）
        self.style = ttk.Style(self.root)
        try:
            # clam 在 Linux 上相对更干净
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("Title.TLabel", font=("Arial", 16, "bold"))
        self.style.configure("Hint.TLabel", foreground="#666666")
        self.style.configure("Section.TLabel", font=("Arial", 11, "bold"))
        self.style.configure("Accent.TButton", font=("Arial", 11, "bold"))
        
        # ROS发布器（延迟初始化）
        self.ros_publisher = None
        self.preview_enabled = False

        # 手指控制器（可选，用于硬件预览）
        self.finger_controller: Optional["DualHandFingerController"] = None
        self.finger_preview_enabled: bool = False
        # 从 ym_info 自然位算出的归一化百分比，用于「归零」（0%=min，100%=max）
        self._finger_neutral_percent: Dict[str, float] = {}
        
        # 当前角度值（度）
        self.current_angles = [0.0] * len(JOINT_NAMES)
        
        # 滑块变量和控件
        self.slider_vars = []
        self.slider_widgets = []
        self.value_labels = []

        # 手指滑块变量（百分比 0-100）
        self.finger_vars: Dict[str, tk.DoubleVar] = {}
        self.finger_value_labels: Dict[str, ttk.Label] = {}

        # 手指预览模式：left / right / both
        self.finger_preview_mode = tk.StringVar(value="both")

        # 实时预览节流/去抖（避免拖动时刷爆ROS）
        self._preview_job = None
        self.preview_debounce_ms = 180
        self.preview_min_interval_s = 0.25
        self._last_preview_ts = 0.0

        # 输出日志：记录最近执行/预览过的12维角度
        self._angle_log_lines: List[str] = []
        self.max_angle_log_lines = 200

        # 控件变量
        self.gesture_name_var = tk.StringVar(value="")
        self.saved_gestures_var = tk.StringVar(value="")
        
        # 创建UI
        self.create_ui()
        
        # 尝试初始化ROS（后台线程，不阻塞UI）
        if ROS_AVAILABLE:
            threading.Thread(target=self.init_ros, daemon=True).start()

        # 尝试初始化手指控制器（后台线程，不阻塞UI）
        if FINGER_CTRL_AVAILABLE:
            threading.Thread(target=self.init_fingers, daemon=True).start()
    
    def init_ros(self):
        """后台初始化ROS发布器"""
        try:
            self.ros_publisher = DigitalHumanROSPublisher()
            self.ros_publisher.initialize_ros()
            self.root.after(0, lambda: self.status_label.config(
                text="状态: ROS已连接，可实时预览", fg="green"
            ))
            self.preview_enabled = True
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(
                text=f"状态: ROS未连接 ({str(e)[:50]})，可保存但无法预览", fg="orange"
            ))
    
    def init_fingers(self):
        """后台初始化手指控制器（双手舵机），用于在GUI里直接预览手指动作。"""
        try:
            # 端口和波特率默认与 main.py 保持一致，也允许通过环境变量覆盖
            right_port = os.environ.get("DH_RIGHT_FINGER_PORT", "/dev/ttyUSB0")
            left_port = os.environ.get("DH_LEFT_FINGER_PORT", "/dev/ttyUSB2")
            baudrate = int(os.environ.get("DH_FINGER_BAUD", "115200"))
            debug = bool(int(os.environ.get("DH_FINGER_DEBUG", "1")))

            self.finger_controller = DualHandFingerController(
                right_port=right_port,
                left_port=left_port,
                baudrate=baudrate,
                enable=True,
                debug=debug,
            )
            self.finger_preview_enabled = True
            # 从 natural 位更新「归零」用的归一化百分比
            try:
                neut = self.finger_controller.get_neutral_percentages(hand="both")
                if neut:
                    self.root.after(0, lambda: self._update_finger_neutral_defaults(neut))
            except Exception:
                pass
            print(f"[手指预览] 已连接双手舵机: right={right_port}, left={left_port}")
        except Exception as e:
            print(f"⚠️  手指控制初始化失败: {e}")
            self.finger_controller = None
            self.finger_preview_enabled = False

    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        # 顶部标题区
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="手势设计器", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="滑块调角度 → 预览 → 一键保存（自动可触发）", style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        # 内容区：左右两栏
        body = ttk.Panedwindow(main, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew")

        # 左侧：关节滑块（人形布局）
        left = ttk.Frame(body)
        body.add(left, weight=5)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        sliders_box = ttk.Labelframe(left, text="关节角度（°）- 人形布局", padding=10)
        sliders_box.grid(row=0, column=0, sticky="nsew")
        sliders_box.columnconfigure(0, weight=1)
        sliders_box.rowconfigure(0, weight=1)

        # 人形布局网格（不需要滚动，12个关节一屏放下）
        humanoid = ttk.Frame(sliders_box)
        humanoid.grid(row=0, column=0, sticky="nsew")
        for c in range(6):
            humanoid.columnconfigure(c, weight=1, uniform="hum")
        # 7行：更清晰地满足“roll 在 yaw 上面”的纵向顺序
        for r in range(7):
            humanoid.rowconfigure(r, weight=1, uniform="hum")

        # 可视化摆放：左右臂在两侧，头在上方中间
        # 网格: 6列x7行
        # 左臂: col0-1，头: col2-3，右臂: col4-5
        # 你指定顺序：
        # - 头部：head_pitch 在上，head_yaw 在下
        # - 左臂/右臂：pitch → roll → yaw → elbow → wrist（从上到下）
        pos = {
            # head (center)
            1: (0, 2),  # head_pitch (top)
            0: (1, 2),  # head_yaw (below)
            # left arm (left side)
            2: (2, 0),  # left_shoulder_pitch
            3: (3, 0),  # left_shoulder_roll
            4: (4, 0),  # left_shoulder_yaw  (yaw below roll)
            5: (5, 0),  # left_elbow
            6: (6, 0),  # left_wrist
            # right arm (right side)
            7: (2, 4),   # right_shoulder_pitch
            8: (3, 4),   # right_shoulder_roll
            9: (4, 4),   # right_shoulder_yaw (yaw below roll)
            10: (5, 4),  # right_elbow
            11: (6, 4),  # right_wrist
        }
        # 关节卡片占用两列：为了“人形布局”视觉一致（避免 roll 比 yaw 短一截）
        # 这里直接让全部12个关节都用宽卡片（两列）。
        wide = set(range(len(JOINT_NAMES)))

        for idx, joint_name in enumerate(JOINT_NAMES):
            if idx not in pos:
                continue
            r, c = pos[idx]
            colspan = 2 if idx in wide else 1
            self.create_joint_tile(humanoid, index=idx, joint_name=joint_name, row=r, col=c, colspan=colspan)

        # 中间“躯干”区域：填充在两侧手臂之间，用于显示关节角度数据
        # 宽度与 head_yaw/head_pitch 等关节卡片一致（占两列）
        torso = ttk.Frame(humanoid, padding=4)
        torso.grid(row=2, column=2, rowspan=5, columnspan=2, sticky="nsew", padx=4, pady=6)
        torso.columnconfigure(0, weight=1)
        torso.rowconfigure(0, weight=1)

        torso_box = tk.Frame(
            torso,
            highlightthickness=1,
            highlightbackground="#cccccc",
            background="#ffffff",
        )
        torso_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        torso_box.columnconfigure(0, weight=1)
        torso_box.rowconfigure(1, weight=1)

        # 标题
        title_label = tk.Label(
            torso_box,
            text="关节角度数据",
            background="#ffffff",
            foreground="#333333",
            font=("Arial", 9, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="ew", pady=(2, 4))

        # 角度数据显示区域（填满中间白色区域，清晰显示）
        self.torso_angle_text = tk.Text(
            torso_box,
            height=8,
            wrap="word",
            font=("Courier", 8),
            background="#ffffff",
            foreground="#000000",
            relief="flat",
            borderwidth=0,
            padx=4,
            pady=4,
            width=20,  # 限制宽度，避免挤压左右滑块
        )
        self.torso_angle_text.grid(row=1, column=0, sticky="nsew")
        self.torso_angle_text.configure(state="disabled")

        # 按钮区域：复制/清空数据，放在数据框下方
        torso_btns = ttk.Frame(torso_box)
        torso_btns.grid(row=2, column=0, sticky="ew", pady=(4, 2))
        ttk.Button(torso_btns, text="复制数据", command=self._copy_torso_data).pack(side="left", padx=(0, 4))
        ttk.Button(torso_btns, text="清空", command=self._clear_torso_data).pack(side="left")

        # 初始化显示
        self.update_torso_angle_display()

        # 右侧：控制面板
        right = ttk.Frame(body)
        body.add(right, weight=2)
        right.columnconfigure(0, weight=1)

        ctrl = ttk.Labelframe(right, text="控制", padding=10)
        ctrl.grid(row=0, column=0, sticky="nsew")
        ctrl.columnconfigure(0, weight=1)

        # 状态栏（这里用 tk.Label，支持 fg）
        self.status_label = tk.Label(ctrl, text="状态: 初始化中...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # 手势名输入
        name_row = ttk.Frame(ctrl)
        name_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        name_row.columnconfigure(1, weight=1)
        ttk.Label(name_row, text="手势名称:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        name_entry = ttk.Entry(name_row, textvariable=self.gesture_name_var)
        name_entry.grid(row=0, column=1, sticky="ew")

        # 单一动作保存时的动作时间（秒），保存时写入 action_durations
        ttk.Label(name_row, text="动作时间(s):").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.single_gesture_duration_var = tk.StringVar(value="1.5")
        ttk.Entry(name_row, textvariable=self.single_gesture_duration_var, width=6).grid(row=0, column=3, padx=2)

        # 已保存手势下拉
        saved_row = ttk.Frame(ctrl)
        saved_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        saved_row.columnconfigure(1, weight=1)
        ttk.Label(saved_row, text="已保存:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.saved_combo = ttk.Combobox(saved_row, textvariable=self.saved_gestures_var, state="readonly", values=[])
        self.saved_combo.grid(row=0, column=1, sticky="ew")
        self.saved_combo.bind("<<ComboboxSelected>>", lambda _: self._load_selected())
        ttk.Button(saved_row, text="刷新", width=6, command=self._refresh_saved_gestures).grid(row=0, column=2, padx=(8, 0))

        # 按钮区
        btns = ttk.Frame(ctrl)
        btns.grid(row=3, column=0, sticky="ew")
        for i in range(2):
            btns.columnconfigure(i, weight=1)

        ttk.Button(btns, text="加载选中", command=self._load_selected).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        ttk.Button(btns, text="归零", command=self.reset_all).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))

        self.preview_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="实时预览（拖动时自动预览，已节流）", variable=self.preview_var).grid(row=4, column=0, sticky="w", pady=(6, 6))

        ttk.Button(ctrl, text="手动预览", command=self.preview_current).grid(row=5, column=0, sticky="ew", pady=(0, 4))

        # 手指预览手选择
        finger_side_row = ttk.Frame(ctrl)
        finger_side_row.grid(row=6, column=0, sticky="w", pady=(0, 6))
        ttk.Label(finger_side_row, text="手指预览手:").pack(side="left")
        ttk.Radiobutton(
            finger_side_row,
            text="左手",
            value="left",
            variable=self.finger_preview_mode,
        ).pack(side="left", padx=(4, 0))
        ttk.Radiobutton(
            finger_side_row,
            text="右手",
            value="right",
            variable=self.finger_preview_mode,
        ).pack(side="left", padx=(4, 0))
        ttk.Radiobutton(
            finger_side_row,
            text="双手",
            value="both",
            variable=self.finger_preview_mode,
        ).pack(side="left", padx=(4, 0))

        ttk.Button(ctrl, text="💾 保存（并自动可触发）", command=self._save_from_entry, style="Accent.TButton").grid(row=7, column=0, sticky="ew", pady=(4, 2))
        ttk.Label(ctrl, text=f"保存到: {CUSTOM_JSON_PATH}\n触发配置: {CUSTOM_ACTIONS_PATH}", style="Hint.TLabel").grid(row=8, column=0, sticky="w", pady=(4, 0))

        # 输出框：显示最近“执行/预览”过的12维角度
        # 手指控制区
        finger_box = ttk.Labelframe(
            right, text="手指姿态（0-100% 归一化，0=min伸直，100=max握紧，归零=natural）", padding=10
        )
        finger_box.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        finger_box.columnconfigure(1, weight=1)

        row_idx = 0
        for fname in FINGER_NAMES:
            ttk.Label(finger_box, text=fname).grid(row=row_idx, column=0, sticky="w", padx=(0, 6))
            var = tk.DoubleVar(value=FINGER_DEFAULT_PERCENT.get(fname, 0.0))
            self.finger_vars[fname] = var

            slider = ttk.Scale(
                finger_box,
                from_=0.0,
                to=100.0,
                orient=tk.HORIZONTAL,
                variable=var,
            )
            slider.grid(row=row_idx, column=1, sticky="ew")

            val_label = ttk.Label(finger_box, text=f"{var.get():.0f}%", width=5, anchor="e")
            val_label.grid(row=row_idx, column=2, sticky="e", padx=(6, 0))
            self.finger_value_labels[fname] = val_label

            def _make_trace(name=fname, v=var, lbl=val_label):
                def _on_change(*_a):
                    try:
                        val = float(v.get())
                    except Exception:
                        val = 0.0
                    # 限制在 0-100 范围
                    if val < 0.0:
                        val = 0.0
                    elif val > 100.0:
                        val = 100.0
                    v.set(val)
                    lbl.config(text=f"{val:.0f}%")
                return _on_change

            var.trace("w", _make_trace())
            row_idx += 1

        ttk.Button(
            finger_box,
            text="手指归零（自然放松）",
            command=self.reset_fingers,
        ).grid(row=row_idx, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # 序列动作构建器
        self.sequence_steps: List[Dict] = []  # [{"gesture": str, "duration": float}, ...]
        self.sequence_name_var = tk.StringVar(value="")  # 保存时的序列名称
        self.seq_sequence_var = tk.StringVar(value="")   # 已保存序列下拉选中
        seq_box = ttk.Labelframe(right, text="序列动作（多步组合，输入名称后保存即可触发）", padding=10)
        seq_box.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        seq_box.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=0)
        # 序列名称输入
        seq_name_row = ttk.Frame(seq_box)
        seq_name_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        seq_name_row.columnconfigure(1, weight=1)
        ttk.Label(seq_name_row, text="序列名称:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(seq_name_row, textvariable=self.sequence_name_var, width=24).grid(row=0, column=1, sticky="ew")
        ttk.Label(seq_name_row, text="（保存后说此名称即可触发）", style="Hint.TLabel").grid(row=0, column=2, sticky="w", padx=(4, 0))
        # 已保存序列下拉 + 加载按钮
        seq_load_row = ttk.Frame(seq_box)
        seq_load_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        seq_load_row.columnconfigure(1, weight=1)
        ttk.Label(seq_load_row, text="已保存序列:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.seq_sequence_combo = ttk.Combobox(seq_load_row, textvariable=self.seq_sequence_var, width=20, state="readonly")
        self.seq_sequence_combo.grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(seq_load_row, text="加载序列", command=self._load_sequence).grid(row=0, column=2, padx=(4, 0))
        # 步骤列表
        seq_list_frame = ttk.Frame(seq_box)
        seq_list_frame.grid(row=2, column=0, sticky="nsew")
        seq_list_frame.columnconfigure(0, weight=1)
        self.sequence_listbox = tk.Listbox(seq_list_frame, height=5, font=("Courier", 9))
        self.sequence_listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(seq_list_frame, orient=tk.VERTICAL, command=self.sequence_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.sequence_listbox.configure(yscrollcommand=sb.set)
        # 添加步骤
        add_row = ttk.Frame(seq_box)
        add_row.grid(row=3, column=0, sticky="ew", pady=(6, 2))
        add_row.columnconfigure(1, weight=1)
        ttk.Label(add_row, text="手势:").grid(row=0, column=0, padx=(0, 4))
        self.seq_gesture_combo = ttk.Combobox(add_row, width=16, state="readonly")
        self.seq_gesture_combo.grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Label(add_row, text="时长(s):").grid(row=0, column=2, padx=(8, 4))
        self.seq_duration_var = tk.StringVar(value="0.8")
        ttk.Entry(add_row, textvariable=self.seq_duration_var, width=6).grid(row=0, column=3, padx=2)
        ttk.Button(add_row, text="从已有添加", command=self._seq_add_from_existing).grid(row=0, column=4, padx=(4, 0))
        ttk.Button(add_row, text="当前姿态添加", command=self._seq_add_current_pose).grid(row=0, column=5, padx=2)
        # 删除/排序
        btn_row = ttk.Frame(seq_box)
        btn_row.grid(row=4, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(btn_row, text="删除选中", command=self._seq_delete_selected).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="上移", command=self._seq_move_up).pack(side="left", padx=2)
        ttk.Button(btn_row, text="下移", command=self._seq_move_down).pack(side="left", padx=2)
        ttk.Button(btn_row, text="预览序列", command=self._seq_preview).pack(side="left", padx=8)
        ttk.Button(btn_row, text="💾 保存序列（并自动可触发）", command=self._save_sequence, style="Accent.TButton").pack(side="left", padx=4)
        ttk.Label(seq_box, text="步骤中的手势须在 base_gestures 中；可从「已保存序列」加载后编辑", style="Hint.TLabel").grid(row=5, column=0, sticky="w", pady=(2, 0))

        # 初始化下拉
        self._refresh_saved_gestures()

        # 默认把分割条往右推：让左侧滑块区域更大（避免遮挡）
        # 同时给两侧设置一个合理的最小宽度，避免左侧“被挤没了”
        try:
            body.paneconfigure(left, minsize=640)
            body.paneconfigure(right, minsize=320)
        except Exception:
            pass

        def _set_sash():
            try:
                self.root.update_idletasks()
                total = max(1, self.root.winfo_width())
                # 左侧默认 74% 宽度（更大一点，避免你说的“没区域，需要手动拉出来”）
                body.sashpos(0, int(total * 0.74))
            except Exception:
                pass
        self.root.after(120, _set_sash)
    
    def create_joint_tile(self, parent, index: int, joint_name: str, row: int, col: int, colspan: int = 1):
        """把一个关节做成小矩形卡片，并按人形布局摆放。"""
        # 外层：用 tk.Frame 做“卡片边框”，更像一个小矩形模块
        outer = tk.Frame(parent, highlightthickness=1, highlightbackground="#d0d0d0", background="#ffffff")
        outer.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=6, pady=6)
        for cc in range(colspan):
            parent.columnconfigure(col + cc, weight=1)
        parent.rowconfigure(row, weight=1)

        # 内层布局
        header = ttk.Frame(outer)
        header.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(header, text=joint_name, style="Section.TLabel").pack(side="left")

        # slider + value
        mid = ttk.Frame(outer)
        mid.pack(fill="both", expand=True, padx=6, pady=4)
        mid.columnconfigure(0, weight=1)

        # 变量
        var = tk.DoubleVar(value=0.0)
        self.slider_vars.append(var)

        min_val, max_val = JOINT_RANGES.get(joint_name, (-90, 90))
        slider = ttk.Scale(
            mid,
            from_=min_val,
            to=max_val,
            orient=tk.HORIZONTAL,
            variable=var,
            command=lambda v, idx=index: self.on_slider_change(idx, float(v)),
        )
        slider.grid(row=0, column=0, sticky="ew")
        self.slider_widgets.append(slider)

        # 底部：数值 + 输入框
        foot = ttk.Frame(outer)
        foot.pack(fill="x", padx=6, pady=(2, 6))
        foot.columnconfigure(2, weight=1)

        value_label = ttk.Label(foot, text="0.0°", width=7, anchor="e")
        value_label.grid(row=0, column=0, padx=(0, 6))
        self.value_labels.append(value_label)

        ttk.Label(foot, text="输入:").grid(row=0, column=1, sticky="w")
        entry_var = tk.StringVar(value="0.0")
        entry = ttk.Entry(foot, textvariable=entry_var, width=7, justify="right")
        entry.grid(row=0, column=2, sticky="w")

        # 初始角度
        self.current_angles[index] = float(var.get())

        def _commit_entry(_evt=None):
            try:
                val = float(entry_var.get())
            except Exception:
                entry_var.set(f"{self.current_angles[index]:.1f}")
                return
            val = max(min_val, min(max_val, val))
            var.set(val)
            self.current_angles[index] = val
            value_label.config(text=f"{val:.1f}°")
            entry_var.set(f"{val:.1f}")

        entry.bind("<Return>", _commit_entry)
        entry.bind("<FocusOut>", _commit_entry)

        # 变量变化：刷新数值显示
        def _sync(*_a):
            v = float(var.get())
            self.current_angles[index] = v
            value_label.config(text=f"{v:.1f}°")
        var.trace("w", _sync)

    def create_joint_slider(self, parent, row, index, joint_name):
        """为单个关节创建滑块控件"""
        frame = ttk.Frame(parent, padding=(4, 2))
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.columnconfigure(1, weight=1)
        
        # 关节名称标签
        name_label = ttk.Label(frame, text=joint_name, width=22, anchor="w")
        name_label.grid(row=0, column=0, padx=(0, 8), sticky="w")
        
        # 滑块变量
        var = tk.DoubleVar(value=0.0)
        self.slider_vars.append(var)
        
        # 获取角度范围
        min_val, max_val = JOINT_RANGES.get(joint_name, (-90, 90))
        
        # 滑块
        slider = ttk.Scale(
            frame,
            from_=min_val,
            to=max_val,
            orient=tk.HORIZONTAL,
            variable=var,
            length=360,
            command=lambda v, idx=index: self.on_slider_change(idx, float(v))
        )
        slider.grid(row=0, column=1, padx=6, sticky="ew")
        self.slider_widgets.append(slider)
        
        # 数值显示标签
        value_label = ttk.Label(frame, text="0.0°", width=8, anchor="e")
        value_label.grid(row=0, column=2, padx=(6, 4))
        self.value_labels.append(value_label)
        
        # 直接输入框
        entry_var = tk.StringVar(value="0.0")
        entry = ttk.Entry(frame, textvariable=entry_var, width=7, justify="right")
        entry.grid(row=0, column=3, padx=(4, 0))

        def _commit_entry(_evt=None):
            try:
                val = float(entry_var.get())
            except Exception:
                entry_var.set(f"{self.current_angles[index]:.1f}")
                return
            val = max(min_val, min(max_val, val))
            var.set(val)
            self.current_angles[index] = val
            value_label.config(text=f"{val:.1f}°")
            entry_var.set(f"{val:.1f}")

        entry.bind("<Return>", _commit_entry)
        entry.bind("<FocusOut>", _commit_entry)
        
        # 绑定滑块变化事件
        var.trace("w", lambda *args, idx=index: self.update_value_label(idx))
    
    def on_slider_change(self, index, value):
        """滑块值变化时的回调"""
        self.current_angles[index] = value
        self.update_value_label(index)
        
        # 如果启用了实时预览，则自动预览
        if self.preview_var.get() and self.preview_enabled:
            self._schedule_preview()
    
    def update_torso_angle_display(self):
        """更新中间躯干区域的关节角度数据显示（清晰格式）"""
        if not hasattr(self, 'torso_angle_text'):
            return
        
        self.torso_angle_text.configure(state="normal")
        self.torso_angle_text.delete("1.0", "end")
        
        # 清晰格式，每行一个关节，对齐显示
        lines = []
        lines.append("【头部】")
        lines.append(f"  head_yaw:     {self.current_angles[0]:7.1f}°")
        lines.append(f"  head_pitch:   {self.current_angles[1]:7.1f}°")
        lines.append("")
        lines.append("【左臂】")
        lines.append(f"  left_shoulder_pitch: {self.current_angles[2]:7.1f}°")
        lines.append(f"  left_shoulder_roll:  {self.current_angles[3]:7.1f}°")
        lines.append(f"  left_shoulder_yaw:   {self.current_angles[4]:7.1f}°")
        lines.append(f"  left_elbow:          {self.current_angles[5]:7.1f}°")
        lines.append(f"  left_wrist:          {self.current_angles[6]:7.1f}°")
        lines.append("")
        lines.append("【右臂】")
        lines.append(f"  right_shoulder_pitch: {self.current_angles[7]:7.1f}°")
        lines.append(f"  right_shoulder_roll:  {self.current_angles[8]:7.1f}°")
        lines.append(f"  right_shoulder_yaw:   {self.current_angles[9]:7.1f}°")
        lines.append(f"  right_elbow:          {self.current_angles[10]:7.1f}°")
        lines.append(f"  right_wrist:          {self.current_angles[11]:7.1f}°")
        
        self.torso_angle_text.insert("1.0", "\n".join(lines))
        self.torso_angle_text.configure(state="disabled")

    def _schedule_preview(self):
        """实时预览：去抖 + 最小间隔，避免拖动滑块时刷爆ROS。"""
        if self._preview_job is not None:
            try:
                self.root.after_cancel(self._preview_job)
            except Exception:
                pass
            self._preview_job = None

        def _do():
            self._preview_job = None
            now = time.time()
            if now - self._last_preview_ts < self.preview_min_interval_s:
                # 还没到最小间隔：再等一点
                self._schedule_preview()
                return
            self._last_preview_ts = now
            self.preview_current(quick=True)

        self._preview_job = self.root.after(self.preview_debounce_ms, _do)

    def _refresh_saved_gestures(self):
        """刷新右侧下拉列表、序列手势下拉、已保存序列下拉。"""
        try:
            data = self.load_custom()
        except Exception:
            data = {"base_gestures": {}, "action_sequences": {}}
        base = data.get("base_gestures", {})
        names = sorted([k for k in base.keys() if isinstance(k, str)])
        try:
            self.saved_combo["values"] = names
        except Exception:
            pass
        try:
            if hasattr(self, "seq_gesture_combo"):
                self.seq_gesture_combo["values"] = names
        except Exception:
            pass
        try:
            if hasattr(self, "seq_sequence_combo"):
                aseq = data.get("action_sequences", {})
                seq_names = sorted([k for k in aseq.keys() if isinstance(k, str)])
                self.seq_sequence_combo["values"] = seq_names
        except Exception:
            pass

    def _load_selected(self):
        """从右侧下拉加载。"""
        name = (self.saved_combo.get() or self.saved_gestures_var.get() or "").strip()
        if not name:
            self.load_gesture()
            return
        data = self.load_custom()
        base = data.get("base_gestures", {})
        if name not in base:
            messagebox.showwarning("提示", f"未找到手势: {name}")
            return
        angles = base[name]
        if not isinstance(angles, list) or len(angles) != len(JOINT_NAMES):
            messagebox.showerror("错误", "手势角度数量不匹配")
            return
        for i, angle in enumerate(angles):
            try:
                v = float(angle)
            except Exception:
                v = 0.0
            self.slider_vars[i].set(v)
            self.current_angles[i] = v
            self.update_value_label(i)
        self.gesture_name_var.set(name)

        # 同步加载该手势对应的手指姿态（如果有）
        self._apply_finger_pose(name, data=data)
        
        # 更新躯干区域显示
        self.update_torso_angle_display()

    def _save_from_entry(self):
        """优先使用右侧输入框的名称保存；为空则走原对话框。"""
        name = (self.gesture_name_var.get() or "").strip()
        if name:
            # 临时注入：让 save_gesture 使用这个名字
            orig = simpledialog.askstring
            try:
                simpledialog.askstring = lambda *a, **k: name
                self.save_gesture()
            finally:
                simpledialog.askstring = orig
        else:
            self.save_gesture()
    
    def update_value_label(self, index):
        """更新数值显示标签"""
        value = self.current_angles[index]
        self.value_labels[index].config(text=f"{value:.1f}°")
        # 同时更新中间躯干区域的角度显示
        self.update_torso_angle_display()
    
    def reset_all(self):
        """重置所有角度为0"""
        for i in range(len(JOINT_NAMES)):
            self.slider_vars[i].set(0.0)
            self.current_angles[i] = 0.0
            self.update_value_label(i)
        # 更新躯干区域显示
        self.update_torso_angle_display()

    def _update_finger_neutral_defaults(self, neutral_pct: Dict[str, float]):
        """将 ym_info 的自然位百分比保存，供「归零」使用。"""
        if neutral_pct:
            self._finger_neutral_percent = dict(neutral_pct)

    def reset_fingers(self):
        """重置所有手指为「自然放松」姿态。使用 ym_info 归一化百分比(0%=min, 100%=max)。"""
        for fname in FINGER_NAMES:
            default = self._finger_neutral_percent.get(
                fname, FINGER_DEFAULT_PERCENT.get(fname, 0.0)
            )
            var = self.finger_vars.get(fname)
            if var is not None:
                try:
                    var.set(float(default))
                except Exception:
                    var.set(0.0)
    
    def load_gesture(self):
        """从JSON加载已有手势"""
        data = self.load_custom()
        base = data.get("base_gestures", {})
        
        if not base:
            messagebox.showinfo("提示", "没有已保存的手势")
            return
        
        # 选择手势对话框
        gesture_name = simpledialog.askstring(
            "加载手势",
            f"请输入手势名称:\n可用手势: {', '.join(sorted(base.keys()))}"
        )
        
        if not gesture_name or gesture_name not in base:
            return
        
        angles = base[gesture_name]
        if len(angles) != len(JOINT_NAMES):
            messagebox.showerror("错误", f"手势角度数量不匹配: 期望{len(JOINT_NAMES)}，实际{len(angles)}")
            return
        
        # 加载角度到滑块
        for i, angle in enumerate(angles):
            self.slider_vars[i].set(float(angle))
            self.current_angles[i] = float(angle)
            self.update_value_label(i)

        # 如果该手势有保存过手指姿态，一并加载到手指滑块
        self._apply_finger_pose(gesture_name)
        
        # 更新躯干区域显示
        self.update_torso_angle_display()

        messagebox.showinfo("成功", f"已加载手势: {gesture_name}")
    
    def preview_current(self, quick=False):
        """预览当前角度"""
        duration = 0.3 if quick else 1.0

        # 1) 先尝试预览手指动作（如果手指控制器已就绪）
        if self.finger_controller and self.finger_preview_enabled:
            try:
                self._preview_fingers(duration=duration)
            except Exception as e:
                print(f"[手指预览] 失败: {e}")

        # 2) 再预览上肢关节（ROS）
        if not self.preview_enabled or not self.ros_publisher:
            # 如果手指已经成功预览，就不再弹窗打扰；只在两者都不可用时提示
            if not (self.finger_controller and self.finger_preview_enabled):
                messagebox.showwarning("警告", "ROS未连接，无法预览上肢关节")
            return
        
        # 创建预览手势
        gesture = {
            "gesture_name": "preview",
            "joint_angles": self.current_angles.copy(),
            "duration": duration,
        }
        
        # 在后台线程中发布（避免阻塞UI）
        def do_preview():
            try:
                # 先记录（表示“即将执行”）
                self.root.after(0, lambda: self._append_angle_log(self.current_angles))
                self.ros_publisher.publish_gesture_sequence(
                    [gesture],
                    fps=50,
                    verbose=False
                )
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("预览失败", str(e)))
        
        threading.Thread(target=do_preview, daemon=True).start()

    def _append_angle_log(self, angles: List[float]):
        """追加一行12维角度到输出框。"""
        try:
            vals = [float(x) for x in (angles or [])]
        except Exception:
            vals = []
        if len(vals) != 12:
            return
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] " + " ".join([f"{v:.1f}" for v in vals])
        self._angle_log_lines.append(line)
        if len(self._angle_log_lines) > self.max_angle_log_lines:
            self._angle_log_lines = self._angle_log_lines[-self.max_angle_log_lines :]
        self._render_angle_log()

    def _render_angle_log(self):
        """渲染角度日志（输出框已移除，此方法保留用于兼容）"""
        # 输出框已移除，不再需要渲染
        pass

    def _copy_torso_data(self):
        """复制中间数据框的当前角度数据到剪贴板"""
        try:
            if not hasattr(self, 'torso_angle_text'):
                return
            # 获取数据框中的文本
            text = self.torso_angle_text.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            pass

    def _clear_torso_data(self):
        """清空中间数据框的显示内容（不改变实际角度值）"""
        if not hasattr(self, 'torso_angle_text'):
            return
        self.torso_angle_text.configure(state="normal")
        self.torso_angle_text.delete("1.0", "end")
        self.torso_angle_text.configure(state="disabled")

    def _copy_angle_log(self):
        """复制角度日志（保留用于兼容）"""
        try:
            text = "\n".join(self._angle_log_lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            pass

    def _clear_angle_log(self):
        """清空角度日志（保留用于兼容）"""
        self._angle_log_lines = []
        self._render_angle_log()

    def _apply_finger_pose(self, gesture_name: str, data: Optional[Dict] = None):
        """根据 JSON 中保存的 finger_gestures，同步更新手指滑块。无对应数据时恢复为默认/归零。"""
        try:
            if data is None:
                data = self.load_custom()
            finger_map = data.get("finger_gestures", {})
        except Exception:
            finger_map = {}
        if not isinstance(finger_map, dict):
            finger_map = {}
        pose = finger_map.get(gesture_name) if gesture_name else None
        if isinstance(pose, dict):
            for fname, val in pose.items():
                if fname == "hand":
                    continue
                var = self.finger_vars.get(fname)
                if var is None:
                    continue
                try:
                    v = float(val)
                except Exception:
                    continue
                if v < 0.0:
                    v = 0.0
                elif v > 100.0:
                    v = 100.0
                var.set(v)
            return
        # 该手势无 finger_gestures 条目时，恢复到默认/归零，保证加载后手指区域有明确状态
        self.reset_fingers()

    def _preview_fingers(self, duration: float = 0.5):
        """根据当前手指滑块，在真实舵机上预览一次手指动作。"""
        if not (self.finger_controller and self.finger_preview_enabled):
            return

        # 收集当前GUI里的手指百分比（0-100）
        pose: Dict[str, float] = {}
        for fname in FINGER_NAMES:
            var = self.finger_vars.get(fname)
            if var is None:
                continue
            try:
                v = float(var.get())
            except Exception:
                v = 0.0
            if v < 0.0:
                v = 0.0
            elif v > 100.0:
                v = 100.0
            pose[fname] = v

        if not pose:
            return

        try:
            # 将当前姿态注册为 FingerMapper 里的一个临时手势
            # 下层会自动将百分比映射到 600-2500 的舵机位置（零位600，弯曲可达 2500）
            # 为了支持“只左手 / 只右手 / 双手”，这里使用三个不同的名字
            mode = (self.finger_preview_mode.get() or "both").lower()
            if mode not in ("left", "right", "both"):
                mode = "both"

            if mode == "left":
                gesture_name = "preview_gui_left"
            elif mode == "right":
                gesture_name = "preview_gui_right"
            else:
                gesture_name = "preview_gui_both"

            self.finger_controller.mapper.add_gesture_mapping(gesture_name, pose)
            self.finger_controller.update_gesture(gesture_name, duration)
        except Exception as e:
            print(f"[手指预览] 调用失败: {e}")
    def _refresh_sequence_listbox(self):
        """刷新序列步骤列表显示。"""
        self.sequence_listbox.delete(0, tk.END)
        for i, s in enumerate(self.sequence_steps):
            g = s.get("gesture", "?")
            d = s.get("duration", 0)
            self.sequence_listbox.insert(tk.END, f"{i+1}. {g} ({d}s)")

    def _load_sequence(self):
        """从已保存序列下拉加载序列到编辑器。"""
        name = (self.seq_sequence_var.get() or self.seq_sequence_combo.get() or "").strip()
        if not name:
            messagebox.showwarning("提示", "请先选择要加载的序列")
            return
        data = self.load_custom()
        aseq = data.get("action_sequences", {})
        if name not in aseq:
            messagebox.showwarning("提示", f"未找到序列: {name}")
            return
        steps = aseq[name]
        if not isinstance(steps, list):
            messagebox.showerror("错误", "序列格式不正确")
            return
        self.sequence_name_var.set(name)
        self.sequence_steps = []
        for s in steps:
            if isinstance(s, dict) and "gesture" in s:
                g = s.get("gesture", "rest")
                d = float(s.get("duration", 0.8))
                self.sequence_steps.append({"gesture": g, "duration": d})
        self._refresh_sequence_listbox()
        messagebox.showinfo("加载成功", f"已加载序列「{name}」({len(self.sequence_steps)}个步骤)")

    def _seq_add_from_existing(self):
        """从已有手势添加步骤。"""
        name = (self.seq_gesture_combo.get() or "").strip()
        if not name:
            messagebox.showwarning("提示", "请先选择已有手势")
            return
        try:
            dur = float(self.seq_duration_var.get() or 0.8)
        except Exception:
            dur = 0.8
        dur = max(0.1, min(10.0, dur))
        self.sequence_steps.append({"gesture": name, "duration": dur})
        self._refresh_sequence_listbox()

    def _seq_add_current_pose(self):
        """将当前姿态保存为新手势并添加为步骤。"""
        gname = simpledialog.askstring("保存为手势", "将当前姿态保存为手势并添加为步骤。\n请输入手势名称:", initialvalue=f"seq_step_{len(self.sequence_steps)+1}")
        if not gname:
            return
        data = self.load_custom()
        base = data.get("base_gestures", {})
        base[gname] = self.current_angles.copy()
        data["base_gestures"] = base
        finger_map = data.get("finger_gestures", {})
        try:
            finger_pose = {n: float(v.get()) for n, v in self.finger_vars.items()}
            if finger_pose:
                hand_mode = (self.finger_preview_mode.get() or "both").strip().lower()
                if hand_mode not in ("left", "right", "both"):
                    hand_mode = "both"
                fp = dict(finger_pose)
                fp["hand"] = hand_mode
                finger_map[gname] = fp
                data["finger_gestures"] = finger_map
        except Exception:
            pass
        try:
            with open(CUSTOM_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        try:
            dur = float(self.seq_duration_var.get() or 0.8)
        except Exception:
            dur = 0.8
        dur = max(0.1, min(10.0, dur))
        self.sequence_steps.append({"gesture": gname, "duration": dur})
        self._refresh_sequence_listbox()
        self._refresh_saved_gestures()

    def _seq_delete_selected(self):
        """删除选中的步骤。"""
        sel = self.sequence_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.sequence_steps):
            self.sequence_steps.pop(idx)
            self._refresh_sequence_listbox()

    def _seq_move_up(self):
        """选中步骤上移。"""
        sel = self.sequence_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = int(sel[0])
        self.sequence_steps[idx], self.sequence_steps[idx - 1] = self.sequence_steps[idx - 1], self.sequence_steps[idx]
        self._refresh_sequence_listbox()
        self.sequence_listbox.selection_set(idx - 1)

    def _seq_move_down(self):
        """选中步骤下移。"""
        sel = self.sequence_listbox.curselection()
        if not sel or sel[0] >= len(self.sequence_steps) - 1:
            return
        idx = int(sel[0])
        self.sequence_steps[idx], self.sequence_steps[idx + 1] = self.sequence_steps[idx + 1], self.sequence_steps[idx]
        self._refresh_sequence_listbox()
        self.sequence_listbox.selection_set(idx + 1)

    def _seq_preview(self):
        """预览序列动作。"""
        if not self.sequence_steps:
            messagebox.showinfo("提示", "序列为空，请先添加步骤")
            return
        if not self.ros_publisher or not self.preview_enabled:
            messagebox.showinfo("提示", "ROS 未连接，无法预览")
            return
        seq = [{"gesture_name": s["gesture"], "gesture": s["gesture"], "duration": s["duration"]} for s in self.sequence_steps]
        self.ros_publisher.publish_enhanced_sequence(seq, fps=50, smooth_transitions=True, verbose=False)
        # 手指按步骤时序执行，每步等待对应 duration 后再更新下一步
        if self.finger_controller and self.finger_preview_enabled:
            def _seq_finger_worker():
                for s in self.sequence_steps:
                    if not getattr(self, "finger_preview_enabled", True):
                        break
                    g = s.get("gesture", "rest")
                    d = float(s.get("duration", 0.8))
                    self.finger_controller.update_gesture(g, d)
                    time.sleep(max(0.1, d))
            threading.Thread(target=_seq_finger_worker, daemon=True).start()

    def _save_sequence(self):
        """保存序列到 action_sequences 并创建动作绑定，保存后直接可触发。"""
        if not self.sequence_steps:
            messagebox.showwarning("提示", "序列为空，请先添加步骤")
            return
        seq_name = (getattr(self, "sequence_name_var", None) and self.sequence_name_var.get() or "").strip()
        if not seq_name:
            seq_name = simpledialog.askstring("保存序列", "请输入序列名称（将作为触发词）:", initialvalue=f"my_sequence_{int(time.time())}")
        if not seq_name:
            return
        data = self.load_custom()
        aseq = data.get("action_sequences", {})
        if not isinstance(aseq, dict):
            aseq = {}
        steps = [{"gesture": s["gesture"], "duration": float(s["duration"])} for s in self.sequence_steps]
        aseq[seq_name] = steps
        data["action_sequences"] = aseq
        try:
            with open(CUSTOM_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        cfg = self.load_custom_actions_cfg()
        mappings = cfg.get("action_mappings", {})
        aliases = cfg.get("action_aliases", {})
        durations = cfg.get("action_durations", {})
        mappings[seq_name] = seq_name
        lst = aliases.setdefault(seq_name, [])
        if seq_name not in lst:
            lst.append(seq_name)
        durations[seq_name] = sum(s["duration"] for s in steps)
        cfg["action_mappings"] = mappings
        cfg["action_aliases"] = aliases
        cfg["action_durations"] = durations
        self.save_custom_actions_cfg(cfg)
        self._refresh_saved_gestures()  # 刷新「已保存序列」下拉，使新序列可加载
        messagebox.showinfo("保存成功", f"序列「{seq_name}」已保存。\n\n说「{seq_name}」即可触发。\n若主程序已运行，需重启后生效。")

    def save_gesture(self):
        """保存当前手势到JSON，并自动配置动作绑定"""
        # 获取手势名称
        gesture_name = simpledialog.askstring(
            "保存手势",
            "请输入手势名称:",
            initialvalue="custom_gesture"
        )
        
        if not gesture_name:
            return

        # 单一动作时长（秒），保存时写入 action_durations
        try:
            dur_var = getattr(self, "single_gesture_duration_var", None)
            single_dur = float((dur_var.get() if dur_var else None) or 1.5)
            single_dur = max(0.3, min(30.0, single_dur))
        except Exception:
            single_dur = 1.5
        
        # 加载现有数据
        data = self.load_custom()
        base = data.get("base_gestures", {})
        finger_map = data.get("finger_gestures", {})
        
        # 检查是否已存在
        if gesture_name in base:
            if not messagebox.askyesno("确认", f"手势 '{gesture_name}' 已存在，是否覆盖？"):
                return
        
        # 保存角度（上肢关节）
        base[gesture_name] = self.current_angles.copy()
        data["base_gestures"] = base

        # 当前手指姿态（百分比 0-100），并记录 hand（左手/右手/双手）供执行时只驱动对应手
        try:
            finger_pose = {name: float(var.get()) for name, var in self.finger_vars.items()}
        except Exception:
            finger_pose = {}
        hand_mode = (self.finger_preview_mode.get() or "both").strip().lower()
        if hand_mode not in ("left", "right", "both"):
            hand_mode = "both"

        if finger_pose:
            if not isinstance(finger_map, dict):
                finger_map = {}
            finger_pose_with_hand = dict(finger_pose)
            finger_pose_with_hand["hand"] = hand_mode
            finger_map[gesture_name] = finger_pose_with_hand
            data["finger_gestures"] = finger_map
        
        # 保存到文件
        try:
            with open(CUSTOM_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存手势失败: {str(e)}")
            return
        
        # 自动添加别名（如果手势名是常见中文名），同时复制手指姿态
        added_aliases = self.maybe_add_aliases(
            gesture_name,
            self.current_angles.copy(),
            base,
            finger_map=finger_map if isinstance(finger_map, dict) else None,
            finger_pose=finger_pose_with_hand if finger_pose else None,
        )
        if added_aliases:
            # 重新保存（包含别名和手指姿态）
            data["base_gestures"] = base
            if isinstance(finger_map, dict):
                data["finger_gestures"] = finger_map
            with open(CUSTOM_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 自动更新动作配置（针对常见中文名，可映射到系统内置动作代号）
        action_updated = self.update_actions_for_gesture(gesture_name, self.current_angles.copy())

        # 若未命中内置规则：仍然强制创建一个“自定义动作”绑定，保证下次对话可直接触发
        bound_action_key = None
        if not action_updated:
            bound_action_key = self.ensure_action_binding(gesture_name)

        # 将用户填写的「动作时间」写入 action_durations（覆盖默认值）
        cfg = self.load_custom_actions_cfg()
        mappings = cfg.get("action_mappings", {})
        durations = cfg.get("action_durations", {})
        for action_key, mapped_gesture in mappings.items():
            if mapped_gesture == gesture_name:
                durations[action_key] = single_dur
        cfg["action_durations"] = durations
        self.save_custom_actions_cfg(cfg)

        # 显示成功消息：保存后默认即可触发（不再提示“还要自己映射”）
        success_msg = f"手势 '{gesture_name}' 已保存到:\n{CUSTOM_JSON_PATH}"
        success_msg += "\n动作触发配置已写入:\n" + CUSTOM_ACTIONS_PATH
        success_msg += "\n\n✅ 下次对话时直接说“" + gesture_name + "”即可触发"
        if bound_action_key:
            success_msg += f"\n（动作代号: {bound_action_key}）"
        messagebox.showinfo("保存成功", success_msg)
    
    def load_custom(self) -> Dict:
        """加载自定义手势JSON"""
        if not os.path.exists(CUSTOM_JSON_PATH):
            return {"base_gestures": {}, "action_sequences": {}}
        try:
            with open(CUSTOM_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"base_gestures": {}, "action_sequences": {}}
            data.setdefault("base_gestures", {})
            data.setdefault("action_sequences", {})
            data.setdefault("finger_gestures", {})
            return data
        except Exception as e:
            messagebox.showerror("加载失败", f"读取 {CUSTOM_JSON_PATH} 失败: {e}")
            return {"base_gestures": {}, "action_sequences": {}}
    
    def load_custom_actions_cfg(self) -> Dict:
        """加载自定义动作配置JSON"""
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
        except Exception as e:
            return {
                "action_aliases": {},
                "action_regex": {},
                "action_mappings": {},
                "action_durations": {},
                "action_full_min": {},
                "quick_hold_gestures": []
            }
    
    def save_custom_actions_cfg(self, data: Dict):
        """保存自定义动作配置JSON"""
        try:
            with open(CUSTOM_ACTIONS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存动作配置失败: {e}")
    
    def maybe_add_aliases(
        self,
        name: str,
        angles: List[float],
        base: Dict[str, List[float]],
        finger_map: Optional[Dict[str, Dict[str, float]]] = None,
        finger_pose: Optional[Dict[str, float]] = None,
    ) -> bool:
        """根据常见中文名称，自动添加策略使用的英文/规范别名。

        若提供 finger_map & finger_pose，则在复制上肢角度别名的同时，也复制对应的手指姿态配置。
        """
        alias_map = {
            "点赞": ["thumbs_up"],
            "肌肉": ["muscle_pose"],
            "秀肌肉": ["muscle_pose"],
            "修肌肉": ["muscle_pose"],
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
                    added = True
                # 同步复制手指姿态到别名（如果有提供）
                if finger_map is not None and finger_pose is not None and alias not in finger_map:
                    try:
                        finger_map[alias] = dict(finger_pose)
                        added = True
                    except Exception:
                        pass
        return added
    
    def update_actions_for_gesture(self, name: str, angles: List[float]) -> bool:
        """根据手势名称自动更新动作配置"""
        cfg = self.load_custom_actions_cfg()
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
            self.save_custom_actions_cfg(cfg)
        
        return updated
    
    @staticmethod
    def _default_action_key_for_gesture(name: str) -> str:
        """为任意手势名生成一个稳定的动作代号（用于 custom_actions.json 的 key）。"""
        raw = (name or "").strip()
        if not raw:
            return f"custom_{int(time.time())}"
        # 将空白替换为下划线；其余字符尽量保留（中文也可作为key）
        raw = re.sub(r"\s+", "_", raw)
        return raw

    def _bind_action_to_gesture(self, action_key: str, gesture_name: str):
        """把 action_key 绑定到 gesture_name，并把 gesture_name 加入触发词。"""
        cfg = self.load_custom_actions_cfg()
        aliases: Dict[str, List[str]] = cfg.get("action_aliases", {})
        mappings: Dict[str, str] = cfg.get("action_mappings", {})
        full_min: Dict[str, float] = cfg.get("action_full_min", {})
        quick: List[str] = cfg.get("quick_hold_gestures", [])
        durations: Dict[str, float] = cfg.get("action_durations", {})

        # 绑定映射：动作 -> 手势名
        mappings[action_key] = gesture_name

        # 触发词：把“手势名本身”作为提示词加入（TextProcessor 会读 action_aliases 并加入关键词）
        lst = aliases.setdefault(action_key, [])
        if gesture_name not in lst:
            lst.append(gesture_name)

        # 让该手势也算“可快速保持”（可选，但不影响触发）
        if gesture_name not in quick:
            quick.append(gesture_name)

        # 给未知动作一个合理默认时长（秒）
        if action_key not in durations:
            durations[action_key] = 1.5
        if action_key not in full_min:
            full_min[action_key] = min(1.5, float(durations.get(action_key, 1.5)))

        cfg["action_aliases"] = aliases
        cfg["action_mappings"] = mappings
        cfg["quick_hold_gestures"] = quick
        cfg["action_full_min"] = full_min
        cfg["action_durations"] = durations
        self.save_custom_actions_cfg(cfg)

    def ensure_action_binding(self, name: str) -> str:
        """未能自动推断动作时：仍然自动绑定一个动作key，确保下次对话可触发。"""
        cfg = self.load_custom_actions_cfg()
        mappings: Dict[str, str] = cfg.get("action_mappings", {})
        
        # 若已由某个动作指向该手势名，则无需处理
        if name in mappings.values():
            # 返回已存在的action_key（取第一个匹配）
            for k, v in mappings.items():
                if v == name:
                    return str(k)
            return self._default_action_key_for_gesture(name)
        
        # 默认动作代号：与手势名一致（最直观，也能直接被TextProcessor触发）
        default_key = self._default_action_key_for_gesture(name)

        # 使用对话框允许用户改成系统内置动作代号（可选）；即使留空/取消，也会使用默认代号自动绑定
        action_options = "thumbs_up, ok, peace, stop, come_here, point_forward, handshake, muscle_pose（可选）"
        result = simpledialog.askstring(
            "绑定动作",
            f"将手势“{name}”绑定为可触发动作。\n\n"
            f"- 直接回车/取消：使用默认动作代号（推荐）\n"
            f"- 或输入系统内置动作代号：{action_options}\n\n"
            f"动作代号（默认: {default_key}）:",
            initialvalue=default_key
        )
        
        act = (result or "").strip() or default_key
        self._bind_action_to_gesture(act, name)
        return act


def main():
    """主函数"""
    root = tk.Tk()
    app = GestureDesignerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

