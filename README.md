# 키트 기록 앱 (안드로이드 APK 만들기)

이 폴더를 GitHub에 올리고, 클라우드에서 APK를 만들어 폰에 설치하는 방법이에요.

1. github.com 에 가입(무료)하고 로그인
2. 오른쪽 위 `+` → `New repository` → 이름 `kit-app`, **Private** 선택 → Create repository
3. 만들어진 화면에서 `uploading an existing file` 링크를 누르고,
   압축을 푼 폴더 안의 **내용물 전체**(src 폴더, pyproject.toml, .github 폴더, README.md)를 끌어다 놓기 → Commit changes
   - `.github` 폴더가 올라가지 않았다면: `Add file` → `Create new file` → 이름칸에
     `.github/workflows/build-apk.yml` 을 입력하고 build-apk.yml 내용을 붙여넣기 → Commit
4. 위쪽 `Actions` 탭 → 왼쪽 `Build APK` → `Run workflow` 버튼 → 초록색 `Run workflow`
5. 10~20분 기다리면 완료(초록 체크). 그 실행을 눌러 맨 아래 `Artifacts`의 `kit-app-apk` 다운로드
6. 압축을 풀면 `.apk` 파일이 있어요. 폰으로 옮겨서 열면 설치돼요
   (`알 수 없는 앱 설치 허용`을 물어보면 허용)

실패(빨간 X)하면 그 실행 화면의 로그 마지막 부분을 캡처해서 Claude에게 보내주세요.
