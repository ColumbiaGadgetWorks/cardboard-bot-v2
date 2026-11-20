#include "config.h"

#include "board.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void cfg_defaults(bot_cfg_t *c)
{
    memset(c, 0, sizeof(*c));
    strcpy(c->name, "Robot");
    strcpy(c->host, "adambot");
    strcpy(c->src, "stable");
    strcpy(c->ap_pw, "cardboard");
    c->bsense = true;
    c->vdiv = VBAT_DIVIDER;
    c->cells = 0;
    c->drive_on = true;
    c->led_on = true;
    c->pins = (pin_cfg_t){
        .ain1 = PIN_AIN1, .ain2 = PIN_AIN2, .bin1 = PIN_BIN1, .bin2 = PIN_BIN2,
        .out = {PIN_OUT1, PIN_OUT2, PIN_OUT3, PIN_OUT4}, .led = PIN_LED, .vbat = PIN_VBAT,
    };

    c->drive = (drive_cfg_t){
        .mode = DRIVE_SPLIT, .max_pct = 100, .slow_pct = 50, .slow_btn = 6 /* LT */,
        .turn_pct = 70, .spin_ms = 100, .expo_pct = 30, .dead_pct = 8, .ramp_ms = 150, .vcap = 6.0f,
    };
    for (int i = 0; i < NUM_OUT; i++) {
        c->out[i] = (out_cfg_t){
            .type = OUT_OFF, .mode = OM_HOLD, .btn = BTN_NONE, .axis = AX_RT,
            .min_us = 1000, .max_us = 2000, .max_pct = 100, .spin_ms = 1000,
            .rest_deg = 0, .fire_deg = 90, .speed = 0,
        };
    }
    // two weapon ESCs: OUT1 on RB, OUT2 on LB. OUT3 / output 4 off.
    c->out[0].type = OUT_ESC;
    c->out[0].btn = 5;
    c->out[1].type = OUT_ESC;
    c->out[1].btn = 4;

    c->safe = (safe_cfg_t){
        .wpn_cut_ms = 300, .fs_ms = 1000, .grace_ms = 1000, .drops = 3, .low_wpn = 3.2f, .low_drv = 3.0f,
        .lockout = true,
    };
}

// GPIOs the XIAO ESP32-C3 brings out: D0-D10
bool cfg_pin_ok(int g) { return (g >= 2 && g <= 10) || g == 20 || g == 21; }
bool cfg_adc_pin_ok(int g) { return g >= 2 && g <= 4; }

void cfg_out_avail(const bot_cfg_t *c, bool avail[NUM_OUT])
{
    for (int i = 0; i < NUM_OUT; i++) {
        int p = c->pins.out[i];
        bool ok = cfg_pin_ok(p);
        if (c->drive_on && (p == c->pins.ain1 || p == c->pins.ain2 || p == c->pins.bin1 || p == c->pins.bin2)) ok = false;
        if (c->led_on && p == c->pins.led) ok = false;
        if (c->bsense && p == c->pins.vbat) ok = false;
        for (int j = 0; j < i; j++)
            if (avail[j] && c->out[j].type != OUT_OFF && c->pins.out[j] == p) ok = false;
        avail[i] = ok;
    }
}

int cfg_net_count(const bot_cfg_t *c)
{
    int n = 0;
    for (int i = 0; i < MAX_NETS; i++) n += c->nets[i].ssid[0] != 0;
    return n;
}

void cfg_net_add(bot_cfg_t *c, const char *ssid, const char *pw)
{
    if (!ssid || !ssid[0]) return;
    wifi_net_t nw = {0};
    strncpy(nw.ssid, ssid, sizeof(nw.ssid) - 1);
    strncpy(nw.pw, pw ? pw : "", sizeof(nw.pw) - 1);
    int at = MAX_NETS - 1;   // full and new: the last one drops off
    for (int i = 0; i < MAX_NETS; i++)
        if (!c->nets[i].ssid[0] || !strcmp(c->nets[i].ssid, nw.ssid)) {
            at = i;
            break;
        }
    memmove(&c->nets[1], &c->nets[0], at * sizeof(wifi_net_t));
    c->nets[0] = nw;
}

bool cfg_net_remove(bot_cfg_t *c, const char *ssid)
{
    for (int i = 0; i < MAX_NETS; i++)
        if (c->nets[i].ssid[0] && !strcmp(c->nets[i].ssid, ssid)) {
            memmove(&c->nets[i], &c->nets[i + 1], (MAX_NETS - 1 - i) * sizeof(wifi_net_t));
            memset(&c->nets[MAX_NETS - 1], 0, sizeof(wifi_net_t));
            return true;
        }
    return false;
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
static float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }

