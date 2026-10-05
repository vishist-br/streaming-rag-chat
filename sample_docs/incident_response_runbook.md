# Incident Response Runbook

This runbook describes how Tidewater Robotics engineering handles production incidents affecting the Fleet API, the dashboard or drone connectivity.

## Severity Levels

- SEV1: complete outage or any risk to flight safety. Acknowledge within 5 minutes. Updates every 30 minutes.
- SEV2: a major feature is unavailable for many customers. Acknowledge within 15 minutes. Updates every hour.
- SEV3: degraded performance or a problem with a known workaround. Acknowledge within 4 business hours.

If you are unsure between two levels, choose the more severe one. It can be downgraded later.

## Roles

Every SEV1 and SEV2 incident has an incident commander, who coordinates and makes decisions but does not debug. The communications lead writes status page updates. The scribe keeps a timeline in the incident channel. For SEV3 incidents the on-call engineer holds all three roles.

## On-call

The on-call rotation changes every Tuesday at 10:00 UTC. The primary on-call engineer is paged first; if the page is not acknowledged within 10 minutes it escalates to the secondary, and after a further 10 minutes to the engineering manager. On-call engineers receive one day of compensatory leave for each week on the rotation.

## First Response

1. Acknowledge the page and open an incident channel named `inc-` followed by the date and a short description.
2. Declare a severity level.
3. For SEV1, page the incident commander on duty immediately.
4. Check the deploy log. If a deploy went out in the last 60 minutes, roll it back before investigating further.
5. Post the first status page update.

## Rollback

Rollbacks use the `tw-deploy rollback` command and take about 4 minutes to complete. A rollback does not require approval during an incident. Database migrations are not rolled back automatically; contact the data platform team before reverting a migration.

## Communication

Status page updates must be written in plain language and must not speculate about causes. Customers with an enterprise contract are also notified by email within 30 minutes of a SEV1 being declared.

## Postmortems

A written postmortem is required for every SEV1 and SEV2 incident and is due within 5 business days. Postmortems are blameless: they describe systems and decisions, not individual mistakes. Each postmortem must list at least one action item with an owner and a due date, and is reviewed at the weekly reliability meeting on Thursdays.
