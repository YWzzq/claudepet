#include "display.h"
#include "config.h"
#include <math.h>

#if AGENTPET_HAS_DISPLAY

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <ArduinoJson.h>

#define RGB565(r, g, b) ((uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))

static SPIClass lcdSPI(HSPI);
static Adafruit_ST7789 lcd(&lcdSPI, PIN_LCD_CS, PIN_LCD_DC, PIN_LCD_RST);

// ── 与 simulator/webui 同一套几何与配色参数 ──
static const uint16_t C_BLACK = 0x0000;
static const uint16_t C_WHITE = 0xFFFF;

static const int EYE_Y = 96, EYE_DX = 38, EYE_R = 14;
static const int MOUTH_Y = 156;
static const int LW = 9;
static const int W = 240, H = 240;

// ── 屏幕配方参数 ──
struct ScreenParams {
  uint16_t bg = C_BLACK, fg = C_WHITE;
  String eye = "open";    // open wide sleep happy x heart spiral angry
  String anim = "still";  // still look scan down
  String mouth = "flat";  // none flat smile o wave frown prompt question tongue
  String extra = "none";  // none dots z tears hearts blush glasses
  bool shake = false;
};

static ScreenParams gSp;
static String gName = "idle", gLabel = "";
static GFXcanvas16 *gCv = nullptr;

static GFXcanvas16 &cv() { return *gCv; }

static uint16_t hexRgb565(const char* hex) {
  if (!hex || strlen(hex) != 7 || hex[0] != '#') return 0xFFFF;
  long v = strtol(hex + 1, nullptr, 16);
  return (uint16_t)(((v >> 16) & 0xF8) << 8 | ((v >> 8) & 0xFC) << 3 | ((v & 0xFF) >> 3));
}

// ── 基础绘制原语 ──
static void thickLine(int x0, int y0, int x1, int y1, int w, uint16_t c) {
  float dx = x1 - x0, dy = y1 - y0;
  float len = sqrtf(dx * dx + dy * dy);
  int half = w / 2;
  if (len < 0.5f) { cv().fillCircle(x0, y0, half + 1, c); return; }
  float nx = -dy / len, ny = dx / len;
  for (int i = -half; i <= half; i++) {
    cv().drawLine((int)lroundf(x0 + nx * i), (int)lroundf(y0 + ny * i),
                  (int)lroundf(x1 + nx * i), (int)lroundf(y1 + ny * i), c);
  }
}

static void thickArc(int cx, int cy, int r, float a0, float a1, int w, uint16_t c) {
  for (float a = a0; a <= a1; a += 3.0f) {
    float rad = a * DEG_TO_RAD;
    cv().fillCircle((int)lroundf(cx + cosf(rad) * r), (int)lroundf(cy + sinf(rad) * r), w / 2, c);
  }
}

static uint16_t dim(uint16_t c) { return (uint16_t)((c >> 1) & 0xF7DE); }

static void eyeOpen(int x, int y, int r, uint16_t c) {
  cv().fillCircle(x, y, r, c);
  cv().fillCircle(x - r * 3 / 10, y - r * 3 / 10 - 1, r / 4 + 1, C_WHITE);
}

static void eyeLine(int x, int y, uint16_t c) { thickLine(x - 10, y, x + 10, y, LW, c); }

static void eyeSleep(int x, int y, uint16_t c) { thickArc(x, y - 6, 16, 25, 155, LW, c); }

static void eyeHappy(int x, int y, uint16_t c) { thickArc(x, y + 8, 16, 205, 335, LW, c); }

static void eyeX(int x, int y, uint16_t c) {
  thickLine(x - 11, y - 11, x + 11, y + 11, LW, c);
  thickLine(x + 11, y - 11, x - 11, y + 11, LW, c);
}

static void drawHeart(int x, int y, float s, uint16_t c) {
  cv().fillCircle((int)(x - s * 0.5), (int)(y - s * 0.3), (int)(s * 0.5), c);
  cv().fillCircle((int)(x + s * 0.5), (int)(y - s * 0.3), (int)(s * 0.5), c);
  cv().fillTriangle((int)(x - s * 0.95), (int)(y - s * 0.02),
                    (int)(x + s * 0.95), (int)(y - s * 0.02),
                    x, (int)(y + s * 0.8), c);
}

