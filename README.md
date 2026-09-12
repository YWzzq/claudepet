# AgentPet V0

桌面 AI Agent 状态摆件：电脑端 Claude Code / Codex 的状态经局域网 Wi-Fi 推到
ESP32-S3，在 1.54" ST7789（240×240）上以桌宠表情实时呈现。

架构总览见 [docs/architecture.png](docs/architecture.png)（由 `docs/draw_architecture.py` 生成）。

## 目录结构

```
agentpet/
├── firmware/            # ESP32-S3 固件（PlatformIO + Arduino，已编译通过）
│   ├── platformio.ini
│   ├── wokwi.toml       # Wokwi 仿真入口
│   ├── diagram.json     # Wokwi 仿真接线
│   └── src/
│       ├── main.cpp     # Wi-Fi + mDNS + HTTP Server + 状态机
│       ├── pet_state.h  # 8 状态定义（与模拟器一一对应）
│       ├── display.cpp  # 矢量表情逐帧渲染（黑底彩五官，整帧推屏防闪烁）
│       ├── config.h     # 引脚 / 超时 / 设备名 / 显示开关
│       └── secrets.h.example  # 复制为 secrets.h 填 Wi-Fi
├── simulator/           # 浏览器表情模拟器（纯静态，直接打开）
├── bridge/              # Python Bridge（事件驱动推送）
│   ├── agentpet_bridge.py   # 规则引擎归一化 + session 仲裁 + 心跳
│   ├── mapping.json         # 事件→状态映射 / 优先级 / 超时（改文件热加载）
│   ├── webui.html           # 可视化配置台（bridge 自动托管）
│   └── test_bridge.py       # 单元测试（python3 test_bridge.py）
├── hooks/               # Claude Code / Codex hooks
│   ├── agentpet_hook.py     # 通用转发脚本（fire-and-forget，离线落盘）
│   └── install_hooks.py     # 一键安装器（自动备份、幂等）
├── tools/
│   └── virtual_device.py    # 虚拟 ESP32：终端表情脸，不插板子跑通全链路
└── docs/
```

## 快速开始

### 1. 表情模拟器（不需要硬件）

直接用浏览器打开 `simulator/index.html`：
8 个状态按钮切换、3 秒自动轮播、可调 `label` 和 `source`，
下方实时显示对应的 `POST /api/v1/state` 请求体。

### 2. 固件

```bash
pip install platformio
cp firmware/src/secrets.h.example firmware/src/secrets.h   # 填入 Wi-Fi
cd firmware
pio run -t upload            # 烧录（CH343P 串口，可能需要 -u 指定端口）
pio device monitor           # 看日志
```

### 3. Python Bridge（V0.5）

```bash
cd bridge
python3 test_bridge.py            # 16 个单元测试
python3 agentpet_bridge.py --demo # 演示：双会话 + 优先级抢占 + done 过期（约 16s）
python3 agentpet_bridge.py        # 正常运行，推送 http://agentpet.local
python3 agentpet_bridge.py --host 192.168.1.23   # 或手动指定设备 IP
```

手动喂一个事件（模拟 hook）：

```bash
curl -X POST http://127.0.0.1:18787/hook \
     -d '{"hook_event_name":"PreToolUse","tool_name":"Edit","session_id":"test"}'
curl http://127.0.0.1:18787/health
```

仲裁规则：`waiting > error > done > writing > shell > reading > thinking > idle`，
同优先级新的赢；done 停留 5s 后自动让位；90s 无事件的 session 丢弃。
20s 心跳兜底喂固件的 90s 超时。事件到达即时推送（事件驱动，非轮询）。

### 4. Hooks 一键安装（V0.6/V0.7）

```bash
python3 hooks/install_hooks.py             # claude + codex 都装
python3 hooks/install_hooks.py --claude    # 只装 Claude Code
```

- 安装器自动备份原配置（`.bak-时间戳`），只增不删、重复运行幂等
- hook 脚本 0.5s 超时 fire-and-forget，bridge 不在线时事件落盘
  `~/.agentpet/missed-hooks.jsonl`，绝不拖慢 CLI
