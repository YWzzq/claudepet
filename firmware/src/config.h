#pragma once

// ── 设备标识 ──
#define DEVICE_NAME  "agentpet"   // mDNS 注册后可访问 http://agentpet.local
#define HTTP_PORT    80

// ── ST7789 接线（交接文档第 3 节）──
#define PIN_LCD_SCK   12
#define PIN_LCD_MOSI  11
#define PIN_LCD_CS    10
#define PIN_LCD_DC    13
#define PIN_LCD_RST   14
#define PIN_LCD_BL    21   // V0 硬件上 BLK 直接接 3V3 常亮；以后改接 GPIO21 可 PWM 调光

// ── 板载状态灯 ──
#define PIN_RGB_LED 48       // 板载 WS2812
#define LED_MAX_BRIGHTNESS 16 // 亮度上限 0~255（≈6%，WS2812 很亮，室内够用不刺眼）

// ── 状态兜底 ──
#define STATE_TIMEOUT_MS  (90 * 1000UL)   // 超过这么久没有任何新事件 → 回 idle
#define DONE_HOLD_MS      (5 * 1000UL)    // done 表情展示时长，之后自动回 idle
#define WIFI_RETRY_MS     (10 * 1000UL)   // Wi-Fi 断线重连检查间隔

// ── 显示开关 ──
// 1 = 驱动 ST7789 真屏 / Wokwi 仿真屏；0 = 只打串口日志
// （当前屏幕未接线，先开启待命；插上屏幕后按 RST 即点亮）
#define AGENTPET_HAS_DISPLAY 1

// IPS 屏颜色反转：大多数 1.54" ST7789 IPS 模块需要 1（否则黑变白）。
// 注意：Wokwi 仿真屏强制 IPS 反转且处理方式不同，仿真用 simdemo 固件（invert=0 + rotation=0）。
// 真机若反色，在 1/0 之间切换试出正确值。
#ifndef LCD_INVERT
#define LCD_INVERT 1
#endif

// 屏幕旋转方向 0~3，按摆件安装方向调整
#ifndef LCD_ROTATION
#define LCD_ROTATION 2
#endif
