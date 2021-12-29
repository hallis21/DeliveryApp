import urllib
import requests as req
import re
from app import cache
import json
from shapely.geometry import Point, Polygon
from app import db
from app import models


class Order():
    def __init__(self, c_o, recv, order_number, location, phone, time, type, latlng=None, active=True):
        self.c_o = c_o
        self.recv = recv
        self.order_number = order_number
        self.location = location
        self.phone = phone
        self.time = time
        self.type = type
        self.objtype = None
        self.latlng = latlng
        self.error = False
        self.found_multi = False
        self.found = []
        self.areaGroups = []
        self.comment = ""
        self.active = active
        if self.latlng == None:
            self.parse_address()
        if not self.error:
            self.checkArea()
        self.dev_list = None

    def parse_address(self, force=False):
        try:
            if self.location == "":
                self.error = True
                return
            # Replace
            rep = {r"vn.": "veien", r"gt.": "gate", r"/skrk[^/w]": "kirke"}
            for r, rr in rep.items():
                self.location = re.sub(r, rr, self.location)
            base_url = "https://ws.geonorge.no/adresser/v1/sok?sok="
            base_opts = "&sokemodus=AND&treffPerSide=10&side=0&asciiKompatibel=true"
            if re.search("(?i)[rakkestad|degernes|eidsberg|indre østfold|indre ostfold|aremark|halden|ørje|orje]", self.location) == None:
                base_opts += "&kommunenavn=RAKKESTAD"
            sok = urllib.parse.quote_plus(self.location)
            url = base_url+sok+base_opts

            response = req.get(url)

            if response.status_code != 200:
                self.error = "reqError"
                return

            rjson = response.json()

            if int(rjson["metadata"]["totaltAntallTreff"]) == 0:
                if "aa" in self.location.lower():
                    self.location = self.location.lower().replace("aa", "å")
                    self.parse_address()
                    return
                if "oe" in self.location.lower():
                    self.location = self.location.lower().replace("oe", "ø")
                    self.parse_address()
                    return
                if "ae" in self.location.lower():
                    self.location = self.location.lower().replace("ae", "æ")
                    self.parse_address()
                    return
                self.error = "noMatch"
                self.latlng = Point(0, 0)
                return
            if int(rjson["metadata"]["totaltAntallTreff"]) > 1:
                if int(rjson["metadata"]["totaltAntallTreff"]) > 10:
                    self.error = "toMany"
                    self.latlng = Point(0, 0)
                    return
                # if more than one address is found, store all and promt user
                # max 10 parsed
                self.found_multi = True
                for address in rjson["adresser"]:

                    loc_data = address["representasjonspunkt"]
                    self.found.append(
                        (loc_data["lon"], loc_data["lat"], address["objtype"]))

            # Else parse one address

            address = rjson["adresser"][0]
            loc_data = address["representasjonspunkt"]
            self.latlng = Point(
                float(loc_data["lon"]), float(loc_data["lat"]))
            self.objtype = address["objtype"]

        except Exception as e:
            print(self.location)
            print(e)
            self.latlng = Point(0, 0)
            self.error = "exception: "+str(e)

    def to_geojson(self):
        """Returns a dict, jsonify
        """
        js = {}
        if self.latlng:
            coords = [self.latlng.coords[0][0], self.latlng.coords[0][1]]
        else:
            coords = [0, 0]
        js["geometry"] = {"type": "Point", "coordinates": coords}
        js["properties"] = {"c_o": self.c_o, "recv": self.recv,
                            "location": self.location, "phone": self.phone, "time": self.time, "type": self.type,
                            "objtype": self.objtype, "error": self.error, "areaGroups": self.areaGroups, "order_number": self.order_number, "active":self.active, "dev_list":self.dev_list or ""}
        js["properties"]["comment"] = self.comment
        js["type"] = "Feature"

        return js

    def checkArea(self):
        if (cache.get("areaContainer") is None):
            return
        areas = cache.get("areaContainer").check_within(self)
        self.areaGroups = [x.name for x in areas]
        # Get areaContainer and check within
        # add bijective refrence
        pass


