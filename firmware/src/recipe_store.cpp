#include "recipe_store.h"
#include <Preferences.h>

// NVS 键规则：配方键 = "st_" + 名字（NVS 键 ≤15 字符），索引键 = "idx"
static const char* NS = "recipes";
static const char* IDX_KEY = "idx";

// ── 出厂预置状态（8 基础 + 8 经典表情，与 simulator 配色一致）──
struct DefaultRecipe {
  const char* name;
  const char* color;
  const char* mode;
  uint16_t period;
};
static const DefaultRecipe DEFAULTS[] = {
    {"idle",     "#646E7D", "steady", 0},
    {"thinking", "#9D8FFF", "breath", 2400},
    {"reading",  "#5AA2F0", "steady", 0},
    {"writing",  "#4FCF84", "double", 2000},
    {"shell",    "#3BB8E8", "blink",  800},
    {"waiting",  "#FFB03A", "blink",  500},
    {"done",     "#3BD692", "breath", 1200},
    {"error",    "#F04848", "blink",  300},
    {"angry",    "#FF8C42", "blink",  700},
    {"love",     "#FF6B9D", "breath", 1600},
    {"cry",      "#5B8DEF", "blink",  1100},
    {"dizzy",    "#B08BE8", "breath", 900},
    {"cool",     "#38E0C8", "steady", 0},
    {"shy",      "#FF9EB5", "breath", 2000},
    {"tongue",   "#FFD93D", "double", 1600},
    {"shock",    "#7FD4FF", "blink",  400},
};
static const size_t N_DEFAULTS = sizeof(DEFAULTS) / sizeof(DEFAULTS[0]);

static String defaultJson(const DefaultRecipe& d) {
  String s = "{\"led\":{\"color\":\"";
  s += d.color;
  s += "\",\"mode\":\"";
  s += d.mode;
  s += "\",\"period\":";
  s += String(d.period);
  s += "}}";
  return s;
}

static Preferences& prefs() {
  static Preferences p;
  return p;
}

bool RecipeStore::validName(const String& name) {
  if (name.length() == 0 || name.length() > 12) return false;
  for (size_t i = 0; i < name.length(); i++) {
    char c = name[i];
    if (!(isalnum(c) || c == '_')) return false;
  }
  return true;
}

bool RecipeStore::parseRecipe(const String& name, const String& body, StateRecipe& out, String& err) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) { err = "invalid json"; return false; }
  if (!doc["led"].is<JsonObject>()) { err = "missing led"; return false; }

  const char* color = doc["led"]["color"] | "";
  int r = -1, g = -1, b = -1;
  if (sscanf(color, "#%02x%02x%02x", &r, &g, &b) != 3 || strlen(color) != 7) {
    err = "color must be #RRGGBB";
    return false;
  }
  const char* mode = doc["led"]["mode"] | "steady";
  if (strcmp(mode, "steady") && strcmp(mode, "breath") &&
      strcmp(mode, "blink") && strcmp(mode, "double")) {
    err = "mode must be steady/breath/blink/double";
    return false;
  }
  long period = doc["led"]["period"] | 0;
  if (strcmp(mode, "steady") != 0 && (period < 50 || period > 20000)) {
    err = "period must be 50~20000ms";
    return false;
  }

  out.name = name;
  out.led.r = (uint8_t)r;
  out.led.g = (uint8_t)g;
  out.led.b = (uint8_t)b;
  out.led.mode = String(mode);
  out.led.period = (uint16_t)period;
  out.raw = body;
  return true;
}

void RecipeStore::begin() {
  prefs().begin(NS, false);
  seedDefaults();
}

bool RecipeStore::isDefault(const String& name) const {
  for (size_t i = 0; i < N_DEFAULTS; i++)
    if (name == DEFAULTS[i].name) return true;
  return false;
}

