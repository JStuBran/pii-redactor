# PII Redactor

> x402 PII redaction API for AI agents — powered by [Microsoft Presidio](https://microsoft.github.io/presidio/)

Detect and redact Personally Identifiable Information (PII) from text at scale. Built for AI pipelines that need to anonymise user data before sending it to LLMs, logs, or third-party services.

---

## Features

- 🔍 **Analyze** — detect PII entities with positions and confidence scores
- 🔒 **Redact** — replace PII with readable placeholders (`[PERSON]`, `[EMAIL_ADDRESS]`, `[PHONE_NUMBER]`, etc.)
- ⚡ **Fast** — pure Python, no external API calls, runs in-process
- 💳 **x402 payments** — pay-per-call with USDC on Base (ERC-20)
- 🐳 **Docker-ready** — deploy anywhere in minutes

---

## Pricing

| Endpoint | Price per call |
|---|---|
| `POST /api/redact` | **$0.01 USDC** |
| `POST /api/analyze` | **$0.005 USDC** |

Payments use the [x402 protocol](https://x402.org) — include an `X-Payment` header with a valid USDC payment proof on Base mainnet.

---

## Endpoints

### `GET /health`

Returns service status.

```json
{ "status": "ok", "version": "1.0.0" }
```

---

### `POST /api/redact`

Redact PII from an array of texts.

**Request**

```json
{
  "texts": ["Hi, I'm John Smith. Email me at john@example.com or call 555-867-5309."],
  "language": "en",
  "entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
}
```

- `texts` — array of strings (max **10 items**, max **5,000 chars** each)
- `language` — ISO 639-1 code (default `"en"`)
- `entities` — optional filter; omit to detect all supported entity types

**Response**

```json
{
  "results": [
    {
      "redacted_text": "Hi, I'm <PERSON>. Email me at <EMAIL_ADDRESS> or call <PHONE_NUMBER>.",
      "original_length": 70,
      "entities_found": [
        { "entity_type": "PERSON", "count": 1 },
        { "entity_type": "EMAIL_ADDRESS", "count": 1 },
        { "entity_type": "PHONE_NUMBER", "count": 1 }
      ]
    }
  ],
  "meta": {
    "total_entities_redacted": 3,
    "processing_time_ms": 42.5
  }
}
```

---

### `POST /api/analyze`

Detect PII without modifying the text.

**Request** — same schema as `/api/redact`

**Response**

```json
{
  "results": [
    {
      "entities": [
        { "entity_type": "PERSON",       "text": "John Smith",       "start": 8,  "end": 18, "score": 0.85 },
        { "entity_type": "EMAIL_ADDRESS", "text": "john@example.com", "start": 29, "end": 45, "score": 1.0  },
        { "entity_type": "PHONE_NUMBER", "text": "555-867-5309",     "start": 54, "end": 66, "score": 0.75 }
      ]
    }
  ]
}
```

---

## x402 Payment Flow

All `/api/*` routes require an `X-Payment` header when `PAYMENT_REQUIRED=true`.

If the header is missing, the service returns **HTTP 402** with a machine-readable payment descriptor:

```json
{
  "x402Version": 1,
  "accepts": [
    {
      "scheme": "exact",
      "network": "eip155:8453",
      "maxAmountRequired": "10000",
      "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "payTo": "<WALLET_ADDRESS>",
      "description": "PII redaction",
      "mimeType": "application/json",
      "maxTimeoutSeconds": 300,
      "extra": { "name": "USDC", "decimals": 6 }
    }
  ]
}
```

Use an x402-compatible client (e.g. the [x402 Python SDK](https://github.com/coinbase/x402)) to automatically handle payment and retry.

---

## Supported Entity Types

Presidio supports 20+ entity types out of the box, including:

| Type | Example |
|---|---|
| `PERSON` | John Smith |
| `EMAIL_ADDRESS` | john@example.com |
| `PHONE_NUMBER` | 555-867-5309 |
| `LOCATION` | New York |
| `CREDIT_CARD` | 4111 1111 1111 1111 |
| `US_SSN` | 078-05-1120 |
| `US_PASSPORT` | A1234567 |
| `IBAN_CODE` | GB82WEST12345698765432 |
| `IP_ADDRESS` | 192.168.1.1 |
| `URL` | https://example.com |
| `DATE_TIME` | January 1, 2024 |
| `NRP` | American |
| `MEDICAL_LICENSE` | MD123456 |

---

## Deployment

### Railway (recommended)

1. Fork this repo
2. Connect to [Railway](https://railway.app)
3. Set environment variables:
   - `WALLET_ADDRESS` — your USDC wallet on Base
   - `PAYMENT_REQUIRED` — `true` (default) or `false` for testing
4. Deploy — Railway auto-detects the Dockerfile

### Docker

```bash
docker build -t pii-redactor .
docker run -p 8080:8080 \
  -e WALLET_ADDRESS=0xYourWalletAddress \
  -e PAYMENT_REQUIRED=false \
  pii-redactor
```

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg

cp .env.example .env
# Edit .env — set PAYMENT_REQUIRED=false for local testing

uvicorn main:app --reload
```

---

## Example cURL

```bash
# Disable payment check for testing
curl -X POST http://localhost:8080/api/redact \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["My name is Alice Johnson and my email is alice@company.org"],
    "language": "en"
  }'
```

With x402 payment header:

```bash
curl -X POST https://pii-redactor.up.railway.app/api/redact \
  -H "Content-Type: application/json" \
  -H "X-Payment: <payment-proof>" \
  -d '{"texts": ["Contact Bob at bob@example.com"]}'
```

---

## License

MIT
