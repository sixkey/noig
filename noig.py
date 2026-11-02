#!/usr/bin/env python3
"""
Deep brown-noise generator for Linux.

Realtime output:
    python3 brownnoise.py

Examples:
    python3 brownnoise.py --volume 0.20 --lowpass 140
    python3 brownnoise.py --preset deep
    python3 brownnoise.py --preset ocean --modulation 0.25
    python3 brownnoise.py --list-devices
    python3 brownnoise.py --device "USB Audio"

Dependencies:
    pip install numpy sounddevice
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
import threading
import time

import numpy as np
import sounddevice as sd


PRESETS = {
    "deep": dict(corner=2.5, lowpass=140.0, highpass=18.0, modulation=0.05),
    "rumble": dict(corner=4.0, lowpass=90.0, highpass=12.0, modulation=0.02),
    "balanced": dict(corner=7.0, lowpass=220.0, highpass=22.0, modulation=0.08),
    "ocean": dict(corner=3.5, lowpass=300.0, highpass=28.0, modulation=0.22),
}


class BrownNoise:
    """Stateful, block-based brown-noise generator."""

    def __init__(
        self,
        samplerate: int,
        channels: int = 2,
        corner_hz: float = 3.0,
        lowpass_hz: float = 160.0,
        highpass_hz: float = 18.0,
        seed: int | None = None,
    ):
        self.sr = float(samplerate)
        self.channels = channels
        self.rng = np.random.default_rng(seed)

        self.corner_hz = corner_hz
        self.lowpass_hz = lowpass_hz
        self.highpass_hz = highpass_hz

        self._brown = np.zeros(channels, dtype=np.float64)
        self._lp = np.zeros(channels, dtype=np.float64)
        self._hp_x = np.zeros(channels, dtype=np.float64)
        self._hp_y = np.zeros(channels, dtype=np.float64)

        self._update_coefficients()

    def _update_coefficients(self) -> None:
        # Leaky integration gives approximately 1/f^2 power density above
        # the corner frequency: the characteristic brown-noise spectrum.
        self.brown_a = math.exp(-2.0 * math.pi * self.corner_hz / self.sr)

        if self.lowpass_hz <= 0:
            self.lp_a = 0.0
        else:
            self.lp_a = math.exp(-2.0 * math.pi * self.lowpass_hz / self.sr)

        # One-pole high-pass / DC blocker.
        if self.highpass_hz <= 0:
            self.hp_a = 0.0
        else:
            self.hp_a = math.exp(-2.0 * math.pi * self.highpass_hz / self.sr)

    def generate(self, frames: int) -> np.ndarray:
        white = self.rng.standard_normal((frames, self.channels))

        out = np.empty_like(white)
        brown_a = self.brown_a

        # For y[n] = a*y[n-1] + x[n]*sqrt(1-a^2), the stationary variance
        # stays near 1, which keeps the output level predictable.
        step = math.sqrt(max(1e-12, 1.0 - brown_a * brown_a))
        state = self._brown.copy()

        for i in range(frames):
            state = brown_a * state + white[i] * step
            out[i] = state

        self._brown = state
        out *= 0.12

        if self.lowpass_hz > 0:
            a = self.lp_a
            lp = self._lp.copy()
            filtered = np.empty_like(out)
            for i in range(frames):
                lp = a * lp + (1.0 - a) * out[i]
                filtered[i] = lp
            self._lp = lp
            out = filtered

        if self.highpass_hz > 0:
            a = self.hp_a
            x_prev = self._hp_x.copy()
            y_prev = self._hp_y.copy()
            filtered = np.empty_like(out)
            for i in range(frames):
                x = out[i]
                y = a * (y_prev + x - x_prev)
                filtered[i] = y
                x_prev = x
                y_prev = y
            self._hp_x = x_prev
            self._hp_y = y_prev
            out = filtered

        return out.astype(np.float32, copy=False)


class ModulatedOutput:
    """Applies slow, smooth amplitude movement."""

    def __init__(self, noise: BrownNoise, modulation: float, seed=None):
        self.noise = noise
        self.depth = float(np.clip(modulation, 0.0, 1.0))
        self.rng = np.random.default_rng(seed)
        self.phase = self.rng.uniform(0, 2 * math.pi)
        self.rate = 0.025

    def generate(self, frames: int) -> np.ndarray:
        audio = self.noise.generate(frames)
        if self.depth <= 0:
            return audio

        t = np.arange(frames, dtype=np.float64) / self.noise.sr
        lfo = (
            0.65 * np.sin(self.phase + 2 * math.pi * self.rate * t)
            + 0.35 * np.sin(
                self.phase * 0.37 + 2 * math.pi * (self.rate * 0.61) * t
            )
        )
        gain = 1.0 - self.depth * 0.35 * (0.5 + 0.5 * lfo)
        return audio * gain[:, None]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate continuous deep brown noise on Linux.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--preset", choices=sorted(PRESETS), default="deep")
    p.add_argument("--volume", type=float, default=0.20,
                   help="output volume, 0.0 to 1.0")
    p.add_argument("--corner", type=float,
                   help="brown-noise corner frequency in Hz; lower is deeper")
    p.add_argument("--lowpass", type=float,
                   help="final low-pass cutoff in Hz; lower is darker/deeper")
    p.add_argument("--highpass", type=float,
                   help="remove subsonic/DC content below this frequency; 0 disables it")
    p.add_argument("--modulation", type=float,
                   help="slow volume movement, 0.0 to 1.0")
    p.add_argument("--samplerate", type=int, default=48000)
    p.add_argument("--blocksize", type=int, default=1024)
    p.add_argument("--channels", type=int, choices=(1, 2), default=2)
    p.add_argument("--seed", type=int,
                   help="random seed for repeatable runs")
    p.add_argument("--device", help="PortAudio output device name or numeric ID")
    p.add_argument("--list-devices", action="store_true",
                   help="list audio devices and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return 0

    if not 0.0 <= args.volume <= 1.0:
        raise SystemExit("--volume must be between 0 and 1")
    if args.corner is not None and args.corner <= 0:
        raise SystemExit("--corner must be > 0")
    if args.lowpass is not None and args.lowpass < 0:
        raise SystemExit("--lowpass must be >= 0")
    if args.highpass is not None and args.highpass < 0:
        raise SystemExit("--highpass must be >= 0")
    if args.modulation is not None and not 0.0 <= args.modulation <= 1.0:
        raise SystemExit("--modulation must be between 0 and 1")

    preset = PRESETS[args.preset].copy()
    corner = args.corner if args.corner is not None else preset["corner"]
    lowpass = args.lowpass if args.lowpass is not None else preset["lowpass"]
    highpass = args.highpass if args.highpass is not None else preset["highpass"]
    modulation = args.modulation if args.modulation is not None else preset["modulation"]

    noise = BrownNoise(
        samplerate=args.samplerate,
        channels=args.channels,
        corner_hz=corner,
        lowpass_hz=lowpass,
        highpass_hz=highpass,
        seed=args.seed,
    )
    generator = ModulatedOutput(noise, modulation, seed=args.seed)

    stop = threading.Event()

    def request_stop(signum, frame):
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    print(
        f"Brown noise: preset={args.preset}, corner={corner:g} Hz, "
        f"lowpass={lowpass:g} Hz, highpass={highpass:g} Hz, "
        f"modulation={modulation:g}"
    )
    print("Press Ctrl-C to stop.")

    def callback(outdata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        block = generator.generate(frames)
        block *= float(args.volume)
        outdata[:] = np.clip(block, -1.0, 1.0)

    try:
        with sd.OutputStream(
            samplerate=args.samplerate,
            blocksize=args.blocksize,
            device=args.device,
            channels=args.channels,
            dtype="float32",
            callback=callback,
        ):
            while not stop.is_set():
                time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    except sd.PortAudioError as exc:
        print(f"Audio error: {exc}", file=sys.stderr)
        print("Try --list-devices and then pass --device <id-or-name>.",
              file=sys.stderr)
        return 2

    print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
