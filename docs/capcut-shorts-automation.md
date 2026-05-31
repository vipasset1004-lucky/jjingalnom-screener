# 캡컷 쇼츠 자동화 — 기획 문서

> 인기 영상에서 **구성·후킹 패턴만 벤치마킹**하고, 내 관점/해설을 얹은
> **변형 콘텐츠(transformative)**를 반자동으로 제작하는 파이프라인 설계.
> 캡컷 조립은 자동, 최종 마감·렌더는 사람이 담당.

## ⚠️ 전제 (반드시 지킬 선)

- **"원본 재업로드 + 감지 회피"는 안 함.** 유튜브 재사용 콘텐츠 정책·Content ID
  위반 → 수익화 거절·삭제·스트라이크. 자동 대량생산이면 더 빨리 잡힘.
- **합법 노선만**: ① 내 목소리/관점 해설(transformative) ② 라이선스 소스
  (Pexels/Pixabay/Storyblocks 등 상업적 사용 가능) ③ 짧은 인용(공정이용 범위).
- 인기 영상은 **소재 영상 자체를 베끼는 대상이 아니라, 주제·구성·훅을 분석하는 대상**.

---

## 1. 전체 파이프라인

```
[1] 벤치마킹     인기 쇼츠 분석 → 주제·구성·후킹 패턴 추출 (영상 X, 메타데이터 O)
       ↓
[2] 대본 생성    Claude API → 내 관점 대본 (씬 단위 JSON)
       ↓
[3] 음성(TTS)    대본 → 나레이션 mp3 + 길이
       ↓
[4] 비주얼       라이선스 소스 + 내 화면/차트 + 짧은 인용 클립 수집
       ↓
[5] 자막         Whisper(STT) → 음성 싱크 SRT
       ↓
[6] 조립         CapCutAPI → draft_content.json 자동 생성 (★ 핵심)
       ↓
[7] 마감         캡컷에서 열어 손질 → 렌더 → 업로드
```

### 단계별 도구·입출력·난이도

| 단계 | 입력 | 처리 | 출력 | 도구 | 난이도 |
|------|------|------|------|------|--------|
| 1 벤치마킹 | 키워드/채널 | 인기 영상 메타 수집·패턴 분석 | `topic.json` | YouTube Data API | ★★☆ |
| 2 대본 | topic | LLM 대본 생성 | `script.json` | Claude API | ★☆☆ |
| 3 TTS | script | 텍스트→음성 | `narration.mp3` | ElevenLabs / 클로바 / Edge-TTS | ★☆☆ |
| 4 비주얼 | script 씬별 키워드 | 클립/이미지 검색·다운로드 | `assets/` + URL목록 | Pexels API 등 | ★★☆ |
| 5 자막 | narration.mp3 | STT 정렬 | `subtitles.srt` | Whisper | ★☆☆ |
| 6 조립 | 위 산출물 전부 | API 호출 시퀀스 번역 | `dfd_xxx/` (캡컷 드래프트) | **CapCutAPI** | ★★★ |
| 7 마감 | 드래프트 | 손질·렌더·업로드 | mp4 / 게시 | 캡컷 + YouTube API | ★★☆ |

---

## 2. 조립 엔진: CapCutAPI

