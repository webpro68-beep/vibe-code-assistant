# Nginx sample for provider callback relay

This Nginx config does not sign webhooks. It simply exposes `/hooks/*` and proxies them to the relay edge worker.
Use it when you want TLS termination, request buffering, or a stable reverse-proxy layer in front of `edge/cloud_run_relay`.
