// Motor PWM, the four servo / ESC outputs, battery ADC and the WS2812 status LED
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"
#include "control.h"

void hw_init(const bot_cfg_t *cfg);
void hw_motors(float left, float right);        // -1..1
void hw_outputs(const uint16_t us[NUM_OUT]);    // pulse width in us, 0 = low
bool hw_out_available(int i);                    // IO3 is busy when it reads the battery
float hw_vbat(void);                             // filtered pack voltage, -1 if not measured
void hw_led(led_state_t s, uint32_t now_ms);
