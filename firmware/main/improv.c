// Improv Wi-Fi over the USB port (https://www.improv-wifi.com/serial/): the web flasher sends
// the Wi-Fi name and password right after installing, and gets the robot's address back.
// Packets share the port with the log, so they are written in one piece and found by their
// "IMPROV" header.
#include "improv.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "app.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "hal/usb_serial_jtag_ll.h"
#include "net.h"
#include "store.h"

static const char *TAG = "improv";

enum { T_STATE = 1, T_ERROR = 2, T_RPC = 3, T_RESULT = 4 };
enum { S_READY = 2, S_PROVISIONING = 3, S_PROVISIONED = 4 };
enum { E_NONE = 0, E_BAD_PACKET = 1, E_UNKNOWN_CMD = 2, E_NO_JOIN = 3, E_UNKNOWN = 0xFF };
enum { C_WIFI = 1, C_STATE = 2, C_INFO = 3, C_SCAN = 4 };

static void send(uint8_t type, const uint8_t *data, int len)
{
    uint8_t p[300];
    if (len > (int)sizeof(p) - 11) return;
    memcpy(p, "IMPROV", 6);
    p[6] = 1;
    p[7] = type;
    p[8] = len;
    memcpy(p + 9, data, len);
    uint8_t sum = 0;
    for (int i = 0; i < 9 + len; i++) sum += p[i];
    p[9 + len] = sum;
    p[10 + len] = '\n';
    fflush(stdout);
    write(fileno(stdout), p, 11 + len);   // one write: the log can't land in the middle
}

static void send_byte(uint8_t type, uint8_t v) { send(type, &v, 1); }

// RPC result: command, total length, then length-prefixed strings
static void send_result(uint8_t cmd, const char *const *s, int n)
{
    uint8_t d[256];
    int k = 2;
    for (int i = 0; i < n; i++) {
        int l = strlen(s[i]);
        if (k + 1 + l > (int)sizeof(d)) break;
        d[k++] = l;
        memcpy(d + k, s[i], l);
        k += l;
    }
    d[0] = cmd;
    d[1] = k - 2;
    send(T_RESULT, d, k);
}

static void send_url(uint8_t cmd)
{
    char ip[16], url[40], local[48];
    net_ip(ip, sizeof(ip));
    snprintf(url, sizeof(url), "http://%s/", ip);
    snprintf(local, sizeof(local), "http://%s.local/", net_host());
    const char *s[] = {url, local};
    send_result(cmd, s, ip[0] ? 2 : 0);
}

static void handle(const uint8_t *d, int len)
{
    if (len < 2 || d[1] + 2 > len) {
        send_byte(T_ERROR, E_BAD_PACKET);
        return;
    }
    uint8_t cmd = d[0];
    const uint8_t *a = d + 2;
    int alen = d[1];
    switch (cmd) {
    case C_STATE:
        send_byte(T_STATE, net_up() ? S_PROVISIONED : S_READY);
        if (net_up()) send_url(C_STATE);
        break;
    case C_INFO: {
        char name[24];
        app_lock();
        snprintf(name, sizeof(name), "%s", g_cfg.name);
        app_unlock();
        const char *s[] = {"Cardboard Bot", app_version(), "ESP32-C3", name};
        send_result(C_INFO, s, 4);
        break;
    }
    case C_SCAN: {
        static net_seen_t seen[16];
        int n = net_scan(seen, 16);
        for (int i = 0; i < n; i++) {
            char rssi[8];
            snprintf(rssi, sizeof(rssi), "%d", seen[i].rssi);
            const char *s[] = {seen[i].ssid, rssi, seen[i].secure ? "YES" : "NO"};
            send_result(C_SCAN, s, 3);
        }
        send_result(C_SCAN, NULL, 0);
        break;
    }
    case C_WIFI: {
        char ssid[33] = {0}, pw[65] = {0};
        int sl = alen > 0 ? a[0] : 0;
        if (sl < 1 || sl > 32 || 1 + sl >= alen + 1) {
            send_byte(T_ERROR, E_BAD_PACKET);
            break;
        }
        memcpy(ssid, a + 1, sl);
        int pl = 1 + sl < alen ? a[1 + sl] : 0;
        if (pl > 64 || 2 + sl + pl > alen) {
            send_byte(T_ERROR, E_BAD_PACKET);
            break;
        }
        memcpy(pw, a + 2 + sl, pl);
        send_byte(T_STATE, S_PROVISIONING);
        int r = net_try(ssid, pw, 15000);
        if (r) {
            ESP_LOGW(TAG, "could not join '%s': %s", ssid, net_reason_text(r));
            send_byte(T_ERROR, E_NO_JOIN);
            send_byte(T_STATE, S_READY);
            break;
        }
        // joined: save it first in the list so it is tried first from now on
        static bot_cfg_t c;
        app_lock();
        cfg_net_add(&g_cfg, ssid, pw);
        c = g_cfg;
        app_unlock();
        store_save(&c);
        net_set_nets(&c, false);
        send_byte(T_STATE, S_PROVISIONED);
        send_url(C_WIFI);
        break;
    }
    default:
        send_byte(T_ERROR, E_UNKNOWN_CMD);
    }
}

static void improv_task(void *arg)
{
    static uint8_t buf[300];
    int n = 0;
    for (;;) {
        uint8_t in[64];
        int got = usb_serial_jtag_ll_rxfifo_data_available() ? usb_serial_jtag_ll_read_rxfifo(in, sizeof(in)) : 0;
        if (!got) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        for (int i = 0; i < got; i++) {
            uint8_t b = in[i];
            // match the "IMPROV" header byte by byte, then collect the rest
            if (n < 6) {
                if (b == "IMPROV"[n]) buf[n++] = b;
                else n = b == 'I' ? (buf[0] = b, 1) : 0;
                continue;
            }
            buf[n++] = b;
            if (n < 9) continue;
            int len = buf[8];
            if (n < 10 + len) continue;
            uint8_t sum = 0;
            for (int k = 0; k < 9 + len; k++) sum += buf[k];
            if (buf[6] != 1) {
                // other protocol version: ignore
            } else if (sum != buf[9 + len]) {
                send_byte(T_ERROR, E_BAD_PACKET);
            } else if (buf[7] == T_RPC) {
                send_byte(T_ERROR, E_NONE);
                handle(buf + 9, len);
            }
            n = 0;
        }
    }
}

void improv_start(void)
{
    // packets carry raw bytes: no "\n" -> "\r\n" on the way out
    usb_serial_jtag_vfs_set_tx_line_endings(ESP_LINE_ENDINGS_LF);
    xTaskCreate(improv_task, "improv", 4096, NULL, 3, NULL);
}
