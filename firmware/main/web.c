// Phone <-> robot protocol (secure WebSocket at wss://192.168.4.1/ws)
//
// Phone -> robot, binary, about 50 per second from the driving phone (12 bytes):
//   [0] 0x01  [1] sequence  [2..5] lx ly rx ry (int8, up/right positive)  [6..7] lt rt (uint8)
//   [8..11] buttons (uint32 LE, see BTN_* in config.h)
// Phone -> robot, JSON text: {"t":"hello","id":<random id kept by the phone>}, take {pw}, arm, disarm,
//   cfg {cfg:{...}}, cal {out,us}, reboot, ota, diag
// Robot -> phone, JSON text: hello (role, names, version, settings), st (status, 5 per second),
//   role, saved, diag, err
#include "web.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "app.h"
#include "cJSON.h"
#include "esp_app_desc.h"
#include "esp_http_server.h"
#include "esp_https_server.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "hw.h"
#include "net.h"
#include "store.h"

static const char *TAG = "web";

extern const uint8_t index_gz_start[] asm("_binary_index_html_gz_start");
extern const uint8_t index_gz_end[] asm("_binary_index_html_gz_end");
extern const uint8_t cert_start[] asm("_binary_servercert_pem_start");
extern const uint8_t cert_end[] asm("_binary_servercert_pem_end");
extern const uint8_t key_start[] asm("_binary_prvtkey_pem_start");
extern const uint8_t key_end[] asm("_binary_prvtkey_pem_end");

static httpd_handle_t https, http;
static int driver_fd = -1;
static char driver_id[24];   // the phone that drives; survives that phone reconnecting

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

// ---------------------------------------------------------------- helpers
static esp_err_t ws_send_text(httpd_req_t *req, const char *s)
{
    httpd_ws_frame_t f = {.type = HTTPD_WS_TYPE_TEXT, .payload = (uint8_t *)s, .len = strlen(s)};
    return httpd_ws_send_frame(req, &f);
}

static esp_err_t ws_send_json(httpd_req_t *req, cJSON *j)
{
    char *s = cJSON_PrintUnformatted(j);
    cJSON_Delete(j);
    if (!s) return ESP_ERR_NO_MEM;
    esp_err_t e = ws_send_text(req, s);
    free(s);
    return e;
}

static void ws_send_fd(int fd, const char *s)   // from the server task only
{
    httpd_ws_frame_t f = {.type = HTTPD_WS_TYPE_TEXT, .payload = (uint8_t *)s, .len = strlen(s)};
    httpd_ws_send_frame_async(https, fd, &f);
}

static esp_err_t send_err(httpd_req_t *req, const char *msg)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "t", "err");
    cJSON_AddStringToObject(j, "msg", msg);
    return ws_send_json(req, j);
}

static void set_driver(int fd, const char *id)
{
    if (driver_fd >= 0 && driver_fd != fd) {
        ws_send_fd(driver_fd, "{\"t\":\"role\",\"role\":\"viewer\"}");
        app_lock();
        ctl_link_closed(&g_ctl, now_ms());
        app_unlock();
    }
    driver_fd = fd;
    snprintf(driver_id, sizeof(driver_id), "%s", id);
}

// ---------------------------------------------------------------- commands
static esp_err_t cmd_hello(httpd_req_t *req, int fd, cJSON *m)
{
    cJSON *id = cJSON_GetObjectItem(m, "id");
    const char *ids = cJSON_IsString(id) ? id->valuestring : "";
    // the first phone since power-on drives; the same phone gets it back when it reconnects
    if (ids[0] && (!driver_id[0] || !strcmp(ids, driver_id))) set_driver(fd, ids);

    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "t", "hello");
    cJSON_AddStringToObject(j, "role", fd == driver_fd ? "driver" : "viewer");
    cJSON_AddStringToObject(j, "ver", app_version());
    cJSON_AddStringToObject(j, "ssid", net_ssid());
    cJSON_AddNumberToObject(j, "ch", net_channel());
    app_lock();
    cJSON_AddBoolToObject(j, "pwSet", g_cfg.pw[0] != 0);
    char *cs = cfg_to_json(&g_cfg);
    app_unlock();
    cJSON *cj = cs ? cJSON_Parse(cs) : NULL;
    free(cs);
    if (cj) {
        // the AP and club Wi-Fi passwords go only to the driving phone
        if (fd != driver_fd) {
            cJSON_ReplaceItemInObject(cj, "pw", cJSON_CreateString(""));
            cJSON *w = cJSON_GetObjectItem(cj, "wifi");
            if (w) cJSON_ReplaceItemInObject(w, "pw", cJSON_CreateString(""));
        }
        cJSON_AddItemToObject(j, "cfg", cj);
    }
    return ws_send_json(req, j);
}

