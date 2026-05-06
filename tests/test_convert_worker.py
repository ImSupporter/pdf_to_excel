import os
from unittest.mock import MagicMock, call, patch


def _make_worker(file_entries, output_path):
    """QThread.__init__ 없이 ConvertWorker 인스턴스 생성."""
    from ui.main_window import ConvertWorker

    with patch("PyQt6.QtCore.QThread.__init__", return_value=None):
        worker = ConvertWorker.__new__(ConvertWorker)
        worker.file_entries = file_entries
        worker.output_path = output_path
        worker.progress = MagicMock()
        worker.finished = MagicMock()
    return worker


class _FakeParser:
    BROKER_NAME = "테스트증권"

    def parse(self, pages, progress_cb=None):
        for i, _ in enumerate(pages):
            if progress_cb:
                progress_cb(i, len(pages))
        return [], [{"col": "val"}]


def test_progress_resets_to_zero_at_file_start(tmp_path):
    pages = [MagicMock(), MagicMock(), MagicMock()]
    worker = _make_worker([("a/파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    first_call = worker.progress.emit.call_args_list[0]
    assert first_call == call(0, "로딩 중: 파일.pdf")


def test_page_progress_emits_correct_percent_and_label(tmp_path):
    pages = [MagicMock(), MagicMock(), MagicMock()]
    worker = _make_worker([("파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = worker.progress.emit.call_args_list
    # 파일 시작(0%) + 페이지 3개(33,66,100%) + 엑셀(100%) = 5번
    assert emitted[1] == call(33, "파일.pdf 페이지 1/3")
    assert emitted[2] == call(66, "파일.pdf 페이지 2/3")
    assert emitted[3] == call(100, "파일.pdf 페이지 3/3")


def test_second_file_resets_to_zero(tmp_path):
    pages = [MagicMock()]
    worker = _make_worker(
        [("first.pdf", "", _FakeParser), ("second.pdf", "", _FakeParser)],
        str(tmp_path / "out.xlsx"),
    )

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = [args for args, _ in worker.progress.emit.call_args_list]
    # first.pdf: (0, "로딩 중: first.pdf"), (100, "first.pdf 페이지 1/1")
    # second.pdf: (0, "로딩 중: second.pdf"), (100, "second.pdf 페이지 1/1")
    assert emitted[0] == (0, "로딩 중: first.pdf")
    assert emitted[2] == (0, "로딩 중: second.pdf")


def test_excel_step_emits_correct_label(tmp_path):
    pages = [MagicMock()]
    worker = _make_worker([("파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = [args for args, _ in worker.progress.emit.call_args_list]
    assert emitted[-2] == (100, "엑셀 파일 생성 중...")
    assert emitted[-1] == (100, "완료!")


def test_export_error_emits_finished_false(tmp_path):
    pages = [MagicMock()]
    worker = _make_worker([("파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel", side_effect=OSError("디스크 오류")):
        worker.run()

    worker.finished.emit.assert_called_once_with(False, "디스크 오류")
