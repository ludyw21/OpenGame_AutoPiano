# MeowField_AutoPiano



## 项目介绍

MeowField AutoPiano 提供从音频到自动演奏的一站式流程：
- 使用 PianoTrans 将音频本地转为 MIDI。

- 支持 MIDI 解析与主旋律提取（熵启发/节拍/重复/混合多算法，可调“强度/重复惩罚/阈值”），生成更易演奏的旋律线。

- 将旋律与和弦映射为键盘按键，适配常见 PC 游戏按键布局，支持自动连播与全局停止热键。

- UI 集成右侧解析页签（MIDI 解析设置/事件表/系统日志），并提供后处理（黑键移调、量化窗口）。

  交流群：478714322（QQ群）

## 1.环境要求

- Windows 10/11（x64）
- AI转谱默认使用显卡推理，显卡须有CUDA核心，推荐使用英伟达20系以上显卡。如果程序内调用失败请到PianoTrans-v1.0文件夹使用PianoTrans.exe。也可以使用CPU推理，速度较慢。

## 2.安装与运行
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



## 3. 快速开始（5 步）

1) 选择音频（mp3/wav/flac 等）并点击“音频转 MIDI”；或直接选择 `.mid` 文件。
2) 在“解析”页签中选择主旋律提取模式与参数（启用或调整“后处理：黑键移调/量化”）。
3) 在“分部识别与选择”中点击“识别分部”，按需要勾选要参与演奏的分部，并“应用所选分部并解析”。
4) 在“控制”页设置倍速、选择演奏模式（不同乐器略有差异），点击“自动弹琴/播放 MIDI”。
5) 播放过程中可随时使用全局热键 Ctrl+Shift+C 立即停止。

------

## 4. 界面与术语概览

- 控制：主操作区（文件选择、倍速、自动弹琴、播放/停止、乐器提示）。
- 合奏：网络对时、统一开始等（可选显示）。
- 播放列表：添加/导入/移除/清空/保存，支持单曲/顺序/循环/随机。
- 解析：MIDI 解析设置（主旋律提取、后处理、解析引擎、和弦伴奏）。
- 事件表：查看解析后的事件列表（时间、音符、通道、时长等）。
- 日志：系统日志输出。
- 帮助：常用热键与操作提示。

文件选择与解析联动：

- 选择新文件时，程序会尝试自动识别分部与勾选，并触发一次解析与白键率计算，便于快速上手。

------

## 5. 常用工作流

### 5.1 音频→MIDI→自动演奏

1) 控制页选择音频文件 → 点击“音频转 MIDI”。
2) 切至“解析”，按需启用主旋律提取、设置模式/强度/阈值等；开启“后处理”。
3) 在“分部识别与选择”中识别、勾选分部 → “应用所选分部并解析”。
4) 返回“控制”，设置倍速与模式 → “自动弹琴/播放 MIDI”。

### 5.2 直接 MIDI 自动演奏

1) 选择 `.mid` 文件。
2) 同上按需解析、勾选分部、设置倍速与模式后播放。

### 5.3 播放列表联播

1) 在“播放列表”添加文件或导入文件夹。
2) 选择播放模式（单曲/顺序/循环/随机），支持上一首/下一首。
3) 双击列表项或用“播放所选”启动；播放结束可自动连播下一首。

### 5.4 合奏（可选）

- 计划开始：设定延时后统一进入。
- 对时：启用公网对时/手动对时/切回本地时钟。
- 统一开始：设定倒计时与“使用右侧解析事件”。

------

## 6. 重要设置说明

### 6.1 主旋律提取

- 模式：熵启发 / 节拍过滤 / 重复过滤 / 混合
- 参数：强度、重复惩罚、熵权重、最小得分阈值、优先通道（自动/手动）
- 单声部化：解析管线会自动按时间窗口保留代表音，减少事件数，利于演奏。

### 6.2 后处理

- 黑键移调策略：关闭 / 向下 / 就近
- 量化窗口（ms）：对时值进行量化，增强节奏稳定性。

### 6.3 解析引擎

- 选项：自动 / pretty_midi / miditoolkit（默认 pretty_midi）。

### 6.4 分部识别与选择

- 识别方式：按轨/通道/音色分离；可选择“仅通道/智能聚类”。
- 操作：识别分部、全选/全不选/反选、应用所选并解析、播放所选、导出所选。

### 6.5 扫弦/聚合（多键聚合）

- 模式：合并 / 扫弦 / 原始
- 聚合窗口（ms）：控制块和弦的聚合/扫弦时序。

### 6.6 回放 · 和弦伴奏

- 启用和弦伴奏、和弦最短持续（ms）、块和弦窗口（ms）、是否用和弦键替代主音键（去根音）。
- 架子鼓/贝斯默认禁用和弦伴奏。

### 6.7 速度与模式

- 倍速：0.25~3.0（步进 0.05）。
- 演奏模式：
  - MIDI 模式：将音高折叠映射到 L/M/H 1..7 键位，可识别和弦并触发 z/x/c/v/b/n/m。

------

## 7. 键位与热键

- 全局停止：Ctrl+Shift+C（如权限或依赖不足会回退为窗口级热键）。
- 键位映射（摘要）：
  - 旋律：L/M/H 1..7 键位（与常见 PC 游戏键位布局相容）。
  - 和弦：z/x/c/v/b/n/m 触发。

------

## 8. 目录与文件

- logs/：运行日志
- output/：导出/中间输出
- temp/：临时文件
- app/start.py / app/main.py：源码启动入口
- start_admin_fixed.bat：Windows 启动批处理（含依赖检查与目录准备）
- requirements.txt：依赖列表

------

## 9. 故障排查（FAQ）

- 音频转 MIDI 失败或卡住：
  - 确认 PianoTrans 模型存在：`PianoTrans-v1.0\piano_transcription_inference_data\note_F1=0.9677_pedal_F1=0.9186.pth`
  - 模型加载较慢；日志出现 “Write out to …” 表示开始输出
- 报 `audioread.exceptions.NoBackendError`：
  - 确认 `PianoTrans-v1.0\ffmpeg` 存在；重启后重试
- 游戏不识别按键：
  - 以管理员启动；切换英文输入法；保证游戏在前台；关闭与键盘冲突的软件
- 无声：
  - 检查系统/程序音量与输出设备；确认日志显示“音频系统初始化成功”
- MIDI 直演节奏不稳：
  - 使用 MIDI 模式；必要时调低倍速或增大量化窗口
- 解析后事件数不减少/旋律不明显：
  - 调整主旋律模式与“强度/重复惩罚/阈值”；确保启用单声部化
- 全局热键无效：
  - 缺少 `keyboard` 模块或权限受限时自动回退为窗口级；确保程序前台
- Python 依赖缺失：
  - 运行时若提示缺包，按提示执行 `pip install ...`，或使用 `start_admin_fixed.bat` 自动安装
- 路径与可移植性：
  - 项目使用相对路径；移动目录后无需修改，仅需确保 `PianoTrans-v1.0` 位于项目根目录

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

