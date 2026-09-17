"""Simulated-inverter test (no Home Assistant needed).

Starts a local Modbus server that, like a Deye, rejects FC06, then checks that
reads, FC16 writes, read-back and the PV Power sum work.
Run from repo root:  pip install pymodbus pyyaml && python tests/sim_inverter_test.py
"""
import os, sys, types, asyncio, logging, yaml
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING)
# --- minimal homeassistant stubs
ha=types.ModuleType("homeassistant"); sys.modules["homeassistant"]=ha
core=types.ModuleType("homeassistant.core"); core.HomeAssistant=object; sys.modules["homeassistant.core"]=core
h=types.ModuleType("homeassistant.helpers"); sys.modules["homeassistant.helpers"]=h
uc=types.ModuleType("homeassistant.helpers.update_coordinator")
class UpdateFailed(Exception): pass
class DataUpdateCoordinator:
    def __class_getitem__(cls, i): return cls
    def __init__(self, hass, logger, name, update_interval): self.data=None
    async def async_request_refresh(self): self.data = await self._async_update_data()
    def async_set_updated_data(self, d): self.data=d
uc.UpdateFailed=UpdateFailed; uc.DataUpdateCoordinator=DataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"]=uc
sys.path.insert(0,REPO + "/custom_components/deye_modbus")
import importlib.util
spec=importlib.util.spec_from_file_location("coord",REPO + "/custom_components/deye_modbus/coordinator.py")
coord=importlib.util.module_from_spec(spec); sys.modules["coord"]=coord; spec.loader.exec_module(coord)

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusDeviceContext
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.pdu import ExceptionResponse

class DeyeBlock(ModbusSparseDataBlock): pass
vals={i:0 for i in range(0,1000)}
vals.update({108:100,117:20,672:1200,673:850,674:0,675:300,588:55})
# advanced settings as shown in the SolarMAN app screenshot: all 2-bit flags in
# 178 "disable" (10), parallel off / slave / Modbus SN 1, MPPT scan on,
# Eastron meter, CT ratio 2000, peak-shaving powers 8000 W
vals.update({178:0x20AA,190:8000,191:8000,336:1<<10,341:0x0004,345:1,347:2000})
block=DeyeBlock(vals)
dev=ModbusDeviceContext(hr=block)
ctx=ModbusServerContext(devices={1:dev},single=False)

async def main():
    import pymodbus.pdu.register_message as rm
    # emulate Deye: FC06 not supported
    pass
    async def reject(self, context, device_id): return ExceptionResponse(self.function_code, 1)
    rm.WriteSingleRegisterRequest.datastore_update=reject
    task=asyncio.create_task(StartAsyncTcpServer(context=ctx,address=("127.0.0.1",15020)))
    await asyncio.sleep(1)
    m=yaml.safe_load(open(REPO + "/custom_components/deye_modbus/maps/sun_3ph_hybrid.yaml"))
    initmod=open(REPO + "/custom_components/deye_modbus/__init__.py").read()
    ns={}
    src=initmod[initmod.index("_REGISTER_FIELDS"):initmod.index("async def async_setup_entry")]
    exec(src,ns)
    sensors,controls=ns["_auto_inject_readbacks"](m["sensors"],m["controls"])
    regs=[coord.RegisterDef(**{k:v for k,v in r.items() if k in ns["_REGISTER_FIELDS"]}) for r in sensors]
    c=coord.DeyeModbusCoordinator(None,"127.0.0.1",15020,1,regs,15)
    await c.async_request_refresh()
    d=c.data
    print("PV power:",d["pv_power"],"| max charge rb:",d["rb_batt_max_charge_current"],"| low soc rb:",d["rb_batt_low_soc"])
    # old-style FC06 write would fail here; new write uses FC16
    ok=await c.write_single_register(108,60); ok2=await c.write_single_register(117,35)
    cl=await c._ensure_client(); r=await cl.read_holding_registers(108,count=10,device_id=1)
    print("writes ok:",ok,ok2,"| device now 108,117:",r.registers[0],r.registers[9])
    print("after refresh rb:",c.data["rb_batt_max_charge_current"],c.data["rb_batt_low_soc"])
    # FC06 directly, to prove emulation rejects it
    cl=await c._ensure_client(); rr=await cl.write_register(108,50,device_id=1); print("raw FC06 isError:",rr.isError())
    # advanced settings decode (bit fields shifted down)
    adv={k:d[k] for k in ("adv_parallel","adv_equipment_mode","adv_modbus_sn","adv_drm","adv_mppt_scan","adv_meter_select","adv_ct_ratio")}
    print("advanced:",adv)
    assert adv=={"adv_parallel":0,"adv_equipment_mode":0,"adv_modbus_sn":1,"adv_drm":2,"adv_mppt_scan":1,"adv_meter_select":1,"adv_ct_ratio":2000}, adv
    # enable grid peak-shaving: only bits 4-5 of 178 may change (10 -> 11)
    ok=await c.write_register_bits(178,0x0030,3<<4)
    r=await cl.read_holding_registers(178,count=1,device_id=1)
    print("bit write ok:",ok,"| 178 now 0x%04X" % r.registers[0])
    assert ok and r.registers[0]==0x20BA, hex(r.registers[0])
    assert c.data["adv_drm"]==2 and (int(c.data["rb_grid_peak_shaving"]) & 0x30)>>4==3
    # then gen peak-shaving: grid flag must survive
    ok=await c.write_register_bits(178,0x000C,3<<2)
    r=await cl.read_holding_registers(178,count=1,device_id=1)
    print("second bit write ok:",ok,"| 178 now 0x%04X" % r.registers[0])
    assert ok and r.registers[0]==0x20BE, hex(r.registers[0])
    print("ALL CHECKS PASSED")
    await c.async_close(); task.cancel()
asyncio.run(main())
