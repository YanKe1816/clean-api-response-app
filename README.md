# clean-api-response-app

Deterministic, stateless Task App node that cleans valid JSON API responses by removing null and empty values recursively.

## App Metadata

- **APP_NAME:** clean-api-response-app
- **APP_VERSION:** 1.0.0
- **TASK_NAME:** Clean API Response for Use
- **TASK_ROLE:** Data Cleaning Node
- **SUPPORT_EMAIL:** your@email.com

## Guarantees

- Deterministic output (same input -> same output)
- Stateless behavior (no memory, no cache, no storage)
- No randomness
- No external calls
- No side effects

## Rules Enforced

- Remove `null`
- Remove empty string `""`
- Remove empty object `{}`
- Remove empty array `[]`
- Recursive cleaning for nested objects and arrays
- Do not fix invalid JSON
- Do not add fields
- Do not rename fields
- Do not infer data

## Routes

- `GET /health` -> `{"status":"ok"}`
- `GET /privacy` -> `no data stored`
- `GET /terms` -> simple usage terms
- `GET /support` -> support email
- `GET /.well-known/openai-apps-challenge` -> static token
- `GET /mcp` -> tool manifest
- `POST /mcp` -> JSON-RPC (`tools/list`, `tools/call`)

## Run

```bash
uvicorn app_main:app --host 0.0.0.0 --port 10000
```

Render entrypoint: `app_main:app` on port `10000`.

## Tool Contract

### tools/list

Returns one fixed tool:

- **name:** `Clean API Response for Use`
- **description:** `Use this when API response data contains null, empty, or unnecessary fields and needs to be cleaned into usable JSON.`
- **annotations.readOnlyHint:** `true`

### tools/call

`params` format:

```json
{
  "name": "Clean API Response for Use",
  "arguments": {
    "data": {}
  }
}
```

Success format:

```json
{
  "structuredContent": {
    "before": {},
    "after": {}
  }
}
```

Error format:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Invalid or missing data field"
  }
}
```

## Test Case

Input:

```json
{
  "data": {
    "a": 1,
    "b": null,
    "c": "",
    "d": {
      "e": null,
      "f": 2
    }
  }
}
```

Output:

```json
{
  "structuredContent": {
    "before": {
      "a": 1,
      "b": null,
      "c": "",
      "d": {
        "e": null,
        "f": 2
      }
    },
    "after": {
      "a": 1,
      "d": {
        "f": 2
      }
    }
  }
}
```
