from json import loads, dumps
from yaml import dump as yamldumps

# Load the routes
with open("routes.json") as f:
    routes = loads(f.read())

with open("basedocs.json") as f:
    docs = loads(f.read())

def find_char(to_find, text):
    results = []
    for i, char in enumerate(text):
        if char == to_find:
            results.append(i)
    return results
def get_url_variable(variable_id, variables):
    for variable in variables:
        if variable["source"] == "url" and variable["query"] == variable_id:
            return variable
def parse_url(url, variables):
    if len(variables) == 0:
        return url
    starting_groups = find_char("(", url)
    ending_groups = find_char(")", url)

    new_url = url

    for variable_id, (start, end) in enumerate(zip(starting_groups, ending_groups)):
        to_replace = url[start:end+1]
        variable_name = get_url_variable(variable_id, variables)["name"]
        new_url = new_url.replace(to_replace, "{%s}" % variable_name)
    return new_url




# Set up some initial stuff
docs["paths"] = {}

# Add routes
for route in routes:
    url = parse_url(route["url"], route["variables"])
    data = {}
    data["summary"] = route["name"]
    data["tags"] = [route["type"]]
    # Responses
    data["responses"] = {
        200: {
            "description": "Ok."
        }
    }

    # Auth only
    if route["require_auth"]:
        data["responses"][401] = {
            "description": "Invalid token or token expired."
        }
        data["security"] = [{"api_key": []}]

    # Custom responses
    for response in route.get("responses", []):
        doc_response = data["responses"].get(response["status"])
        if response.get("override", False) or response["status"] not in data["responses"]:
            data["responses"][response["status"]] = {
                "description": response["description"]
            }
            doc_response = data["responses"].get(response["status"])
        else:
            doc_response = data["responses"][response["status"]]
            description = doc_response["description"]
            doc_response["description"] = "%s / %s" % (description, response["description"])
        
        if response.get("schema"):
            doc_response["schema"] = {
                "$ref": "#/definitions/%s" % response["schema"]
            }


    # Parameters
    parameters = []
    for variable in route["variables"]:
        parameter = {}
        parameter["name"] = variable["name"]
        parameter["required"] = True
        parameter["description"] = variable["description"]

        # Variable validations
        if variable["type"] == "int":
            # Int type
            parameter["type"] = "integer"
            parameter["format"] = "int64"
        elif variable["type"] == "str":
            # String type
            parameter["type"] = "string"
        else:
            raise TypeError("Unknown parameter cast: %s" % variable["type"])

        # Variable sources
        if variable["source"] == "url":
            parameter["in"] = "path"
        elif variable["source"] == "headers":
            parameter["in"] = "header"
        elif variable["source"] == "form":
            parameter["in"] = "formData"
            data["consumes"] = ["multipart/form-data"]
        else:
            raise TypeError("Unknown source %s" % variable["source"])

        parameters.append(parameter)
    data["parameters"] = parameters


    # Add the data to the docs
    if url not in docs["paths"]:
        docs["paths"][url] = {}
    docs["paths"][url][route["method"].lower()] = data
# Add tags
tags = []
for route in routes:
    if route["type"] in [i["name"] for i in tags]:
        continue # Already added
    tags.append({
        "name": route["type"],
        "description": "The %s microservice. Source code: https://github.com/bluemediaapp/%s" % (route["type"], route["type"])
    })
docs["tags"] = tags

# Output it
if __name__ == "__main__":
    print(dumps(docs))