- 端口冲突时：bridge `--port XXXX`，并设环境变量
  `AGENTPET_BRIDGE=http://127.0.0.1:XXXX/hook`
- 验证：开着 `bridge --dry-run`，正常使用 Claude Code，就能看到真实状态流

### 5. 用 curl 直接驱动固件（V0.4 验收，不经过 bridge）

```bash
curl -X POST http://agentpet.local/api/v1/state \
     -H 'Content-Type: application/json' \
     -d '{"source":"claude","state":"writing","label":"Edit"}'

curl http://agentpet.local/api/v1/health
```

### 6. 虚拟设备：不插板子跑通全链路

```bash
python3 tools/virtual_device.py 8080                                # 终端 A：虚拟 ESP32
AGENTPET_HOST=127.0.0.1:8080 python3 bridge/agentpet_bridge.py      # 终端 B：bridge 指向它
# 正常使用 Claude Code / Codex（或用 curl 喂 hook），终端 A 实时画表情脸
```

### 7. Wokwi 仿真（没有板子也能跑固件）

```bash
# 1) secrets.h 里 SSID 填 Wokwi-GUEST，密码留空
# 2) 编译 + 启动仿真（二选一）：
cd firmware && pio run
npm i -g @wokwi/cli && wokwi-cli      # 命令行方式
# 或 VS Code 装 Wokwi 扩展，打开 diagram.json 点播放
```

说明：
- **服务器仿真已部署**：wokwi-cli v0.26.1 装在服务器 `/usr/local/bin`，
  固件与配置在 `/root/agentpet/`。拿到 token 后：
  `WOKWI_CLI_TOKEN=<token> /root/agentpet/run_sim.sh`
- 本地跑也可以：`npm i -g` 不可用（CLI 不在 npm 上），用官方脚本
  `curl -L https://wokwi.com/ci/install.sh | sh`
- Wokwi 没有官方 ST7789 零件，`diagram.json` 用 `wokwi-ili9341` 代演
  （ST77xx 命令集兼容，社区通行做法；仿真屏下方留黑边属正常现象）
- wokwi-cli 自带虚拟 IoT Gateway，仿真里的固件可以访问外网乃至本机 bridge
- 仿真若颜色反色，调 `display.cpp` 里初始化后的反转设置即可

## 状态协议 v1

`POST /api/v1/state`

```json
{"source": "claude", "state": "writing", "label": "Edit", "session_id": "abc123"}
```

| state | 含义 | 表情（黑底 = 屏幕不显示，亮起的只有彩色五官） |
|---|---|---|
| idle | 空闲/睡觉 | 灰蓝：闭眼 ∪ + 飘 z |
| thinking | 思考 | 紫：眼神飘 + 平嘴 + "..." |
| reading | 读取代码 | 蓝：眼睛左右扫 |
| writing | 编辑/写代码 | 绿：眼睛向下 + o 嘴 |
| shell | 执行命令 | 青：嘴 = `> _` 提示符闪烁 |
| waiting | 等待确认/授权 | 琥珀：瞪大眼 + 嘴 = 大问号 |
| done | 任务完成 | 翠绿：笑眼 ∩ + 大笑嘴（5s 后自动回 idle） |
| error | 异常/失败 | 红：X 眼 + 波浪嘴 + 轻微抖动 |

`GET /api/v1/health` 返回：state / state_for_s / source / label / session_id /
uptime_s / wifi / rssi / heap / ip。

兜底规则：90 秒没有任何事件自动回 idle；done 停留 5 秒回 idle。

## 状态配方系统（V1.0）

板子内置"配方库"（NVS 持久化，断电不丢），出厂预置 8 个状态，支持动态增删改：

```bash
# 列出板上全部状态
curl http://agentpet.local/api/v1/states
# 新增自定义状态（颜色 + 灯效 + 周期）
curl -X PUT http://agentpet.local/api/v1/states/tea \
     -H 'Content-Type: application/json' \
     -d '{"led":{"color":"#3BC4E8","mode":"breath","period":1500}}'
# 查看 / 删除
curl http://agentpet.local/api/v1/states/tea
curl -X DELETE http://agentpet.local/api/v1/states/tea
```

