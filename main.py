from json import loads
import re
from flask import Flask, request
from os import environ as env
from itsdangerous import URLSafeSerializer
from pymongo import MongoClient

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
            "variables": raw_route["variables"],
            "require_auth": raw_route["require_auth"],
        }
        routes.append(route)
    print("Loaded %s routes" % len(routes))


load_routes()
app = Flask(__name__)
security = URLSafeSerializer(env["SECRET_KEY"], "bloo-auth")
mongo = MongoClient(env["mongo_uri"])
blue = mongo["blue"]
users_login_collection = blue["users_login"]

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

def get_variable(variable, groups):
    source = variable["source"]
    if source == "url":
        data = groups[variable["query"]]
    elif source == "headers":
        data = request.headers[variable["query"]]
    else:
        raise TypeError("Unknown variable source: %s" % source)
    variable_type = variables.get("type")
    if variable_type is None:
        return data
    
    # Types
    if variable_type == "int":
        return int(data)
    raise TypeError("Unknown variable type: %s" % variable_type)

def get_variables(route, groups):
    variables = {}
    for variable in route["variables"]:
        variables[variable["name"]] = get_variable(variable, groups)
    return variables


@app.route("/api/<path:path>")
def redirect(path):
    # Get the correct route
    path = "/" + path
    res = get_matching_route(path)
    if res is None:
        return "No route found.", 404
    route, match = res
    # Variables
    variables = get_variables(route, match.groups())

    # Auth
    if auth["require_auth"]:
        if "token" not in request.headers.keys():
            return "Authentication required", 401
        try:
            auth_data = security.loads(token)
        except:
            return "Bad token", 401
        user_login = users_login_collection.find_one({"_id": auth["user_id"]})
        if user_login is None:
            return "Account can no longer be used.", 403
        if user_login["password_change_id"] != auth_data["password_change_id"]:
            return "Authentication expired.", 401
        variables["auth_user_id"] = auth_data["user_id"]


    # Get the internal URL
    internal_endpoint = env["INTERNAL_URL_" + route["type"].upper()]
    internal_url = route["internal_url"].format(internal_endpoint, **variables)
    print("Showing %s" % internal_url)
    return {"url": internal_url}
