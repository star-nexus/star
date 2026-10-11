"""Worker-lifetime operation journal. Request IDs remain transport correlation IDs."""
from copy import deepcopy
import json
from threading import RLock


class OperationJournal:
    def __init__(self):
        self._records = {}
        self._lock = RLock()

    def get(self, epoch, agent, operation_id):
        if not isinstance(operation_id, str):
            return {"state": "not_found"}
        with self._lock:
            record = self._records.get((epoch, agent, operation_id))
            return deepcopy(record) if record else {"state": "not_found"}

    def execute(self, epoch, agent, operation_id, action, parameters, execute):
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
            return {"success": False, "error": "invalid_operation_id"}, False
        try:
            fingerprint = json.dumps([action, parameters], sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError):
            return {"success": False, "error": "invalid_operation_payload"}, False
        key = (epoch, agent, operation_id)
        with self._lock:
            previous = self._records.get(key)
            if previous:
                if previous["fingerprint"] != fingerprint:
                    return {"success": False, "error": "operation_conflict"}, False
                if previous["state"] == "completed":
                    return deepcopy(previous["result"]), False
                return {"success": False, "error": "operation_outcome_unknown"}, False
            record = {"state": "pending", "fingerprint": fingerprint}
            self._records[key] = record
            try:
                result = execute()
            except BaseException:
                record["state"] = "unknown"
                raise
            record.update(state="completed", result=deepcopy(result))
            return deepcopy(result), True
