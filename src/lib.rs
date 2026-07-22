#![allow(non_snake_case)]
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyInt, PyList, PyString, PyTuple};

#[pyclass]
struct Bencached {
    #[pyo3(get)]
    bencoded: Py<PyBytes>,
}

#[pymethods]
impl Bencached {
    #[new]
    fn new(s: Py<PyBytes>) -> Self {
        Bencached { bencoded: s }
    }

    fn as_bytes(&self, py: Python) -> PyResult<&[u8]> {
        Ok(self.bencoded.as_bytes(py))
    }
}

#[pyclass]
struct Decoder {
    data: Vec<u8>,
    position: usize,
    yield_tuples: bool,
    bytestring_encoding: Option<String>,
}

// A container being built up during iterative decoding.
enum Frame<'py> {
    List(Vec<Bound<'py, PyAny>>),
    Dict {
        dict: Bound<'py, PyDict>,
        pending_key: Option<Bound<'py, PyAny>>,
        last_key: Option<Vec<u8>>,
    },
}

impl<'py> Frame<'py> {
    fn into_value(self, py: Python<'py>, yield_tuples: bool) -> PyResult<Bound<'py, PyAny>> {
        match self {
            Frame::List(items) => {
                if yield_tuples {
                    Ok(PyTuple::new(py, &items)?.into_any())
                } else {
                    Ok(PyList::new(py, &items)?.into_any())
                }
            }
            Frame::Dict { dict, .. } => Ok(dict.into_any()),
        }
    }
}

#[pymethods]
impl Decoder {
    #[new]
    fn new(
        s: &Bound<PyBytes>,
        yield_tuples: Option<bool>,
        bytestring_encoding: Option<String>,
    ) -> PyResult<Self> {
        Ok(Decoder {
            data: s.as_bytes().to_vec(),
            position: 0,
            yield_tuples: yield_tuples.unwrap_or(false),
            bytestring_encoding,
        })
    }

    fn decode<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let result = self.decode_object(py)?;
        if self.position < self.data.len() {
            return Err(PyValueError::new_err("junk in stream"));
        }
        Ok(result)
    }

    // Decode a single bencode value using an explicit work-stack rather than
    // recursion, so that deeply nested input raises ValueError instead of
    // overflowing the native stack.
    fn decode_object<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let mut stack: Vec<Frame<'py>> = Vec::new();

