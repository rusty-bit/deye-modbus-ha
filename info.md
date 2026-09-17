# Deye Modbus (Hybrid Inverter)

> **Personal fork** of [Developer089/deye-modbus-ha](https://github.com/Developer089/deye-modbus-ha).
> It fixes settings writes (upstream sends FC06, which Deye hybrids reject, and the wrong
> pymodbus unit id on current HA releases), reports failed writes instead of failing silently,
> and adds a **PV Power** sensor plus the SolarMAN **advanced settings**. Same `deye_modbus`
> domain, so entity IDs are kept — uninstall the upstream version first.

Local Home Assistant integration for **Deye three-phase hybrid inverters** — SUN-\*K-SG04LP3 / SG05LP3 family, including the **SUN-12K-SG05LP3**. It polls the inverter over **Modbus TCP** directly, either through the Deye WiFi/LAN logger (default port **8899**) or an RS485-to-TCP gateway (port **502**). No cloud, no SolarMAN account.

## What you get

- 100% local polling — nothing leaves your network.
- Sensors: PV strings, battery (SOC/power/temperature), grid import/export, per-phase grid/inverter/load, temperatures, plus daily and lifetime energy counters for the Energy dashboard.
- Controls: work mode, solar sell, grid/generator charge, battery current & SOC limits, max sell power, and 6-slot time-of-use programming.
- Advanced settings (fork): SmartLoad Setup, GEN Connect To Grid Input, ARC Fault Detection, Gen/Grid Peak Shaving + power, Asymmetric Phase Feeding; Parallel, Equipment Mode, Modbus SN, DRM, Backup Delay, AC Couple, MPPT Scan, Meter Select and CT Ratio are read-only.
- Guided config flow (pick model → host/port/unit ID/scan interval) and an options flow for transport, address offset and serial params.
- Services: `write_register`, `write_registers`, `write_u32` for advanced access.

Some entities (PV3/PV4, per-phase detail, TOU slots) ship **disabled by default** — enable them in the entity settings.

## Supported models

- Deye SUN-12K-SG05LP3 (3-phase hybrid)
- Deye SUN-5/6/8/10/12K-SG05LP3 (3-phase hybrid)
- Deye SUN-5/6/8/10/12K-SG04LP3 (3-phase hybrid)

## Quick start

1. Install via HACS, then **restart Home Assistant**.
2. **Settings ▸ Devices & Services ▸ Add Integration → "Deye Modbus"**.
3. Pick your model and enter the logger IP (e.g. `192.168.x.x`), port (`8899` for the Deye logger, `502` for an RS485↔TCP gateway), Modbus unit ID (`1`) and scan interval.

> Note: the inverter accepts only **one Modbus connection at a time**, so this conflicts with SolarMAN cloud logging and other Modbus pollers.

See the [README](https://github.com/rusty-bit/deye-modbus-ha) for the full entity list, options, services and troubleshooting.
