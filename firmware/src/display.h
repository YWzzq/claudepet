#pragma once

#include <Arduino.h>

// 屏幕显示：配方参数驱动（V1.1）
// screenJson 为配方里的 screen 对象原始 JSON；缺字段时按状态名用默认表情表
void displayInit();
void displaySetStateByName(const String& name, const String& label, const String& screenJson);
void displayRender();  // 每帧调用（约 15fps），动画全程非阻塞
