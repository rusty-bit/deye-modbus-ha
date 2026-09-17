# Changelog (personal fork)

## 0.1.4
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
