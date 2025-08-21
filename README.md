# MeowField_AutoPiano

MeowField_AutoPiano 是一款面向 PC 游戏的自动弹琴软件，支持AI扒谱、MIDI→LRCp 转换、LRCp/MIDI 双模式自动演奏、播放列表自动连播。
交流群：478714322（QQ群）


## 功能特性
- 音频→MIDI：集成调用 `PianoTrans`，本地AI自动将常见音频格式文件转为MIDI谱

- MIDI→LRCp：生成时间轴格式文件
- 双演奏模式：
  - `lrcp`（时间轴精准演奏）
  - `midi`（映射直演，支持和弦）
- 自动连播：双击列表播放；一首结束自动跳到下一首
- 支持自行选择MIDI文件演奏

## 环境要求

- Windows 10/11（x64）
- AI转谱默认使用显卡推理，显卡须有CUDA核心，推荐使用英伟达20系以上显卡

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
   
- 程序将调用 PianoTrans 输出 `.mid`，并自动生成 `.lrcp`，加入“自动演奏列表”。
   
2. 或直接选择 `.mid` 文件，程序会自动生成 `.lrcp` 并加入列表。

3. “播放控制”里设置：
   - 演奏模式：`auto` / `lrcp` / `midi`
   - 映射策略：`folded` / `qmp`
   - 速度、音量

4. 双击“自动演奏列表”任一条目开始演奏；完成后自动连播下一首。

   ### 注意：

   **目前midi映射不完善，最好是选择比较简单的钢琴曲，或者使用`Ultimate Vocal Remover`软件对乐器伴奏进行分离**

### 两种演奏模式说明
- LRCp 模式（不支持老李和弦）：使用时间轴 `[start][end]` 精准调度，适合有 LRCp 乐谱的播放/联动。
- MIDI 模式（支持和弦）：将任意 MIDI 音符折叠到 C3~B5 并映射到 L/M/H 的 1..7；黑键按 `qmp` 规则归并到邻近白键。

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
  - 将演奏模式设为 `midi`，该模式使用绝对时间调度

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

