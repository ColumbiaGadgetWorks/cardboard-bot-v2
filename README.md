# Cardboard Bot v2

Cardboard battlebots for Columbia Gadget Works, built on the Seeed XIAO ESP32-C3.

- Each robot hosts its own Wi-Fi access point. You drive it from a phone browser,
  with an optional Bluetooth gamepad (DS4 and others) through the browser's Gamepad API.
- Firmware is flashed from a browser-based web flasher on GitHub Pages; updates go over the
  robot's own AP.
- The board runs on 2 × 18650 cells, charges them over USB-C with balancing, drives two
  gearmotors, and has four 3-pin outputs for ESCs or servos.

| Folder | Contents |
|---|---|
| [`hardware/`](hardware/) | KiCad 7 main board, rev A: schematic, PCB, JLCPCB fab files and the generator scripts |
| [`firmware/`](firmware/) | ESP-IDF firmware for the XIAO ESP32-C3, including the phone controller page |
| [`site/`](site/) | Web flasher, published to GitHub Pages with every firmware build |

**Flash a robot:** <https://columbiagadgetworks.github.io/cardboard-bot-v2/> (desktop Chrome or Edge, or Firefox 151+).
**Drive it:** join the robot's Wi-Fi (`CGW-<name>`) and open **https://192.168.4.1** on the phone.
