// Drive mixing, weapon outputs and the arm / failsafe rules. Plain C with no ESP-IDF calls,
// so test/test_control.c can run it on a PC.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "config.h"

typedef struct {
    int8_t ax[4];        // lx, ly, rx, ry: -127..127, up and right positive
    uint8_t trig[2];     // lt, rt: 0..255
    uint32_t btn;        // see BTN_* in config.h
} ctl_input_t;

typedef enum {
    LED_BOOT = 0,     // white blink
    LED_UPDATE,       // white blink
    LED_WAITING,      // blue pulse: no phone driving
    LED_CONNECTED,    // green: connected, weapon safe
    LED_LOWBATT,      // purple blink
    LED_ARMED,        // red solid
    LED_ARMED_RUN,    // red fast flash: weapon running
    LED_FAILSAFE,     // amber flash: link lost
} led_state_t;

typedef struct {
    // inputs the caller fills in each step
    float vbat;          // pack voltage, < 0 = not measured
    bool updating;

    // outputs
    float motor[2];      // left, right: -1..1 duty, voltage cap applied
    uint16_t out_us[NUM_OUT];  // pulse width, 0 = output held low
    led_state_t led;
    bool armed;
    bool failsafe;
    bool weapon_lock;    // low battery: weapon locked out
    bool drive_lock;     // very low battery: drive stopped
    bool weapon_running;
    uint8_t cells;       // 2 or 3 once a pack is seen, 0 before
    char reason[64];     // why it last disarmed / refused to arm

    // internal
    bool linked;         // a driver has ever sent input since boot
    uint32_t last_pkt;
    uint32_t fs_start;
    uint32_t drops[20];
    uint8_t ndrops;
    bool need_release;
    ctl_input_t in;
    float drive_cur[2];
    float esc_thr[NUM_OUT];
    float servo_deg[NUM_OUT];
    bool latch[NUM_OUT];
    bool prev_pressed[NUM_OUT];
    uint32_t esc_start;  // when the first ESC started spinning (0 = none)
    uint32_t low_wpn_since, low_drv_since;
    uint32_t last_step;
    bool have_step;
} ctl_t;

void ctl_init(ctl_t *c, const bot_cfg_t *cfg);
// A control packet from the phone that is driving
void ctl_input(ctl_t *c, const ctl_input_t *in, uint32_t now_ms);
// The driving phone's link closed: drop its held inputs now, the timers do the rest
void ctl_link_closed(ctl_t *c, uint32_t now_ms);
bool ctl_arm(ctl_t *c, const bot_cfg_t *cfg, uint32_t now_ms);   // false: reason says why
void ctl_disarm(ctl_t *c, const char *reason);
// Run every ~10 ms. out_avail[i] false: that pin is busy (IO3 reading the battery).
void ctl_step(ctl_t *c, const bot_cfg_t *cfg, uint32_t now_ms, bool out_avail[NUM_OUT]);
// Pulse width an output idles at (ESC stop / servo rest), 0 for off
uint16_t ctl_idle_us(const out_cfg_t *o);
