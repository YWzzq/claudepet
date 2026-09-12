/**
 * AgentPet V1.0 固件
 * Wi-Fi + mDNS + HTTP + 配方驱动状态机
 *
 * 状态不再是写死的枚举：板子内置"配方库"（NVS 持久化，出厂预置 8 态），
 * 收到的 state 名字先查配方库，按配方渲染 LED 与屏幕。
 *
 * 路由：
 *   POST   /api/v1/state            {"state":"writing","source":"claude",...}
 *   GET    /api/v1/states           列出全部状态配方
 *   GET    /api/v1/states/<name>    查看单个配方
 *   PUT    /api/v1/states/<name>    新增/覆盖配方（存 NVS，断电不丢）
 *   DELETE /api/v1/states/<name>    删除配方
 *   GET    /api/v1/health           健康检查
 *
 * 烧录前：复制 src/secrets.h.example 为 src/secrets.h 并填入 Wi-Fi 信息
 */
#include <Arduino.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <ArduinoJson.h>

#include "config.h"
#include "display.h"
#include "pet_state.h"
#include "recipe_store.h"
#include "secrets.h"
#include "status_led.h"

WebServer server(HTTP_PORT);

RecipeStore gRecipes;
String gStateName = "idle";
String gSource, gLabel, gSession;
unsigned long gStateSince = 0;             // 当前状态开始时间
unsigned long gLastEvent = 0;              // 最近一次收到 state POST
String gRendered = "";                     // 上次已渲染的状态名

void setState(const String& name, const String& source, const String& label, const String& session) {
  gStateName = name;
  gSource = source;
  gLabel = label;
  gSession = session;
  gStateSince = gLastEvent = millis();

  // 配方驱动：查库取渲染参数（查不到回落 idle，理论上有 API 校验不会发生）
  StateRecipe sr;
  if (!gRecipes.get(name, sr)) gRecipes.get("idle", sr);
  ledApplyRecipe(sr.led);

  // 屏幕：配方参数驱动（内置表情表 + 配方 screen 覆盖）
  displaySetStateByName(name, label, sr.raw);
}

void handleState() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"missing body\"}");
    return;
  }
  JsonDocument doc;
  if (deserializeJson(doc, server.arg("plain"))) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }
  String name = String(doc["state"] | "");
  if (!gRecipes.has(name)) {
    server.send(404, "application/json",
                ("{\"error\":\"unknown state: " + name + "\"}").c_str());
    return;
  }
  setState(name, String(doc["source"] | ""), String(doc["label"] | ""),
           String(doc["session_id"] | ""));
  JsonDocument resp;
  resp["ok"] = true;
  resp["state"] = name;
  String out;
  serializeJson(resp, out);
  server.send(200, "application/json", out);
}

void handleStatesList() {
  server.send(200, "application/json", gRecipes.listJson());
}

// /api/v1/states/<name> 的 GET / PUT / DELETE
void handleStateItem() {
  // 浏览器跨域预检：任何路径的 OPTIONS 都直接放行（CORS 头由 enableCORS 附加）
  if (server.method() == HTTP_OPTIONS) {
    server.send(200, "application/json", "{}");
    return;
  }
  String prefix = String("/api/v1/states/");
  String uri = server.uri();
  if (!uri.startsWith(prefix)) {
    server.send(404, "application/json", "{\"error\":\"not found\"}");
    return;
  }
  String name = uri.substring(prefix.length());
  if (!RecipeStore::validName(name)) {
    server.send(400, "application/json", "{\"error\":\"invalid name\"}");
    return;
  }

  switch (server.method()) {
    case HTTP_GET: {
      StateRecipe r;
      if (!gRecipes.get(name, r)) {
        server.send(404, "application/json", "{\"error\":\"no such state\"}");
        return;
      }
      server.send(200, "application/json", r.raw);
      return;
    }
    case HTTP_PUT: {
      String body = server.arg("plain");
      String err;
      if (gRecipes.put(name, body, err)) {
        String out = "{\"ok\":true,\"state\":\"" + name + "\"}";
        server.send(200, "application/json", out);
      } else {
        String out = "{\"error\":\"" + err + "\"}";
        server.send(400, "application/json", out);
      }
      return;
    }
    case HTTP_DELETE: {
      bool ok = gRecipes.remove(name);
      server.send(ok ? 200 : 404, "application/json",
                  ok ? "{\"ok\":true}" : "{\"error\":\"no such state\"}");
      return;
    }
    default:
      server.send(405, "application/json", "{\"error\":\"method not allowed\"}");
  }
}

