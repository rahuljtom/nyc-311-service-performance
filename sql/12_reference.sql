-- Reference table joined to requests by ZIP: the NYC Heat Vulnerability Index (1 = least, 5 = most vulnerable).
-- __REF_DIR__ is replaced by src/pipeline.py; the file comes from src/download_reference.py.
create or replace table ref_hvi as
select
    lpad(trim(zip), 5, '0') as zip,
    try_cast(hvi as integer) as hvi
from read_csv('__REF_DIR__/hvi_zcta.csv', header = true, all_varchar = true);
