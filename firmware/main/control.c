#include "control.h"

#include <math.h>
#include <string.h>

#define ESC_STAGGER_MS 300   // a second ESC starts this long after the first
#define LOW_FILTER_MS 2000   // battery must stay low this long before a lockout
#define NO_BATT_V 2.0f       // below this the pack isn't connected (running from USB)
#define CELLS3_V 8.9f        // above this at power-on it's a 3S pack (2S is 8.4 V full)

static float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }

static void set_reason(ctl_t *c, const char *r)
{
    strncpy(c->reason, r, sizeof(c->reason) - 1);
    c->reason[sizeof(c->reason) - 1] = 0;
}

uint16_t ctl_idle_us(const out_cfg_t *o)
{
    if (o->type == OUT_ESC) return o->min_us;
    if (o->type == OUT_SERVO) return o->min_us + (uint16_t)((o->max_us - o->min_us) * o->rest_deg / 180);
    return 0;
}

void ctl_init(ctl_t *c, const bot_cfg_t *cfg)
{
    memset(c, 0, sizeof(*c));
    c->vbat = -1;
    for (int i = 0; i < NUM_OUT; i++) {
        c->servo_deg[i] = cfg->out[i].rest_deg;
        c->out_us[i] = ctl_idle_us(&cfg->out[i]);
    }
    set_reason(c, "Starts disarmed");
}

void ctl_input(ctl_t *c, const ctl_input_t *in, uint32_t now)
{
    if (c->failsafe) {
        c->failsafe = false;
        // still armed only if the link came back within the grace time (ctl_step disarms after it);
        // the weapon waits for its fire input to be released and pressed again
        if (c->armed) c->need_release = true;
    }
    c->in = *in;
    c->last_pkt = now;
    c->linked = true;
}

void ctl_link_closed(ctl_t *c, uint32_t now)
{
    (void)now;
    memset(&c->in, 0, sizeof(c->in));
}

void ctl_disarm(ctl_t *c, const char *reason)
{
    if (c->armed) set_reason(c, reason);
    c->armed = false;
    memset(c->latch, 0, sizeof(c->latch));
}

bool ctl_arm(ctl_t *c, const bot_cfg_t *cfg, uint32_t now)
{
    if (c->updating) {
        set_reason(c, "Updating firmware");
        return false;
    }
    if (!c->linked || c->failsafe || now - c->last_pkt > cfg->safe.fs_ms) {
        set_reason(c, "No controller connected");
        return false;
    }
    if (c->weapon_lock) {
        set_reason(c, "Battery low: weapon locked out");
        return false;
    }
    c->armed = true;
    c->need_release = true;   // a fire button held while arming doesn't fire
    c->reason[0] = 0;
    return true;
}

static float shape(float v, const drive_cfg_t *d)
{
    float dz = d->dead_pct / 100.0f;
    float a = fabsf(v);
    if (a <= dz) return 0;
    a = (a - dz) / (1 - dz);
    float e = d->expo_pct / 100.0f;
    a = (1 - e) * a + e * a * a * a;
    return v < 0 ? -a : a;
}

static void mix(const ctl_input_t *in, const drive_cfg_t *d, float out[2])
{
    float lx = in->ax[AX_LX] / 127.0f, ly = in->ax[AX_LY] / 127.0f;
    float rx = in->ax[AX_RX] / 127.0f, ry = in->ax[AX_RY] / 127.0f;
    float l, r;
    if (d->mode == DRIVE_TANK) {
        l = shape(ly, d);
        r = shape(ry, d);
    } else {
        float thr = shape(ly, d);
        float str = shape(d->mode == DRIVE_ARCADE ? lx : rx, d) * d->turn_pct / 100.0f;
        if (d->rev_steer) str = -str;
        l = thr + str;
        r = thr - str;
        float m = fmaxf(fabsf(l), fabsf(r));
        if (m > 1) {
            l /= m;
            r /= m;
        }
    }
    bool slow = (in->btn >> BTN_SCREEN_SLOW) & 1;
    if (d->slow_btn < 32 && ((in->btn >> d->slow_btn) & 1)) slow = true;
    float k = (slow ? d->slow_pct : d->max_pct) / 100.0f;
    l *= k;
    r *= k;
    if (d->swap) {
        float t = l;
        l = r;
        r = t;
    }
    if (d->inv_l) l = -l;
    if (d->inv_r) r = -r;
    out[0] = clampf(l, -1, 1);
    out[1] = clampf(r, -1, 1);
}

