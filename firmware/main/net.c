#include "net.h"

#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "mdns.h"

static const char *TAG = "net";
static esp_netif_t *sta_netif;
static char ssid[33];
static char host[32];
static volatile bool up;           // joined and has an IP
static volatile uint32_t drops;    // times the Wi-Fi link dropped since boot
static volatile uint8_t last_reason;
static esp_timer_handle_t retry_timer;
static int retry_ms;

const char *net_ssid(void) { return ssid; }
const char *net_host(void) { return host; }
bool net_up(void) { return up; }
uint32_t net_drops(void) { return drops; }
uint8_t net_last_reason(void) { return last_reason; }

uint8_t net_channel(void)
{
    wifi_ap_record_t ap;
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.primary : 0;
}

int net_rssi(void)
{
    wifi_ap_record_t ap;
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}

void net_ip(char *buf, int len)
{
    esp_netif_ip_info_t ip;
    if (up && esp_netif_get_ip_info(sta_netif, &ip) == ESP_OK) snprintf(buf, len, IPSTR, IP2STR(&ip.ip));
    else snprintf(buf, len, "%s", "");
}

static void retry_cb(void *arg) { esp_wifi_connect(); }

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *d = data;
        if (up) drops++;
        up = false;
        last_reason = d->reason;
        // retry for ever: quickly at first (a short drop mid-match), then every few seconds
        ESP_LOGW(TAG, "Wi-Fi lost (reason %d), retry in %d ms", d->reason, retry_ms);
        esp_timer_start_once(retry_timer, (uint64_t)retry_ms * 1000);
        retry_ms = retry_ms < 4000 ? retry_ms * 2 : 5000;
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        ESP_LOGI(TAG, "joined %s as " IPSTR ", http://%s.local", ssid, IP2STR(&e->ip_info.ip), host);
        up = true;
        retry_ms = 250;
    }
}

void net_start(const bot_cfg_t *cfg)
{
    snprintf(ssid, sizeof(ssid), "%s", cfg->wifi_ssid);
    snprintf(host, sizeof(host), "%s", cfg->host);
    retry_ms = 250;

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    sta_netif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(sta_netif, host);   // shows up by this name in the router's device list
    wifi_init_config_t ic = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&ic));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);
    esp_timer_create_args_t ta = {.callback = retry_cb, .name = "wifi_retry"};
    esp_timer_create(&ta, &retry_timer);

    // http://<host>.local
    if (mdns_init() == ESP_OK) {
        mdns_hostname_set(host);
        mdns_instance_name_set(cfg->name);
        mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0);
    } else {
        ESP_LOGE(TAG, "mDNS failed to start");
    }

    if (!ssid[0]) {
        ESP_LOGE(TAG, "no Wi-Fi set: set it in the web flasher");
        return;
    }
    wifi_config_t sc = {0};
    snprintf((char *)sc.sta.ssid, sizeof(sc.sta.ssid), "%s", cfg->wifi_ssid);
    snprintf((char *)sc.sta.password, sizeof(sc.sta.password), "%s", cfg->wifi_pw);
    sc.sta.threshold.authmode = cfg->wifi_pw[0] ? WIFI_AUTH_WPA_PSK : WIFI_AUTH_OPEN;
    // scan every channel and pick the strongest access point (networks with several)
    sc.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    sc.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    // WPA3 / WPA2-WPA3 transition networks
    sc.sta.pmf_cfg.capable = true;
    sc.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sc));
    ESP_ERROR_CHECK(esp_wifi_start());
    // no modem sleep: with it the robot only hears the router every beacon (100-300 ms), which
    // shows up as laggy driving and failsafe trips
    esp_wifi_set_ps(WIFI_PS_NONE);
    ESP_LOGI(TAG, "joining '%s'", ssid);
}