캡컷은 프로젝트를 `draft_content.json`으로 저장. 이 JSON을 코드로 생성해
캡컷 드래프트 폴더에 넣으면 **완성된 편집 프로젝트로 열림**.
[CapCutAPI](https://github.com/renqingfei/CapCutAPI)가 HTTP/MCP로 이를 래핑.

> 공식 API 아님(커뮤니티 오픈소스). 데스크탑(Win/macOS) 대상.
> **렌더는 사람이 캡컷에서** → 무인 100% 아님, "조립 자동 + 마감 수동".

### 동작 흐름
```
create_draft → (add_* 누적 호출) → save_draft → dfd_xxx 폴더 → 캡컷 폴더로 복사
```
`draft_id` 발급 → 트랙을 하나씩 쌓음. 시간은 전부 **초 단위**.

### 11개 도구 스펙

| 도구 | 역할 | 주요 입력 |
|------|------|-----------|
| `create_draft` | 프로젝트 생성 | `width`, `height` → `draft_id` |
| `get_video_duration` | 길이 조회 | `video_url` → 초 |
| `add_video` | 영상 클립 | `video_url`, `start`, `end`, `volume`, `transform_x/y`, `transition` |
| `add_audio` | 오디오/나레이션 | `audio_url`, `volume`, `speed`, `effects[]` |
| `add_image` | 이미지 | `image_url`, `transform`, `animation`, `transition` |
| `add_text` | 텍스트 오버레이 | `text`, `start`, `end`, `font_size`, `font_color`, 그림자/배경 |
| `add_subtitle` | 자막(SRT) | `srt_path`, `font_style`, `position` |
| `add_effect` | 비주얼 효과 | `effect_type`, `parameters`, `duration` |
| `add_sticker` | 스티커 | `resource_id`, `position`, `scale`, `rotation` |
| `add_video_keyframe` | 키프레임 애니 | `track_name`, `property_types[]`, `times[]`, `values[]` |
| `save_draft` | 저장 | `draft_id` → `draft_url` |

**유의점**
- 자막은 **SRT 경로** 통째로 전달 → 5단계 Whisper 출력 그대로 꽂으면 싱크 끝.
- 소스는 전부 **URL** → 로컬 파일은 서빙하거나 업로드 필요(미해결 과제).
- `add_video_keyframe`(`scale_x/scale_y/alpha`)로 줌인·페이드 등 "캡컷st 다이나믹" 부여.

---

## 3. 데이터 계약 (단계 간 인터페이스)

### `script.json` (2단계 출력 → 4·6단계 입력)
```json
{
  "title": "오늘의 갈놈 TOP3",
  "format": "shorts",
  "resolution": [1080, 1920],
  "hook": "이 종목, 3개 스크리너가 동시에 찍었습니다",
  "scenes": [
    { "id": 1, "text": "첫 번째는...", "clip_query": "stock chart bull", "duration": 4.0 },
    { "id": 2, "text": "두 번째는...", "clip_query": "trading desk",      "duration": 4.0 }
  ],
  "outro": "구독하고 매일 갈놈 받아가세요"
}
```

### `assets.json` (4단계 출력 → 6단계 입력)
```json
{
  "narration": { "url": "file:///.../narration.mp3", "duration": 28.4 },
  "subtitles": "file:///.../subtitles.srt",
  "scenes": [
    { "id": 1, "clip_url": "https://.../clip1.mp4", "in": 0.0,  "out": 4.0 },
    { "id": 2, "clip_url": "https://.../clip2.mp4", "in": 4.0,  "out": 8.0 }
  ]
}
```

---

## 4. 연출 오케스트레이터 (의사코드)

> 우리가 새로 짤 코드는 이 **"재료 → API 호출 시퀀스 번역기"** 하나.
> 편집 엔진은 CapCutAPI가, 우리는 **연출 로직**(언제·무엇을·어떤 효과로)만 담당.

### 쇼츠 템플릿 규칙
```
[0 ~ 3s]   훅(HOOK)    : 큰 자막 + 줌인, 강한 첫 문장으로 이탈 방지
[3 ~ Ns]   본문(BODY)  : 씬별 클립 + 나레이션 자막, 씬 전환 시 살짝 줌/페이드
[N ~ end]  아웃트로     : CTA(구독/팔로우) 자막 + 정지 클립
공통        : 나레이션 1트랙 전체 깔고, 자막 SRT 1트랙, BGM 1트랙(저음량)
```

### 의사코드
```python
def assemble(script, assets, capcut):
    W, H = script["resolution"]
    draft = capcut.create_draft(width=W, height=H)
    did = draft["draft_id"]

    # 1) 나레이션 — 전체 길이의 기준 트랙
    narr = assets["narration"]
    capcut.add_audio(draft_id=did, audio_url=narr["url"], volume=1.0)

    # 2) 본문 씬: 클립을 시간축에 순서대로 배치 + 씬마다 줌인 키프레임
    for sc, meta in zip(script["scenes"], assets["scenes"]):
        capcut.add_video(
            draft_id=did, video_url=meta["clip_url"],
            start=meta["in"], end=meta["out"], volume=0.0,   # 원본음 죽이고 나레이션만
            transition="fade_in",
        )
        # "캡컷st" 천천히 줌인 (1.0 → 1.08)
        capcut.add_video_keyframe(
            draft_id=did, track_name="video_main",
            property_types=["scale_x", "scale_y"],
            times=[meta["in"], meta["out"]],
            values=["1.0", "1.08"],
        )

    # 3) 자막 — Whisper SRT 그대로 (싱크 자동)
    capcut.add_subtitle(
        draft_id=did, srt_path=assets["subtitles"],
        font_style="ZY_Courage", position="bottom",
    )

    # 4) 훅 자막 (0~3초, 화면 상단 큰 글씨)
    capcut.add_text(
        draft_id=did, text=script["hook"],
        start=0.0, end=3.0, font_size=64, font_color="#FFE400",
        shadow_enabled=True, shadow_color="#000000",
    )

    # 5) 아웃트로 CTA
    end_t = narr["duration"]
    capcut.add_text(
        draft_id=did, text=script["outro"],
        start=end_t - 3.0, end=end_t, font_size=52, font_color="#FFFFFF",
    )

    # 6) BGM (선택) — 저음량 배경
    # capcut.add_audio(draft_id=did, audio_url=BGM_URL, volume=0.12)

    result = capcut.save_draft(draft_id=did)
    return result["draft_url"]   # dfd_xxx → 캡컷 폴더로 복사
```

### 연출 규칙을 데이터로 빼기 (확장성)
하드코딩 대신 `template.yaml`로 분리하면 톤별(정보/감성/주식) 템플릿 교체 가능:
```yaml
hook:    { dur: 3.0, font_size: 64, color: "#FFE400", animation: zoom_in }
body:    { transition: fade_in, kenburns: [1.0, 1.08], narration_only: true }
outro:   { dur: 3.0, font_size: 52, color: "#FFFFFF", text: "구독!" }
subtitle:{ font: ZY_Courage, position: bottom }
bgm:     { volume: 0.12 }
```

---

## 5. 미해결 과제 (구현 전 정해야 할 것)

1. **URL 서빙**: `add_video`가 URL을 받음 → 로컬 클립을 어떻게 노출?
   - 옵션 A) CapCutAPI 로컬 파일경로 지원 여부 확인
   - 옵션 B) 임시 로컬 HTTP 서버(`http://localhost:port/clip.mp4`)
   - 옵션 C) 임시 클라우드 업로드(S3 등)
