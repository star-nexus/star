use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
};
use serde_json::{Value, json};
use star_rotk::runtime::Runtime;
use std::sync::Mutex;

/// Owned Rust world. The lock is always acquired after detaching from Python.
/// A poisoned instance errors permanently; no recovery into a different world.
#[pyclass(frozen, module = "star_native._native")]
struct NativeRuntime {
    inner: Mutex<Option<Runtime>>,
}

impl NativeRuntime {
    fn with_runtime<T: Send>(
        &self,
        py: Python<'_>,
        f: impl FnOnce(&mut Runtime) -> Result<T, String> + Send,
    ) -> PyResult<T> {
        py.detach(|| {
            let mut guard = self
                .inner
                .lock()
                .map_err(|_| "native runtime is poisoned".to_string())?;
            let runtime = guard.as_mut().ok_or("native runtime is closed")?;
            f(runtime)
        })
        .map_err(PyRuntimeError::new_err)
    }
}

#[pymethods]
impl NativeRuntime {
    #[new]
    #[pyo3(signature=(scene_json, threads=1))]
    fn new(py: Python<'_>, scene_json: String, threads: usize) -> PyResult<Self> {
        let world = py
            .detach(|| Runtime::from_json(&scene_json, threads, 1))
            .map_err(PyValueError::new_err)?;
        Ok(Self {
            inner: Mutex::new(Some(world)),
        })
    }
    fn reset(&self, py: Python<'_>, scene_json: String) -> PyResult<()> {
        self.with_runtime(py, |old| {
            let epoch = old.epoch.checked_add(1).ok_or("lifecycle exhausted")?;
            let replacement = Runtime::from_json(&scene_json, old.threads, epoch)?;
            *old = replacement;
            Ok(())
        })
    }
    fn step(&self, py: Python<'_>, dt: f64, wall_time: f64) -> PyResult<()> {
        self.with_runtime(py, |r| r.step(dt, wall_time))
    }
    /// Trusted Framework keyboard/menu input; not an Agent wire verb.
    fn finish_human_turn(&self, py: Python<'_>, wall_time: f64) -> PyResult<()> {
        self.with_runtime(py, |r| r.finish_human_turn(wall_time))
    }
    fn set_clock(&self, py: Python<'_>, paused: bool, time_scale: f64) -> PyResult<()> {
        self.with_runtime(py, |r| r.set_clock(paused, time_scale))
    }
    fn _set_wall_metadata(&self, py: Python<'_>, wall_time: f64) -> PyResult<()> {
        self.with_runtime(py, |r| r.set_wall_metadata(wall_time))
    }
    fn export_state_json(&self, py: Python<'_>) -> PyResult<String> {
        self.with_runtime(py, |r| {
            serde_json::to_string(&r.export()).map_err(|e| e.to_string())
        })
    }
    fn diagnostics_json(&self, py: Python<'_>) -> PyResult<String> {
        self.with_runtime(py, |r| Ok(r.diagnostics().to_string()))
    }
    fn take_presentation_delta_json(&self, py: Python<'_>) -> PyResult<String> {
        self.with_runtime(py, |r| Ok(r.presentation().to_string()))
    }
    fn close(&self, py: Python<'_>) -> PyResult<()> {
        py.detach(|| {
            self.inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("native runtime is poisoned"))?
                .take();
            Ok(())
        })
    }
    /// Internal differential harness, never advertised as an Agent action gate.
    fn _vision_probe_json(&self, py: Python<'_>, operations_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            let mut results = Vec::new();
            for op in ops {
                let revision = r.revision.checked_add(1).ok_or("revision exhausted")?;
                let result = r.vision_probe(&op);
                r.revision = revision;
                results.push(result?);
            }
            Ok(json!(results).to_string())
        })
    }
    /// Internal differential harness, never advertised as an Agent action gate.
    fn _combat_probe_json(&self, py: Python<'_>, operations_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            let mut results = Vec::new();
            for op in ops {
                let id = op["unit_id"].as_u64().ok_or("invalid unit_id")?;
                let target = op["target_id"].as_u64();
                let result = match op["kind"].as_str() {
                    Some("ready") => json!(r.can_attack(id, target)),
                    Some("effective") => json!(r.effective_stats(id)?),
                    Some("attack") => {
                        let revision = r.revision.checked_add(1).ok_or("revision exhausted")?;
                        let result = r.execute_attack(id, target.ok_or("missing target")?);
                        // Partial execution still invalidates all read contexts.
                        r.revision = revision;
                        result?
                    }
                    _ => return Err("unknown combat probe".into()),
                };
                results.push(result);
            }
            Ok(json!(results).to_string())
        })
    }
    /// Trusted local ingress. agent_id is supplied by the Python/Protocol adapter.
    fn execute_action_json(&self, py: Python<'_>, request_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let request = serde_json::from_str(&request_json).map_err(|e| e.to_string())?;
            Ok(r.execute_request(request)?.to_string())
        })
    }
    /// Ordered requests; consecutive faction queries share a borrowed read context.
    /// Envelope decoding is atomic; execution is sequential, not a transaction.
    fn execute_actions_json(&self, py: Python<'_>, requests_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let requests = serde_json::from_str(&requests_json).map_err(|e| e.to_string())?;
            Ok(r.execute_requests(requests)?.to_string())
        })
    }
    /// Internal component probe; does not authorize Agent actions.
    fn _team_probe_json(&self, py: Python<'_>, operations_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            Ok(json!(r.team_probe(ops)?).to_string())
        })
    }
    /// Handler-level differential probe, not the authenticated Agent interface.
    fn _observation_probe_json(&self, py: Python<'_>, parameters_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let requests: Vec<Value> =
                serde_json::from_str(&parameters_json).map_err(|e| e.to_string())?;
            let mut batch = star_rotk::observation::ObservationBatch::new(r);
            let results: Vec<_> = requests.iter().map(|p| batch.faction_state(p)).collect();
            Ok(json!({"results":results,"metrics":batch.metrics}).to_string())
        })
    }
    /// Internal differential harness, never advertised as an Agent action gate.
    fn _resource_probe_json(&self, py: Python<'_>, operations_json: String) -> PyResult<String> {
        use star_rotk::components::{ActionPoints, SkillPoints};
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            let mut results = Vec::new();
            for op in ops {
                let id = op["unit_id"].as_u64().ok_or("invalid unit_id")?;
                let entity = r.world.entity(id).ok_or("missing unit")?;
                let accepted = match op["kind"].as_str() {
                    Some("ap") => {
                        let mut ap = r
                            .world
                            .ecs
                            .get_mut::<ActionPoints>(entity)
                            .ok_or("missing AP")?;
                        let ok = ap.current_ap >= 1;
                        if ok {
                            ap.current_ap -= 1;
                        }
                        if ok {
                            r.mark_ap_spent(id);
                        }
                        ok
                    }
                    Some("skill") => {
                        let name = op["name"].as_str().ok_or("missing skill")?.to_string();
                        let cost = op["cost"].as_i64().ok_or("missing cost")?;
                        let cooldown = op["cooldown"].as_i64().ok_or("missing cooldown")?;
                        if cost < 0 || cooldown < 0 {
                            return Err("invalid skill probe".into());
                        }
                        let mut sp = r
                            .world
                            .ecs
                            .get_mut::<SkillPoints>(entity)
                            .ok_or("missing SP")?;
                        let ok = sp.current_sp >= cost
                            && sp.skill_cooldowns.get(&name).is_none_or(|v| *v <= 0);
                        if ok {
                            sp.current_sp -= cost;
                            if cooldown > 0 {
                                sp.skill_cooldowns.insert(name, cooldown);
                            }
                        }
                        if ok {
                            r.mark_skill_started(id);
                        }
                        ok
                    }
                    _ => return Err("unknown resource probe".into()),
                };
                if accepted {
                    r.revision = r.revision.checked_add(1).ok_or("revision exhausted")?;
                }
                results.push(accepted);
            }
            Ok(json!(results).to_string())
        })
    }
    /// Internal differential harness, never advertised as an Agent action gate.
    fn _movement_probe_json(&self, py: Python<'_>, operations_json: String) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            let mut results = Vec::with_capacity(ops.len());
            for op in ops {
                let id = op["unit_id"].as_u64().ok_or("invalid unit_id")?;
                let kind = op["kind"].as_str().ok_or("missing kind")?;
                let result = if kind == "reachable" {
                    json!(r.reachable(id))
                } else {
                    let goal: (i64, i64) =
                        serde_json::from_value(op["goal"].clone()).map_err(|e| e.to_string())?;
                    if goal.0.unsigned_abs() > i32::MAX as u64
                        || goal.1.unsigned_abs() > i32::MAX as u64
                    {
                        return Err("probe coordinates exceed native range".into());
                    }
                    match kind {
                        "path" => json!(r.plan_path(id, goal, op["max_cost"].as_i64())),
                        "move" => {
                            let revision = r.revision.checked_add(1).ok_or("revision exhausted")?;
                            let result = r.move_unit(id, goal);
                            r.revision = revision;
                            result
                        }
                        _ => return Err("unknown movement probe".into()),
                    }
                };
                results.push(result);
            }
            Ok(json!(results).to_string())
        })
    }
    /// Diagnostic replay probe for the native RNG, not an Agent game verb.
    fn _rng_probe_json(
        &self,
        py: Python<'_>,
        domain: String,
        operations_json: String,
    ) -> PyResult<String> {
        self.with_runtime(py, |r| {
            let ops: Vec<Value> =
                serde_json::from_str(&operations_json).map_err(|e| e.to_string())?;
            // Work on a clone: invalid probe input cannot partly advance a stream.
            let mut rng = r.rng.trial(&domain);
            let mut results = Vec::with_capacity(ops.len());
            for op in ops {
                let value = match op["kind"].as_str() {
                    Some("random") => json!(rng.random()),
                    Some("bits") => {
                        let bits = op["bits"].as_u64().ok_or("missing bits")?;
                        if bits > 64 {
                            return Err("invalid bit width".into());
                        }
                        json!(rng.getrandbits(bits as u32)?)
                    }
                    Some("randbelow") => {
                        json!(rng.randbelow(op["n"].as_u64().ok_or("missing n")?)?)
                    }
                    Some("randint") => json!(rng.randint(
                        op["lo"].as_i64().ok_or("missing lo")?,
                        op["hi"].as_i64().ok_or("missing hi")?
                    )?),
                    Some("uniform") => json!(rng.uniform(
                        op["lo"].as_f64().ok_or("missing lo")?,
                        op["hi"].as_f64().ok_or("missing hi")?
                    )),
                    Some("shuffle") => {
                        let mut values = op["values"].as_array().ok_or("missing values")?.clone();
                        rng.shuffle(&mut values);
                        json!(values)
                    }
                    _ => return Err("unknown RNG probe operation".into()),
                };
                results.push(value);
            }
            let state = rng.state();
            r.rng.commit(domain, rng);
            Ok(json!({"results": results, "state": state}).to_string())
        })
    }
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("API_VERSION", star_rotk::API_VERSION)?;
    m.add("RULES_VERSION", star_rotk::RULES_VERSION)?;
    m.add_class::<NativeRuntime>()?;
    Ok(())
}
