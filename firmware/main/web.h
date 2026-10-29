// HTTPS + secure WebSocket control server, plain-HTTP captive landing page, captive DNS
#pragma once

void web_start(void);
void web_broadcast_status(void);   // call ~5 times a second
void dns_start(void);
