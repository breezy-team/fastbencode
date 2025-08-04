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

#[pymethods]
impl Decoder {
    #[new]
    fn new(
        s: &Bound<PyBytes>,
        yield_tuples: Option<bool>,
        bytestring_encoding: Option<String>,
    ) -> Self {
        Decoder {
            data: s.as_bytes().to_vec(),
            position: 0,
            yield_tuples: yield_tuples.unwrap_or(false),
            bytestring_encoding,
        }
    }

    fn decode<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let result = self.decode_object(py)?;
        if self.position < self.data.len() {
            return Err(PyValueError::new_err("junk in stream"));
        }
        Ok(result)
    }

    fn decode_object<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        if self.position >= self.data.len() {
            return Err(PyValueError::new_err("stream underflow"));
        }

        // Check for recursion - in a real implementation we would track recursion depth
        let next_byte = self.data[self.position];

        match next_byte {
            b'0'..=b'9' => Ok(self.decode_bytes(py)?.into_any()),
            b'l' => {
                self.position += 1;
                Ok(self.decode_list(py)?.into_any())
            }
            b'i' => {
                self.position += 1;
                Ok(self.decode_int(py)?.into_any())
            }
            b'd' => {
                self.position += 1;
                Ok(self.decode_dict(py)?.into_any())
            }
            _ => Err(PyValueError::new_err(format!(
                "unknown object type identifier {:?}",
                next_byte as char
            ))),
        }
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
            Ok(PyString::from_object(&bytes_obj, encoding, "strict")?.into_any())
        } else {
            Ok(bytes_obj)
        }
    }

    fn decode_list<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let mut result = Vec::new();

        while self.position < self.data.len() && self.data[self.position] != b'e' {
            let item = self.decode_object(py)?;
            result.push(item);
        }

        if self.position >= self.data.len() {
            return Err(PyValueError::new_err("malformed list"));
        }

        // Skip the 'e'
        self.position += 1;

        if self.yield_tuples {
            let tuple = PyTuple::new(py, &result)?;
            Ok(tuple.into_any())
        } else {
            let list = PyList::new(py, &result)?;
            Ok(list.into_any())
        }
    }

    fn decode_dict<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        let mut last_key: Option<Vec<u8>> = None;

        while self.position < self.data.len() && self.data[self.position] != b'e' {
            // Keys should be strings only
            if self.data[self.position] < b'0' || self.data[self.position] > b'9' {
                return Err(PyValueError::new_err("key was not a simple string"));
            }

            // Decode key as bytes
            let key_obj = self.decode_bytes(py)?;

            // Get bytes representation for comparison
            let key_bytes = if let Some(encoding) = &self.bytestring_encoding {
                if encoding == "utf-8" {
                    let key_str = key_obj.extract::<&str>()?;
                    key_str.as_bytes().to_vec()
                } else {
                    let key_bytes = key_obj.extract::<Bound<PyBytes>>()?;
                    key_bytes.as_bytes().to_vec()
                }
            } else {
                let key_bytes = key_obj.extract::<Bound<PyBytes>>()?;
                key_bytes.as_bytes().to_vec()
            };

            // Check key ordering
            if let Some(ref last) = last_key {
                if last >= &key_bytes {
                    return Err(PyValueError::new_err("dict keys disordered"));
                }
            }

            last_key = Some(key_bytes);

            // Decode value
            let value = self.decode_object(py)?;

            // Insert into dictionary
            dict.set_item(key_obj, value)?;
        }

        if self.position >= self.data.len() {
            return Err(PyValueError::new_err("malformed dict"));
        }

        // Skip the 'e'
        self.position += 1;

        Ok(dict)
    }
}

#[pyclass]
struct Encoder {
    buffer: Vec<u8>,
    bytestring_encoding: Option<String>,
}

#[pymethods]
impl Encoder {
    #[new]
    fn new(_maxsize: Option<usize>, bytestring_encoding: Option<String>) -> Self {
        Encoder {
            buffer: Vec::new(),
            bytestring_encoding,
        }
    }

    fn to_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.buffer)
    }

    fn process(&mut self, py: Python, x: Bound<PyAny>) -> PyResult<()> {
        if let Ok(s) = x.extract::<Bound<PyBytes>>() {
            self.encode_bytes(s)?;
        } else if let Ok(n) = x.extract::<i64>() {
            self.encode_int(n)?;
        } else if let Ok(n) = x.extract::<Bound<PyInt>>() {
            self.encode_long(n)?;
        } else if x.is_instance_of::<PyList>() {
            self.encode_list(py, x)?;
        } else if x.is_instance_of::<PyTuple>() {
            self.encode_list(py, x)?;
        } else if let Ok(d) = x.extract::<Bound<PyDict>>() {
            self.encode_dict(py, d)?;
        } else if let Ok(b) = x.extract::<bool>() {
            self.encode_int(if b { 1 } else { 0 })?;
        } else if let Ok(obj) = x.extract::<PyRef<Bencached>>() {
            self.append_bytes(obj.as_bytes(py)?)?;
        } else if let Ok(s) = x.extract::<&str>() {
            self.encode_string(s)?;
        } else {
            return Err(PyTypeError::new_err(format!("unsupported type: {:?}", x)));
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

    fn encode_list(&mut self, py: Python, sequence: Bound<PyAny>) -> PyResult<()> {
        self.buffer.push(b'l');

        for item in sequence.try_iter()? {
            self.process(py, item?.into())?;
        }

        self.buffer.push(b'e');
        Ok(())
    }

    fn encode_dict(&mut self, py: Python, dict: Bound<PyDict>) -> PyResult<()> {
        self.buffer.push(b'd');

        // Get all keys and sort them
        let mut keys: Vec<Bound<PyBytes>> = dict
            .keys()
            .iter()
            .map(|key| key.extract::<Bound<PyBytes>>())
            .collect::<PyResult<Vec<_>>>()?;
        keys.sort_by(|a, b| {
            let a_str = a.extract::<&[u8]>().unwrap();
            let b_str = b.extract::<&[u8]>().unwrap();
            a_str.cmp(b_str)
        });

        for key in keys {
            if let Ok(bytes) = key.extract::<Bound<PyBytes>>() {
                self.encode_bytes(bytes)?;
            } else {
                return Err(PyTypeError::new_err("key in dict should be string"));
            }

            if let Some(value) = dict.get_item(key)? {
                self.process(py, value.into())?;
            }
        }

        self.buffer.push(b'e');
        Ok(())
    }
}

#[pyfunction]
fn bdecode<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, None, None);
    decoder.decode(py)
}

#[pyfunction]
fn bdecode_as_tuple<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, Some(true), None);
    decoder.decode(py)
}

#[pyfunction]
fn bdecode_utf8<'py>(py: Python<'py>, s: &Bound<PyBytes>) -> PyResult<Bound<'py, PyAny>> {
    let mut decoder = Decoder::new(s, None, Some("utf-8".to_string()));
    decoder.decode(py)
}

#[pyfunction]
fn bencode(py: Python, x: Bound<PyAny>) -> PyResult<PyObject> {
    let mut encoder = Encoder::new(None, None);
    encoder.process(py, x)?;
    Ok(encoder.to_bytes(py).into())
}

#[pyfunction]
fn bencode_utf8(py: Python, x: Bound<PyAny>) -> PyResult<PyObject> {
    let mut encoder = Encoder::new(None, Some("utf-8".to_string()));
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
