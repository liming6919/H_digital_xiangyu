#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舵机串口控制器
Servo Serial Controller - 支持SCS/STS协议 (#1P1000T200)
"""

import serial
import serial.tools.list_ports
import time
import threading
import re
from typing import List, Optional, Dict


def parse_ym_info_text(text: str) -> Optional[Dict]:
    """
    从 ym_info 文本解析 min/max/neutral。格式：第1行=自然放松，第2行=最大值，第3行=最小值。
    行需包含 #1P 等舵机指令格式。返回与 read_ym_info_limits 相同的结构，或 None。
    """
    if not text or not text.strip():
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cmd_lines = [ln for ln in lines if "#1P" in ln]
    if len(cmd_lines) < 3:
        return None

    def _parse_line_map(line: str) -> Dict[int, int]:
        out: Dict[int, int] = {}
        try:
            for sid, pos in re.findall(r"#(\d+)P(\d+)", line):
                out[int(sid)] = int(pos)
        except Exception:
            pass
        return out

    neutral_map = _parse_line_map(cmd_lines[0])
    max_map = _parse_line_map(cmd_lines[1])  # 第2行=最大值
    min_map = _parse_line_map(cmd_lines[2])  # 第3行=最小值
    if not max_map or not min_map:
        return None
    max_pos = max(max_map.values())
    min_pos = min(min_map.values())
    if max_pos <= min_pos:
        return None
    result: Dict = {"min": min_pos, "max": max_pos, "min_map": min_map, "max_map": max_map}
    if neutral_map:
        result["neutral"] = neutral_map
    return result


class ServoController:
    """舵机串口控制器 - 支持SCS/STS协议"""
    
    def __init__(self, port: str = "/dev/ttyUSB1", baudrate: int = 115200, timeout: float = 1.0):
        """
        初始化舵机控制器
        
        Args:
            port: 串口设备路径，如 "/dev/ttyUSB1"
            baudrate: 波特率，默认115200
            timeout: 超时时间（秒）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.debug = False
        # 手指位置安全范围（可由外部根据 ym_info.txt 调整）
        self.min_position = 600
        self.max_position = 2500

    def set_position_limits(self, min_pos: int, max_pos: int):
        """设置舵机位置的安全范围（例如从 ym_info.txt 读取后调用）"""
        try:
            min_pos = int(min_pos)
            max_pos = int(max_pos)
        except Exception:
            return
        if max_pos <= min_pos:
            return
        # 做一下安全夹紧，避免异常值
        min_pos = max(0, min(min_pos, 4000))
        max_pos = max(min_pos + 10, min(max_pos, 4095))
        self.min_position = min_pos
        self.max_position = max_pos
        
    def connect(self) -> bool:
        """
        连接串口
        
        Returns:
            成功返回True，失败返回False
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # 清空缓冲区
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            
            if self.debug:
                print(f"[舵机] 串口连接成功: {self.port} @ {self.baudrate} baud")
            
            return True
            
        except serial.SerialException as e:
            print(f"[舵机] 串口连接失败: {e}")
            return False
        except Exception as e:
            print(f"[舵机] 连接异常: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            if self.debug:
                print(f"[舵机] 串口已断开: {self.port}")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.serial_conn is not None and self.serial_conn.is_open
    
    def set_servo_position(self, servo_id: int, position: int, time_ms: int = 500) -> bool:
        """
        设置单个舵机位置
        
        Args:
            servo_id: 舵机ID (1-254)
            position: 位置值 (0-1000, 对应0-180度)
            time_ms: 运行时间 (ms, 0-30000)
            
        Returns:
            成功返回True，失败返回False
        """
        if not self.is_connected():
            if not self.connect():
                return False
        
        # 参数检查（位置值范围 self.min_position-self.max_position，默认 600-2500）
        servo_id = max(1, min(254, servo_id))
        position = max(self.min_position, min(self.max_position, position))  # 安全范围限制
        time_ms = max(0, min(30000, time_ms))
        
        # 构建指令: #<ID>P<Position>T<Time>
        command = f"#{servo_id}P{position}T{time_ms}\r\n"
        
        return self._send_command(command)
    
    def set_multiple_servos(self, servo_positions: Dict[int, int], time_ms: int = 500) -> bool:
        """
        设置多个舵机位置（同步控制）
        
        Args:
            servo_positions: 舵机位置字典 {servo_id: position}
            time_ms: 运行时间 (ms)
            
        Returns:
            成功返回True，失败返回False
        """
        if not servo_positions:
            return True
        
        if not self.is_connected():
            if not self.connect():
                return False
        
        time_ms = max(0, min(30000, time_ms))
        
        # 构建多舵机同步指令: #<ID1>P<Pos1>#<ID2>P<Pos2>...T<Time>
            # 位置值范围：self.min_position-self.max_position（默认 600-2500，零位600）
        command_parts = []
        for servo_id, position in servo_positions.items():
            servo_id = max(1, min(254, servo_id))
            position = max(self.min_position, min(self.max_position, position))
            command_parts.append(f"#{servo_id}P{position}")
        
        command = "".join(command_parts) + f"T{time_ms}\r\n"
        
        return self._send_command(command)
    
    def _send_command(self, command: str) -> bool:
        """
        发送指令到串口
        
        Args:
            command: 指令字符串
            
        Returns:
            成功返回True，失败返回False
        """
        if not self.is_connected():
            return False
        
        try:
            with self.lock:
                if self.debug:
                    print(f"[舵机] 发送指令: {command.strip()}")
                
                self.serial_conn.write(command.encode('utf-8'))
                self.serial_conn.flush()
                
                return True
                
        except serial.SerialTimeoutException:
            print(f"[舵机] 发送超时")
            return False
        except Exception as e:
            print(f"[舵机] 发送失败: {e}")
            return False
    
    def read_ym_info_limits(self) -> Optional[Dict[str, int]]:
        """
        通过串口发送 #FRead-ym_info.txt 命令，读取设备返回的 ym_info 内容并解析最小/最大位置。
        返回 {'min': min_pos, 'max': max_pos} 或 None（失败时）。
        """
        if not self.is_connected():
            if not self.connect():
                return None
        try:
            # 清空缓冲区
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            time.sleep(0.01)
            # 发送读取命令
            cmd = "#FRead-ym_info.txt\r\n"
            if self.debug:
                print(f"[舵机] 请求 ym_info: {cmd.strip()}")
            self.serial_conn.write(cmd.encode("utf-8"))
            self.serial_conn.flush()
            # 等待设备准备响应
            time.sleep(0.1)
            # 读取若干行响应
            lines: List[str] = []
            for _ in range(20):
                if self.serial_conn.in_waiting > 0:
                    raw = self.serial_conn.read_until(b"\n", size=128)
                    cleaned = "".join(chr(b) for b in raw if 32 <= b <= 126)
                    if cleaned:
                        lines.append(cleaned)
                        if self.debug:
                            print(f"[舵机] ym_info 行: {cleaned}")
                else:
                    time.sleep(0.01)
            if not lines:
                return None

            # 优先按“3 行舵机指令”的格式解析：
            # 第 1 行：自然放松值；第 2 行：最大值；第 3 行：最小值
            cmd_lines = [ln for ln in lines if "#1P" in ln and "T" in ln]

            def _parse_line_positions(line: str) -> list:
                # 匹配 #<id>P<pos> 里的位置值（仅数值列表）
                try:
                    pairs = re.findall(r"#(\d+)P(\d+)", line)
                    return [int(p) for (_sid, p) in pairs]
                except Exception:
                    return []

            def _parse_line_map(line: str) -> Dict[int, int]:
                # 匹配 #<id>P<pos>，返回 {id: pos}
                out: Dict[int, int] = {}
                try:
                    pairs = re.findall(r"#(\d+)P(\d+)", line)
                    for sid, pos in pairs:
                        out[int(sid)] = int(pos)
                except Exception:
                    return out
                return out

            min_pos = None
            max_pos = None
            neutral_map: Dict[int, int] = {}
            min_map: Dict[int, int] = {}
            max_map: Dict[int, int] = {}
            side: Optional[str] = None

            # 检测手别标记：行内容为单独的 "L" 或 "R"
            for ln in lines:
                s = ln.strip()
                if s in ("L", "R"):
                    side = s
                    break
            if len(cmd_lines) >= 3:
                # 第一行：自然放松；第二行：最大值；第三行：最小值（每舵机独立）
                neutral_map = _parse_line_map(cmd_lines[0])
                max_map = _parse_line_map(cmd_lines[1])
                min_map = _parse_line_map(cmd_lines[2])
                if max_map and min_map:
                    max_vals = list(max_map.values())
                    min_vals = list(min_map.values())
                    max_pos = max(max_vals)
                    min_pos = min(min_vals)

            # 如果上面的专用格式没解析出来，再退回到“全局数字最小/最大”的通用解析
            if min_pos is None or max_pos is None:
                text = "\n".join(lines)
                nums = [int(x) for x in re.findall(r"\d{3,4}", text)]
                nums = [n for n in nums if 200 <= n <= 4095]
                if len(nums) < 2:
                    return None
                min_pos = min(nums)
                max_pos = max(nums)

            if max_pos <= min_pos:
                return None
            if self.debug:
                print(f"[舵机] ym_info 解析范围: min={min_pos}, max={max_pos}, neutral={neutral_map}, side={side}")
            result: Dict[str, int] | Dict[str, object]
            result = {"min": min_pos, "max": max_pos}
            if neutral_map:
                result["neutral"] = neutral_map
            if min_map:
                result["min_map"] = min_map
            if max_map:
                result["max_map"] = max_map
            if side:
                result["side"] = side
            return result  # type: ignore[return-value]
        except Exception as e:
            print(f"[舵机] 读取 ym_info 失败: {e}")
            return None
    
    @staticmethod
    def angle_to_position(angle_deg: float, min_pos: int = 800, max_pos: int = 2200) -> int:
        """
        角度转位置值（适配800-2200范围）
        
        Args:
            angle_deg: 角度（度，0-180）
            min_pos: 最小位置值，默认800
            max_pos: 最大位置值，默认2200
            
        Returns:
            位置值 (min_pos-max_pos)
        """
        angle_deg = max(0.0, min(180.0, angle_deg))
        range_size = max_pos - min_pos
        position = int(round(min_pos + angle_deg * range_size / 180.0))
        return max(min_pos, min(max_pos, position))
    
    @staticmethod
    def position_to_angle(position: int, min_pos: int = 800, max_pos: int = 2200) -> float:
        """
        位置值转角度（适配800-2200范围）
        
        Args:
            position: 位置值 (min_pos-max_pos)
            min_pos: 最小位置值，默认800
            max_pos: 最大位置值，默认2200
            
        Returns:
            角度（度）
        """
        position = max(min_pos, min(max_pos, position))
        range_size = max_pos - min_pos
        return (position - min_pos) * 180.0 / range_size
    
    def set_debug(self, enable: bool):
        """设置调试模式"""
        self.debug = enable
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

