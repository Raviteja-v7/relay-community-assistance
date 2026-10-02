"""Run the Lambda handler locally using Python's standard-library WSGI server."""

from wsgiref.simple_server import make_server
import os

from app.api.handler import handler


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length).decode("utf-8") if length else ""
    headers = {
        key[5:].replace("_", "-").lower(): value
        for key, value in environ.items()
        if key.startswith("HTTP_")
    }
    if os.environ.get("RELAY_LOCAL_AUTH", "true").lower() == "true":
        os.environ["RELAY_LOCAL_AUTH"] = "true"
    result = handler({"httpMethod": method, "path": path, "body": body, "headers": headers})
    status = result["statusCode"]
    phrase = {
        200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request",
        404: "Not Found", 409: "Conflict", 500: "Internal Server Error",
        401: "Unauthorized", 403: "Forbidden", 502: "Bad Gateway", 503: "Service Unavailable",
    }.get(status, "Internal Server Error")
    response_body = result["body"].encode("utf-8")
    headers = [(key, value) for key, value in result["headers"].items()]
    headers.append(("content-length", str(len(response_body))))
    start_response(f"{status} {phrase}", headers)
    return [response_body]


if __name__ == "__main__":
    print("Relay API listening at http://127.0.0.1:8000")
    with make_server("127.0.0.1", 8000, application) as server:
        server.serve_forever()
