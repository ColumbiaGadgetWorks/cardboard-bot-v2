// Settings <-> JSON (the robot's web page and the botcfg partition both use it)
#include <string.h>

#include "cJSON.h"
#include "config.h"

#define GET_STR(obj, key, dst)                                                   \
    do {                                                                         \
        cJSON *_j = cJSON_GetObjectItemCaseSensitive(obj, key);                  \
        if (cJSON_IsString(_j)) {                                                \
            strncpy(dst, _j->valuestring, sizeof(dst) - 1);                      \
            dst[sizeof(dst) - 1] = 0;                                            \
        }                                                                        \
    } while (0)
#define GET_NUM(obj, key, dst)                                                   \
    do {                                                                         \
        cJSON *_j = cJSON_GetObjectItemCaseSensitive(obj, key);                  \
        if (cJSON_IsNumber(_j)) dst = _j->valuedouble;                           \
    } while (0)
#define GET_BOOL(obj, key, dst)                                                  \
    do {                                                                         \
        cJSON *_j = cJSON_GetObjectItemCaseSensitive(obj, key);                  \
        if (cJSON_IsBool(_j)) dst = cJSON_IsTrue(_j);                            \
    } while (0)

bool cfg_from_json(bot_cfg_t *c, const char *json)
{
    cJSON *r = cJSON_Parse(json);
    if (!r) return false;
    GET_STR(r, "name", c->name);
    GET_STR(r, "driver", c->driver);
    GET_STR(r, "ap", c->ap);
    GET_STR(r, "pw", c->pw);
    GET_NUM(r, "ch", c->ch);
    GET_STR(r, "src", c->src);
    GET_STR(r, "srcUrl", c->src_url);
    GET_BOOL(r, "bsense", c->bsense);
    GET_BOOL(r, "driveOn", c->drive_on);
    GET_BOOL(r, "ledOn", c->led_on);
    GET_BOOL(r, "captive", c->captive);
    cJSON *p = cJSON_GetObjectItemCaseSensitive(r, "pins");
    if (cJSON_IsObject(p)) {
        pin_cfg_t *x = &c->pins;
        GET_NUM(p, "ain1", x->ain1);
        GET_NUM(p, "ain2", x->ain2);
        GET_NUM(p, "bin1", x->bin1);
        GET_NUM(p, "bin2", x->bin2);
        GET_NUM(p, "led", x->led);
        GET_NUM(p, "vbat", x->vbat);
        cJSON *po = cJSON_GetObjectItemCaseSensitive(p, "out");
        if (cJSON_IsArray(po))
            for (int i = 0; i < NUM_OUT && i < cJSON_GetArraySize(po); i++) {
                cJSON *e = cJSON_GetArrayItem(po, i);
                if (cJSON_IsNumber(e)) x->out[i] = e->valuedouble;
            }
    }
    cJSON *w = cJSON_GetObjectItemCaseSensitive(r, "wifi");
    if (cJSON_IsObject(w)) {
        GET_STR(w, "ssid", c->wifi_ssid);
        GET_STR(w, "pw", c->wifi_pw);
    }
    cJSON *d = cJSON_GetObjectItemCaseSensitive(r, "drive");
    if (cJSON_IsObject(d)) {
        drive_cfg_t *x = &c->drive;
        GET_NUM(d, "mode", x->mode);
        GET_BOOL(d, "invL", x->inv_l);
        GET_BOOL(d, "invR", x->inv_r);
        GET_BOOL(d, "swap", x->swap);
        GET_BOOL(d, "revSteer", x->rev_steer);
        GET_NUM(d, "max", x->max_pct);
        GET_NUM(d, "slow", x->slow_pct);
        GET_NUM(d, "slowBtn", x->slow_btn);
        GET_NUM(d, "turn", x->turn_pct);
        GET_NUM(d, "spin", x->spin_ms);
        GET_NUM(d, "expo", x->expo_pct);
        GET_NUM(d, "dead", x->dead_pct);
        GET_NUM(d, "ramp", x->ramp_ms);
        GET_NUM(d, "vcap", x->vcap);
    }
    cJSON *o = cJSON_GetObjectItemCaseSensitive(r, "out");
    if (cJSON_IsArray(o)) {
        for (int i = 0; i < NUM_OUT && i < cJSON_GetArraySize(o); i++) {
            cJSON *e = cJSON_GetArrayItem(o, i);
            if (!cJSON_IsObject(e)) continue;
            out_cfg_t *x = &c->out[i];
            GET_NUM(e, "type", x->type);
            GET_NUM(e, "mode", x->mode);
            GET_NUM(e, "btn", x->btn);
            GET_NUM(e, "axis", x->axis);
            GET_NUM(e, "min", x->min_us);
            GET_NUM(e, "max", x->max_us);
            GET_NUM(e, "maxPct", x->max_pct);
            GET_NUM(e, "spin", x->spin_ms);
            GET_NUM(e, "rest", x->rest_deg);
            GET_NUM(e, "fire", x->fire_deg);
            GET_NUM(e, "speed", x->speed);
        }
    }
    cJSON *s = cJSON_GetObjectItemCaseSensitive(r, "safe");
    if (cJSON_IsObject(s)) {
        safe_cfg_t *x = &c->safe;
        GET_NUM(s, "wpnCut", x->wpn_cut_ms);
        GET_NUM(s, "fs", x->fs_ms);
        GET_NUM(s, "grace", x->grace_ms);
        GET_NUM(s, "drops", x->drops);
        GET_NUM(s, "lowWpn", x->low_wpn);
        GET_NUM(s, "lowDrv", x->low_drv);
        GET_BOOL(s, "lockout", x->lockout);
    }
    cJSON_Delete(r);
    cfg_sanitize(c);
    return true;
}

