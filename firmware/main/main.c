// Cardboard Bot v2 firmware for the Seeed XIAO ESP32-C3 on the CGW main board.
#include <string.h>

#include "app.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "hw.h"
#include "net.h"
#include "store.h"
#include "web.h"

static const char *TAG = "bot";

bot_cfg_t g_cfg;
ctl_t g_ctl;
app_diag_t g_diag;
static SemaphoreHandle_t mtx;
static volatile int cal_out = -1;
static volatile uint16_t cal_us;

void app_lock(void) { xSemaphoreTake(mtx, portMAX_DELAY); }
void app_unlock(void) { xSemaphoreGive(mtx); }

void app_calibrate(int out, uint16_t us)
{
    cal_us = us;
    cal_out = (us && out >= 0 && out < NUM_OUT) ? out : -1;
}

const char *app_version(void) { return esp_app_get_description()->version; }

static void reboot_cb(void *arg)
{
    hw_motors(0, 0);
    esp_restart();
}

void app_reboot_soon(void)
{
    static esp_timer_handle_t t;
    if (t) return;
    esp_timer_create_args_t a = {.callback = reboot_cb, .name = "reboot"};
    if (esp_timer_create(&a, &t) == ESP_OK) esp_timer_start_once(t, 800 * 1000);
}

// 100 Hz: battery, control rules, motors, outputs, status LED
static void control_task(void *arg)
{
    bool avail[NUM_OUT];
    for (int i = 0; i < NUM_OUT; i++) avail[i] = hw_out_available(i);
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        uint32_t now = (uint32_t)(esp_timer_get_time() / 1000);
        float vb = hw_vbat();
        float ml, mr;
        uint16_t us[NUM_OUT];
        led_state_t led;
        app_lock();
        g_ctl.vbat = vb;
        g_ctl.updating = ota_status()[0] != 0;
        if (g_ctl.updating && g_ctl.armed) ctl_disarm(&g_ctl, "Updating firmware");
        ctl_step(&g_ctl, &g_cfg, now, avail);
        ml = g_ctl.motor[0];
        mr = g_ctl.motor[1];
        memcpy(us, g_ctl.out_us, sizeof(us));
        led = g_ctl.led;
        int co = cal_out;
        if (co >= 0 && !g_ctl.armed) us[co] = cal_us;
        if (vb > 2.0f && (g_diag.vmin < 0 || vb < g_diag.vmin)) g_diag.vmin = vb;
        app_unlock();
        hw_motors(ml, mr);
        hw_outputs(us);
        hw_led(led, now);
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(10));
    }
}

void app_main(void)
{
    mtx = xSemaphoreCreateMutex();
    store_init();
    store_push_reset(esp_reset_reason());
    g_diag.nresets = store_resets(g_diag.resets);
    g_diag.vmin = -1;
    store_load(&g_cfg);
    ESP_LOGI(TAG, "Cardboard Bot %s, robot '%s'", app_version(), g_cfg.name);

    // outputs come up safe (motors coast, ESCs at stop, servos at rest) before Wi-Fi starts
    hw_init(&g_cfg);
    ctl_init(&g_ctl, &g_cfg);
    xTaskCreate(control_task, "ctl", 4096, NULL, 10, NULL);

    net_start(&g_cfg);
    web_start();
    if (g_cfg.captive) dns_start();   // off: phones don't show "Sign in to network"

    // a new image that gets this far without crashing is kept; otherwise the bootloader rolls back
    int64_t t0 = esp_timer_get_time();
    bool marked = false;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(200));
        web_broadcast_status();
        if (!marked && esp_timer_get_time() - t0 > 10 * 1000000LL) {
            esp_ota_mark_app_valid_cancel_rollback();
            marked = true;
        }
    }
}
