// Cardboard Bot v2 main board, rev A (hardware/README.md has the full pin map)
#pragma once

// DRV8833: AIN1/AIN2 = left motor (J3), BIN1/BIN2 = right motor (J4). nSLEEP is tied high.
#define PIN_AIN1 4    // D2
#define PIN_AIN2 5    // D3
#define PIN_BIN1 6    // D4
#define PIN_BIN2 7    // D5

// 3-pin outputs (GND / V+ / SIG): OUT1, OUT2, IO3, IO21
#define PIN_OUT1 10   // D10, 10k pull-down
#define PIN_OUT2 20   // D7, 10k pull-down
#define PIN_IO3 3     // D1, also battery sense through JP1
#define PIN_IO21 21   // D6, UART0 TX in the ROM bootloader

#define PIN_VBAT 3    // ADC1 channel 3: VSYS / 4 (300k / 100k)
#define VBAT_DIVIDER 4.0f

#define PIN_LED 9     // D9, WS2812B data (also the BOOT button)
#define PIN_SDA 2     // D0, I2C header J2
#define PIN_SCL 8     // D8
