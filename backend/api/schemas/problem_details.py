"""RFC 7807 Problem Details schema for standardized API error responses.

This module implements the RFC 7807 "Problem Details for HTTP APIs" specification,
which provides a standardized format for machine-readable error responses.

RFC 7807 specifies the following members for problem details:
- type: A URI reference that identifies the problem type
- title: A short, human-readable summary of the problem type
- status: The HTTP status code
- detail: A human-readable explanation specific to this occurrence
- instance: A URI reference that identifies the specific occurrence

References:
    - RFC 7807: https://tools.ietf.org/html/rfc7807
    - IANA Media Type: application/problem+json

Usage:
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    from backend.api.schemas.problem_details import ProblemDetail, get_status_phrase

    @app.exception_handler(HTTPException)
    async def problem_details_handler(request: Request, exc: HTTPException):
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(exc.status_code),
            status=exc.status_code,
            detail=str(exc.detail) if exc.detail else get_status_phrase(exc.status_code),
            instance=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )
"""

from pydantic import BaseModel, Field

# HTTP status code to standard phrase mapping per RFC 7231
# https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml
HTTP_STATUS_PHRASES: dict[int, str] = {
    # 1xx Informational
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing",
    103: "Early Hints",
    # 2xx Success
    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-Authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    207: "Multi-Status",
    208: "Already Reported",
    226: "IM Used",
    # 3xx Redirection
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    # 4xx Client Errors
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Content Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    416: "Range Not Satisfiable",
    417: "Expectation Failed",
    418: "I'm a Teapot",
    421: "Misdirected Request",
    422: "Unprocessable Content",
    423: "Locked",
    424: "Failed Dependency",
    425: "Too Early",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    451: "Unavailable For Legal Reasons",
    # 5xx Server Errors
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
    506: "Variant Also Negotiates",
    507: "Insufficient Storage",
    508: "Loop Detected",
    510: "Not Extended",
    511: "Network Authentication Required",
}


def get_status_phrase(status_code: int) -> str:
    """Get the standard HTTP status phrase for a given status code.

    This function returns the canonical phrase for HTTP status codes as defined
    by IANA HTTP Status Code Registry and RFC 7231.

    Args:
        status_code: The HTTP status code (e.g., 404, 500)

    Returns:
        The standard phrase for the status code, or "Unknown Error" if the
        status code is not recognized.

    Examples:
        >>> get_status_phrase(404)
        'Not Found'
        >>> get_status_phrase(500)
        'Internal Server Error'
        >>> get_status_phrase(418)
        "I'm a Teapot"
        >>> get_status_phrase(999)
        'Unknown Error'
    """
    return HTTP_STATUS_PHRASES.get(status_code, "Unknown Error")


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details object for API error responses.

    This schema implements the Problem Details format as specified in RFC 7807,
    which provides a standardized, machine-readable format for error responses
    in HTTP APIs.

    The media type for responses using this format is "application/problem+json".

    Attributes:
        type: A URI reference [RFC 3986] that identifies the problem type.
            When dereferenced, it should provide human-readable documentation.
            When this member is not present, its value is assumed to be
            "about:blank", indicating the problem has no additional semantics
            beyond the HTTP status code.

        title: A short, human-readable summary of the problem type. It should
            NOT change from occurrence to occurrence of the problem, except
            for purposes of localization. Typically uses the standard HTTP
            status phrase (e.g., "Not Found" for 404).

        status: The HTTP status code generated by the origin server for this
            occurrence of the problem. Included for convenience, as it may not
            always be possible to determine the status code from the response
            (e.g., when forwarded through a proxy).

        detail: A human-readable explanation specific to this occurrence of
            the problem. Unlike "title", this can change between occurrences
            and should provide information helpful for debugging.

        instance: A URI reference that identifies the specific occurrence of
            the problem. It may or may not yield further information if
            dereferenced. Typically the request path or a unique error ID.

    Example:
        >>> problem = ProblemDetail(
        ...     type="about:blank",
        ...     title="Not Found",
        ...     status=404,
        ...     detail="Camera 'front_door' does not exist",
        ...     instance="/api/cameras/front_door",
        ... )
        >>> problem.model_dump(exclude_none=True)
        {
            'type': 'about:blank',
            'title': 'Not Found',
            'status': 404,
            'detail': "Camera 'front_door' does not exist",
            'instance': '/api/cameras/front_door'
        }

    References:
        - RFC 7807: https://tools.ietf.org/html/rfc7807
        - RFC 3986 (URI): https://tools.ietf.org/html/rfc3986
    """

    type: str = Field(
        default="about:blank",
        description=(
            "A URI reference that identifies the problem type. "
            "When this member is not present, its value is assumed to be 'about:blank'."
        ),
        examples=["about:blank", "https://api.example.com/problems/resource-not-found"],
    )

    title: str = Field(
        ...,
        description=(
            "A short, human-readable summary of the problem type. "
            "It should NOT change from occurrence to occurrence."
        ),
        examples=["Not Found", "Bad Request", "Internal Server Error"],
    )

    status: int = Field(
        ...,
        ge=100,
        le=599,
        description="The HTTP status code generated by the origin server.",
        examples=[400, 404, 500],
    )

    detail: str = Field(
        ...,
        description=("A human-readable explanation specific to this occurrence of the problem."),
        examples=[
            "Camera 'front_door' does not exist",
            "The 'email' field must be a valid email address",
        ],
    )

    instance: str | None = Field(
        default=None,
        description=(
            "A URI reference that identifies the specific occurrence of the problem. "
            "Typically the request path."
        ),
        examples=["/api/cameras/front_door", "/api/events/12345"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "Camera 'front_door' does not exist",
                "instance": "/api/cameras/front_door",
            }
        }
    }
