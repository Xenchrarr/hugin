import logging

from src.persistence.DatabaseLogger import DatabaseLogger
from src.persistence.RequestLogger import RequestLogger

log = logging.getLogger(__name__)


def handle_response(response, area, request_type, function_name, api_name:str,  request_data = "", response_type=None, comment=None):
    """
    Handles HTTP responses from API requests.

    This function processes the response of an API call based on its type and status code.
    It logs the request and response details, parses the response data, and raises an
    exception if the status code indicates an error.

    Parameters:
    response (Response): The response object returned by the API call.
    area (str): The target area or module where the request was made.
    request_type (str): The HTTP method of the request (e.g., 'GET', 'POST', 'DELETE').
    function_name (str): The name of the function associated with the API request.
    api_name (str): The name or identifier of the target API being called.
    request_data (str, optional): The data sent with the request. Default is an empty string.
    response_type (type, optional): A class type to parse the response data into. Defaults to None.
    comment (str, optional): Additional text or comment associated with the request. Defaults to None.

    Returns:
    Any: Returns the parsed response data, a list of parsed items, or True for a deleted resource.

    Raises:
    Exception: If the response status code is not 200 or the request encounters an error.
    """
    request_logger = RequestLogger()
    logger = DatabaseLogger()

    request_logger.log_request(area, str(request_data), request_type, response.status_code, response.text, function_name, api_name, comment)
    if response.status_code == 200:
        if request_type == "DELETE":
            return True
        data = response.json()
        if response_type is not None:
            if isinstance(data, list):
                return [response_type.from_dict(item) for item in data]
            else:
                return response_type.from_dict(data)
        else:
            return data
    else:
        log.error("%s: %s", response.status_code, response.text)
        logger.log_error(f"Error: {response.status_code} | {response.text}", "")

        raise Exception(f"{response.status_code}: {response.text}")


def handle_animals_response(response, area, request_type, function_name, api_name:str, request_data = "",  response_type=None):
    """
    Handles the response from an API call related to animals, including logging the request and response.
    Processes the response data if the status code is 200. If a response type is defined,
    it converts the data to the specified type. Logs and raises an exception in case of an error status.

    Args:
        response: The response object from the API call.
        area: A string representing the area or context of the API call.
        request_type: A string representing the type of request made (e.g., "GET", "POST").
        function_name: The name of the function making the API call.
        api_name (str): The name of the API being called.
        request_data: Optional; the data sent with the request. Defaults to an empty string.
        response_type: Optional; the class type to which the response data should be converted. Defaults to None.

    Returns:
        The processed response data:
            - If response_type is defined and data is a list, a list of objects of the specified type is returned.
            - If response_type is defined and data is not a list, a single object of the specified type is returned.
            - If response_type is not defined, the raw response data is returned.

    Raises:
        Exception: If the response status code is not 200.

    """
    request_logger = RequestLogger()
    logger = DatabaseLogger()
    request_logger.log_request(area, request_data, request_type, response.status_code, response.text, function_name, api_name, None)
    if response.status_code == 200:
        data = response.json()
        data = data["animals"]
        if response_type is not None:
            if isinstance(data, list):
                return [response_type.from_dict(item) for item in data]
            else:
                return response_type.from_dict(data)
        else:
            return data
    else:
        log.error("%s: %s", response.status_code, response.text)
        logger.log_error(f"Error: {response.status_code} | {response.text}", "")
        raise Exception(f"{response.status_code}: {response.text}")

def handle_response_with_no_logging(response) -> bool:
    """
    Determine the success of an HTTP response based on its status code.

    This function evaluates the HTTP status code of the given response to determine
    if the request was successful. A successful response is indicated by a status
    code of 200.

    Parameters:
    response (Response): The HTTP response object to evaluate.

    Returns:
    bool: True if the response status code is 200, False otherwise.
    """
    if response.status_code == 200:
        return True
    else:
        return False
