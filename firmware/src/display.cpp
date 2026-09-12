#include "display.h"
#include "config.h"
#include "pet_state.h"

#if AGENTPET_HAS_DISPLAY

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <esp_heap_caps.h>
#include <math.h>

static SPIClass lcdSPI(HSPI);
static Adafruit_ST7789 lcd(&lcdSPI, PIN_LCD_CS, PIN_LCD_DC, PIN_LCD_RST);

// ── 与 simulator/index.html 同一套参数 ──
#define RGB565(r, g, b) ((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3))
static const uint16_t C_BLACK = 0x0000;
static const uint16_t C_WHITE = 0xFFFF;
static uint16_t FG[PET_STATE_COUNT];  // 每个状态的五官颜色

static const int EYE_Y = 96, EYE_DX = 38, EYE_R = 14;  // 眼睛布局
static const int MOUTH_Y = 156;                        // 嘴的纵向位置
static const int LW = 9;                               // 五官线条粗细
static const int W = 240, H = 240;

static PetState gState = PET_IDLE;
static String gLabel;
static GFXcanvas16 *gCv = nullptr;  // 全帧缓冲：整帧绘制后一次推屏，避免闪烁

// ── 基础绘制 ──
static GFXcanvas16 &cv() { return *gCv; }

static void thickLine(int x0, int y0, int x1, int y1, int w, uint16_t c) {
  float dx = x1 - x0, dy = y1 - y0;
  float len = sqrtf(dx * dx + dy * dy);
  int half = w / 2;
  if (len < 0.5f) {
    cv().fillCircle(x0, y0, half + 1, c);
    return;
  }
  float nx = -dy / len, ny = dx / len;
  for (int i = -half; i <= half; i++) {
    cv().drawLine((int)lroundf(x0 + nx * i), (int)lroundf(y0 + ny * i),
                  (int)lroundf(x1 + nx * i), (int)lroundf(y1 + ny * i), c);
  }
}

// 厚弧线：沿圆弧撒实心圆点（a0/a1 单位度，屏幕坐标系 y 向下）
static void thickArc(int cx, int cy, int r, float a0, float a1, int w, uint16_t c) {
  for (float a = a0; a <= a1; a += 3.0f) {
    float rad = a * DEG_TO_RAD;
    cv().fillCircle((int)lroundf(cx + cosf(rad) * r), (int)lroundf(cy + sinf(rad) * r),
                    w / 2, c);
  }
}

// 半亮度颜色（565 技巧），用于 "..." 的熄灭态
static uint16_t dim(uint16_t c) { return (c >> 1) & 0xF7DE; }

static void eyeOpen(int x, int y, int r, uint16_t c) {
  cv().fillCircle(x, y, r, c);
  cv().fillCircle(x - r * 3 / 10, y - r * 3 / 10 - 1, r / 4 + 1, C_WHITE);
}

static void eyeLine(int x, int y, uint16_t c) { thickLine(x - 10, y, x + 10, y, LW, c); }

static void eyeSleep(int x, int y, uint16_t c) {   // 闭眼 "∪"
  thickArc(x, y - 6, 16, 25, 155, LW, c);
}

static void eyeHappy(int x, int y, uint16_t c) {  // 开心眯眼 "∩"
  thickArc(x, y + 8, 16, 205, 335, LW, c);
}

static void eyeX(int x, int y, uint16_t c) {
  thickLine(x - 11, y - 11, x + 11, y + 11, LW, c);
  thickLine(x + 11, y - 11, x - 11, y + 11, LW, c);
}

static void mouthFlat(int x, int y, uint16_t c) { thickLine(x - 22, y, x + 22, y, LW, c); }

static void mouthSmile(int x, int y, uint16_t c) { thickArc(x, y - 10, 26, 20, 160, LW, c); }

static void mouthO(int x, int y, uint16_t c) { cv().fillCircle(x, y, 9, c); }

