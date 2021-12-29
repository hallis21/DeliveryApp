
# from app.order_obj.order_objects import DevList
from flask import render_template, request, flash, redirect, url_for, flash
from flask import Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from flask.helpers import make_response
import datetime
from flask_login import login_user, login_required, current_user, logout_user

from sqlalchemy.orm import session
# from collections import defaultdict

from app import app, db, models
from app.parser import parse_orders
from app.routeplanner import create_route

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)



@main.route('/')
def index():
    return render_template('index.html')


@auth.route('/add')
@login_required
def add():
    return render_template('add.html')


routes = {}


@auth.route('/route')
@login_required
def route():
    day = request.args.get('day', default=0, type=int)
    s = {}
    if day in routes:
        print("yo")
        s = routes[day]
    else:
        s = api_route(internal=True, day=day)
        routes[day] = s
    point = {"type": "FeatureCollection"}
    point["features"] = s["orders"] if "orders" in s else []
    point["excluded"] = s["excluded"] if "excluded" in s else []
    return render_template('route.html', route=point)


@main.route('/about')
def about():
    return render_template('about.html')


@auth.route('/map')
@login_required
def map():
    parse_orders()
    # day = models.Day.
    # day_db = models.Day.query.filter(models.Day.date == datetime.datetime.today().date()).first()
    orders = [x for x in models.Order.query.all()]
    # for order in orders:
    #     if order.day_id == day_db.ID:
    #         orders.remove(order)
            
    nodes = [x.to_geojson() for x in orders]
    # ac = cache.get("areaContainer")
    point = {"type": "FeatureCollection"}
    point["features"] = nodes

    areas = {"type": "FeatureCollection"}
    areas["features"] = {}
    return render_template('map.html', routeString=point, areas=areas)




# API

@auth.route('/api/orders')
@login_required
def api_orders():
    # Area can be name and id
    # Days are id-bases, use 0 for today
    # True or false
    area = request.args.get('area', default=None, type=str)
    day = request.args.get('day', default=None, type=str)
    active = request.args.get('active', default="true", type=str)
    day_list = [int(x) for x in day.split(";")] if day else []
    try:
        parse_orders()

        if 0 in day_list:
            day_db = models.Day.query.filter(models.Day.date == datetime.datetime.today().date()).first()
            if day_db != None:
                day_list.append(day_db.id)
                day_list.remove(0)
            else:
                return make_response({"orders": [], "metadata": {"args": {"area": area or "Any", "day": day or "Any", "active": active},
                                                                 "found": 0,
                                                                 "error": "No orders for date (today) / Date does not exist"}}, 404)




        orders = [x for x in models.Order.query.all()]
        to_remove = set()
        for order in orders:
            if area:
                if area not in order.areas:
                    to_remove.add(order)
            if day:
                if order.day_id not in day_list:
                    to_remove.add(order)
            if active.lower() == "true":
                if 1 != order.active:
                    to_remove.add(order)
        for x in to_remove:
            orders.remove(x)
            
        to_ret = {"orders":[x.to_geojson() for x in orders]} #, "metadata": {"args":{"area":area or "Any", "day":day or "Any", "active":active},
                                                              #          "found":len(orders),
                                                               #         "error":"none"}}

        return make_response(to_ret, 200)




    except Exception as e:
        return make_response({"orders": [], "metadata": {"args": {"area": area or "Any", "day": day or "Any", "active": active},
                                                                                     "found": 0,
                                                                                     "error": str(e)}}, 404)
    

# @app.route("/api/areas")
# def api_areas():
#     ac = cache.get("areaContainer")
#     return make_response({"areas": [x.to_geojson() for x in models.Area.query.all()]}, 200)


@auth.route('/api/days')
@login_required
def api_days():
    parse_orders()
    return make_response({"days": [x.json() for x in models.Day.query.all()]}, 200)


@auth.route('/api/route')
@login_required
def api_route(internal=False, day=0):
    try:
        
        if not internal:
            day = request.args.get('day', default=None, type=int)
            area = request.args.get('area_id', default=None, type=str)
            order_number = request.args.get('order_number', default=None, type=str)
            steps = request.args.get('trip', default=False, type=bool)
            start = request.args.get('start', default="", type=str)
        else:
            day = day
            area = None
            order_number = None
            steps = False
            start = ""


        if area == None and order_number == None and day == None:
            return make_response({"error":"area_id or order_number must be specified"}, 404)
        if area != None: areas = [x.lower() for x in area.split(",")]
        else: areas = []
        if order_number != None: nums = order_number.split(',')
        else: nums = []
        # Additive, if area and num are given, show all from area + specified nodes
        # default day is the current day / or first day with orders
        parse_orders()
        orders = set()
        for nr in nums:
            orders.update(models.Order.query.filter_by(order_nr=nr).all())
        if day != "None":
            orders.update(models.Order.query.filter_by(day_id=day).all())
        for area_id in areas:
            for ass in models.association_table_area.query.filter_by(id=area_id).all():
                if day:
                    orders.add(models.Order.query.filter_by(
                        order_nr=ass.order_id, day_id=day).first())
                else:
                    orders.add(models.Order.query.filter_by(order_nr=ass.order_id).first())
        
        route = create_route([z for z in orders if z.error == ""], steps, start)
        route["excluded"] = [z.to_geojson() for z in orders if z.error != ""]
        if internal:
            return route
        return make_response(route, 200)
    except Exception as e:
        if internal:
            return {}
        return make_response({"status":"error occured", "er":str(e)}, 400)


