import * as Sentry from "@sentry/nextjs";

import {
  getSentryProfilesSampleRate,
  getSentryTracesSampleRate,
  scrubSentryBreadcrumb,
} from "./sentry.shared";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    environment:
      process.env.NEXT_PUBLIC_ENVIRONMENT ||
      process.env.VERCEL_ENV ||
      process.env.NODE_ENV,
    release:
      process.env.APP_RELEASE ||
      process.env.VERCEL_GIT_COMMIT_SHA ||
      process.env.RAILWAY_GIT_COMMIT_SHA ||
      undefined,
    tracesSampleRate: getSentryTracesSampleRate(),
    profilesSampleRate: getSentryProfilesSampleRate(),
    sendDefaultPii: false,
    beforeBreadcrumb(breadcrumb) {
      return scrubSentryBreadcrumb(breadcrumb);
    },
    ...(process.env.NEXT_PUBLIC_SENTRY_TUNNEL
      ? { tunnel: process.env.NEXT_PUBLIC_SENTRY_TUNNEL }
      : {}),
  });
}
