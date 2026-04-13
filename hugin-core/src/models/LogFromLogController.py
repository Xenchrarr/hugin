
class LogFromLogController:
    def __init__(self,
                 job_run_id: int,
                 log_text: str,
                 severity: str,
                 stack_trace: str = ''):
        self.job_run_id = job_run_id
        self.log_text = log_text
        self.severity = severity
        self.stack_trace = stack_trace

    @staticmethod
    def from_dict(obj):
        return LogFromLogController(
            obj.get("job_run_id"),
            obj.get("log_text"),
            obj.get("severity"),
            obj.get("stack_trace")
        )

    def to_dict(self):
        result = {}
        result["job_run_id"] = self.job_run_id
        result["log_text"] = self.log_text
        result["severity"] = self.severity
        result["stack_trace"] = self.stack_trace
        return result
