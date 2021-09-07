import numpy as np
import pandas as pd
import os
import pytest

from oemof_b3.tools.data_processing import stack_timeseries, unstack_timeseries

ts_row_wise_cols = [
    "var_name",
    "timeindex_start",
    "timeindex_stop",
    "timeindex_resolution",
    "series",
]

ts_column_wise = pd.DataFrame(
    np.random.randint(0, 10, size=(25, 3)),
    columns=list("ABC"),
    index=pd.date_range("2021-01-01", "2021-01-02", freq="H"),
)

ts_column_wise_different = pd.DataFrame(
    np.random.randint(0, 5, size=(25, 3)),
    columns=list("ABC"),
    index=pd.date_range("2021-01-01", "2021-01-02", freq="H"),
)


def test_stack():

    ts_row_wise = stack_timeseries(ts_column_wise)

    assert list(ts_row_wise.columns) == ts_row_wise_cols


def test_unstack():

    ts_row_wise = stack_timeseries(ts_column_wise)
    ts_column_wise_again = unstack_timeseries(ts_row_wise)

    # Test will error out if the frames are not equal
    pd.testing.assert_frame_equal(ts_column_wise_again, ts_column_wise)

    # In case the test does not error out it is None. Hence a passed test results
    # to None
    assert pd.testing.assert_frame_equal(ts_column_wise_again, ts_column_wise) is None
    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(ts_column_wise_again, ts_column_wise_different)


def test_stack_unstack_on_example_data():
    this_path = os.path.realpath(__file__)
    file_path = os.path.join(
        os.path.abspath(os.path.join(this_path, os.pardir)),
        "_files",
        "test_sequence.csv",
    )

    df = pd.read_csv(file_path, index_col=0)
    df.index = pd.to_datetime(df.index)

    df_stacked = stack_timeseries(df)
    df_unstacked = unstack_timeseries(df_stacked)
    assert pd.testing.assert_frame_equal(df, df_unstacked) is None