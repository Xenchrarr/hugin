jobs_registry = {}

def job_type(job_type_name, description=None):
    """
    Registers a function as a specific type of job with an optional description.

    The `job_type` function decorates another function, associating it with a given
    job type name and optionally a description. This makes the decorated function
    discoverable within the `jobs_registry` for later use or categorization.

    Attributes:
        jobs_registry (dict): The global registry mapping job type names to their
        corresponding functions and descriptions.

    Args:
        job_type_name: Name of the job type under which the decorated function
        will be registered.
        description: Optional description for the job type.

    Returns:
        A decorator function that registers the target function in the job
        registry.
    """
    def decorator(func):
        # Add the function to the registry with its job_type_name
        jobs_registry[job_type_name] = {
            'function': func,
            'description': description or ''
        }

        return func
    return decorator