class Area:
    def __init__(self, name, points):
        self.name = name
        self.orders = []
        self.points = points
        self.poly = Polygon(points)

    def to_geojson(self):
        """Returns a dict, jsonify
        """
        js = {}
        js["properties"] = {}
        js["properties"]["name"] = self.name

        js["type"] = "Feature"

        js["geometry"] = {"type": "Polygon", "coordinates": [[[x.coords[0][0], x.coords[0][1]] for x in self.points]]
                          }

        return js

    def from_geo_json(geojson):
        """Returns a list of Areas
        Can handle feature and FeatureCollection
        Needs ["properties"]["name"] and ["geometry"]["coordinates"]
        """
        try:
            js = json.loads(geojson)

            def _singular(js):
                name = js["properties"]["name"] if js["properties"] else ""
                points_js = js["geometry"]["coordinates"] if js["geometry"] else ""
                points = []
                for p in points_js[0]:
                    lat = float(p[0])
                    lon = float(p[1])
                    points.append(Point(lat, lon))
                return Area(name, points)

            areas = []
            if js["type"] == "FeatureCollection":
                names = []
                for feat in js["features"]:
                    if feat["properties"]["name"] not in names:
                        areas.append(_singular(feat))
                        names.append(feat["properties"]["name"])

            elif js["type"] == "Feature":
                areas.append(_singular(js))

            return areas
        except Exception:
            return []


class AreaContainer:

    def __init__(self):
        self.areas = {}
        self.loadAreas()

    def exists(self, string):
        for a in self.areas.keys():
            if a.lower() == string.lower():
                return True
        return False

    def loadAreas(self):
        self.areas = {}

        areas_db = models.Area.query.all()

        for area in areas_db:
            p = area.points
            new_points = [Point(x.lat, x.lon) for x in p]
            new_points.append(new_points[0])
            new_area = Area(area.name, new_points)
            self.areas[area.name] = new_area

    def to_geojson(self):
        """List
        """
        return [self.areas[x].to_geojson() for x in self.areas.keys()]

    def add_area_geojson(self, json):
        areas = Area.from_geo_json(json)
        d = {}
        self.addAreas(a.name, areas)
        for a in areas:
            d[a.name:a]
        self.areas.extend(d)
        return len(d)

    def addAreas(self, areas):
        new_db_area = []
        for a in areas:
            points_db = [models.Point(
                lat=x.coords[0][0], lon=x.coords[0][1],  area_name=a.name) for x in a.points[:-1]]
            new_db_area = models.Area(name=a.name)
            new_db_area.points.extend(points_db)
        db.session.add(new_db_area)
        db.session.commit()
        self.loadAreas()

    def addArea(self, name, points):

        print(f"adding {name}")
        if len(points) < 2:
            print("too few points min 3")
            return
        if type(points[0]) == Point:
            points_db = [models.Point(lat=x.coords[0][0], lon=x.coords[0][1],  area_name=name)
                         for x in points[:-1]]
        else:
            # Tuple
            points_db = [models.Point(
                lat=x[0], lon=x[1],  area_name=name) for x in points[:-1]]

        new_db_area = models.Area(name=name)
        new_db_area.points.extend(points_db)
        db.session.add(new_db_area)
        db.session.commit()
        self.loadAreas()

    def check_within(self, order):
        areas_within = []
        for area in self.areas.values():
            if order.latlng.within(area.poly):
                areas_within.append(area)
        return areas_within

    # DEBUG - ikke bruk i faktisk kjøring

    def del_all():
        current_db_sessions = db.session
        for p in models.Point.query.all():
            current_db_sessions = db.object_session(p)
            current_db_sessions.delete(p)
        for p in models.Area.query.all():
            current_db_sessions = db.object_session(p)
            current_db_sessions.delete(p)
        current_db_sessions.commit()

    def init_area_db(self):
        with open("app/order_obj/area_obj.json") as f:
            areas = Area.from_geo_json(f.read())
            for a in areas:
                self.addArea(a.name, a.points)



class DevList():
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc
        self.orders = []

    def add_order(self, order):
        pass
