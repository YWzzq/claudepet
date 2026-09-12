#pragma once

#include <Arduino.h>
#include "pet_state.h"

void displayInit();
void displaySetState(PetState state, const String& label);
void displayShowUnknown(const String& name);  // 自定义状态：屏幕显示名字（V1.1 配方化）
void displayRender();  // 每帧调用（约 15fps），动画全程非阻塞
