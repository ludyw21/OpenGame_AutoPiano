# WinForms 前端对接 MeowField AutoPiano 方案

本文档说明如何在保留现有 Python 功能模块的基础上，用 C# WinForms 实现桌面前端并完成对接。

---

## 1. 可行性与结论

- 结论：可行。推荐“Python 后端服务 + WinForms 前端客户端”的 IPC（进程间通信）模式。
- 首选方案：Python 使用 FastAPI 暴露 REST + WebSocket；WinForms 用 HttpClient + WebSocket 客户端调用与订阅。
- 优点：
  - 与现有 `meowauto` 功能解耦，复用逻辑最大化；
  - 前后端独立演进、调试友好；
  - 崩溃隔离（UI 不会因后端异常直接退出）。
- 备选：
  - `pythonnet` 直接嵌入 CPython（部署与线程协调复杂、不推荐初期采用）。
  - 子进程标准输入输出/命名管道（需自定义协议、维护成本高）。
  - gRPC（强类型，初期成本高）。

---

## 2. 现有功能模块可否修改并对接？

- 可以，建议“轻量改造，服务化暴露”。
- 对接点（建议）：
  - 播放控制：`meowauto.app.services.playback_service.PlaybackService`
  - 控制器：`meowauto.app.controllers.playback_controller.PlaybackController`
  - 事件总线：`event_bus`/`Events`（转发到 WebSocket 推送）
  - MIDI 解析：`meowauto.midi.analyzer`
  - 分部处理：`meowauto.midi.partitioner.*`
  - 导出：`meowauto.utils.exporters.*`
- 需要避免：后端 API 层不应依赖 `tkinter` 主循环（GUI 逻辑保留在旧 Python UI，或逐步下线）。

---

## 3. 推荐架构

- 进程：
  - Python 后端（FastAPI + Uvicorn）运行在本地 127.0.0.1:8088。
  - WinForms 前端通过 HTTP 调用控制、通过 WebSocket 订阅事件与进度。
- API 映射（示例）：
  - `POST /api/session/open` -> 创建/初始化后端会话
  - `POST /api/midi/load` { path } -> 加载 MIDI
  - `POST /api/play/start|pause|resume|stop`
  - `GET /api/status` -> 播放状态、进度、曲目信息
  - `POST /api/export/csv` -> 导出事件表
  - `WS /ws/events` -> 事件/日志/进度推送（来自 `event_bus`）

---

## 4. 准备工作

- Python 端：
  - 新增依赖：`fastapi`, `uvicorn[standard]`, `pydantic`
  - 目录建议：
    - `app/server/api.py`（FastAPI 路由与 WS）
    - `app/server/adapters/`（封装/适配 `meowauto` 能力）
  - 启动：`uvicorn app.server.api:app --host 127.0.0.1 --port 8088`
  - 批处理扩展（可选）：`start_admin_fixed.bat /server` 一键启动后端

- WinForms 端：
  - .NET 版本：.NET 8（推荐）或 .NET 6/7
  - 依赖：
    - REST：`System.Net.Http.Json`（随 SDK 提供）或 `Refit`
    - WebSocket：`System.Net.WebSockets.Client`
  - 项目结构：
    - `Services/AutoPianoClient.cs`（封装 REST 调用）
    - `Services/EventListener.cs`（WebSocket 事件订阅）
    - `Forms/MainForm.cs`（文件选择、播放控制、进度显示、日志区域）

---

## 5. Python FastAPI 最小骨架（示例）

```python
# 文件：app/server/api.py
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="MeowField AutoPiano API", version="1.0.0")

class LoadMidiReq(BaseModel):
    path: str

@app.post("/api/session/open")
def open_session():
    # TODO: 初始化 PlaybackService / Controller / 状态容器
    return {"ok": True, "session": "default"}

@app.post("/api/midi/load")
def load_midi(req: LoadMidiReq):
    # TODO: 使用 meowauto.midi.analyzer 等进行预加载/缓存
    return {"ok": True, "path": req.path}

@app.post("/api/play/start")
def play_start(countdown: Optional[int] = 0):
    # TODO: 调用 PlaybackService / Controller
    return {"ok": True}

@app.post("/api/play/pause")
def play_pause():
    return {"ok": True}

@app.post("/api/play/resume")
def play_resume():
    return {"ok": True}

@app.post("/api/play/stop")
def play_stop():
    return {"ok": True}

@app.get("/api/status")
def get_status():
    # TODO: 返回播放状态/进度
    return {"ok": True, "playing": False, "progress": 0.0}

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    # TODO: 将 event_bus 的日志/进度推送
    await ws.send_json({"type": "welcome", "msg": "connected"})
```

