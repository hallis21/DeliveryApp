import re
import urllib
import requests
from shapely.geometry import Point, Polygon
from app import db
from sqlalchemy import Column, Integer, ForeignKey, String, Float, Text, Sequence, Date
from sqlalchemy.orm import relationship
from flask_login import UserMixin

"""Database db.Models

Simple relational database
"""

association_table = db.Table('association', db.Model.metadata,
                             Column('order_id', Integer,
                                       ForeignKey('order.order_nr')),
                             Column('devlist_id', Integer,
                                       ForeignKey('devlist.id'))
                             )
association_table_area = db.Table('association_area', db.Model.metadata,
                             Column('order_id', Integer,
                                    ForeignKey('order.order_nr')),
                             Column('area_id', Integer,
                                    ForeignKey('area.id'))
                             )


class Order(db.Model):
    __tablename__ = 'order'
    order_nr: str = Column(String(50), nullable=False, primary_key=True)
    day_id = Column(Integer, ForeignKey('day.id'))
    changed: int = Column(Integer, nullable=False, default=0)
    active: int = Column(Integer, nullable=False, default=1)
    c_o: str = Column(String(100), default="")
    recv: str = Column(String(100), default="")
    location: str = Column(String(100), default="")
    phone: str = Column(String(10), default="")
    time: str = Column(String(100), default="")
    type: str = Column(String(50), default="")
    lat: float = Column(Float, default=0.0)
    lon: float = Column(Float, default=0.0)
    error: str = Column(Text, default="")
    objtype: str = Column(String(50), default="")
    comment: str = Column(Text, default="")
    devlists = relationship("DevList",
                               secondary=association_table,
                               back_populates="orders")
    areas = relationship("Area",
                            secondary=association_table_area,
                            back_populates="orders")



    def __repr__(self) -> str:
        return f"{self.order_nr or ''}: {self.recv}"

    def get_point(self):
        return Point(self.lon, self.lat)

    def to_geojson(self):
        """Returns a dict, jsonify
        """
        js = {}

        devlists_dict = {}
        for list in self.devlists:
            devlists_dict[list.id] = list.name
        areas_dict = {}
        for list in self.areas:
            areas_dict[list.id] = list.name

        js["geometry"] = {"type": "Point", "coordinates": [self.lon, self.lat]}
        js["properties"] = {"c_o": self.c_o, "recv": self.recv,
                            "location": self.location, "phone": self.phone, "time": self.time, "type": self.type,
                            "objtype": self.objtype, "error": self.error, "order_number": self.order_nr, "active": self.active, "devlist": devlists_dict, "areas": areas_dict, "day_id":self.day_id}
        js["properties"]["comment"] = self.comment
        js["type"] = "Feature"

        return js

    def parse_address(self):
        try:
            if self.location == "":
                self.error = "noLocation"
                return
            # Replace
            rep = {r"vn.": "veien ", r"gt.": "gate ", r"/skrk[^/w]": "kirke "}
            for r, rr in rep.items():
                self.location = re.sub(r, rr, self.location)
            base_url = "https://ws.geonorge.no/adresser/v1/sok?sok="
            base_opts = "&sokemodus=AND&treffPerSide=10&side=0&asciiKompatibel=true"
            if re.search("(?i)[rakkestad|degernes|eidsberg|indre østfold|indre ostfold|mysen|aremark|halden|ørje|orje]", self.location) == None:
                base_opts += "&kommunenavn=RAKKESTAD"
            sok = urllib.parse.quote_plus(self.location)
            url = base_url+sok+base_opts

            response = requests.get(url)

            if response.status_code != 200:
                self.error = "reqError"
                return

            rjson = response.json()

            if int(rjson["metadata"]["totaltAntallTreff"]) == 0:

                if "skautun" in self.location.lower() or "skautun" in self.c_o.lower():
                    self.comment += "\n" if self.comment else "" +"Old loc: "+self.location
                    self.location = "Granveien 11, Rakkestad"
                    self.error = ""
                    self.parse_address()
                    return

                if re.search(r"(?!\s)(\d+)?\s(\w)", self.location.lower()) != None:
                    self.location = re.sub(r"(?!\s)(\d+)?\s(\w)", r"\g<1>\g<2>", self.location.lower())
                    self.parse_address()
                    return

                if "aa" in self.location.lower():
                    self.location = self.location.lower().replace("aa", "å")
                    self.error = ""
                    self.parse_address()
                    return
                if "oe" in self.location.lower():
                    self.location = self.location.lower().replace("oe", "ø")
                    self.error = ""
                    self.parse_address()
                    return
                if "ae" in self.location.lower():
                    self.location = self.location.lower().replace("ae", "æ")
                    self.error = ""
                    self.parse_address()
                    return
                self.error = "noMatch"
                self.lat = 0.0
                self.lon = 0.0
                return
            if int(rjson["metadata"]["totaltAntallTreff"]) > 1:
                if int(rjson["metadata"]["totaltAntallTreff"]) > 10:
                    self.error = "toMany "+str(rjson["metadata"]["totaltAntallTreff"])

            # Else parse første

            address = rjson["adresser"][0]
            loc_data = address["representasjonspunkt"]
            self.lat = float(loc_data["lat"])
            self.lon = float(loc_data["lon"])
            self.objtype = address["objtype"]

        except Exception as identifier:
            #TODO: Seperate exceptions
            pass
        finally:
            db.session.commit()