static esp_err_t cmd_take(httpd_req_t *req, int fd, cJSON *m)
{
    cJSON *pw = cJSON_GetObjectItem(m, "pw");
    cJSON *id = cJSON_GetObjectItem(m, "id");
    app_lock();
    bool ok = !g_cfg.pw[0] || (cJSON_IsString(pw) && !strcmp(pw->valuestring, g_cfg.pw));
    app_unlock();
    if (!ok) return send_err(req, "Wrong password");
    set_driver(fd, cJSON_IsString(id) ? id->valuestring : "phone");
    return ws_send_text(req, "{\"t\":\"role\",\"role\":\"driver\"}");
}

// network settings only take effect after a restart
static bool needs_reboot(const bot_cfg_t *a, const bot_cfg_t *b)
{
    return strcmp(a->ap, b->ap) || strcmp(a->pw, b->pw) || a->ch != b->ch || a->bsense != b->bsense ||
           (strcmp(a->name, b->name) && !a->ap[0]);
}

static esp_err_t cmd_cfg(httpd_req_t *req, cJSON *m)
{
    cJSON *c = cJSON_GetObjectItem(m, "cfg");
    if (!cJSON_IsObject(c)) return send_err(req, "No settings");
    char *s = cJSON_PrintUnformatted(c);
    if (!s) return ESP_ERR_NO_MEM;
    bot_cfg_t *n = malloc(sizeof(bot_cfg_t));
    if (!n) {
        free(s);
        return ESP_ERR_NO_MEM;
    }
    app_lock();
    *n = g_cfg;
    bool ok = cfg_from_json(n, s);
    bool reboot = ok && needs_reboot(&g_cfg, n);
    if (ok) g_cfg = *n;
    app_unlock();
    free(s);
    if (ok) ok = store_save(n);
    free(n);
    if (!ok) return send_err(req, "Saving settings failed");
    char out[64];
    snprintf(out, sizeof(out), "{\"t\":\"saved\",\"reboot\":%s}", reboot ? "true" : "false");
    return ws_send_text(req, out);
}

static const char *reset_name(int r)
{
    switch (r) {
    case ESP_RST_POWERON: return "power on";
    case ESP_RST_SW: return "restart";
    case ESP_RST_PANIC: return "crash";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_DEEPSLEEP: return "sleep";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_USB: return "USB";
    case ESP_RST_EXT: return "reset pin";
    default: return "other";
    }
}

static esp_err_t cmd_diag(httpd_req_t *req)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "t", "diag");
    cJSON *r = cJSON_AddArrayToObject(j, "resets");
    app_lock();
    for (int i = 0; i < g_diag.nresets; i++) cJSON_AddItemToArray(r, cJSON_CreateString(reset_name(g_diag.resets[i])));
    cJSON_AddNumberToObject(j, "vmin", g_diag.vmin);
    app_unlock();
    cJSON_AddNumberToObject(j, "rssi", net_rssi());
    cJSON_AddNumberToObject(j, "clients", net_clients());
    cJSON_AddNumberToObject(j, "ch", net_channel());
    cJSON_AddStringToObject(j, "ssid", net_ssid());
    cJSON_AddNumberToObject(j, "up", now_ms() / 1000);
    cJSON_AddNumberToObject(j, "heap", esp_get_free_heap_size());
    cJSON_AddNumberToObject(j, "heapMin", esp_get_minimum_free_heap_size());
    cJSON_AddStringToObject(j, "ver", app_version());
    const esp_partition_t *p = esp_ota_get_running_partition();
    cJSON_AddStringToObject(j, "slot", p ? p->label : "?");
    return ws_send_json(req, j);
}

