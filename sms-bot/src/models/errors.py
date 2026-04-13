ERR_PARSE = "ERR_PARSE"
ERR_UNKNOWN_CMD = "ERR_UNKNOWN_CMD"
ERR_AMBIG = "ERR_AMBIG"
ERR_AUTH = "ERR_AUTH"
ERR_BAD_ARG = "ERR_BAD_ARG"
ERR_INTERNAL = "ERR_INTERNAL"


def error_response(code: str, message: str, hint: str = "") -> str:
    resp = f"{code}: {message}"
    if hint:
        resp += f". Hint: {hint}"
    return resp