static void eyeHeart(int x, int y, uint16_t c) { drawHeart(x, y, 11, c); }

static void eyeSpiral(int x, int y, uint16_t c) {
  for (float a = 0; a <= 720; a += 14) {
    float rad = a * DEG_TO_RAD;
    float rr = 2 + (a / 720.0f) * 12;
    cv().fillCircle((int)lroundf(x + cosf(rad) * rr), (int)lroundf(y + sinf(rad) * rr), 2, c);
  }
}

static void browAngry(int x, int y, uint16_t c, bool left) {
  if (left) thickLine(x - 12, y - 24, x + 10, y - 15, LW - 1, c);
  else      thickLine(x + 12, y - 24, x - 10, y - 15, LW - 1, c);
}

static void mouthFlat(int x, int y, uint16_t c) { thickLine(x - 22, y, x + 22, y, LW, c); }

static void mouthSmile(int x, int y, uint16_t c) { thickArc(x, y - 10, 26, 20, 160, LW, c); }

static void mouthO(int x, int y, uint16_t c) { cv().fillCircle(x, y, 9, c); }

static void mouthFrown(int x, int y, uint16_t c) { thickArc(x, y + 12, 16, 205, 335, LW, c); }

static void mouthWave(int x, int y, uint16_t c) {
  const int pts[5][2] = {{x - 24, y}, {x - 12, y - 10}, {x, y}, {x + 12, y + 10}, {x + 24, y}};
  int px = pts[0][0], py = pts[0][1];
  for (int seg = 0; seg < 2; seg++) {
    const int *p0 = pts[seg * 2], *p1 = pts[seg * 2 + 1], *p2 = pts[seg * 2 + 2];
    for (float k = 0.1f; k <= 1.0f; k += 0.1f) {
      float mt = 1.0f - k;
      int nx = (int)(mt * mt * p0[0] + 2 * mt * k * p1[0] + k * k * p2[0]);
      int ny = (int)(mt * mt * p0[1] + 2 * mt * k * p1[1] + k * k * p2[1]);
      thickLine(px, py, nx, ny, LW - 1, c);
      px = nx; py = ny;
    }
  }
}

static const uint16_t C_TONGUE_PINK = RGB565(0xFF, 0x6B, 0x9D);
static const uint16_t C_TEAR_BLUE   = RGB565(0x7E, 0xC8, 0xFF);
static const uint16_t C_BLUSH_PINK  = RGB565(0xF7, 0x9E, 0xB5);
static const uint16_t C_INK         = RGB565(0x20, 0x24, 0x2B);

static void mouthTongue(int x, int y, uint16_t c) {
  mouthSmile(x, y, c);
  cv().fillRoundRect(x - 8, y + 2, 16, 13, 5, C_TONGUE_PINK);
  cv().drawRoundRect(x - 8, y + 2, 16, 13, 5, C_INK);
}

// ── 出厂屏幕表情表（16 态：名字 → 默认屏幕参数；配方带 screen 时逐字段覆盖）──
struct DefaultScreen {
  const char* name;
  const char* fg;
  const char* eye;    // open wide sleep happy x heart spiral angry
  const char* anim;   // still look scan down
  const char* mouth;  // none flat smile o wave frown prompt question tongue
  const char* extra;  // none dots z tears hearts blush glasses
  bool shake;
};
static const DefaultScreen DEFAULT_SCREEN[] = {
    {"idle",     "#8C9BAB", "sleep",  "still", "none",     "z",      false},
    {"thinking", "#9D8FFF", "open",   "look",  "flat",     "dots",   false},
    {"reading",  "#5AA2F0", "open",   "scan",  "flat",     "none",   false},
    {"writing",  "#4FCF84", "open",   "down",  "o",        "none",   false},
    {"shell",    "#3BB8E8", "open",   "still", "prompt",   "none",   false},
    {"waiting",  "#FFB03A", "wide",   "still", "question", "none",   false},
    {"done",     "#3BD692", "happy",  "still", "smile",    "none",   false},
    {"error",    "#F04848", "x",      "still", "wave",     "none",   true },
    {"angry",    "#FF8C42", "angry",  "still", "frown",    "none",   false},
    {"love",     "#FF6B9D", "heart",  "still", "smile",    "hearts", false},
    {"cry",      "#5B8DEF", "sleep",  "still", "frown",    "tears",  false},
    {"dizzy",    "#B08BE8", "spiral", "still", "wave",     "none",   false},
    {"cool",     "#38E0C8", "open",   "still", "smile",    "glasses",false},
    {"shy",      "#FF9EB5", "happy",  "still", "o",        "blush",  false},
    {"tongue",   "#FFD93D", "open",   "still", "tongue",   "none",   false},
    {"shock",    "#7FD4FF", "wide",   "still", "o",        "none",   false},
};
static const size_t N_DEFAULT_SCREEN = sizeof(DEFAULT_SCREEN) / sizeof(DEFAULT_SCREEN[0]);

