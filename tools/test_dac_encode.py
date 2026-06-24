import numpy as np
from dac_encode import encode_dpcm, decode_dpcm, DELTA_TABLES

def test_roundtrip_wraps_no_clamp():
    # decode(encode(x)) tracks the signal within the table's quantization; the
    # decoder is pure mod-256 wrap with NO clamp branch.
    x = (np.sin(np.linspace(0, 40*np.pi, 2000)) * 110 + 128).astype(np.uint8)
    nibbles, ti = encode_dpcm(x, seed=0x80)            # returns (packed_bytes, table_index)
    assert isinstance(ti, int) and 0 <= ti < len(DELTA_TABLES)
    y = decode_dpcm(nibbles, DELTA_TABLES[ti], seed=0x80)
    assert len(y) == len(x)
    assert np.corrcoef(x.astype(float), y.astype(float))[0, 1] > 0.95

def test_decode_is_pure_wrap():
    table = DELTA_TABLES[0]
    out = decode_dpcm(bytes([0x00]), table, seed=0x80)  # one byte = 2 nibbles
    exp0 = (0x80 + table[0]) & 0xFF
    exp1 = (exp0 + table[0]) & 0xFF
    assert list(out) == [exp0, exp1]
