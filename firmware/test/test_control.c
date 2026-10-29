// Host tests for the control logic and the botcfg image format.
//   cc -O1 -Wall -I../main test_control.c ../main/control.c ../main/config.c -lm -o t && ./t
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "config.h"
#include "control.h"

static int fails = 0, checks = 0;
#define CHECK(cond)                                                       \
    do {                                                                  \
        checks++;                                                         \
        if (!(cond)) {                                                    \
            fails++;                                                      \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);        \
        }                                                                 \
    } while (0)
#define NEAR(a, b) (fabsf((a) - (b)) < 0.02f)

static bot_cfg_t cfg;
static ctl_t c;
static bool avail[NUM_OUT] = {true, true, false, true};
static uint32_t now;

static void reset(void)
{
    cfg_defaults(&cfg);
    cfg.drive.ramp_ms = 0;
    cfg.drive.spin_ms = 0;
    cfg.drive.expo_pct = 0;
    cfg.drive.dead_pct = 0;
    cfg.drive.vcap = 8.4f;
    ctl_init(&c, &cfg);
    c.vbat = 8.0f;
    now = 2000;
}

// send the same input every 20 ms for ms milliseconds, stepping the controller every 10 ms
static void run(const ctl_input_t *in, uint32_t ms)
{
    for (uint32_t t = 0; t < ms; t += 10) {
        if (in && t % 20 == 0) ctl_input(&c, in, now);
        ctl_step(&c, &cfg, now, avail);
        now += 10;
    }
}

static void test_drive(void)
{
    reset();
    ctl_input_t in = {0};
    in.ax[AX_LY] = 127;   // split arcade: full forward
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 1) && NEAR(c.motor[1], 1));
    in.ax[AX_LY] = 0;
    in.ax[AX_RX] = 127;   // turn right on the spot, 70 % turn rate
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 0.7f) && NEAR(c.motor[1], -0.7f));
    cfg.drive.mode = DRIVE_TANK;
    memset(&in, 0, sizeof(in));
    in.ax[AX_LY] = 127;
    in.ax[AX_RY] = -64;
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 1) && NEAR(c.motor[1], -0.504f));
    cfg.drive.swap = true;
    cfg.drive.inv_l = true;
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 0.504f) && NEAR(c.motor[1], 1));

    // slow mode button
    reset();
    memset(&in, 0, sizeof(in));
    in.ax[AX_LY] = 127;
    in.btn = 1u << BTN_SCREEN_SLOW;
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 0.5f));

    // deadzone: 8 % stick does nothing
    reset();
    cfg.drive.dead_pct = 10;
    memset(&in, 0, sizeof(in));
    in.ax[AX_LY] = 10;
    run(&in, 100);
    CHECK(c.motor[0] == 0);

    // voltage cap: 6 V on an 8 V pack = 75 % duty
    reset();
    cfg.drive.vcap = 6.0f;
    memset(&in, 0, sizeof(in));
    in.ax[AX_LY] = 127;
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 0.75f));
    c.vbat = 5.0f;   // pack below the cap: full duty
    run(&in, 50);
    CHECK(NEAR(c.motor[0], 1.0f));

    // ramp: 150 ms to full speed
    reset();
    cfg.drive.ramp_ms = 150;
    run(&in, 80);
    CHECK(c.motor[0] > 0.3f && c.motor[0] < 0.7f);
    run(&in, 100);
    CHECK(NEAR(c.motor[0], 1));
}

static void test_failsafe(void)
{
    reset();
    ctl_input_t in = {0};
    in.ax[AX_LY] = 127;
    run(&in, 100);
    CHECK(ctl_arm(&c, &cfg, now));
    CHECK(c.armed);
    // weapon on RB: held while arming doesn't fire until released
    in.btn = 1u << 5;
    run(&in, 100);
    CHECK(c.out_us[0] == 1000);
    in.btn = 0;
    run(&in, 40);
    in.btn = 1u << 5;
    run(&in, 1100);   // 1 s spin-up
    CHECK(c.out_us[0] == 2000);
    CHECK(c.led == LED_ARMED_RUN);

    // link drops: 300 ms weapon to zero, still armed, drive still running
    run(NULL, 350);
    CHECK(c.out_us[0] == 1000);
    CHECK(c.armed && !c.failsafe && c.motor[0] > 0.9f);
    // 1 s: failsafe, drive stops
    run(NULL, 700);
    CHECK(c.failsafe && c.motor[0] == 0 && c.led == LED_FAILSAFE);
    CHECK(c.armed);
    // back within the grace time: still armed, weapon waits for release
    run(&in, 100);
    CHECK(!c.failsafe && c.armed && c.out_us[0] == 1000);
    in.btn = 0;
    run(&in, 40);
    in.btn = 1u << 5;
    run(&in, 200);
    CHECK(c.out_us[0] > 1000);

    // second drop, past the grace time: disarmed
    run(NULL, 2200);
    CHECK(!c.armed);
    CHECK(strstr(c.reason, "Link lost") != NULL);
    run(&in, 100);
    CHECK(!c.armed && c.out_us[0] == 1000);
}

