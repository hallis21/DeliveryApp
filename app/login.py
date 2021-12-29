# from os import environ
# import requests as req
# import pandas as pd
# from bs4 import BeautifulSoup as bs
# import time
# from app import cache
# import json


# def get_orders(force_update=False):
#     return False
#     cached = cache.get("orders_cached")
#     return cached[1]
#     # Orker ikke hente data hele tiden
#     # letterer sånn her

#     # Ensure password / username
#     if "bring_user" not in environ:
#         print("no user stored in bring_user")
#         raise ValueError("No username")
#     if "bring_pass" not in environ:
#         print("no password stored in bring_pass")
#         raise ValueError("No password")

#     if force_update or cached is None:
#         update_orders()
#         cached = cache.get("orders_cached")
#         return cached[1]

#     last_update = cached[0]
#     if time.time() - last_update > 1800:
#         update_orders()
#         return cached[1]
#     else:
#         return cached[1]


# def update_orders():
  
#     return False
#     print("Updating list")
#     r = req.get("https://www.interflora.no/?")
#     if r.status_code != 200:
#         raise ValueError(str(r.status_code))
#     parsed = bs(
#         r.text, features="html.parser")

#     cat = parsed.find("input", {"name": "cat"})["value"]

#     ses = req.Session()

#     # Ensure password / username

#     r = ses.post("https://www.interflora.no/?", params={
#         "gologin": "1", "user": environ["bring_user"], "pass": environ["bring_pass"], "cat": str(cat), "login": "Logg+inn"})
#     if r.status_code != 200:
#         raise ValueError(str(r.status_code))

#     php_sessid = ses.cookies.get_dict()["PHPSESSID"]

#     orders = ses.post("https://www.interflora.no/plugins/interflorabutikkportal/ajax/cmd_orders/orders.php?orderfilter=ready&printlist=1",
#                       cookies={"PHPSESSID": php_sessid})
#     if orders.status_code != 200:
#         raise ValueError(str(r.status_code))

#     orders_parsed = bs(orders.text, features="html.parser")
#     # TODO: Check for failed login

#     ses.close()
#     tables = orders_parsed.find_all('table')

#     days = {}
#     for table in tables:
#         date = table.find("caption").text
#         orders = []
#         df = pd.read_html(str(table))
#         df = [d.fillna('') for d in df]
#         days[date] = df[0].to_dict(orient='records')

#     orders_cached = (int(time.time()), days)
#     cache.set("orders_cached", orders_cached)
