#include "status_led.h"
#include "config.h"
#include <math.h>

enum LedMode : uint8_t { LED_STEADY, LED_BREATH, LED_BLINK, LED_DOUBLE };

static LedRecipe gRecipe;      // 当前配方
static LedMode gMode = LED_STEADY;
static unsigned long gLastRender = 0;

static LedMode parseMode(const String& m) {
  if (m == "breath") return LED_BREATH;
  if (m == "blink") return LED_BLINK;
  if (m == "double") return LED_DOUBLE;
  return LED_STEADY;
}

void ledApplyRecipe(const LedRecipe& r) {
  gRecipe = r;
  gMode = parseMode(r.mode);
  ledRender();  // 立即生效一帧
}

void ledBegin(RecipeStore& store, const String& name) {
  StateRecipe sr;
  if (!store.get(name, sr)) store.get("idle", sr);  // 找不到状态时回落 idle
  ledApplyRecipe(sr.led);
}

void ledRender() {
  unsigned long now = millis();
  if (now - gLastRender < 20) return;  // 20ms 节流（50fps，呼吸更顺滑）
  gLastRender = now;

  unsigned long period = gRecipe.period ? gRecipe.period : 1000;
  unsigned long t = now % period;  // period 已保证 > 0
  uint8_t level;

  switch (gMode) {
    case LED_STEADY:
      level = 255;
      break;
    case LED_BREATH: {  // 余弦呼吸 + gamma²：暗区过渡更绵密不卡顿
      float ph = (now % period) * 6.28318f / period;
      float n = 0.5f - 0.5f * cosf(ph);
      n = n * n;
      level = (uint8_t)(n * 255.0f);
      break;
    }
    case LED_BLINK:  // 半亮半灭
      level = (t < period / 2) ? 255 : 0;
      break;
    case LED_DOUBLE:  // 快两下 + 停顿
      level = (t < 120 || (t >= 240 && t < 360)) ? 255 : 0;
      break;
    default:
      level = 0;
      break;
  }

  // 亮度上限压到 LED_MAX_BRIGHTNESS/255，WS2812 很亮，室内 6% 足够
  uint8_t r = (uint16_t)gRecipe.r * level * LED_MAX_BRIGHTNESS / 65025UL;
  uint8_t g = (uint16_t)gRecipe.g * level * LED_MAX_BRIGHTNESS / 65025UL;
  uint8_t b = (uint16_t)gRecipe.b * level * LED_MAX_BRIGHTNESS / 65025UL;
  neopixelWrite(PIN_RGB_LED, r, g, b);
}
