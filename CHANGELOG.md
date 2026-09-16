# Changelog (personal fork)

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