static void battery(ctl_t *c, const bot_cfg_t *cfg, uint32_t now)
{
    float v = c->vbat;
    if (v < NO_BATT_V) c->cells = 0;   // pack removed: detect again when one is connected
    else if (!c->cells) c->cells = cfg->cells ? cfg->cells : (v > CELLS3_V ? 3 : 2);
    if (v < NO_BATT_V || !cfg->safe.lockout) {   // not measured, no pack, or lockouts turned off
        c->weapon_lock = c->drive_lock = false;
        c->low_wpn_since = c->low_drv_since = 0;
        return;
    }
    v /= c->cells;   // the thresholds are per cell
    // lockouts need 2 s below the threshold (motor current sags the pack) and some hysteresis to clear
    if (v < cfg->safe.low_wpn) {
        if (!c->low_wpn_since) c->low_wpn_since = now ? now : 1;
        if (now - c->low_wpn_since >= LOW_FILTER_MS) c->weapon_lock = true;
    } else {
        c->low_wpn_since = 0;
        if (v > cfg->safe.low_wpn + 0.1f) c->weapon_lock = false;
    }
    if (v < cfg->safe.low_drv) {
        if (!c->low_drv_since) c->low_drv_since = now ? now : 1;
        if (now - c->low_drv_since >= LOW_FILTER_MS) c->drive_lock = true;
    } else {
        c->low_drv_since = 0;
        if (v > cfg->safe.low_drv + 0.15f) c->drive_lock = false;
    }
}

static float input_analog(const ctl_input_t *in, uint8_t axis)
{
    if (axis == AX_LT || axis == AX_RT) return in->trig[axis - AX_LT] / 255.0f;
    if (axis < 4) return fmaxf(0, in->ax[axis] / 127.0f);   // a stick pushed up / right
    return 0;
}

static bool input_pressed(const ctl_input_t *in, const out_cfg_t *o, int i)
{
    if ((in->btn >> BTN_SCREEN_FIRE(i)) & 1) return true;
    if (o->btn < 32 && ((in->btn >> o->btn) & 1)) return true;
    if (o->mode == OM_ANALOG && input_analog(in, o->axis) > 0.05f) return true;
    return false;
}

