#include "net.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "mdns.h"

static const char *TAG = "net";

#define AP_AFTER_MS 60000      // not on a saved network this long: open the access point
#define AP_IDLE_OFF_MS 15000   // joined and nobody on the access point this long: close it
#define JOIN_MS 15000
#define TX_FULL 80             // 20 dBm (units of 0.25 dBm)
#define TX_LOW 34              // 8.5 dBm: some ESP32-C3 boards only join at reduced power

#define EV_UP BIT0
#define EV_FAIL BIT1
#define EV_KICK BIT2

static esp_netif_t *sta_netif, *ap_netif;
static EventGroupHandle_t evg;
static SemaphoreHandle_t op_mx;     // one scan / join at a time
static SemaphoreHandle_t nets_mx;
static wifi_net_t nets[MAX_NETS];
static char host[32], ap_ssid[33], ap_pw[65];
static char cur_ssid[33];
static volatile bool up, ap_on, force_join, leaving, low_tx;
static volatile uint32_t drops;
static volatile uint8_t last_reason;
static volatile int64_t down_since_us;

const char *net_ssid(void) { return up ? cur_ssid : ""; }
const char *net_ap_ssid(void) { return ap_ssid; }
const char *net_host(void) { return host; }
bool net_up(void) { return up; }
bool net_ap_on(void) { return ap_on; }
bool net_low_power(void) { return low_tx; }
uint32_t net_drops(void) { return drops; }
uint8_t net_last_reason(void) { return last_reason; }

int net_clients(void)
{
    if (!ap_on) return 0;
    wifi_sta_list_t l;
    return esp_wifi_ap_get_sta_list(&l) == ESP_OK ? l.num : 0;
}

uint8_t net_channel(void)
{
    wifi_ap_record_t ap;
    return up && esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.primary : 0;
}

int net_rssi(void)
{
    wifi_ap_record_t ap;
    return up && esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}

void net_ip(char *buf, int len)
{
    esp_netif_ip_info_t ip;
    if (up && esp_netif_get_ip_info(sta_netif, &ip) == ESP_OK) snprintf(buf, len, IPSTR, IP2STR(&ip.ip));
    else snprintf(buf, len, "%s", "");
}

const char *net_reason_text(int r)
{
    switch (r) {
    case 0: return "joined";
    case 1: return "no answer from the network";
    case WIFI_REASON_NO_AP_FOUND:
    case WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY:
    case WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD:
    case WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD: return "network not found (is it 2.4 GHz?)";
    case WIFI_REASON_AUTH_FAIL:
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
    case WIFI_REASON_HANDSHAKE_TIMEOUT:
    case WIFI_REASON_MIC_FAILURE:
    case WIFI_REASON_CONNECTION_FAIL: return "wrong password?";
    case WIFI_REASON_BEACON_TIMEOUT: return "signal lost";
    default: return "could not join";
    }
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *d = data;
        if (up) {
            if (!leaving) drops++;
            down_since_us = esp_timer_get_time();
            ESP_LOGW(TAG, "left %s (reason %d)", cur_ssid, d->reason);
        }
        up = false;
        if (!leaving) last_reason = d->reason;
        xEventGroupSetBits(evg, EV_FAIL);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        wifi_config_t c;
        if (esp_wifi_get_config(WIFI_IF_STA, &c) == ESP_OK) snprintf(cur_ssid, sizeof(cur_ssid), "%s", (char *)c.sta.ssid);
        ESP_LOGI(TAG, "joined %s as " IPSTR ", http://%s.local", cur_ssid, IP2STR(&e->ip_info.ip), host);
        up = true;
        xEventGroupSetBits(evg, EV_UP);
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_AP_STACONNECTED) {
        ESP_LOGI(TAG, "phone joined the access point");
    }
}

