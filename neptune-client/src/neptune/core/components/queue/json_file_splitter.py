#
# Copyright (c) 2022, Neptune Labs Sp. z o.o.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
__all__ = ["JsonFileSplitter"]

from collections import deque
from io import StringIO
from json import (
    JSONDecodeError,
    JSONDecoder,
)
from pathlib import Path
from types import TracebackType
from typing import (
    IO,
    Any,
    Deque,
    Optional,
    Tuple,
    Type,
    Union,
)


class JsonFileSplitter:
    BUFFER_SIZE = 64 * 1024
    MAX_PART_READ = 8 * 1024

    def __init__(self, file_path: Union[str, Path]):
        self._file: IO = open(file_path, "r")
        self._decoder: JSONDecoder = JSONDecoder(strict=False)
        self._part_buffer: StringIO = StringIO()
        self._parsed_queue: Deque[Tuple[Any, int]] = deque()
        self._start_pos: int = 0

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
        if not self._part_buffer.closed:
            self._part_buffer.close()

    def get(self) -> Optional[dict]:
        return (self.get_with_size() or (None, None))[0]

    def get_with_size(self) -> Tuple[Optional[dict], int]:
        if self._parsed_queue:
            return self._parsed_queue.popleft()
        self._read_data()
        if self._parsed_queue:
            return self._parsed_queue.popleft()
        return None, 0

    def _read_data(self) -> None:
        if self._part_buffer.tell() < self.MAX_PART_READ:
            data = self._file.read(self.BUFFER_SIZE)
            if not data:
                return
            if self._part_buffer.tell() > 0:
                data = self._reset_part_buffer() + data
            self._decode(data)

        if not self._parsed_queue:
            data = self._file.read(self.BUFFER_SIZE)
            while data:
                self._part_buffer.write(data)
                data = self._file.read(self.BUFFER_SIZE)
            data = self._reset_part_buffer()
            self._decode(data)

    def _decode(self, data: str) -> None:
        start = self._json_start(data)
        while start is not None:
            try:
                json_data, new_start = self._decoder.raw_decode(data, start)
                size = new_start - start
                start = new_start
            except JSONDecodeError:
                self._part_buffer.write(data[start:])
                break
            else:
                self._parsed_queue.append((json_data, size))
                start = self._json_start(data, start)

    @staticmethod
    def _json_start(data: str, start: int = 0) -> Optional[int]:
        try:
            return data.index("{", start)
        except ValueError:
            return None

    def _reset_part_buffer(self) -> str:
        data = self._part_buffer.getvalue()
        self._part_buffer.close()
        self._part_buffer = StringIO()
        return data

    def __enter__(self) -> "JsonFileSplitter":
        return self

    def __exit__(
        self,
        exc_type: Type[Optional[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()
