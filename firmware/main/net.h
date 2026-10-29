// Robot access point with automatic channel pick; club Wi-Fi station for pulling updates
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"

void net_start(const bot_cfg_t *cfg);
uint8_t net_channel(void);
const char *net_ssid(void);
int net_rssi(void);     // strongest connected phone, 0 if none
int net_clients(void);
// Join club Wi-Fi as a station (the AP stays up, but moves to the router's channel).
bool net_join_club(const bot_cfg_t *cfg, int timeout_ms);