灯效 mode：`steady` 常亮 / `breath` 呼吸 / `blink` 闪烁 / `double` 双闪，
period 50~20000ms（steady 忽略）。预置状态可覆盖更新。

**bridge 事件映射**同样数据化（`bridge/mapping.json`）：规则（source/event/tool 通配/字段匹配）
→ 状态、优先级表、超时。改文件保存即热加载，不用重启。

### 可视化配置台（V1.2）

bridge 跑起来后，浏览器打开 **http://localhost:18787/ui**：

- 左栏：状态配方管理——列表点选、颜色拾取器、灯效下拉、周期滑杆，LED 实时预览，
  保存直接写入板子 NVS；可新增/删除状态、一键试灯
- 右栏：事件绑定规则编辑（mapping.json），保存即热加载
- 板子固件已开 CORS，网页可跨域直连板子；自动从 bridge 获取板子 IP

## 屏幕接线（交接文档第 3 节）

| ST7789 | ESP32-S3 | 备注 |
|---|---|---|
| VCC / GND | 3V3 / GND | |
| SCK | GPIO12 | |
| MOSI | GPIO11 | |
| CS | GPIO10 | |
| DC | GPIO13 | |
| RST | GPIO14 | |
| BLK | 3V3（V0） | 后续可改 GPIO21 PWM 调光 |

避开：GPIO48（板载 RGB）、GPIO0（BOOT）、GPIO19/20（USB）、GPIO43/44（串口）、
GPIO35/36/37（N16R8 Octal PSRAM 占用）。

## 路线图

- [x] V0.1 固件骨架：Wi-Fi + mDNS + HTTP + 状态机（编译通过）
- [x] V0.2 浏览器 240×240 表情模拟器（8 状态黑底彩五官，动画可调）
- [ ] V0.3 真机点亮 ST7789 —— 代码就绪（`AGENTPET_HAS_DISPLAY=1` 已实现），等板子验证 rotation / 颜色顺序
- [x] V0.4 固件矢量表情：与模拟器同一套参数移植为 Adafruit GFX（编译通过，真机观感待验证）
- [x] V0.5 Python Bridge：归一化 + session 优先级仲裁 + 心跳 + mDNS 解析（16 测试通过，事件驱动即时推送）
- [x] V0.6 Claude Code hooks：7 事件转发 + 一键安装器（沙箱安装 + 端到端验证通过）
- [x] V0.7 Codex hooks：事件归一化 + 安装器（Codex 配置格式随版本演进，不生效时按官方文档微调 `hooks/install_hooks.py`）
- [ ] V0.8 外壳、动画打磨、可选电池版
- [x] V1.0 状态配方系统：配方 NVS 持久化 + GET/PUT/DELETE /states API + bridge 规则引擎（mapping.json 热加载）
- [ ] V1.1 屏幕表情配方化（配方 screen 字段已预留）
- [ ] V1.2 可视化配置台（bridge 自带网页 UI + 实时预览）

## 主要参考

- [clawd-mochi-esp32s3](https://github.com/TangYifu/clawd-mochi-esp32s3)：硬件完全一致
  （ESP32-S3 + 1.54" ST7789 240×240），ST7789 初始化参数与点屏细节第一参考
- [cc-mochi](https://github.com/alvis-HaoH/cc-mochi)：Claude/Codex hooks 一键安装器、
  事件归一化映射表、session 优先级、表情预览工具思路
- [VibeMonitor](https://github.com/austingregoryus/VibeMonitor)：Python Bridge、局域网 HTTP
- [Tiny Engineer](https://github.com/jamro/tiny-engineer)："设备只懂 REST" 的简单 API 设计
- [AgentDeck](https://github.com/puritysb/AgentDeck)：未来多 Agent / 多设备架构参考
- HachimoDock：桌宠 UI 与产品形态参考
