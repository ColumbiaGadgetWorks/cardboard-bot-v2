// Settings in the botcfg partition, diagnostics in NVS
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"

void store_init(void);
bool store_load(bot_cfg_t *c);         // false: defaults (blank or damaged partition)
bool store_save(const bot_cfg_t *c);

#define RESET_HISTORY 5
void store_push_reset(uint8_t reason);  // esp_reset_reason_t
int store_resets(uint8_t out[RESET_HISTORY]);   // newest first
uint8_t store_last_channel(void);
void store_set_last_channel(uint8_t ch);
