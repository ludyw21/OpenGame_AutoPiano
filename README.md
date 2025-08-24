# MeowField_AutoPiano



## 项目介绍

MeowField AutoPiano 提供从音频到自动演奏的一站式流程：
- 使用 PianoTrans 将音频本地转为 MIDI。

- 支持 MIDI 解析与主旋律提取（熵启发/节拍/重复/混合多算法，可调“强度/重复惩罚/阈值”），生成更易演奏的旋律线。

- 将旋律与和弦映射为键盘按键，适配常见 PC 游戏按键布局，支持自动连播与全局停止热键。

- UI 集成右侧解析页签（MIDI 解析设置/事件表/系统日志），并提供后处理（黑键移调、量化窗口、BPM）。

  交流群：478714322（QQ群）

## 功能特性
- 音频→MIDI：集成调用 `PianoTrans`，将常见音频格式本地转换为 MIDI。
- MIDI→LRCp：生成时间轴格式 `.lrcp` 文件。
- 主旋律提取：支持多算法模式与参数调节
  - 模式：`entropy`、`beat`、`repetition`、`hybrid`
  - 参数：强度、重复惩罚、熵权重、最小得分阈值、优先通道
  - 单声部化：自动按时间窗口保留单一代表音，显著减少事件数
- 双演奏模式：
  - `lrcp`（时间轴精准调度）
  - `midi`（映射直演，支持和弦触发）
- 和弦支持：识别和弦并映射到 z/x/c/v/b/n/m 键位，可在右侧开关联动。
- 后处理：黑键移调策略、时间量化窗口、BPM 设置。
- 播放控制：
  - 倒计时启动（可自定义/取消）
  - 全局停止热键 Ctrl+Shift+C（系统级优先，回退窗口级）
- 播放列表：双击播放，自动连播下一首。

## 环境要求

- Windows 10/11（x64）
- AI转谱默认使用显卡推理，显卡须有CUDA核心，推荐使用英伟达20系以上显卡。如果程序内调用失败请到PianoTrans-v1.0文件夹使用PianoTrans.exe。也可以使用CPU推理，速度较慢。

## 安装与运行
### 使用exe程序：

1.在Release下载MeowField_AutoPiano.zip

2.解压

3.下载PianoTrans

下载地址

