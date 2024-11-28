#!/usr/bin/python3

import argparse
import pandas as pd
import pvlib
from datetime import datetime
import pytz
from tabulate import tabulate
import json
import sys
from tzlocal import get_localzone

def parse_arguments():
    parser = argparse.ArgumentParser(description='Calculate theoretical PV DC production under clear sky conditions')
    parser.add_argument('--latitude', type=float, required=True, help='Location latitude')
    parser.add_argument('--longitude', type=float, required=True, help='Location longitude')
    parser.add_argument('--system-capacity', type=float, required=True, help='System capacity in kW')
    parser.add_argument('--panel-tilt', type=float, required=True, help='Panel tilt angle in degrees')
    parser.add_argument('--panel-azimuth', type=float, required=True, help='Panel azimuth angle in degrees (180=South)')
    parser.add_argument('--timezone', type=str, help='Timezone name (default: system timezone)')
    parser.add_argument('--shortname', type=str, help='Short name identifier for the system')
    
    # Time options group
    time_group = parser.add_mutually_exclusive_group(required=True)
    time_group.add_argument('--now', action='store_true', help='Calculate for current time')
    time_group.add_argument('--time', type=str, help='Specific time in format YYYY-MM-DD HH:MM')
    time_group.add_argument('--timeframe', type=str, help='Timeframe in format YYYY-MM-DD:YYYY-MM-DD')
    
    parser.add_argument('--resolution', type=str, default='1H',
                        choices=['1min', '10min', '20min', '30min', '1H'],
                        help='Time resolution for calculations (only with --timeframe)')
    parser.add_argument('--format', type=str, choices=['table', 'json', 'prometheus'], default='table',
                        help='Output format (default: table)')
    return parser.parse_args()

def get_current_time(timezone):
    """Get current time in specified timezone"""
    return datetime.now(timezone)

def get_time_range(timeframe, resolution, timezone):
    start_date, end_date = timeframe.split(':')
    
    resolution_map = {
        '1min': 'min',
        '10min': '10min',
        '20min': '20min',
        '30min': '30min',
        '1H': 'H'
    }
    freq = resolution_map[resolution]
    
    start = pd.Timestamp(start_date).tz_localize(timezone)
    end = (pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)).tz_localize(timezone)
    return pd.date_range(start=start, end=end, freq=freq)

def calculate_production(args, timestamp):
    """Calculate PV production for a specific timestamp"""
    location = pvlib.location.Location(latitude=args.latitude, longitude=args.longitude, tz=str(args.timezone))
    
    # Convert timestamp to pandas Timestamp with timezone if needed
    if isinstance(timestamp, datetime):
        timestamp = pd.Timestamp(timestamp)
    if timestamp.tz is None:
        timestamp = timestamp.tz_localize(args.timezone)
    
    # Calculate solar position
    solar_position = location.get_solarposition(times=pd.DatetimeIndex([timestamp]))
    
    # Calculate clear sky radiation
    clearsky = location.get_clearsky(times=pd.DatetimeIndex([timestamp]))
    
    # Get plane of array irradiance
    poa_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=args.panel_tilt,
        surface_azimuth=args.panel_azimuth,
        dni=clearsky['dni'],
        ghi=clearsky['ghi'],
        dhi=clearsky['dhi'],
        solar_zenith=solar_position['apparent_zenith'],
        solar_azimuth=solar_position['azimuth']
    )
    
    # Calculate DC power
    dc_power = poa_irradiance['poa_global'] * args.system_capacity / 1000
    
    return {
        'timestamp': timestamp,
        'ghi': float(clearsky['ghi'].iloc[0]),
        'poa_irradiance': float(poa_irradiance['poa_global'].iloc[0]),
        'dc_power_kw': float(dc_power.iloc[0])
    }

def calculate_timeframe_production(args):
    """Calculate PV production for a timeframe"""
    location = pvlib.location.Location(latitude=args.latitude, longitude=args.longitude, tz=str(args.timezone))
    times = get_time_range(args.timeframe, args.resolution, args.timezone)
    
    results = []
    for timestamp in times:
        result = calculate_production(args, timestamp)
        if result['dc_power_kw'] > 0.001:  # Filter out negligible production
            results.append(result)
    
    return results

def format_table_output(data):
    """Format data as a table"""
    if isinstance(data, dict):
        return tabulate([
            ["Time", data['timestamp'].strftime('%Y-%m-%d %H:%M %Z')],
            ["DC Power", f"{data['dc_power_kw']:.2f} kW"],
            ["POA Irradiance", f"{data['poa_irradiance']:.2f} W/m²"],
            ["GHI", f"{data['ghi']:.2f} W/m²"]
        ], tablefmt="simple")
    else:
        # For timeframe data
        table_data = []
        for entry in data:
            table_data.append([
                entry['timestamp'].strftime('%Y-%m-%d %H:%M %Z'),
                f"{entry['dc_power_kw']:.2f}",
                f"{entry['poa_irradiance']:.2f}",
                f"{entry['ghi']:.2f}"
            ])
        return tabulate(table_data, 
                       headers=["Time", "DC Power (kW)", "POA Irr (W/m²)", "GHI (W/m²)"],
                       tablefmt="simple")

def format_json_output(data):
    """Format data as JSON"""
    if isinstance(data, dict):
        return json.dumps({
            'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M %Z'),
            'dc_power_kw': round(data['dc_power_kw'], 2),
            'poa_irradiance': round(data['poa_irradiance'], 2),
            'ghi': round(data['ghi'], 2)
        }, indent=2)
    else:
        # For timeframe data
        formatted_data = []
        for entry in data:
            formatted_data.append({
                'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M %Z'),
                'dc_power_kw': round(entry['dc_power_kw'], 2),
                'poa_irradiance': round(entry['poa_irradiance'], 2),
                'ghi': round(entry['ghi'], 2)
            })
        return json.dumps(formatted_data, indent=2)

def format_prometheus_output(data, args):
    """Format data as Prometheus metrics"""
    labels = [
        f'latitude="{args.latitude}"',
        f'longitude="{args.longitude}"',
        f'capacity="{args.system_capacity}"',
        f'tilt="{args.panel_tilt}"',
        f'azimuth="{args.panel_azimuth}"'
    ]
    
    if args.shortname:
        labels.append(f'shortname="{args.shortname}"')
    
    location_labels = '{' + ','.join(labels) + '}'
    
    if isinstance(data, dict):
        return f'theoretical_pv_kw{location_labels} {data["dc_power_kw"]:.2f}'
    else:
        # For timeframe data, only output the latest values
        latest = data[-1]
        return f'theoretical_pv_kw{location_labels} {latest["dc_power_kw"]:.2f}'

def main():
    args = parse_arguments()
    
    # Get system timezone if not specified
    if args.timezone is None:
        args.timezone = get_localzone()
    else:
        args.timezone = pytz.timezone(args.timezone)
    
    try:
        if args.now:
            timestamp = get_current_time(args.timezone)
            result = calculate_production(args, timestamp)
        elif args.time:
            if args.time.lower() == 'now':
                timestamp = get_current_time(args.timezone)
            else:
                timestamp = pd.Timestamp(args.time, tz=args.timezone)
            result = calculate_production(args, timestamp)
        elif args.timeframe:
            result = calculate_timeframe_production(args)
            if not result:
                print("No significant production values in the specified timeframe.")
                sys.exit(0)

        # Handle different output formats
        if args.format == 'table':
            output = format_table_output(result)
        elif args.format == 'json':
            output = format_json_output(result)
        elif args.format == 'prometheus':
            output = format_prometheus_output(result, args)
        
        print(output)
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
