# Tidewater Fleet API Reference

The Fleet API lets you manage drones, schedule missions and download survey data. The base URL is `https://api.tidewater.example/v2`.

## Authentication

Every request must include an API key in the `X-Tidewater-Key` header. Keys are created in the dashboard under Settings and are shown only once. A key expires 90 days after it is created unless it is rotated. Requests without a valid key receive a 401 response.

## Rate Limits

Each API key may make 120 requests per minute. Bulk export endpoints have a separate limit of 5 requests per minute. When you exceed a limit the API returns status 429 with a `Retry-After` header that gives the number of seconds to wait.

## Pagination

List endpoints return 50 items per page by default and at most 200. Pass the `cursor` value from the previous response to fetch the next page. Cursors expire after 10 minutes.

## Endpoints

### List drones

`GET /drones` returns every drone in your organisation with its serial number, firmware version and last known position.

### Create a mission

`POST /missions` schedules a survey flight. The body must contain a `drone_id`, a `flight_plan_id` and a `start_time` in ISO 8601 format. A mission can be scheduled at most 30 days in advance. The response contains the mission `id` and a status of `scheduled`.

### Cancel a mission

`DELETE /missions/{id}` cancels a mission. Cancellation is only possible until 5 minutes before the start time; after that the API returns status 409.

### Download survey data

`GET /missions/{id}/export` returns a signed download link for the mission's images and logs. The link is valid for 15 minutes. Survey data is retained for 180 days after the flight and is then deleted.

## Webhooks

The API can send a POST request to your server when a mission changes state. Events are `mission.started`, `mission.completed` and `mission.failed`. Each delivery is signed with HMAC-SHA256 in the `X-Tidewater-Signature` header. If your server does not answer with a 2xx status within 10 seconds, delivery is retried up to 6 times with exponential backoff.

## Errors

Errors use a JSON body with a `code` and a `message`.

- `invalid_flight_plan`: the flight plan crosses a restricted zone or exceeds the height limit.
- `drone_offline`: the drone has not reported in for more than 24 hours.
- `quota_exceeded`: the organisation has used its monthly allowance of 500 missions.
- `firmware_too_old`: the drone runs firmware older than 3.2.0 and must be updated first.
