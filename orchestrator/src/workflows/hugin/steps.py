import json

from src.workflows import StepContext, StepResult, WorkflowStepError, step


@step(
    "hugin.run_job",
    description="Run one registered Hugin job capability",
    input_schema={
        "type": "object",
        "required": ["job_type"],
        "properties": {
            "job_type": {"type": "string"},
            "param": {"type": "string"},
        },
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
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
    return StepResult(summary=f"{job_type} completed")


@step("hugin.git_sync", description="Synchronize one or all configured Git repositories",
      input_schema={"type":"object","properties":{"repository":{"type":"string"}},"additionalProperties":False},
      output_schema={"type":"object"})
def git_sync_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.git_service import run_git_sync
    context.check_cancellation()
    output = run_git_sync(inputs.get("repository", "")) or {}
    return StepResult(output=output, summary="Git repositories synchronized")


@step("hugin.power_aggregation", description="Trigger Hugin Core energy aggregation",
      input_schema={"type":"object","additionalProperties":False}, output_schema={"type":"object"})
def power_aggregation_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.power_aggregation_service import run_power_aggregation
    context.check_cancellation()
    output = run_power_aggregation() or {}
    return StepResult(output=output, summary="Power aggregation completed")


@step("hugin.print_news", description="Fetch an RSS feed and print its headlines",
      input_schema={"type":"object","required":["feed_url"],"properties":{
          "feed_url":{"type":"string","minLength":1},"count":{"type":"integer","minimum":1,"maximum":50,"default":5},
          "summarize":{"type":"boolean","default":False}},"additionalProperties":False}, output_schema={"type":"object"})
def print_news_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_news
    context.check_cancellation(); run_print_news(json.dumps(inputs))
    return StepResult(summary="News printed")


@step("hugin.print_weather", description="Print a yr.no weather meteogram",
      input_schema={"type":"object","properties":{"yr_id":{"type":"string"}},"additionalProperties":False}, output_schema={"type":"object"})
def print_weather_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_weather
    context.check_cancellation(); run_print_weather(inputs.get("yr_id", ""))
    return StepResult(summary="Weather printed")


@step("hugin.print_today", description="Print today's calendar and reminders",
      input_schema={"type":"object","additionalProperties":False}, output_schema={"type":"object"})
def print_today_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_today
    context.check_cancellation(); run_print_today()
    return StepResult(summary="Today's agenda printed")


@step("hugin.print_shopping", description="Print the current shopping list",
      input_schema={"type":"object","additionalProperties":False}, output_schema={"type":"object"})
def print_shopping_step(context: StepContext, _inputs: dict) -> StepResult:
    from src.services.external.printer_hub_service import run_print_shopping
    context.check_cancellation(); run_print_shopping()
    return StepResult(summary="Shopping list printed")


@step("hugin.sms_brief", description="Send a daily agenda briefing by SMS",
      input_schema={"type":"object","required":["phone","user_id"],"properties":{
          "phone":{"type":"string","minLength":8},"user_id":{"type":"integer","minimum":1}},"additionalProperties":False},
      output_schema={"type":"object"})
def sms_brief_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.sms_brief_service import run_sms_brief
    context.check_cancellation(); run_sms_brief(json.dumps(inputs))
    return StepResult(summary="SMS briefing queued")


@step("hugin.phone_call", description="Place a ring-only phone call",
      input_schema={"type":"object","required":["target"],"properties":{
          "target":{"type":"string","minLength":1},"ring_seconds":{"type":"integer","minimum":5,"maximum":60,"default":20}},
          "additionalProperties":False}, output_schema={"type":"object"})
def phone_call_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.phone_call_job_service import run_phone_call
    context.check_cancellation(); output = run_phone_call(json.dumps(inputs))
    return StepResult(output=output, summary="Phone call completed")
