# 手势时间轴修复方案

## 问题描述
动作时间与长语音的时间不匹配，明明语音还没结束，动作已经停了很久了。

## 根本原因
手势序列生成时，如果序列动作时长不足，没有生成足够的填充动作来填满整个语音时长。

## 借鉴口型算法的核心思想

你同事的口型算法有以下关键特性：

### 1. 精确的时间窗口预留
```python
def reserve_utterance_window(self, duration_sec: float) -> float:
    """为一句文本保留播放时间窗，返回该句的绝对开始时间"""
    start_at = max(time.monotonic(), self.next_available_time)
    self.next_available_time = start_at + max(0.0, duration_sec)  # ✅ 累加时长
    return start_at
```

### 2. 基于绝对时间戳的动作调度
```python
def enqueue_servo_action(..., begin_offset_sec, utter_start_monotonic, ...):
    scheduled_time = utter_start_monotonic + max(0.0, begin_offset_sec)  # ✅ 绝对时间
    heapq.heappush(self.event_heap, (scheduled_time, seq_counter, task))
```

### 3. 智能闭嘴策略（确保动作持续到语音结束）
```python
# 在张嘴动作结束后执行智能闭嘴（位置插值）
close_time = utter_start_monotonic + begin_offset_sec + (mouth_open_duration_ms / 1000.0)

# 检查是否会与下一个字冲突
if close_time + close_duration > next_word_start_time:
    skip_close()  # 跳过闭嘴，直接过渡
else:
    schedule_close()  # 调度闭嘴指令
```

## 已实施的修复

### 修复1：gesture_policy.py - 确保填充动作始终生成

**位置：** `_generate_timeline_aligned_sequence` 函数（约第1820行）

**修改前：**
```python
if remaining_time <= 0:
    # 序列动作已经超时或刚好用完，不执行填充动作
    sequence = sequence_gestures  # ❌ 问题：只返回序列动作
```

**修改后：**
```python
# ✅ 借鉴口型算法：确保动作时长始终等于语音时长
if remaining_time > 0.1:  # 如果剩余时间 > 0.1秒
    if filler_gestures and filler_duration > 0:
        # 有填充动作，缩放到剩余时间
        scale_factor = remaining_time / filler_duration
        scaled_fillers = [(name, dur * scale_factor) for name, dur in filler_gestures]
        sequence = sequence_gestures + scaled_fillers
    else:
        # 没有填充动作，生成新的填充
        new_filler = self._generate_semantic_filler(remaining_time, emotion, intent, flow_mode)
        sequence = sequence_gestures + new_filler
else:
    sequence = sequence_gestures

# ✅ 关键修复：如果时长不足，强制添加保持动作
if final_duration < total_duration - 0.3:  # 如果差距 > 0.3秒
    hold_duration = total_duration - final_duration
    if sequence:
        last_gesture_name = sequence[-1][0]
        sequence.append((last_gesture_name, hold_duration))
    else:
        sequence.append(("attentive_listen", hold_duration))
```

### 修复2：gesture_policy.py - 添加详细的时间轴验证日志

**位置：** `_generate_timeline_aligned_sequence` 函数末尾

**新增代码：**
```python
# ✅ 最终验证：打印完整的手势序列时间轴
print(f"\n📊 [时间轴验证] 手势序列详情:")
cumulative_time = 0.0
for i, (gesture_name, duration) in enumerate(sequence):
    cumulative_time += duration
    is_seq = "🔵序列" if i < sequence_gesture_count else "🟢填充"
    print(f"  {i+1:2d}. {is_seq} {gesture_name:30s} 时长:{duration:5.2f}s  累计:{cumulative_time:6.2f}s")
print(f"📊 [时间轴验证] 总计: {len(sequence)}个手势, 总时长: {cumulative_time:.2f}s, 目标: {total_duration:.2f}s")
```

### 修复3：main.py - 在执行时验证并添加保持动作

**位置：** `_execute_gesture_sequence` 函数（约第470行）

**新增代码：**
```python
# ✅ 借鉴口型算法：验证动作时长是否匹配语音时长
gesture_total_duration = max(
    float(g.get("start_offset", 0.0) or 0.0) + float(g.get("duration", 0.0) or 0.0) 
    for g in seq_sorted
)

# 从gesture_seq中获取speech_duration（如果有的话）
speech_duration = None
if hasattr(self, '_current_speech_duration'):
    speech_duration = self._current_speech_duration

print(f"[时间轴验证] 手势总时长: {gesture_total_duration:.2f}s")
if speech_duration:
    print(f"[时间轴验证] 语音总时长: {speech_duration:.2f}s")
    time_diff = speech_duration - gesture_total_duration
    print(f"[时间轴验证] 时间差异: {time_diff:.2f}s")
    
    # ✅ 如果动作时长明显短于语音时长，添加保持动作
    if time_diff > 0.5:  # 差距 > 0.5秒
        print(f"⚠️  [时间轴修复] 动作时长不足！添加保持动作: {time_diff:.2f}s")
        if seq_sorted:
            last_gesture = seq_sorted[-1]
            last_gesture_name = last_gesture.get('gesture_name', 'attentive_listen')
            last_end_offset = (float(last_gesture.get('start_offset', 0.0) or 0.0) + 
                             float(last_gesture.get('duration', 0.0) or 0.0))
            
            hold_gesture = {
                'gesture_name': last_gesture_name,
                'start_offset': last_end_offset,
                'duration': time_diff - 0.2,  # 留0.2秒缓冲
                'is_sequence_action': False
            }
            seq_sorted.append(hold_gesture)
            print(f"   [时间轴修复] 添加保持手势: {last_gesture_name}")
```

