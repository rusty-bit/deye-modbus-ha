"""DataUpdateCoordinator that polls a Deye hybrid inverter over Modbus.

Deye three-phase hybrid inverters expose *all* live measurements through the
holding-register space (function code 0x03), including the 500+ real-time block.
Unlike some vendors there is no separate "read once" settings space here, so
every mapped register is polled each cycle. Contiguous registers are batched
into single Modbus reads to keep the poll cheap.

Writes always use function code 0x10 (Write Multiple Registers): Deye
inverters reject or silently ignore FC06 (Write Single Register).
"""
from __future__ import annotations
import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

try:
    from pymodbus.client import AsyncModbusTcpClient
except Exception as exc:  # pragma: no cover
    _LOGGER.error("pymodbus import failed: %s", exc)
    raise

try:  # pymodbus >= 3.7
    from pymodbus import FramerType as _FramerType
    _RTU_FRAMER: Any = _FramerType.RTU
except Exception:  # noqa: BLE001
    try:
        from pymodbus.framer import ModbusRtuFramer as _RTU_FRAMER  # type: ignore
    except Exception:  # noqa: BLE001
        _RTU_FRAMER = None

# How long a freshly written value is trusted over a stale poll result.
PENDING_WRITE_SECONDS = 30


def _unit_kw(method) -> str | None:
    """Return the keyword pymodbus uses for the Modbus unit on this version.

    pymodbus >= 3.10: device_id, 3.0-3.9: slave, 2.x: unit.
    """
    try:
        params = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return None
    for kw in ("device_id", "slave", "unit"):
        if kw in params:
            return kw
    return None


@dataclass
class RegisterDef:
    """One decoded value read from the inverter."""

    name: str
    unique_id: str
    register_type: str = "holding"          # "holding" (0x03) or "input" (0x04)
    address: int = 0
    count: int = 1                           # 1 = 16-bit, 2 = 32-bit
    scale: float = 1.0
    offset: float = 0.0                      # raw is (value - offset) before scaling
    unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    signed: bool = False
    word_order: str = "high_low"             # 32-bit word order: high_low | low_high
    options: dict[int, str] | None = None    # enum mapping for sensors (0 -> "text")
    mask: int | None = None                  # bitmask applied to raw before sign/scale
    icon: str | None = None
    enabled_default: bool = True             # entity_registry_enabled_default
    precision: int | None = None             # suggested_display_precision (decimals)
    compute: str | None = None               # derived value: "sum" (no Modbus read)
    sources: list[str] = field(default_factory=list)  # unique_ids feeding `compute`


class DeyeModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls all mapped registers each cycle and decodes them."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        unit_id: int,
        registers: List[RegisterDef],
        scan_interval: int,
        transport: str = "tcp",
        serial_params: dict | None = None,
        address_offset: int = 0,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name="deye_modbus coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._host, self._port, self._unit_id = host, port, int(unit_id)
        self._registers: List[RegisterDef] = registers
        self._transport = (transport or "tcp").lower()
        self._serial_params = serial_params or {}
        self._client = None
        self._lock = asyncio.Lock()
        self._addr_off = int(address_offset or 0)
        self._computed = [r for r in registers if r.compute]
        self._polled = [r for r in registers if not r.compute]
        # address -> (raw word, expiry) for values we just wrote
        self._pending: dict[int, tuple[int, float]] = {}

    def _addr(self, addr: int) -> int:
        return int(addr) - self._addr_off if self._addr_off else int(addr)

    # ------------------------------------------------------------------ client
    async def _ensure_client(self):
        if self._client is None:
            kwargs: dict[str, Any] = {"port": self._port, "timeout": 5}
            if self._transport == "rtutcp":
                # Modbus RTU frames tunnelled over a raw TCP socket.
                if _RTU_FRAMER is None:
                    raise UpdateFailed("This pymodbus version has no RTU framer")
                kwargs["framer"] = _RTU_FRAMER
            self._client = AsyncModbusTcpClient(self._host, **kwargs)
        if not bool(getattr(self._client, "connected", False)):
            try:
                await self._client.connect()
            except Exception as e:  # noqa: BLE001
                raise UpdateFailed(f"Modbus connect failed: {e}") from e
            if not bool(getattr(self._client, "connected", False)):
                raise UpdateFailed(f"Modbus connect to {self._host}:{self._port} failed")
        return self._client

    def _unit_kwargs(self, method) -> dict[str, int]:
        kw = _unit_kw(method)
        return {kw: self._unit_id} if kw else {}

    # ------------------------------------------------------------------ polling
    async def _async_update_data(self) -> dict[str, Any]:
        async with self._lock:
            try:
                result: dict[str, Any] = {}
                inputs = [r for r in self._polled if r.register_type == "input"]
                holdings = [r for r in self._polled if r.register_type != "input"]
                if holdings:
                    await self._read_grouped(holdings, result, self._read_holding)
                if inputs:
                    await self._read_grouped(inputs, result, self._read_input)
                self._apply_computed(result)
                return result
            except UpdateFailed:
                raise
            except Exception as err:  # noqa: BLE001
                await self._reset_client()
                raise UpdateFailed(err) from err

    def _apply_computed(self, out: dict[str, Any]) -> None:
        for r in self._computed:
            if r.compute == "sum":
                vals = [out.get(src) for src in r.sources]
                vals = [v for v in vals if v is not None]
                out[r.unique_id] = (sum(vals) * r.scale) if vals else None
            else:
                out[r.unique_id] = None

    async def _reset_client(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

    async def _read_grouped(self, regs: list[RegisterDef], out: dict[str, Any], fn):
        regs = sorted(regs, key=lambda r: r.address)
        GAP = 8          # merge registers within this many words into one read
        MAX_WORDS = 110  # keep each Modbus frame comfortably below the 125 limit
        start = end = None
        acc: list[RegisterDef] = []
        for r in regs:
            if start is None:
                start, end, acc = r.address, r.address + r.count, [r]
                continue
            if r.address <= end + GAP and (r.address + r.count - start) <= MAX_WORDS:
                end = max(end, r.address + r.count)
                acc.append(r)
            else:
                await self._read_window(fn, out, start, end, acc)
                start, end, acc = r.address, r.address + r.count, [r]
        if start is not None:
            await self._read_window(fn, out, start, end, acc)

    async def _read_window(self, fn, out, start, end, regs):
        raw = await fn(start, end - start)
        if raw is None:
            _LOGGER.debug("Read of registers %s-%s failed", start, end - 1)
        elif fn == self._read_holding and self._pending:
            raw = list(raw)
            now = time.monotonic()
            for addr, (val, expiry) in list(self._pending.items()):
                if not start <= addr < end:
                    continue
                idx = addr - start
                if raw[idx] == val or now > expiry:
                    self._pending.pop(addr, None)   # inverter caught up (or gave up)
                else:
                    raw[idx] = val                  # stale poll - keep what we wrote
        for r in regs:
            out[r.unique_id] = self._decode(r, raw, start)

    def _decode(self, r: RegisterDef, raw, start) -> Any:
        if not raw:
            return None
        off = r.address - start
        chunk = raw[off:off + r.count]
        if len(chunk) < r.count:
            return None
        if r.count == 1:
            v = chunk[0]
            if r.mask is not None:
                v &= r.mask
            if r.signed and v >= 0x8000:
                v -= 0x10000
            return (v - r.offset) * r.scale
        if r.count == 2:
            if r.word_order == "low_high":
                low, high = chunk[0], chunk[1]
            else:
                high, low = chunk[0], chunk[1]
            v = (high << 16) | low
            if r.mask is not None:
                v &= r.mask
            if r.signed and v >= 0x80000000:
                v -= 0x100000000
            return (v - r.offset) * r.scale
        return None

    # ------------------------------------------------------------------ reads
    async def _call_read(self, method_name, address, count):
        client = await self._ensure_client()
        method = getattr(client, method_name)
        a = self._addr(address)
        try:
            return await method(a, count=count, **self._unit_kwargs(method))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("%s(%s, %s) raised %s", method_name, a, count, err)
            return None

    async def _read_input(self, address, count):
        rr = await self._call_read("read_input_registers", address, count)
        return None if rr is None or (getattr(rr, "isError", None) and rr.isError()) else getattr(rr, "registers", None)

    async def _read_holding(self, address, count):
        rr = await self._call_read("read_holding_registers", address, count)
        return None if rr is None or (getattr(rr, "isError", None) and rr.isError()) else getattr(rr, "registers", None)

    # ------------------------------------------------------------------ writes
    async def write_multiple_registers(self, address: int, values: list[int]) -> bool:
        """Write with FC16 - the only write function Deye inverters accept."""
        vals = [int(v) & 0xFFFF for v in values]
        a = self._addr(address)
        async with self._lock:
            try:
                client = await self._ensure_client()
                method = client.write_registers
                rr = await method(a, vals, **self._unit_kwargs(method))
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Write %s to register %s failed: %s", vals, address, err)
                await self._reset_client()
                return False
            if rr is None or (getattr(rr, "isError", None) and rr.isError()):
                _LOGGER.error("Inverter rejected write %s to register %s: %s", vals, address, rr)
                return False
            expiry = time.monotonic() + PENDING_WRITE_SECONDS
            for i, v in enumerate(vals):
                self._pending[address + i] = (v, expiry)
        _LOGGER.debug("Wrote %s to register %s", vals, address)
        self._patch_data(address, vals)
        await self.async_request_refresh()
        return True

    async def write_single_register(self, address: int, value: int) -> bool:
        # Deliberately FC16 with one value, not FC06.
        return await self.write_multiple_registers(address, [value])

    def _patch_data(self, address: int, vals: list[int]) -> None:
        """Reflect a successful write in coordinator data immediately."""
        if not self.data:
            return
        span = range(address, address + len(vals))
        data = dict(self.data)
        changed = False
        for r in self._polled:
            if r.register_type == "input" or r.address not in span:
                continue
            if r.address + r.count - 1 not in span:
                continue
            words = vals[r.address - address:r.address - address + r.count]
            data[r.unique_id] = self._decode(r, words, r.address)
            changed = True
        if changed:
            self._apply_computed(data)
            self.async_set_updated_data(data)

    async def write_u32(self, base_address: int, value: int, word_order: str = "high_low") -> bool:
        v = int(value) & 0xFFFFFFFF
        hi, lo = (v >> 16) & 0xFFFF, v & 0xFFFF
        values = [hi, lo] if word_order == "high_low" else [lo, hi]
        return await self.write_multiple_registers(base_address, values)

    async def write_coil(self, address: int, value: int) -> bool:
        a = self._addr(address)
        async with self._lock:
            try:
                client = await self._ensure_client()
                method = client.write_coil
                rr = await method(a, bool(value), **self._unit_kwargs(method))
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Write coil %s failed: %s", address, err)
                return False
        if rr is None or (getattr(rr, "isError", None) and rr.isError()):
            _LOGGER.error("Inverter rejected coil write %s: %s", address, rr)
            return False
        await self.async_request_refresh()
        return True

    async def async_close(self):
        try:
            if self._client:
                res = self._client.close()
                if inspect.isawaitable(res):
                    await res
        except Exception:  # noqa: BLE001
            pass
