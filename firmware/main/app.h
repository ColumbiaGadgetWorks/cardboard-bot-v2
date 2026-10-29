// State shared between the control loop (main.c) and the web server (web.c)
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"
#include "control.h"

extern bot_cfg_t g_cfg;
extern ctl_t g_ctl;

// g_cfg and g_ctl are only touched with this held
void app_lock(void);
void app_unlock(void);

// ESC calibration: hold one output at a fixed pulse width while disarmed (-1 = off)
void app_calibrate(int out, uint16_t us);

typedef struct {
    float vmin;            // lowest pack voltage since boot (-1: none)
    uint8_t resets[5];     // last reset reasons, newest first
    int nresets;
    uint32_t boot_ms;
} app_diag_t;
extern app_diag_t g_diag;

const char *app_version(void);
void app_reboot_soon(void);

// OTA
void ota_start_pull(void);                 // download from the firmware source over club Wi-Fi
const char *ota_status(void);              // "" when idle
void ota_set_status(const char *s);
const char *ota_base_url(const bot_cfg_t *c, char *buf, int len);
