class JobForApi:
    # {
    #     'id': job.id,
    #     'name': job.name,
    #     'next_run_time': job.next_run_time,
    #     'status': job.status,
    #     'trigger': job.trigger,
    #     'hour': job.hour,
    #     'minute': job.minute,
    # }

    def __init__(self, job_id, name, next_run_time, trigger):
        self.job_id = job_id
        self.name = name
        self.next_run_time = next_run_time
        self.trigger = trigger

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "name": self.name,
            "next_run_time": self.next_run_time,
            "trigger": str(self.trigger)
        }