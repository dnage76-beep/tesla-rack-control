/*
 * tesla_rc_bridge.ino  --  Arduino Nano firmware (SLT3 / SR315 variant)
 *
 * Reads 3 PWM channels from a Spektrum SR315 surface receiver bound to
 * a Spektrum SLT3 wheel/trigger transmitter, frames them with COBS +
 * CRC8, and sends them to the laptop at 115200 baud over USB CDC.
 *
 * Pin map (Arduino Nano, ATmega328P):
 *   D2  (PCINT18, PD2)  SR315 ch1 STR (wheel)    -> STEERING
 *   D3  (PCINT19, PD3)  SR315 ch2 THR (trigger)  -> P button (gesture)
 *   D4  (PCINT20, PD4)  SR315 ch3 AUX1 (rocker)  -> R/N/D selector
 *
 * Wiring:
 *   SR315 servo lead negative (black) -> Nano GND
 *   SR315 servo lead positive (red)   -> Nano 5V (powers Rx; current is fine)
 *   SR315 servo lead signal (white)   -> Nano D2 / D3 / D4
 *   Nano USB                          -> laptop
 *
 * Standard Spektrum surface PWM: 1000-2000 us pulse, 5.5-22 ms frame
 * rate. SR315 holds last value on signal loss (SmartSafe), same as
 * any other Spektrum surface receiver. Signal-loss detection happens
 * on the Python side (NO SERIAL pill + TX LOST stick-frozen heuristic).
 *
 * Output framing (COBS-encoded, terminated by 0x00):
 *   [seq:u8][ch_steer:u16 LE][ch_p:u16 LE][ch_rnd:u16 LE][flags:u8][crc8:u8]
 *   Total raw payload = 9 bytes. COBS overhead at most +2.
 *
 * CRC8: polynomial 0x07 (CRC-8/ITU), init 0x00, no reflection, no xorout.
 *   Standard "lookup-table free" left-shift implementation.
 *
 * Send rate: 100 Hz. Latency budget: 10 ms RC frame + 10 ms USB transit.
 *
 * Build target: Arduino Nano, ATmega328P (Old Bootloader if needed).
 *
 * NOTE: this firmware is byte-identical to the AR6200 variant on
 * dev/v5-rc except for the channel-source comments above. The Nano
 * doesn't know which receiver feeds it; it just reads PWM widths.
 */

#include <avr/interrupt.h>

// ---------- Pin assignments ----------

// All three pins are on PORTD, PCINT2 group (pins 0..7).
constexpr uint8_t PIN_STEER = 2;  // PD2 / PCINT18
constexpr uint8_t PIN_P     = 3;  // PD3 / PCINT19
constexpr uint8_t PIN_RND   = 4;  // PD4 / PCINT20

constexpr uint8_t MASK_STEER = (1 << PIN_STEER);
constexpr uint8_t MASK_P     = (1 << PIN_P);
constexpr uint8_t MASK_RND   = (1 << PIN_RND);

// ---------- PWM capture state (volatile -- ISR shared) ----------

struct PwmChannel {
    volatile uint32_t rise_us;
    volatile uint16_t width_us;
    volatile uint8_t  fresh;    // bumped on each falling edge
};

static volatile PwmChannel ch_steer = {0, 1500, 0};
static volatile PwmChannel ch_p     = {0, 1500, 0};
static volatile PwmChannel ch_rnd   = {0, 1500, 0};

static volatile uint8_t prev_portd = 0;

