"""Custom client handling, including CSVStream base class."""

import csv
import os
from typing import Iterable, List, Optional

from singer_sdk import typing as th
from singer_sdk.streams import Stream
import pandas as pd


class CSVStream(Stream):
    """Stream class for CSV streams."""

    file_paths: List[str] = []

    def __init__(self, *args, **kwargs):
        """Init CSVStream."""
        # cache file_config so we dont need to go iterating the config list again later
        self.file_config = kwargs.pop("file_config")
        super().__init__(*args, **kwargs)

    def get_records(self, context: Optional[dict]) -> Iterable[dict]:
        """Return a generator of row-type dictionary objects.

        The optional `context` argument is used to identify a specific slice of the
        stream if partitioning is required for the stream. Most implementations do not
        require partitioning and should ignore the `context` argument.
        """
        for file_path in self.get_file_paths():
            df = pd.read_csv(file_path, engine="pyarrow",
                             delimiter=self.file_config.get("delimiter", ","),
                             doublequote=self.file_config.get("doublequote", True),
                             escapechar=self.file_config.get("escapechar", None),
                             quotechar=self.file_config.get("quotechar", '"'),
                             skipinitialspace=self.file_config.get("skipinitialspace", False),
                             encoding_errors=self.file_config.get("encoding_errors", False),
                             thousands=self.file_config.get("thousands", None),
                             decimal=self.file_config.get("decimal", "."),
                             encoding = self.file_config.get("encoding", None))
            records = df.to_dict(orient="records")
            for r in records:
                yield r

    def get_file_paths(self) -> list:
        """Return a list of file paths to read.

        This tap accepts file names and directories so it will detect
        directories and iterate files inside.
        """
        # Cache file paths so we dont have to iterate multiple times
        if self.file_paths:
            return self.file_paths

        file_path = self.file_config["path"]
        if not os.path.exists(file_path):
            raise Exception(f"File path does not exist {file_path}")

        file_paths = []
        if os.path.isdir(file_path):
            clean_file_path = os.path.normpath(file_path) + os.sep
            for filename in os.listdir(clean_file_path):
                file_path = clean_file_path + filename
                if self.is_valid_filename(file_path):
                    file_paths.append(file_path)
        else:
            if self.is_valid_filename(file_path):
                file_paths.append(file_path)

        if not file_paths:
            raise Exception(
                f"Stream '{self.name}' has no acceptable files. \
                    See warning for more detail."
            )
        self.file_paths = file_paths
        return file_paths

    def is_valid_filename(self, file_path: str) -> bool:
        """Return a boolean of whether the file includes CSV extension."""
        is_valid = True
        if file_path[-4:] != ".csv":
            is_valid = False
            self.logger.warning(f"Skipping non-csv file '{file_path}'")
            self.logger.warning(
                "Please provide a CSV file that ends with '.csv'; e.g. 'users.csv'"
            )
        return is_valid

    def get_header(self, file_path: str) -> Iterable:
        df = pd.read_csv(file_path,
                         delimiter=self.file_config.get("delimiter", ","),
                         doublequote=self.file_config.get("doublequote", True),
                         escapechar=self.file_config.get("escapechar", None),
                         quotechar=self.file_config.get("quotechar", '"'),
                         skipinitialspace=self.file_config.get("skipinitialspace", False),
                         encoding_errors=self.file_config.get("encoding_errors", False),
                         thousands=self.file_config.get("thousands", None),
                         decimal=self.file_config.get("decimal", "."),
                         encoding=self.file_config.get("encoding", None),
                         nrows=100)
        return df.columns, df.dtypes

    @property
    def schema(self) -> dict:
        """Return dictionary of record schema.

        Dynamically detect the json schema for the stream.
        This is evaluated prior to any records being retrieved.
        """
        properties: List[th.Property] = []
        self.primary_keys = self.file_config.get("keys", [])

        file_path = self.get_file_paths()[0]
        header, data_types = self.get_header(file_path)

        for column in header:
            # Set all types to string
            # TODO: Try to be smarter about inferring types.
            properties.append(th.Property(column, th.StringType()))
        return th.PropertiesList(*properties).to_dict()
