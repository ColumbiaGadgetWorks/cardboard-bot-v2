#include "store.h"

#include <stdlib.h>
#include <string.h>

#include "esp_log.h"
#include "esp_partition.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "store";
#define BOTCFG_SUBTYPE 0x40

static const esp_partition_t *part(void)
{
    return esp_partition_find_first(ESP_PARTITION_TYPE_DATA, BOTCFG_SUBTYPE, "botcfg");
}

void store_init(void)
{
    esp_err_t e = nvs_flash_init();
    if (e == ESP_ERR_NVS_NO_FREE_PAGES || e == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        e = nvs_flash_init();
    }
    ESP_ERROR_CHECK(e);
}

bool store_load(bot_cfg_t *c)
{
    cfg_defaults(c);
    const esp_partition_t *p = part();
    if (!p) {
        ESP_LOGE(TAG, "no botcfg partition");
        return false;
    }
    uint8_t *img = malloc(BOTCFG_SIZE + 1);
    if (!img) return false;
    bool ok = false;
    const char *json;
    uint32_t len;
    if (esp_partition_read(p, 0, img, BOTCFG_SIZE) == ESP_OK && cfg_parse_image(img, BOTCFG_SIZE, &json, &len)) {
        char *s = malloc(len + 1);
        if (s) {
            memcpy(s, json, len);
            s[len] = 0;
            ok = cfg_from_json(c, s);
            free(s);
        }
    }
    free(img);
    if (!ok) ESP_LOGW(TAG, "botcfg blank or damaged, using defaults");
    cfg_sanitize(c);
    return ok;
}

bool store_save(const bot_cfg_t *c)
{
    const esp_partition_t *p = part();
    if (!p) return false;
    char *json = cfg_to_json(c);
    if (!json) return false;
    uint8_t *img = malloc(BOTCFG_SIZE);
    bool ok = false;
    if (img && cfg_make_image(json, img)) {
        ok = esp_partition_erase_range(p, 0, BOTCFG_SIZE) == ESP_OK &&
             esp_partition_write(p, 0, img, BOTCFG_SIZE) == ESP_OK;
    }
    free(img);
    free(json);
    if (!ok) ESP_LOGE(TAG, "saving settings failed");
    return ok;
}

void store_push_reset(uint8_t reason)
{
    uint8_t h[RESET_HISTORY] = {0};
    nvs_handle_t n;
    if (nvs_open("diag", NVS_READWRITE, &n) != ESP_OK) return;
    size_t sz = sizeof(h);
    nvs_get_blob(n, "rst", h, &sz);
    memmove(h + 1, h, RESET_HISTORY - 1);
    h[0] = reason;
    nvs_set_blob(n, "rst", h, sizeof(h));
    nvs_commit(n);
    nvs_close(n);
}

int store_resets(uint8_t out[RESET_HISTORY])
{
    memset(out, 0, RESET_HISTORY);
    nvs_handle_t n;
    if (nvs_open("diag", NVS_READONLY, &n) != ESP_OK) return 0;
    size_t sz = RESET_HISTORY;
    nvs_get_blob(n, "rst", out, &sz);
    nvs_close(n);
    int k = 0;
    while (k < RESET_HISTORY && out[k]) k++;
    return k;
}

uint8_t store_last_channel(void)
{
    uint8_t ch = 0;
    nvs_handle_t n;
    if (nvs_open("diag", NVS_READONLY, &n) == ESP_OK) {
        nvs_get_u8(n, "ch", &ch);
        nvs_close(n);
    }
    return ch;
}

void store_set_last_channel(uint8_t ch)
{
    nvs_handle_t n;
    if (nvs_open("diag", NVS_READWRITE, &n) != ESP_OK) return;
    nvs_set_u8(n, "ch", ch);
    nvs_commit(n);
    nvs_close(n);
}
