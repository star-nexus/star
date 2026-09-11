//! CPython integer-seeded MT19937 and its used sampling primitives.
//! Algorithm provenance and license: native/python/python/star_native/NOTICE.md.
use blake2::{Blake2b, Digest, digest::consts::U8};
use num_bigint::BigInt;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub fn canonical_seed(seed: &str) -> Result<String, String> {
    seed.parse::<BigInt>()
        .map(|n| n.to_string())
        .map_err(|_| "invalid integer seed".into())
}

pub fn domain_seed(root: &str, domain: &str) -> Result<u64, String> {
    let root = canonical_seed(root)?;
    let hash = Blake2b::<U8>::digest(format!("{root}:{domain}").as_bytes());
    Ok(u64::from_be_bytes(hash.into()))
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RandomState {
    pub words: Vec<u32>,
    pub index: usize,
    pub gauss_next: Option<f64>,
}

#[derive(Clone)]
pub struct PyRandom {
    words: [u32; 624],
    index: usize,
    gauss_next: Option<f64>,
}
impl PyRandom {
    pub fn seed_u64(seed: u64) -> Self {
        let key = if seed > u32::MAX as u64 {
            vec![seed as u32, (seed >> 32) as u32]
        } else {
            vec![seed as u32]
        };
        Self::seed_words(&key)
    }
    pub fn seed_words(key: &[u32]) -> Self {
        assert!(!key.is_empty());
        let mut words = [0_u32; 624];
        words[0] = 19650218;
        for i in 1..624 {
            words[i] = (words[i - 1] ^ (words[i - 1] >> 30))
                .wrapping_mul(1812433253)
                .wrapping_add(i as u32);
        }
        let (mut i, mut j) = (1, 0);
        for _ in 0..624.max(key.len()) {
            words[i] = (words[i] ^ (words[i - 1] ^ (words[i - 1] >> 30)).wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i == 624 {
                words[0] = words[623];
                i = 1;
            }
            if j == key.len() {
                j = 0;
            }
        }
        for _ in 0..623 {
            words[i] = (words[i] ^ (words[i - 1] ^ (words[i - 1] >> 30)).wrapping_mul(1566083941))
                .wrapping_sub(i as u32);
            i += 1;
            if i == 624 {
                words[0] = words[623];
                i = 1;
            }
        }
        words[0] = 0x80000000;
        Self {
            words,
            index: 624,
            gauss_next: None,
        }
    }
    pub fn from_state(state: &RandomState) -> Result<Self, String> {
        if state.words.len() != 624
            || state.index > 624
            || state.gauss_next.is_some_and(|v| !v.is_finite())
        {
            return Err("invalid CPython MT19937 state".into());
        }
        let words = state
            .words
            .as_slice()
            .try_into()
            .map_err(|_| "invalid MT words")?;
        Ok(Self {
            words,
            index: state.index,
            gauss_next: state.gauss_next,
        })
    }
    pub fn state(&self) -> RandomState {
        RandomState {
            words: self.words.to_vec(),
            index: self.index,
            gauss_next: self.gauss_next,
        }
    }
    fn next_u32(&mut self) -> u32 {
        if self.index == 624 {
            for i in 0..624 {
                let y = (self.words[i] & 0x80000000) | (self.words[(i + 1) % 624] & 0x7fffffff);
                self.words[i] = self.words[(i + 397) % 624]
                    ^ (y >> 1)
                    ^ if y & 1 != 0 { 0x9908b0df } else { 0 };
            }
            self.index = 0;
        }
        let mut y = self.words[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^ (y >> 18)
    }
    pub fn random(&mut self) -> f64 {
        let a = self.next_u32() >> 5;
        let b = self.next_u32() >> 6;
        (a as f64 * 67108864.0 + b as f64) * (1.0 / 9007199254740992.0)
    }
    /// CPython takes high bits for a short final word, in little-endian word order.
    pub fn getrandbits(&mut self, bits: u32) -> Result<u64, String> {
        if bits > 64 {
            return Err("getrandbits kernel width exceeds 64".into());
        }
        if bits == 0 {
            return Ok(0);
        }
        if bits <= 32 {
            return Ok((self.next_u32() >> (32 - bits)) as u64);
        }
        let lo = self.next_u32() as u64;
        Ok(lo | (((self.next_u32() >> (64 - bits)) as u64) << 32))
    }
    pub fn randbelow(&mut self, n: u64) -> Result<u64, String> {
        if n == 0 {
            return Err("empty random range".into());
        }
        let bits = 64 - n.leading_zeros();
        loop {
            let r = self.getrandbits(bits)?;
            if r < n {
                return Ok(r);
            }
        }
    }
    pub fn randint(&mut self, lo: i64, hi: i64) -> Result<i64, String> {
        let span = hi as i128 - lo as i128 + 1;
        if span <= 0 || span > u64::MAX as i128 {
            return Err("invalid randint range".into());
        }
        Ok((lo as i128 + self.randbelow(span as u64)? as i128) as i64)
    }
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.random()
    }
    pub fn shuffle<T>(&mut self, values: &mut [T]) {
        for i in (1..values.len()).rev() {
            let j = self
                .randbelow((i + 1) as u64)
                .expect("nonempty shuffle range") as usize;
            values.swap(i, j);
        }
    }
}

pub struct DomainRng {
    root: String,
    streams: BTreeMap<String, PyRandom>,
}
impl DomainRng {
    pub fn new(root: &str, states: BTreeMap<String, RandomState>) -> Result<Self, String> {
        Ok(Self {
            root: canonical_seed(root)?,
            streams: states
                .into_iter()
                .map(|(k, v)| Ok((k, PyRandom::from_state(&v)?)))
                .collect::<Result<_, String>>()?,
        })
    }
    pub fn get(&mut self, domain: &str) -> &mut PyRandom {
        self.streams.entry(domain.into()).or_insert_with(|| {
            PyRandom::seed_u64(domain_seed(&self.root, domain).expect("validated seed"))
        })
    }
    pub fn states(&self) -> BTreeMap<String, RandomState> {
        self.streams
            .iter()
            .map(|(k, v)| (k.clone(), v.state()))
            .collect()
    }
    pub fn trial(&self, domain: &str) -> PyRandom {
        self.streams.get(domain).cloned().unwrap_or_else(|| {
            PyRandom::seed_u64(domain_seed(&self.root, domain).expect("validated seed"))
        })
    }
    pub fn commit(&mut self, domain: String, stream: PyRandom) {
        self.streams.insert(domain, stream);
    }
}
