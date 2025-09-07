# WinForms 集成任务清单与重构方案（在独立文件夹进行开发）

本计划用于指导在“独立的新开发文件夹”中，以 WinForms 作为前端，对现有 Python 功能进行服务化改造与集成。文档包含：任务清单、现有代码分析、目标架构、API 设计建议、目录规划、维护性与扩展性建议、风险与里程碑。

---

## 1. 目标与范围（Goals & Scope）

- 保留并复用现有 Python 功能（`meowauto/*`、`PlaybackService`、`PlaybackController`、MIDI 解析/分部/导出等）。
- 在另一个独立目录中新建 WinForms 前端，以进程间通信方式对接 Python 服务。
- 解耦 UI 与业务，提升维护性和扩展性，支持后续模块拓展（工具页、导出、设备控制）。

---

## 2. 现有代码快速分析（Current State）

- 主要入口：
  - `app/app.py`：定义 `MeowFieldAutoPiano`（Tk/ttkbootstrap UI），集成事件总线、模块管理、UI 组件、播放控制等。
  - `app/start.py`：启动脚本，检查依赖、导入 `MeowFieldAutoPiano` 并 `run()`。
- 关键模块：
  - 事件与路由：`app/event_bus.py`（`event_bus`、`Events`）、`app/router.py`。
  - 播放：`meowauto/app/services/playback_service.py`、`meowauto/app/controllers/playback_controller.py`。
  - MIDI：`meowauto/midi/analyzer.py`、`meowauto/midi/partitioner/*`、`meowauto/midi/groups.py`。
  - 导出：`meowauto/utils/exporters/*`（如 `event_csv.py`、`key_notation.py`）。
- 启动脚本：
  - `start_admin_fixed.bat`：纯批处理启动、依赖安装、UTF-8 处理、自动切换 `app/`。
- 结论：业务逻辑大多在 `meowauto/*` 中，具备服务化复用基础；UI（Tk）应与服务层剥离。

---

## 3. 目标架构（Target Architecture）

- 进程模型：
  - Python 作为后端服务（FastAPI + Uvicorn），提供 REST + WebSocket；不依赖 Tk 主循环。
  - C# WinForms 作为前端，使用 `HttpClient` 调用 REST，`ClientWebSocket` 订阅事件。
- 设计原则：
  - API 粒度清晰、幂等；
  - WebSocket 推送 `event_bus` 的状态/日志/进度；
  - 后端无 UI 依赖；
  - 配置集中管理（JSON）。

---

## 4. API 设计建议（Draft）

- 会话与状态：
  - `POST /api/session/open` → 初始化后端（返回 sessionId）
  - `GET  /api/status` → 播放状态、进度、当前曲目、错误码
- MIDI 与流程：
  - `POST /api/midi/load` { path }
  - `POST /api/play/start?countdown=0`
  - `POST /api/play/pause|resume|stop`
  - `GET  /api/progress` → 进度/时间文本（可与 `/api/status` 合并）
- 导出：
  - `POST /api/export/csv` { parts?, path? }
- WebSocket：
  - `GET /ws/events` → 推送 `{type, level, message, progress, ts}` 等事件

返回体统一 `{ ok: bool, data?: any, error?: { code: string, message: string } }`。

---

## 5. 新开发目录建议结构（New Folder Layout）

假设新开发根目录为 `AutoPiano.WinForms/`（与现有仓库并列或独立）：

```
AutoPiano.WinForms/
  backend/                   # Python 后端（可作为子模块或复制）
    app/
      server/
        api.py               # FastAPI 路由与 WS
        adapters/            # 适配 meowauto 的服务封装
      meowauto/              # 复用现有模块（建议作为 git submodule 或包引用）
    requirements.txt         # 在此补充 fastapi/uvicorn/pydantic 等
    run_server.bat           # 本地一键启动后端（可选）

  frontend-winforms/         # C# WinForms 解决方案
    AutoPiano.WinForms.sln
    AutoPiano.WinForms/
      AutoPiano.WinForms.csproj
      Forms/MainForm.cs
      Services/AutoPianoClient.cs
      Services/EventListener.cs
      Models/StatusDto.cs
      appsettings.json       # 后端地址等配置

  README.md
```

