#include "hw.h"

#include <math.h>
#include <string.h>

#include "board.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/rmt_tx.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_rom_gpio.h"
#include "soc/gpio_sig_map.h"

static const char *TAG = "hw";

// ---- motors: one LEDC channel each, slow decay ----
// Forward: IN1 high, IN2 = inverted PWM (low for the "on" part of each period, brake for the rest).
// Reverse: the other way round. Stop: both low (coast).
#define MOTOR_FREQ 20000
#define MOTOR_RES LEDC_TIMER_10_BIT
#define MOTOR_MAX ((1 << 10) - 1)
static const int motor_pins[2][2] = {{PIN_AIN1, PIN_AIN2}, {PIN_BIN1, PIN_BIN2}};
static int motor_dir[2] = {2, 2};   // -1, 0, 1; 2 = not set yet

static void pin_static(int pin, int level)
{
    esp_rom_gpio_connect_out_signal(pin, SIG_GPIO_OUT_IDX, false, false);
    gpio_set_level(pin, level);
}

static void pin_pwm_inverted(int pin, int channel)
{
    esp_rom_gpio_connect_out_signal(pin, LEDC_LS_SIG_OUT0_IDX + channel, true, false);
}

void hw_motors(float left, float right)
{
    float v[2] = {left, right};
    for (int m = 0; m < 2; m++) {
        float a = fabsf(v[m]);
        int dir = a < 0.01f ? 0 : (v[m] > 0 ? 1 : -1);
        if (dir != motor_dir[m]) {
            int in1 = motor_pins[m][0], in2 = motor_pins[m][1];
            if (dir == 0) {
                pin_static(in1, 0);
                pin_static(in2, 0);
            } else if (dir > 0) {
                pin_static(in1, 1);
                pin_pwm_inverted(in2, m);
            } else {
                pin_static(in2, 1);
                pin_pwm_inverted(in1, m);
            }
            motor_dir[m] = dir;
        }
        uint32_t duty = dir == 0 ? 0 : (uint32_t)(fminf(a, 1.0f) * MOTOR_MAX + 0.5f);
        ledc_set_duty(LEDC_LOW_SPEED_MODE, m, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, m);
    }
}

// ---- servo / ESC outputs: 50 Hz on LEDC channels 2-5 ----
#define OUT_FREQ 50
#define OUT_RES LEDC_TIMER_14_BIT
static const int out_pins[NUM_OUT] = {PIN_OUT1, PIN_OUT2, PIN_IO3, PIN_IO21};
static bool out_avail[NUM_OUT];

bool hw_out_available(int i) { return i >= 0 && i < NUM_OUT && out_avail[i]; }

void hw_outputs(const uint16_t us[NUM_OUT])
{
    for (int i = 0; i < NUM_OUT; i++) {
        if (!out_avail[i]) continue;
        uint32_t duty = (uint32_t)us[i] * (1 << 14) / (1000000 / OUT_FREQ);
        ledc_set_duty(LEDC_LOW_SPEED_MODE, 2 + i, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, 2 + i);
    }
}

// ---- battery: VSYS / 4 on GPIO3 ----
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t cali;
static bool vbat_on;
static float vbat_f = -1;

float hw_vbat(void)
{
    if (!vbat_on) return -1;
    int sum = 0, n = 0;
    for (int i = 0; i < 8; i++) {
        int raw, mv;
        if (adc_oneshot_read(adc, ADC_CHANNEL_3, &raw) != ESP_OK) continue;
        if (cali) {
            if (adc_cali_raw_to_voltage(cali, raw, &mv) != ESP_OK) continue;
        } else {
            mv = raw * 2500 / 4095;
        }
        sum += mv;
        n++;
    }
    if (!n) return vbat_f;
    float v = sum / (float)n / 1000.0f * VBAT_DIVIDER;
    // light filter; jump straight to the new value when it moves a lot (pack connected / removed)
    vbat_f = (vbat_f < 0 || fabsf(v - vbat_f) > 1.0f) ? v : vbat_f + 0.15f * (v - vbat_f);
    return vbat_f;
}

// ---- WS2812B status LED on RMT ----
static rmt_channel_handle_t led_ch;
static rmt_encoder_handle_t led_enc;

static void led_send(uint8_t r, uint8_t g, uint8_t b)
{
    if (!led_ch) return;
    static uint8_t grb[3];
    rmt_tx_wait_all_done(led_ch, 20);
    grb[0] = g;
    grb[1] = r;
    grb[2] = b;
    rmt_transmit_config_t tc = {.loop_count = 0};
    rmt_transmit(led_ch, led_enc, grb, sizeof(grb), &tc);
}

