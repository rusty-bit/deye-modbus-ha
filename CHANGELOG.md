# Changelog (personal fork)

## 0.1.7
- Change: "Battery Shutdown SOC" and "Battery Low SOC" are now named
  "Battery Shutdown SOC (cutoff)" (register 115) and "Battery Low SOC (warning)"
  (117), matching the protocol. Entity IDs are unchanged.
  Neither is the discharge floor while Time of Use is on: the inverter then stops
  at the active slot's TOU SOC (166-171). Confirmed on a live inverter, where 117
  held the requested 20 % while all six TOU slots held 30 % and discharge stopped
  at 30 %.

## 0.1.6
- Cross-checked every control against the Deye Modbus RTU protocol (V117). That document
  is the single-phase edition; the three-phase settings block sits **102 registers lower**
  (doc 206 "ZeroExport power" = 104 here). Offset verified on 26 known registers.
- Confirmed correct: zero export power (104), work mode (142), max sell power (143),
  solar sell (145), time of use (146), TOU blocks (148-177), grid voltage/frequency
  protection (185-188), peak-shaving power (190/191), lithium/BMS type (223).
- Changed: register 178 holds 2-bit fields (10 = disable, 11 = enable), so each switch
  writes the whole pair: generator peak-shaving bits 2-3, grid peak-shaving 4-5, on-grid
  always on 6-7, DRM 12-13. Verified by reading this inverter: 178 = 0x2ABA, a valid code
  in every pair. (An earlier draft read them as single bits 4/8/12/15, which would have
  written the neighbouring external-relay and grounding-fault fields instead.)
- New: Activate Battery (112, inverted logic), Generator Force On (132), Generator minimum
  solar power (139), ARC fault detection (181), generator connected to grid input (189),
  SmartLoad open delay (192), DRM (178 bits 12-13), on-grid always on (178 bits 6-7).
- New diagnostic sensors (read-only, disabled by default) for registers whose mapping is
  still unproven: 140, 178, 209, 224, 228, 341.
- Confirmed by a read-only probe of this inverter: 336 holds parallel / master-slave /
  Modbus SN (0x0400 = parallel off, slave, SN 1) and 347 the CT ratio (2000), so the
  guesses at 225 and 315 are dropped. 345 reads 0 while Deye Cloud shows "Eastron", so
  Meter Select stays unconfirmed.

## 0.1.5
- Entity ranges taken from the inverter's own "Export All Configurations" (SN 2512153227):
  max solar power 400-19200 W, max sell power 0-24000 W, zero export power 0-500 W,
  battery charge/discharge and grid charge current 0-240 A, battery capacity 0-20000 Ah,
  batt low 10-100 %, batt restart 20-100 %, lithium mode 0-20, grid reconnection 1-900 s,
  grid peak-shaving 1000-65000 W, generator peak-shaving 500-16000 W, grid voltage 80-300 V.
- Confirms the registers are unscaled (1 W per step) on this model.
- New: Grid Level select (138).

## 0.1.4
- New: **Zero Export Power** (reg 104), **Energy Pattern** (141) and **Time of Use / active days** (146).
- New Battery Setting entities: battery control mode (98), operation mode (111), lithium/BMS
  protocol (223), battery resistance (113), charging efficiency (114), grid-charge start SOC (127),
  generator charge start SOC (124) and current (125), generator max run (121) and down time (122).
- New Grid setting entities: grid frequency (183), reconnection time (180), frequency
  high/low protection (187/188).
- New SmartLoad entities: IO mode (133), SmartLoad on/off SOC (137/135).
- New Advanced Function entities: grid and generator peak-shaving switches (bits of 178) and
  their power limits (191/190), asymmetric phase feeding (237), MPPT multi-point scan (341).
- Fix: **register 340 was labelled "Max Sell Power" and 143 "Max Grid Output Power"** - they are
  Max Solar Power (340) and Max Sell Power (143). Renamed; `max_grid_output_power` is now
  `max_sell_power_143`.
- Fix: number read-back ignored the write scaling, so Active Power Regulation and the grid
  voltage limits read 10x too high. Read factor now defaults to 1/write_factor.
- New: switches support `bit:`/`mask:` for settings that share one register (178, 341),
  read-modify-write so neighbouring bits are preserved.
- New: controls are grouped into sub-devices mirroring the Deye Cloud batch-command pages
  (Battery Setting, System Work Mode, Grid Setting, SmartLoad Setting, Advanced Function,
  Time of Use, Basic Setting).
- New: advanced settings from the SolarMAN app (SmartLoad Setting / Advanced Function-1).
  - Writable: SmartLoad Setup (133), GEN Connect To Grid Input (189), ARC Fault
    Detection (181), Gen/Grid Peak Shaving on/off (178 bit fields) and power (190/191),
    Asymmetric Phase Feeding (237).
  - Read-only (disabled by default): Parallel, Equipment Mode, Parallel Modbus SN (336),
    DRM (178), Backup Delay (209), AC Couple Setup (234), MPPT Scan (341), Grid Check
    Source (344), Meter Select (345), CT Ratio (347).
  - Not included (no documented register): BMS-stop, Neutral to earth bonding,
    EX_MeterCT, Grid Tie Meter2, Low_Noise.
- New: `mask:` on switch/select controls writes only that bit field. The register is
  re-read inside the write lock, so flags packed into one register don't clobber each other.
- Change: sensor `mask:` now shifts the field down to bit 0.

## 0.1.3 (personal fork of upstream 0.1.1)
- Fix: settings (battery currents, SOC limits, work mode, switches, TOU) were never
  applied. Deye hybrids reject Modbus FC06; all writes now use FC16.
- Fix: pymodbus >= 3.10 renamed `slave=` to `device_id=`; the unit id is now passed
  correctly for any pymodbus version.
- Fix: writes share the polling lock; freshly written values are held for 30 s so a
  stale poll does not flip the UI back.
- Fix: failed writes raise an error in HA and are logged.
- Fix: address offset was applied twice on reads; RTU-over-TCP client construction.
- New: `PV Power` sensor = PV1 + PV2 + PV3 + PV4 power.
- New: `compute: sum` + `sources:` supported in register maps for derived sensors.
