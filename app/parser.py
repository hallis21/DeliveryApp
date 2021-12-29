from sqlalchemy.sql.sqltypes import DateTime
from app import cache
# from app.login import get_orders
from app import db
from app import models
from datetime import datetime

def parse_orders():
   return
   orders_live: dict = get_orders()

   stored_days = models.Day.query.all()
   days_live = [x for x in orders_live.keys()]
   days_stored = [x.name for x in stored_days]
   for day_str in days_live:
      if day_str not in days_stored:
         # Create day entry
         temp = day_str.split()
         day_month = temp[1].split(".")
         new_date = datetime(2020, int(day_month[1]), int(day_month[0]))
         new_day = models.Day(name=day_str, date=new_date)
         db.session.add(new_day)

   
   orders_stored = [x.order_nr for x in models.Order.query.all()]
   all_live = []
   for day_str, order_list in orders_live.items():
      


      # Only add new entries
      all_live.extend([str(x["Ordrenr"]) for x in order_list])
      for order_live in [x for x in order_list if str(x["Ordrenr"]) not in orders_stored and "hentes" not in  x["Sted"].lower() and "hentes" not in x["C/O"].lower()]:
         try:
            day_entry = models.Day.query.filter(models.Day.name == day_str).first()
            new_order = models.Order(order_nr=str(order_live["Ordrenr"]), day_id=day_entry.id)
            new_order.c_o = order_live["C/O"]
            new_order.recv = order_live["Mottaker"]
            new_order.location = order_live["Sted"]
            new_order.phone = str(order_live["Telefon"])
            new_order.time = order_live["Tidspunkt"] or ""
            new_order.type = order_live["Type"]
            new_order.parse_address()
            db.session.add(new_order)
            # Commit everytime to ensure one error does not cause all to be discarded
            db.session.commit()
         except Exception as e:
            print("Order add failed")
   
   for order_nr in all_live:
      order = models.Order.query.filter_by(order_nr=order_nr).first()
      if order and order.active == 0:
         order.active = 1
   db.session.commit()

   not_active = [x for x in models.Order.query.filter_by(active=1).all() if x.order_nr not in all_live]
   for order in not_active:
      order.active = 0
   

   for order in models.Order.query.filter_by(changed=1).all():
      order.error = ""
      order.parse_address()
      order.changed = 0
   db.session.commit()

   for area in models.Area.query.all():
      area.check_all_within()
