#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include "onkar_gfx.inc"
volatile uint32_t sink;
static void gfx_out(int x0, int y0, int w, int h, const uint16_t *pix) { sink = x0 + y0 + w + h + pix[0]; }
static void gfx_out_wait(void) {}
static void gfx_frame_start(void) {}
static uint32_t plat_ms(void) { return sink; }
static void plat_bright(uint8_t v) { sink = v; }
static void plat_display(bool on) { sink = on; }
static bool plat_bt(void) { return sink & 1; }
static uint32_t plat_now_s(void) { return sink; }
static bool plat_time_ok(void) { return 1; }
static void plat_haptic(uint8_t id) { (void)id; }
static int plat_batt(int *mv) { *mv = 0; return -1; }
static void plat_save(void) { sink = 3; }
static bool plat_info(int i, char *k, char *v) { if (i > 3) return false; k[0] = v[0] = 0; return true; }
#include "onkar_ui.inc"
T_UI_CFG cfg;
int main(void) { ui_init(&cfg, 0); for (;;) { ui_frame(sink); ui_touch(sink & 1, sink, sink, sink); ui_crown(sink, sink); ui_button(sink & 2, sink); if (sink == 7) ui_dfu(); } }
void _exit(int c) { for (;;); }
