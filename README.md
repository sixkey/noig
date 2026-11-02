# Deep Brown Noise for Linux

A small command-line brown-noise generator for Linux. It produces
continuous real-time audio through PortAudio using Python, NumPy, and
`sounddevice`.

The generator is designed for a **deep, dark, low-frequency sound**
rather than ordinary broadband brown noise. It includes several presets,
adjustable filtering, optional slow amplitude modulation, stereo/mono
output, repeatable random seeds, and audio-device selection.

## Features

-   Real-time continuous brown-noise generation
-   Deep/dark filtering suitable for background sound, sleep, focus, or
    masking
-   Four built-in presets:
    -   `deep` --- default, deep and dark
    -   `rumble` --- lower and heavier
    -   `balanced` --- broader spectrum
    -   `ocean` --- more slowly evolving
-   Adjustable:
    -   brown-noise corner frequency
    -   low-pass cutoff
    -   high-pass/DC filtering
    -   slow amplitude modulation
    -   output volume
    -   sample rate
    -   block size
    -   mono/stereo channels
-   Select a PortAudio output device by name or ID
-   `--list-devices` for discovering available audio outputs
-   Optional deterministic output with `--seed`

## Requirements

-   Linux
-   Python 3.10+ recommended
-   NumPy
-   `sounddevice`
-   A working PortAudio-compatible audio output

The Python dependencies can be installed with:

``` bash
python3 -m pip install numpy sounddevice
```

On Debian/Ubuntu, you may also need the PortAudio runtime library:

``` bash
sudo apt install libportaudio2
```

If your distribution packages `python3-sounddevice`, you can use that
instead of installing the Python package with `pip`.

## Installation

Clone or copy `noig.py` into a directory of your choice.

For an isolated Python environment:

``` bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install numpy sounddevice
```

Then make the script executable:

``` bash
chmod +x noig.py
```

## Basic usage

Start the default deep preset:

``` bash
./noig.py
```

Stop playback with `Ctrl-C`.

The script prints the active parameters when it starts.

You can also run it explicitly with Python:

``` bash
python3 noig.py
```

## Presets

### Deep

The default preset. Low and dark without being excessively subsonic.

``` bash
./noig.py --preset deep
```

### Rumble

A darker, heavier sound with a lower low-pass cutoff.

``` bash
./noig.py --preset rumble
```

### Balanced

A little more high-frequency content while retaining the brown-noise
character.

``` bash
./noig.py --preset balanced
```

### Ocean

Adds stronger slow amplitude movement to make the sound less static.

``` bash
./noig.py --preset ocean
```

## Examples

Quiet, deep background noise:

``` bash
./noig.py --preset deep --volume 0.12
```

Extra-dark rumble:

``` bash
./noig.py \
    --corner 2 \
    --lowpass 100 \
    --highpass 15 \
    --volume 0.15
```

Slowly evolving sound:

``` bash
./noig.py --preset ocean --modulation 0.25
```

Mono output:

``` bash
./noig.py --channels 1
```

Use a fixed random seed:

``` bash
./noig.py --seed 1234
```

A fixed seed makes the generated sequence repeatable for the same
settings and runtime conditions.

## Audio devices

List available PortAudio devices:

``` bash
./noig.py --list-devices
```

You can then select an output device by numeric ID or name:

``` bash
./noig.py --device 3
```

or:

``` bash
./noig.py --device "USB Audio"
```

If playback fails with a PortAudio error, run `--list-devices` first and
choose an appropriate output device.

## Command-line options

Run:

``` bash
./noig.py --help
```

Available options:

  -----------------------------------------------------------------------------
  Option                                    Description
  ----------------------------------------- -----------------------------------
  `--preset {balanced,deep,ocean,rumble}`   Starting preset

  `--volume 0.0..1.0`                       Output volume

  `--corner HZ`                             Brown-noise corner frequency; lower
                                            values sound deeper

  `--lowpass HZ`                            Final low-pass cutoff; lower values
                                            sound darker

  `--highpass HZ`                           Removes DC/subsonic content; `0`
                                            disables it

  `--modulation 0.0..1.0`                   Slow amplitude movement

  `--samplerate HZ`                         Audio sample rate; default is
                                            `48000`

  `--blocksize FRAMES`                      Audio callback block size; default
                                            is `1024`

  `--channels {1,2}`                        Mono or stereo output

  `--seed INTEGER`                          Random seed

  `--device DEVICE`                         PortAudio device name or numeric ID

  `--list-devices`                          List devices and exit
  -----------------------------------------------------------------------------