---

## 6. WinForms 最小调用示例

```csharp
// Services/AutoPianoClient.cs
using System.Net.Http;
using System.Net.Http.Json;

public class AutoPianoClient
{
    private readonly HttpClient _http;
    public AutoPianoClient(string baseUrl)
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl) };
    }

    public Task<HttpResponseMessage> OpenSessionAsync()
        => _http.PostAsync("/api/session/open", null);

    public Task<HttpResponseMessage> LoadMidiAsync(string path)
        => _http.PostAsJsonAsync("/api/midi/load", new { path });

    public Task<HttpResponseMessage> StartAsync(int countdown = 0)
        => _http.PostAsync($"/api/play/start?countdown={countdown}", null);

    public Task<HttpResponseMessage> PauseAsync()
        => _http.PostAsync("/api/play/pause", null);

    public Task<HttpResponseMessage> ResumeAsync()
        => _http.PostAsync("/api/play/resume", null);

    public Task<HttpResponseMessage> StopAsync()
        => _http.PostAsync("/api/play/stop", null);

    public Task<T?> GetStatusAsync<T>()
        => _http.GetFromJsonAsync<T>("/api/status");
}
```

WebSocket 事件订阅：

```csharp
// Services/EventListener.cs
using System.Net.WebSockets;
using System.Text;

public class EventListener
{
    public async Task ListenAsync(string wsUrl, Action<string> onMessage, CancellationToken token)
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(new Uri(wsUrl), token);
        var buf = new byte[8192];
        while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
        {
            var result = await ws.ReceiveAsync(buf, token);
            if (result.MessageType == WebSocketMessageType.Close) break;
            var msg = Encoding.UTF8.GetString(buf, 0, result.Count);
            onMessage?.Invoke(msg);
        }
    }
}
```

主窗体使用建议：
- 控件：文件选择按钮、开始/暂停/停止按钮、进度条、日志文本框；
- 线程：使用 `async/await` + `CancellationToken`，通过 `Invoke` 更新 UI；
- 定时刷新：`System.Windows.Forms.Timer` 周期调用 `GetStatusAsync`。

---

## 7. 开发步骤（Checklist）

- [ ] Python：创建 `app/server/api.py`，接入现有 `meowauto` 能力
- [ ] Python：requirements 增加 `fastapi`, `uvicorn[standard]`, `pydantic`
- [ ] 批处理：`start_admin_fixed.bat` 增加 `/server` 模式（可选）
- [ ] WinForms：新建 .NET 8 工程
- [ ] WinForms：实现 `AutoPianoClient` 与 `EventListener`
- [ ] WinForms：实现 `MainForm` 基础 UI 与最小闭环（加载 MIDI → 开始 → 状态显示 → 停止）
- [ ] 测试：并发调用、异常断线重连、长任务流畅度

---

## 8. 注意事项与风险

- 权限：全局热键/设备访问可能需要管理员权限（批处理已改为警告不中断）。
- 依赖：`pygame` 在部分机器需要 VC++ 运行库，必要时提供镜像或离线包。
- 线程：后端避免阻塞事件循环；WinForms UI 更新需在 UI 线程调用。
- 迁移：Python 旧 GUI 与服务可并存一段时间，逐步实体化 API 覆盖所有功能。

---

## 9. 里程碑建议

1) 原型：后端 3-5 个接口 + 前端最小窗体
2) 扩展：引入 WS 事件、导出接口、错误处理
3) 发布：后端一键启动、前端自包含发布

---

如需我为你直接创建 `app/server/api.py` 的最小实现，并调整批处理 `/server` 启动选项，以及生成 WinForms 示例工程骨架，请告知偏好端口与 .NET 版本，我将自动生成并验证。
