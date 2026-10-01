"""Expose every existing Hugin job as a one-step versioned workflow."""

import src.jobs  # noqa: F401 - populate the legacy capability registry
from src.jobs_registry import jobs_registry
from src.workflows import input_ref, use, workflow
from .steps import (
    git_sync_step, phone_call_step, power_aggregation_step, print_news_step,
    print_shopping_step, print_today_step, print_weather_step, run_hugin_job_step,
    sms_brief_step,
)


_native = {
    "git_sync": git_sync_step,
    "phone_call": phone_call_step,
    "power_aggregation": power_aggregation_step,
    "print_news": print_news_step,
    "print_shopping": print_shopping_step,
    "print_today": print_today_step,
    "print_weather": print_weather_step,
    "sms_brief": sms_brief_step,
}

for _key, _step in _native.items():
    workflow(
        _key,
        _step,
        version=1,
        description=jobs_registry[_key].get("description", ""),
        input_schema=_step.spec.input_schema,
    )


for _job_type, _registration in sorted(jobs_registry.items()):
    if _job_type == "run_script" or _job_type in _native:
        # Native workflows expose typed input and structured output. Optional
        # development jobs still receive the generic adapter below.
        continue
    workflow(
        _job_type,
        use(
            run_hugin_job_step,
            key="run",
            inputs={
                "job_type": _job_type,
                "param": input_ref("param", optional=True),
            },
        ),
        version=1,
        description=_registration.get("description", ""),
        input_schema={
            "type": "object",
            "properties": {"param": {"type": "string", "default": ""}},
            "additionalProperties": False,
        },
    )