void handleHealth() {
  JsonDocument doc;
  doc["device"] = DEVICE_NAME;
  doc["state"] = gStateName;
  doc["state_for_s"] = (millis() - gStateSince) / 1000;
  doc["source"] = gSource;
  doc["label"] = gLabel;
  doc["session_id"] = gSession;
  doc["uptime_s"] = millis() / 1000;
  doc["wifi"] = (WiFi.status() == WL_CONNECTED) ? "connected" : "disconnected";
  doc["rssi"] = WiFi.RSSI();
  doc["heap"] = ESP.getFreeHeap();
  doc["ip"] = WiFi.localIP().toString();
  doc["states"] = gRecipes.count();
  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // 状态推送走低延迟路径，关闭 Wi-Fi 休眠
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[wifi] connecting to %s ", WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[wifi] connected, ip=%s rssi=%ddBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    if (MDNS.begin(DEVICE_NAME)) {
      MDNS.addService("http", "tcp", HTTP_PORT);
      Serial.printf("[mdns] http://%s.local\n", DEVICE_NAME);
    }
  } else {
    Serial.println("\n[wifi] connect failed, will retry in loop()");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  gRecipes.begin();  // NVS 配方库（首次启动播种 8 个预置状态）
  ledBegin(gRecipes, "idle");
  displayInit();
  connectWiFi();

  server.on("/api/v1/state", HTTP_POST, handleState);
  server.on("/api/v1/states", HTTP_GET, handleStatesList);
  server.on("/api/v1/health", HTTP_GET, handleHealth);
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/plain",
                "AgentPet V1.0 - POST /api/v1/state, GET/PUT/DELETE /api/v1/states/<name>, GET /api/v1/health");
  });
  // 动态路径 /api/v1/states/<name> 与兜底 404
  server.onNotFound(handleStateItem);
  server.enableCORS(true);  // 允许网页配置台跨域直连板子
  server.begin();

  setState("idle", "", "", "");
  Serial.println("[app] AgentPet V1.0 ready");
}

void loop() {
  server.handleClient();

  // Wi-Fi 断线自动重连
  static unsigned long lastWifiCheck = 0;
  if (millis() - lastWifiCheck > WIFI_RETRY_MS) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[wifi] reconnecting...");
      WiFi.reconnect();
    }
  }

  // 兜底回落：长时间无事件回 idle（done 的短停留由 bridge 侧管理）
  if (gStateName != "idle" && millis() - gLastEvent > STATE_TIMEOUT_MS) {
    Serial.println("[app] state timeout -> idle");
    setState("idle", "", "", "");
  }

  // 状态切换日志
  if (gStateName != gRendered) {
    Serial.printf("[app] state -> %s (source=%s label=%s)\n",
                  gStateName.c_str(), gSource.c_str(), gLabel.c_str());
    gRendered = gStateName;
  }

  // 约 15fps 的动画帧率，眨眼/扫读/光标闪烁全程非阻塞
  static unsigned long lastFrame = 0;
  if (millis() - lastFrame >= 66) {
    lastFrame = millis();
    displayRender();
  }
  ledRender();  // 状态灯灯效（内部 20ms 节流，独立于屏幕节拍更顺滑）

#ifdef AGENTPET_SIM_DEMO
  // 仿真演示模式：每 6 秒轮流展示预置状态（Wokwi 截图验证用，真机构建不含此代码）
  static unsigned long lastDemo = 0;
  static uint8_t demoIdx = 0;
  if (millis() - lastDemo > 6000) {
    lastDemo = millis();
    setState(petStateName((PetState)(demoIdx % PET_STATE_COUNT)), "demo", "", "");
    demoIdx++;
  }
#endif
}