static esp_err_t handle_text(httpd_req_t *req, int fd, const char *txt)
{
    cJSON *m = cJSON_Parse(txt);
    if (!m) return ESP_OK;
    cJSON *t = cJSON_GetObjectItem(m, "t");
    const char *cmd = cJSON_IsString(t) ? t->valuestring : "";
    esp_err_t e = ESP_OK;
    bool drv = fd == driver_fd;
    app_lock();
    bool armed = g_ctl.armed;
    app_unlock();

    if (!strcmp(cmd, "hello")) e = cmd_hello(req, fd, m);
    else if (!strcmp(cmd, "take")) e = cmd_take(req, fd, m);
    else if (!strcmp(cmd, "diag")) e = cmd_diag(req);
    else if (!drv) e = send_err(req, "Only the driving phone can do that");
    else if (!strcmp(cmd, "arm")) {
        app_lock();
        ctl_arm(&g_ctl, &g_cfg, now_ms());
        app_unlock();
    } else if (!strcmp(cmd, "disarm")) {
        app_lock();
        ctl_disarm(&g_ctl, "Disarmed");
        app_unlock();
    } else if (armed) e = send_err(req, "Disarm first");
    else if (!strcmp(cmd, "cfg")) e = cmd_cfg(req, m);
    else if (!strcmp(cmd, "cal")) {
        cJSON *o = cJSON_GetObjectItem(m, "out"), *us = cJSON_GetObjectItem(m, "us");
        if (cJSON_IsNumber(o) && cJSON_IsNumber(us)) app_calibrate(o->valueint, us->valueint);
    } else if (!strcmp(cmd, "reboot")) app_reboot_soon();
    else if (!strcmp(cmd, "ota")) ota_start_pull();
    cJSON_Delete(m);
    return e;
}

static void handle_control(int fd, const uint8_t *p, size_t n)
{
    if (fd != driver_fd || n < 12 || p[0] != 0x01) return;
    ctl_input_t in;
    for (int i = 0; i < 4; i++) in.ax[i] = (int8_t)p[2 + i];
    in.trig[0] = p[6];
    in.trig[1] = p[7];
    in.btn = p[8] | p[9] << 8 | p[10] << 16 | (uint32_t)p[11] << 24;
    app_lock();
    ctl_input(&g_ctl, &in, now_ms());
    app_unlock();
}

static esp_err_t ws_handler(httpd_req_t *req)
{
    if (req->method == HTTP_GET) return ESP_OK;   // handshake
    int fd = httpd_req_to_sockfd(req);
    httpd_ws_frame_t f = {0};
    esp_err_t e = httpd_ws_recv_frame(req, &f, 0);
    if (e != ESP_OK) return e;
    if (f.len == 0 || f.len > 4096) return f.len ? ESP_FAIL : ESP_OK;
    uint8_t *buf = malloc(f.len + 1);
    if (!buf) return ESP_ERR_NO_MEM;
    f.payload = buf;
    e = httpd_ws_recv_frame(req, &f, f.len);
    if (e == ESP_OK) {
        buf[f.len] = 0;
        if (f.type == HTTPD_WS_TYPE_BINARY) handle_control(fd, buf, f.len);
        else if (f.type == HTTPD_WS_TYPE_TEXT) e = handle_text(req, fd, (const char *)buf);
    }
    free(buf);
    return e;
}

static void on_close(httpd_handle_t hd, int fd)
{
    if (fd == driver_fd) {
        driver_fd = -1;   // driver_id stays: the same phone takes over again on reconnect
        app_lock();
        ctl_link_closed(&g_ctl, now_ms());
        app_unlock();
    }
    close(fd);
}

// ---------------------------------------------------------------- status broadcast
typedef struct {
    int len;
    char s[];
} bc_t;

static void broadcast_work(void *arg)
{
    bc_t *b = arg;
    size_t n = 8;
    int fds[8];
    if (httpd_get_client_list(https, &n, fds) == ESP_OK) {
        for (size_t i = 0; i < n; i++) {
            if (httpd_ws_get_fd_info(https, fds[i]) != HTTPD_WS_CLIENT_WEBSOCKET) continue;
            // the status ends with the receiver's own role
            b->s[b->len - 2] = fds[i] == driver_fd ? '1' : '0';
            httpd_ws_frame_t f = {.type = HTTPD_WS_TYPE_TEXT, .payload = (uint8_t *)b->s, .len = b->len};
            httpd_ws_send_frame_async(https, fds[i], &f);
        }
    }
    free(b);
}

