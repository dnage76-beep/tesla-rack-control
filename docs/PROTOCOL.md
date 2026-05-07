# CAN Protocol Reference

All bit positions verified against `commaai/opendbc/tesla_can.dbc`.
All checksums verified against `gregjhogan/tesla-pre-ap-epas-patch`
and tested against the patched 2013 Tesla Model S EPAS rack on
Jordan's bench.

Tesla chassis CAN: 500 kbps, 11-bit identifiers, big-endian
(Motorola) bit ordering for multi-byte signals.

---

## TX from `tesla_control.py`

### `0x488` DAS_steeringControl  --  4 bytes  --  50 Hz (always)

| Byte | Bits  | Field                          | Encoding                                    |
|------|-------|--------------------------------|---------------------------------------------|
| b0   | 6..0  | angle_raw high                 | top 7 bits of 15-bit angle (bit 7 reserved) |
| b1   | 7..0  | angle_raw low                  | bottom 8 bits of 15-bit angle               |
| b2   | 7..6  | controlType                    | 0=NONE, 1=ANGLE_CONTROL                     |
| b2   | 3..0  | counter                        | 0..15, increments each frame                |
| b3   | 7..0  | checksum                       | `(0x88 + 0x04 + b0 + b1 + b2) & 0xFF`       |

```
angle_raw = round((angle_deg + 1638.35) * 10)
clamped to 0..0x7FFF (15-bit)
```

The MSB of byte 0 is `DAS_steeringHapticRequest`. We always leave it
zero.

### `0x214` EPB_epasControl  --  3 bytes  --  10 Hz (always)

| Byte | Bits  | Field                          | Encoding                                    |
|------|-------|--------------------------------|---------------------------------------------|
| b0   | 7..5  | EPB_epasEACAllow               | 0=DISABLE, 1=ENABLE (ignored after patch)   |
| b1   | 3..0  | EPB_epasControlCounter         | 0..15, increments each frame                |
| b2   | 7..0  | EPB_epasControlChecksum        | `(0x14 + 0x02 + b0 + b1) & 0xFF`            |

Per gregjhogan's README, the patched rack ignores the EAC_Allow
*content* but requires the message to be present at rate with valid
checksum and counter. We send `EAC_Allow = 1` for cleanliness.

### `0x101` GTW_epasControl  --  3 bytes  --  20 Hz (only if `SYNTHESIZE_GTW = True`)

| Byte | Bits  | Field                          | Encoding                                    |
|------|-------|--------------------------------|---------------------------------------------|
| b0   | 7     | GTW_epasEmergencyOn            | 0=NORMAL                                    |
| b0   | 5..3  | GTW_epasPowerMode              | 1=DRIVE_ON                                  |
| b0   | 2..0  | GTW_epasTuneRequest            | 2=DM_STANDARD                               |
| b1   | 7..6  | GTW_epasControlType            | 1=WITH_ANGLE (when engaged), 0 otherwise    |
| b1   | 4     | GTW_epasLDWEnabled             | 1 when engaged, 0 otherwise                 |
| b1   | 3..0  | GTW_epasControlCounter         | 0..15, increments each frame                |
| b2   | 7..0  | GTW_epasControlChecksum        | `(0x01 + 0x01 + b0 + b1) & 0xFF`            |

Patch ignores controlType / LDWEnabled content. When the real Tesla
GTW is on the bus (in-car default), set `SYNTHESIZE_GTW = False` to
avoid arbitration contention -- harmless after patch but adds bus
noise.

### `0x155` ESP_B fake speed  --  8 bytes  --  200 Hz (only when 30 MPH MODE on)

| Byte | Bits  | Field                          | Encoding                                    |
|------|-------|--------------------------------|---------------------------------------------|
| 0..2 |       | (zeroed -- counter, other)     | rack does not check these on patched fork  |
| 3    | 7..0  | ESP_vehicleSpeed low           | bits 24..31 little-endian                   |
| 4    | 4..0  | ESP_vehicleSpeed high          | bits 32..36 little-endian (5 bits)          |
| 5..7 |       | (zeroed)                       |                                             |

```
raw_13bit = round((speed_kph + 40.0) / 0.04)
masked to 0x1FFF
```

Not OEM-accurate. Sufficient to clear EAC_ERROR_MIN_SPEED.

### Real Tesla messages we share IDs with

These exist on the bus naturally; we either don't send (0x370) or
send only when the real source is absent:

| ID    | Real source                      | Our role                          |
|-------|----------------------------------|-----------------------------------|
| 0x101 | Tesla GTW @ 10 Hz                | Off by default; bench-only        |
| 0x155 | Tesla ESP @ 50 Hz                | 200 Hz when 30 MPH MODE on        |
| 0x214 | (nothing on pre-AP)              | We are the only source            |
| 0x370 | Tesla EPAS @ ~100 Hz             | Listen only                       |

---

## RX in `tesla_control.py`

