use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SimClock {
    pub elapsed: f64,
    pub time_scale: f64,
    pub paused: bool,
    pub realtime: bool,
    pub tick: u64,
}

impl SimClock {
    pub fn step(&mut self, dt: f64) -> Result<(), String> {
        if !dt.is_finite() || dt < 0.0 {
            return Err("dt must be finite and nonnegative".into());
        }
        let elapsed = if self.realtime && !self.paused {
            self.elapsed + dt * self.time_scale
        } else {
            self.elapsed
        };
        if !elapsed.is_finite() {
            return Err("simulation time overflow".into());
        }
        let tick = self.tick.checked_add(1).ok_or("tick overflow")?;
        self.elapsed = elapsed;
        self.tick = tick;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fixed_steps_pause_and_invalid_inputs() {
        let mut c = SimClock {
            elapsed: 0.,
            time_scale: 1.,
            paused: false,
            realtime: true,
            tick: 0,
        };
        for _ in 0..30 {
            c.step(1. / 30.).unwrap();
        }
        assert!((c.elapsed - 1.).abs() < 1e-12);
        c.paused = true;
        let before = c.elapsed;
        c.step(9.).unwrap();
        assert_eq!(c.elapsed, before);
        let before = c.clone();
        assert!(c.step(f64::NAN).is_err());
        assert_eq!(c, before);
    }
}
