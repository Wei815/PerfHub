# PerfHub Pro 系統架構規格書 (Architecture Spec)

## 1. 系統架構圖 (Data Flow)

```mermaid
graph TD
    subgraph Device Layer [測試設備 (真機)]
        A[Android Device]
        I[iOS Device]
    end

    subgraph Agent Layer [邊緣擷取層 (Agent)]
        ADB[ADB Commands]
        TD[tidevice Commands]
        SCRCPY[scrcpy]
    end

    subgraph Backend Layer [後端服務 (Python/FastAPI)]
        AP[FastAPI Server]
        MO[Monitor Logic]
        WS[WebSocket /ws/perf]
        WS_CTL[WebSocket /ws/control]
        WS_STR[WebSocket /ws/stream]
    end

    subgraph Frontend Layer [前端看板 (React/Vite)]
        UI[Web Dashboard]
        CH[Recharts Charts]
        ST[Data Storage / CSV Export]
        CV[Canvas / jmuxer]
    end

    A -->|USB| ADB
    I -->|USB| TD
    A -->|USB| SCRCPY
    
    ADB -->|top, dumpsys, gfxinfo| MO
    TD -->|perf.start(), instruments| MO
    SCRCPY -->|H.264 Binary| WS_STR
    
    MO -->|Regex 解析清洗| AP
    AP -->|JSON 格式化| WS
    
    WS <-->|即時雙向通訊 (效能指標)| UI
    WS_CTL <-->|JSON 觸控指令 (action, x, y)| CV
    WS_STR -->|Binary H.264| CV
    
    UI --> CH
    UI --> ST
    CV -->|ADB input commands| ADB
```

## 2. 目錄結構 (Directory Structure)

- `backend/`: 負責數據採集與 WebSocket 服務的 Python 程式碼
  - `server.py`: FastAPI 啟動入口與路由定義 (含 `/ws/perf`, `/ws/stream`, `/ws/control`)
  - `monitor.py`: ADB 與 tidevice 資料採集、解析邏輯
  - `requirements.txt`: Python 相依套件列表
- `frontend/`: 負責資料即時視覺化的 React SPA
  - `src/App.jsx`: 儀表板主要介面與元件
  - `src/components/DeviceScreen.jsx`: 負責 H.264 畫面解碼 (jmuxer) 與觸控事件攔截
  - `src/hooks/useWebSocket.js`: WebSocket 連線與數據滑動視窗狀態管理
  - `src/index.css`: 自訂高質感樣式 (Vanilla CSS)
- `ARCHITECTURE.md`: 專案核心架構與設計文件

## 3. 核心模組職責

- **Monitor (數據採集模組)**: 每秒一次 (1 Hz) 向設備下發命令，萃取 CPU、Memory 與 FPS 數據。具備防呆機制捕捉異常（如斷線、套件不存在）。
- **WebSocket (通訊模組)**: 確保低延遲地推送數據給前端。當採集發生錯誤時，回傳 `status_code: 500` 給前端警示。新增 `/ws/stream` 與 `/ws/control` 處理畫面與觸控。
- **UI Dashboard (視覺化模組)**: 提供即時指標卡片、時序折線圖（60 秒視窗），並包含控制面板進行測式記錄。
- **Remote Control & Streaming (遠端控制與串流)**: 透過 scrcpy 將手機畫面以低延遲 H.264 傳至前端，並將前端 Canvas 點擊與滑動事件透過座標映射，使用 ADB 下發至手機執行。
