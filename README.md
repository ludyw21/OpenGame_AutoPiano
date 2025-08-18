# MeowField_AutoPiano

MeowField_AutoPiano 是一款面向 PC 游戏的自动弹琴软件，集成音频→MIDI 转换（PianoTrans）、MIDI→LRCp 转换、LRCp/MIDI 双模式自动演奏、3×7（21 键）映射、播放列表自动连播与可视化日志。



## 功能特性
- 图形界面（Tkinter）：左侧文件/列表/控制区，右侧实时日志；布局随窗口大小自适应
- 音频→MIDI：集成调用 `PianoTrans`，本地AI自动将常见音频格式文件转为MIDI谱

- MIDI→LRCp：生成时间轴格式 `[start][end] TOKENS`，支持和弦/延长音，并自动加入“自动演奏列表”
- 双演奏模式：
  - `lrcp`（时间轴精准演奏）
  - `midi`（映射直演，支持和弦）
- 自动连播：双击列表播放；一首结束自动跳到下一首
- 支持自行选择MIDI文件演奏

## 目录结构（关键）
- `auto_piano_py312.py` / `auto_piano_py312.pyw`：主程序
- `PianoTrans-v1.0/`：音频转 MIDI 工具目录（需包含模型与 ffmpeg）
  - `piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth`（约 165MB）
  - `ffmpeg/`（已在运行时自动加入 PATH）
- `music/`：示例或你的音频/MIDI文件
- `TMIDI/`：MIDI谱播放器
- `logs/`：运行日志
- `output/`：输出文件
- `requirements.txt`：依赖列表

## 环境要求
- Windows 10/11（x64）
- Python 3.12（64 位）
- 首次安装依赖需联网（或使用已打包的 `.venv`）

## 安装与运行
1) 下载本项目到目标电脑（例如 `D:\AutoPiano`），保持目录结构不变。下载地址： **https://pan.baidu.com/s/16jUGmw--O3PCEfMBdk5OEA?pwd=rz74**  提取码: rz74 
2) 安装依赖：
```powershell
cd D:\AutoPiano

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
3) 启动：
- 双击start_admin.bat



## 使用说明（常用流程）
1. 选择音频（mp3/wav/flac…）→ 点击“音频转MIDI”。
   - 程序将调用 PianoTrans 输出 `.mid`，并自动生成 `.lrcp`，加入“自动演奏列表”。

2. 或直接选择 `.mid` 文件，程序会自动生成 `.lrcp` 并加入列表。

3. “播放控制”里设置：
   - 演奏模式：`auto` / `lrcp` / `midi`
   - 映射策略：`folded` / `qmp`
   - 速度、音量

4. 双击“自动演奏列表”任一条目开始演奏；完成后自动连播下一首。

   ### 注意：

   **目前midi映射不完善，最好是选择比较简单的钢琴曲，或者使用`Ultimate Vocal Remover`这个软件对乐器伴奏进行分离**

### 两种演奏模式说明
- LRCp 模式（不支持老李和弦）：使用时间轴 `[start][end]` 精准调度，适合有 LRCp 乐谱的播放/联动。
- MIDI 模式（支持和弦）：将任意 MIDI 音符折叠到 C3~B5 并映射到 L/M/H 的 1..7；黑键按 `qmp` 规则归并到邻近白键。

## 故障排查（FAQ）
- 音频转 MIDI 失败或卡住：
  - 确认模型文件存在：`PianoTrans-v1.0\piano_transcription_inference_data\note_F1=0.9677_pedal_F1=0.9186.pth`
  - 首次加载模型会较慢；日志中出现 “Write out to …” 即开始输出
- 报 `audioread.exceptions.NoBackendError`：
  - 确认 `PianoTrans-v1.0\ffmpeg` 存在；程序会自动加入 PATH，重启后重试
- 游戏不识别按键：
  - 以管理员启动；切换英文输入法；保证游戏在前台；关闭与键盘冲突的软件
- 无声：
  - 检查系统/程序音量与输出设备；确认日志显示“音频系统初始化成功”
- MIDI 直演节奏不稳：
  - 将演奏模式设为 `midi`、映射策略设为 `qmp`；该模式使用绝对时间调度

## 提交问题
- 提交issue请附：复现步骤、问题出现的时间点、相关文件路径、`logs` 中对应时间段日志。
- 也可以加入反馈交流群：47814322（QQ）

# 致谢

本项目的lrcp格式支持参考了[Nuist666/OverField_Auto_Piano: OverField 开放空间 自动弹琴工具](https://github.com/Nuist666/OverField_Auto_Piano)

音频转换MIDI谱来自[azuwis/pianotrans：字节跳动使用踏板进行钢琴转录的简单 GUI](https://github.com/azuwis/pianotrans)