void RecipeStore::seedDefaults() {
  // 增量播种：缺哪个补哪个（首次开机全部播种；固件升级新增预置态也会自动补）
  bool added = false;
  for (size_t i = 0; i < N_DEFAULTS; i++) {
    String key = String("st_") + DEFAULTS[i].name;
    if (!prefs().isKey(key.c_str())) {
      prefs().putString(key.c_str(), defaultJson(DEFAULTS[i]));
      added = true;
    }
  }
  if (added || prefs().getString(IDX_KEY, "").length() == 0) saveIndex();
}

void RecipeStore::saveIndex() {
  String idx = "[";
  bool first = true;
  for (size_t i = 0; i < N_DEFAULTS; i++) {
    if (prefs().isKey((String("st_") + DEFAULTS[i].name).c_str())) {
      if (!first) idx += ",";
      idx += "\"" + String(DEFAULTS[i].name) + "\"";
      first = false;
    }
  }
  // 非预置配方：从旧索引里找回
  String raw = prefs().getString(IDX_KEY, "");
  if (raw.length() > 2) {
    JsonDocument doc;
    if (!deserializeJson(doc, raw)) {
      for (JsonVariant v : doc.as<JsonArray>()) {
        String n = v.as<String>();
        if (isDefault(n)) continue;
        if (!prefs().isKey((String("st_") + n).c_str())) continue;
        if (!first) idx += ",";
        idx += "\"" + n + "\"";
        first = false;
      }
    }
  }
  idx += "]";
  prefs().putString(IDX_KEY, idx);
}

bool RecipeStore::has(const String& name) const {
  return const_cast<Preferences&>(prefs()).isKey((String("st_") + name).c_str());
}

bool RecipeStore::get(const String& name, StateRecipe& out) const {
  String raw = const_cast<Preferences&>(prefs()).getString((String("st_") + name).c_str(), "");
  if (raw.length() == 0) return false;
  String err;
  return parseRecipe(name, raw, out, err);
}

bool RecipeStore::put(const String& name, const String& body, String& err) {
  if (!validName(name)) { err = "name must be 1~12 chars [a-zA-Z0-9_]"; return false; }
  StateRecipe r;
  if (!parseRecipe(name, body, r, err)) return false;
  prefs().putString((String("st_") + name).c_str(), body);
  // 更新索引
  String idx = prefs().getString(IDX_KEY, "[]");
  JsonDocument doc;
  deserializeJson(doc, idx);
  JsonArray arr = doc.as<JsonArray>();
  bool exists = false;
  for (JsonVariant v : arr)
    if (v.as<String>() == name) { exists = true; break; }
  if (!exists) {
    arr.add(name);
    String out;
    serializeJson(doc, out);
    prefs().putString(IDX_KEY, out);
  }
  return true;
}

bool RecipeStore::remove(const String& name) {
  String key = String("st_") + name;
  if (!prefs().isKey(key.c_str())) return false;
  if (isDefault(name)) {
    // 预置状态只清空键（下次 begin 会重新播种），不允许长期删除
    prefs().putString(key.c_str(), defaultJson(DEFAULTS[0]));  // 占位防误删，实际由 GUI 层限制
  }
  prefs().remove(key.c_str());
  saveIndex();
  return true;
}

size_t RecipeStore::count() const {
  String idx = const_cast<Preferences&>(prefs()).getString(IDX_KEY, "[]");
  JsonDocument doc;
  deserializeJson(doc, idx);
  return doc.as<JsonArray>().size();
}

String RecipeStore::listJson() const {
  String idx = const_cast<Preferences&>(prefs()).getString(IDX_KEY, "[]");
  JsonDocument idxDoc;
  deserializeJson(idxDoc, idx);
  String out = "{\"states\":{";
  bool first = true;
  for (JsonVariant v : idxDoc.as<JsonArray>()) {
    String n = v.as<String>();
    String key = String("st_") + n;
    String raw = const_cast<Preferences&>(prefs()).getString(key.c_str(), "");
    if (!first) out += ",";
    first = false;
    out += "\"" + n + "\":" + (raw.length() ? raw : "{}");
  }
  out += "}}";
  return out;
}