// ---- access point ----
static void ap_start(void)
{
    if (ap_on) return;
    wifi_config_t ac = {0};
    memcpy(ac.ap.ssid, ap_ssid, strlen(ap_ssid));
    ac.ap.ssid_len = strlen(ap_ssid);
    ac.ap.channel = 1;
    ac.ap.max_connection = 4;
    if (strlen(ap_pw) >= 8) {
        snprintf((char *)ac.ap.password, sizeof(ac.ap.password), "%s", ap_pw);
        ac.ap.authmode = WIFI_AUTH_WPA2_PSK;
    } else {
        ac.ap.authmode = WIFI_AUTH_OPEN;
    }
    leaving = true;
    esp_err_t e = esp_wifi_set_mode(WIFI_MODE_APSTA);
    if (e == ESP_OK) e = esp_wifi_set_config(WIFI_IF_AP, &ac);
    leaving = false;
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "access point failed: %s", esp_err_to_name(e));
        return;
    }
    static bool dns_on;
    if (!dns_on) {
        dns_start();
        dns_on = true;
    }
    ap_on = true;
    ESP_LOGW(TAG, "access point %s open: http://192.168.4.1", ap_ssid);
}

static void ap_stop(void)
{
    if (!ap_on) return;
    ap_on = false;
    leaving = true;
    esp_wifi_set_mode(WIFI_MODE_STA);
    leaving = false;
    ESP_LOGI(TAG, "access point closed");
}

// ---- scan / join (hold op_mx) ----
static int scan_raw(wifi_ap_record_t **out)
{
    *out = NULL;
    if (!up) {
        leaving = true;
        esp_wifi_disconnect();   // a station still trying to join can't scan
        vTaskDelay(pdMS_TO_TICKS(50));
        leaving = false;
    }
    wifi_scan_config_t sc = {.show_hidden = false, .scan_type = WIFI_SCAN_TYPE_ACTIVE,
                             .scan_time.active = {.min = 50, .max = 110}};
    if (esp_wifi_scan_start(&sc, true) != ESP_OK) return 0;
    uint16_t n = 0;
    esp_wifi_scan_get_ap_num(&n);
    if (n > 24) n = 24;
    wifi_ap_record_t *r = calloc(n ? n : 1, sizeof(*r));
    if (!r) {
        esp_wifi_clear_ap_list();
        return 0;
    }
    esp_wifi_scan_get_ap_records(&n, r);   // strongest first
    *out = r;
    return n;
}

static int join(const char *ssid, const char *pw, const uint8_t *bssid, uint8_t ch, int timeout_ms)
{
    wifi_config_t sc = {0};
    snprintf((char *)sc.sta.ssid, sizeof(sc.sta.ssid), "%s", ssid);
    memcpy(sc.sta.password, pw, strnlen(pw, sizeof(sc.sta.password)));
    sc.sta.threshold.authmode = pw[0] ? WIFI_AUTH_WPA_PSK : WIFI_AUTH_OPEN;
    if (bssid) {
        sc.sta.bssid_set = true;
        memcpy(sc.sta.bssid, bssid, 6);
        sc.sta.channel = ch;
        sc.sta.scan_method = WIFI_FAST_SCAN;
    } else {
        // hidden network or not seen in the scan: let the driver look on every channel
        sc.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
        sc.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    }
    // WPA3 / WPA2-WPA3 transition networks
    sc.sta.pmf_cfg.capable = true;
    sc.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;

    leaving = true;
    esp_wifi_disconnect();
    vTaskDelay(pdMS_TO_TICKS(50));
    leaving = false;
    xEventGroupClearBits(evg, EV_UP | EV_FAIL);
    esp_wifi_set_max_tx_power(low_tx ? TX_LOW : TX_FULL);
    if (esp_wifi_set_config(WIFI_IF_STA, &sc) != ESP_OK || esp_wifi_connect() != ESP_OK) return WIFI_REASON_UNSPECIFIED;
    ESP_LOGI(TAG, "joining '%s'%s", ssid, low_tx ? " at low power" : "");
    EventBits_t b = xEventGroupWaitBits(evg, EV_UP | EV_FAIL, pdTRUE, pdFALSE, pdMS_TO_TICKS(timeout_ms));
    if (b & EV_UP) return 0;
    leaving = true;
    esp_wifi_disconnect();
    vTaskDelay(pdMS_TO_TICKS(50));
    leaving = false;
    int r = (b & EV_FAIL) ? last_reason : 1;
    if (!r) r = WIFI_REASON_UNSPECIFIED;
    ESP_LOGW(TAG, "'%s': %s (%d)", ssid, net_reason_text(r), r);
    return r;
}

