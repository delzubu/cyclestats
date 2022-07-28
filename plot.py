from datetime import timedelta
import gpxpy
import gpxpy.gpx

import pandas as pd
import matplotlib.pyplot as plt
import sys
from pathlib import Path
import haversine as hs

import folium
import pandas as pd
from IPython.display import display
 
def calc_distance(p, pp):
    if(pp == 0):
        return 0
    else:  
        # print(pp)
        d = hs.haversine(
            point1=(pp['latitude'], pp['longitude']),
            point2=(p['latitude'], p['longitude']),
            unit=hs.Unit.METERS
        )
        # print(d)
        return d

def calc_time(p, pp):
    if(pp == 0):
        return timedelta()
    else:  
        return p['time']-pp['time']


def calc_elevation(p, pp):
    if(pp == 0):
        return 0
    else:  
        return p['elevation']-pp['elevation']


def calc_speed(p,pp):
    if(pp == 0):
        return 0
    else:  
        return p['d_distance'] / p['d_time'].total_seconds()*3.6

def process_gpx(gpx):
    route_info = []
    pastPoint = 0

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point = {
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'elevation': point.elevation,
                    'time': point.time           
                };
                point['d_distance'] = calc_distance(point, pastPoint)
                point['d_time'] = calc_time(point, pastPoint)
                point['d_elevation'] = calc_elevation(point, pastPoint)
                point['d_speed'] = calc_speed(point, pastPoint)
                route_info.append(point)
                pastPoint = point
    return route_info

def aggregate_by_minute(source_info, timespan):
    acc = 0
    result = []

    for p in source_info:
        if acc == 0:
            acc = {
                'time': p['time'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
                'd_distance': p['d_distance'],
                'd_time': p['d_time'],
                'd_elevation': 0
            }
        else:
            acc['d_distance'] += p['d_distance']
            acc['d_time'] += p['d_time']
            acc['d_elevation'] += p['d_elevation']
            acc['latitude_end'] = p['latitude']
            acc['longitude_end'] = p['longitude']

        if acc['d_time'].total_seconds() >= timespan*60:
            acc['d_speed'] = calc_speed(acc, acc)
            result.append(acc)
            acc = 0

    if acc != 0:
        acc['d_speed'] = calc_speed(acc, acc)
        result.append(acc)
    return result

def aggregate_by_km(source_info, distance):
    acc = 0
    result = []

    for p in source_info:
        if acc == 0:
            acc = {
                'time': p['time'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
                'latitude_end': p['latitude'],
                'longitude_end': p['longitude'],
                'd_distance': 0,
                'd_time': p['d_time'],
                'd_elevation': 0
            }
        else:
            acc['d_distance'] += p['d_distance']
            acc['d_time'] += p['d_time']
            acc['d_elevation'] += p['d_elevation']
            acc['latitude_end'] = p['latitude']
            acc['longitude_end'] = p['longitude']

        if acc['d_distance'] >= distance*1000:
            acc['d_speed'] = calc_speed(acc, acc)
            result.append(acc)
            acc = 0

    if acc != 0:
        acc['d_speed'] = calc_speed(acc, acc)
        result.append(acc)
    return result

def plot_data(dataframe, fn):
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.figure(figsize=(14, 8))
    plt.scatter(dataframe['longitude'], dataframe['latitude'], color='#101010')
    plt.title(fn, size=20);
    plt.savefig(fn + '.png')  

def init_map(dataframe):
    return folium.Map(
        location=(dataframe['latitude'].mean(), dataframe['longitude'].mean()),
        zoom_start=12,
        tiles='OpenStreetMap',
        width=1024,
        height=600
    )

def plot_map_poly(map, dataframe, weight = 2):
    coordinates = [tuple(x) for x in dataframe[['latitude', 'longitude']].to_numpy()]
    folium.PolyLine(coordinates, weight=weight).add_to(map)

def timedelta_str(td):
    mm, ss = divmod(td.total_seconds(), 60)
    hh, mm = divmod(mm, 60)
    return "%d:%02d:%02d" % (hh, mm, ss)

def plot_map_marker(map, dataframe, radius = 3):
    i=0
    for _, row in dataframe.iterrows():
        i=i+1

        folium.CircleMarker(
            location=[row['latitude_end'], row['longitude_end']],
            radius=radius,
            tooltip="Lap " + str(i) + 
                "<br />Distance: " + str(round(row['d_distance']/1000,2)) +
                "<br />Elevation: " + str(round(row['d_elevation'],0)) +
                "<br />Lap time: " + timedelta_str(row['d_time'])+
                "<br />Speed: " + str(round(row['d_speed'],1)) +
                ""
        ).add_to(map)


def add_gpx_stats(stats, gpx):
    stats['Date'] = str(gpx.get_time_bounds().start_time.date())
    stats['Name'] = gpx.name

def add_route_stats(stats, df):
    stats['Km'] = round(df['d_distance'].sum()/1000,2)
    stats['Tour Duration'] = timedelta_str(df['d_time'].sum())
    stats['Tour Avg'] = round(df['d_distance'].sum() / df['d_time'].sum().total_seconds() * 3.6, 1);
    stats['Max'] = round(df['d_speed'].max(), 1);

def add_route_stats_aggr(stats, df):
    stats['Lap Best'] = round(df['d_speed'].max(), 1);

def main():
    fn = ""
    aggregated = 0
    stats = {}

    if(len(sys.argv) > 1):
        fn = Path(sys.argv[1]).stem
    else:
        fn = "2022-07-11_839902350_Kalcreuth 34km";

    if(len(sys.argv) > 3):
        if(sys.argv[2].upper() == "-T"):
                aggregate_func = lambda route: aggregate_by_minute(route, int(sys.argv[3]))
                aggregated = 1
        elif(sys.argv[2].upper() == "-D"):
                aggregate_func = lambda route: aggregate_by_km(route, int(sys.argv[3]))
                aggregated = 1


    # read gpx
    with open(fn+'.gpx', 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    add_gpx_stats(stats, gpx)

    #Parse route
    route = process_gpx(gpx);

    # Draw route map
    route_df = pd.DataFrame(route)
    add_route_stats(stats, route_df)

    map = init_map(route_df)
    plot_map_poly(map, route_df, 2)

    # If map need to be aggregated
    if aggregated == 1:
        route = aggregate_func(route)
        route_df = pd.DataFrame(route)
        plot_map_marker(map, route_df)

    add_route_stats_aggr(stats, route_df)

    # Export data frame to CSV
    route_df.to_csv(fn+'.csv', index=False)
    map.save(fn+".html")

    print(stats)

if __name__ == "__main__":
    main()