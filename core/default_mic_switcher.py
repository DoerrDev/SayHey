from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import comtypes
from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
from ctypes import c_uint, pointer
from ctypes.wintypes import LPCWSTR

from pycaw.pycaw import AudioUtilities, PROPERTYKEY
from pycaw.constants import EDataFlow, ERole

log = logging.getLogger(__name__)

_STATE_PATH = Path(__file__).resolve().parent.parent / "mic_switch_state.json"

CLSID_PolicyConfigClient = GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
IID_IPolicyConfig = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")

_PKEY_FRIENDLY = PROPERTYKEY()
_PKEY_FRIENDLY.fmtid = GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")
_PKEY_FRIENDLY.pid = 14


class _IPolicyConfig(IUnknown):
    _iid_ = IID_IPolicyConfig
    _methods_ = [
        COMMETHOD([], HRESULT, "GetMixFormat"),
        COMMETHOD([], HRESULT, "GetDeviceFormat"),
        COMMETHOD([], HRESULT, "ResetDeviceFormat"),
        COMMETHOD([], HRESULT, "SetDeviceFormat"),
        COMMETHOD([], HRESULT, "GetProcessingPeriod"),
        COMMETHOD([], HRESULT, "SetProcessingPeriod"),
        COMMETHOD([], HRESULT, "GetShareMode"),
        COMMETHOD([], HRESULT, "SetShareMode"),
        COMMETHOD([], HRESULT, "GetPropertyValue"),
        COMMETHOD([], HRESULT, "SetPropertyValue"),
        COMMETHOD(
            [], HRESULT, "SetDefaultEndpoint",
            (["in"], LPCWSTR, "wszDeviceId"),
            (["in"], c_uint, "eRole"),
        ),
        COMMETHOD([], HRESULT, "SetEndpointVisibility"),
    ]


def _set_default(device_id: str) -> None:
    comtypes.CoInitialize()
    try:
        policy = comtypes.CoCreateInstance(
            CLSID_PolicyConfigClient, _IPolicyConfig, comtypes.CLSCTX_ALL
        )
        for role in (0, 1, 2):
            policy.SetDefaultEndpoint(device_id, role)
    finally:
        comtypes.CoUninitialize()


def _list_capture():
    enumerator = AudioUtilities.GetDeviceEnumerator()
    default = enumerator.GetDefaultAudioEndpoint(
        EDataFlow.eCapture.value, ERole.eConsole.value
    )
    default_id = default.GetId()
    coll = enumerator.EnumAudioEndpoints(EDataFlow.eCapture.value, 1)
    out = []
    for i in range(coll.GetCount()):
        dev = coll.Item(i)
        dev_id = dev.GetId()
        store = dev.OpenPropertyStore(0)
        name = store.GetValue(pointer(_PKEY_FRIENDLY)).GetValue()
        out.append((dev_id, name, dev_id == default_id))
    return out


def _find_by_keyword(devices, keyword: str):
    kw = keyword.lower()
    return next(((i, n) for i, n, _ in devices if kw in n.lower()), None)


def _save_state(original_id: str, switched_to_id: str) -> None:
    _STATE_PATH.write_text(
        json.dumps({"original_id": original_id, "switched_to_id": switched_to_id}),
        encoding="utf-8",
    )


def _load_state() -> Optional[dict]:
    if not _STATE_PATH.exists():
        return None
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_state() -> None:
    if _STATE_PATH.exists():
        try:
            _STATE_PATH.unlink()
        except Exception:
            pass


class DefaultMicSwitcher:
    """启动时切到目标设备，关闭时恢复。崩溃保护通过状态文件实现。"""

    def __init__(self, keyword: str = "CABLE Output") -> None:
        self.keyword = keyword
        self._switched = False

    def recover_from_crash(self) -> None:
        """启动最早期调用：如果上次进程崩溃留下状态文件，先恢复原设备。"""
        state = _load_state()
        if not state:
            return
        try:
            devices = _list_capture()
            current_default = next((i for i, _, d in devices if d), None)
            # 仅当当前默认仍是上次切到的设备时才恢复，避免覆盖用户手动改动
            if current_default == state.get("switched_to_id"):
                original = state.get("original_id")
                if original and any(i == original for i, _, _ in devices):
                    _set_default(original)
                    log.info("crash recovery: restored default mic to %s", original)
        except Exception as e:
            log.warning("crash recovery failed: %s", e)
        finally:
            _clear_state()

    def switch(self) -> Optional[str]:
        """切到关键词匹配的设备。成功返回目标设备名，未切返回 None。"""
        try:
            devices = _list_capture()
            current_default = next(((i, n) for i, n, d in devices if d), None)
            target = _find_by_keyword(devices, self.keyword)
            if not target:
                log.info("default mic switcher: no device matches '%s', skip", self.keyword)
                return None
            target_id, target_name = target
            if current_default and current_default[0] == target_id:
                log.info("default mic already is '%s', skip", target_name)
                return None
            original_id = current_default[0] if current_default else ""
            _set_default(target_id)
            _save_state(original_id, target_id)
            self._switched = True
            log.info("default mic switched: '%s' -> '%s'",
                     current_default[1] if current_default else "?", target_name)
            return target_name
        except Exception as e:
            log.warning("default mic switch failed: %s", e)
            return None

    def restore(self) -> None:
        """正常关闭时调用，恢复原始默认设备。"""
        if not self._switched:
            return
        state = _load_state()
        if not state:
            return
        try:
            original = state.get("original_id")
            if original:
                _set_default(original)
                log.info("default mic restored to %s", original)
        except Exception as e:
            log.warning("default mic restore failed: %s", e)
        finally:
            _clear_state()
            self._switched = False
