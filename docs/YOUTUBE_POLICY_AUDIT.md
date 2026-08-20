# YouTube policy audit for autonomous Liquid Wire publication

Audit date: 2026-08-20. Scope: one procedural-art channel and the YouTube Data API.

## Authoritative findings

- YouTube's current spam policy prohibits automated or synthetic mass-production
  of high volumes of substantially similar content. Liquid Wire therefore uses
  final-render near-duplicate rejection, family saturation, novelty pressure,
  a default maximum of three scheduled publications per rolling 24 hours, a hard
  ceiling of four and a minimum six-hour learning interval.
  Source: https://support.google.com/youtube/answer/2801973
- API uploads from unaudited projects may be restricted to private, and a scheduled
  `publishAt` value requires private status. The project uploads privately first,
  validates processing and claims, and only then permits the configured transition.
  Source: https://developers.google.com/youtube/v3/docs/videos
- The API has separate upload and general quota limits and requires a compliance
  audit for increased quota. The local tracker models both buckets and never treats
  retry or quota exhaustion as permission to bypass policy.
  Source: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- Disclosure is required for realistic, meaningfully altered or generated scenes.
  Liquid Wire is explicitly non-photorealistic procedural animation with synthetic
  music, so the current policy does not require the realistic-content disclosure.
  Provenance remains recorded internally and descriptions identify the work as
  procedural rather than pretending it was camera-captured.
  Source: https://support.google.com/youtube/answer/14328491

## Operational conclusion

The automation is acceptable only while originality, perceptual diversity,
truthful metadata, quota governance, private validation and the cadence guard all
remain enforced. A kill switch must be used if platform policy changes or the
channel begins producing repetitive outputs despite the novelty gate.