        loop {
            if self.position >= self.data.len() {
                return Err(PyValueError::new_err("stream underflow"));
            }

            let next_byte = self.data[self.position];

            // When the innermost container is a dict awaiting a key, that key
            // must be a simple byte string. A dict awaiting a value must not
            // be terminated before the value is supplied.
            if let Some(Frame::Dict { pending_key, .. }) = stack.last() {
                if pending_key.is_none() {
                    if next_byte != b'e' && !next_byte.is_ascii_digit() {
                        return Err(PyValueError::new_err("key was not a simple string"));
                    }
                } else if next_byte == b'e' {
                    return Err(PyValueError::new_err(format!(
                        "unknown object type identifier {:?}",
                        next_byte as char
                    )));
                }
            }

            // A closing 'e' finishes the innermost container; anything else
            // produces a value that we then attach to the enclosing container.
            let value = if next_byte == b'e' {
                match stack.pop() {
                    Some(frame) => {
                        self.position += 1;
                        frame.into_value(py, self.yield_tuples)?
                    }
                    None => {
                        return Err(PyValueError::new_err(format!(
                            "unknown object type identifier {:?}",
                            next_byte as char
                        )));
                    }
                }
            } else {
                match next_byte {
                    b'0'..=b'9' => self.decode_bytes(py)?,
                    b'i' => {
                        self.position += 1;
                        self.decode_int(py)?
                    }
                    b'l' => {
                        self.position += 1;
                        stack.push(Frame::List(Vec::new()));
                        continue;
                    }
                    b'd' => {
                        self.position += 1;
                        stack.push(Frame::Dict {
                            dict: PyDict::new(py),
                            pending_key: None,
                            last_key: None,
                        });
                        continue;
                    }
                    _ => {
                        return Err(PyValueError::new_err(format!(
                            "unknown object type identifier {:?}",
                            next_byte as char
                        )));
                    }
                }
            };

            match stack.last_mut() {
                None => return Ok(value),
                Some(Frame::List(items)) => items.push(value),
                Some(Frame::Dict {
                    pending_key,
                    last_key,
                    ..
                }) => {
                    if pending_key.is_none() {
                        // This value is a key; it must be a byte string.
                        let key_bytes = self.key_bytes(&value)?;
                        if let Some(last) = last_key {
                            if *last >= key_bytes {
                                return Err(PyValueError::new_err("dict keys disordered"));
                            }
                        }
                        *last_key = Some(key_bytes);
                        *pending_key = Some(value);
                    } else {
                        let key = pending_key.take().unwrap();
                        if let Some(Frame::Dict { dict, .. }) = stack.last() {
                            dict.set_item(key, value)?;
                        }
                    }
                }
            }
        }
    }

    // Extract the raw key bytes from a decoded key object for ordering checks.
    fn key_bytes(&self, key_obj: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
        if let Some(encoding) = &self.bytestring_encoding {
            if encoding == "utf-8" {
                return Ok(key_obj.extract::<&str>()?.as_bytes().to_vec());
            }
        }
        Ok(key_obj.extract::<Bound<PyBytes>>()?.as_bytes().to_vec())
    }

    fn read_digits(&mut self, stop_char: u8) -> PyResult<String> {
        let start = self.position;
        while self.position < self.data.len() {
            let b = self.data[self.position];
            if b == stop_char {
                break;
            }
            if (b < b'0' || b > b'9') && b != b'-' {
                return Err(PyValueError::new_err(format!(
                    "Stop character {} not found: {}",
                    stop_char as char, b as char
                )));
            }
            self.position += 1;
        }

        if self.position >= self.data.len() || self.data[self.position] != stop_char {
            return Err(PyValueError::new_err(format!(
                "Stop character {} not found",
                stop_char as char
            )));
        }

        // Check for leading zeros
        if self.data[start] == b'0' && self.position - start > 1 {
            return Err(PyValueError::new_err("leading zeros are not allowed"));
        } else if self.data[start] == b'-'
            && self.data[start + 1] == b'0'
            && self.position - start > 2
        {
            return Err(PyValueError::new_err("leading zeros are not allowed"));
        }

        Ok(String::from_utf8_lossy(&self.data[start..self.position]).to_string())
    }

    fn decode_int<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let digits = self.read_digits(b'e')?;

        // Move past the 'e'
        self.position += 1;

        // Check for negative zero
        if digits == "-0" {
            return Err(PyValueError::new_err("negative zero not allowed"));
        }

        // Parse the integer directly
        let parsed_int = match digits.parse::<i64>() {
            Ok(n) => n.into_pyobject(py)?.into_any(),
            Err(_) => {
                // For very large integers, fallback to Python's conversion
                let py_str = PyString::new(py, &digits);

                let int_type = py.get_type::<PyInt>();
                int_type.call1((py_str,))?
            }
        };

        Ok(parsed_int.into_any())
    }

    fn decode_bytes<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let len_end_pos = self.data[self.position..].iter().position(|&b| b == b':');
        if len_end_pos.is_none() {
            return Err(PyValueError::new_err("string len not terminated by \":\""));
        }

        let len_end_pos = len_end_pos.unwrap() + self.position;
        let len_str = std::str::from_utf8(&self.data[self.position..len_end_pos])
            .map_err(|_| PyValueError::new_err("invalid length string"))?;

        // Check for leading zeros in the length
        if len_str.starts_with('0') && len_str.len() > 1 {
            return Err(PyValueError::new_err("leading zeros are not allowed"));
        }

        let length: usize = len_str
            .parse()
            .map_err(|_| PyValueError::new_err("invalid length value"))?;

        // Skip past the ':' character
        self.position = len_end_pos + 1;

        if length > self.data.len() - self.position {
            return Err(PyValueError::new_err("stream underflow"));
        }

        let bytes_slice = &self.data[self.position..self.position + length];
        self.position += length;

        let bytes_obj = PyBytes::new(py, bytes_slice).into_any();

        // Return as bytes or decode depending on bytestring_encoding
        if let Some(encoding) = &self.bytestring_encoding {
            let encoding_cstr = std::ffi::CString::new(encoding.as_str())
                .map_err(|_| PyValueError::new_err("invalid encoding string"))?;
            Ok(
                PyString::from_encoded_object(&bytes_obj, Some(&encoding_cstr), Some(c"strict"))?
                    .into_any(),
            )
        } else {
            Ok(bytes_obj)
        }
    }
}