static void test_drops(void)
{
    reset();
    ctl_input_t in = {0};
    run(&in, 100);
    CHECK(ctl_arm(&c, &cfg, now));
    for (int i = 0; i < 2; i++) {
        run(NULL, 1100);   // drop, then come back within grace
        run(&in, 200);
        CHECK(c.armed);
    }
    run(NULL, 1100);   // third drop in 60 s
    CHECK(!c.armed && strstr(c.reason, "too often"));
    // can't arm without a link
    CHECK(!ctl_arm(&c, &cfg, now));
}

static void test_outputs(void)
{
    reset();
    cfg.out[0].mode = OM_TOGGLE;
    cfg.out[0].spin_ms = 0;
    cfg.out[3].type = OUT_ESC;   // a second ESC on IO21
    cfg.out[3].btn = 5;
    cfg.out[3].spin_ms = 0;
    ctl_input_t in = {0};
    run(&in, 100);
    ctl_arm(&c, &cfg, now);
    run(&in, 40);
    in.btn = 1u << 5;
    run(&in, 40);
    CHECK(c.out_us[0] == 2000);
    CHECK(c.out_us[3] == 1000);   // second ESC waits 300 ms
    run(&in, 300);
    CHECK(c.out_us[3] == 2000);
    in.btn = 0;
    run(&in, 40);
    CHECK(c.out_us[0] == 2000 && c.out_us[3] == 1000);   // OUT1 toggled on, OUT4 holds only while pressed
    in.btn = 1u << 5;   // second press: OUT1 toggles off, OUT4 runs while held
    run(&in, 40);
    CHECK(c.out_us[0] == 1000);
    CHECK(c.out_us[3] == 2000);
    in.btn = 0;
    run(&in, 40);
    CHECK(c.out_us[3] == 1000);

    // servo on LB: 500..2500 us, rest 0, fire 90
    in.btn = 1u << 4;
    run(&in, 40);
    CHECK(c.out_us[1] == 1500);
    ctl_disarm(&c, "test");
    run(&in, 40);
    CHECK(c.out_us[1] == 500);
    // IO3 unavailable (battery sense) stays low
    CHECK(c.out_us[2] == 0);
}

static void test_battery(void)
{
    reset();
    ctl_input_t in = {0};
    in.ax[AX_LY] = 127;
    run(&in, 100);
    ctl_arm(&c, &cfg, now);
    c.vbat = 6.3f;   // below the weapon cut-off
    run(&in, 1000);
    CHECK(c.armed);   // needs 2 s
    run(&in, 1100);
    CHECK(!c.armed && c.weapon_lock && c.motor[0] > 0);
    CHECK(!ctl_arm(&c, &cfg, now));
    c.vbat = 5.9f;
    run(&in, 2100);
    CHECK(c.drive_lock && c.motor[0] == 0 && c.led == LED_LOWBATT);
    c.vbat = 1.0f;   // no pack (running from USB): no lockouts
    run(&in, 50);
    CHECK(!c.drive_lock && !c.weapon_lock);
}

static void test_image(void)
{
    CHECK(cfg_crc32((const uint8_t *)"123456789", 9) == 0xCBF43926u);
    static uint8_t img[BOTCFG_SIZE];
    const char *j = "{\"name\":\"Tank\"}";
    CHECK(cfg_make_image(j, img) == 12 + strlen(j));
    const char *out;
    uint32_t len;
    CHECK(cfg_parse_image(img, BOTCFG_SIZE, &out, &len) && len == strlen(j) && !memcmp(out, j, len));
    img[14] ^= 1;
    CHECK(!cfg_parse_image(img, BOTCFG_SIZE, &out, &len));
    memset(img, 0xFF, sizeof(img));
    CHECK(!cfg_parse_image(img, BOTCFG_SIZE, &out, &len));
}

int main(void)
{
    test_drive();
    test_failsafe();
    test_drops();
    test_outputs();
    test_battery();
    test_image();
    printf("%d checks, %d failed\n", checks, fails);
    return fails != 0;
}