2. **렌더 자동화**: 캡컷 데스크탑 CLI/단축키 매크로로 export 자동화 가능한지.
   불가하면 마감은 수동 유지.
3. **라이선스 소스 자동수집**: Pexels/Pixabay API 쿼리 → 씬 키워드 매칭 품질.
4. **음성 품질**: 한국어 TTS 자연스러움 (ElevenLabs vs 클로바 vs Edge-TTS) 비교.
5. **CapCutAPI 설치/구동**: 로컬 서버 띄우기, 캡컷 버전 호환성, 폰트 리소스 ID.
6. **저작권 가드레일**: 인용 클립 길이 제한·출처 표기 로직.

---

## 6. 구현 로드맵 (데스크탑 착수 시)

- [ ] **M0** CapCutAPI 로컬 설치 → `create_draft`~`save_draft` 최소 1개 드래프트 수동 생성 검증
- [ ] **M1** 오케스트레이터 골격 + `template.yaml` (더미 클립으로 조립 테스트)
- [ ] **M2** 2~3단계(대본·TTS) 붙이기 → 텍스트 한 줄로 나레이션까지
- [ ] **M3** 5단계 Whisper 자막 자동 싱크
- [ ] **M4** 4단계 라이선스 소스 자동수집
- [ ] **M5** 1단계 벤치마킹(주제 추천) — 선택
- [ ] **M6** 7단계 업로드 자동화 — 선택

> 권장 착수 순서: **M0 → M1**. 조립부가 되면 나머지는 재료 공급일 뿐.

---

## 참고 링크
- [CapCutAPI (renqingfei)](https://github.com/renqingfei/CapCutAPI)
- [CapCutAPI MCP 도구 문서](https://github.com/ashreo/CapCutAPI/blob/main/MCP_Documentation_English.md)
- [pyCapCut](https://github.com/GuanYixuan/pyCapCut)
- [capgenie (PyPI)](https://pypi.org/project/capgenie/)
