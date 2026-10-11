//! Bounded scoped read jobs. No job can outlive the borrowed read phase.
use bevy_tasks::{TaskPool, TaskPoolBuilder};
use std::thread::ThreadId;

pub struct ReadPool {
    pool: TaskPool,
    threads: usize,
}
impl ReadPool {
    pub fn new(threads: usize) -> Self {
        assert!(matches!(threads, 2 | 4));
        Self {
            pool: TaskPoolBuilder::new()
                .num_threads(threads)
                .thread_name("star-observation".into())
                .build(),
            threads,
        }
    }
    /// One worker overlaps caller work. Both panic paths join before unwinding.
    /// The caller never steals pool jobs; at most two participants are active.
    pub fn fork_join<R: Send + 'static, C>(
        &self,
        worker: impl FnOnce() -> R + Send,
        caller: impl FnOnce() -> C,
    ) -> (R, C) {
        use std::panic::{AssertUnwindSafe, catch_unwind, resume_unwind};
        let mut called = None;
        let mut results = self.pool.scope_with_executor(false, None, |scope| {
            scope.spawn(async move { catch_unwind(AssertUnwindSafe(worker)) });
            called = Some(catch_unwind(AssertUnwindSafe(caller)));
        });
        let computed = results.pop().expect("one scoped job");
        let called = called.expect("caller completed");
        match (computed, called) {
            (_, Err(panic)) | (Err(panic), _) => resume_unwind(panic),
            (Ok(worker), Ok(caller)) => (worker, caller),
        }
    }
    /// At most one chunk per worker; completed values are returned in input order.
    /// The caller waits without running pool jobs, so this uses N workers, not N+1.
    pub fn map_chunks<T: Sync, R: Send + 'static>(
        &self,
        input: &[T],
        compute: impl Fn(&[T]) -> R + Sync,
    ) -> Vec<(R, ThreadId)> {
        if input.is_empty() {
            return Vec::new();
        }
        let chunk_size = input.len().div_ceil(self.threads);
        let mut output = self.pool.scope_with_executor(false, None, |scope| {
            let compute = &compute;
            for (index, chunk) in input.chunks(chunk_size).enumerate() {
                scope.spawn(async move { (index, compute(chunk), std::thread::current().id()) });
            }
        });
        output.sort_unstable_by_key(|(index, _, _)| *index);
        output
            .into_iter()
            .map(|(_, value, worker)| (value, worker))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    use std::sync::Barrier;

    #[test]
    fn fork_overlaps_caller_and_joins_both_panic_paths() {
        use std::panic::{AssertUnwindSafe, catch_unwind};
        use std::sync::atomic::{AtomicBool, Ordering};
        for threads in [2, 4] {
            let pool = ReadPool::new(threads);
            let barrier = Barrier::new(2);
            let caller_id = std::thread::current().id();
            let (worker_id, value) = pool.fork_join(
                || {
                    barrier.wait();
                    std::thread::current().id()
                },
                || {
                    barrier.wait();
                    7
                },
            );
            assert_ne!(worker_id, caller_id);
            assert_eq!(value, 7);
            let completed = AtomicBool::new(false);
            assert!(
                catch_unwind(AssertUnwindSafe(|| pool.fork_join(
                    || {
                        completed.store(true, Ordering::SeqCst);
                    },
                    || panic!("caller fault"),
                )))
                .is_err()
            );
            assert!(completed.load(Ordering::SeqCst));
            completed.store(false, Ordering::SeqCst);
            assert!(
                catch_unwind(AssertUnwindSafe(|| pool.fork_join(
                    || panic!("worker fault"),
                    || {
                        completed.store(true, Ordering::SeqCst);
                    },
                )))
                .is_err()
            );
            assert!(completed.load(Ordering::SeqCst));
            assert_eq!(pool.fork_join(|| 3, || 4), (3, 4));
        }
    }

    #[test]
    fn scoped_jobs_run_on_distinct_bounded_workers_and_keep_input_order() {
        for threads in [2, 4] {
            let pool = ReadPool::new(threads);
            let barrier = Barrier::new(threads);
            let input: Vec<_> = (0..threads).collect();
            let caller = std::thread::current().id();
            let values = pool.map_chunks(&input, |chunk| {
                barrier.wait(); // Cannot complete if jobs merely run serially.
                chunk[0] * 2
            });
            assert_eq!(
                values.iter().map(|(v, _)| *v).collect::<Vec<_>>(),
                input.iter().map(|i| i * 2).collect::<Vec<_>>()
            );
            assert_eq!(
                values
                    .iter()
                    .map(|(_, id)| *id)
                    .collect::<HashSet<_>>()
                    .len(),
                threads
            );
            assert!(values.iter().all(|(_, id)| *id != caller));
            assert!(pool.map_chunks::<usize, ()>(&[], |_| ()).is_empty());
            assert_eq!(pool.map_chunks(&[7], |items| items[0])[0].0, 7);
        }
    }
}
