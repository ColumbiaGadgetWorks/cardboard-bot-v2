// Wi-Fi station: the robot joins the Wi-Fi in its settings, reconnects by itself, and answers
// to http://<host>.local (mDNS)
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"

void net_start(const bot_cfg_t *cfg);
bool net_up(void);              // joined, with an IP address
const char *net_ssid(void);
const char *net_host(void);
uint8_t net_channel(void);      // 0 when not joined
int net_rssi(void);             // signal from the router, 0 when not joined
void net_ip(char *buf, int len);
uint32_t net_drops(void);       // Wi-Fi drops since boot
uint8_t net_last_reason(void);  // last disconnect reason code (wifi_err_reason_t)
