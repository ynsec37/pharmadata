<div align="center">

<em>CDISC SDTM and ADaM Test Datasets in Python for Clinical Programming</em>

[![CI](https://github.com/ynsec37/pharmadata/actions/workflows/ci.yml/badge.svg)](https://github.com/ynsec37/pharmadata/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/ynsec37/pharmadata/branch/main/graph/badge.svg)](https://codecov.io/gh/ynsec37/pharmadata)
[![PyPI](https://img.shields.io/pypi/v/pharmadata.svg)](https://pypi.org/project/pharmadata/)

</div>

## Installation

```bash
pip install pharmadata
```

## Quick start

```python
from pharmadata import pharmaverseadam as adam

adsl = adam.adsl
adsl_meta = adam.adsl_meta

# Other datasets
from pharmadata import pharmaversesdtm, cdiscpilotadam, cdiscpilotsdtm
```

Default output is polars, `set_output_pandas()` switches to pandas.

## Credits

Data from the following projects. They are gratefully acknowledged for making the data available.

- [pharmaverseadam](https://github.com/pharmaverse/pharmaverseadam)
- [pharmaversesdtm](https://github.com/pharmaverse/pharmaversesdtm)
- [phuse-org/phuse-scripts](https://github.com/phuse-org/phuse-scripts)

See [NOTICE](NOTICE)
