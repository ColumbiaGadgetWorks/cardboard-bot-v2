// Pull firmware from GitHub Pages over club Wi-Fi. (Phone uploads are in web.c.)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "net.h"

static const char *TAG = "ota";
static char status[48];
static volatile bool busy;

#ifndef FW_PAGES_BASE
#define FW_PAGES_BASE "https://columbiagadgetworks.github.io/cardboard-bot-v2"
#endif

const char *ota_status(void) { return status; }
void ota_set_status(const char *s) { snprintf(status, sizeof(status), "%s", s); }

// stable / beta come from the Pages site this firmware was built for; custom is any folder URL
const char *ota_base_url(const bot_cfg_t *c, char *buf, int len)
{
    if (!strcmp(c->src, "custom") && c->src_url[0]) {
        int n = strlen(c->src_url);
        snprintf(buf, len, "%s%s", c->src_url, c->src_url[n - 1] == '/' ? "" : "/");
    } else {
        snprintf(buf, len, "%s/fw/%s/", FW_PAGES_BASE, !strcmp(c->src, "beta") ? "beta" : "stable");
    }
    return buf;
}

static void fail(const char *msg)
{
    ESP_LOGW(TAG, "%s", msg);
    ota_set_status(msg);
    vTaskDelay(pdMS_TO_TICKS(8000));
    ota_set_status("");
    busy = false;
    vTaskDelete(NULL);
}

static void pull_task(void *arg)
{
    bot_cfg_t *c = malloc(sizeof(bot_cfg_t));
    if (!c) fail("Out of memory");
    app_lock();
    *c = g_cfg;
    app_unlock();
    static char url[200];
    ota_base_url(c, url, sizeof(url) - 8);
    strcat(url, "app.bin");

    ota_set_status("Joining club Wi-Fi");
    bool joined = net_join_club(c, 10000);
    free(c);
    if (!joined) fail("Can't join the club Wi-Fi");

    ota_set_status("Downloading");
    ESP_LOGI(TAG, "pulling %s", url);
    esp_http_client_config_t hc = {
        .url = url, .crt_bundle_attach = esp_crt_bundle_attach, .timeout_ms = 15000, .keep_alive_enable = true,
        .buffer_size = 2048,
    };
    esp_https_ota_config_t oc = {.http_config = &hc};
    esp_https_ota_handle_t h = NULL;
    if (esp_https_ota_begin(&oc, &h) != ESP_OK) fail("Download failed: check the firmware source");
    esp_err_t e;
    while ((e = esp_https_ota_perform(h)) == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
        int got = esp_https_ota_get_image_len_read(h), total = esp_https_ota_get_image_size(h);
        char st[32];
        snprintf(st, sizeof(st), "Downloading %d%%", total > 0 ? (int)(100LL * got / total) : 0);
        ota_set_status(st);
    }
    if (e != ESP_OK || !esp_https_ota_is_complete_data_received(h)) {
        esp_https_ota_abort(h);
        fail("Download failed");
    }
    if (esp_https_ota_finish(h) != ESP_OK) fail("Downloaded file is not valid firmware");
    ota_set_status("Restarting");
    app_reboot_soon();
    vTaskDelete(NULL);
}

void ota_start_pull(void)
{
    if (busy) return;
    busy = true;
    if (xTaskCreate(pull_task, "ota", 8192, NULL, 5, NULL) != pdPASS) busy = false;
}
