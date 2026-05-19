import json
import sounddevice as sd


def main() -> None:
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    rows = []
    for index, device in enumerate(devices):
        hostapi_name = hostapis[device["hostapi"]]["name"]
        rows.append(
            {
                "index": index,
                "name": device["name"],
                "hostapi": hostapi_name,
                "max_input_channels": device["max_input_channels"],
                "max_output_channels": device["max_output_channels"],
                "default_samplerate": device["default_samplerate"],
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