// Try the saved networks once: the ones seen in a scan, strongest first; then, if none was seen,
// each by name (hidden networks). Returns true when joined.
static bool join_saved(void)
{
    wifi_net_t l[MAX_NETS];
    xSemaphoreTake(nets_mx, portMAX_DELAY);
    memcpy(l, nets, sizeof(l));
    xSemaphoreGive(nets_mx);
    if (!l[0].ssid[0]) return false;

    wifi_ap_record_t *r;
    int n = scan_raw(&r);
    int tried = 0;
    for (int i = 0; i < n && tried < 3 && !up; i++)
        for (int k = 0; k < MAX_NETS; k++)
            if (l[k].ssid[0] && !strcmp((char *)r[i].ssid, l[k].ssid)) {
                tried++;
                join(l[k].ssid, l[k].pw, r[i].bssid, r[i].primary, JOIN_MS);
                break;
            }
    free(r);
    if (up) return true;
    if (!tried)
        for (int k = 0; k < MAX_NETS && l[k].ssid[0] && !up; k++) join(l[k].ssid, l[k].pw, NULL, 0, 10000);
    return up;
}

// ---- the Wi-Fi task ----
static void net_task(void *arg)
{
    int fails = 0;
    int64_t ap_idle_since = 0;
    bool was_up = false;
    uint8_t last_bssid[6];
    uint8_t last_ch = 0;
    for (;;) {
        int64_t now = esp_timer_get_time();
        if (up) {
            if (!was_up) {
                wifi_ap_record_t ap;
                if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
                    memcpy(last_bssid, ap.bssid, 6);
                    last_ch = ap.primary;
                }
            }
            was_up = true;
            fails = 0;
            // joined: close the access point once nobody is using it
            if (ap_on && net_clients() == 0) {
                if (!ap_idle_since) ap_idle_since = now;
                if (now - ap_idle_since > AP_IDLE_OFF_MS * 1000LL) {
                    xSemaphoreTake(op_mx, portMAX_DELAY);
                    ap_stop();
                    xSemaphoreGive(op_mx);
                }
            } else {
                ap_idle_since = 0;
            }
            xEventGroupWaitBits(evg, EV_FAIL | EV_KICK, pdTRUE, pdFALSE, pdMS_TO_TICKS(2000));
            continue;
        }
        ap_idle_since = 0;

        xSemaphoreTake(nets_mx, portMAX_DELAY);
        bool have = nets[0].ssid[0] != 0;
        xSemaphoreGive(nets_mx);
        bool force = force_join;
        force_join = false;

        // nothing saved, or a minute without Wi-Fi: open the access point
        if (!ap_on && (!have || now - down_since_us > AP_AFTER_MS * 1000LL)) {
            xSemaphoreTake(op_mx, portMAX_DELAY);
            ap_start();
            xSemaphoreGive(op_mx);
        }

        int wait_ms;
        if (!have) {
            wait_ms = 30000;
        } else if (ap_on && net_clients() > 0 && !force) {
            // a phone is on the access point: joining could move it to another channel and drop the phone
            wait_ms = 5000;
        } else {
            xSemaphoreTake(op_mx, portMAX_DELAY);
            bool ok = false;
            if (was_up && last_ch) {
                // just dropped (a hiccup mid-match): straight back to the same router, no scan
                for (int i = 0; i < 3 && !ok; i++) {
                    char s[33], p[65];
                    xSemaphoreTake(nets_mx, portMAX_DELAY);
                    snprintf(s, sizeof(s), "%s", cur_ssid);
                    p[0] = 0;
                    for (int k = 0; k < MAX_NETS; k++)
                        if (!strcmp(nets[k].ssid, cur_ssid)) snprintf(p, sizeof(p), "%s", nets[k].pw);
                    xSemaphoreGive(nets_mx);
                    ok = join(s, p, last_bssid, last_ch, 6000) == 0;
                }
                was_up = false;
            }
            if (!ok) ok = join_saved();
            xSemaphoreGive(op_mx);
            if (ok) continue;
            fails++;
            // some boards (XIAO ESP32-C3 among them) fail to join at full power: try lower every other round
            if (fails >= 2) low_tx = !low_tx;
            wait_ms = ap_on ? 20000 : (fails < 3 ? 1000 : 5000);
        }
        xEventGroupWaitBits(evg, EV_KICK, pdTRUE, pdFALSE, pdMS_TO_TICKS(wait_ms));
    }
}

