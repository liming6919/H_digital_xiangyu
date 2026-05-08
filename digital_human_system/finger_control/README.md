# 手指控制模块

## 概述

手指控制模块用于在数字人系统中同步控制手指动作。当数字人执行手势时，手指会根据手势语义自动调整到相应的姿态。

## 功能特性

- ✅ 支持SCS/STS舵机协议（`#1P1000T200`格式）
- ✅ 与数字人手势系统无缝集成
- ✅ 基于语义的手势映射（点赞、握手、指向等）
- ✅ 平滑控制和位置容差（避免抖动）
- ✅ 支持多舵机同步控制

## 文件结构

```
finger_control/
├── __init__.py              # 模块初始化
├── servo_controller.py      # 舵机串口控制器
├── finger_mapper.py         # 手指映射器（手势语义到手指动作）
├── finger_controller.py      # 手指控制器（集成接口）
└── README.md                # 本文档
```

## 使用方法

### 1. 基本使用

手指控制已集成到数字人系统中，默认启用。启动数字人系统时会自动初始化：

```bash
cd digital_human_system
python3 main.py --enable-finger --finger-port /dev/ttyUSB1
```

### 2. 禁用手指控制

如果不需要手指控制：

```bash
python3 main.py --disable-finger
```

### 3. 配置串口

```bash
python3 main.py --finger-port /dev/ttyUSB1 --finger-baudrate 115200
```

## 手势映射

手指控制器会根据手势名称自动映射到相应的手指动作：

| 手势名称 | 手指动作 |
|---------|---------|
| `thumbs_up` | 拇指竖起，其他手指弯曲 |
| `ok_gesture` | 拇指和食指形成O形 |
| `handshake` | 手指自然弯曲（握手姿态） |
| `point` | 食指伸直，其他手指弯曲 |
| `fist` | 所有手指弯曲（握拳） |
| `open_hand` | 所有手指伸直 |
| `rest` / `neutral` | 手指轻微弯曲（休息状态） |

## 自定义映射

可以在代码中添加自定义手势映射：

```python
from finger_control import FingerMapper

mapper = FingerMapper()
mapper.add_gesture_mapping('custom_gesture', {
    'left_thumb': 90,
    'left_index': 180,
    # ... 其他手指
})
```

## 配置说明

### 手指配置

默认配置：左右手各5个手指，每个手指1个舵机

- 左手：舵机ID 1-5（thumb, index, middle, ring, pinky）
- 右手：舵机ID 6-10（thumb, index, middle, ring, pinky）

如需修改，可以在代码中更新：

```python
from finger_control import FingerController

controller = FingerController()
controller.finger_mapper.update_finger_config({
    'left_thumb': 1,
    'left_index': 2,
    # ... 自定义配置
})
```

## 串口设置

### 1. 检查串口设备

```bash
ls -l /dev/ttyUSB*
```

### 2. 设置权限

```bash
sudo chmod 666 /dev/ttyUSB1
# 或
sudo usermod -a -G dialout $USER
```

### 3. 测试串口

```python
from finger_control import ServoController

with ServoController('/dev/ttyUSB1', 115200) as servo:
    servo.set_servo_position(1, 500, 500)  # 舵机1移动到中间位置
```

## 故障排除

### 1. 串口连接失败

- 检查设备路径是否正确
- 检查串口权限
- 检查是否有其他程序占用串口

### 2. 手指无响应

- 检查串口连接
- 检查波特率设置（默认115200）
- 检查舵机ID配置

### 3. 手指动作不匹配

- 检查手势名称是否正确
- 在 `finger_mapper.py` 中添加或修改手势映射

## 技术细节

### 舵机协议

使用SCS/STS舵机协议：

- **单舵机控制**：`#<ID>P<Position>T<Time>`
- **多舵机同步**：`#<ID1>P<Pos1>#<ID2>P<Pos2>...T<Time>`

### 角度映射

- 数字人关节角度：-90° ~ +90°
- 舵机位置值：0 ~ 1000（对应0° ~ 180°）
- 映射公式：`position = (angle_deg + 90) * 1000 / 180`

### 平滑控制

手指控制器实现了平滑控制算法，避免突然的位置变化：

```python
smoothed_pos = current_pos * (1.0 - smoothing_factor) + 
               target_pos * smoothing_factor
```

## 集成说明

手指控制器已集成到数字人系统的主程序中：

1. 在 `DigitalHumanSystem.__init__()` 中初始化
2. 在手势执行时自动调用 `update_gesture()`
3. 与身体动作同步执行

无需额外配置，启动数字人系统即可使用。