static double round2(double v) { return (double)(long)(v * 100 + (v >= 0 ? 0.5 : -0.5)) / 100; }

char *cfg_to_json(const bot_cfg_t *c)
{
    cJSON *r = cJSON_CreateObject();
    cJSON_AddStringToObject(r, "name", c->name);
    cJSON_AddStringToObject(r, "driver", c->driver);
    cJSON_AddStringToObject(r, "ap", c->ap);
    cJSON_AddStringToObject(r, "pw", c->pw);
    cJSON_AddNumberToObject(r, "ch", c->ch);
    cJSON_AddStringToObject(r, "src", c->src);
    cJSON_AddStringToObject(r, "srcUrl", c->src_url);
    cJSON_AddBoolToObject(r, "bsense", c->bsense);
    cJSON_AddBoolToObject(r, "driveOn", c->drive_on);
    cJSON_AddBoolToObject(r, "ledOn", c->led_on);
    cJSON_AddBoolToObject(r, "captive", c->captive);
    const pin_cfg_t *pc = &c->pins;
    cJSON *p = cJSON_AddObjectToObject(r, "pins");
    cJSON_AddNumberToObject(p, "ain1", pc->ain1);
    cJSON_AddNumberToObject(p, "ain2", pc->ain2);
    cJSON_AddNumberToObject(p, "bin1", pc->bin1);
    cJSON_AddNumberToObject(p, "bin2", pc->bin2);
    cJSON *po = cJSON_AddArrayToObject(p, "out");
    for (int i = 0; i < NUM_OUT; i++) cJSON_AddItemToArray(po, cJSON_CreateNumber(pc->out[i]));
    cJSON_AddNumberToObject(p, "led", pc->led);
    cJSON_AddNumberToObject(p, "vbat", pc->vbat);
    cJSON *w = cJSON_AddObjectToObject(r, "wifi");
    cJSON_AddStringToObject(w, "ssid", c->wifi_ssid);
    cJSON_AddStringToObject(w, "pw", c->wifi_pw);
    const drive_cfg_t *x = &c->drive;
    cJSON *d = cJSON_AddObjectToObject(r, "drive");
    cJSON_AddNumberToObject(d, "mode", x->mode);
    cJSON_AddBoolToObject(d, "invL", x->inv_l);
    cJSON_AddBoolToObject(d, "invR", x->inv_r);
    cJSON_AddBoolToObject(d, "swap", x->swap);
    cJSON_AddBoolToObject(d, "revSteer", x->rev_steer);
    cJSON_AddNumberToObject(d, "max", x->max_pct);
    cJSON_AddNumberToObject(d, "slow", x->slow_pct);
    cJSON_AddNumberToObject(d, "slowBtn", x->slow_btn);
    cJSON_AddNumberToObject(d, "turn", x->turn_pct);
    cJSON_AddNumberToObject(d, "spin", x->spin_ms);
    cJSON_AddNumberToObject(d, "expo", x->expo_pct);
    cJSON_AddNumberToObject(d, "dead", x->dead_pct);
    cJSON_AddNumberToObject(d, "ramp", x->ramp_ms);
    cJSON_AddNumberToObject(d, "vcap", round2(x->vcap));
    cJSON *o = cJSON_AddArrayToObject(r, "out");
    for (int i = 0; i < NUM_OUT; i++) {
        const out_cfg_t *y = &c->out[i];
        cJSON *e = cJSON_CreateObject();
        cJSON_AddNumberToObject(e, "type", y->type);
        cJSON_AddNumberToObject(e, "mode", y->mode);
        cJSON_AddNumberToObject(e, "btn", y->btn);
        cJSON_AddNumberToObject(e, "axis", y->axis);
        cJSON_AddNumberToObject(e, "min", y->min_us);
        cJSON_AddNumberToObject(e, "max", y->max_us);
        cJSON_AddNumberToObject(e, "maxPct", y->max_pct);
        cJSON_AddNumberToObject(e, "spin", y->spin_ms);
        cJSON_AddNumberToObject(e, "rest", y->rest_deg);
        cJSON_AddNumberToObject(e, "fire", y->fire_deg);
        cJSON_AddNumberToObject(e, "speed", y->speed);
        cJSON_AddItemToArray(o, e);
    }
    const safe_cfg_t *z = &c->safe;
    cJSON *s = cJSON_AddObjectToObject(r, "safe");
    cJSON_AddNumberToObject(s, "wpnCut", z->wpn_cut_ms);
    cJSON_AddNumberToObject(s, "fs", z->fs_ms);
    cJSON_AddNumberToObject(s, "grace", z->grace_ms);
    cJSON_AddNumberToObject(s, "drops", z->drops);
    cJSON_AddNumberToObject(s, "lowWpn", round2(z->low_wpn));
    cJSON_AddNumberToObject(s, "lowDrv", round2(z->low_drv));
    cJSON_AddBoolToObject(s, "lockout", z->lockout);
    char *out = cJSON_PrintUnformatted(r);
    cJSON_Delete(r);
    return out;
}
