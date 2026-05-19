from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import sounddevice as sd


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


class DeviceResolver:
    def __init__(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        self.devices = [
            AudioDevice(
                index=index,
                name=device["name"],
                hostapi=hostapis[device["hostapi"]]["name"],
                max_input_channels=int(device["max_input_channels"]),
                max_output_channels=int(device["max_output_channels"]),
                default_samplerate=float(device["default_samplerate"]),
            )
            for index, device in enumerate(devices)
        ]

    def refresh(self) -> None:
        self._refresh()

    def input_devices(self) -> list[AudioDevice]:
        return [device for device in self.devices if device.max_input_channels > 0]

    def output_devices(self) -> list[AudioDevice]:
        return [device for device in self.devices if device.max_output_channels > 0]

    def stable_input_candidates(self, preferred: AudioDevice) -> list[AudioDevice]:
        return self._stable_candidates(preferred, direction="input")

    def stable_output_candidates(self, preferred: AudioDevice) -> list[AudioDevice]:
        return self._stable_candidates(preferred, direction="output")

    def get(self, index: int) -> AudioDevice:
        return self.devices[index]

    def resolve_input(self, index: Optional[int], name: Optional[str]) -> AudioDevice:
        return self._resolve(index, name, direction="input")

    def resolve_output(self, index: Optional[int], name: Optional[str]) -> AudioDevice:
        return self._resolve(index, name, direction="output")

    def resolve_cable_input(self, preferred_name: str = "CABLE Input") -> AudioDevice:
        return self._resolve_required_name(
            preferred_name,
            direction="output",
            fallback_keywords=("cable input", "cable in", "vb-audio virtual cable"),
        )

    def resolve_cable_output(self, preferred_name: str = "CABLE Output") -> AudioDevice:
        return self._resolve_required_name(
            preferred_name,
            direction="input",
            fallback_keywords=("cable output", "vb-audio virtual cable"),
        )

    def _resolve(self, index: Optional[int], name: Optional[str], direction: str) -> AudioDevice:
        channel_attr = "max_input_channels" if direction == "input" else "max_output_channels"
        candidates = self.input_devices() if direction == "input" else self.output_devices()

        if index is not None:
            device = self.get(index)
            if getattr(device, channel_attr) < 1:
                raise RuntimeError(f"Device #{index} is not a valid {direction} device.")
            return device

        keyword = (name or "").lower()
        if keyword:
            matches = [device for device in candidates if keyword in device.name.lower()]
            if matches:
                return self._prefer_hostapi(matches)

        if direction == "input":
            default_index = sd.default.device[0]
        else:
            default_index = sd.default.device[1]
        if default_index is not None and int(default_index) >= 0:
            default_device = self.get(int(default_index))
            if getattr(default_device, channel_attr) > 0:
                return default_device

        raise RuntimeError(f"No matching {direction} device found.")

    def _prefer_hostapi(self, devices: list[AudioDevice]) -> AudioDevice:
        for hostapi in ("MME", "Windows DirectSound", "Windows WASAPI"):
            for device in devices:
                if device.hostapi == hostapi:
                    return device
        return devices[0]

    def _stable_candidates(self, preferred: AudioDevice, direction: str) -> list[AudioDevice]:
        channel_attr = "max_input_channels" if direction == "input" else "max_output_channels"
        candidates = self.input_devices() if direction == "input" else self.output_devices()
        same_device = [
            device
            for device in candidates
            if getattr(device, channel_attr) > 0 and self._logical_key(device.name) == self._logical_key(preferred.name)
        ]
        if preferred not in same_device:
            same_device.append(preferred)

        hostapi_order = {"MME": 0, "Windows DirectSound": 1, "Windows WASAPI": 2}
        return sorted(
            same_device,
            key=lambda device: (
                hostapi_order.get(device.hostapi, 99),
                0 if device.index == preferred.index else 1,
                device.index,
            ),
        )

    def _logical_key(self, name: str) -> str:
        # MME truncates long names, so compare the stable prefix before host API suffixes differ.
        return name.lower().strip()[:28]

    def _resolve_required_name(
        self,
        name: str,
        direction: str,
        fallback_keywords: tuple[str, ...] = (),
    ) -> AudioDevice:
        keyword = name.lower()
        candidates = self.input_devices() if direction == "input" else self.output_devices()
        matches = [device for device in candidates if keyword in device.name.lower()]
        if not matches:
            for fallback_keyword in fallback_keywords:
                matches = [device for device in candidates if fallback_keyword in device.name.lower()]
                if matches:
                    break
        if not matches:
            raise RuntimeError(f"Required {direction} device not found: {name}")
        return self._prefer_hostapi(matches)