void web_broadcast_status(void)
{
    if (!https) return;
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "t", "st");
    app_lock();
    ctl_t *c = &g_ctl;
    cJSON_AddBoolToObject(j, "armed", c->armed);
    cJSON_AddBoolToObject(j, "fs", c->failsafe);
    cJSON_AddBoolToObject(j, "wl", c->weapon_lock);
    cJSON_AddBoolToObject(j, "dl", c->drive_lock);
    cJSON_AddBoolToObject(j, "run", c->weapon_running);
    cJSON_AddNumberToObject(j, "led", c->led);
    cJSON_AddStringToObject(j, "reason", c->reason);
    cJSON_AddNumberToObject(j, "vb", c->vbat < 0 ? -1 : (int)(c->vbat * 100) / 100.0);
    cJSON_AddNumberToObject(j, "ml", (int)(c->motor[0] * 100));
    cJSON_AddNumberToObject(j, "mr", (int)(c->motor[1] * 100));
    cJSON *o = cJSON_AddArrayToObject(j, "out");
    for (int i = 0; i < NUM_OUT; i++) cJSON_AddItemToArray(o, cJSON_CreateNumber(c->out_us[i]));
    cJSON_AddStringToObject(j, "driver", g_cfg.driver);
    app_unlock();
    cJSON_AddStringToObject(j, "upd", ota_status());
    cJSON_AddNumberToObject(j, "rssi", net_rssi());
    cJSON_AddNumberToObject(j, "you", 0);
    char *s = cJSON_PrintUnformatted(j);
    cJSON_Delete(j);
    if (!s) return;
    int len = strlen(s);   // ends in ...,"you":0}
    bc_t *b = malloc(sizeof(bc_t) + len + 1);
    if (b) {
        b->len = len;
        memcpy(b->s, s, len + 1);
        if (httpd_queue_work(https, broadcast_work, b) != ESP_OK) free(b);
    }
    free(s);
}

// ---------------------------------------------------------------- pages
static esp_err_t index_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Content-Encoding", "gzip");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache");
    return httpd_resp_send(req, (const char *)index_gz_start, index_gz_end - index_gz_start);
}

static esp_err_t nothing_handler(httpd_req_t *req)
{
    httpd_resp_set_status(req, "204 No Content");
    return httpd_resp_send(req, NULL, 0);
}

// Firmware upload from the phone: POST /ota?id=<driving phone's id>, body = app .bin
static esp_err_t ota_handler(httpd_req_t *req)
{
    char q[64] = "", id[24] = "";
    httpd_req_get_url_query_str(req, q, sizeof(q));
    httpd_query_key_value(q, "id", id, sizeof(id));
    app_lock();
    bool armed = g_ctl.armed;
    app_unlock();
    if (!driver_id[0] || strcmp(id, driver_id)) {
        httpd_resp_set_status(req, "403 Forbidden");
        return httpd_resp_sendstr(req, "Only the driving phone can update");
    }
    if (armed) {
        httpd_resp_set_status(req, "409 Conflict");
        return httpd_resp_sendstr(req, "Disarm first");
    }
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t h;
    if (!part || esp_ota_begin(part, OTA_WITH_SEQUENTIAL_WRITES, &h) != ESP_OK) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_sendstr(req, "No update slot");
    }
    char *buf = malloc(4096);
    int total = req->content_len, got = 0;
    bool ok = buf != NULL;
    while (ok && got < total) {
        int r = httpd_req_recv(req, buf, 4096);
        if (r == HTTPD_SOCK_ERR_TIMEOUT) continue;
        if (r <= 0) {
            ok = false;
            break;
        }
        if (got == 0 && (uint8_t)buf[0] != 0xE9) ok = false;   // not an ESP32 app image
        if (ok && esp_ota_write(h, buf, r) != ESP_OK) ok = false;
        got += r;
        char st[32];
        snprintf(st, sizeof(st), "Uploading %d%%", (int)(100LL * got / (total ? total : 1)));
        ota_set_status(st);
    }
    free(buf);
    if (ok && esp_ota_end(h) == ESP_OK && esp_ota_set_boot_partition(part) == ESP_OK) {
        ota_set_status("Restarting");
        httpd_resp_sendstr(req, "OK");
        app_reboot_soon();
        return ESP_OK;
    }
    if (!ok) esp_ota_abort(h);
    ota_set_status("");
    httpd_resp_set_status(req, "400 Bad Request");
    return httpd_resp_sendstr(req, "Update failed: not a valid firmware file");
}

