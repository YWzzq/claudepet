#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

// LED 渲染配方（V1.1 会扩展 screen 字段）
struct LedRecipe {
  uint8_t r = 0, g = 0, b = 0;
  String mode = "steady";  // steady / breath / blink / double
  uint16_t period = 0;     // ms，steady 时忽略
};

struct StateRecipe {
  String name;
  LedRecipe led;
  String raw;  // 原始 JSON（含 screen 等扩展字段，V1.1 使用）
};

// 配方库：NVS 持久化存储，断电不丢；首次启动预置 8 个默认状态
class RecipeStore {
 public:
  void begin();  // 初始化 + 首次播种默认配方
  bool has(const String& name) const;
  bool get(const String& name, StateRecipe& out) const;
  // 校验并保存配方 JSON；失败时 err 返回原因
  bool put(const String& name, const String& body, String& err);
  bool remove(const String& name);
  // 返回 {"states":{"idle":{...},...}}；bridge/GUI 同步用
  String listJson() const;
  size_t count() const;

  static bool validName(const String& name);
  static bool parseRecipe(const String& name, const String& body, StateRecipe& out, String& err);

 private:
  void seedDefaults();
  void saveIndex();
  bool isDefault(const String& name) const;

  // Preferences 对象不可拷贝，用指针避免隐式拷贝问题
  void* _prefs = nullptr;
};
