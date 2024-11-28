# PV Calculator

A Python script for calculating theoretical PV DC production under clear sky conditions. This tool uses the `pvlib` library to estimate solar panel output based on location, system specifications, and time.

## Features

- Calculate theoretical DC power output for solar PV systems
- Support for instant, specific time, and timeframe calculations
- Multiple output formats (table, JSON, Prometheus metrics)
- Timezone-aware calculations using system or specified timezone
- Configurable time resolution for timeframe calculations

## Requirements

```bash
pip install pandas pvlib pytz tabulate tzlocal
```

## Usage

### Basic Usage

```bash
./pvcalc.py --latitude <lat> --longitude <lon> --system-capacity <kW> --panel-tilt <degrees> --panel-azimuth <degrees> [options]
```

### Time Options

- Current time:
```bash
--now
# or
--time=now
```

- Specific time:
```bash
--time "2024-03-20 12:00"
```

- Time range:
```bash
--timeframe "2024-03-20:2024-03-21"
```

### Optional Parameters

- `--timezone`: Timezone name (default: system timezone)
- `--shortname`: Short identifier for the system
- `--resolution`: Time resolution for timeframe calculations (1min, 10min, 20min, 30min, 1H)
- `--format`: Output format (table, json, prometheus)

### Examples

1. Get current production in table format:
```bash
./pvcalc.py --latitude 42.804 --longitude 23.378 --system-capacity 9.2 --panel-tilt 22.0 --panel-azimuth 162.0 --now
```

2. Get production for specific time in JSON format:
```bash
./pvcalc.py --latitude 42.804 --longitude 23.378 --system-capacity 9.2 --panel-tilt 22.0 --panel-azimuth 162.0 --time "2024-03-20 12:00" --format json
```

3. Get production in Prometheus format with system identifier:
```bash
./pvcalc.py --latitude 42.804 --longitude 23.378 --system-capacity 9.2 --panel-tilt 22.0 --panel-azimuth 162.0 --now --format prometheus --shortname "system1"
```

## Output Formats

### Table Format (default)
```
Time                DC Power    POA Irr    GHI
------------------  ----------  ---------  --------
2024-03-20 12:00   5.23 kW     850 W/m²   750 W/m²
```

### JSON Format
```json
{
  "timestamp": "2024-03-20 12:00 EET",
  "dc_power_kw": 5.23,
  "poa_irradiance": 850.0,
  "ghi": 750.0
}
```

### Prometheus Format
```
theoretical_pv_kw{latitude="42.804",longitude="23.378",capacity="9.2",tilt="22.0",azimuth="162.0",shortname="system1"} 5.23
```

## Notes

- Panel azimuth angle: 180° represents South, 90° East, 270° West
- Timeframe calculations filter out negligible production values (< 0.001 kW)
- All calculations assume clear sky conditions
- Time values are timezone-aware

## License

This project is open-sourced under the MIT license.
