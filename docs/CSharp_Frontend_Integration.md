# C# 前端对接 MeowField AutoPiano 方案

本文档给出在保留现有 Python 功能基础上，使用 C#（WPF/WinUI/WinForms 等）编写前端并对接的可行性评估、总体架构与实施步骤。

---

## 1. 可行性结论（TL;DR）
- 结论：可行，推荐采用“Python 后端服务 + C# 前端客户端”的进程间通信模式。
- 首选方案：Python 使用 FastAPI 暴露 REST/WebSocket API；C# 使用 HttpClient/SignalR/WebSocket 进行调用与事件订阅。
- 备选方案：
  - 直接嵌入：C# 通过 pythonnet 嵌入 CPython 解释器直接调用现有 Python 代码（工程耦合更高）。
  - 子进程桥接：C# 以标准输入输出（或命名管道、ZeroMQ）与 Python 子进程通信（协议需自定义）。
  - gRPC：定义 .proto 接口，生成 C#/Python 双端代码（跨语言强类型，初期成本略高）。

---

## 2. 推荐架构（FastAPI + C# WPF 示例）

- 进程：
  - Python：作为“业务后端 + 音频/MIDI/设备控制”服务，运行在 `app/`（或 `app/back/`）中，基于 FastAPI 提供接口。
  - C#：作为“桌面 UI 前端”，负责交互、状态展示、文件选择等，通过 HTTP/WebSocket 访问 Python 服务。

- 对现有代码的最小改动：
  - 将当前 GUI 逻辑（`app/app.py` 中 `MeowFieldAutoPiano`）中的“业务控制能力”抽取/复用到服务层（已有大量函数位于 `meowauto` 包下，可直接复用）。
  - 在 API 层包装这些能力，例如：加载 MIDI、解析分部、开始/暂停/停止播放、导出等。

- 映射关系建议（示例）：
  - `POST /api/session/open`：初始化会话，返回会话 ID。
  - `POST /api/midi/load`：加载 MIDI 文件，参数：`path`。
  - `POST /api/play/start`：开始自动演奏（可带倒计时等参数）。
  - `POST /api/play/pause` / `/api/play/resume` / `/api/play/stop`：控制播放。
  - `GET /api/status`：获取播放状态、进度、当前曲目信息等。
  - `POST /api/export/csv`：导出事件表（复用 `meowauto.utils.exporters.event_csv`）。
  - `WS /ws/events`：发布系统日志、错误、播放进度等事件（复用 `event_bus` 输出）。

---

## 3. 准备工作与依赖

- Python 端：
  - 新增依赖：`fastapi`, `uvicorn[standard]`, `pydantic`
  - 现有依赖继续沿用：`tkinter`（如保留）、`ttkbootstrap`（如保留）、`mido`, `pygame`, `keyboard`, `numpy`, `pillow` 等。
  - 运行环境仍由 `start_admin_fixed.bat` 保持 UTF-8，并可新增启动后端模式开关。

- C# 端：
  - 目标框架：.NET 6/7/8（建议 8）。
  - 依赖：
    - REST：`System.Net.Http.Json`（自带）或 `Refit`。
    - WebSocket/事件：`System.Net.WebSockets.Client` 或 `SignalR.Client`（若采用 SignalR）。
    - UI：WPF（推荐）或 WinUI 3。

- 路由与跨域：
  - 桌面应用本地直连后端，一般无需 CORS；开发期可放开 `127.0.0.1`。

---

## 4. 目录与启动建议

- 新增 Python 后端服务文件（示例路径）：
  - `app/server/__init__.py`
  - `app/server/api.py`（FastAPI 实现）
  - `app/server/adapters/`（将 `meowauto` 的能力以服务方式适配暴露）

- 启动方式：
  - 方式 A（开发期）：
    - 先运行 Python 后端：`uvicorn app.server.api:app --host 127.0.0.1 --port 8088 --reload`
    - 再运行 C# 前端（配置后端地址为 `http://127.0.0.1:8088`）。
  - 方式 B（一键批处理）：
    - `start_admin_fixed.bat` 增加参数：`/server` 表示仅启动后端；`/ui` 表示旧版 Python UI；默认 `/server`。
    - C# 前端启动时若探测不到后端，提示用户启动或尝试自启后端。

---

## 5. Python 端最小示例（FastAPI）

```python
# 文件：app/server/api.py
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="MeowField AutoPiano API", version="1.0.0")

class LoadMidiReq(BaseModel):
    path: str

@app.post("/api/midi/load")
def load_midi(req: LoadMidiReq):
    # TODO: 调用 meowauto.midi.analyzer / 播放服务进行预处理或缓存
    # 比如：app_state.load_midi(req.path)
    return {"ok": True, "path": req.path}

@app.post("/api/play/start")
def play_start(countdown: Optional[int] = 0):
    # TODO: 调用 PlaybackService / PlaybackController
    return {"ok": True}

@app.get("/api/status")
def get_status():
    # TODO: 返回当前进度/状态
    return {"ok": True, "playing": False, "progress": 0.0}

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    # TODO: 将 event_bus 的日志/事件推送到 ws
    await ws.send_json({"type": "welcome", "msg": "ws connected"})
```