维护建议：将 `meowauto` 作为独立包或子模块引入 `backend/`，避免复制粘贴导致的漂移。

---

## 6. 任务清单（Task Breakdown）

- 阶段 A：规划与骨架
  - [ ] 选定新开发根目录（如 `AutoPiano.WinForms/`）
  - [ ] 后端骨架：`app/server/api.py` + `adapters/` 目录
  - [ ] 依赖：`fastapi`, `uvicorn[standard]`, `pydantic`
  - [ ] 定义 API 契约（接口、响应模型、错误码）
  - [ ] 确认 `meowauto` 的引用方式（子模块/包路径）

- 阶段 B：后端服务化改造
  - [ ] 将 `PlaybackService`、`PlaybackController` 实例化为进程级单例/容器管理
  - [ ] 实现 `/api/session/open` 初始化路径与设备资源
  - [ ] 实现 `/api/midi/load`（复用 `analyzer`，缓存中间结果）
  - [ ] 实现播放控制 `/api/play/*`（倒计时参数、异常包装）
  - [ ] `/api/status` 汇总进度/当前文件/错误码
  - [ ] WebSocket 推送 `event_bus` 事件（适配为标准消息结构）
  - [ ] 单元测试：核心服务/路由 70%+ 覆盖

- 阶段 C：WinForms 前端最小闭环
  - [ ] 新建 .NET 8 WinForms 工程
  - [ ] `AutoPianoClient`（REST 封装）与 `EventListener`（WS）
  - [ ] `MainForm`：文件选择、开始/暂停/停止、进度条、日志文本框
  - [ ] 定时器刷新状态（或依赖 WS 推送）
  - [ ] 错误提示/重试/取消（CancellationToken）

- 阶段 D：联调与增强
  - [ ] 压测与稳定性：长时间播放/暂停切换
  - [ ] 导出接口集成（CSV 等）
  - [ ] 设备/权限提示（管理员需求）
  - [ ] 配置文件化（`appsettings.json`/`config.json`）

- 阶段 E：发布与打包
  - [ ] 后端：可选 venv/pyinstaller，提供 `run_server.bat`
  - [ ] 前端：WinForms 自包含发布（x64）
  - [ ] 文档：用户指南、故障排查、API 文档

---

## 7. 最佳实践：维护性与扩展性

- 模块边界清晰：
  - 业务服务（播放/解析）与 API 层分离；
  - API 仅做 DTO 转换与异常映射，不写业务。
- 统一数据模型：
  - 定义请求/响应 DTO，避免透传内部对象；
  - 错误码集中枚举，统一处理。
- 事件总线标准化：
  - 使用标准消息结构 `{type, level, message, data?, ts}`，便于前端消费。
- 配置集中：
  - 后端/前端均从配置文件读取端口、路径、设备策略；
  - 环境区分（dev/prod）。
- 可测试性：
  - 将 `meowauto` 能力通过适配器抽象出接口，便于 mock；
  - API/服务层单元测试 + 集成测试。
- 依赖管理：
  - Python `requirements.txt` 明确版本；
  - C# 使用 SDK 风格项目，锁定 `TargetFramework=net8.0-windows`。

---

## 8. 风险与对策

- Pygame/设备依赖：
  - 对策：安装前置（VC++ 运行库）、提供国内镜像或离线包；
- 管理员权限：
  - 对策：功能到位但 UI 提示，不强制；
- 线程与长任务：
  - 对策：后端异步/线程池；前端 UI 线程更新用 `Invoke`；
- 协议演进：
  - 对策：接口版本化 `v1`，新增保持兼容。

---

## 9. 里程碑（Milestones）

1) 原型（1-2 天）：后端 4-5 个接口 + WinForms 最小窗体闭环；
2) 增强（3-5 天）：WS 事件、导出、错误处理、测试；
3) 发布（2-3 天）：一键启动、发布包与文档齐备。

---

## 10. 后续文档

- `docs/WinForms_Frontend_Integration.md`：WinForms 对接具体示例与代码片段。
- `docs/CSharp_Frontend_Integration.md`：跨技术栈总体方案参考。

---

如需，我可基于此清单直接在“新开发文件夹”初始化骨架（不影响现有仓库），并提供示例代码与运行脚本。