static void mouthWave(int x, int y, uint16_t c) {  // 二次贝塞尔近似波浪嘴
  const int pts[5][2] = {{x - 24, y}, {x - 12, y - 10}, {x, y}, {x + 12, y + 10}, {x + 24, y}};
  int px = pts[0][0], py = pts[0][1];
  for (int seg = 0; seg < 2; seg++) {
    const int *p0 = pts[seg * 2], *p1 = pts[seg * 2 + 1], *p2 = pts[seg * 2 + 2];
    for (float t = 0.1f; t <= 1.0f; t += 0.1f) {
      float mt = 1.0f - t;
      int nx = (int)(mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]);
      int ny = (int)(mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]);
      thickLine(px, py, nx, ny, LW - 1, c);
      px = nx;
      py = ny;
    }
  }
}

static bool blinking(float t) { return fmodf(t + 1.3f, 3.6f) < 0.12f; }

// ── 逐帧渲染 ──
void displayRender() {
  if (!gCv) return;
  if (gState == (PetState)PET_STATE_COUNT) return;  // 自定义状态帧已由 displayShowUnknown 绘制
  float t = millis() / 1000.0f;
  GFXcanvas16 &c = cv();
  c.fillScreen(C_BLACK);  // 黑底 = 屏幕不显示

  // error 整屏轻微抖动（特征整体平移）
  int ox = 0, oy = 0;
  if (gState == PET_ERROR) {
    ox = (int)lroundf(sinf(t * 28.0f) * 2.0f);
    oy = (int)lroundf(cosf(t * 33.0f) * 1.5f);
  }

  uint16_t fg = FG[gState];
  int lx = 120 - EYE_DX + ox, rx = 120 + EYE_DX + ox;
  int my = MOUTH_Y + oy;

  switch (gState) {
    case PET_IDLE:
      eyeSleep(lx, EYE_Y + oy, fg);
      eyeSleep(rx, EYE_Y + oy, fg);
      if (fmodf(t, 1.4f) < 0.9f) {  // 一个飘着的 z
        c.setTextColor(fg);
        c.setTextSize(3);
        c.setCursor(188 + ox, 32 + oy);
        c.print('z');
      }
      break;

    case PET_THINKING: {
      float lookx = sinf(t * 0.7f) * 6.0f - 2.0f;
      eyeOpen((int)(lx + lookx), EYE_Y - 6 + oy, EYE_R, fg);
      eyeOpen((int)(rx + lookx), EYE_Y - 6 + oy, EYE_R, fg);
      for (int i = 0; i < 3; i++) {  // 右上角 "..." 依次点亮
        bool on = sinf(t * 2.4f - i * 0.7f) > -0.2f;
        c.fillCircle(178 + i * 14 + ox, 40 + oy, 4, on ? fg : dim(fg));
      }
      mouthFlat(120 + ox, my, fg);
      break;
    }

    case PET_READING: {
      int dx = (int)(sinf(t * 2.4f) * 8.0f);
      eyeOpen(lx + dx, EYE_Y + 3 + oy, EYE_R - 1, fg);
      eyeOpen(rx + dx, EYE_Y + 3 + oy, EYE_R - 1, fg);
      mouthFlat(120 + ox, my, fg);
      break;
    }

    case PET_WRITING:
      eyeOpen(lx, EYE_Y + 5 + oy, EYE_R - 1, fg);
      eyeOpen(rx, EYE_Y + 5 + oy, EYE_R - 1, fg);
      mouthO(120 + ox, my, fg);
      break;

    case PET_SHELL:
      if (blinking(t)) {
        eyeLine(lx, EYE_Y + oy, fg);
        eyeLine(rx, EYE_Y + oy, fg);
      } else {
        eyeOpen(lx, EYE_Y + oy, EYE_R, fg);
        eyeOpen(rx, EYE_Y + oy, EYE_R, fg);
      }
      c.setTextColor(fg);  // 嘴 = 命令行提示符，光标闪烁
      c.setTextSize(3);
      c.setCursor(84 + ox, my - 13);
      c.print(fmodf(t, 1.0f) < 0.55f ? "> _" : ">  ");
      break;

    case PET_WAITING:
      if (blinking(t)) {
        eyeLine(lx, EYE_Y + oy, fg);
        eyeLine(rx, EYE_Y + oy, fg);
      } else {
        eyeOpen(lx, EYE_Y + oy, EYE_R + 4, fg);
        eyeOpen(rx, EYE_Y + oy, EYE_R + 4, fg);
      }
      c.setTextColor(fg);  // 嘴 = 大问号
      c.setTextSize(5);
      c.setCursor(102 + ox, (int)(my - 22 + sinf(t * 3.0f) * 3.0f));
      c.print('?');
      break;

    case PET_DONE:
      eyeHappy(lx, EYE_Y + oy, fg);
      eyeHappy(rx, EYE_Y + oy, fg);
      mouthSmile(120 + ox, my, fg);
      break;

    case PET_ERROR:
      eyeX(lx, EYE_Y + oy, fg);
      eyeX(rx, EYE_Y + oy, fg);
      mouthWave(120 + ox, my, fg);
      break;

    default:
      break;
  }

  lcd.drawRGBBitmap(0, 0, c.getBuffer(), W, H);
}

