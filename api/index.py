"""Status page for Vercel deployments.

Vercel runs short-lived serverless functions, so it cannot keep the Discord
gateway connection open. The bot itself runs on Railway (see railway.toml);
this entrypoint only lets Vercel builds succeed and reports that fact.
"""

PAGE = b"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Resources Bot</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.5">
<h1>Resources Discord Bot</h1>
<p>The bot runs as a long-lived worker on Railway with <code>python run.py</code>.</p>
<p>This Vercel deployment is a status page only.</p>
</body>
</html>
"""


def app(environ, start_response):
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(PAGE))),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ],
    )
    return [PAGE]