---

## 6. C# 端最小示例（WPF + HttpClient）

```csharp
// .NET 8 WPF 代码片段
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;

public class AutoPianoClient
{
    private readonly HttpClient _http;
    public AutoPianoClient(string baseUrl)
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl) };
    }

    public Task<HttpResponseMessage> LoadMidiAsync(string path)
        => _http.PostAsJsonAsync("/api/midi/load", new { path });

    public Task<HttpResponseMessage> StartAsync(int countdown = 0)
        => _http.PostAsync($"/api/play/start?countdown={countdown}", null);

    public Task<T?> GetStatusAsync<T>()
        => _http.GetFromJsonAsync<T>("/api/status");
}
```

WebSocket 订阅：

```csharp
using System.Net.WebSockets;
using System.Text;

public async Task ListenEventsAsync(string wsUrl, CancellationToken token)
{
    using var ws = new ClientWebSocket();
    await ws.ConnectAsync(new Uri(wsUrl), token);
    var buf = new byte[8 * 1024];
    while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
    {
        var result = await ws.ReceiveAsync(buf, token);
        if (result.MessageType == WebSocketMessageType.Close) break;
        var msg = Encoding.UTF8.GetString(buf, 0, result.Count);
        // TODO: 解析 JSON 并更新 UI
    }
}
```

---

## 7. 备选方案对比

- 直接嵌入（pythonnet）：
  - 优点：调用开销小，可直接使用现有 Python 代码与对象。
  - 缺点：部署复杂（解释器/依赖绑定）、UI/消息循环与 GIL 协调复杂、崩溃隔离性差。

- 子进程桥（StdIO/命名管道/ZeroMQ）：
  - 优点：无需 Web 框架，完全本地，不暴露端口。
  - 缺点：需要自定义协议和消息路由；维护成本较高。

- gRPC：
  - 优点：强类型、跨语言生态成熟、性能好。
  - 缺点：引入 proto 工具链与生成代码；对于纯本地桌面应用略显重。

结论：首选 FastAPI + HTTP/WS，开发效率高、调试友好、演进空间大。

---

## 8. 与现有功能的对接点（建议）

- `meowauto.app.services.playback_service.PlaybackService`：播放服务统一出口。
- `meowauto.app.controllers.playback_controller.PlaybackController`：控制器封装，API 层可直接使用。
- 事件总线 `event_bus`/`Events`：将系统日志、状态变化通过 WS 推送给前端。
- 导出功能：`meowauto.utils.exporters.*` 可直接映射为 REST 导出接口。
- MIDI 解析：`meowauto.midi.analyzer`；分部：`meowauto.midi.partitioner.*`；
- UI 相关逻辑（`app/app.py`）仅保留给旧版 Python UI，后端不要依赖 Tk 主循环。

---

## 9. 路线图（建议）

1) 原型期（1-2 天）
- 在 `app/server/api.py` 提供 3-5 个基础接口：加载 MIDI、开始/暂停/停止、获取状态。
- C# WPF 建立最小页面：选择文件、开始/暂停、状态刷新。

2) 扩展期（3-5 天）
- 增加 WebSocket 事件流，将 event_bus 日志与进度推送到前端。
- 完善导出接口与错误处理；补充单元测试/集成测试。

3) 打包发布（2-3 天）
- Python 后端：可选 `pyinstaller` 或自带 venv；
- C# 前端：`self-contained` 发布；
- 批处理启动整合：`start_admin_fixed.bat /server` 支持一键启动后端。

---

## 10. 风险与注意事项

- 设备/权限：部分 MIDI/键盘全局热键在非管理员权限下可能受限（已在批处理中改为警告不中断）。
- 依赖安装：`pygame` 等包在部分机器需要 VC++ 运行时；提供国内镜像或离线包。
- 线程与阻塞：确保 Python 后端不依赖 Tk 主线程；播放/解析在独立线程或异步任务中执行。
- 兼容与迁移：保持现有 Python UI 可运行（双轨制），C# 前端逐步切换。

---

## 11. 清单（Checklist）

- [ ] Python：新增 `app/server/api.py` 与最小接口
- [ ] Python：requirements 增加 `fastapi`, `uvicorn[standard]`
- [ ] 批处理：`start_admin_fixed.bat` 增加 `/server` 模式（可选）
- [ ] C#：创建 WPF 工程，封装 `AutoPianoClient`
- [ ] C#：实现文件选择/播放控制/状态显示最小闭环
- [ ] C#：增加 WS 事件监听，驱动 UI 进度与日志
- [ ] 文档：补充 API 说明与错误码

---

## 12. 后续可选优化

- 使用 SignalR 统一事件通道；
- 引入 gRPC 以获得强类型与更好的跨语言契约；
- 引入配置中心（JSON/YAML），由前端管理参数并下发到后端。

---

如需我直接在项目中创建 `app/server/api.py` 的最小可运行版本，并修改 `start_admin_fixed.bat` 增加 `/server` 启动选项，请告知，我将自动补全并验证运行。
