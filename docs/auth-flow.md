# IFB Auth Flow

This document keeps the My IFB login, token, discovery, and MQTT auth flow in one reusable place.

Do not commit real account tokens, refresh tokens, serial numbers, MAC addresses, OTPs, or extracted app signing values here. Use placeholders in examples.

## Components

Base URLs:

```text
Login/OTP:     https://mcprod.ifbappliances.com/
Cloud/Auth:    https://myifb.ifbcloud.in/api/v5/
MQTT broker:   mqtt2.ifbcloud.in:8883
```

Important headers:

```text
Accept: application/json
Content-Type: application/json; charset=utf-8
x-channel-key: mobile
User-Agent: okhttp/4.12.0 HomeAssistant-IFBWasher/0.1
```

The `mcprod.ifbappliances.com` login endpoints require an OAuth1 `Authorization` header using:

```text
oauth_signature_method = HMAC-SHA256
oauth_version          = 1.0
oauth_consumer_key     = <IFB app consumer key>
oauth_consumer_secret  = <IFB app consumer secret>
oauth_token            = <IFB app OAuth token>
oauth_token_secret     = <IFB app OAuth token secret>
```

In the Home Assistant integration these are stored in the config entry fields:

```text
oauth_consumer_key
oauth_consumer_secret
oauth_token
oauth_token_secret
```

## High-Level Flow

1. User enters My IFB phone/email and OAuth1 app signing values.
2. Integration requests OTP through the signed login API.
3. User enters OTP.
4. Integration verifies OTP and receives a cloud authorization code.
5. Integration exchanges the authorization code plus PKCE verifier for access/refresh tokens.
6. Integration calls cloud APIs with the bearer access token.
7. Integration discovers washer details and MQTT client ID.
8. MQTT uses washer serial as username and bearer token as password.

## PKCE

The integration creates a PKCE verifier/challenge pair for each login attempt:

```text
code_verifier  = base64url(random 64 bytes)
code_challenge = base64url(sha256(code_verifier))
method         = S256
```

The current code sends `code_challenge` and `code_challenge_method` during OTP verification, then sends the original `code_verifier` during token exchange.

## Step 1: Request OTP

Endpoint:

```text
POST https://mcprod.ifbappliances.com/rest/V1/restapi/login
Authorization: OAuth <HMAC-SHA256 OAuth1 header>
```

Phone body:

```json
{
  "method": "phone",
  "phonenumber": "<phone number>",
  "calling_code": "+91"
}
```

Email body:

```json
{
  "method": "mailotp",
  "username": "<email address>",
  "calling_code": "+91"
}
```

Notes:

- Some app captures use `91` and some integration paths use `+91`; keep this visible when debugging server rejection.
- The Android app also has an optional `app-pincode` interceptor. The HA integration does not currently send it.

## Step 2: Verify OTP

Endpoint:

```text
POST https://mcprod.ifbappliances.com/rest/V1/restapi/otpverify
Authorization: OAuth <HMAC-SHA256 OAuth1 header>
```

Phone body:

```json
{
  "method": "phone",
  "phonenumber": "<phone number>",
  "calling_code": "+91",
  "otp": "<otp>",
  "code_challenge": "<pkce challenge>",
  "code_challenge_method": "S256",
  "base_version": 2
}
```

Email body:

```json
{
  "method": "mail",
  "username": "<email address>",
  "calling_code": "+91",
  "otp": "<otp>",
  "code_challenge": "<pkce challenge>",
  "code_challenge_method": "S256",
  "base_version": 2
}
```

Reverse-engineering note:

- The MyIFB app model also references an optional `VerifyToken` field with capital `V` and `T`. If OTP verification starts failing, compare whether the OTP request response includes a token that needs to be sent back as `VerifyToken`.

Expected useful values in a successful response:

```text
authorization code: code or authorization_code
client id:          clientId or client_id
```

Observed app path:

```text
list[0].cloud_data.data.code
list[0].cloud_data.data.client_id
```

The integration searches recursively for these keys so minor response nesting changes are tolerated.

## Step 3: Exchange Token

Endpoint:

```text
POST https://myifb.ifbcloud.in/api/v5/auth/token
```

Body:

```json
{
  "code_verifier": "<pkce verifier>",
  "code": "<authorization code from otpverify>",
  "client_id": "<client id from otpverify>",
  "grant_type": "authorization_code"
}
```

Useful response fields:

```text
access_token  or accessToken or token_val
refresh_token or refreshToken
expires_in    or expiresIn
```

The integration stores:

```text
access_token
refresh_token
client_id
expires_in
token_response
```

## Step 4: Refresh Token

Endpoint:

```text
POST https://myifb.ifbcloud.in/api/v5/auth/token
```

Body:

```json
{
  "refresh_token": "<refresh token>",
  "client_id": "<client id>",
  "grant_type": "refresh_token"
}
```

The integration retries a cloud request once after a `401` by refreshing the access token.

## Step 5: Cloud Discovery

All cloud API calls use:

```text
Authorization: Bearer <access_token>
x-channel-key: mobile
```

Device list:

```text
POST https://myifb.ifbcloud.in/api/v5/device/all
```

The integration selects the best device where:

```text
applianceType == WASHING_MACHINE
```

It prefers Wi-Fi, online, primary, and devices with a MAC address.

MQTT client mapping:

```text
POST https://myifb.ifbcloud.in/api/v5/config/update/mqttClient
```

Expected useful key:

```text
clientID or clientId or client_id
```

Initial progress read:

```text
POST https://myifb.ifbcloud.in/api/v5/device/smart/progress
```

## Step 6: MQTT Auth

Broker:

```text
mqtt2.ifbcloud.in:8883
```

Credentials:

```text
client id: returned by config/update/mqttClient
username:  washer serial
password:  bearer access token
```

Topics:

```text
subscribe: Response/<washer mac>
publish:   Command/<washer mac>
```

Read-status command payload:

```text
63 0A 01 00 01 07 00 00 00 00 76 EC
```

MQTT note:

- Local Python TLS validation may fail against the broker certificate chain. Reverse-engineering tools may allow insecure TLS, but the integration should prefer normal TLS behavior unless a specific workaround is needed.

## Current Integration Files

Main implementation:

```text
custom_components/ifb_washer/config_flow.py
custom_components/ifb_washer/api.py
custom_components/ifb_washer/const.py
```

Reverse-engineering reference:

```text
reverse/ifb_remote/IFB_WASHER_RE_FINDINGS.md
```

## Debug Checklist

When login fails, compare in this order:

1. OAuth1 signing values are present and correct.
2. OAuth base string uses method `POST`, lowercase scheme/host, path only in base URL, and sorted encoded parameters.
3. `calling_code` format is accepted by the API (`+91` vs `91`).
4. OTP verify response includes an authorization code and client ID.
5. `VerifyToken` is required or not required for the current app/API version.
6. Token exchange body uses the original PKCE verifier, not the challenge.
7. Bearer token works against `device/all`.
8. `config/update/mqttClient` returns a client ID before MQTT connect.
