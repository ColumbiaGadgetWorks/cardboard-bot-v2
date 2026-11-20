// Wi-Fi. The robot joins the strongest of its saved networks and answers to http://<host>.local
// (mDNS). If it isn't on one of them within a minute of power-on (or has none saved), it opens
// its own access point "<host>-XXXX" so a phone can still reach it and add a network.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"

typedef struct {
    char ssid[33];
    int8_t rssi;
    bool secure;
} net_seen_t;

void net_start(const bot_cfg_t *cfg);
// The saved networks changed: use the new list. join_now: try them now, even if a phone is on
// the access point (it may drop off when the robot changes channel).
void net_set_nets(const bot_cfg_t *cfg, bool join_now);
bool net_up(void);              // joined a network, with an IP address
bool net_ap_on(void);           // fallback access point is up
int net_clients(void);          // phones on the access point
const char *net_ssid(void);     // network joined ("" when not)
const char *net_ap_ssid(void);
const char *net_host(void);
uint8_t net_channel(void);      // 0 when not joined
int net_rssi(void);             // signal from the router, 0 when not joined
bool net_low_power(void);       // joined at reduced transmit power (some boards can't join at full)
void net_ip(char *buf, int len);  // "" when not joined
uint32_t net_drops(void);       // Wi-Fi drops since boot
uint8_t net_last_reason(void);  // last disconnect reason code (wifi_err_reason_t)
// Blocking (about 2 s). Returns how many networks were found, strongest first, one per name.
int net_scan(net_seen_t *out, int max);
// Blocking: join this network now. Returns 0 when joined, else a wifi_err_reason_t (or 1 = timed out).
int net_try(const char *ssid, const char *pw, int timeout_ms);
const char *net_reason_text(int reason);

void dns_start(void);