void displaySetState(PetState state, const String& label) {
  gState = state;
  gLabel = label;
  // 立即渲染一帧，状态切换零延迟；后续动画交给 displayRender
  displayRender();
}

void displayShowUnknown(const String& name) {
  // 自定义状态（无内置表情）：黑底 + 状态名，V1.1 由配方驱动
  gState = PET_STATE_COUNT;  // 标记为自定义，displayRender 不再画内置表情
  gLabel = name;
#if AGENTPET_HAS_DISPLAY
  if (!gCv) return;
  gCv->fillScreen(0x0000);
  gCv->setTextColor(0xFFFF);
  gCv->setTextSize(2);
  gCv->setCursor(120 - name.length() * 6, 110);
  gCv->print(name);
  lcd.drawRGBBitmap(0, 0, gCv->getBuffer(), 240, 240);
#else
  Serial.printf("[lcd] (stub) custom: %s\n", name.c_str());
#endif
}

void displayInit() {
  lcdSPI.begin(PIN_LCD_SCK, -1, PIN_LCD_MOSI, PIN_LCD_CS);
  lcd.init(240, 240);
  lcd.setRotation(LCD_ROTATION);
  lcd.invertDisplay(LCD_INVERT);  // IPS 屏需要反转，否则黑底显示成白底
  // ESP32 上 writePixels 自带字节序交换，drawRGBBitmap 直接推即可
  lcd.fillScreen(C_BLACK);

  // BLK 接 3V3 时这行无效也无害；改接 GPIO21 后即背光开关
  pinMode(PIN_LCD_BL, OUTPUT);
  digitalWrite(PIN_LCD_BL, HIGH);

  // 与模拟器同一套状态色
  FG[PET_IDLE] = RGB565(0x8C, 0x9B, 0xAB);
  FG[PET_THINKING] = RGB565(0x9D, 0x8F, 0xFF);
  FG[PET_READING] = RGB565(0x5A, 0xA2, 0xF0);
  FG[PET_WRITING] = RGB565(0x4F, 0xCF, 0x84);
  FG[PET_SHELL] = RGB565(0x3B, 0xB8, 0xE8);
  FG[PET_WAITING] = RGB565(0xFF, 0xB0, 0x3A);
  FG[PET_DONE] = RGB565(0x3B, 0xD6, 0x92);
  FG[PET_ERROR] = RGB565(0xF0, 0x48, 0x48);

  gCv = new GFXcanvas16(W, H);  // 240*240*2 = 112.5KB，ESP32-S3 内部 RAM 足够
  if (!gCv || gCv->getBuffer() == nullptr) {
    Serial.println("[lcd] frame buffer alloc failed, display disabled");
    delete gCv;
    gCv = nullptr;
  }
}

#else  // 没有屏幕：渲染降级为串口日志

void displayInit() {}

void displaySetState(PetState state, const String& label) {
  Serial.printf("[lcd] (stub) %s%s%s\n", petStateName(state),
                label.length() ? " | " : "", label.c_str());
}

void displayShowUnknown(const String& name) {
  Serial.printf("[lcd] (stub) custom: %s\n", name.c_str());
}

void displayRender() {}

#endif
