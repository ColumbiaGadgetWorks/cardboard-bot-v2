// Captive-portal DNS: every name resolves to the robot, so typing any address lands on it.
#include <string.h>
#include <sys/socket.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "web.h"

static void dns_task(void *arg)
{
    int s = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons(53), .sin_addr.s_addr = htonl(INADDR_ANY)};
    if (s < 0 || bind(s, (struct sockaddr *)&a, sizeof(a)) < 0) {
        ESP_LOGE("dns", "can't bind port 53");
        vTaskDelete(NULL);
    }
    static uint8_t buf[512];
    for (;;) {
        struct sockaddr_in from;
        socklen_t fl = sizeof(from);
        int n = recvfrom(s, buf, sizeof(buf) - 16, 0, (struct sockaddr *)&from, &fl);
        if (n < 12) continue;
        if ((buf[2] & 0x80) || buf[4] != 0 || buf[5] != 1) continue;   // queries with one question only
        // walk the question name to its type / class
        int p = 12;
        while (p < n && buf[p]) p += buf[p] + 1;
        if (p + 5 > n) continue;
        uint16_t qtype = buf[p + 1] << 8 | buf[p + 2];
        int end = p + 5;
        buf[2] = 0x84 | (buf[2] & 0x01);   // response, authoritative, keep RD
        buf[3] = 0x80;                      // recursion available, no error
        buf[6] = 0;
        buf[7] = qtype == 1 ? 1 : 0;        // one A answer; nothing for AAAA and friends
        buf[8] = buf[9] = buf[10] = buf[11] = 0;
        if (qtype == 1) {
            static const uint8_t ans[] = {0xC0, 0x0C, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4, 192, 168, 4, 1};
            memcpy(buf + end, ans, sizeof(ans));
            end += sizeof(ans);
        }
        sendto(s, buf, end, 0, (struct sockaddr *)&from, fl);
    }
}

void dns_start(void) { xTaskCreate(dns_task, "dns", 3072, NULL, 3, NULL); }
