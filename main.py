from json import loads
import re
from flask import Flask, request
from os import environ as env

# Load the routes
routes = []
def load_routes():
    global routes
    with open("routes.json") as f:
        raw_routes = loads(f.read())
    for raw_route in raw_routes:
        route = {
            "url": re.compile(raw_route["url"]),
            "method": raw_route["method"],
            "internal_url": raw_route["internal_url"],
            "type": raw_route["type"],
        }
        routes.append(route)
    print("Loaded %s routes" % len(routes))


load_routes()
app = Flask(__name__)

def meets_criteria(route, path):
    match = route["url"].match(path)
    if match is None:
        return
    if request.method != route["method"]:
        return
    return match


def get_matching_route(path):
    for route in routes:
        match = meets_criteria(route, path)
        if match is not None:
            break
    if match is None:
        return
    return route, match


@app.route("/api/<path:path>")
def redirect(path):
    path = "/" + path
    res = get_matching_route(path)
    if res is None:
        return "No route found.", 404
    route, match = res
    internal_url = route["internal_url"].format(env["INTERNAL_URL_" + route["type"].upper()], params=match.groups())
    print("Showing %s" % internal_url)
    return {"url": internal_url}
