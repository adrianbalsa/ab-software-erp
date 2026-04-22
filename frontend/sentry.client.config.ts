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
      process.env.NEXT_PUBLIC_VERCEL_ENV ||
      process.env.NODE_ENV,
    release:
      process.env.NEXT_PUBLIC_APP_RELEASE ||
      process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ||
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