void hw_led(led_state_t s, uint32_t now)
{
    static uint32_t last_rgb = 0xFFFFFFFF;
    const uint8_t B = 60;   // brightness: bright enough in daylight, not blinding
    uint8_t r = 0, g = 0, b = 0;
    uint32_t ph = now % 1000;
    float pulse = 0.5f - 0.5f * cosf(2 * (float)M_PI * (now % 2000) / 2000.0f);
    switch (s) {
    case LED_BOOT:
    case LED_UPDATE:
        if (ph < 250 || (ph >= 500 && ph < 750)) r = g = b = B;
        break;
    case LED_WAITING:
        b = (uint8_t)(8 + pulse * (B - 8));
        break;
    case LED_CONNECTED:
        g = B;
        break;
    case LED_LOWBATT:
        if (ph < 500) r = b = B;
        break;
    case LED_ARMED:
        r = B;
        break;
    case LED_ARMED_RUN:
        if ((now / 80) % 2) r = B;
        break;
    case LED_FAILSAFE:
        if ((now / 200) % 2) {
            r = B;
            g = B / 3;
        }
        break;
    }
    uint32_t rgb = r << 16 | g << 8 | b;
    if (rgb != last_rgb) {
        led_send(r, g, b);
        last_rgb = rgb;
    }
}

void hw_init(const bot_cfg_t *cfg)
{
    // motors: all four inputs low first (coast)
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << PIN_AIN1) | (1ULL << PIN_AIN2) | (1ULL << PIN_BIN1) | (1ULL << PIN_BIN2),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    ledc_timer_config_t mt = {
        .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = MOTOR_RES, .timer_num = LEDC_TIMER_0,
        .freq_hz = MOTOR_FREQ, .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&mt));
    for (int m = 0; m < 2; m++) {
        // the channel starts on IN1; hw_motors() re-routes the pins through the GPIO matrix
        ledc_channel_config_t ch = {
            .gpio_num = motor_pins[m][0], .speed_mode = LEDC_LOW_SPEED_MODE, .channel = m,
            .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0,
        };
        ESP_ERROR_CHECK(ledc_channel_config(&ch));
    }
    hw_motors(0, 0);

    // outputs
    vbat_on = cfg->bsense;
    for (int i = 0; i < NUM_OUT; i++) out_avail[i] = !(i == 2 && vbat_on);
    ledc_timer_config_t ot = {
        .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = OUT_RES, .timer_num = LEDC_TIMER_1,
        .freq_hz = OUT_FREQ, .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&ot));
    for (int i = 0; i < NUM_OUT; i++) {
        if (!out_avail[i]) continue;
        ledc_channel_config_t ch = {
            .gpio_num = out_pins[i], .speed_mode = LEDC_LOW_SPEED_MODE, .channel = 2 + i,
            .timer_sel = LEDC_TIMER_1, .duty = 0, .hpoint = 0,
        };
        ESP_ERROR_CHECK(ledc_channel_config(&ch));
    }

    // battery ADC
    if (vbat_on) {
        adc_oneshot_unit_init_cfg_t uc = {.unit_id = ADC_UNIT_1};
        ESP_ERROR_CHECK(adc_oneshot_new_unit(&uc, &adc));
        adc_oneshot_chan_cfg_t cc = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12};
        ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_3, &cc));
        adc_cali_curve_fitting_config_t cal = {
            .unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_3, .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12,
        };
        if (adc_cali_create_scheme_curve_fitting(&cal, &cali) != ESP_OK) {
            ESP_LOGW(TAG, "no ADC calibration in eFuse, battery reading is approximate");
            cali = NULL;
        }
    }

    // status LED: 10 MHz ticks, WS2812 bit timing 0.3 / 0.9 us
    rmt_tx_channel_config_t tx = {
        .gpio_num = PIN_LED, .clk_src = RMT_CLK_SRC_DEFAULT, .resolution_hz = 10000000,
        .mem_block_symbols = 48, .trans_queue_depth = 2,
    };
    if (rmt_new_tx_channel(&tx, &led_ch) == ESP_OK) {
        rmt_bytes_encoder_config_t ec = {
            .bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},
            .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
            .flags.msb_first = 1,
        };
        rmt_new_bytes_encoder(&ec, &led_enc);
        rmt_enable(led_ch);
    } else {
        ESP_LOGE(TAG, "LED RMT channel failed");
        led_ch = NULL;
    }
}