static void applyDefaultScreen(const String& name) {
  gSp = ScreenParams();
  for (size_t i = 0; i < N_DEFAULT_SCREEN; i++) {
    if (name == DEFAULT_SCREEN[i].name) {
      gSp.fg = hexRgb565(DEFAULT_SCREEN[i].fg);
      gSp.eye = DEFAULT_SCREEN[i].eye;
      gSp.anim = DEFAULT_SCREEN[i].anim;
      gSp.mouth = DEFAULT_SCREEN[i].mouth;
      gSp.extra = DEFAULT_SCREEN[i].extra;
      gSp.shake = DEFAULT_SCREEN[i].shake;
      return;
    }
  }
}

void displaySetStateByName(const String& name, const String& label, const String& screenJson) {
  gName = name;
  gLabel = label;
  applyDefaultScreen(name);
  // 配方里带 screen 对象时，逐字段覆盖默认值
  if (screenJson.length()) {
    JsonDocument doc;
    if (!deserializeJson(doc, screenJson)) {
      JsonObject s = doc["screen"].as<JsonObject>();
      if (!s.isNull()) {
        if (s["bg"].is<const char*>()) gSp.bg = hexRgb565(s["bg"] | "#000000");
        if (s["fg"].is<const char*>()) gSp.fg = hexRgb565(s["fg"] | "#FFFFFF");
        if (s["eye"].is<const char*>()) gSp.eye = String(s["eye"] | "open");
        if (s["anim"].is<const char*>()) gSp.anim = String(s["anim"] | "still");
        if (s["mouth"].is<const char*>()) gSp.mouth = String(s["mouth"] | "flat");
        if (s["extra"].is<const char*>()) gSp.extra = String(s["extra"] | "none");
        gSp.shake = s["shake"] | false;
      }
    }
  }
  displayRender();  // 立即出第一帧
}

