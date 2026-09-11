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
    fn set_clock(&self, py: Python<'_>, paused: bool, time_scale: f64) -> PyResult<()> {
        self.with_runtime(py, |r| r.set_clock(paused, time_scale))
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
    m.add("RULES_VERSION", star_rotk::RULES_VERSION)?;
    m.add_class::<NativeRuntime>()?;
    Ok(())
}
