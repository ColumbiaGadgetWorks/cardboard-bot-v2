// HTTP + WebSocket control server on port 80
#pragma once

void web_start(void);
void web_broadcast_status(void);   // call ~5 times a second