// ── 参数化逐帧渲染 ──
void displayRender() {
  if (!gCv) return;
  float t = millis() / 1000.0f;
  GFXcanvas16 &c = cv();

  c.fillScreen(gSp.bg);
  bool blink = fmodf(t + 1.3f, 3.6f) < 0.12f;

  uint16_t fg = gSp.fg;
  int lx = 120 - EYE_DX, rx = 120 + EYE_DX, ey = EYE_Y, my = MOUTH_Y;

  // ── 眼睛 ──
  if (gSp.eye == "sleep") { eyeSleep(lx, ey, fg); eyeSleep(rx, ey, fg); }
  else if (gSp.eye == "happy") { eyeHappy(lx, ey, fg); eyeHappy(rx, ey, fg); }
  else if (gSp.eye == "x") { eyeX(lx, ey, fg); eyeX(rx, ey, fg); }
  else if (gSp.eye == "heart") { eyeHeart(lx, ey, fg); eyeHeart(rx, ey, fg); }
  else if (gSp.eye == "spiral") { eyeSpiral(lx, ey, fg); eyeSpiral(rx, ey, fg); }
  else if (gSp.eye == "angry") {
    if (blink) { eyeLine(lx, ey, fg); eyeLine(rx, ey, fg); }
    else { eyeOpen(lx, ey, EYE_R, fg); eyeOpen(rx, ey, EYE_R, fg); }
    browAngry(lx, ey, fg, true);
    browAngry(rx, ey, fg, false);
  } else {  // open / wide
    if (blink) { eyeLine(lx, ey, fg); eyeLine(rx, ey, fg); }
    else {
      int r = (gSp.eye == "wide") ? EYE_R + 4 : EYE_R;
      float dx = 0, dy = 0;
      if (gSp.anim == "look") { dx = sinf(t * 0.7f) * 6 - 2; dy = -6; }
      else if (gSp.anim == "scan") { dx = sinf(t * 2.4f) * 8; dy = 3; }
      else if (gSp.anim == "down") { dy = 5; }
      eyeOpen(lx + (int)dx, ey + (int)dy, r, fg);
      eyeOpen(rx + (int)dx, ey + (int)dy, r, fg);
    }
  }

  // ── 嘴 ──
  if (gSp.mouth == "flat") mouthFlat(120, my, fg);
  else if (gSp.mouth == "smile") mouthSmile(120, my, fg);
  else if (gSp.mouth == "o") mouthO(120, my, fg);
  else if (gSp.mouth == "wave") mouthWave(120, my, fg);
  else if (gSp.mouth == "frown") mouthFrown(120, my, fg);
  else if (gSp.mouth == "tongue") mouthTongue(120, my, fg);
  else if (gSp.mouth == "prompt") {
    c.setTextColor(fg); c.setTextSize(3); c.setCursor(84, my - 13);
    c.print(fmodf(t, 1.0f) < 0.55f ? "> _" : ">  ");
  } else if (gSp.mouth == "question") {
    c.setTextColor(fg); c.setTextSize(5);
    c.setCursor(102, (int)(my - 22 + sinf(t * 3) * 3)); c.print('?');
  }

  // ── 附加 ──
  if (gSp.extra == "dots") {
    for (int i = 0; i < 3; i++) {
      bool on = sinf(t * 2.4f - i * 0.7f) > -0.2f;
      c.fillCircle(178 + i * 14, 40, 4, on ? fg : dim(fg));
    }
  } else if (gSp.extra == "z" && fmodf(t, 1.4f) < 0.9f) {
    c.setTextColor(fg); c.setTextSize(3); c.setCursor(188, 32); c.print('z');
  } else if (gSp.extra == "tears") {
    for (int i = 0; i < 2; i++) {
      int ex = (i == 0) ? lx : rx;
      float ph = fmodf(t * 30 + i * 22, 45);
      c.fillCircle(ex, (int)(ey + 14 + ph), 3, C_TEAR_BLUE);
    }
  } else if (gSp.extra == "hearts") {
    for (int i = 0; i < 2; i++) {
      float a = sinf(t * 1.8f + i * 2.2f);
      drawHeart(60 + i * 120, (int)(44 - a * 8), 8 + 2 * a + 2, fg);
    }
  } else if (gSp.extra == "blush") {
    c.fillCircle(lx - 14, ey + 18, 7, C_BLUSH_PINK);
    c.fillCircle(rx + 14, ey + 18, 7, C_BLUSH_PINK);
  } else if (gSp.extra == "glasses") {
    c.fillRect(lx - 17, ey - 11, 34, 22, C_BLACK);
    c.fillRect(rx - 17, ey - 11, 34, 22, C_BLACK);
    c.drawRoundRect(lx - 17, ey - 11, 34, 22, 5, fg);
    c.drawRoundRect(rx - 17, ey - 11, 34, 22, 5, fg);
    thickLine(lx + 17, ey - 6, rx - 17, ey - 6, 4, fg);
    c.drawLine(lx - 17, ey - 8, lx - 34, ey - 14, fg);
    c.drawLine(rx + 17, ey - 8, rx + 34, ey - 14, fg);
  }

  lcd.drawRGBBitmap(0, 0, c.getBuffer(), W, H);
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

  // 与模拟器/webui 同一套状态配色（LED 颜色由配方决定，此处为屏幕五官默认色表）
  gCv = new GFXcanvas16(W, H);  // 240*240*2 = 112.5KB
  if (!gCv || gCv->getBuffer() == nullptr) {
    Serial.println("[lcd] frame buffer alloc failed, display disabled");
    delete gCv;
    gCv = nullptr;
  }
}

#else  // 没有屏幕：渲染降级为串口日志

void displayInit() {}

void displaySetStateByName(const String& name, const String& label, const String& screenJson) {
  Serial.printf("[lcd] (stub) %s%s%s\n", name.c_str(),
                label.length() ? " | " : "", label.c_str());
}

void displayRender() {}

#endif
