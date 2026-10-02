import json

from src.workflows import StepContext, StepResult, WorkflowStepError, step


@step(
    "hugin.run_job",
    description="Run one registered Hugin job capability",
    input_schema={
        "type": "object",
        "required": ["job_type"],
        "properties": {
            "job_type": {"type": "string", "minLength": 1,
                         "description": "Registered Hugin capability key"},
            "param": {"type": "string", "default": "",
                      "description": "Capability-specific string parameter"},
        },
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "required": ["job_type", "completed"],
        "properties": {
            "job_type": {"type": "string"},
            "completed": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
)
def run_hugin_job_step(context: StepContext, inputs: dict) -> StepResult:
    from src.jobs_registry import jobs_registry

    context.check_cancellation()
    job_type = inputs["job_type"]
    registered = jobs_registry.get(job_type)
    if registered is None:
        raise WorkflowStepError(f"Unknown Hugin job capability: {job_type}")
    registered["function"](inputs.get("param", ""))
    context.check_cancellation()
    return StepResult(
        output={"job_type": job_type, "completed": True},
        summary=f"{job_type} completed",
    )


@step("hugin.git_sync", description="Synchronize one or all configured Git repositories",
      input_schema={"type":"object","properties":{"repository":{"type":"string","default":"",
                    "description":"Repository name, or empty to synchronize all repositories"}},"additionalProperties":False},
      output_schema={"type":"object","required":["repositories","repository_count","updated_count"],
                     "properties":{"repositories":{"type":"object","description":"Results keyed by repository name"},
                                   "repository_count":{"type":"integer","minimum":0},
                                   "updated_count":{"type":"integer","minimum":0}},"additionalProperties":False},
      idempotent=True)
def git_sync_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.git_service import run_git_sync
    context.check_cancellation()
    repositories = run_git_sync(inputs.get("repository", "")) or {}
    updated_count = sum(
        1 for value in repositories.values()
        if isinstance(value, dict) and value.get("updated")
    )
    return StepResult(
        output={"repositories": repositories, "repository_count": len(repositories),
                "updated_count": updated_count},
        summary="Git repositories synchronized",
    )


@step("hugin.power_aggregation", description="Trigger Hugin Core energy aggregation",
      input_schema={"type":"object","properties":{},"additionalProperties":False},
      output_schema={"type":"object","required":["ok","message"],
                     "properties":{"ok":{"type":"boolean"},"message":{"type":"string"}},
                     "additionalProperties":False}, idempotent=True)
def power_aggregation_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.power_aggregation_service import run_power_aggregation
    context.check_cancellation()
    output = run_power_aggregation() or {}
    return StepResult(output=output, summary="Power aggregation completed")


@step("hugin.print_news", description="Fetch an RSS feed and print its headlines",
      input_schema={"type":"object","required":["feed_url"],"properties":{
          "feed_url":{"type":"string","minLength":1,"description":"RSS or Atom feed URL"},
          "count":{"type":"integer","minimum":1,"maximum":50,"default":5,"description":"Maximum headlines to print"},
          "summarize":{"type":"boolean","default":False,"description":"Summarize headlines before printing"}},"additionalProperties":False},
      output_schema={"type":"object","required":["printed"],"properties":{"printed":{"type":"boolean"}},"additionalProperties":False})
def print_news_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_news
    context.check_cancellation(); run_print_news(json.dumps(inputs))
    return StepResult(output={"printed": True}, summary="News printed")


@step("hugin.print_weather", description="Print a yr.no weather meteogram",
      input_schema={"type":"object","properties":{"yr_id":{"type":"string","default":"",
                    "description":"yr.no location identifier, or empty to use the configured default"}},"additionalProperties":False},
      output_schema={"type":"object","required":["printed"],"properties":{"printed":{"type":"boolean"}},"additionalProperties":False})
def print_weather_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_weather
    context.check_cancellation(); run_print_weather(inputs.get("yr_id", ""))
    return StepResult(output={"printed": True}, summary="Weather printed")


@step("hugin.print_today", description="Print today's calendar and reminders",
      input_schema={"type":"object","properties":{},"additionalProperties":False},
      output_schema={"type":"object","required":["printed"],"properties":{"printed":{"type":"boolean"}},"additionalProperties":False})
def print_today_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_today
    context.check_cancellation(); run_print_today()
    return StepResult(output={"printed": True}, summary="Today's agenda printed")


@step("hugin.print_shopping", description="Print the current shopping list",
      input_schema={"type":"object","properties":{},"additionalProperties":False},
      output_schema={"type":"object","required":["printed"],"properties":{"printed":{"type":"boolean"}},"additionalProperties":False})
def print_shopping_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_shopping
    context.check_cancellation(); run_print_shopping()
    return StepResult(output={"printed": True}, summary="Shopping list printed")


@step("hugin.sms_brief", description="Send a daily agenda briefing by SMS",
      input_schema={"type":"object","required":["phone","user_id"],"properties":{
          "phone":{"type":"string","minLength":8,"description":"Destination phone number in international format"},
          "user_id":{"type":"integer","minimum":1,"description":"Hugin user whose agenda is summarized"}},"additionalProperties":False},
      output_schema={"type":"object","required":["queued"],"properties":{"queued":{"type":"boolean"}},"additionalProperties":False})
def sms_brief_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.sms_brief_service import run_sms_brief
    context.check_cancellation(); run_sms_brief(json.dumps(inputs))
    return StepResult(output={"queued": True}, summary="SMS briefing queued")


@step("hugin.phone_call", description="Place a ring-only phone call",
      input_schema={"type":"object","required":["target"],"properties":{
          "target":{"type":"string","minLength":1,"description":"User ID, user name, or E.164 phone number"},
          "ring_seconds":{"type":"integer","minimum":5,"maximum":60,"default":20,
                          "description":"Maximum ringing duration"}},
          "additionalProperties":False}, output_schema={"type":"object","required":["ok","status","uncertain"],"properties":{
              "ok":{"type":"boolean"},"status":{"type":"string"},"uncertain":{"type":"boolean"},
              "diagnostics":{"type":"object"},"voice_ready":{"type":"boolean"}},"additionalProperties":False})
def phone_call_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.phone_call_job_service import run_phone_call
    context.check_cancellation(); output = run_phone_call(json.dumps(inputs))
    return StepResult(output=output, summary="Phone call completed")