### `0x118` DI_torque2  --  6 bytes  --  ~100 Hz from drive inverter (v4.2+)

| Field                    | Position             | Encoding                                                     |
|--------------------------|----------------------|--------------------------------------------------------------|
| `DI_gear`                | byte 1, bits 6..4    | 0=INVALID, 1=P, 2=R, 3=N, 4=D, 7=SNA                         |
| `DI_vehicleSpeed`        | byte 2 + byte 3 lo4  | 12-bit LE, factor 0.05, offset -25, units MPH                |
| `DI_gearRequest`         | byte 3, bits 6..4    | same enum as `DI_gear`                                       |

```python
gear     = (data[1] >> 4) & 0x07
gear_req = (data[3] >> 4) & 0x07
speed_raw = data[2] | ((data[3] & 0x0F) << 8)
speed_mph = speed_raw * 0.05 - 25.0
```

Used by v4.2's park-to-engage safety gate. The gate is bypassed
automatically when `0x118` has never been received (bench mode
without a real DI module on the bus).

### `0x370` EPAS_sysStatus  --  8 bytes  --  ~100 Hz from rack

| Field                | Position             | Encoding                                                   |
|----------------------|----------------------|------------------------------------------------------------|
| `eacStatus`          | byte 6, bits 7..5    | 0=INHIBITED, 1=AVAILABLE, 2=ACTIVE, 3=FAULT, 4=SNA         |
| `eacErrorCode`       | byte 2, bits 7..4    | see EAC error table below                                  |
| `EPAS_internalSAS`   | byte 4 bit 5..byte 5 | big-endian 14-bit, factor 0.1, offset -819.2, units deg    |

```python
# Decode reference from tesla_control.py
eac_status = (data[6] >> 5) & 0x07
eac_err    = (data[2] >> 4) & 0x0F
raw_14bit  = ((data[4] & 0x3F) << 8) | data[5]
angle_deg  = raw_14bit * 0.1 - 819.2
```

### EAC error codes (from `tesla_can.dbc`)

| Code | Name                  | What the rack is complaining about              |
|------|-----------------------|--------------------------------------------------|
| 0    | NONE                  | All clear                                        |
| 1    | MIN_SPEED             | Vehicle below speed gate, or 0x155 absent        |
| 2    | MAX_SPEED             | Vehicle exceeds rack's at-speed envelope cap     |
| 3    | HANDS_ON              | Driver torque sensor non-zero                    |
| 4    | OUT_OF_RANGE          | A required keepalive missing or off-rate         |
| 5    | OVER_TORQUE           | Driver torque exceeded threshold                 |
| 6    | HIGH_ANGLE_REQ        | Commanded angle above standstill ceiling (~60)   |
| 7    | HIGH_ANGLE_RATE_REQ   | Commanded rate too high for current envelope     |
| 8    | HIGH_TORQUE_REQ       | (legacy AP signal)                               |
| 9    | BLEND_REQ             | (legacy AP signal)                               |
| 10   | TIMEOUT               | Required input stopped arriving                  |
| 11   | ECU_FAULT             | Internal rack fault                              |
| 12   | BUS_FAULT             | CAN bus errors                                   |
| 13   | INVALID_REQ           | Our 0x488 malformed                              |
| 14   | EPB_INHIBIT           | EPB module inhibit, or 0x214 missing/malformed   |
| 15   | SNA                   | Signal Not Available                             |

---

## Sign convention

Verified by Jordan in-car 2026-05-03: **positive commanded angle =
wheel turns RIGHT.**

If you see the wheel go opposite the commanded direction, your sign
convention got flipped somewhere upstream. Easiest sanity check:
type +5 in the SET box, observe direction, multiply by -1 in your
caller if needed. The rack's internal sign convention does not
change.

---

## Standstill envelope

Without `0x155` reporting motion (or with 30 MPH MODE OFF), the
patched rack enforces:

- Angle ceiling: ~ +/- 60 degrees. Beyond -> `HIGH_ANGLE_REQ`.
- Rate ceiling: ~ 250 deg/s. Beyond -> `HIGH_ANGLE_RATE_REQ`.
- Modest torque output (enough to spin free wheels on jacks; not
  enough to overcome ground load).

With 30 MPH MODE ON (`0x155` reports 30 km/h at 200 Hz):

- Angle ceiling: full mechanical travel (~ +/- 540 degrees, but
  v4.1 software clamps at +/- 180).
- Rate ceiling: higher; v4.1 caps at 150 deg/s.
- Higher torque output.

---

## Sources

- `commaai/opendbc` `tesla_can.dbc` -- all field encodings and the
  `EAC_*` enum
- `gregjhogan/tesla-pre-ap-epas-patch` README -- the exact patched
  bytes and the `0x214` keepalive requirement
- `BogGyver/panda` `safety_tesla.h` on `tesla_unity_dev` -- the
  reference panda firmware that BogGyver's openpilot ships, used to
  cross-check our checksum and counter logic
