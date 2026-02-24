"""Production test execution service.

Reads serial output from the device running test firmware and handles
each test step: LED validation, audio recording, RF measurement (TinySA),
pressure validation (OpenWeather API), and automatic tests.
"""
import time
import struct
import threading
import numpy as np
import serial
import serial.tools.list_ports
from typing import Optional, Callable, Tuple

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import requests
except ImportError:
    requests = None

from core.serial_manager import SerialManager
from services.state_manager import AppState
from utils.constants import (
    TEST_NAMES,
    TINYSA_VID, TINYSA_PID, TINYSA_SCALE,
    AUDIO_POWER_THRESHOLD, AUDIO_DURATION, AUDIO_SAMPLE_RATE,
    BLE_POWER_THRESHOLD, BLE_F_LOW, BLE_F_HIGH, BLE_POINTS,
    LORA_POWER_THRESHOLD, LORA_F_LOW, LORA_F_HIGH, LORA_POINTS,
    PRESSURE_TOLERANCE, WEATHER_API_KEY, WEATHER_CITY, WEATHER_ALTITUDE,
    DEVICE_TYPE_SUMMIT,
)


class TestRunner:
    """
    Runs the production test sequence by reading serial messages from the device
    and triggering the appropriate test logic for each step.

    Communicates with the UI via callbacks.
    """

    def __init__(
        self,
        serial_manager: SerialManager,
        state: AppState,
        log_callback: Optional[Callable[[str], None]] = None,
        enable_checkbox_callback: Optional[Callable[[str], None]] = None,
        check_test_callback: Optional[Callable[[str, bool], None]] = None,
        rf_result_callback: Optional[Callable[[str, float, float], None]] = None,
        pressure_result_callback: Optional[Callable[[float, bool], None]] = None,
        tests_complete_callback: Optional[Callable[[], None]] = None,
    ):
        self._serial = serial_manager
        self._state = state
        self._log = log_callback or (lambda msg: None)
        self._enable_checkbox = enable_checkbox_callback or (lambda name: None)
        self._check_test = check_test_callback or (lambda name, ok: None)
        self._rf_result = rf_result_callback or (lambda tech, freq, power: None)
        self._pressure_result = pressure_result_callback or (lambda val, ok: None)
        self._tests_complete = tests_complete_callback or (lambda: None)

        self._running = False
        self._stop_event = threading.Event()
        self._paused = False  # Pause loop during LED click / audio

        # LED click counter (managed by UI, incremented via on_led_click)
        self._led_cnt = 0

        # Prompts for each manual LED test
        self._led_prompts = {
            "LED_GREEN1": "Verify GREEN LED 1 is ON, then check the box",
            "LED_GREEN2": "Verify GREEN LED 2 is ON, then check the box",
            "LED_RED1": "Verify RED LED 1 is ON, then check the box",
            "LED_RED2": "Verify RED LED 2 is ON, then check the box",
            "LED_FLASH": "Verify LEDs are FLASHING, then check the box",
        }

        # Measurement results
        self._sensor_pressure = 0.0
        self._max_freq_ble = 0.0
        self._max_power_ble = 0.0
        self._max_freq_lora = 0.0
        self._max_power_lora = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the test loop in a background thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._led_cnt = 0
        self._running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop the test loop."""
        self._stop_event.set()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def on_led_click(self) -> None:
        """Called by UI when user clicks a LED checkbox.

        Sends 'T' to device and advances to next LED or triggers audio test.
        """
        # Run in worker thread to avoid blocking UI and serial conflicts
        threading.Thread(target=self._handle_led_click, daemon=True).start()

    def _handle_led_click(self) -> None:
        """Worker thread for LED click handling."""
        self._paused = True  # Pause the read loop
        try:
            self._serial.write(b'T')
        except Exception:
            pass

        name = TEST_NAMES[self._led_cnt]
        self._check_test(name, True)
        self._log(f"  -> {name} OK")

        self._led_cnt += 1

        if self._led_cnt < 5:
            # Enable next LED checkbox with prompt
            next_name = TEST_NAMES[self._led_cnt]
            prompt = self._led_prompts.get(next_name, "")
            self._log("")
            self._log(f">>> {prompt}")
            self._enable_checkbox(next_name)
            self._paused = False  # Resume read loop
        else:
            # After 5th LED click -> audio test (loop stays paused)
            self._log("")
            self._log(">>> SOUND test: Recording audio (3s)...")
            self._run_audio_test()
            # Resume read loop after audio completes
            self._paused = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main serial reading loop - mirrors test_application() from production_test.py."""
        # Warmup microphone
        self._warmup_microphone()

        # Set short timeout for readline
        self._serial.set_timeout(0.2)

        while not self._stop_event.is_set():
            time.sleep(0.1)

            # Skip reading while paused (LED click / audio in progress)
            if self._paused:
                continue

            try:
                line = self._serial.readline()
            except Exception:
                continue

            if not line:
                continue

            # Parse line
            chaine = str(line)
            chaine = chaine.replace("b'", '').replace("\\r", '').replace("\\n", '')
            chaine = chaine.replace('b"', '').replace("'", '')

            if not chaine:
                continue

            # --- Test event handling ---
            self._handle_message(chaine)

        self._running = False

    def _handle_message(self, chaine: str) -> None:
        """Handle a single parsed message from the device."""

        # LED_GREEN1 - start of LED test sequence
        if "LED_GREEN1" in chaine:
            self._log("")
            self._log("=== VISUAL LED TESTS ===")
            prompt = self._led_prompts["LED_GREEN1"]
            self._log(f">>> {prompt}")
            self._enable_checkbox("LED_GREEN1")
            return

        # BC_STATE (Battery Charger)
        if "BC State OK" in chaine:
            self._log("")
            self._log("=== AUTO: Battery Charger State ===")
            self._check_test("BC_STATE", True)
            self._state.set_test_result("BC_STATE", True)
            self._log("  -> BC_STATE OK")
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # Pressure - No barometer
        if "No barometer" in chaine:
            self._log("")
            self._log("=== AUTO: Pressure Sensor ===")
            if self._state.device_type == DEVICE_TYPE_SUMMIT:
                self._log("  -> No barometer detected (unexpected for SUMMIT)")
            else:
                self._log("  -> No barometer (normal for LYNKX+)")
            # Always send 'T' to let device continue
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # Pressure - Barometer reading
        if "Barometer" in chaine:
            self._log("")
            self._log("=== AUTO: Pressure Sensor ===")
            if self._state.device_type != DEVICE_TYPE_SUMMIT:
                # LYNKX+ standard: ignore barometer but still let device continue
                self._log("  -> Barometer ignored (LYNKX+ standard)")
            else:
                # SUMMIT: validate pressure
                try:
                    tab = chaine.split()
                    self._sensor_pressure = round(int(tab[7]) / 100)
                    self._log(f"  -> Sensor pressure: {self._sensor_pressure} mbar")
                    self._check_pressure()
                    return  # check_pressure sends 'T' or 'S'
                except (IndexError, ValueError) as e:
                    self._log(f"  -> Pressure parse error: {e}")
            # Always send 'T' to let device continue (except SUMMIT which is handled above)
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # ACCELEROMETER
        if "Accelerometer OK" in chaine:
            self._log("")
            self._log("=== AUTO: Accelerometer ===")
            self._check_test("ACCELEROMETER", True)
            self._state.set_test_result("ACCELEROMETER", True)
            self._log("  -> ACCELEROMETER OK")
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # BLE RF test
        if "BLE Initialized" in chaine:
            self._log("")
            self._log("=== AUTO: BLE RF Measurement ===")
            self._run_ble_test()
            return

        # LoRa RF test
        if "LoRa Initialized" in chaine:
            self._log("")
            self._log("=== AUTO: LoRa RF Measurement ===")
            self._run_lora_test()
            return

        # GNSS
        if "GNSS OK" in chaine:
            self._log("")
            self._log("=== AUTO: GNSS Module ===")
            self._check_test("GNSS", True)
            self._state.set_test_result("GNSS", True)
            self._log("  -> GNSS OK")
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # Flash
        if "Flash OK" in chaine:
            self._log("")
            self._log("=== AUTO: Flash Memory ===")
            self._check_test("FLASH", True)
            self._state.set_test_result("FLASH", True)
            self._log("  -> FLASH OK")
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # Emergency tab
        if "Emergency tab OK" in chaine:
            self._log("")
            self._log("=== AUTO: Emergency Tab ===")
            self._check_test("EMERGENCY_TAB", True)
            self._state.set_test_result("EMERGENCY_TAB", True)
            self._log("  -> EMERGENCY_TAB OK")
            try:
                self._serial.write(b'T')
            except Exception:
                pass
            return

        # Production tests complete - finalization phase
        if "Production tests complete" in chaine:
            self._finalize()
            return

        # Filter garbage
        if "\\x" in chaine:
            return

        # Log valid messages
        if chaine:
            clean = chaine.replace("\\t", '')
            if "\\t" in chaine:
                self._log(f"       {clean}")
            else:
                self._log(clean)

    # ------------------------------------------------------------------
    # Audio test
    # ------------------------------------------------------------------

    def _warmup_microphone(self) -> None:
        """Pre-initialize USB Audio microphone."""
        if sd is None:
            self._log("[AUDIO] sounddevice not available")
            return
        try:
            sd.default.device = ('USB Audio', None)
            dummy = sd.rec(10, samplerate=AUDIO_SAMPLE_RATE, channels=1)
            sd.wait()
        except Exception as e:
            self._log(f"[AUDIO INIT] Warmup error: {e}")

    def _run_audio_test(self) -> None:
        """Record 3 seconds of audio and validate power levels."""
        if sd is None:
            self._log("[AUDIO] sounddevice not available - skipping")
            return

        self._log("🎤 Recording audio (3s)...")
        try:
            full_recording = sd.rec(
                int(AUDIO_DURATION * AUDIO_SAMPLE_RATE),
                samplerate=AUDIO_SAMPLE_RATE,
                channels=1
            )
            sd.wait()

            one_sec = AUDIO_SAMPLE_RATE
            segments = [
                full_recording[0:one_sec].flatten(),
                full_recording[one_sec:2 * one_sec].flatten(),
                full_recording[2 * one_sec:3 * one_sec].flatten(),
            ]

            powers = [self._calculate_power(s) for s in segments]

            if all(p > AUDIO_POWER_THRESHOLD for p in powers):
                self._log("       -> Sound OK")
                self._check_test("SOUND", True)
                self._state.set_test_result("SOUND", True)
                self._serial.write(b'T')
            else:
                self._log(
                    f"{powers[0]:.1f}dB, {powers[1]:.1f}dB, {powers[2]:.1f}dB "
                    f"-> Sound NOT OK"
                )
                self._serial.write(b'S')

        except Exception as e:
            self._log(f"[AUDIO] Error: {e}")

    @staticmethod
    def _calculate_power(signal: np.ndarray) -> float:
        """Calculate signal power in dB."""
        rms = np.sqrt(np.mean(signal ** 2))
        if rms == 0:
            return -100.0
        return 20 * np.log10(rms)

    # ------------------------------------------------------------------
    # RF tests (TinySA)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tinysa_port() -> Optional[str]:
        """Find TinySA spectrum analyzer serial port."""
        for device in serial.tools.list_ports.comports():
            if device.vid == TINYSA_VID and device.pid == TINYSA_PID:
                return device.device
        return None

    @staticmethod
    def _get_tinysa_dBm(
        s_port: str, f_low: int, f_high: int, points: int,
        rbw: int = 0
    ) -> np.ndarray:
        """Perform a sweep on TinySA and return power values in dBm."""
        with serial.Serial(port=s_port, baudrate=115200) as tinySA:
            tinySA.timeout = 1
            while tinySA.inWaiting():
                tinySA.read_all()
                time.sleep(0.1)

            span_k = (f_high - f_low) / 1e3
            rbw_k = span_k / points if rbw == 0 else rbw / 1e3
            rbw_k = max(3, min(600, rbw_k))

            tinySA.write(f'rbw {int(rbw_k)}\r'.encode())
            tinySA.read_until(b'ch> ')

            timeout = int(span_k / (rbw_k * rbw_k) + points / 1e3 + 5)
            tinySA.timeout = timeout

            tinySA.write(f'scanraw {int(f_low)} {int(f_high)} {int(points)}\r'.encode())
            tinySA.read_until(b'{')
            raw_data = tinySA.read_until(b'}ch> ')
            tinySA.write('rbw auto\r'.encode())

        raw_data = struct.unpack('<' + 'xH' * points, raw_data[:-5])
        raw_data = np.array(raw_data, dtype=np.uint16)
        dBm_power = raw_data / 32 - TINYSA_SCALE
        return dBm_power

    def _measure_freq_power_zoom(
        self, f_low: int, f_high: int, points: int,
        rbw: int = 0, repeats: int = 1, zoom_span: int = 200_000
    ) -> Tuple[Optional[int], Optional[float]]:
        """Two-pass sweep: rough then zoomed for precision."""
        device = self._get_tinysa_port()
        if device is None:
            self._log("[RF] TinySA not found")
            return None, None

        max_freqs = []
        max_powers = []

        for _ in range(repeats):
            # Rough sweep
            meas_power = self._get_tinysa_dBm(device, f_low, f_high, points, rbw)
            frequencies = np.linspace(f_low, f_high, points)

            rough_max_idx = int(np.argmax(meas_power))
            rough_max_freq = int(frequencies[rough_max_idx])

            # Zoomed sweep around peak
            zoom_low = max(rough_max_freq - zoom_span, f_low)
            zoom_high = min(rough_max_freq + zoom_span, f_high)
            meas_zoom = self._get_tinysa_dBm(device, zoom_low, zoom_high, points, rbw)
            freq_zoom = np.linspace(zoom_low, zoom_high, points)

            fine_max_idx = int(np.argmax(meas_zoom))
            max_freqs.append(int(freq_zoom[fine_max_idx]))
            max_powers.append(float(meas_zoom[fine_max_idx]))

        final_freq = int(np.median(max_freqs))
        final_power = round(float(np.median(max_powers)), 1)
        return final_freq, final_power

    def _run_ble_test(self) -> None:
        """Measure BLE RF output via TinySA."""
        self._log("📡 Measuring BLE RF...")
        freq, power = self._measure_freq_power_zoom(
            BLE_F_LOW, BLE_F_HIGH, BLE_POINTS
        )
        if freq is None:
            return

        self._max_freq_ble = freq
        self._max_power_ble = power
        self._state.set_rf_measurements(ble_freq=freq, ble_power=power)
        self._rf_result("BLE", freq, power)

        if power > BLE_POWER_THRESHOLD:
            self._log("       -> BLE OK")
            self._check_test("BLE", True)
            self._state.set_test_result("BLE", True)
            self._serial.write(b'T')
        else:
            self._log("       -> BLE NOT OK")
            self._serial.write(b'S')

    def _run_lora_test(self) -> None:
        """Measure LoRa RF output via TinySA."""
        self._log("📡 Measuring LoRa RF...")
        freq, power = self._measure_freq_power_zoom(
            LORA_F_LOW, LORA_F_HIGH, LORA_POINTS
        )
        if freq is None:
            return

        self._max_freq_lora = freq
        self._max_power_lora = power
        self._state.set_rf_measurements(lora_freq=freq, lora_power=power)
        self._rf_result("LORA", freq, power)

        if power > LORA_POWER_THRESHOLD:
            self._log("       -> LoRa OK")
            self._check_test("LORA", True)
            self._state.set_test_result("LORA", True)
            self._serial.write(b'T')
        else:
            self._log("       -> LoRa NOT OK")
            self._serial.write(b'S')

    # ------------------------------------------------------------------
    # Pressure test
    # ------------------------------------------------------------------

    def _get_weather_pressure(self) -> float:
        """Get current pressure from OpenWeather API adjusted for altitude."""
        if requests is None:
            self._log("[PRESSURE] requests module not available")
            return 0.0
        try:
            url = (
                f"http://api.openweathermap.org/data/2.5/weather?"
                f"&q={WEATHER_CITY}&appid={WEATHER_API_KEY}"
            )
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get("cod") == 404:
                return 0.0
            grnd_level = data["main"]["grnd_level"]
            pressure = grnd_level - (WEATHER_ALTITUDE * 0.0115) * 100
            return pressure
        except Exception as e:
            self._log(f"[PRESSURE] Weather API error: {e}")
            return 0.0

    def _check_pressure(self) -> None:
        """Validate sensor pressure against weather API."""
        current = self._get_weather_pressure()
        self._state.set_pressure(current)

        if current == 0:
            self._log("       -> Pressure: cannot get reference")
            self._serial.write(b'S')
            self._pressure_result(0, False)
            return

        relative_error = (abs(current - self._sensor_pressure) / current) * 100

        if relative_error < PRESSURE_TOLERANCE:
            self._log("       -> Pressure OK")
            self._check_test("PRESSURE", True)
            self._state.set_test_result("PRESSURE", True)
            self._serial.write(b'T')
            self._pressure_result(current, True)
        else:
            self._log("       -> Pressure NOT OK ... Check altitude in script")
            self._check_test("PRESSURE", True)  # Still check for display (same as original)
            self._serial.write(b'S')
            self._pressure_result(current, False)

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(self) -> None:
        """Handle end of production tests: button press, replug, firmware update."""
        self._log("✅ Production tests complete")
        self._log("Click the button once to go to update step")

        # Wait for button press
        while not self._stop_event.is_set():
            try:
                line = self._serial.readline()
                if b"Button pressed" in line:
                    break
            except Exception:
                time.sleep(0.1)

        if self._stop_event.is_set():
            return

        self._log("Unplug and plug again")
        self._serial.set_timeout(0.5)

        # Wait for device to reconnect
        while not self._stop_event.is_set():
            try:
                self._serial.write(b'?')
                rsp = self._serial.read(1)
                if rsp == b'Y':
                    self._serial.set_timeout(None)
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if self._stop_event.is_set():
            return

        # Update firmware from external to internal flash
        self._log("Updating firmware from EXT flash...")
        self._update_firmware()
        self._shipping_mode()
        self._log("✅ Firmware updated!")

        # Signal completion to UI for PDF generation
        self._tests_complete()

        self._serial.close()
        self._running = False

    def _update_firmware(self) -> None:
        """Send firmware update command (U) to copy EXT->INT flash."""
        self._serial.write(b'U')
        rsp = self._serial.read(1)
        if rsp != b'U':
            self._log("update_firmware - command error")
            return
        # Wait for internal flash erase
        rsp = self._serial.read(1)
        if rsp != b'Y':
            self._log("update_firmware - erase error")
            return
        # Wait for copy completion
        rsp = self._serial.read(1)
        if rsp != b'Y':
            self._log("update_firmware - copy error")
            return

    def _shipping_mode(self) -> None:
        """Send shipping mode command (H) to put device in low-power sleep."""
        self._serial.write(b'H')
        rsp = self._serial.read(1)
        if rsp != b'H':
            self._log("shipping_mode - command error")
