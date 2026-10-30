// Robot settings. Stored as JSON in the 4 KB "botcfg" flash partition, which the web flasher
// can also write. Missing keys keep their defaults, so old and new settings files both load.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define NUM_OUT 4

enum { DRIVE_TANK = 0, DRIVE_ARCADE = 1, DRIVE_SPLIT = 2 };
enum { OUT_OFF = 0, OUT_ESC = 1, OUT_SERVO = 2 };
// ESC: hold / toggle / variable.  Servo: hold / toggle / position.
enum { OM_HOLD = 0, OM_TOGGLE = 1, OM_ANALOG = 2 };

// Input axes, in the order the phone sends them
enum { AX_LX = 0, AX_LY, AX_RX, AX_RY, AX_LT, AX_RT, AX_NONE = 255 };

// Button bits: 0-16 are the browser's standard gamepad layout, 20-23 the on-screen FIRE 1-4
// buttons, 24 the on-screen slow-mode toggle.
#define BTN_SCREEN_FIRE(i) (20 + (i))
#define BTN_SCREEN_SLOW 24
#define BTN_NONE 255

typedef struct {
    uint8_t type;       // OUT_*
    uint8_t mode;       // OM_*
    uint8_t btn;        // button bit that fires it (BTN_NONE = on-screen only)
    uint8_t axis;       // axis for OM_ANALOG
    uint16_t min_us;    // ESC: stop / servo: 0 degrees
    uint16_t max_us;    // ESC: full / servo: 180 degrees
    uint8_t max_pct;    // ESC throttle limit
    uint16_t spin_ms;   // ESC spin-up ramp, 0 to full
    uint8_t rest_deg;   // servo
    uint8_t fire_deg;   // servo
    uint16_t speed;     // servo slew, degrees per second (0 = as fast as it goes)
} out_cfg_t;

typedef struct {
    uint8_t mode;       // DRIVE_*
    bool inv_l, inv_r, swap, rev_steer;
    uint8_t max_pct;    // top speed
    uint8_t slow_pct;   // top speed in slow mode
    uint8_t slow_btn;   // gamepad button that holds slow mode
    uint8_t turn_pct;   // steering strength
    uint16_t spin_ms;   // extra ramp when spinning in place
    uint8_t expo_pct;
    uint8_t dead_pct;
    uint16_t ramp_ms;   // 0 to full speed
    float vcap;         // motor voltage cap (V)
} drive_cfg_t;

typedef struct {
    uint16_t wpn_cut_ms;   // no packets: weapon outputs to zero
    uint16_t fs_ms;        // no packets: failsafe, drive stops
    uint16_t grace_ms;     // reconnect within this after failsafe: still armed
    uint8_t drops;         // this many failsafes in 60 s: disarm
    float low_wpn;         // volts per cell: weapon lockout
    float low_drv;         // volts per cell: drive stops
    bool lockout;          // low-battery lockouts on (needs battery sensing)
} safe_cfg_t;

// Which XIAO pin does what. Defaults are the main board's wiring (board.h); a prototype or another
// board can move them. Any of GPIO 2-10, 20, 21; the battery input must be an ADC pin (GPIO 2, 3, 4).
typedef struct {
    uint8_t ain1, ain2, bin1, bin2;  // DRV8833 inputs: left motor A, right motor B
    uint8_t out[NUM_OUT];            // outputs 1-4
    uint8_t led;                     // WS2812 data
    uint8_t vbat;                    // battery divider (pack / vdiv)
} pin_cfg_t;

typedef struct {
    char name[24];         // robot name
    char driver[24];       // driver name
    char ap[33];           // AP SSID ("" = CGW-<name>)
    char pw[65];           // AP password ("" = open, else 8+ chars)
    uint8_t ch;            // 0 = auto (quietest of 1/6/11)
    char wifi_ssid[33];    // club Wi-Fi, for pulling updates
    char wifi_pw[65];
    char src[16];          // firmware source: stable / beta / custom
    char src_url[160];     // custom: base URL of the firmware folder
    bool bsense;           // read the battery voltage
    float vdiv;            // battery divider ratio: board 6 (100k / 20k); 4 for a 300k / 100k divider
    uint8_t cells;         // 0 = detect 2S / 3S at power-on
    bool drive_on;         // motor driver fitted
    bool led_on;           // status LED fitted
    bool captive;          // DNS answers every name, so phones show "Sign in to network"
    pin_cfg_t pins;
    drive_cfg_t drive;
    out_cfg_t out[NUM_OUT];
    safe_cfg_t safe;
} bot_cfg_t;

void cfg_defaults(bot_cfg_t *c);
// JSON <-> struct. cfg_from_json only overwrites keys present in the text.
bool cfg_from_json(bot_cfg_t *c, const char *json);
char *cfg_to_json(const bot_cfg_t *c);   // malloc'd, caller frees
void cfg_sanitize(bot_cfg_t *c);
bool cfg_pin_ok(int gpio);
bool cfg_adc_pin_ok(int gpio);
// Which outputs can run: a valid pin not taken by the motors, LED, battery input or an earlier output
void cfg_out_avail(const bot_cfg_t *c, bool avail[NUM_OUT]);

// botcfg partition image: "BCFG", u16 version, u16 length, u32 crc32(json), json, 0xFF padding
#define BOTCFG_SIZE 4096
uint32_t cfg_crc32(const uint8_t *p, uint32_t n);
bool cfg_parse_image(const uint8_t *img, uint32_t n, const char **json, uint32_t *len);
uint32_t cfg_make_image(const char *json, uint8_t *img /* BOTCFG_SIZE */);
