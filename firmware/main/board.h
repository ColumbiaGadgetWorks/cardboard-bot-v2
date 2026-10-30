// Cardboard Bot v2 main board, rev B (hardware/README.md has the full pin map).
// These are the firmware's default pins; the settings can move any of them.
#pragma once

// Two DRV8870 drivers: AIN1/AIN2 = left motor, BIN1/BIN2 = right motor. 10k pull-downs on the board.
#define PIN_AIN1 4    // D2
#define PIN_AIN2 5    // D3
#define PIN_BIN1 6    // D4
#define PIN_BIN2 7    // D5

// 3-pin outputs (GND / V+ / SIG), 10k pull-downs: OUT1, OUT2, OUT3. Output 4 has no header on the board.
#define PIN_OUT1 10   // D10
#define PIN_OUT2 20   // D7
#define PIN_OUT3 21   // D6, UART0 TX: the ROM bootloader prints on it for a moment at power-up
#define PIN_OUT4 2    // D0 (shared with the I2C header's SDA)

#define PIN_VBAT 3    // D1, ADC1 channel 3: pack / 6 (100k / 20k), so 3S (12.6 V) reads 2.1 V
#define VBAT_DIVIDER 6.0f

#define PIN_LED 9     // D9, WS2812B data (also the BOOT button)
#define PIN_SDA 2     // D0
#define PIN_SCL 8     // D8