// plain HTTP on port 80: what the phone's captive-portal check and typed addresses land on
static const char LANDING[] =
    "<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>Cardboard Bot</title><style>body{font:18px system-ui,sans-serif;margin:24px;background:#f4ede1;color:#2b2118}"
    "a.b{display:block;padding:16px;margin:16px 0;background:#c8402e;color:#fff;text-align:center;border-radius:10px;"
    "text-decoration:none;font-weight:700}small{color:#6b5a48}</style></head><body><h2>Cardboard Bot</h2>"
    "<p>Open the controller in <b>Chrome</b> or <b>Safari</b>. This sign-in pop-up can't run it.</p>"
    // Android: an intent link leaves the captive-portal window and opens Chrome directly
    "<a class=b href='intent://192.168.4.1/#Intent;scheme=https;package=com.android.chrome;end'>Open in Chrome</a>"
    "<p><small>Not Android, or no Chrome? Open <b>https://192.168.4.1</b> in your browser.</small></p>"
    "<p><small>The first time, the browser warns about the certificate: tap <i>Advanced</i>, then <i>Proceed</i>. "
    "Club phones can <a href='/cgw-robot.crt'>install the certificate</a> once to skip the warning on every robot."
    "</small></p></body></html>";

// What iOS / macOS expect from captive.apple.com when there's no portal
static const char APPLE_OK[] = "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>";

static esp_err_t landing_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    // iPhones: answer the captive check as "online". Their sign-in sheet can't open the controller and
    // disconnects from the robot when closed, so it's better that it doesn't appear at all.
    char ua[96] = "";
    if (httpd_req_get_hdr_value_str(req, "User-Agent", ua, sizeof(ua)) != ESP_ERR_NOT_FOUND &&
        strstr(ua, "CaptiveNetworkSupport"))
        return httpd_resp_send(req, APPLE_OK, sizeof(APPLE_OK) - 1);
    return httpd_resp_send(req, LANDING, sizeof(LANDING) - 1);
}

static esp_err_t cert_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "application/x-x509-ca-cert");
    return httpd_resp_send(req, (const char *)cert_start, cert_end - cert_start - 1);
}

void web_start(void)
{
    httpd_ssl_config_t sc = HTTPD_SSL_CONFIG_DEFAULT();
    sc.servercert = cert_start;
    sc.servercert_len = cert_end - cert_start;
    sc.prvtkey_pem = key_start;
    sc.prvtkey_len = key_end - key_start;
    sc.httpd.max_open_sockets = 6;
    sc.httpd.max_uri_handlers = 8;
    sc.httpd.lru_purge_enable = true;
    sc.httpd.close_fn = on_close;
    sc.httpd.recv_wait_timeout = 10;
    sc.httpd.send_wait_timeout = 10;
    sc.httpd.stack_size = 10240;
    sc.httpd.ctrl_port = 32768;
    if (httpd_ssl_start(&https, &sc) != ESP_OK) {
        ESP_LOGE(TAG, "HTTPS server failed to start");
        https = NULL;
    } else {
        httpd_uri_t u_index = {.uri = "/", .method = HTTP_GET, .handler = index_handler};
        httpd_uri_t u_ws = {.uri = "/ws", .method = HTTP_GET, .handler = ws_handler, .is_websocket = true};
        httpd_uri_t u_ota = {.uri = "/ota", .method = HTTP_POST, .handler = ota_handler};
        httpd_uri_t u_fav = {.uri = "/favicon.ico", .method = HTTP_GET, .handler = nothing_handler};
        httpd_register_uri_handler(https, &u_index);
        httpd_register_uri_handler(https, &u_ws);
        httpd_register_uri_handler(https, &u_ota);
        httpd_register_uri_handler(https, &u_fav);
    }

    httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
    hc.server_port = 80;
    hc.ctrl_port = 32769;
    hc.max_open_sockets = 3;
    hc.lru_purge_enable = true;
    hc.uri_match_fn = httpd_uri_match_wildcard;
    if (httpd_start(&http, &hc) == ESP_OK) {
        httpd_uri_t u_cert = {.uri = "/cgw-robot.crt", .method = HTTP_GET, .handler = cert_handler};
        httpd_uri_t u_any = {.uri = "/*", .method = HTTP_GET, .handler = landing_handler};
        httpd_register_uri_handler(http, &u_cert);
        httpd_register_uri_handler(http, &u_any);
    }
}
