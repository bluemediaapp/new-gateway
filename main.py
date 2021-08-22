from json import loads
import re
from flask import Flask, request, make_response
from os import environ as env
from itsdangerous import URLSafeSerializer
from pymongo import MongoClient
from requests import post, ConnectionError as RequestsConnectionError
from generatedocs import docs
from json import dumps

from errors import * 

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
            "attach_content": raw_route.get("attach_content"),
        }
        routes.append(route)
    print("Loaded %s routes" % len(routes))


load_routes()
app = Flask(__name__)
security = URLSafeSerializer(env["SECRET_KEY"], "auth")
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
        data = request.headers.get(variable["query"])
        if data is None and variable.get("required", True):
            raise MissingRequiredArgumentError(variable["name"])

    elif source == "form":
        return # Should be passed by attach_content
    else:
        raise TypeError("Unknown variable source: %s" % source)
    variable_type = variable.get("type")
    if variable_type is None:
        return data
    
    # Types
    if variable_type == "int":
        try:
            int(data)
        except:
            raise CriteriaNotFilledError(variable["name"], "int")
        return data
    elif variable_type == "str":
        return data
    raise TypeError("Unknown variable type: %s" % variable_type)

def get_variables(route, groups):
    variables = {}
    for variable in route["variables"]:
        if (variable_data := get_variable(variable, groups)) is None:
            continue
        variables[variable["name"]] = variable_data
    return variables

@app.route("/api/<path:path>", methods=["GET", "POST", "DELETE"])
def redirect(path):
    # Get the correct route
    path = "/" + path
    res = get_matching_route(path)
    if res is None:
        return "No route found.", 404
    route, match = res
    # Variables
    try:
        variables = get_variables(route, match.groups())
    except ValueError as e:
        return {"detail": str(e)}, 400
    except MissingRequiredArgumentError as e:
        return {"detail": "Missing required variable \"%s\"" % e.args[0] }, 400
    except CriteriaNotFilledError as e:
        return {"detail": "%s could not be converted to %s" % (e.variable_name, e.variable_type)}, 400

    # Auth
    if route["require_auth"]:
        if "Authorization" not in request.headers.keys():
            return "Authentication required", 401
        try:
            auth_data = security.loads(request.headers["Authorization"])
        except:
            return "Bad token", 401
        user_login = users_login_collection.find_one({"_id": auth_data["user_id"]})
        if user_login is None:
            return "Account can no longer be used.", 401
        if user_login["password_change_id"] != auth_data["password_change_id"]:
            return "Authentication expired.", 401
        variables["auth_user_id"] = str(auth_data["user_id"])


    # Get the internal URL
    internal_endpoint = env["INTERNAL_URL_" + route["type"].upper()]
    internal_url = internal_endpoint + route["internal_url"]


    # Proxy the request
    try:
        if route.get("attach_content", False) is True:
            # Attach content type headers
            variables["Content-Type"] = request.headers["Content-Type"]
            r = post(internal_url, headers=variables, stream=True, data=request.get_data())
        else:
            r = post(internal_url, headers=variables, stream=True)
    except RequestsConnectionError:
        return "Microservice down.", 500

    resp = make_response(r.content, r.status_code)
    for name, value in r.headers.items():
        resp.headers[name] = value
    resp.headers["Internal-Status"] = "Forwarded"
    return resp

@app.route("/api/cached/docs")
def get_docs():
    return docs
