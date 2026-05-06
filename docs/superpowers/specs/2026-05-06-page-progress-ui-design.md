# 페이지 기준 진행 상황 UI 설계

**날짜:** 2026-05-06  
**상태:** 승인됨

## 목표

PDF → Excel 변환 시 진행률을 현재 파일 단위(파일 i/n, 0-80%)에서 **페이지 단위**로 변경한다. 파일이 바뀔 때 progress bar를 0%로 리셋하고, 각 페이지 처리 후 해당 파일 내 진행률(0→100%)과 `{파일명} 페이지 X/Y` 텍스트를 표시한다.

## 요구사항

- 파일 전환 시 progress bar 0%로 리셋
- 각 페이지 처리 완료 후 `int((page_idx + 1) / total_pages * 100)` 값으로 bar 업데이트
- status label: `"{filename} 페이지 {page_idx+1}/{total_pages}"` 형식
- start_page 이전 스킵 페이지도 루프를 통과하며 콜백 호출(진행률이 자연스럽게 올라감)
- Excel 저장 단계: bar 값 유지, 텍스트 "엑셀 파일 생성 중..."
- 완료: bar 100%, 텍스트 "완료!"
- `progress(int, str)` 시그널 구조 변경 없음

## 접근법: progress_cb 콜백

`parse()` 메서드에 `progress_cb=None` 파라미터를 추가한다. `ConvertWorker`가 파일별 람다를 만들어 넘기고, `build_class` 내부 페이지 루프에서 호출한다.

선택 이유: 실제 페이지 처리 시점과 동기화되어 정확하며, 변경 범위가 3개 파일로 최소화된다.

## 수정 파일

### `parsers/base.py`

```python
@abstractmethod
def parse(self, pages, progress_cb=None):
    ...
```

추상 메서드 시그니처에 `progress_cb=None` 추가. 기존 호출 코드는 키워드 인자 미전달이므로 하위 호환 유지.

### `core/parser_registry.py` — `build_class` 내부 `parse()`

```python
def parse(self, pages, progress_cb=None):
    ...
    total_pages = len(pages)
    for page_idx, page in enumerate(pages):
        if page_idx < _cfg.start_page:
            if progress_cb:
                progress_cb(page_idx, total_pages)
            continue
        # 기존 페이지 처리 로직
        ...
        if progress_cb:
            progress_cb(page_idx, total_pages)
    return transactions, raw_rows
```

### `ui/main_window.py` — `ConvertWorker.run()`

```python
def run(self):
    broker_raw = defaultdict(list)
    for path, password, parser_class in self.file_entries:
        filename = os.path.basename(path)
        self.progress.emit(0, f"로딩 중: {filename}")
        try:
            pages = load_pdf(path, password)
        except Exception as e:
            self.finished.emit(False, str(e))
            return

        total_pages = len(pages)

        def make_cb(fn, tp):
            def cb(page_idx, _total):
                pct = int((page_idx + 1) / tp * 100)
                self.progress.emit(pct, f"{fn} 페이지 {page_idx + 1}/{tp}")
            return cb

        try:
            parser = parser_class()
            _transactions, raw_rows = parser.parse(pages, progress_cb=make_cb(filename, total_pages))
            broker_raw[parser_class.BROKER_NAME].extend(raw_rows)
        except Exception as e:
            self.finished.emit(False, str(e))
            return

    self.progress.emit(100, "엑셀 파일 생성 중...")
    try:
        export_to_excel(dict(broker_raw), self.output_path)
    except PermissionError:
        self.finished.emit(False, f"파일이 열려 있습니다. 닫고 다시 시도하세요:\n{self.output_path}")
        return

    self.progress.emit(100, "완료!")
    self.finished.emit(True, self.output_path)
```

`make_cb` 헬퍼로 클로저 캡처 문제를 방지한다(`filename`, `total_pages`를 루프 인자로 바인딩).

## 데이터 흐름

```
ConvertWorker.run()
  for 파일:
      progress.emit(0, "로딩 중: {filename}")
      load_pdf() → list[fitz.Page]
      make_cb(filename, total_pages) → cb
      parser.parse(pages, progress_cb=cb)
        for page_idx in range(total_pages):
            페이지 처리
            cb(page_idx, total_pages)
              └─ progress.emit(pct, "{filename} 페이지 X/Y")
  progress.emit(100, "엑셀 파일 생성 중...")
  export_to_excel()
  progress.emit(100, "완료!")
  finished.emit(True, output_path)
```

## 테스트 포인트

- `ConvertWorker`에 mock parser를 넣어 `progress` 시그널 값 순서 검증
- 첫 번째 emit이 `(0, "로딩 중: ...")` 인지 확인
- 페이지 3개짜리 파일: emit 값이 `33, 66, 100`% 순서인지 확인
- start_page=1인 파서: 스킵 페이지도 콜백 호출되는지 확인
- 파일 2개 이상: 두 번째 파일 시작 시 0%로 리셋되는지 확인
