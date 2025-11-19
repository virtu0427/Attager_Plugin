# 서버 실행 방법
```
uvicorn app.main:app --reload
```

# API 개요

## 1. `POST /token`
OAuth2 비밀번호 방식으로 로그인한 뒤 액세스 토큰을 반환합니다. 요청 본문은 `username`, `password` 필드를 가진 form-data 여야 합니다. 현재 `jwt-server/app/users.py` 에 정의된 fake DB에는 아래 계정이 등록되어 있고, 각 계정의 tenant 정보도 토큰에 같이 담깁니다.

| 이메일 | 비밀번호 | tenant |
| --- | --- | --- |
| `user2@example.com` | `password1234` | `logistics` |
| `user@example.com` | `password123` | `customer-service` |
| `admin@example.com` | `admin123` | `["logistics", "customer-service"]` |

성공하면 `access_token` 과 `token_type` 이 응답됩니다.

## 2. `GET /users/me`
`Authorization: Bearer <access_token>` 헤더로 요청하면 토큰을 디코딩해서 사용자 정보를 반환합니다.  `users.py` 에서도 보듯이 토큰의 `sub`(이메일)과 `tenant` 클레임이 fake DB의 값과 일치하지 않으면 `404 Not Found` 를 반환합니다. `tenant` 클레임은 문자열 또는 문자열 목록 모두 정규화하여 비교하므로 여러 tenant 를 가진 관리자가 토큰으로 접근할 수 있습니다.

## 상세 흐름

1. `/token` 엔드포인트로 로그인 시도.
2. fake DB 에서 사용자 확인 후 패스워드를 조회해서 비교.
3. `create_access_token` 으로 email + tenant 정보가 포함된 JWT를 발급.
4. 클라이언트가 `/users/me` 로 요청 시 토큰을 검증하고, 입력된 tenant 클레임과 fake DB의 tenant가 정확히 일치하는지 확인.
5. 조건을 만족하면 `User` 모델 형태의 사용자 데이터를 반환.
