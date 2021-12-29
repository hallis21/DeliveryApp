from flask.json import jsonify
from app import cache
from app import db
import json as jss
import operator
import requests as req



def create_route(orders, metadata=False, source="11.355041,59.413895"):

    
    
    
    home = source if len(source.split(",")) == 2 else "11.355041,59.413895"
    if home[-1] != ";": home += ";"


    coord_string = ";".join([f"{x.lon},{x.lat}" for x in orders if x.lat != 0.0 or x.lon != 0.0])
    coord_string = home+coord_string
    response = req.get(
        "http://router.project-osrm.org/trip/v1/driving/"+coord_string+"?source=first"+("&steps=true" if metadata else "&steps=false"))
    

    
    waypoints = response.json()["waypoints"]
    json = [x.to_geojson() for x in orders]
    first = True
    json.insert(0, None)
    for order, waypoint in zip(json, waypoints):
        if first:
            first = False
        else:
            order["properties"]["waypoint_index"] = waypoint["waypoint_index"]
    json.remove(None)
    
    
    json.sort(key=lambda k: k["properties"]["waypoint_index"])
    
    
    
    # jo = sorted(jo, key=lambda k: k)
    # for k in jo:
    #     print(k)
    
    
    to_ret = {"orders":json, "trip": response.json()["trips"][0] if metadata else []}
    # jo.sort(key=operator.itemgetter('waypoint_index'))

    return to_ret
#router.project-osrm.org/trip/v1/driving/11.355041,59.413895;11.358965957495268,59.42092907142464;11.35503962976206,59.41389385060446
