#pragma once

#include <Arduino.h>
#include "pet_state.h"
#include "recipe_store.h"

// 状态灯：完全由配方驱动（颜色 + 灯效 + 周期）
void ledBegin(RecipeStore& store, const String& name);
void ledApplyRecipe(const LedRecipe& r);
void ledRender();  // 每帧调用，内部自带 20ms 节流