void cfg_sanitize(bot_cfg_t *c)
{
    if (!c->name[0]) strcpy(c->name, "Robot");
    // host name: lower-case letters, digits and '-', not starting or ending with '-'
    char h[sizeof(c->host)];
    int n = 0;
    for (const char *s = c->host; *s && n < (int)sizeof(h) - 1; s++) {
        char ch = *s;
        if (ch >= 'A' && ch <= 'Z') ch += 'a' - 'A';
        if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || (ch == '-' && n > 0)) h[n++] = ch;
        else if ((ch == ' ' || ch == '_') && n > 0) h[n++] = '-';
    }
    while (n > 0 && h[n - 1] == '-') n--;
    h[n] = 0;
    strcpy(c->host, n ? h : "adambot");
    // fallback access point: WPA2 needs 8+ characters; anything shorter goes back to the default
    size_t apl = strlen(c->ap_pw);
    if (apl > 0 && apl < 8) strcpy(c->ap_pw, "cardboard");
    // networks: no gaps, no empty names, no repeats
    int k = 0;
    for (int i = 0; i < MAX_NETS; i++) {
        bool dup = false;
        for (int j = 0; j < k; j++) dup |= !strcmp(c->nets[j].ssid, c->nets[i].ssid);
        if (!c->nets[i].ssid[0] || dup) continue;
        if (k != i) c->nets[k] = c->nets[i];
        k++;
    }
    for (int i = k; i < MAX_NETS; i++) memset(&c->nets[i], 0, sizeof(c->nets[i]));
    // pins: anything not on the XIAO goes back to the board default; the motor pins must all differ
    bot_cfg_t def;
    cfg_defaults(&def);
    pin_cfg_t *p = &c->pins;
    uint8_t *pp[] = {&p->ain1, &p->ain2, &p->bin1, &p->bin2, &p->out[0], &p->out[1], &p->out[2], &p->out[3], &p->led};
    const uint8_t *dp[] = {&def.pins.ain1, &def.pins.ain2, &def.pins.bin1, &def.pins.bin2, &def.pins.out[0],
                           &def.pins.out[1], &def.pins.out[2], &def.pins.out[3], &def.pins.led};
    for (int i = 0; i < 9; i++)
        if (!cfg_pin_ok(*pp[i])) *pp[i] = *dp[i];
    if (!cfg_adc_pin_ok(p->vbat)) p->vbat = def.pins.vbat;
    uint8_t m[4] = {p->ain1, p->ain2, p->bin1, p->bin2};
    bool clash = false;
    for (int i = 0; i < 4; i++)
        for (int j = i + 1; j < 4; j++) clash |= m[i] == m[j];
    if (c->led_on && c->drive_on) for (int i = 0; i < 4; i++) clash |= m[i] == p->led;
    if (c->bsense && c->drive_on) for (int i = 0; i < 4; i++) clash |= m[i] == p->vbat;
    if (clash) {
        p->ain1 = def.pins.ain1;
        p->ain2 = def.pins.ain2;
        p->bin1 = def.pins.bin1;
        p->bin2 = def.pins.bin2;
    }
    if (c->led_on && c->bsense && p->led == p->vbat) c->led_on = false;

    drive_cfg_t *d = &c->drive;
    d->mode = clampi(d->mode, 0, 2);
    d->max_pct = clampi(d->max_pct, 10, 100);
    d->slow_pct = clampi(d->slow_pct, 5, 100);
    d->turn_pct = clampi(d->turn_pct, 10, 100);
    d->expo_pct = clampi(d->expo_pct, 0, 100);
    d->dead_pct = clampi(d->dead_pct, 0, 40);
    d->ramp_ms = clampi(d->ramp_ms, 0, 2000);
    d->spin_ms = clampi(d->spin_ms, 0, 2000);
    d->vcap = clampf(d->vcap, 3.0f, 8.4f);
    for (int i = 0; i < NUM_OUT; i++) {
        out_cfg_t *o = &c->out[i];
        o->type = clampi(o->type, 0, 2);
        o->mode = clampi(o->mode, 0, 2);
        if (o->axis > AX_RT) o->axis = AX_RT;
        o->min_us = clampi(o->min_us, 400, 2600);
        o->max_us = clampi(o->max_us, 400, 2600);
        o->max_pct = clampi(o->max_pct, 0, 100);
        o->spin_ms = clampi(o->spin_ms, 0, 10000);
        o->rest_deg = clampi(o->rest_deg, 0, 180);
        o->fire_deg = clampi(o->fire_deg, 0, 180);
    }
    safe_cfg_t *s = &c->safe;
    s->wpn_cut_ms = clampi(s->wpn_cut_ms, 100, 1000);
    s->fs_ms = clampi(s->fs_ms, 300, 3000);
    if (s->wpn_cut_ms > s->fs_ms) s->wpn_cut_ms = s->fs_ms;
    s->grace_ms = clampi(s->grace_ms, 0, 5000);
    s->drops = clampi(s->drops, 1, 20);
    // older settings held 2S pack voltages (6.4 / 6.0): convert to per cell
    if (s->low_wpn > 4.5f) s->low_wpn /= 2;
    if (s->low_drv > 4.5f) s->low_drv /= 2;
    s->low_wpn = clampf(s->low_wpn, 2.8f, 3.8f);
    s->low_drv = clampf(s->low_drv, 2.8f, 3.8f);
    c->vdiv = clampf(c->vdiv, 2.0f, 12.0f);
    if (c->cells != 0 && c->cells != 2 && c->cells != 3) c->cells = 0;
}

// ---- botcfg partition image (same format as site/flasher.js) ----
uint32_t cfg_crc32(const uint8_t *p, uint32_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

static uint32_t rd32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

bool cfg_parse_image(const uint8_t *img, uint32_t n, const char **json, uint32_t *len)
{
    if (n < 12 || memcmp(img, "BCFG", 4) != 0) return false;
    uint32_t l = img[6] | img[7] << 8;
    if (img[4] != 1 || l == 0 || 12 + l > n) return false;
    if (cfg_crc32(img + 12, l) != rd32(img + 8)) return false;
    *json = (const char *)img + 12;
    *len = l;
    return true;
}

uint32_t cfg_make_image(const char *json, uint8_t *img)
{
    uint32_t l = strlen(json);
    if (l > BOTCFG_SIZE - 12) return 0;
    memset(img, 0xFF, BOTCFG_SIZE);
    memcpy(img, "BCFG", 4);
    img[4] = 1;
    img[5] = 0;
    img[6] = l & 0xFF;
    img[7] = l >> 8;
    uint32_t crc = cfg_crc32((const uint8_t *)json, l);
    for (int i = 0; i < 4; i++) img[8 + i] = crc >> (8 * i);
    memcpy(img + 12, json, l);
    return 12 + l;
}