#[pyclass]
struct Encoder {
    buffer: Vec<u8>,
    bytestring_encoding: Option<String>,
}

// A unit of pending encoding work. Containers push their children as Encode
// tasks followed by a CloseContainer, so encoding stays iterative.
enum Task<'py> {
    Encode(Bound<'py, PyAny>),
    CloseContainer,
}

#[pymethods]
impl Encoder {
    #[new]
    fn new(
        _py: Python,
        _maxsize: Option<usize>,
        bytestring_encoding: Option<String>,
    ) -> PyResult<Self> {
        Ok(Encoder {
            buffer: Vec::new(),
            bytestring_encoding,
        })
    }

    fn to_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.buffer)
    }

    // Encode a value using an explicit work-stack rather than recursion, so
    // that deeply nested input does not overflow the native stack.
    fn process<'py>(&mut self, py: Python<'py>, x: Bound<'py, PyAny>) -> PyResult<()> {
        let mut stack: Vec<Task<'py>> = vec![Task::Encode(x)];

        while let Some(task) = stack.pop() {
            let x = match task {
                Task::CloseContainer => {
                    self.buffer.push(b'e');
                    continue;
                }
                Task::Encode(x) => x,
            };

            if let Ok(s) = x.extract::<Bound<PyBytes>>() {
                self.encode_bytes(s)?;
            } else if let Ok(n) = x.extract::<i64>() {
                self.encode_int(n)?;
            } else if let Ok(n) = x.extract::<Bound<PyInt>>() {
                self.encode_long(n)?;
            } else if x.is_instance_of::<PyList>() || x.is_instance_of::<PyTuple>() {
                self.push_list(&mut stack, x)?;
            } else if let Ok(d) = x.extract::<Bound<PyDict>>() {
                self.push_dict(&mut stack, d)?;
            } else if let Ok(b) = x.extract::<bool>() {
                self.encode_int(if b { 1 } else { 0 })?;
            } else if let Ok(obj) = x.extract::<PyRef<Bencached>>() {
                self.append_bytes(obj.as_bytes(py)?)?;
            } else if let Ok(s) = x.extract::<&str>() {
                self.encode_string(s)?;
            } else {
                return Err(PyTypeError::new_err(format!("unsupported type: {:?}", x)));
            }
        }
        Ok(())
    }

    fn encode_int(&mut self, x: i64) -> PyResult<()> {
        let s = format!("i{}e", x);
        self.buffer.extend(s.as_bytes());
        Ok(())
    }

    fn encode_long(&mut self, x: Bound<PyInt>) -> PyResult<()> {
        let s = format!("i{}e", x.str()?);
        self.buffer.extend(s.as_bytes());
        Ok(())
    }

    fn append_bytes(&mut self, bytes: &[u8]) -> PyResult<()> {
        self.buffer.extend(bytes);
        Ok(())
    }

    fn encode_bytes(&mut self, bytes: Bound<PyBytes>) -> PyResult<()> {
        let len_str = format!("{}:", bytes.len()?);
        self.buffer.extend(len_str.as_bytes());
        self.buffer.extend(bytes.as_bytes());
        Ok(())
    }

    fn encode_string(&mut self, x: &str) -> PyResult<()> {
        if let Some(encoding) = &self.bytestring_encoding {
            if encoding == "utf-8" {
                let len_str = format!("{}:", x.len());
                self.buffer.extend(len_str.as_bytes());
                self.buffer.extend(x.as_bytes());
                Ok(())
            } else {
                Err(PyTypeError::new_err(
                    "Only utf-8 encoding is supported for string encoding",
                ))
            }
        } else {
            Err(PyTypeError::new_err(
                "string found but no encoding specified. Use bencode_utf8 rather bencode?",
            ))
        }
    }
}