void net_set_nets(const bot_cfg_t *cfg, bool join_now)
{
    xSemaphoreTake(nets_mx, portMAX_DELAY);
    memcpy(nets, cfg->nets, sizeof(nets));
    xSemaphoreGive(nets_mx);
    if (join_now) {
        force_join = true;
        xEventGroupSetBits(evg, EV_KICK);
    }
}

int net_scan(net_seen_t *out, int max)
{
    xSemaphoreTake(op_mx, portMAX_DELAY);
    wifi_ap_record_t *r;
    int n = scan_raw(&r);
    xSemaphoreGive(op_mx);
    int k = 0;
    for (int i = 0; i < n && k < max; i++) {
        if (!r[i].ssid[0]) continue;
        bool dup = false;
        for (int j = 0; j < k; j++) dup |= !strcmp(out[j].ssid, (char *)r[i].ssid);
        if (dup) continue;
        snprintf(out[k].ssid, sizeof(out[k].ssid), "%s", (char *)r[i].ssid);
        out[k].rssi = r[i].rssi;
        out[k].secure = r[i].authmode != WIFI_AUTH_OPEN;
        k++;
    }
    free(r);
    return k;
}

int net_try(const char *ssid, const char *pw, int timeout_ms)
{
    xSemaphoreTake(op_mx, portMAX_DELAY);
    if (up && !strcmp(cur_ssid, ssid)) {
        // already on it (asked again by the flasher)
        xSemaphoreGive(op_mx);
        return 0;
    }
    int r = join(ssid, pw, NULL, 0, timeout_ms);
    if (r) {
        // full power failed: one more go at low power
        low_tx = !low_tx;
        r = join(ssid, pw, NULL, 0, timeout_ms);
    }
    xSemaphoreGive(op_mx);
    if (r) xEventGroupSetBits(evg, EV_KICK);   // back to the saved networks
    return r;
}

void net_start(const bot_cfg_t *cfg)
{
    snprintf(host, sizeof(host), "%s", cfg->host);
    snprintf(ap_pw, sizeof(ap_pw), "%s", cfg->ap_pw);
    memcpy(nets, cfg->nets, sizeof(nets));
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
    snprintf(ap_ssid, sizeof(ap_ssid), "%.26s-%02X%02X", host, mac[4], mac[5]);
    evg = xEventGroupCreate();
    op_mx = xSemaphoreCreateMutex();
    nets_mx = xSemaphoreCreateMutex();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    sta_netif = esp_netif_create_default_wifi_sta();
    ap_netif = esp_netif_create_default_wifi_ap();
    esp_netif_set_hostname(sta_netif, host);   // shows up by this name in the router's device list
    wifi_init_config_t ic = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&ic));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);

    // http://<host>.local, on the home network and on the access point
    if (mdns_init() == ESP_OK) {
        mdns_hostname_set(host);
        mdns_instance_name_set(cfg->name);
        mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0);
    } else {
        ESP_LOGE(TAG, "mDNS failed to start");
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    // no modem sleep: with it the robot only hears the router every beacon (100-300 ms), which
    // shows up as laggy driving and failsafe trips
    esp_wifi_set_ps(WIFI_PS_NONE);
    down_since_us = esp_timer_get_time();
    xTaskCreate(net_task, "net", 4096, NULL, 4, NULL);
}