void ctl_step(ctl_t *c, const bot_cfg_t *cfg, uint32_t now, bool out_avail[NUM_OUT])
{
    uint32_t dt = c->have_step ? now - c->last_step : 0;
    if (dt > 100) dt = 100;
    c->last_step = now;
    c->have_step = true;

    battery(c, cfg, now);
    if (c->weapon_lock && c->armed) ctl_disarm(c, "Battery low: weapon locked out");

    // ---- link timing ----
    uint32_t age = c->linked ? now - c->last_pkt : UINT32_MAX;
    bool weapon_cut = !c->linked || age > cfg->safe.wpn_cut_ms;
    if (c->linked && age > cfg->safe.fs_ms && !c->failsafe) {
        c->failsafe = true;
        c->fs_start = now;
        uint8_t n = 0;   // keep drops from the last 60 s, then add this one
        for (int i = 0; i < c->ndrops; i++)
            if (now - c->drops[i] < 60000) c->drops[n++] = c->drops[i];
        if (n < sizeof(c->drops) / sizeof(c->drops[0])) c->drops[n++] = now;
        c->ndrops = n;
        if (c->armed && n >= cfg->safe.drops) ctl_disarm(c, "Link dropped too often: re-arm");
    }
    if (c->failsafe && c->armed && now - c->fs_start > cfg->safe.grace_ms) ctl_disarm(c, "Link lost: re-arm");
    if (c->failsafe) memset(&c->in, 0, sizeof(c->in));

    // ---- drive ----
    float target[2] = {0, 0};
    bool drive_ok = cfg->drive_on && c->linked && !c->failsafe && !c->drive_lock && age <= cfg->safe.fs_ms;
    if (drive_ok) mix(&c->in, &cfg->drive, target);
    if (!drive_ok) {
        c->drive_cur[0] = c->drive_cur[1] = 0;   // stop at once, no ramp
    } else {
        float ramp = cfg->drive.ramp_ms;
        bool spin = (target[0] > 0.05f && target[1] < -0.05f) || (target[0] < -0.05f && target[1] > 0.05f);
        if (spin) ramp += cfg->drive.spin_ms;
        float stepv = ramp > 0 ? dt / ramp : 2.0f;
        for (int m = 0; m < 2; m++) {
            float d = target[m] - c->drive_cur[m];
            c->drive_cur[m] += clampf(d, -stepv, stepv);
        }
    }
    float vb = c->vbat >= NO_BATT_V ? c->vbat : 8.4f;
    float k = cfg->drive.vcap / fmaxf(vb, cfg->drive.vcap);
    c->motor[0] = c->drive_cur[0] * k;
    c->motor[1] = c->drive_cur[1] * k;

    // ---- weapon outputs ----
    bool allowed = c->armed && !weapon_cut && !c->weapon_lock && !c->need_release && !c->failsafe;
    bool all_released = true, any_esc_on = false;
    int esc_rank = 0;
    c->weapon_running = false;
    for (int i = 0; i < NUM_OUT; i++) {
        const out_cfg_t *o = &cfg->out[i];
        if (!out_avail[i] || o->type == OUT_OFF) {
            c->out_us[i] = 0;
            c->esc_thr[i] = 0;
            c->latch[i] = false;
            continue;
        }
        bool pressed = input_pressed(&c->in, o, i);
        if (pressed) all_released = false;
        bool rising = pressed && !c->prev_pressed[i];
        c->prev_pressed[i] = pressed;
        if (!allowed) c->latch[i] = false;
        else if (o->mode == OM_TOGGLE && rising) c->latch[i] = !c->latch[i];

        float a = 0;   // 0..1 how far "fired"
        if (allowed) {
            if (o->mode == OM_HOLD) a = pressed ? 1 : 0;
            else if (o->mode == OM_TOGGLE) a = c->latch[i] ? 1 : 0;
            else a = input_analog(&c->in, o->axis);
        }

        if (o->type == OUT_ESC) {
            float tgt = a * o->max_pct / 100.0f;
            if (tgt > 0) {
                any_esc_on = true;
                if (!c->esc_start) c->esc_start = now ? now : 1;
            }
            if (tgt < c->esc_thr[i]) {
                c->esc_thr[i] = tgt;   // stopping is immediate
            } else if (tgt > c->esc_thr[i] && now - c->esc_start >= (uint32_t)esc_rank * ESC_STAGGER_MS) {
                float stepv = o->spin_ms ? (float)dt / o->spin_ms : 1.0f;
                c->esc_thr[i] = fminf(tgt, c->esc_thr[i] + stepv);
            }
            if (tgt > 0) esc_rank++;   // only ESCs that are being fired wait for the ones before them
            if (c->esc_thr[i] > 0.01f) c->weapon_running = true;
            c->out_us[i] = o->min_us + (uint16_t)((o->max_us - o->min_us) * c->esc_thr[i]);
        } else {
            float tgt = o->rest_deg + a * ((float)o->fire_deg - o->rest_deg);
            float d = tgt - c->servo_deg[i];
            if (o->speed) {
                float stepv = o->speed * dt / 1000.0f;
                c->servo_deg[i] += clampf(d, -stepv, stepv);
            } else {
                c->servo_deg[i] = tgt;
            }
            if (fabsf(c->servo_deg[i] - o->rest_deg) > 2) c->weapon_running = true;
            c->out_us[i] = o->min_us + (uint16_t)((o->max_us - o->min_us) * c->servo_deg[i] / 180.0f);
        }
    }
    if (!any_esc_on) {
        bool spinning = false;
        for (int i = 0; i < NUM_OUT; i++) spinning |= c->esc_thr[i] > 0;
        if (!spinning) c->esc_start = 0;
    }
    if (c->need_release && all_released) c->need_release = false;

    // ---- status light: the most urgent state wins ----
    if (c->updating) c->led = LED_UPDATE;
    else if (!c->linked && now < 1500) c->led = LED_BOOT;
    else if (c->failsafe) c->led = LED_FAILSAFE;
    else if (c->armed) c->led = c->weapon_running ? LED_ARMED_RUN : LED_ARMED;
    else if (c->weapon_lock || c->drive_lock) c->led = LED_LOWBATT;
    else if (c->linked) c->led = LED_CONNECTED;
    else c->led = LED_WAITING;
}