@auth.route("/api/update_order", methods=["POST"])
@login_required
def update_order():
    pass


@auth.route("/api/add/area", methods=["POST"])
@login_required
def add_area():
    try:
        json = request.json
        new_area = models.Area.from_geojson(json)
        return make_response({"response": "ok", "added":new_area.name}, 202)
    except:
        return make_response({"error": "Error occured, 0 areas added", "post_structure": "follow geojson structure for Feature. Must be sent as a json POST"}, 400)


@auth.route("/api/add/order", methods=["POST"])
@login_required
def add_order():
    
    
    print(request)
    try:
        
        json = request.get_json(force=True)
        print(json)
        new_nr = 0
        for order in models.Order.query.all():
            if order.order_nr[0] == "C":
                if int(order.order_nr[1:]) >= new_nr:
                    new_nr = int(order.order_nr[1:])+1
                    # new_nr = str(new_nr)
        new_order = models.Order(order_nr="C"+str(new_nr))
        
        new_order.day_id = json["day_id"] or "0"
        new_order.c_o = ""
        new_order.recv = json["recv"] or ""
        new_order.location = json["location"] or ""
        new_order.phone = json["phone"] or "000"
        new_order.time = ""
        new_order.type = ""
        new_order.comment = ""

        db.session.add(new_order)
        db.session.commit()
        new_order.parse_address()
        
        if new_order.day_id in routes:
            del routes[new_order.day_id]
        if new_order.error != "":
            return make_response({"response": "ok", "added": new_order.recv+": "+new_order.location, "order_nr": new_order.order_nr, "error": "No gps match was found"}, 207)



        return make_response({"response": "ok", "added": new_order.recv+": "+new_order.location, "order_nr":new_order.order_nr}, 202)
    except:
        return make_response({"error": "Error occured, no order added", "params": "day_id, c_o, recv, location, phone, time, type, comment"}, 400)


@auth.route("/api/update/order/day", methods=["POST"])
@login_required
def change_day():
    # try:
        jss = request.get_json(force=True)
        order_nr = jss["order_nr"]
        old_day = jss["old_day"]
        new_day = jss["new_day"]
        order_number = [x for x in order_nr.split(",")]
        
        results = db.session.query(models.Order).filter(
            models.Order.order_nr.in_(set(order_number)))

        results.update({"day_id":new_day})
        db.session.commit()
        if new_day in routes:
            del routes[new_day]
        if old_day in routes:
            del routes[old_day]


        return make_response({"response": "OK"})
    # except:
        # return make_response({"response": "Not ok"}, 400)


@auth.route("/api/remove/order", methods=["POST"])
@login_required
def remove_order():
    try:
        order_nr = request.json["order_nr"]
        order = models.Order.query.filter_by(order_nr=order_nr).first()
        day = order.day_id
        
        if order != None:
            current_db_sessions = db.object_session(order)
            current_db_sessions.delete(order)
            current_db_sessions.commit()
            if day in routes:
                del routes[day]
            return make_response({"response": "OK", "order_nr":order_nr})
        else:
            return make_response({"response":"order not found", "order_nr":order_nr})
    except:
        return make_response({"response": "an error occured", "order_nr": "not found, post must include json with order_nr key"})


@auth.route("/api/reset/for/real")
@login_required
def reset():
    orders = models.Order.query.all()
    for order in orders:
        current_db_sessions = db.object_session(order)
        current_db_sessions.delete(order)
    days = models.Day.query.all()
    for day in days:
        current_db_sessions = db.object_session(day)
        current_db_sessions.delete(day)
    current_db_sessions.commit()
    return make_response({"response": "reset"}, 200)
    

@auth.route('/login')
def login():
    return render_template('login.html')


@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@auth.route('/login', methods=['POST'])
def login_post():
    # login code goes here
    n = request.form.get('name')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = models.User.query.filter_by(name=n).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.')
        # if the user doesn't exist or password is wrong, reload the page
        return redirect(url_for('auth.login'))
    login_user(user, remember=remember)
    # if the above check passes, then we know the user has the right credentials
    return redirect(url_for('main.profile'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
