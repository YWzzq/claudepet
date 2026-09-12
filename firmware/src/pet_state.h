#pragma once

#include <Arduino.h>

enum PetState : uint8_t {
  PET_IDLE = 0,
  PET_THINKING,
  PET_READING,
  PET_WRITING,
  PET_SHELL,
  PET_WAITING,
  PET_DONE,
  PET_ERROR,
  PET_STATE_COUNT,
};

inline const char* petStateName(PetState s) {
  static const char* NAMES[PET_STATE_COUNT] = {
      "idle", "thinking", "reading", "writing", "shell", "waiting", "done", "error"};
  return NAMES[s];
}

inline bool petStateFromName(const String& name, PetState& out) {
  for (uint8_t i = 0; i < PET_STATE_COUNT; i++) {
    if (name == petStateName((PetState)i)) {
      out = (PetState)i;
      return true;
    }
  }
  return false;
}