impl Encoder {
    fn push_list<'py>(
        &mut self,
        stack: &mut Vec<Task<'py>>,
        sequence: Bound<'py, PyAny>,
    ) -> PyResult<()> {
        self.buffer.push(b'l');

        let items: Vec<Bound<PyAny>> = sequence.try_iter()?.collect::<PyResult<Vec<_>>>()?;

        stack.push(Task::CloseContainer);
        for item in items.into_iter().rev() {
            stack.push(Task::Encode(item));
        }
        Ok(())
    }

    fn push_dict<'py>(
        &mut self,
        stack: &mut Vec<Task<'py>>,
        dict: Bound<'py, PyDict>,
    ) -> PyResult<()> {
        self.buffer.push(b'd');

        // Keys must be byte strings; sort them for canonical ordering.
        let mut keys: Vec<Bound<PyBytes>> = dict
            .keys()
            .iter()
            .map(|key| {
                key.extract::<Bound<PyBytes>>()
                    .map_err(|_| PyTypeError::new_err("key in dict should be string"))
            })
            .collect::<PyResult<Vec<_>>>()?;
        keys.sort_by(|a, b| {
            let a_str = a.extract::<&[u8]>().unwrap();
            let b_str = b.extract::<&[u8]>().unwrap();
            a_str.cmp(b_str)
        });

        // Stack key/value pairs in reverse so they pop in key order, each key
        // (a byte string) encoded immediately before its value.
        stack.push(Task::CloseContainer);
        for key in keys.into_iter().rev() {
            let value = dict
                .get_item(&key)?
                .ok_or_else(|| PyTypeError::new_err("dict key vanished during encoding"))?;
            stack.push(Task::Encode(value));
            stack.push(Task::Encode(key.into_any()));
        }
        Ok(())
    }
}

#[pyfunction]
fn bdecode<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, None, None)?;
    decoder.decode(py)
}

#[pyfunction]
fn bdecode_as_tuple<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, Some(true), None)?;
    decoder.decode(py)
}

#[pyfunction]
fn bdecode_utf8<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, None, Some("utf-8".to_string()))?;
    decoder.decode(py)
}

#[pyfunction]
fn bencode(py: Python, x: Bound<PyAny>) -> PyResult<Py<PyAny>> {
    let mut encoder = Encoder::new(py, None, None)?;
    encoder.process(py, x)?;
    Ok(encoder.to_bytes(py).into())
}

#[pyfunction]
fn bencode_utf8(py: Python, x: Bound<PyAny>) -> PyResult<Py<PyAny>> {
    let mut encoder = Encoder::new(py, None, Some("utf-8".to_string()))?;
    encoder.process(py, x)?;
    Ok(encoder.to_bytes(py).into())
}

#[pymodule]
fn _bencode_rs(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<Bencached>()?;
    m.add_class::<Decoder>()?;
    m.add_class::<Encoder>()?;
    m.add_function(wrap_pyfunction!(bdecode, m)?)?;
    m.add_function(wrap_pyfunction!(bdecode_as_tuple, m)?)?;
    m.add_function(wrap_pyfunction!(bdecode_utf8, m)?)?;
    m.add_function(wrap_pyfunction!(bencode, m)?)?;
    m.add_function(wrap_pyfunction!(bencode_utf8, m)?)?;
    Ok(())
}