class DevList(db.Model):
    __tablename__ = 'devlist'
    id: int = Column(Integer, Sequence(
        'devlist_id_seq'), primary_key=True)
    name: str = Column(String(100))
    comment: str = Column(Text)
    orders = relationship("Order",
                             secondary=association_table,
                             back_populates="devlists")
    def __repr__(self) -> str:
        return f"{self.name}: {len(self.orders)}"


class Area(db.Model):
    __tablename__ = 'area'
    id: int = Column(Integer, Sequence(
        'area_id_seq'), primary_key=True)
    name: str = Column(String(100), unique=True)
    points: str = Column(Text, nullable=False)
    orders = relationship("Order",
                          secondary=association_table_area,
                          back_populates="areas")
    
    def get_polygon(self):
        point_list = [[float(y) for y in x.split(",")] for x in self.points.split(";")]
        return Polygon(point_list)

    def get_points(self):
        return [[float(y) for y in x.split(",")] for x in self.points.split(";")]

        
    def check_all_within(self):
        orders = Order.query.all()
        poly = self.get_polygon()
        for order in orders:
            if poly.contains(order.get_point()) and order not in self.orders:
                self.orders.append(order)
    

    def from_geojson(json):
        """Needs a dictionary

        Standard output from json POST
        """
        name = json["properties"]["name"] if json["properties"] else ""
        points_js = json["geometry"]["coordinates"] if json["geometry"] else ""
        points = []
        for p in points_js[0]:
            lat = float(p[0])
            lon = float(p[1])
            points.append([lat, lon])
        return Area.add_area(name, points)


    def add_area(name, point_list):
        """

        Not try-catched
        """

        # Point list: [(x,y), (x,y)]
        new_area = Area(name=name)
        point_string = ";".join([",".join([str(y) for y in x]) for x in point_list])
        new_area.points = point_string
        db.session.add(new_area)
        new_area.check_all_within()
        db.session.commit()
        return new_area
    
    def to_geojson(self):
        js = {}
        js["properties"] = {}
        js["properties"]["name"] = self.name

        js["type"] = "Feature"

        js["geometry"] = {"type": "Polygon", "coordinates": [[[x[0], x[1]] for x in self.get_points()]]
                          }

        return js


    def __repr__(self) -> str:
        return f"Area: {self.name} {len(self.orders)}"

    def __eq__(self, o: object) -> bool:
        return o == self.id or o == self.name


class Day(db.Model):
    __tablename__ = "day"
    id = Column(Integer, Sequence('day_id_seq'), primary_key=True)
    name = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    orders = relationship("Order")

    def __repr__(self) -> str:
        return f"Day: {self.name}: {len(self.orders)}"
    def __eq__(self, o: object) -> bool:
        return o == self.id

    def json(self):
        return {"id":self.id, "name":self.name, "date":str(self.date), "orders":len([x for x in self.orders if x.active==1]), "active_orders":len([x for x in self.orders if x.active ==1])}


class User(UserMixin, db.Model):
    # primary keys are required by SQLAlchemy
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
