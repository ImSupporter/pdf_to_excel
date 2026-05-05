import sys
from types import SimpleNamespace


def test_get_reader_enables_gpu_when_cuda_is_available(monkeypatch):
    from core import ocr

    calls = []

    def fake_reader(languages, gpu):
        calls.append((languages, gpu))
        return object()

    monkeypatch.setattr(ocr, "_reader", None)
    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=fake_reader))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)),
    )

    ocr._get_reader()

    assert calls == [(["ko", "en"], True)]


def test_get_reader_uses_cpu_when_cuda_is_unavailable(monkeypatch):
    from core import ocr

    calls = []

    def fake_reader(languages, gpu):
        calls.append((languages, gpu))
        return object()

    monkeypatch.setattr(ocr, "_reader", None)
    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=fake_reader))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False),
            backends=SimpleNamespace(
                mps=SimpleNamespace(is_available=lambda: False),
            ),
        ),
    )

    ocr._get_reader()

    assert calls == [(["ko", "en"], False)]


def test_get_reader_enables_gpu_when_mps_is_available(monkeypatch):
    from core import ocr

    calls = []

    def fake_reader(languages, gpu):
        calls.append((languages, gpu))
        return object()

    monkeypatch.setattr(ocr, "_reader", None)
    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=fake_reader))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False),
            backends=SimpleNamespace(
                mps=SimpleNamespace(is_available=lambda: True),
            ),
        ),
    )

    ocr._get_reader()

    assert calls == [(["ko", "en"], True)]
