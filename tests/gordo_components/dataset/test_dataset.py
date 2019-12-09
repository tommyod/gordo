# -*- coding: utf-8 -*-

from typing import List, Iterable, Optional

import pytest
import numpy as np
import pandas as pd
import dateutil.parser
from datetime import datetime

from gordo_components.data_provider.base import GordoBaseDataProvider
from gordo_components.dataset.datasets import RandomDataset, TimeSeriesDataset
from gordo_components.dataset.base import GordoBaseDataset
from gordo_components.dataset.sensor_tag import SensorTag


def create_timeseries_list():
    """Create three dataframes with different resolution and different start/ends"""
    # Test for no NaNs, test for correct first and last date
    latest_start = "2018-01-03 06:00:00Z"
    earliest_end = "2018-01-05 06:00:00Z"

    index_seconds = pd.date_range(
        start="2018-01-01 06:00:00Z", end="2018-01-07 06:00:00Z", freq="S"
    )
    index_minutes = pd.date_range(
        start="2017-12-28 06:00:00Z", end=earliest_end, freq="T"
    )
    index_hours = pd.date_range(
        start=latest_start, end="2018-01-12 06:00:00Z", freq="H"
    )

    timeseries_seconds = pd.Series(
        data=np.random.randint(0, 100, len(index_seconds)),
        index=index_seconds,
        name="ts-seconds",
    )
    timeseries_minutes = pd.Series(
        data=np.random.randint(0, 100, len(index_minutes)),
        index=index_minutes,
        name="ts-minutes",
    )
    timeseries_hours = pd.Series(
        data=np.random.randint(0, 100, len(index_hours)),
        index=index_hours,
        name="ts-hours",
    )

    return (
        [timeseries_seconds, timeseries_minutes, timeseries_hours],
        latest_start,
        earliest_end,
    )


def test_random_dataset_attrs():
    """
    Test expected attributes
    """

    start = dateutil.parser.isoparse("2017-12-25 06:00:00Z")
    end = dateutil.parser.isoparse("2017-12-29 06:00:00Z")

    dataset = RandomDataset(
        from_ts=start,
        to_ts=end,
        tag_list=[SensorTag("Tag 1", None), SensorTag("Tag 2", None)],
    )

    assert isinstance(dataset, GordoBaseDataset)
    assert hasattr(dataset, "get_data")
    assert hasattr(dataset, "get_metadata")

    X, y = dataset.get_data()
    assert isinstance(X, pd.DataFrame)

    # y can either be None or an numpy array
    assert isinstance(y, pd.DataFrame) or y is None

    metadata = dataset.get_metadata()
    assert isinstance(metadata, dict)


def test_join_timeseries():

    timeseries_list, latest_start, earliest_end = create_timeseries_list()

    assert len(timeseries_list[0]) > len(timeseries_list[1]) > len(timeseries_list[2])

    frequency = "7T"
    timedelta = pd.Timedelta("7 minutes")
    resampling_start = dateutil.parser.isoparse("2017-12-25 06:00:00Z")
    resampling_end = dateutil.parser.isoparse("2018-01-15 08:00:00Z")
    all_in_frame = GordoBaseDataset.join_timeseries(
        timeseries_list, resampling_start, resampling_end, frequency
    )

    # Check that first resulting resampled, joined row is within "frequency" from
    # the real first data point
    assert all_in_frame.index[0] >= pd.Timestamp(latest_start) - timedelta
    assert all_in_frame.index[-1] <= pd.Timestamp(resampling_end)


def test_join_timeseries_nonutcstart():
    timeseries_list, latest_start, earliest_end = create_timeseries_list()
    frequency = "7T"
    resampling_start = dateutil.parser.isoparse("2017-12-25 06:00:00+07:00")
    resampling_end = dateutil.parser.isoparse("2018-01-12 13:07:00+07:00")
    all_in_frame = GordoBaseDataset.join_timeseries(
        timeseries_list, resampling_start, resampling_end, frequency
    )
    assert len(all_in_frame) == 1854


def test_join_timeseries_with_gaps():

    timeseries_list, latest_start, earliest_end = create_timeseries_list()

    assert len(timeseries_list[0]) > len(timeseries_list[1]) > len(timeseries_list[2])

    remove_from = "2018-01-03 10:00:00Z"
    remove_to = "2018-01-03 18:00:00Z"
    timeseries_with_holes = [
        ts[(ts.index < remove_from) | (ts.index >= remove_to)] for ts in timeseries_list
    ]

    frequency = "10T"
    resampling_start = dateutil.parser.isoparse("2017-12-25 06:00:00Z")
    resampling_end = dateutil.parser.isoparse("2018-01-12 07:00:00Z")

    all_in_frame = GordoBaseDataset.join_timeseries(
        timeseries_with_holes, resampling_start, resampling_end, frequency
    )
    assert all_in_frame.index[0] == pd.Timestamp(latest_start)
    assert all_in_frame.index[-1] == pd.Timestamp(resampling_end)

    expected_index = pd.date_range(
        start=dateutil.parser.isoparse(latest_start), end=resampling_end, freq=frequency
    )
    assert list(all_in_frame.index) == list(expected_index)


