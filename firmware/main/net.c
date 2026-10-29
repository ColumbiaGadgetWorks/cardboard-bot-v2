#include "net.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_attr.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "store.h"

static const char *TAG = "net";
static uint8_t channel;
static char ssid[33];
static esp_netif_t *sta_netif;
static EventGroupHandle_t ev;
#define EV_GOT_IP BIT0
#define EV_STA_FAIL BIT1

// survives a brownout reset (not a power cycle), so the phone finds the robot on the same channel
RTC_NOINIT_ATTR static uint32_t rtc_ch_magic;
RTC_NOINIT_ATTR static uint8_t rtc_ch;
#define CH_MAGIC 0xC6A11E15u

uint8_t net_channel(void) { return channel; }
const char *net_ssid(void) { return ssid; }

// Score channels 1, 6 and 11 by what can be heard on and next to them; other CGW robots count
// three times as much as other networks, and strong signals more than weak ones.
static uint8_t pick_channel(void)
{
    static const uint8_t chans[3] = {1, 6, 11};
    float score[3] = {0, 0, 0};
    wifi_ap_record_t *rec = malloc(sizeof(wifi_ap_record_t) * 32);
    if (!rec) return 1;
    for (int k = 0; k < 3; k++) {
        wifi_scan_config_t sc = {
            .channel = chans[k], .show_hidden = true, .scan_type = WIFI_SCAN_TYPE_ACTIVE,
            .scan_time.active = {.min = 100, .max = 160},
        };
        if (esp_wifi_scan_start(&sc, true) != ESP_OK) continue;
        uint16_t n = 32;
        if (esp_wifi_scan_get_ap_records(&n, rec) != ESP_OK) continue;
        for (int i = 0; i < n; i++) {
            float w = (rec[i].rssi + 100) / 10.0f;
            if (w < 1) w = 1;
            if (!strncmp((const char *)rec[i].ssid, "CGW-", 4)) w *= 3;
            for (int j = 0; j < 3; j++) {
                int d = abs((int)rec[i].primary - chans[j]);
                if (d == 0) score[j] += w;
                else if (d < 5) score[j] += w * 0.5f;
            }
        }
    }
    free(rec);
    // ties (an empty room) go to a channel picked from the MAC, so robots switched on together spread out
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
    int best = mac[5] % 3;
    for (int j = 0; j < 3; j++)
        if (score[j] < score[best] - 0.5f) best = j;
    ESP_LOGI(TAG, "channel scores 1:%.1f 6:%.1f 11:%.1f -> %d", score[0], score[1], score[2], chans[best]);
    return chans[best];
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) xEventGroupSetBits(ev, EV_GOT_IP);
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) xEventGroupSetBits(ev, EV_STA_FAIL);
}

void net_start(const bot_cfg_t *cfg)
{
    ev = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();
    sta_netif = esp_netif_create_default_wifi_sta();
    wifi_init_config_t ic = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&ic));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);
    esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, on_event, NULL);

    if (cfg->ch) {
        channel = cfg->ch;
    } else if (esp_reset_reason() == ESP_RST_BROWNOUT && rtc_ch_magic == CH_MAGIC && rtc_ch) {
        channel = rtc_ch;   // skip the scan: the phone reconnects faster
        ESP_LOGI(TAG, "brownout: reusing channel %d", channel);
    } else {
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
        ESP_ERROR_CHECK(esp_wifi_start());
        channel = pick_channel();
        esp_wifi_stop();
    }
    rtc_ch = channel;
    rtc_ch_magic = CH_MAGIC;
    store_set_last_channel(channel);

    if (cfg->ap[0]) {
        snprintf(ssid, sizeof(ssid), "%s", cfg->ap);
    } else {
        snprintf(ssid, sizeof(ssid), "CGW-%.28s", cfg->name);
    }
    wifi_config_t ac = {0};
    memcpy(ac.ap.ssid, ssid, strlen(ssid));
    ac.ap.ssid_len = strlen(ssid);
    ac.ap.channel = channel;
    ac.ap.max_connection = 4;
    if (strlen(cfg->pw) >= 8) {
        snprintf((char *)ac.ap.password, sizeof(ac.ap.password), "%s", cfg->pw);
        ac.ap.authmode = WIFI_AUTH_WPA2_PSK;
    } else {
        ac.ap.authmode = WIFI_AUTH_OPEN;
    }
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ac));
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_NONE);   // lowest latency for the control packets
    ESP_LOGI(TAG, "AP '%s' on channel %d (%s)", ssid, channel, ac.ap.authmode == WIFI_AUTH_OPEN ? "open" : "WPA2");
}

int net_rssi(void)
{
    wifi_sta_list_t l;
    if (esp_wifi_ap_get_sta_list(&l) != ESP_OK || l.num == 0) return 0;
    int best = -127;
    for (int i = 0; i < l.num; i++)
        if (l.sta[i].rssi > best) best = l.sta[i].rssi;
    return best;
}

int net_clients(void)
{
    wifi_sta_list_t l;
    if (esp_wifi_ap_get_sta_list(&l) != ESP_OK) return 0;
    return l.num;
}

bool net_join_club(const bot_cfg_t *cfg, int timeout_ms)
{
    if (!cfg->wifi_ssid[0]) return false;
    wifi_config_t sc = {0};
    snprintf((char *)sc.sta.ssid, sizeof(sc.sta.ssid), "%s", cfg->wifi_ssid);
    snprintf((char *)sc.sta.password, sizeof(sc.sta.password), "%s", cfg->wifi_pw);
    sc.sta.threshold.authmode = cfg->wifi_pw[0] ? WIFI_AUTH_WPA_PSK : WIFI_AUTH_OPEN;
    xEventGroupClearBits(ev, EV_GOT_IP | EV_STA_FAIL);
    if (esp_wifi_set_mode(WIFI_MODE_APSTA) != ESP_OK) return false;
    esp_wifi_set_config(WIFI_IF_STA, &sc);
    for (int attempt = 0; attempt < 3; attempt++) {
        xEventGroupClearBits(ev, EV_STA_FAIL);
        esp_wifi_connect();
        EventBits_t b = xEventGroupWaitBits(ev, EV_GOT_IP | EV_STA_FAIL, pdFALSE, pdFALSE, pdMS_TO_TICKS(timeout_ms));
        if (b & EV_GOT_IP) {
            ESP_LOGI(TAG, "joined %s", cfg->wifi_ssid);
            return true;
        }
    }
    ESP_LOGW(TAG, "could not join %s", cfg->wifi_ssid);
    esp_wifi_disconnect();
    esp_wifi_set_mode(WIFI_MODE_AP);
    return false;
}