### Overriding a preset

A preset supplies defaults, but individual parameters can be overridden:

``` bash
./noig.py \
    --preset deep \
    --lowpass 90 \
    --highpass 12 \
    --volume 0.10
```

## How it works

The generator starts with Gaussian white noise and feeds it through a
**leaky Brownian integrator**. This produces the characteristic
approximately `1/f²` power-density behavior associated with brown noise
over the useful part of the spectrum.

It then applies:

1.  A low-pass filter to emphasize the deep portion of the spectrum.
2.  A one-pole high-pass/DC blocker to prevent excessive DC and subsonic
    drift.
3.  Optional slow amplitude modulation for a more naturally evolving
    sound.
4.  A final volume adjustment before sending floating-point samples to
    PortAudio.

The noise state is maintained between audio blocks, so playback remains
continuous rather than restarting the filter at every callback.

## Tuning the sound

The most useful parameters for making the sound deeper are:

### `--corner`

Lower values emphasize slower variations:

``` bash
./noig.py --corner 2
```

### `--lowpass`

Lower values remove more high-frequency content:

``` bash
./noig.py --lowpass 100
```

For a very dark sound:

``` bash
./noig.py --corner 2 --lowpass 80
```

### `--highpass`

This controls the removal of very low-frequency/DC content. A small
value such as `12`--`20 Hz` is useful for keeping the signal from
accumulating excessive subsonic energy:

``` bash
./noig.py --highpass 15
```

Set it to zero if you deliberately want to disable this filtering:

``` bash
./noig.py --highpass 0
```

Be careful with very low frequencies and high playback levels,
especially with headphones or speakers that can reproduce substantial
sub-bass.

### `--modulation`

This adds slow volume movement:

``` bash
./noig.py --modulation 0.20
```

Use `0` for a static level.

## Performance

The generator works in real time and processes audio in blocks. A
default block size of `1024` frames at `48 kHz` provides roughly 21 ms
of audio per callback.

If you experience audio dropouts, try a larger block size:

``` bash
./noig.py --blocksize 2048
```

If your audio system is stable and you want lower callback latency, a
smaller value may work:

``` bash
./noig.py --blocksize 512
```

The script prioritizes simplicity and portability over highly optimized
DSP. For a typical desktop Linux system, the workload should be modest.

## Troubleshooting

### `ModuleNotFoundError: No module named 'numpy'`

Install NumPy:

``` bash
python3 -m pip install numpy
```

### `ModuleNotFoundError: No module named 'sounddevice'`

Install `sounddevice`:

``` bash
python3 -m pip install sounddevice
```

### PortAudio errors

First list the available devices:

``` bash
./noig.py --list-devices
```

Then explicitly select the desired output:

``` bash
./noig.py --device 3
```

If PortAudio itself is missing, install your distribution's PortAudio
runtime/development packages. On Debian/Ubuntu, for example:

``` bash
sudo apt install libportaudio2
```

### Audio dropouts or underruns

Try increasing the block size:

``` bash
./noig.py --blocksize 2048
```

Also check that the selected output device is available and that the
system is not under unusually heavy CPU load.

## Safety

This program generates continuous audio and can produce substantial
low-frequency energy. Start at a low volume and increase it gradually.

Do not use high volume for extended periods. Very low frequencies can
also cause unexpected movement or distortion in speakers that are not
designed for sub-bass reproduction.

## Project structure

The project is intentionally small:

``` text
.
└── noig.py
```

The main components are:

-   `BrownNoise` --- stateful brown-noise and filtering engine
-   `ModulatedOutput` --- optional slow amplitude modulation
-   `PRESETS` --- built-in sound profiles
-   CLI argument parsing and PortAudio output in `main()`

## License

No license is currently specified for this project. Add a license file
if you plan to distribute or publish it.