def test_row_filter():
    """Tests that row_filter filters away rows"""
    kwargs = dict(
        data_provider=MockDataSource(),
        tag_list=[
            SensorTag("Tag 1", None),
            SensorTag("Tag 2", None),
            SensorTag("Tag 3", None),
        ],
        from_ts=dateutil.parser.isoparse("2017-12-25 06:00:00Z"),
        to_ts=dateutil.parser.isoparse("2017-12-29 06:00:00Z"),
    )
    X, _ = TimeSeriesDataset(**kwargs).get_data()
    assert 577 == len(X)

    X, _ = TimeSeriesDataset(row_filter="'Tag 1' < 5000", **kwargs).get_data()
    assert 8 == len(X)

    X, _ = TimeSeriesDataset(
        row_filter="'Tag 1' / 'Tag 3' < 0.999", **kwargs
    ).get_data()
    assert 3 == len(X)


def test_aggregation_methods():
    """Tests that it works to set aggregation method(s)"""

    kwargs = dict(
        data_provider=MockDataSource(),
        tag_list=[
            SensorTag("Tag 1", None),
            SensorTag("Tag 2", None),
            SensorTag("Tag 3", None),
        ],
        from_ts=dateutil.parser.isoparse("2017-12-25 06:00:00Z"),
        to_ts=dateutil.parser.isoparse("2017-12-29 06:00:00Z"),
    )

    # Default aggregation gives no extra columns
    X, _ = TimeSeriesDataset(**kwargs).get_data()
    assert (577, 3) == X.shape

    # The default single aggregation method gives the tag-names as columns
    assert list(X.columns) == ["Tag 1", "Tag 2", "Tag 3"]

    # Using two aggregation methods give a multi-level column with tag-names
    # on top and aggregation_method as second level
    X, _ = TimeSeriesDataset(aggregation_methods=["mean", "max"], **kwargs).get_data()

    assert (577, 6) == X.shape
    assert list(X.columns) == [
        ("Tag 1", "mean"),
        ("Tag 1", "max"),
        ("Tag 2", "mean"),
        ("Tag 2", "max"),
        ("Tag 3", "mean"),
        ("Tag 3", "max"),
    ]


def test_time_series_no_resolution():
    kwargs = dict(
        data_provider=MockDataSource(),
        tag_list=[
            SensorTag("Tag 1", None),
            SensorTag("Tag 2", None),
            SensorTag("Tag 3", None),
        ],
        from_ts=dateutil.parser.isoparse("2017-12-25 06:00:00Z"),
        to_ts=dateutil.parser.isoparse("2017-12-29 06:00:00Z"),
    )
    no_resolution, _ = TimeSeriesDataset(resolution=None, **kwargs).get_data()
    wi_resolution, _ = TimeSeriesDataset(resolution="10T", **kwargs).get_data()
    assert len(no_resolution) > len(wi_resolution)


@pytest.mark.parametrize(
    "tag_list",
    [
        [SensorTag("Tag 1", None), SensorTag("Tag 2", None), SensorTag("Tag 3", None)],
        [SensorTag("Tag 1", None)],
    ],
)
@pytest.mark.parametrize(
    "target_tag_list",
    [
        [SensorTag("Tag 2", None), SensorTag("Tag 1", None), SensorTag("Tag 3", None)],
        [SensorTag("Tag 1", None)],
        [SensorTag("Tag10", None)],
        [],
    ],
)
def test_timeseries_target_tags(tag_list, target_tag_list):
    start = dateutil.parser.isoparse("2017-12-25 06:00:00Z")
    end = dateutil.parser.isoparse("2017-12-29 06:00:00Z")
    tsd = TimeSeriesDataset(
        start,
        end,
        tag_list=tag_list,
        target_tag_list=target_tag_list,
        data_provider=MockDataSource(),
    )
    X, y = tsd.get_data()

    # If we have targets, y and X should be equal length and axis=1 == N in target tag list
    if target_tag_list:
        assert len(X) == len(y)
        assert y.shape[1] == len(target_tag_list)

        # Ensure the order in maintained
        assert [tag.name for tag in target_tag_list] == y.columns.tolist()
    else:
        assert y is None

    # Features should match the tag_list
    assert X.shape[1] == len(tag_list)

    # Ensure the order in maintained
    assert [tag.name for tag in tag_list] == X.columns.tolist()


class MockDataSource(GordoBaseDataProvider):
    def __init__(self, **kwargs):
        pass

    def can_handle_tag(self, tag):
        return True

    def load_series(
        self,
        from_ts: datetime,
        to_ts: datetime,
        tag_list: List[SensorTag],
        dry_run: Optional[bool] = False,
    ) -> Iterable[pd.Series]:
        days = pd.date_range(from_ts, to_ts, freq="s")
        tag_list_strings = sorted([tag.name for tag in tag_list])
        for i, name in enumerate(tag_list_strings):
            series = pd.Series(
                index=days, data=list(range(i, len(days) + i)), name=name
            )
            yield series


def test_timeseries_dataset_compat():
    """
    There are accepted keywords in the config file when using type: TimeSeriesDataset
    which don't actually match the kwargs of the dataset's __init__; for compatibility
    :func:`gordo_components.dataset.datasets.compat` should adjust for these differences.
    """
    dataset = TimeSeriesDataset(
        data_provider=MockDataSource(),
        train_start_date="2017-12-25 06:00:00Z",
        train_end_date="2017-12-29 06:00:00Z",
        tags=[SensorTag("Tag 1", None)],
    )
    assert dataset.from_ts == dateutil.parser.isoparse("2017-12-25 06:00:00Z")
    assert dataset.to_ts == dateutil.parser.isoparse("2017-12-29 06:00:00Z")
    assert dataset.tag_list == [SensorTag("Tag 1", None)]