ISR(PCINT2_vect) {
    const uint8_t portd = PIND;
    const uint8_t changed = portd ^ prev_portd;
    prev_portd = portd;

    const uint32_t now = micros();

    // STEER
    if (changed & MASK_STEER) {
        if (portd & MASK_STEER) {
            ch_steer.rise_us = now;
        } else {
            uint32_t w = now - ch_steer.rise_us;
            if (w >= 800 && w <= 2200) {
                ch_steer.width_us = (uint16_t)w;
                ch_steer.fresh++;
            }
        }
    }
    // P
    if (changed & MASK_P) {
        if (portd & MASK_P) {
            ch_p.rise_us = now;
        } else {
            uint32_t w = now - ch_p.rise_us;
            if (w >= 800 && w <= 2200) {
                ch_p.width_us = (uint16_t)w;
                ch_p.fresh++;
            }
        }
    }
    // RND
    if (changed & MASK_RND) {
        if (portd & MASK_RND) {
            ch_rnd.rise_us = now;
        } else {
            uint32_t w = now - ch_rnd.rise_us;
            if (w >= 800 && w <= 2200) {
                ch_rnd.width_us = (uint16_t)w;
                ch_rnd.fresh++;
            }
        }
    }
}

// ---------- CRC-8 / ITU (poly 0x07, init 0x00) ----------

static uint8_t crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++) {
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

// ---------- COBS encode (in-place safe; writes to dst, returns length) ----------
// Reference: Cheshire & Baker, "Consistent Overhead Byte Stuffing", 1999.
// Encoded length is at most src_len + ceil(src_len / 254) + 1, then +1 for the
// trailing 0x00 terminator.

static uint8_t cobs_encode(const uint8_t *src, uint8_t src_len, uint8_t *dst) {
    uint8_t  code_idx = 0;
    uint8_t  dst_idx  = 1;
    uint8_t  code     = 1;

    for (uint8_t i = 0; i < src_len; i++) {
        if (src[i] == 0) {
            dst[code_idx] = code;
            code_idx = dst_idx++;
            code = 1;
        } else {
            dst[dst_idx++] = src[i];
            if (++code == 0xFF) {
                dst[code_idx] = code;
                code_idx = dst_idx++;
                code = 1;
            }
        }
    }
    dst[code_idx] = code;
    dst[dst_idx++] = 0x00;  // frame terminator
    return dst_idx;
}

// ---------- Frame ----------

static uint8_t seq = 0;

static void send_frame() {
    // Snapshot under cli/sei to avoid torn 16-bit reads.
    noInterrupts();
    const uint16_t w_steer = ch_steer.width_us;
    const uint16_t w_p     = ch_p.width_us;
    const uint16_t w_rnd   = ch_rnd.width_us;
    const uint8_t  f_steer = ch_steer.fresh;
    const uint8_t  f_p     = ch_p.fresh;
    const uint8_t  f_rnd   = ch_rnd.fresh;
    interrupts();

    uint8_t flags = 0;
    if (f_steer) flags |= 0x01;
    if (f_p)     flags |= 0x02;
    if (f_rnd)   flags |= 0x04;

    uint8_t payload[9];
    payload[0] = seq++;
    payload[1] = (uint8_t)(w_steer & 0xFF);
    payload[2] = (uint8_t)(w_steer >> 8);
    payload[3] = (uint8_t)(w_p & 0xFF);
    payload[4] = (uint8_t)(w_p >> 8);
    payload[5] = (uint8_t)(w_rnd & 0xFF);
    payload[6] = (uint8_t)(w_rnd >> 8);
    payload[7] = flags;
    payload[8] = crc8(payload, 8);

    uint8_t encoded[12];
    uint8_t n = cobs_encode(payload, 9, encoded);
    Serial.write(encoded, n);
}

// ---------- Setup / loop ----------

void setup() {
    pinMode(PIN_STEER, INPUT);
    pinMode(PIN_P,     INPUT);
    pinMode(PIN_RND,   INPUT);

    Serial.begin(115200);

    // Enable pin-change interrupts on PORTD pins 2, 3, 4.
    PCMSK2 = MASK_STEER | MASK_P | MASK_RND;
    PCICR |= (1 << PCIE2);
    prev_portd = PIND;
}

void loop() {
    static uint32_t next_tx_ms = 0;
    const uint32_t now_ms = millis();
    if ((int32_t)(now_ms - next_tx_ms) >= 0) {
        next_tx_ms = now_ms + 10;  // 100 Hz
        send_frame();
    }
}
