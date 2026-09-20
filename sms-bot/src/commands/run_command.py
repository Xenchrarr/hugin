from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RunCommand(BaseCommand):
    path = "run"
    aliases = ["job"]
    description = "Run an allowlisted orchestrator job"
    usage = "run <name>"

    def execute(self, cmd: ParsedCommand) -> str:
        allowed = cmd.user_config.get("sms_jobs", {})
        if not isinstance(allowed, dict) or not allowed:
            return "No SMS jobs configured. Set config.sms_jobs."
        if not cmd.positional or cmd.positional[0].lower() == "list":
            return "Jobs: " + ", ".join(sorted(str(name) for name in allowed))
        name = " ".join(cmd.positional).lower()
        job_id = next((value for key, value in allowed.items() if str(key).lower() == name), None)
        if job_id is None:
            return f"Unknown job '{name}'. Try: run list"
        jobs = _orchestrator.list_jobs()
        if jobs is None:
            return "Jobs unavailable"
        job = next((item for item in jobs if str(item.get("id")) == str(job_id)), None)
        if job is None:
            return f"Configured job {job_id} not found"
        result = _orchestrator.start_job(job)
        return f"OK started {name}" if result else f"Could not start {name}"