## 测试方法

### 1. 查看日志输出

运行系统后，查看以下关键日志：

```
🔍 统计:
  序列动作总时长: 2.50s (完整执行)
  序列动作手势数: 3个
  填充动作原始时长: 5.20s
  填充动作手势数: 8个
  目标总时长: 10.00s
  剩余时间: 7.50s
🎯 填充动作缩放: 5.20s -> 7.50s (x1.442)
✅ [初步完成] 最终时长: 10.00s，目标: 10.00s，误差: 0.000s

📊 [时间轴验证] 手势序列详情:
   1. 🔵序列 wave_right                     时长: 1.50s  累计:  1.50s
   2. 🔵序列 point_forward                  时长: 1.00s  累计:  2.50s
   3. 🟢填充 attentive_listen               时长: 2.50s  累计:  5.00s
   4. 🟢填充 thinking                       时长: 2.50s  累计:  7.50s
   5. 🟢填充 rest                           时长: 2.50s  累计: 10.00s
📊 [时间轴验证] 总计: 5个手势, 总时长: 10.00s, 目标: 10.00s
```

### 2. 验证时间对齐

在执行阶段，查看：

```
[时间轴验证] 手势总时长: 10.00s
[时间轴验证] 语音总时长: 10.00s
[时间轴验证] 时间差异: 0.00s
```

如果出现差异：

```
[时间轴验证] 手势总时长: 7.50s
[时间轴验证] 语音总时长: 10.00s
[时间轴验证] 时间差异: 2.50s
⚠️  [时间轴修复] 动作时长不足！添加保持动作: 2.50s
   [时间轴修复] 添加保持手势: attentive_listen
```

## 下一步优化（可选）

### 1. 实现speech_duration的完整传递链路

目前 `speech_duration` 需要从缓存中获取。可以优化为：

```python
# 在缓存时保存
self.gesture_cache[play_id] = {
    'gestures': final_gesture_seq,
    'speech_duration': total_speech_duration
}

# 在执行时提取
cached_data = self.gesture_cache[play_id]
if isinstance(cached_data, dict):
    gesture_seq = cached_data['gestures']
    speech_duration = cached_data.get('speech_duration')
else:
    gesture_seq = cached_data  # 兼容旧格式
    speech_duration = None
```

### 2. 添加动作去重逻辑

如果发现重复动作，可以在 `gesture_policy.py` 中添加：

```python
def _merge_similar_gestures(self, gesture_sequence):
    """合并相似的连续手势"""
    if not gesture_sequence:
        return []
    
    merged = []
    current_gesture = list(gesture_sequence[0])
    
    for next_gesture in gesture_sequence[1:]:
        if next_gesture[0] == current_gesture[0]:
            # 相同手势，合并时长
            current_gesture[1] += next_gesture[1]
        else:
            merged.append(tuple(current_gesture))
            current_gesture = list(next_gesture)
    
    merged.append(tuple(current_gesture))
    return merged
```

### 3. 实现智能过渡策略

借鉴口型算法的插值逻辑，在相似手势之间使用插值过渡：

```python
def _calculate_transition_gesture(self, gesture1, gesture2, ratio=0.5):
    """计算两个手势之间的过渡姿态"""
    angles1 = self.gesture_mapper.get_gesture_angles(gesture1)
    angles2 = self.gesture_mapper.get_gesture_angles(gesture2)
    
    if angles1 and angles2:
        transition_angles = [
            a1 + (a2 - a1) * ratio 
            for a1, a2 in zip(angles1, angles2)
        ]
        return transition_angles
    return None
```

## 总结

核心改进：
1. ✅ 确保填充动作始终生成，填满整个语音时长
2. ✅ 添加保持动作作为兜底，防止动作提前结束
3. ✅ 添加详细日志，方便调试和验证
4. ⏳ 待实现：speech_duration的完整传递链路
5. ⏳ 待实现：动作去重和智能过渡

这些改进借鉴了你同事口型算法的核心思想：**精确的时间戳控制 + 智能填充策略 + 详细的日志验证**。