[Release Release v1.0 · azuwis/pianotrans](https://github.com/azuwis/pianotrans/releases/tag/v1.0)

https://pan.baidu.com/s/1Cu8dHEe4PTMhHZG7rvSIBQ?pwd=88cf 提取码: 88cf 

4.将解压后的PianoTrans-v1.0文件夹移动到程序根目录

5.右键选择exe以管理员模式打开

### 使用源码：

1.下载本项目到目标电脑（例如 `D:\AutoPiano`），保持目录结构不变。
2.安装依赖：

```powershell
cd 项目所在目录的路径

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
3.下载PianoTrans

下载地址

[Release Release v1.0 · azuwis/pianotrans](https://github.com/azuwis/pianotrans/releases/tag/v1.0)

https://pan.baidu.com/s/1Cu8dHEe4PTMhHZG7rvSIBQ?pwd=88cf 提取码: 88cf 
4.将解压后的PianoTrans-v1.0文件夹移动到程序根目录

5.双击start_admin.bat启动



## 使用说明（常用流程）
1. 选择音频（mp3/wav/flac…）→ 点击“音频转MIDI”。
   
   - 程序将调用 PianoTrans 输出 `.mid`，并可自动生成 `.lrcp`，加入“自动演奏列表”。
2. 或直接选择 `.mid` 文件，程序会自动解析并生成 `.lrcp` 加入列表。
3. 右侧“解析/日志”区域：
   - 在“MIDI 解析设置”选择主旋律算法与参数（模式、强度、重复惩罚、阈值、优先通道）
   - 可开启“后处理”（黑键移调策略、量化窗口、BPM）
   - 解析后可在“事件表”查看过滤前后事件数变化
4. 左侧“播放控制”：
   - 选择演奏模式：`lrcp` / `midi`
   - 设置“倒计时(秒)”“速度”“音量”，需要时可启用/取消倒计时
   - 点击“自动弹琴”或“播放MIDI”开始；双击播放列表可直接播放，结束后自动连播下一首
5. 随时使用 Ctrl+Shift+C 立即停止所有播放（系统级热键可用时自动启用）。

   ### 注意：
   - 如果原始 MIDI 编配较复杂，建议通过主旋律提取与后处理获得更易演奏的旋律线。
   - 对人声/乐器混合音频，推荐先用分离工具（如 Ultimate Vocal Remover）处理后再转谱。

### 两种演奏模式说明
- LRCp 模式：使用时间轴 `[start][end]` 精准调度，严格按谱播放，适合已有 LRCp 的场景。
- MIDI 模式：将 MIDI 音高折叠映射到 L/M/H 1..7 的键位，可识别和弦并触发 z/x/c/v/b/n/m 键；黑键可按策略归并至邻近白键。

## 故障排查（FAQ）
- 音频转 MIDI 失败或卡住：
  - 确认模型文件存在：`PianoTrans-v1.0\piano_transcription_inference_data\note_F1=0.9677_pedal_F1=0.9186.pth`
  - 加载模型会较慢；日志中出现 “Write out to …” 即开始输出
- 报 `audioread.exceptions.NoBackendError`：
  - 确认 `PianoTrans-v1.0\ffmpeg` 存在；程序会自动加入 PATH，重启后重试
- 游戏不识别按键：
  - 以管理员启动；切换英文输入法；保证游戏在前台；关闭与键盘冲突的软件
- 无声：
  - 检查系统/程序音量与输出设备；确认日志显示“音频系统初始化成功”
- MIDI 直演节奏不稳：
  - 将演奏模式设为 `midi`；必要时调低速度或启用量化窗口
- 解析后事件数不减少/旋律不明显：
  - 在右侧调整主旋律模式与“强度/重复惩罚/阈值”，并确保启用单声部化（已默认）
- 全局热键无效：
  - 未安装 `keyboard` 模块或权限受限时将自动回退为窗口级 Ctrl+Shift+C；请确保程序在前台
- 路径/可移植性：
  - 项目使用相对路径，移动目录后将自动生效；仅需确保 `PianoTrans-v1.0` 位于项目根目录

## 提交问题
- 提交issue请附：复现步骤、问题出现的时间点、相关文件路径、`logs` 中对应时间段日志。
- 也可以加入反馈交流群：478714322（QQ群）

# 致谢

本项目的lrcp格式支持参考了[Nuist666/OverField_Auto_Piano: OverField 开放空间 自动弹琴工具](https://github.com/Nuist666/OverField_Auto_Piano)

音频转换MIDI谱来自[azuwis/pianotrans：字节跳动使用踏板进行钢琴转录的简单 GUI](https://github.com/azuwis/pianotrans)

感谢开发者

# 许可证

本项目采用 [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/) 许可证。

## 许可证条款

**您可以：**
- ✅ **共享** - 以任何媒介或格式复制及分发本材料
- ✅ **改编** - 重混、转换和基于本材料创作
- ✅ **署名** - 您必须给出适当的署名，提供指向本许可证的链接，同时标明是否作出了修改

**在以下条件下：**
- ❌ **非商业性使用** - 您不得将本材料用于商业目的
- 🔄 **相同方式共享** - 如果您重混、转换或基于本材料创作，您必须按照与原始许可协议相同的条款分发您的贡献

## 署名要求

当您使用、共享或修改本项目时，请包含以下信息：

```
基于 MeowField_AutoPiano 项目
原作者：Tsundeer/970thunder

许可证：CC BY-NC-SA 4.0
项目地址：https://github.com/MeowField/MeowField_AutoPiano
```

## 完整许可证

完整的许可证文本请访问：[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)

---

**注意：** 本许可证仅适用于本项目代码和文档。第三方依赖库（如 PianoTrans、ffmpeg 等）遵循其各自的许可证条款。

